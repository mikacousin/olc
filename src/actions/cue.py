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

import copy
import typing
from collections.abc import Mapping

from olc.core.action import Action
from olc.show.cue import Cue
from olc.show.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.lightshow import LightShow
    from olc.show.sequence import Sequence


def _resolve_sequence(lightshow: LightShow, sequence: int) -> Sequence | None:
    """Resolve sequence index (0/1 -> main_playback, >=2 -> secondary sequence)."""
    if sequence in (0, 1):
        return lightshow.main_playback
    return lightshow.get_sequence(float(sequence))


def _insert_cue_step(seq: Sequence, cue: Cue) -> tuple[Step, int]:
    """Wrap *cue* in a Step and insert it in sorted order before trailing sentinel."""
    step = Step(seq.index, cue=cue)
    if (
        len(seq.steps) >= 2
        and seq.steps[-1].cue is not None
        and seq.steps[-1].cue.number == 0.0
    ):
        insert_idx = len(seq.steps) - 1
        for idx, s in enumerate(seq.steps[:-1]):
            if s.cue is not None and s.cue.number > cue.number:
                insert_idx = max(1, idx)
                break
    else:
        insert_idx = len(seq.steps)
        for idx, s in enumerate(seq.steps):
            if s.cue is not None and s.cue.number > cue.number:
                insert_idx = idx
                break
    seq.insert_step(insert_idx, step)
    seq.update_channels()
    return step, insert_idx


