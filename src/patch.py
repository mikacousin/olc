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
from typing import Dict, List, Optional, Tuple
from olc.define import App, MAX_CHANNELS, NB_UNIVERSES, UNIVERSES, is_int


class DMXPatch:
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
    channels: Dict[int, List[List[Optional[int]]]]
    outputs: Dict[int, Dict[int, List[int]]]

    def __init__(self, universes: List[int]):
        self.universes = universes
        self.channels = {}
        self.outputs = {}
        self.by_outputs = PatchByOutputs()

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

    def is_patched(self, channel: int) -> bool:
        """Test if channel is patched

        Args:
            channel: [1 - MAX_CHANNELS]

        Returns:
            True if patched, else False
        """
        if None in self.channels[channel][0]:
            return False
        return True

    def patch_empty(self) -> None:
        """Set Dimmers patch to Zero"""
        self.outputs = {}
        for channel in range(1, MAX_CHANNELS + 1):
            self.channels[channel] = [[None, None]]

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
        if self.channels[channel] == [[None, None]]:
            del self.channels[channel]
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
            self.channels[channel] = [[None, None]]
        index = self.universes.index(univ)
        App().dmx.frame[index][output - 1] = 0

    def get_first_patched_channel(self) -> int:
        """Return first patched channel

        Returns:
            Channel number (1-MAX_CHANNELS)
        """
        for channel in range(MAX_CHANNELS):
            if self.is_patched(channel + 1):
                break
        return channel + 1

    def get_last_patched_channel(self) -> int:
        """Return last patched channel

        Returns:
            Channel number (1-MAX_CHANNELS)
        """
        for channel in range(MAX_CHANNELS, 0, -1):
            if self.is_patched(channel):
                break
        return channel


class PatchByOutputs:
    """Manipulate Patch using Outputs order"""

    def __init__(self):
        self.outputs = []
        self.last = 0

    def get_selected(self) -> str:
        """Return selected outputs

        Returns:
            String like "1, 2, 3, 4"
        """
        outs = []
        for out in self.outputs:
            output, universe = self.get_output_universe(out)
            outs.append(f"{output}.{universe}")
        string = ", ".join(str(out) for out in outs)
        return string

    def select_output(self) -> None:
        """Select one output"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            self.outputs = [output_index]
            self.last = output_index
        else:
            self.outputs = []
            self.last = 0
        if App().osc:
            App().osc.client.send(
                "/olc/patch/selected_outputs", ("s", self.get_selected())
            )
        if App().tabs.tabs["patch_outputs"]:
            App().tabs.tabs["patch_outputs"].select_outputs()
        App().window.commandline.set_string("")

    def thru(self) -> None:
        """Thru output"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            if output_index > self.last:
                for out in range(self.last + 1, output_index + 1):
                    self.outputs.append(out)
            else:
                for out in range(self.last - 1, output_index - 1, -1):
                    self.outputs.append(out)
            self.last = output_index
        if App().osc:
            App().osc.client.send(
                "/olc/patch/selected_outputs", ("s", self.get_selected())
            )
        if App().tabs.tabs["patch_outputs"]:
            App().tabs.tabs["patch_outputs"].select_outputs()
        App().window.commandline.set_string("")

    def add_output(self) -> None:
        """Add an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            self.outputs.append(output_index)
            self.last = output_index
        if App().osc:
            App().osc.client.send(
                "/olc/patch/selected_outputs", ("s", self.get_selected())
            )
        if App().tabs.tabs["patch_outputs"]:
            App().tabs.tabs["patch_outputs"].select_outputs()
        App().window.commandline.set_string("")

    def del_output(self) -> None:
        """Remove an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            self.outputs.remove(output_index)
            self.last = output_index
        if App().osc:
            App().osc.client.send(
                "/olc/patch/selected_outputs", ("s", self.get_selected())
            )
        if App().tabs.tabs["patch_outputs"]:
            App().tabs.tabs["patch_outputs"].select_outputs()
        App().window.commandline.set_string("")

    def patch_channel(self, several) -> None:
        """Patch

        Args:
            several: True if increment channels for each output,
                     False if same channel for every output
        """
        channel = self._string_to_channel()
        if channel is None:
            return
        self.__for_each_output(channel, several)
        App().window.live_view.channels_view.update()
        if App().osc:
            App().osc.client.send(
                "/olc/patch/selected_outputs", ("s", self.get_selected())
            )
        if App().tabs.tabs["patch_outputs"]:
            App().tabs.tabs["patch_outputs"].refresh()
            # Select next output
            output_index = self.last
            if output_index < NB_UNIVERSES * 512:
                output_index += 1
            output, universe = App().patch.by_outputs.get_output_universe(output_index)
            App().window.commandline.set_string(f"{output}.{universe}")
            App().patch.by_outputs.select_output()
        App().ascii.set_modified()
        App().window.commandline.set_string("")

    def __for_each_output(self, channel, several) -> None:
        for i, output_index in enumerate(self.outputs):
            output, univ = self.get_output_universe(output_index)
            if output and univ:
                # Unpatch if no channel
                if not channel:
                    self.__unpatch(output, univ)
                else:
                    old_channel = None
                    if (
                        univ in App().patch.outputs
                        and output in App().patch.outputs[univ]
                    ):
                        old_channel = App().patch.outputs[univ][output][0]
                    # Unpatch old value if exist
                    if old_channel:
                        App().patch.unpatch(old_channel, output, univ)
                    if several:
                        # Patch Channel : increment channels for each output
                        App().patch.add_output(channel + i, output, univ)
                    else:
                        # Patch Channel : same channel for every outputs
                        App().patch.add_output(channel, output, univ)
                # Refresh LiveView
                if 0 < channel <= MAX_CHANNELS:
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][output - 1]
                    widget = App().window.live_view.channels_view.get_channel_widget(
                        channel
                    )
                    widget.level = level
                    widget.queue_draw()

    def __unpatch(self, output, univ) -> None:
        if univ in App().patch.outputs and output in App().patch.outputs[univ]:
            chan = App().patch.outputs[univ][output][0]
            App().patch.unpatch(chan, output, univ)

    def get_output_universe(self, out: int) -> Tuple[Optional[int], Optional[int]]:
        """Returns output.universe correponding to output index (1 - NB_UNIVERSES * 512)

        Args:
            out: output index

        Returns:
            output, universe
        """
        output = None
        universe = None
        if 0 < out <= (NB_UNIVERSES * 512):
            univ_index = int((out - 1) / 512)
            universe = UNIVERSES[univ_index]
            output = out - (univ_index * 512)
        return (output, universe)

    def _get_output_index(
        self, out: Optional[int], univ: Optional[int]
    ) -> Optional[int]:
        output = None
        if out is None or univ is None:
            return None
        if (0 < out <= 512) and univ in App().universes:
            univ_index = App().universes.index(univ)
            output = out + (univ_index * 512)
        return output

    def _string_to_output(self) -> Tuple[Optional[int], Optional[int]]:
        output = None
        universe = None
        keystring = App().window.commandline.get_string()
        if not keystring:
            keystring = "0"
        if "." in keystring:
            if keystring.index("."):
                split = keystring.split(".")
                output = int(split[0])
                if 0 < output <= 512:
                    universe = int(split[1])
        else:
            output = int(keystring)
            universe = UNIVERSES[0]
        return (output, universe)

    def _string_to_channel(self) -> Optional[int]:
        keystring = App().window.commandline.get_string()
        if not keystring:
            keystring = "0"
        if not is_int(keystring):
            return None
        return int(keystring)
