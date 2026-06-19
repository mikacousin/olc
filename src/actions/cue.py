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
        self.new_channels: dict[int, int] = {}
        self.old_channels: dict[int, int] = {}

    def configure(self, number: float, sequence: int, channels: dict[int, int]) -> None:
        """Configure the action.

        Args:
            number: Cue number (float, e.g. 1.0, 1.5).
            sequence: Sequence number (0 = preset).
            channels: New channel levels to apply.
        """
        self.number = number
        self.sequence = sequence
        self.new_channels = dict(channels)

    def execute(self) -> None:
        """Execute the action, updating the cue's channel levels."""
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.old_channels = copy.deepcopy(dict(cue.channels))
        cue.channels = self.new_channels
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.lightshow.cues.cue_editor.clear(self.number, self.sequence)
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the update, restoring the previous channel levels."""
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            return
        cue.channels = self.old_channels
        self.app.lightshow.main_playback.update_channels()
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
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.deleted_cue = cue
        try:
            self.deleted_index = list(self.app.lightshow.cues).index(cue)
        except ValueError:
            self.deleted_index = -1
        self.app.lightshow.cues.remove(cue)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.deleted", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the deletion, re-inserting the cue at its original position."""
        if self.deleted_cue is None:
            return
        if self.deleted_index != -1:
            self.app.lightshow.cues.insert(self.deleted_index, self.deleted_cue)
        else:
            self.app.lightshow.cues.add(self.deleted_cue)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.created", self.sequence, self.number)

    def redo(self) -> None:
        """Redo the deletion."""
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            return
        try:
            self.deleted_index = list(self.app.lightshow.cues).index(cue)
        except ValueError:
            self.deleted_index = -1
        self.app.lightshow.cues.remove(cue)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.deleted", self.sequence, self.number)


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
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.old_text = cue.text
        cue.text = self.new_text
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the rename, restoring the previous text."""
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
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
        self._dst_old_channels: dict[int, int] = {}
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
        src_cue = self.app.lightshow.cues.get(self.src_number, self.sequence)
        if src_cue is None:
            raise ValueError(
                f"Source cue {self.src_number} (seq {self.sequence}) does not exist."
            )
        new_channels = copy.deepcopy(dict(src_cue.channels))

        dst_cue = self.app.lightshow.cues.get(self.dst_number, self.sequence)
        if dst_cue is not None:
            self._dst_was_new = False
            self._dst_old_channels = copy.deepcopy(dict(dst_cue.channels))
            try:
                self._dst_index = list(self.app.lightshow.cues).index(dst_cue)
            except ValueError:
                self._dst_index = -1
            dst_cue.channels = new_channels
        else:
            self._dst_was_new = True
            new_cue = Cue(self.sequence, self.dst_number, new_channels)
            self.app.lightshow.cues.add(new_cue)
            try:
                self._dst_index = list(self.app.lightshow.cues).index(new_cue)
            except ValueError:
                self._dst_index = -1
            self.app.emit("cue.created", self.sequence, self.dst_number)

        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.dst_number)

    def execute(self) -> None:
        """Execute the action, copying channels from source to destination."""
        self._do_copy()

    def undo(self) -> None:
        """Undo the copy."""
        if self._dst_was_new:
            dst_cue = self.app.lightshow.cues.get(self.dst_number, self.sequence)
            if dst_cue is not None:
                self.app.lightshow.cues.remove(dst_cue)
                self.app.emit("cue.deleted", self.sequence, self.dst_number)
        else:
            dst_cue = self.app.lightshow.cues.get(self.dst_number, self.sequence)
            if dst_cue is not None:
                dst_cue.channels = self._dst_old_channels
                self.app.emit("cue.updated", self.sequence, self.dst_number)
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
        self.number: float = 0.0
        self.sequence: int = 0
        self.channels: dict[int, int] = {}
        self._inserted_index: int = -1

    def configure(
        self, number: float, sequence: int, channels: dict[int, int] | None = None
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
        if self.app.lightshow.cues.get(self.number, self.sequence) is not None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) already exists.")
        new_cue = Cue(self.sequence, self.number, copy.deepcopy(self.channels))
        self.app.lightshow.cues.add(new_cue)
        try:
            self._inserted_index = list(self.app.lightshow.cues).index(new_cue)
        except ValueError:
            self._inserted_index = -1
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.created", self.sequence, self.number)

    def execute(self) -> None:
        """Execute the action, inserting the new cue."""
        self._do_insert()

    def undo(self) -> None:
        """Undo the insertion, removing the newly created cue."""
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            return
        self.app.lightshow.cues.remove(cue)
        self.app.lightshow.main_playback.update_channels()
        self.app.lightshow.set_modified()
        self.app.emit("cue.deleted", self.sequence, self.number)

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
        self.level: int = 0
        self.old_level: int = 0

    def configure(self, number: float, sequence: int, channel: int, level: int) -> None:
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
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
        if cue is None:
            raise ValueError(f"Cue {self.number} (seq {self.sequence}) does not exist.")
        self.old_level = cue.get_level(self.channel)
        cue.set_level(self.channel, self.level)
        self.app.lightshow.set_modified()
        self.app.emit("cue.updated", self.sequence, self.number)

    def undo(self) -> None:
        """Undo the level change, restoring the previous level."""
        cue = self.app.lightshow.cues.get(self.number, self.sequence)
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
        self.new_levels: dict[int, int] = {}
        self.old_levels: dict[int, int] = {}

    def configure(self, number: float, sequence: int, channels: dict[int, int]) -> None:
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
        cue_editor = self.app.lightshow.cues.cue_editor
        levels = cue_editor.get_levels(self.number, self.sequence)
        self.old_levels = {}
        for channel in self.new_levels:
            self.old_levels[channel] = int(levels[channel - 1])

        for channel, level in self.new_levels.items():
            cue_editor.set_level(self.number, self.sequence, channel, level)

    def undo(self) -> None:
        """Undo the temporary levels, restoring previous overrides."""
        cue_editor = self.app.lightshow.cues.cue_editor
        for channel, level in self.old_levels.items():
            cue_editor.set_level(self.number, self.sequence, channel, level)
