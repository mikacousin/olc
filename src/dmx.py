# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
import time
from typing import Dict, List
from olc.define import UNIVERSES, MAX_CHANNELS, NB_UNIVERSES, App


class Dmx:
    """Thread to send levels to Ola"""

    grand_master: int
    frame: List[array.array]
    sequence: array.array
    user: array.array
    pause: bool
    loop: bool

    def __init__(self):
        self.grand_master = 255
        self.frame = []
        # Dimers levels
        self.sequence = array.array("B", [0] * MAX_CHANNELS)
        # User levels
        self.user = array.array("h", [-1] * MAX_CHANNELS)
        # To test outputs
        self.user_outputs = {}
        # DMX values send to Ola
        for _ in range(NB_UNIVERSES):
            self.frame.append(array.array("B", [0] * 512))
        self.pause = False
        App().ola.thread.wrapper.AddEvent(30, self.send)
        self.loop = False

    def send(self) -> None:
        """Send DMX values to Ola"""
        if not self.pause:
            App().ola.thread.wrapper.AddEvent(30, self.send)
        univ = []  # To store universes changed
        for channel, outputs in App().patch.channels.items():
            self.loop = True
            for i in outputs:
                output = i[0]
                universe = i[1]
                if universe not in univ:
                    univ.append(universe)
                # Level in Sequence
                level = self.sequence[channel - 1]
                widget = App().window.live_view.channels_view.get_channel_widget(
                    channel
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
                    if channel in inde.channels and inde.dmx[channel - 1] > level_inde:
                        level_inde = inde.dmx[channel - 1]
                if level_inde != -1:
                    level = level_inde
                    widget.color_level = {"red": 0.4, "green": 0.4, "blue": 0.7}
                # Curve
                curve_numb = App().patch.outputs[universe][output][1]
                if curve_numb:
                    curve = App().curves.get_curve(curve_numb)
                    level = curve.values.get(level, 0)
                # Grand Master
                level = round(level * (self.grand_master / 255))
                # Update output level
                index = App().universes.index(universe)
                self.frame[index][output - 1] = level
        self.loop = False
        if self.user_outputs:
            univ = self._send_user_outputs(univ)
        # Send DMX frames to Ola
        for universe in univ:
            index = App().universes.index(universe)
            App().ola.thread.client.SendDmx(universe, self.frame[index], self.sent)

    def set_pause(self, pause: bool) -> None:
        """Set pause for DMX sent

        Args:
            pause: True = pause
        """
        self.pause = pause
        if pause:
            # Wait to avoid "dictionary changed size during iteration"
            while self.loop:
                time.sleep(0.01)
        else:
            App().ola.thread.wrapper.AddEvent(30, self.send)

    def sent(self, state) -> None:  # pylint: disable=E0601
        """DmxSent callback

        Args:
            state: OlaClient.RequestStatus
        """
        if not state.Succeeded():
            App().ola.thread.wrapper.Stop()
            print("Error with olad Wrapper!")

    def _send_user_outputs(self, univ) -> List[int]:
        """Outputs at level on user demand

        Args:
            univ: Universes with level modification

        Returns:
            Universes with level modification updated
        """
        user_outputs_to_delete = []
        for output, level in self.user_outputs.items():
            out = output[0]
            universe = output[1]
            if universe not in univ:
                univ.append(universe)
            index = App().universes.index(universe)
            self.frame[index][out - 1] = level
            if not level:
                user_outputs_to_delete.append(output)
        for output in user_outputs_to_delete:
            self.user_outputs.pop(output)
        return univ

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
        for universe in UNIVERSES:
            index = App().universes.index(universe)
            self.frame[index] = array.array("B", [0] * 512)
            App().ola.thread.client.SendDmx(universe, self.frame[index], self.sent)

    def send_user_output(self, output: int, universe: int, level: int) -> None:
        """Send level to an output

        Args:
            output: Output number (1-512)
            universe: Universe number (one in UNIVERSES)
            level: Output level (0-255)
        """
        self.user_outputs[(output, universe)] = level
        index = App().universes.index(universe)
        self.frame[index][output - 1] = level
        if not level:
            self.user_outputs.pop((output, universe))
        App().ola.thread.client.SendDmx(universe, self.frame[index], self.sent)


class PatchDmx:
    """To store and manipulate DMX patch
    Default patch is 1:1 (channel = output)

    Attributes:
        channels: Dictionary of [output (1-512), universe (0-NB_UNIVERSES)] for each
            channel (1-MAX_CHANNELS).
            For example, channel 5 could be patched on [1, 0] and [5, 1] i.e. output 1
            of universe 1 and output 5 of universe 2
        outputs: Dictionaries of [channel (1-MAX_CHANNELS), curve number] for each
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
        #             "Curve",
        #             App().curves.get_curve(chan_dic[1]).name,
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

    def add_output(self, channel: int, output: int, univ: int, curve: int = 0) -> None:
        """Add an output to a channel

        Args:
            channel: Channel number (1-MAX_CHANNELS)
            output: Dimmer number (1-512)
            univ: Universe number (one of UNIVERSES in define.py)
            curve: Curve number (default 0, Linear Curve)
        """
        if channel not in self.channels:
            self.channels[channel] = [[output, univ]]
        else:
            self.channels[channel].append([output, univ])
        if univ not in self.outputs:
            self.outputs[univ] = {}
        self.outputs[univ][output] = [channel, curve]

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
