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
        """Synchronize fader page changes to the GUI and MIDI controller.

        Args:
            _page: Active page number.

        Returns:
            Always False.
        """
        if self.app.virtual_console:
            self.app.virtual_console.update_page_display()
        else:
            if self.app.midi is not None:
                self.app.midi.update_faders()
        return False

    def _on_fader_level_changed(self, fader_index: int, level: float) -> bool:
        """Synchronize fader level to GUI or MIDI controller.

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

        if self.app.midi is not None:
            midi_fader = self.app.midi.faders.faders[fader_index - 1]
            midi_fader.set_state(level)
        return False

    def _on_fader_flash_changed(self, fader_index: int, _pressed: bool) -> bool:
        """Queue a redraw on the virtual console flash button.

        Args:
            fader_index: Fader index (1-based).
            _pressed: Flash button pressed state.

        Returns:
            Always False.
        """
        if self.app.virtual_console:
            self.app.virtual_console.flashes[fader_index - 1].queue_draw()
        return False

    def _on_fader_assignment_changed(self, _page: int, _index: int) -> bool:
        """Refresh the FaderTab when a fader assignment changes.

        Args:
            _page: Fader page number (unused, full refresh is simpler).
            _index: Fader index within the page (unused).

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("faders") is not None:
            fader_tab = typing.cast(FaderTab, self.app.tabs.tabs["faders"])
            fader_tab.refresh()
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
