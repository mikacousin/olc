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

from olc.core.action import Action

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class PatchAddOutputAction(Action):
    """Action to associate a DMX output with a channel."""

    name = "patch.add_output"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channel: int = 1
        self.output: int = 1
        self.univ: int = 0
        self.curve: int = 0

        # State saved for undo
        self.old_channel: typing.Optional[int] = None
        self.old_curve: int = 0

    def configure(self, channel: int, output: int, univ: int, curve: int = 0) -> None:
        """Configure the action with output patching parameters.

        Args:
            channel: The channel to associate with the output.
            output: The DMX output number.
            univ: The DMX universe index.
            curve: The transfer curve index (default 0 = linear).
        """
        self.channel = channel
        self.output = output
        self.univ = univ
        self.curve = curve

    def execute(self) -> None:
        """Execute the action, patching the configured output."""
        patch = self.app.lightshow.patch

        # Save previous state of this output
        if self.univ in patch.outputs and self.output in patch.outputs[self.univ]:
            self.old_channel = patch.outputs[self.univ][self.output][0]
            self.old_curve = patch.outputs[self.univ][self.output][1]
        else:
            self.old_channel = None
            self.old_curve = 0

        # Execute
        if self.old_channel is not None:
            patch.unpatch(self.old_channel, self.output, self.univ)
        patch.add_output(self.channel, self.output, self.univ, self.curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.unpatch(self.channel, self.output, self.univ)
        if self.old_channel is not None:
            patch.add_output(self.old_channel, self.output, self.univ, self.old_curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        if self.old_channel is not None:
            patch.unpatch(self.old_channel, self.output, self.univ)
        patch.add_output(self.channel, self.output, self.univ, self.curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchUnpatchOutputAction(Action):
    """Action to unpatch a DMX output."""

    name = "patch.unpatch_output"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.output: int = 1
        self.univ: int = 0
        self.old_channel: typing.Optional[int] = None
        self.old_curve: int = 0

    def configure(self, output: int, univ: int) -> None:
        """Configure the action with the output to unpatch.

        Args:
            output: The DMX output number.
            univ: The DMX universe index.
        """
        self.output = output
        self.univ = univ

    def execute(self) -> None:
        """Execute the action, unpatching the configured output."""
        patch = self.app.lightshow.patch
        if self.univ in patch.outputs and self.output in patch.outputs[self.univ]:
            self.old_channel = patch.outputs[self.univ][self.output][0]
            self.old_curve = patch.outputs[self.univ][self.output][1]
        else:
            self.old_channel = None
            self.old_curve = 0

        if self.old_channel is not None:
            patch.unpatch(self.old_channel, self.output, self.univ)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        if self.old_channel is not None:
            patch = self.app.lightshow.patch
            patch.add_output(self.old_channel, self.output, self.univ, self.old_curve)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def redo(self) -> None:
        if self.old_channel is not None:
            patch = self.app.lightshow.patch
            patch.unpatch(self.old_channel, self.output, self.univ)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")


class PatchClearAction(Action):
    """Action to clear the entire DMX patch."""

    name = "patch.clear"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.saved_patch: list[tuple[int, int, int, int]] = []

    def execute(self) -> None:
        patch = self.app.lightshow.patch

        # Save all patched outputs: (channel, output, univ, curve)
        self.saved_patch = []
        for univ, outputs in patch.outputs.items():
            for output, (channel, curve) in outputs.items():
                self.saved_patch.append((channel, output, univ, curve))

        patch.patch_empty()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_empty()
        for channel, output, univ, curve in self.saved_patch:
            patch.add_output(channel, output, univ, curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_empty()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchSet1on1Action(Action):
    """Action to set default 1:1 patch."""

    name = "patch.set_1on1"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.saved_patch: list[tuple[int, int, int, int]] = []

    def execute(self) -> None:
        patch = self.app.lightshow.patch

        # Save all patched outputs: (channel, output, univ, curve)
        self.saved_patch = []
        for univ, outputs in patch.outputs.items():
            for output, (channel, curve) in outputs.items():
                self.saved_patch.append((channel, output, univ, curve))

        patch.patch_1on1()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_empty()
        for channel, output, univ, curve in self.saved_patch:
            patch.add_output(channel, output, univ, curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_1on1()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchSetOutputCurveAction(Action):
    """Action to set the transfer curve of a patched DMX output."""

    name = "patch.set_output_curve"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.output: int = 1
        self.univ: int = 0
        self.curve: int = 0
        self.old_curve: int = 0

    def configure(self, output: int, univ: int, curve: int) -> None:
        """Configure the action with the output and new curve.

        Args:
            output: The DMX output number.
            univ: The DMX universe index.
            curve: The new transfer curve index.
        """
        self.output = output
        self.univ = univ
        self.curve = curve

    def execute(self) -> None:
        """Execute the action, assigning the configured curve to the output."""
        patch = self.app.lightshow.patch
        if self.univ in patch.outputs and self.output in patch.outputs[self.univ]:
            self.old_curve = patch.outputs[self.univ][self.output][1]
            patch.outputs[self.univ][self.output][1] = self.curve
            patch.invalidate_cache()
        else:
            raise ValueError(
                f"Output {self.output} in universe {self.univ} is not patched."
            )

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        if self.univ in patch.outputs and self.output in patch.outputs[self.univ]:
            patch.outputs[self.univ][self.output][1] = self.old_curve
            patch.invalidate_cache()
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        if self.univ in patch.outputs and self.output in patch.outputs[self.univ]:
            patch.outputs[self.univ][self.output][1] = self.curve
            patch.invalidate_cache()
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")


class PatchSelectOutputAction(Action):
    """Action to select DMX outputs."""

    name = "output.select"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.outputs: list[int] = []
        self.last: int = 0
        self.old_outputs: list[int] = []
        self.old_last: int = 0

    def configure(self, outputs: list[int], last: int) -> None:
        """Configure the action with the target outputs selection.

        Args:
            outputs: List of selected DMX output indexes.
            last: The last selected DMX output index.
        """
        self.outputs = list(outputs)
        self.last = last

    def execute(self) -> None:
        """Execute the action, updating the logical outputs selection."""
        patch_by_outputs = self.app.lightshow.patch_by_outputs
        self.old_outputs = list(patch_by_outputs.outputs)
        self.old_last = patch_by_outputs.last

        patch_by_outputs.outputs = list(self.outputs)
        patch_by_outputs.last = self.last

        self._update()

    def undo(self) -> None:
        patch_by_outputs = self.app.lightshow.patch_by_outputs
        patch_by_outputs.outputs = list(self.old_outputs)
        patch_by_outputs.last = self.old_last
        self._update()

    def redo(self) -> None:
        patch_by_outputs = self.app.lightshow.patch_by_outputs
        patch_by_outputs.outputs = list(self.outputs)
        patch_by_outputs.last = self.last
        self._update()

    def _update(self) -> None:
        patch_by_outputs = self.app.lightshow.patch_by_outputs
        if self.app.engine is not None:
            self.app.engine.send_osc(
                "/olc/patch/selected_outputs", patch_by_outputs.get_selected()
            )
        self.app.emit("patch.selected_outputs_changed")
