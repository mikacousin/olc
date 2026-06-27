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
"""Actions for independents (independent.set_level, independent.update_channels,
independent.rename)."""

from __future__ import annotations

import typing

from olc.core.action import Action
from olc.independent import IndependentType

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class IndependentSetLevelAction(Action):
    """Action to set independent level in real time."""

    name = "independent.set_level"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: int = 1
        self.level: float = 0.0

    def configure(self, number: int, level: float) -> None:
        """Configure the action parameters.

        Args:
            number: Independent number (1 to 9).
            level: The target intensity level (0.0 to 1.0).
        """
        self.number = number
        self.level = level

    def execute(self) -> None:
        """Apply the level to the independent and emit event."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        inde.set_level(self.level)
        self.app.emit("independent.level_changed", self.number, self.level)


class IndependentUpdateChannelsAction(Action):
    """Action to update independent channels configuration."""

    name = "independent.update_channels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: int = 1
        self.levels: dict[int, int] = {}
        self.old_levels: dict[int, int] = {}

    def configure(self, number: int, levels: dict[int, int]) -> None:
        """Configure the action parameters.

        Args:
            number: Independent number (1 to 9).
            levels: Channel levels dict.
        """
        self.number = number
        self.levels = levels

    def execute(self) -> None:
        """Apply the channels level configuration."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        self.old_levels = dict(inde.levels)
        inde.set_levels(self.levels)
        independents.update_channels()
        inde.update_dmx()
        self.app.lightshow.set_modified()
        self.app.emit("independent.channels_changed", self.number)

    def undo(self) -> None:
        """Restore the previous channels level configuration."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        inde.set_levels(self.old_levels)
        independents.update_channels()
        inde.update_dmx()
        self.app.lightshow.set_modified()
        self.app.emit("independent.channels_changed", self.number)

    def redo(self) -> None:
        """Re-apply the channels level configuration."""
        self.execute()


class IndependentRenameAction(Action):
    """Action to rename an independent."""

    name = "independent.rename"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: int = 1
        self.text: str = ""
        self.old_text: str = ""

    def configure(self, number: int, text: str) -> None:
        """Configure the action parameters.

        Args:
            number: Independent number (1 to 9).
            text: New text.
        """
        self.number = number
        self.text = text

    def execute(self) -> None:
        """Rename the independent."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        self.old_text = inde.text
        inde.text = self.text
        self.app.lightshow.set_modified()
        self.app.emit("independent.text_changed", self.number, self.text)

    def undo(self) -> None:
        """Restore the previous name."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        inde.text = self.old_text
        self.app.lightshow.set_modified()
        self.app.emit("independent.text_changed", self.number, self.old_text)

    def redo(self) -> None:
        """Re-rename the independent."""
        self.execute()


class IndependentChangeTypeAction(Action):
    """Action to change the type of an independent."""

    name = "independent.change_type"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.number: int = 1
        self.inde_type: IndependentType = IndependentType.KNOB
        self.old_inde_type: IndependentType = IndependentType.KNOB

    def configure(self, number: int, inde_type: str | IndependentType) -> None:
        """Configure the action parameters.

        Args:
            number: Independent number (1 to 9).
            inde_type: New type.
        """
        self.number = number
        self.inde_type = IndependentType(inde_type)

    def execute(self) -> None:
        """Change the independent type."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        self.old_inde_type = inde.inde_type
        inde.inde_type = self.inde_type
        self.app.lightshow.set_modified()
        self.app.emit("independent.type_changed", self.number, self.inde_type)

    def undo(self) -> None:
        """Restore the previous type."""
        independents = self.app.lightshow.independents
        inde = independents.independents[self.number - 1]
        inde.inde_type = self.old_inde_type
        self.app.lightshow.set_modified()
        self.app.emit("independent.type_changed", self.number, self.old_inde_type)

    def redo(self) -> None:
        """Re-apply the type change."""
        self.execute()
