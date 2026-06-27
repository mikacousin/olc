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
"""Actions for fader assignment (fader.assign, fader.clear)."""

from __future__ import annotations

import typing

from olc.core.action import Action
from olc.fader import FaderType

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _get_fader_contents_number(
    app: CoreApplication, page: int, index: int
) -> float | None:
    """Return the numeric identifier of the current fader contents, or None.

    Args:
        app: Core application instance.
        page: Fader page number.
        index: Fader index within the page.

    Returns:
        Float identifier (group.index, cue.number, chaser.index) or None.
    """
    fader = app.lightshow.fader_bank.faders[page][index]
    contents = getattr(fader, "contents", None)
    if contents is None:
        return None
    # Sequence / Chaser has both .index and .steps — check steps first
    if hasattr(contents, "index") and hasattr(contents, "steps"):
        return float(contents.index)
    # Group has .index but no .steps
    if hasattr(contents, "index"):
        return float(contents.index)
    # Cue / Preset has .number
    if hasattr(contents, "number"):
        return float(contents.number)
    return None


class FaderAssignAction(Action):
    """Action to assign a type and optional contents to a fader.

    Supports full undo/redo: the previous type and contents are saved and
    restored on undo.
    """

    name = "fader.assign"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.new_type: FaderType = FaderType.NONE
        self.new_contents: float | None = None
        self.old_type: FaderType = FaderType.NONE
        self.old_contents: float | None = None

    def configure(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: float | None = None,
    ) -> None:
        """Configure the fader assignment.

        Args:
            page: Fader page number.
            index: Fader index within the page.
            fader_type: Target FaderType to assign.
            contents: Optional numeric identifier for the fader contents
                (group index, cue number, or chaser index).
        """
        self.page = page
        self.index = index
        self.new_type = fader_type
        self.new_contents = contents

    def execute(self) -> None:
        """Snapshot the current state, then apply the new assignment."""
        self.old_type = self.app.lightshow.fader_bank.get_fader_type(
            self.page, self.index
        )
        self.old_contents = _get_fader_contents_number(self.app, self.page, self.index)

        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.new_type, self.new_contents
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def undo(self) -> None:
        """Restore the previous fader assignment."""
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.old_type, self.old_contents
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def redo(self) -> None:
        """Re-apply the fader assignment."""
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.new_type, self.new_contents
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)


class FaderClearAction(Action):
    """Action to clear (reset to NONE) a fader assignment.

    A dedicated action rather than a simple alias of fader.assign so that it
    appears explicitly in OSC/MIDI bindings and the action registry.
    """

    name = "fader.clear"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.old_type: FaderType = FaderType.NONE
        self.old_contents: float | None = None

    def configure(self, page: int, index: int) -> None:
        """Configure the fader to clear.

        Args:
            page: Fader page number.
            index: Fader index within the page.
        """
        self.page = page
        self.index = index

    def execute(self) -> None:
        """Snapshot the current assignment, then clear the fader."""
        self.old_type = self.app.lightshow.fader_bank.get_fader_type(
            self.page, self.index
        )
        self.old_contents = _get_fader_contents_number(self.app, self.page, self.index)

        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, FaderType.NONE, None
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def undo(self) -> None:
        """Restore the previous fader assignment."""
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.old_type, self.old_contents
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def redo(self) -> None:
        """Re-clear the fader."""
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, FaderType.NONE, None
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)
