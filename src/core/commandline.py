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
"""Logical command line state model and execution coordinator."""

from __future__ import annotations

import typing

from olc.core.parser.completer import CommandCompleter, CompletionResult
from olc.core.parser.executor import CommandExecutor, CommandResult
from olc.core.parser.parser import CommandParser, CommandSyntaxError

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class CoreCommandLine:
    """Logical command line state helper, decoupled from the GUI."""

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the logical command line.

        Args:
            app: The core application instance.
        """
        self.app = app
        self._keystring: str = ""
        self.parser = CommandParser()
        self.executor = CommandExecutor(app)
        self.completer = CommandCompleter(self.parser, getattr(app, "lightshow", None))
        self.history: list[str] = []
        self.history_index: int = -1

    def update(self) -> None:
        """Emit local core events when command line state changes."""
        self.app.emit("commandline.changed", self._keystring)

    def add_string(self, string: str) -> None:
        """Add a string segment to the current command line.

        Args:
            string: The string to append.
        """
        self.completer.reset_cycle()
        self._keystring += string
        self.update()

    def set_string(self, string: str) -> None:
        """Set the exact command line string.

        Args:
            string: The new command line string.
        """
        self.completer.reset_cycle()
        self._keystring = string
        self.update()

    def autocomplete(self) -> CompletionResult:
        """Attempt to auto-complete the current command line buffer with Tab.

        Returns:
            CompletionResult containing the outcome and suggestions.
        """
        if self.completer.lightshow is None and hasattr(self.app, "lightshow"):
            self.completer.lightshow = self.app.lightshow

        result = self.completer.complete(self._keystring)
        if result.has_completed:
            self._keystring = result.new_text
            self.update()
        if result.candidates:
            self.app.emit("commandline.suggestions", result.candidates)
        return result

    def get_string(self) -> str:
        """Return the current command line string.

        Returns:
            The raw keystring.
        """
        return self._keystring

    def clear(self) -> None:
        """Clear the current command line buffer."""
        self.completer.reset_cycle()
        self.set_string("")

    def backspace(self) -> None:
        """Remove the last character from the command line buffer."""
        self.completer.reset_cycle()
        if self._keystring:
            self.set_string(self._keystring[:-1])

    def history_prev(self) -> None:
        """Recall previous command from history."""
        if not self.history:
            return

        if self.history_index == -1:
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1

        self.set_string(self.history[self.history_index])

    def history_next(self) -> None:
        """Recall next command from history."""
        if not self.history or self.history_index == -1:
            return

        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.set_string(self.history[self.history_index])
        else:
            self.history_index = -1
            self.set_string("")

    def execute(self) -> CommandResult:
        """Parse and execute the current command line buffer.

        Returns:
            CommandResult with execution outcome.
        """
        raw_cmd = self._keystring.strip()
        if not raw_cmd:
            return CommandResult(True, "Empty command line")

        # Save to command history
        if not self.history or self.history[-1] != raw_cmd:
            self.history.append(raw_cmd)
        self.history_index = -1

        try:
            node = self.parser.parse(raw_cmd)
            result = self.executor.execute(node)

            if result.success:
                # Clear buffer on successful execution
                self.set_string("")
                self.app.emit("commandline.executed", result.message)
            else:
                self.app.emit("commandline.error", result.message)

            return result

        except CommandSyntaxError as exc:
            err_msg = f"Syntax Error: {exc.message}"
            self.app.emit("commandline.error", err_msg)
            return CommandResult(False, err_msg)