class CueUpdateAction(Action):
    """Action to overwrite a cue's channels with a new set of levels.

    Supports Undo/Redo by capturing the previous channels dict via deep copy.
    """

    name = "cue.update"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 0
        self.new_channels: dict[int, int | float] = {}
        self.old_channels: dict[int, int | float] = {}
        self.new_device_values: dict[int, dict[str, float]] | None = None
        self.old_device_values: dict[int, dict[str, float]] = {}
        self.new_palette_refs: dict[int, dict[str, tuple[str, float]]] | None = None
        self.old_palette_refs: dict[int, dict[str, tuple[str, float]]] = {}
        self.new_effect_refs: dict[int, dict[str, typing.Any]] | None = None
        self.old_effect_refs: dict[int, dict[str, typing.Any]] = {}

    def configure(
        self,
        number: float,
        sequence: int,
        channels: Mapping[int, int | float],
        device_values: dict[int, dict[str, float]] | None = None,
        palette_refs: dict[int, dict[str, tuple[str, float]]] | None = None,
        effect_refs: dict[int, dict[str, typing.Any]] | None = None,
    ) -> None:
        """Configure the action.

        Args:
            number: Cue number (float, e.g. 1.0, 1.5).
            sequence: Sequence number (0 = preset).
            channels: New channel levels to apply.
            device_values: Optional per-device parameter overrides to merge.
            palette_refs: Optional per-channel palette references mapping.
            effect_refs: Optional per-channel effect references mapping.
        """
        self.number = number
        self.sequence = sequence
        self.new_channels = dict(channels)
        self.new_device_values = (
            copy.deepcopy(device_values) if device_values is not None else None
        )
        self.new_palette_refs = (
            copy.deepcopy(palette_refs) if palette_refs is not None else None
        )
        self.new_effect_refs = (
            copy.deepcopy(effect_refs) if effect_refs is not None else None
        )

    def execute(self) -> None:
        """Execute the action, updating the cue's channel levels."""
        cue = self.app.lightshow.get_cue(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.old_channels = copy.deepcopy(dict(cue.channels))
        self.old_device_values = copy.deepcopy(dict(cue.device_values))
        self.old_palette_refs = copy.deepcopy(dict(cue.palette_refs))
        self.old_effect_refs = copy.deepcopy(dict(cue.effect_refs))
        cue.channels = self.new_channels
        if self.new_device_values is not None:
            for dev_id, vals in self.new_device_values.items():
                cue.device_values.setdefault(dev_id, {}).update(vals)
        if self.new_palette_refs is not None:
            cue.palette_refs = copy.deepcopy(self.new_palette_refs)
        if self.new_effect_refs is not None:
            cue.effect_refs = copy.deepcopy(self.new_effect_refs)
        seq = (
            self.app.lightshow.main_playback
            if self.sequence in (0, 1)
            else self.app.lightshow.get_sequence(float(self.sequence))
        )
        if seq is not None:
            seq.update_channels()
        self.app.lightshow.set_modified()
        self.app.lightshow.cue_editor.clear(self.number, self.sequence)
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the update, restoring the previous channel levels."""
        cue = self.app.lightshow.get_cue(self.number, self.sequence)
        if cue is None:
            return
        cue.channels = copy.deepcopy(self.old_channels)
        cue.device_values = copy.deepcopy(self.old_device_values)
        cue.palette_refs = copy.deepcopy(self.old_palette_refs)
        cue.effect_refs = copy.deepcopy(self.old_effect_refs)
        seq = (
            self.app.lightshow.main_playback
            if self.sequence in (0, 1)
            else self.app.lightshow.get_sequence(float(self.sequence))
        )
        if seq is not None:
            seq.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)


class CueDeleteAction(Action):
    """Action to delete a cue from the lightshow.

    Supports Undo/Redo by retaining the deleted cue object and its list index.

    Note: Steps referencing this cue are NOT removed here — that is handled by a
    dedicated step.delete action (Phase 3).
    """

    name = "cue.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 0
        self.deleted_cue: Cue | None = None
        self.deleted_step: Step | None = None
        self.deleted_index: int = -1

    def configure(self, number: float, sequence: int) -> None:
        """Configure the action.

        Args:
            number: Cue number to delete.
            sequence: Sequence number.
        """
        self.number = number
        self.sequence = sequence

    def execute(self) -> None:
        """Execute the action, deleting the cue."""
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            raise ValueError(f"Sequence {self.sequence} does not exist.")
        for idx, step in enumerate(seq.steps):
            if step.cue is not None and step.cue.number == self.number:
                self.deleted_cue = step.cue
                self.deleted_step = step
                self.deleted_index = idx
                seq.steps.pop(idx)
                seq.last = len(seq.steps)
                seq.update_channels()
                self.app.lightshow.set_modified()
                self.app.emit("cue.deleted", self.sequence, self.number)
                return
        raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")

    def undo(self) -> None:
        """Undo the deletion, re-inserting the cue step at its original position."""
        if self.deleted_step is None or self.deleted_cue is None:
            return
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            return
        if 0 <= self.deleted_index <= len(seq.steps):
            seq.insert_step(self.deleted_index, self.deleted_step)
        else:
            _insert_cue_step(seq, self.deleted_cue)
        seq.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.created", self.sequence, self.number)

    def redo(self) -> None:
        """Redo the deletion."""
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            return
        for idx, step in enumerate(seq.steps):
            if step.cue is not None and step.cue.number == self.number:
                self.deleted_index = idx
                seq.steps.pop(idx)
                seq.last = len(seq.steps)
                seq.update_channels()
                self.app.lightshow.set_modified()
                self.app.emit("cue.deleted", self.sequence, self.number)
                return


class CueRenameAction(Action):
    """Action to rename a cue (change its text label).

    Supports Undo/Redo by storing the previous text.
    """

    name = "cue.rename"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 0
        self.new_text: str = ""
        self.old_text: str = ""

    def configure(self, number: float, sequence: int, text: str) -> None:
        """Configure the action.

        Args:
            number: Cue number to rename.
            sequence: Sequence number.
            text: New label text.
        """
        self.number = number
        self.sequence = sequence
        self.new_text = text

    def execute(self) -> None:
        """Execute the action, applying the new label."""
        cue = self.app.lightshow.get_cue(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.old_text = cue.text
        cue.text = self.new_text
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the rename, restoring the previous text."""
        cue = self.app.lightshow.get_cue(self.number, self.sequence)
        if cue is None:
            return
        cue.text = self.old_text
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)


