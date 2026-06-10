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

if typing.TYPE_CHECKING:
    from olc.core.action import Action
    from olc.core.app import CoreApplication


class HistoryManager:
    """Manages the undo and redo stacks for the application."""

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the HistoryManager.

        Args:
            app: The core application instance.
        """
        self.app = app
        self._undo_stack: list[Action] = []
        self._redo_stack: list[Action] = []

    def push(self, action: Action) -> None:
        """Register a newly executed action and clear the redo history.

        Args:
            action: The executed action to store.
        """
        if action.can_undo:
            self._undo_stack.append(action)
            self._redo_stack.clear()
            self.notify_ui_and_controllers()

    def undo(self) -> None:
        """Undo the last reversible action."""
        if not self._undo_stack:
            return

        action = self._undo_stack.pop()
        try:
            action.undo()
            self._redo_stack.append(action)
            self.notify_ui_and_controllers()
        except Exception as err:  # pylint: disable=broad-exception-caught
            # In case undo fails, log and push it back to maintain consistency
            print(f"[HistoryManager] Error during undo of '{action.name}': {err}")
            self._undo_stack.append(action)

    def redo(self) -> None:
        """Redo the last undone action."""
        if not self._redo_stack:
            return

        action = self._redo_stack.pop()
        try:
            action.redo()
            self._undo_stack.append(action)
            self.notify_ui_and_controllers()
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[HistoryManager] Error during redo of '{action.name}': {err}")
            self._redo_stack.append(action)

    def notify_ui_and_controllers(self) -> None:
        """Update states of Undo/Redo triggers on physical surfaces and GUI."""
        self.app.emit(
            "history.changed",
            {
                "can_undo": len(self._undo_stack) > 0,
                "can_redo": len(self._redo_stack) > 0,
            },
        )
        self.app.action_registry.trigger_feedback("edit.undo")
        self.app.action_registry.trigger_feedback("edit.redo")

    def clear(self) -> None:
        """Clear both undo and redo stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.notify_ui_and_controllers()
