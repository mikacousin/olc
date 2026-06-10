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
"""Bridge connecting Core events to thread-safe GUI updates."""

from __future__ import annotations

import typing

from gi.repository import GLib
from olc.fader import FaderType
from olc.fader_edition import FaderTab

if typing.TYPE_CHECKING:
    from olc.application import Application
    from olc.group import Group, GroupTab


# pylint: disable=too-few-public-methods
class GuiEventBridge:
    """GuiEventBridge maps core events to GTK main-thread UI operations.

    It subscribes to various Core events and triggers the corresponding
    UI refreshes safely on the GTK main loop using GLib.idle_add.
    """

    def __init__(self, app: Application) -> None:
        """Initialize the event bridge and subscribe to Core events.

        Args:
            app: The main application instance.
        """
        self.app = app
        self._go_timeout_id: int | None = None
        self._pause_timeout_id: int | None = None

        # Setup GUI-safe event callbacks from Core
        self.app.core.subscribe(
            "group.created", lambda _: self._run_idle(self._safe_refresh_groups)
        )
        self.app.core.subscribe(
            "group.deleted", lambda g: self._run_idle(self._on_group_deleted, g)
        )
        self.app.core.subscribe(
            "channel.level_changed",
            lambda c, level: self._run_idle(self._on_channel_level_ui, c, level),
        )
        self.app.core.subscribe(
            "playback.go_triggered",
            lambda feedback: self._run_idle(self._on_go_triggered, feedback),
        )
        self.app.core.subscribe(
            "playback.pause_triggered",
            lambda feedback: self._run_idle(self._on_pause_triggered, feedback),
        )

    def _run_idle(self, func: typing.Callable[..., bool], *args: object) -> None:
        """Run a function safely in the GTK main loop, discarding return value.

        Args:
            func: The callable to run on idle.
            *args: Arguments for the function.
        """
        GLib.idle_add(func, *args)

    def _safe_refresh_groups(self) -> bool:
        """Refresh the groups tab UI safely in the GTK thread.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        if self.app.tabs and self.app.tabs.tabs.get("groups") is not None:
            group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
            group_tab.refresh()
        return False

    def _on_group_deleted(self, group: Group) -> bool:
        """Clean up faders referencing the deleted group and refresh UI.

        Args:
            group: The deleted group instance.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        fader_bank = self.app.core.lightshow.fader_bank
        faders_updated = False
        for page, faders in fader_bank.faders.items():
            for fader in faders.values():
                if fader.contents is group:
                    fader_bank.set_fader(page, fader.index, FaderType.NONE, None)
                    faders_updated = True

        self._safe_refresh_groups()
        if (
            faders_updated
            and self.app.tabs
            and self.app.tabs.tabs.get("faders") is not None
        ):
            fader_tab = typing.cast(FaderTab, self.app.tabs.tabs["faders"])
            fader_tab.refresh()
        return False

    def _on_channel_level_ui(self, channel: int, level: int) -> bool:
        """Safely update a channel widget in the GTK main thread.

        Args:
            channel: Channel number.
            level: DMX level.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.update_channel_widget(channel, level)
        return False

    def _on_go_triggered(self, _feedback: dict[str, typing.Any]) -> bool:
        """Handle the go triggered event by flashing the Go button.

        Args:
            _feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, "go_button") and vc.go_button:
            if self._go_timeout_id is not None:
                GLib.source_remove(self._go_timeout_id)
                self._go_timeout_id = None
            vc.go_button.pressed = True
            vc.go_button.queue_draw()
            self._go_timeout_id = GLib.timeout_add(150, self._reset_go_button)
        return False

    def _reset_go_button(self) -> bool:
        """Reset the Go button pressed state after the timeout.

        Returns:
            Always False.
        """
        self._go_timeout_id = None
        vc = self.app.virtual_console
        if vc and hasattr(vc, "go_button") and vc.go_button:
            vc.go_button.pressed = False
            vc.go_button.queue_draw()
        return False

    def _on_pause_triggered(self, feedback: dict[str, typing.Any]) -> bool:
        """Handle the pause triggered event by flashing the Pause button.

        Args:
            feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, "pause") and vc.pause:
            if self._pause_timeout_id is not None:
                GLib.source_remove(self._pause_timeout_id)
                self._pause_timeout_id = None
            vc.pause.btn_pressed = True
            vc.pause.queue_draw()
            active = bool(feedback.get("active", False))
            self._pause_timeout_id = GLib.timeout_add(
                150, self._reset_pause_button, active
            )
        return False

    def _reset_pause_button(self, active: bool) -> bool:
        """Reset the Pause button to its final state after the timeout.

        Args:
            active: The final active state.

        Returns:
            Always False.
        """
        self._pause_timeout_id = None
        vc = self.app.virtual_console
        if vc and hasattr(vc, "pause") and vc.pause:
            vc.pause.btn_pressed = active
            vc.pause.queue_draw()
        return False
