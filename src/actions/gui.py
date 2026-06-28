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
    from olc.core.app import CoreApplication


class ZoomAction(Action):
    """Action to change GUI zoom level with undo/redo support."""

    name = "gui.zoom"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.target_zoom: float = 1.0
        self.old_zoom_level: float = 1.0

    def configure(self, target_zoom: float) -> None:
        """Configure the target zoom level.

        Args:
            target_zoom: The target zoom level value.
        """
        self.target_zoom = target_zoom

    def execute(self) -> None:
        self.old_zoom_level = getattr(self.app, "zoom_level", 1.0)
        self.app.zoom_level = self.target_zoom
        self.app.emit("gui.zoom_changed", self.target_zoom)

    def undo(self) -> None:
        self.app.zoom_level = self.old_zoom_level
        self.app.emit("gui.zoom_changed", self.old_zoom_level)

    def redo(self) -> None:
        self.app.zoom_level = self.target_zoom
        self.app.emit("gui.zoom_changed", self.target_zoom)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        return {
            "level": self.target_zoom,
        }


class SwitchTabAction(Action):
    """Action to switch active GUI tab with undo/redo support."""

    name = "gui.switch_tab"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.target_tab: str = ""
        self.old_tab: str = ""

    def configure(self, target_tab: str) -> None:
        """Configure the target active tab name.

        Args:
            target_tab: The target active tab name.
        """
        self.target_tab = target_tab

    def execute(self) -> None:
        self.old_tab = getattr(self.app, "active_tab", "channels")
        self.app.active_tab = self.target_tab
        self.app.emit("gui.active_tab_changed", self.target_tab)

    def undo(self) -> None:
        self.app.active_tab = self.old_tab
        self.app.emit("gui.active_tab_changed", self.old_tab)

    def redo(self) -> None:
        self.app.active_tab = self.target_tab
        self.app.emit("gui.active_tab_changed", self.target_tab)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        return {
            "active_tab": self.target_tab,
        }
