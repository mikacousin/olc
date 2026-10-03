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
"""Actions for command line interactions (append_char, clear, set)."""

from __future__ import annotations

import typing

from olc.core.action import Action

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class CommandLineAppendCharAction(Action):
    """Action to append a character to the command line."""

    name = "commandline.append_char"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.char: str = ""
        self.old_text: str = ""

    def configure(self, char: str) -> None:
        """Configure the character to append.

        Args:
            char: The character or string segment to append.
        """
        self.char = str(char)

    def execute(self) -> None:
        """Save previous text and append character."""
        self.old_text = self.app.commandline.get_string()
        self.can_undo = bool(self.char)
        self.app.commandline.add_string(self.char)

    def undo(self) -> None:
        """Revert the command line text to the state before append."""
        super().undo()
        self.app.commandline.set_string(self.old_text)

    def redo(self) -> None:
        """Reapply the append action."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state for this action."""
        return {"text": self.app.commandline.get_string()}


class CommandLineClearAction(Action):
    """Action to clear the command line."""

    name = "commandline.clear"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.old_text: str = ""

    def execute(self) -> None:
        """Save previous text and clear the command line."""
        self.old_text = self.app.commandline.get_string()
        self.can_undo = bool(self.old_text)
        self.app.commandline.set_string("")

    def undo(self) -> None:
        """Restore the command line text prior to clearing."""
        super().undo()
        self.app.commandline.set_string(self.old_text)

    def redo(self) -> None:
        """Reapply the clear action."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state for this action."""
        return {"text": self.app.commandline.get_string()}


class CommandLineSetAction(Action):
    """Action to set the exact text of the command line."""

    name = "commandline.set"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.text: str = ""
        self.old_text: str = ""

    def configure(self, text: str) -> None:
        """Configure the target text.

        Args:
            text: The new command line string.
        """
        self.text = str(text)

    def execute(self) -> None:
        """Save previous text and set new command line text."""
        self.old_text = self.app.commandline.get_string()
        self.can_undo = self.old_text != self.text
        self.app.commandline.set_string(self.text)

    def undo(self) -> None:
        """Restore the command line text prior to setting."""
        super().undo()
        self.app.commandline.set_string(self.old_text)

    def redo(self) -> None:
        """Reapply the set action."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state for this action."""
        return {"text": self.app.commandline.get_string()}
