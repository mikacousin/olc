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
    pass


class UndoAction(Action):
    """System action to trigger an undo operation."""

    name = "edit.undo"
    can_undo = False  # Undo operations cannot be undone (reverted by redo)

    def execute(self) -> None:
        """Execute the undo operation in the history manager."""
        self.app.history.undo()


class RedoAction(Action):
    """System action to trigger a redo operation."""

    name = "edit.redo"
    can_undo = False  # Redo operations cannot be undone (reverted by undo)

    def execute(self) -> None:
        """Execute the redo operation in the history manager."""
        self.app.history.redo()
