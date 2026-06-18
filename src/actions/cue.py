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

from olc.core.action import Action
from olc.cue import Cue

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _find_cue(cues: list[Cue], memory: float, sequence: int) -> tuple[int, Cue] | None:
    """Return (index, cue) for the cue matching memory and sequence, or None."""
    for i, cue in enumerate(cues):
        if cue.memory == memory and cue.sequence == sequence:
            return i, cue
    return None


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
        self.memory: float = 0.0
        self.sequence: int = 0
        self.new_channels: dict[int, int] = {}
        self.old_channels: dict[int, int] = {}

    def configure(self, memory: float, sequence: int, channels: dict[int, int]) -> None:
        """Configure the action.

        Args:
            memory: Cue number (float, e.g. 1.0, 1.5).
            sequence: Sequence number (0 = preset).
            channels: New channel levels to apply.
        """
        self.memory = memory
        self.sequence = sequence
        self.new_channels = dict(channels)

    def execute(self) -> None:
        """Execute the action, updating the cue's channel levels."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            raise ValueError(f"Cue {self.memory} (seq {self.sequence}) does not exist.")
        _, cue = result
        self.old_channels = copy.deepcopy(dict(cue.channels))
        cue.channels = self.new_channels
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.memory)

    def undo(self) -> None:
        """Undo the update, restoring the previous channel levels."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            return
        _, cue = result
        cue.channels = self.old_channels
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.memory)


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
        self.memory: float = 0.0
        self.sequence: int = 0
        self.deleted_cue: Cue | None = None
        self.deleted_index: int = -1

    def configure(self, memory: float, sequence: int) -> None:
        """Configure the action.

        Args:
            memory: Cue number to delete.
            sequence: Sequence number.
        """
        self.memory = memory
        self.sequence = sequence

    def execute(self) -> None:
        """Execute the action, deleting the cue."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            raise ValueError(f"Cue {self.memory} (seq {self.sequence}) does not exist.")
        idx, cue = result
        self.deleted_cue = cue
        self.deleted_index = idx
        self.app.lightshow.cues.pop(idx)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.deleted", self.sequence, self.memory)

    def undo(self) -> None:
        """Undo the deletion, re-inserting the cue at its original position."""
        if self.deleted_cue is None:
            return
        self.app.lightshow.cues.insert(self.deleted_index, self.deleted_cue)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.created", self.sequence, self.memory)

    def redo(self) -> None:
        """Redo the deletion."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            return
        idx, _ = result
        self.deleted_index = idx
        self.app.lightshow.cues.pop(idx)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.deleted", self.sequence, self.memory)


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
        self.memory: float = 0.0
        self.sequence: int = 0
        self.new_text: str = ""
        self.old_text: str = ""

    def configure(self, memory: float, sequence: int, text: str) -> None:
        """Configure the action.

        Args:
            memory: Cue number to rename.
            sequence: Sequence number.
            text: New label text.
        """
        self.memory = memory
        self.sequence = sequence
        self.new_text = text

    def execute(self) -> None:
        """Execute the action, applying the new label."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            raise ValueError(f"Cue {self.memory} (seq {self.sequence}) does not exist.")
        _, cue = result
        self.old_text = cue.text
        cue.text = self.new_text
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.memory)

    def undo(self) -> None:
        """Undo the rename, restoring the previous text."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            return
        _, cue = result
        cue.text = self.old_text
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.memory)


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
        self.src_memory: float = 0.0
        self.dst_memory: float = 0.0
        self.sequence: int = 0
        self._dst_was_new: bool = False
        self._dst_old_channels: dict[int, int] = {}
        self._dst_index: int = -1

    def configure(self, src_memory: float, dst_memory: float, sequence: int) -> None:
        """Configure the action.

        Args:
            src_memory: Source cue number (to copy from).
            dst_memory: Destination cue number (to copy into).
            sequence: Sequence number.
        """
        self.src_memory = src_memory
        self.dst_memory = dst_memory
        self.sequence = sequence

    def _do_copy(self) -> None:
        """Internal helper: perform the copy operation."""
        src = _find_cue(self.app.lightshow.cues, self.src_memory, self.sequence)
        if src is None:
            raise ValueError(
                f"Source cue {self.src_memory} (seq {self.sequence}) does not exist."
            )
        _, src_cue = src
        new_channels = copy.deepcopy(dict(src_cue.channels))

        dst = _find_cue(self.app.lightshow.cues, self.dst_memory, self.sequence)
        if dst is not None:
            self._dst_was_new = False
            dst_idx, dst_cue = dst
            self._dst_old_channels = copy.deepcopy(dict(dst_cue.channels))
            self._dst_index = dst_idx
            dst_cue.channels = new_channels
        else:
            self._dst_was_new = True
            new_cue = Cue(self.sequence, self.dst_memory, new_channels)
            insert_idx = len(self.app.lightshow.cues)
            for i, c in enumerate(self.app.lightshow.cues):
                if c.memory > self.dst_memory:
                    insert_idx = i
                    break
            self._dst_index = insert_idx
            self.app.lightshow.cues.insert(insert_idx, new_cue)
            self.app.emit("cue.created", self.sequence, self.dst_memory)

        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.dst_memory)

    def execute(self) -> None:
        """Execute the action, copying channels from source to destination."""
        self._do_copy()

    def undo(self) -> None:
        """Undo the copy."""
        if self._dst_was_new:
            result = _find_cue(self.app.lightshow.cues, self.dst_memory, self.sequence)
            if result is not None:
                idx, _ = result
                self.app.lightshow.cues.pop(idx)
                self.app.emit("cue.deleted", self.sequence, self.dst_memory)
        else:
            result = _find_cue(self.app.lightshow.cues, self.dst_memory, self.sequence)
            if result is not None:
                _, dst_cue = result
                dst_cue.channels = self._dst_old_channels
                self.app.emit("cue.updated", self.sequence, self.dst_memory)
        self.app.lightshow.main_playback.update_channels()
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
        self.memory: float = 0.0
        self.sequence: int = 0
        self.channels: dict[int, int] = {}
        self._inserted_index: int = -1

    def configure(
        self, memory: float, sequence: int, channels: dict[int, int] | None = None
    ) -> None:
        """Configure the action.

        Args:
            memory: New cue number.
            sequence: Sequence number (0 = preset).
            channels: Optional initial channel levels dict.
        """
        self.memory = memory
        self.sequence = sequence
        self.channels = dict(channels) if channels is not None else {}

    def _do_insert(self) -> None:
        """Internal helper: perform the insert operation."""
        if _find_cue(self.app.lightshow.cues, self.memory, self.sequence) is not None:
            raise ValueError(f"Cue {self.memory} (seq {self.sequence}) already exists.")
        new_cue = Cue(self.sequence, self.memory, copy.deepcopy(self.channels))
        insert_idx = len(self.app.lightshow.cues)
        for i, c in enumerate(self.app.lightshow.cues):
            if c.memory > self.memory:
                insert_idx = i
                break
        self._inserted_index = insert_idx
        self.app.lightshow.cues.insert(insert_idx, new_cue)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.created", self.sequence, self.memory)

    def execute(self) -> None:
        """Execute the action, inserting the new cue."""
        self._do_insert()

    def undo(self) -> None:
        """Undo the insertion, removing the newly created cue."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            return
        idx, _ = result
        self.app.lightshow.cues.pop(idx)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.deleted", self.sequence, self.memory)

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
        self.memory: float = 0.0
        self.sequence: int = 0
        self.channel: int = 1
        self.level: int = 0
        self.old_level: int = 0

    def configure(self, memory: float, sequence: int, channel: int, level: int) -> None:
        """Configure the action.

        Args:
            memory: Cue number.
            sequence: Sequence number.
            channel: Channel number (1-based).
            level: New DMX level (0-255).
        """
        self.memory = memory
        self.sequence = sequence
        self.channel = channel
        self.level = level

    def execute(self) -> None:
        """Execute the action, setting the channel level in the cue."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            raise ValueError(f"Cue {self.memory} (seq {self.sequence}) does not exist.")
        _, cue = result
        self.old_level = cue.get_level(self.channel)
        cue.set_level(self.channel, self.level)
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.memory)

    def undo(self) -> None:
        """Undo the level change, restoring the previous level."""
        result = _find_cue(self.app.lightshow.cues, self.memory, self.sequence)
        if result is None:
            return
        _, cue = result
        cue.set_level(self.channel, self.old_level)
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.memory)
