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
"""Patch manipulation sorted by outputs."""

from __future__ import annotations

import typing
from typing import Optional

from olc.define import is_int

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.patch import DMXPatch


class PatchByOutputs:
    """Manipulate Patch using Outputs order"""

    app: Application | CoreApplication
    outputs: list[int]
    last: int
    patch: DMXPatch

    def __init__(self, app: Application | CoreApplication, patch: DMXPatch) -> None:
        self.app = app
        self.outputs = []
        self.last = 0
        self.patch = patch

    @property
    def commandline(self) -> CoreCommandLine:
        """Get the logical command line instance."""
        return self.app.core.commandline

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
            outputs = [output_index]
            last = output_index
        else:
            outputs = []
            last = 0
        self.app.core.action_registry.execute("output.select", outputs, last)

    def thru(self) -> None:
        """Thru output"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            new_outputs = list(self.outputs)
            if output_index > self.last:
                for out in range(self.last + 1, output_index + 1):
                    new_outputs.append(out)
            else:
                for out in range(self.last - 1, output_index - 1, -1):
                    new_outputs.append(out)
            self.app.core.action_registry.execute(
                "output.select", new_outputs, output_index
            )

    def add_output(self) -> None:
        """Add an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            new_outputs = list(self.outputs)
            new_outputs.append(output_index)
            self.app.core.action_registry.execute(
                "output.select", new_outputs, output_index
            )

    def del_output(self) -> None:
        """Remove an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            new_outputs = list(self.outputs)
            if output_index in new_outputs:
                new_outputs.remove(output_index)
            self.app.core.action_registry.execute(
                "output.select", new_outputs, output_index
            )

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

        # Select next output
        output_index = self.last
        if output_index < len(self.patch.universes) * 512:
            output_index += 1
        output, universe = self.get_output_universe(output_index)
        self._set_commandline_string(f"{output}.{universe}")
        self.select_output()

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

    def _get_commandline_string(self) -> str:
        return self.commandline.get_string()

    def _set_commandline_string(self, value: str) -> None:
        self.app.core.action_registry.execute("commandline.set", value)

    def get_output_universe(self, out: int) -> tuple[Optional[int], Optional[int]]:
        """Returns output.universe corresponding to output index
        (1 to count of universes * 512).

        Args:
            out: output index

        Returns:
            output, universe
        """
        output = None
        universe = None
        max_out = len(self.patch.universes) * 512
        if 0 < out <= max_out:
            univ_index = int((out - 1) / 512)
            universe = self.patch.universes[univ_index]
            output = out - (univ_index * 512)
        return (output, universe)

    def _get_output_index(
        self, out: Optional[int], univ: Optional[int]
    ) -> Optional[int]:
        output = None
        if out is None or univ is None:
            return None
        if (0 < out <= 512) and univ in self.patch.universes:
            univ_index = self.patch.universes.index(univ)
            output = out + (univ_index * 512)
        return output

    def _string_to_output(self) -> tuple[Optional[int], Optional[int]]:
        output = None
        universe = None
        keystring = self._get_commandline_string()
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
            universe = self.patch.universes[0] if self.patch.universes else 1
        return (output, universe)

    def _string_to_channel(self) -> Optional[int]:
        keystring = self._get_commandline_string()
        if not keystring:
            keystring = "0"
        if not is_int(keystring):
            return None
        return int(keystring)


__all__ = ["PatchByOutputs"]
