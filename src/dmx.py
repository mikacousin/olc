# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import array
import threading
from typing import Dict, List

from olc.define import MAX_CHANNELS, NB_UNIVERSES, App


class Dmx(threading.Thread):
    """Thread to send levels to Ola"""

    grand_master: int
    frame: List[array.array]
    sequence: array.array
    user: array.array

    def __init__(self):
        threading.Thread.__init__(self)
        self.grand_master = 255
        self.frame = []
        # Dimers levels
        self.sequence = array.array("B", [0] * MAX_CHANNELS)
        # User levels
        self.user = array.array("h", [-1] * MAX_CHANNELS)

    def run(self) -> None:
        # les valeurs DMX echangées avec Ola
        for _ in range(NB_UNIVERSES):
            self.frame.append(array.array("B", [0] * 512))

    def send(self) -> None:
        """Send DMX values to Ola"""
        univ = []  # To store universes changed
        for channel, outputs in App().patch.channels.items():
            for i in outputs:
                output = i[0]
                universe = i[1]
                if universe not in univ:
                    univ.append(universe)
                # Level in Sequence
                level = self.sequence[channel - 1]
                widget = (
                    App()
                    .window.channels_view.flowbox.get_child_at_index(channel - 1)
                    .get_child()
                )
                widget.color_level = {"red": 0.9, "green": 0.9, "blue": 0.9}
                if not App().sequence.on_go and self.user[channel - 1] != -1:
                    # If not on Go, use user level
                    level = self.user[channel - 1]
                for master in App().masters:
                    # If master level is bigger, use it
                    if master.dmx[channel - 1] > level:
                        level = master.dmx[channel - 1]
                        widget.color_level = {"red": 0.4, "green": 0.7, "blue": 0.4}
                # Independents
                level_inde = -1
                for inde in App().independents.independents:
                    if (
                        channel - 1 in inde.channels
                        and inde.dmx[channel - 1] > level_inde
                    ):
                        level_inde = inde.dmx[channel - 1]
                if level_inde != -1:
                    level = level_inde
                    widget.color_level = {"red": 0.4, "green": 0.4, "blue": 0.7}
                # Proportional patch level
                level = level * (App().patch.outputs[universe][output][1] / 100)
                # Grand Master
                level = round(level * (self.grand_master / 255))
                # Update output level
                index = App().universes.index(universe)
                self.frame[index][output - 1] = level
        # Send DMX frames to Ola
        for universe in univ:
            index = App().universes.index(universe)
            App().ola_thread.ola_client.SendDmx(universe, self.frame[index])


class PatchDmx:
    """To store and manipulate DMX patch
    Default patch is 1:1 (channel = output)

    Attributes:
        channels: Dictionary of [output (1-512), universe (0-NB_UNIVERSES)] for each
            channel (1-MAX_CHANNELS).
            For example, channel 5 could be patched on [1, 0] and [5, 1] i.e. output 1
            of universe 1 and output 5 of universe 2
        outputs: Dictionaries of [channel (1-MAX_CHANNELS), level (0-100)] for each
            output (1-512) of each universe (0-NB_UNIVERSES)
        universes: List of universes to use
    """

    universes: List[int]
    channels: Dict[int, List[List[int]]]
    outputs: Dict[int, Dict[int, List[int]]]

    def __init__(self, universes: List[int]):
        self.universes = universes
        self.channels = {}
        self.outputs = {}

        self.patch_1on1()

        # for chan, chan_list in self.channels.items():
        #     for out in chan_list:
        #         print("Channel", chan, "Output", out[0], "Universe", out[1])
        # for key, value in self.outputs.items():
        #     for output, chan_dic in value.items():
        #         print(
        #             "Univers",
        #             key,
        #             "Output",
        #             output,
        #             "Channel",
        #             chan_dic[0],
        #             "Level",
        #             chan_dic[1],
        #         )

    def patch_empty(self) -> None:
        """Set Dimmers patch to Zero"""
        self.channels = {}
        self.outputs = {}

    def patch_1on1(self) -> None:
        """Set patch 1:1"""
        self.patch_empty()
        for channel in range(1, MAX_CHANNELS + 1):
            index = int((channel - 1) / 512)
            univ = self.universes[index]
            output = channel - (index * 512)
            self.add_output(channel, output, univ)

    def add_output(
        self, channel: int, output: int, univ: int, level: int = 100
    ) -> None:
        """Add an output to a channel

        Args:
            channel: Channel number (1-MAX_CHANNELS)
            output: Dimmer number (1-512)
            univ: Universe number (one of UNIVERSES in define.py)
            level: Max level (0-100)
        """
        if channel not in self.channels:
            self.channels[channel] = [[output, univ]]
        else:
            self.channels[channel].append([output, univ])
        if univ not in self.outputs:
            self.outputs[univ] = {}
        self.outputs[univ][output] = [channel, level]

    def unpatch(self, channel: int, output: int, univ: int) -> None:
        """Unpatch an output from a channel

        Args:
            channel: Channel number (1-MAX_CHANNELS)
            output: Dimmer number (1-512)
            univ: Universe number (one of UNIVERSES in define.py)
        """
        del self.outputs[univ][output]
        self.channels[channel].remove([output, univ])
        if not self.channels[channel]:
            del self.channels[channel]
        index = self.universes.index(univ)
        App().dmx.frame[index][output - 1] = 0

    def get_first_patched_channel(self) -> int:
        """Return first patched channel

        Returns:
            Channel number (1-MAX_CHANNELS)
        """
        for channel in range(MAX_CHANNELS):
            if channel + 1 in self.channels:
                break
        return channel + 1

    def get_last_patched_channel(self) -> int:
        """Return last patched channel

        Returns:
            Channel number (1-MAX_CHANNELS)
        """
        for channel in range(MAX_CHANNELS, 0, -1):
            if channel in self.channels:
                break
        return channel
