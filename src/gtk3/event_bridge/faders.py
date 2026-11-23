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
"""GUI event bridge handler for faders, pages, flashes, and buttons."""

from __future__ import annotations

import typing

from olc.gtk3.fader import FaderTab

from .base import BaseEventBridgeHandler


# pylint: disable=too-few-public-methods
class FaderBridgeHandler(BaseEventBridgeHandler):
    """Handles fader level, flash, assignment, and virtual console button events."""

    def register(self) -> None:
        """Subscribe to Core events for faders and button feedback."""
        self.app.core.subscribe(
            "fader.page_changed",
            lambda page: self._run_idle(self._on_fader_page_changed, page),
        )
        self.app.core.subscribe(
            "fader.page_count_changed",
            lambda count: self._run_idle(self._on_fader_page_count_changed, count),
        )
        self.app.core.subscribe(
            "fader.level_changed",
            lambda fader_index, level: self._run_idle(
                self._on_fader_level_changed, fader_index, level
            ),
        )
        self.app.core.subscribe(
            "fader.flash_changed",
            lambda fader_index, pressed: self._run_idle(
                self._on_fader_flash_changed, fader_index, pressed
            ),
        )
        self.app.core.subscribe(
            "fader.changed",
            lambda page, index: self._run_idle(
                self._on_fader_assignment_changed, page, index
            ),
        )
        self.app.core.subscribe(
            "button.pressed",
            lambda name, pressed: self._run_idle(
                self._on_button_pressed, name, pressed
            ),
        )

    def _on_fader_page_changed(self, _page: int) -> bool:
        """Synchronize fader page changes to the GUI.

        Args:
            _page: Active page number.

        Returns:
            Always False.
        """
        if self.app.virtual_console:
            self.app.virtual_console.update_page_display()
        return False

    def _on_fader_page_count_changed(self, _count: int) -> bool:
        """Refresh FaderTab when total available fader pages change.

        Args:
            _count: Updated total fader page count.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("faders") is not None:
            fader_tab = typing.cast(FaderTab, self.app.tabs.tabs["faders"])
            fader_tab.refresh()
        return False

    def _on_fader_level_changed(self, fader_index: int, level: float) -> bool:
        """Synchronize fader level to GUI.

        Args:
            fader_index: Fader index (1-based).
            level: Level in [0.0, 1.0].

        Returns:
            Always False.
        """
        if self.app.virtual_console:
            self.app.virtual_console.updating_fader = True
            try:
                self.app.virtual_console.faders[fader_index - 1].set_value(level * 255)
            finally:
                self.app.virtual_console.updating_fader = False
        return False

    def _on_fader_flash_changed(self, fader_index: int, pressed: bool) -> bool:
        """Synchronize flash button redraw and slider level on Virtual Console.

        Args:
            fader_index: Fader index (1-based).
            pressed: Flash button pressed state.

        Returns:
            Always False.
        """
        if self.app.virtual_console:
            vc = self.app.virtual_console
            fader = self.app.core.lightshow.fader_bank.get_fader(fader_index)
            vc.updating_fader = True
            try:
                vc.faders[fader_index - 1].set_value(
                    255 if pressed else round(fader.level * 255)
                )
            finally:
                vc.updating_fader = False
            vc.flashes[fader_index - 1].queue_draw()
        return False

    def _on_fader_assignment_changed(self, page: int, index: int) -> bool:
        """Refresh the FaderTab and Virtual Console when a fader assignment changes.

        Args:
            page: Fader page number.
            index: Fader index within the page.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("faders") is not None:
            fader_tab = typing.cast(FaderTab, self.app.tabs.tabs["faders"])
            fader_tab.refresh()
        fader_bank = self.app.core.lightshow.fader_bank
        if self.app.virtual_console and (
            page == fader_bank.active_page
            or fader_bank.resolve_page(fader_bank.active_page, index) == page
        ):
            vc = self.app.virtual_console
            fader = fader_bank.get_fader(index)
            vc.updating_fader = True
            try:
                vc.faders[index - 1].set_value(round(fader.level * 255))
            finally:
                vc.updating_fader = False
            vc.flashes[index - 1].label = vc.format_fader_flash_label(fader)
            vc.flashes[index - 1].queue_draw()
        return False

    def _on_button_pressed(self, name: str, pressed: bool) -> bool:
        """Handle visual button pressed/released state feedback on Virtual Console.

        Args:
            name: Button attribute name.
            pressed: Pressed state.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, name):
            widget = getattr(vc, name)
            if hasattr(widget, "pressed"):
                widget.pressed = pressed
                widget.queue_draw()
        return False
