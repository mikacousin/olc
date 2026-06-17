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
from abc import ABC, abstractmethod

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class Action(ABC):
    """Base class for all application actions (Command Pattern).

    Supports headless execution, Undo/Redo, and state feedback for physical
    controllers.
    """

    name: str = ""  # Unique action identifier (e.g., "group.new")
    can_undo: bool = False  # Set to True if the action supports undo/redo

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        self.app = app

    @abstractmethod
    def execute(self) -> object:
        """Execute the action using its already-configured state.

        Must be implemented by all subclasses. Arguments are provided
        via configure() before this method is called.
        """

    def undo(self) -> None:
        """Revert the state changes made by execute().

        Must be overridden if can_undo is True.
        """
        if not self.can_undo:
            raise NotImplementedError(f"Action '{self.name}' does not support undo.")

    def redo(self) -> None:
        """Reapply the action. Defaults to calling execute() with saved state."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the current state of this action for MIDI/OSC feedback.

        Returns:
            A dictionary representing feedback parameters (e.g., {'active': True}).
        """
        return {}