class CueCopyAction(Action):
    """Action to copy an existing cue's channels to another cue number.

    If the destination cue does not exist, a new one is created.
    If it already exists, its channels are overwritten.
    Supports Undo/Redo.
    """

    name = "cue.copy"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.src_number: float = 0.0
        self.dst_number: float = 0.0
        self.sequence: int = 0
        self._dst_was_new: bool = False
        self._dst_old_channels: dict[int, int | float] = {}
        self._dst_index: int = -1

    def configure(self, src_number: float, dst_number: float, sequence: int) -> None:
        """Configure the action.

        Args:
            src_number: Source cue number (to copy from).
            dst_number: Destination cue number (to copy into).
            sequence: Sequence number.
        """
        self.src_number = src_number
        self.dst_number = dst_number
        self.sequence = sequence

    def _do_copy(self) -> None:
        """Internal helper: perform the copy operation."""
        src_cue = self.app.lightshow.get_cue(self.src_number, self.sequence)
        if src_cue is None:
            raise ValueError(
                f"Source cue {self.src_number} (seq {self.sequence}) does not exist."
            )
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            raise ValueError(f"Sequence {self.sequence} does not exist.")
        new_channels = copy.deepcopy(dict(src_cue.channels))

        dst_cue = self.app.lightshow.get_cue(self.dst_number, self.sequence)
        if dst_cue is not None:
            self._dst_was_new = False
            self._dst_old_channels = copy.deepcopy(dict(dst_cue.channels))
            dst_cue.channels = new_channels
            seq.update_channels()
        else:
            self._dst_was_new = True
            new_cue = Cue(int(seq.index), self.dst_number, new_channels)
            _step, self._dst_index = _insert_cue_step(seq, new_cue)
            self.app.emit("cue.created", self.sequence, self.dst_number)

        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.dst_number)

    def execute(self) -> None:
        """Execute the action, copying channels from source to destination."""
        self._do_copy()

    def undo(self) -> None:
        """Undo the copy."""
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            return
        if self._dst_was_new:
            for idx, step in enumerate(seq.steps):
                if step.cue is not None and step.cue.number == self.dst_number:
                    seq.steps.pop(idx)
                    seq.last = len(seq.steps)
                    self.app.emit("cue.deleted", self.sequence, self.dst_number)
                    break
        else:
            dst_cue = self.app.lightshow.get_cue(self.dst_number, self.sequence)
            if dst_cue is not None:
                dst_cue.channels = self._dst_old_channels
                self.app.emit("cue.updated", self.sequence, self.dst_number)
        seq.update_channels()
        self.app.lightshow.set_modified()

    def redo(self) -> None:
        """Redo the copy."""
        self._do_copy()


class CueInsertAction(Action):
    """Action to insert a new cue at a given number (optionally copying channels).

    Supports Undo/Redo.
    """

    name = "cue.insert"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 0
        self.channels: dict[int, int | float] = {}
        self._inserted_index: int = -1

    def configure(
        self,
        number: float,
        sequence: int,
        channels: Mapping[int, int | float] | None = None,
    ) -> None:
        """Configure the action.

        Args:
            number: New cue number.
            sequence: Sequence number (0 = preset).
            channels: Optional initial channel levels dict.
        """
        self.number = number
        self.sequence = sequence
        self.channels = dict(channels) if channels is not None else {}

    def _do_insert(self) -> None:
        """Internal helper: perform the insert operation."""
        if self.app.lightshow.get_cue(self.number, self.sequence) is not None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) already exists.")
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            raise ValueError(f"Sequence {self.sequence} does not exist.")
        new_cue = Cue(int(seq.index), self.number, copy.deepcopy(self.channels))
        _step, self._inserted_index = _insert_cue_step(seq, new_cue)
        self.app.lightshow.set_modified()
        self.app.emit("cue.created", self.sequence, self.number)

    def execute(self) -> None:
        """Execute the action, inserting the new cue."""
        self._do_insert()

    def undo(self) -> None:
        """Undo the insertion, removing the newly created cue."""
        seq = _resolve_sequence(self.app.lightshow, self.sequence)
        if seq is None:
            return
        for idx, step in enumerate(seq.steps):
            if step.cue is not None and step.cue.number == self.number:
                seq.steps.pop(idx)
                seq.last = len(seq.steps)
                seq.update_channels()
                self.app.lightshow.set_modified()
                self.app.emit("cue.deleted", self.sequence, self.number)
                return

    def redo(self) -> None:
        """Redo the insertion."""
        self._do_insert()


