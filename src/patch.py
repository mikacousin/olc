# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
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
from __future__ import annotations

import typing
from typing import Optional

import numpy as np
from olc.define import MAX_CHANNELS, NB_UNIVERSES, UNIVERSES, is_int

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


# pylint: disable=too-many-instance-attributes
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

    universes: list[int]
    channels: dict[int, list[list[Optional[int]]]]
    outputs: dict[int, dict[int, list[int]]]

    def __init__(self, universes: list[int]) -> None:
        self.universes = universes
        self.channels = {}
        self.outputs = {}
        self.on_patch_empty_cb: typing.Callable[[], None] | None = None
        self.on_unpatch_cb: typing.Callable[[int, int], None] | None = None
        self._numpy_cache_dirty = True
        self.is_patched_mask = np.zeros(MAX_CHANNELS, dtype=bool)
        self.map_src_channels = np.array([], dtype=np.intp)
        self.map_dst_universes = np.array([], dtype=np.intp)
        self.map_dst_outputs = np.array([], dtype=np.intp)
        self.map_dst_curves = np.array([], dtype=np.intp)

        self.patch_1on1()

    def invalidate_cache(self) -> None:
        """Invalidate the numpy cache."""
        self._numpy_cache_dirty = True

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
        if self.on_patch_empty_cb:
            self.on_patch_empty_cb()
        self.outputs = {}
        for channel in range(1, MAX_CHANNELS + 1):
            self.channels[channel] = [[None, None]]
        self._numpy_cache_dirty = True

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
            univ: Universe number (one of UNIVERSES in define module)
            curve: Curve number (default 0, Linear Curve)
        """
        if self.channels[channel] == [[None, None]]:
            self.channels[channel] = [[output, univ]]
        elif [output, univ] not in self.channels[channel]:
            self.channels[channel].append([output, univ])
        if univ not in self.outputs:
            self.outputs[univ] = {}
        self.outputs[univ][output] = [channel, curve]
        self._numpy_cache_dirty = True

    def unpatch(self, channel: int, output: int, univ: int) -> None:
        """Unpatch an output from a channel

        Args:
            channel: Channel number (1-MAX_CHANNELS)
            output: Dimmer number (1-512)
            univ: Universe number (one of UNIVERSES in define module)
        """
        del self.outputs[univ][output]
        self.channels[channel].remove([output, univ])
        if not self.channels[channel]:
            self.channels[channel] = [[None, None]]
        index = self.universes.index(univ)
        if self.on_unpatch_cb:
            self.on_unpatch_cb(index, output - 1)
        self._numpy_cache_dirty = True

    def update_numpy_cache_if_dirty(self) -> None:
        """Update cached mappings if dirty."""
        if getattr(self, "_numpy_cache_dirty", True) or not hasattr(
            self, "map_src_channels"
        ):
            self._update_numpy_cache()
            self._numpy_cache_dirty = False

    def _update_numpy_cache(self) -> None:
        """Update cached arrays for fast block operations."""
        # 1. Boolean mask of patched channels (True if patched, False if not)
        mask = np.zeros(MAX_CHANNELS, dtype=bool)
        for channel in range(1, MAX_CHANNELS + 1):
            if channel in self.channels:
                if (
                    self.channels[channel] != [[None, None]]
                    and None not in self.channels[channel][0]
                ):
                    mask[channel - 1] = True
        self.is_patched_mask = mask

        # 2. Flat indexing arrays for fast block level distribution
        src_channels = []
        dst_universes = []
        dst_outputs = []
        dst_curves = []

        for channel, outputs in self.channels.items():
            if outputs == [[None, None]] or None in outputs[0]:
                continue
            for out in outputs:
                output = out[0]
                universe = out[1]
                if universe and output:
                    src_channels.append(channel - 1)
                    dst_universes.append(UNIVERSES.index(universe))
                    dst_outputs.append(output - 1)

                    # Curve number
                    curve_numb = 0
                    if universe in self.outputs and output in self.outputs[universe]:
                        curve_numb = self.outputs[universe][output][1]
                    dst_curves.append(curve_numb)

        self.map_src_channels = np.array(src_channels, dtype=np.intp)
        self.map_dst_universes = np.array(dst_universes, dtype=np.intp)
        self.map_dst_outputs = np.array(dst_outputs, dtype=np.intp)
        self.map_dst_curves = np.array(dst_curves, dtype=np.intp)

    def get_first_patched_channel(self) -> int:
        """Return first patched channel

        Returns:
            Channel number (1-MAX_CHANNELS)
        """
        self.update_numpy_cache_if_dirty()
        indices = np.nonzero(self.is_patched_mask)[0]
        return int(indices[0]) + 1 if len(indices) > 0 else 1

    def get_last_patched_channel(self) -> int:
        """Return last patched channel

        Returns:
            Channel number (1-MAX_CHANNELS)
        """
        self.update_numpy_cache_if_dirty()
        indices = np.nonzero(self.is_patched_mask)[0]
        return int(indices[-1]) + 1 if len(indices) > 0 else 1


class PatchByOutputs:
    """Manipulate Patch using Outputs order"""

    def __init__(self, app: Application, patch: DMXPatch) -> None:
        self.app = app
        self.outputs = []
        self.last = 0
        self.patch = patch

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
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/patch/selected_outputs", self.get_selected())
        tab = self.app.tabs.tabs["patch_outputs"] if self.app.tabs else None
        if tab is not None:
            typing.cast(typing.Any, tab).select_outputs()
        if self.app.window is not None:
            self.app.window.commandline.set_string("")

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
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/patch/selected_outputs", self.get_selected())
        tab = self.app.tabs.tabs["patch_outputs"] if self.app.tabs else None
        if tab is not None:
            typing.cast(typing.Any, tab).select_outputs()
        if self.app.window is not None:
            self.app.window.commandline.set_string("")

    def add_output(self) -> None:
        """Add an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            self.outputs.append(output_index)
            self.last = output_index
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/patch/selected_outputs", self.get_selected())
        tab = self.app.tabs.tabs["patch_outputs"] if self.app.tabs else None
        if tab is not None:
            typing.cast(typing.Any, tab).select_outputs()
        if self.app.window is not None:
            self.app.window.commandline.set_string("")

    def del_output(self) -> None:
        """Remove an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            self.outputs.remove(output_index)
            self.last = output_index
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/patch/selected_outputs", self.get_selected())
        tab = self.app.tabs.tabs["patch_outputs"] if self.app.tabs else None
        if tab is not None:
            typing.cast(typing.Any, tab).select_outputs()
        if self.app.window is not None:
            self.app.window.commandline.set_string("")

    def patch_channel(self, several: bool) -> None:
        """Patch

        Args:
            several: True if increment channels for each output,
                     False if same channel for every output
        """
        channel = self._string_to_channel()
        if channel is None:
            return
        self.__for_each_output(channel, several)
        if self.app.window is not None:
            self.app.window.live_view.channels_view.update()
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/patch/selected_outputs", self.get_selected())
        tab = self.app.tabs.tabs["patch_outputs"] if self.app.tabs else None
        if tab is not None:
            typing.cast(typing.Any, tab).refresh()
            # Select next output
            output_index = self.last
            if output_index < NB_UNIVERSES * 512:
                output_index += 1
            output, universe = self.get_output_universe(output_index)
            if self.app.window is not None:
                self.app.window.commandline.set_string(f"{output}.{universe}")
            self.select_output()
        self.app.core.lightshow.set_modified()
        if self.app.window is not None:
            self.app.window.commandline.set_string("")

    def __for_each_output(self, channel: int, several: bool) -> None:
        for i, output_index in enumerate(self.outputs):
            output, univ = self.get_output_universe(output_index)
            if output and univ:
                # Unpatch if no channel
                if not channel:
                    self.__unpatch(output, univ)
                else:
                    chan = channel + i if several else channel
                    self.app.core.action_registry.execute(
                        "patch.add_output", chan, output, univ
                    )

    def __unpatch(self, output: int, univ: int) -> None:
        if univ in self.patch.outputs and output in self.patch.outputs[univ]:
            self.app.core.action_registry.execute("patch.unpatch_output", output, univ)

    def get_output_universe(self, out: int) -> tuple[Optional[int], Optional[int]]:
        """Returns output.universe corresponding to output index (1-NB_UNIVERSES * 512)

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
        if (0 < out <= 512) and univ in UNIVERSES:
            univ_index = UNIVERSES.index(univ)
            output = out + (univ_index * 512)
        return output

    def _string_to_output(self) -> tuple[Optional[int], Optional[int]]:
        output = None
        universe = None
        if self.app.window is None:
            return (None, None)
        keystring = self.app.window.commandline.get_string()
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
        if self.app.window is None:
            return None
        keystring = self.app.window.commandline.get_string()
        if not keystring:
            keystring = "0"
        if not is_int(keystring):
            return None
        return int(keystring)