class CueSetChannelLevelAction(Action):
    """Action to set the level of a single channel within a specific cue.

    Supports Undo/Redo by capturing the previous channel level.
    """

    name = "cue.set_channel_level"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 0
        self.channel: int = 1
        self.level: int | float = 0
        self.old_level: int | float = 0

    def configure(
        self, number: float, sequence: int, channel: int, level: int | float
    ) -> None:
        """Configure the action.

        Args:
            number: Cue number.
            sequence: Sequence number.
            channel: Channel number (1-based).
            level: New DMX level (0-255).
        """
        self.number = number
        self.sequence = sequence
        self.channel = channel
        self.level = level

    def execute(self) -> None:
        """Execute the action, setting the channel level in the cue."""
        cue = self.app.lightshow.get_cue(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.old_level = cue.get_level(self.channel)
        cue.set_level(self.channel, self.level)
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the level change, restoring the previous level."""
        cue = self.app.lightshow.get_cue(self.number, self.sequence)
        if cue is None:
            return
        cue.set_level(self.channel, self.old_level)
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)


class CueSetTempChannelsAction(Action):
    """Action to set temp channel levels in a cue, supporting Undo/Redo."""

    name = "cue.set_temp_channels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 0
        self.new_levels: dict[int, float] = {}
        self.old_levels: dict[int, float] = {}

    def configure(
        self, number: float, sequence: int, channels: dict[int, float]
    ) -> None:
        """Configure the action.

        Args:
            number: Cue number.
            sequence: Sequence index.
            channels: Dict mapping channel number (1-based) to level (0-255).
        """
        self.number = number
        self.sequence = sequence
        self.new_levels = dict(channels)

    def execute(self) -> None:
        """Execute the action, storing temp levels and applying overrides."""
        cue_editor = self.app.lightshow.cue_editor
        levels = cue_editor.get_levels(self.number, self.sequence)
        self.old_levels = {}
        for channel in self.new_levels:
            self.old_levels[channel] = float(levels[channel - 1])

        for channel, level in self.new_levels.items():
            cue_editor.set_level(self.number, self.sequence, channel, level)

    def undo(self) -> None:
        """Undo the temporary channel level changes."""
        cue_editor = self.app.lightshow.cue_editor
        for channel, level in self.old_levels.items():
            cue_editor.set_level(self.number, self.sequence, channel, level)

    def redo(self) -> None:
        """Redo the temporary channel level changes."""
        cue_editor = self.app.lightshow.cue_editor
        for channel, level in self.new_levels.items():
            cue_editor.set_level(self.number, self.sequence, channel, level)


class CueSelectAction(Action):
    """Action to select a cue logically.

    Supports Undo/Redo by storing the previous selected cue.
    """

    name = "cue.select"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.cue_id: typing.Optional[tuple[float, int]] = None
        self.old_cue_id: typing.Optional[tuple[float, int]] = None

    def configure(self, cue_id: tuple[float, int] | None) -> None:
        """Configure the action with the cue ID to select.

        Args:
            cue_id: A tuple of (number, sequence) to select, or None to unselect.
        """
        self.cue_id = cue_id

    def execute(self) -> None:
        self.old_cue_id = self.app.selected_cue
        self.app.selected_cue = self.cue_id
        self.app.emit("cue.selected_changed", self.cue_id)

    def undo(self) -> None:
        self.app.selected_cue = self.old_cue_id
        self.app.emit("cue.selected_changed", self.old_cue_id)

    def redo(self) -> None:
        self.app.selected_cue = self.cue_id
        self.app.emit("cue.selected_changed", self.cue_id)


class CueClearEditorAction(Action):
    """Action to clear temporary edits in the cue editor for a cue."""

    name = "cue.clear_editor"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 1

    def configure(self, number: float, sequence: int = 1) -> None:
        """Configure the cue number and sequence index to clear."""
        self.number = float(number)
        self.sequence = int(sequence)

    def execute(self) -> None:
        self.app.lightshow.cue_editor.clear(self.number, self.sequence)
        self.app.emit("cue.editor_cleared", self.number, self.sequence)


def _find_cue(app: CoreApplication, number: float, sequence: int) -> Cue | None:
    """Find a cue by number/sequence across sequences (with legacy fallback)."""
    return app.lightshow.get_cue(number, sequence)


class _CueBoolFlagAction(Action):
    """Base action to toggle a boolean flag on a Cue with Undo/Redo."""

    _flag_attr: str = ""
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 1
        self.value: bool = True
        self.old_value: bool = False

    def configure(self, number: float, value: bool, sequence: int = 1) -> None:
        """Configure the cue number, flag state, and sequence index."""
        self.number = float(number)
        self.value = bool(value)
        self.sequence = int(sequence)

    def _get_cue(self) -> Cue | None:
        return _find_cue(self.app, self.number, self.sequence)

    def _apply(self, target: bool) -> None:
        cue = self._get_cue()
        if cue is not None:
            setattr(cue, self._flag_attr, target)
            self.app.lightshow.set_modified()
            self.app.emit("cue.updated", self.sequence, self.number)

    def execute(self) -> None:
        cue = self._get_cue()
        if cue is None:
            raise ValueError(f"Cue {self.number} not found")
        self.old_value = bool(getattr(cue, self._flag_attr, False))
        self._apply(self.value)

    def undo(self) -> None:
        self._apply(self.old_value)

    def redo(self) -> None:
        self._apply(self.value)


class CueSetBlockAction(_CueBoolFlagAction):
    """Action to set or clear the block flag on a cue."""

    name = "cue.set_block"
    _flag_attr = "is_block"


class CueSetAssertAction(_CueBoolFlagAction):
    """Action to set or clear the assert flag on a cue."""

    name = "cue.set_assert"
    _flag_attr = "is_assert"


class CueSetIntBlockAction(_CueBoolFlagAction):
    """Action to set or clear the intensity block flag on a cue."""

    name = "cue.set_int_block"
    _flag_attr = "is_int_block"


class CueSetNotesAction(Action):
    """Action to update the notes field on a cue."""

    name = "cue.set_notes"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 0.0
        self.sequence: int = 1
        self.notes: str = ""
        self.old_notes: str = ""

    def configure(self, number: float, notes: str, sequence: int = 1) -> None:
        """Configure the cue number, notes text, and sequence index."""
        self.number = float(number)
        self.notes = str(notes)
        self.sequence = int(sequence)

    def _get_cue(self) -> Cue | None:
        return _find_cue(self.app, self.number, self.sequence)

    def execute(self) -> None:
        cue = self._get_cue()
        if cue is None:
            raise ValueError(f"Cue {self.number} not found")
        self.old_notes = str(getattr(cue, "notes", ""))
        cue.notes = self.notes
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        cue = self._get_cue()
        if cue is not None:
            cue.notes = self.old_notes
            self.app.lightshow.set_modified()
            self.app.emit("cue.updated", self.sequence, self.number)

    def redo(self) -> None:
        cue = self._get_cue()
        if cue is not None:
            cue.notes = self.notes
            self.app.lightshow.set_modified()
            self.app.emit("cue.updated", self.sequence, self.number)
