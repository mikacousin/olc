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
from olc.sequence import update_ui

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
        self._goback_timeout_id: int | None = None
        self._pause_timeout_id: int | None = None
        self._seq_plus_timeout_id: int | None = None
        self._seq_minus_timeout_id: int | None = None

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
            "playback.go_back_triggered",
            lambda feedback: self._run_idle(self._on_goback_triggered, feedback),
        )
        self.app.core.subscribe(
            "playback.pause_triggered",
            lambda feedback: self._run_idle(self._on_pause_triggered, feedback),
        )
        self.app.core.subscribe(
            "playback.sequence_plus_triggered",
            lambda feedback: self._run_idle(self._on_seq_plus_triggered, feedback),
        )
        self.app.core.subscribe(
            "playback.sequence_minus_triggered",
            lambda feedback: self._run_idle(self._on_seq_minus_triggered, feedback),
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

    def _on_goback_triggered(self, _feedback: dict[str, typing.Any]) -> bool:
        """Handle the go-back triggered event by flashing the Go Back button.

        Args:
            _feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, "goback") and vc.goback:
            if self._goback_timeout_id is not None:
                GLib.source_remove(self._goback_timeout_id)
                self._goback_timeout_id = None
            vc.goback.pressed = True
            vc.goback.queue_draw()
            self._goback_timeout_id = GLib.timeout_add(150, self._reset_goback_button)
        return False

    def _reset_goback_button(self) -> bool:
        """Reset the Go Back button pressed state after the timeout.

        Returns:
            Always False.
        """
        self._goback_timeout_id = None
        vc = self.app.virtual_console
        if vc and hasattr(vc, "goback") and vc.goback:
            vc.goback.pressed = False
            vc.goback.queue_draw()
        return False

    def _on_pause_triggered(self, feedback: dict[str, typing.Any]) -> bool:
        """Handle the pause triggered event by flashing the Pause button.

        Args:
            feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        active = bool(feedback.get("active", False))
        vc = self.app.virtual_console
        if vc and hasattr(vc, "pause") and vc.pause:
            if self._pause_timeout_id is not None:
                GLib.source_remove(self._pause_timeout_id)
                self._pause_timeout_id = None
            vc.pause.btn_pressed = True
            vc.pause.queue_draw()
            self._pause_timeout_id = GLib.timeout_add(
                150, self._reset_pause_button, active
            )
        if self.app.midi:
            self.app.midi.messages.notes.send("playback.pause", 127 if active else 0)
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

    def _on_seq_plus_triggered(self, feedback: dict[str, typing.Any]) -> bool:
        """Handle the sequence plus triggered event by flashing the Next Cue button.

        Args:
            feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, "seq_plus") and vc.seq_plus:
            if self._seq_plus_timeout_id is not None:
                GLib.source_remove(self._seq_plus_timeout_id)
                self._seq_plus_timeout_id = None
            vc.seq_plus.pressed = True
            vc.seq_plus.queue_draw()
            self._seq_plus_timeout_id = GLib.timeout_add(
                150, self._reset_seq_plus_button
            )
        self._update_sequential_ui(feedback)
        return False

    def _reset_seq_plus_button(self) -> bool:
        """Reset the Next Cue button pressed state after the timeout.

        Returns:
            Always False.
        """
        self._seq_plus_timeout_id = None
        vc = self.app.virtual_console
        if vc and hasattr(vc, "seq_plus") and vc.seq_plus:
            vc.seq_plus.pressed = False
            vc.seq_plus.queue_draw()
        return False

    def _on_seq_minus_triggered(self, feedback: dict[str, typing.Any]) -> bool:
        """Handle the sequence minus triggered event by flashing the Previous Cue
        button.

        Args:
            feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, "seq_minus") and vc.seq_minus:
            if self._seq_minus_timeout_id is not None:
                GLib.source_remove(self._seq_minus_timeout_id)
                self._seq_minus_timeout_id = None
            vc.seq_minus.pressed = True
            vc.seq_minus.queue_draw()
            self._seq_minus_timeout_id = GLib.timeout_add(
                150, self._reset_seq_minus_button
            )
        self._update_sequential_ui(feedback)
        return False

    def _reset_seq_minus_button(self) -> bool:
        """Reset the Previous Cue button pressed state after the timeout.

        Returns:
            Always False.
        """
        self._seq_minus_timeout_id = None
        vc = self.app.virtual_console
        if vc and hasattr(vc, "seq_minus") and vc.seq_minus:
            vc.seq_minus.pressed = False
            vc.seq_minus.queue_draw()
        return False

    def _update_sequential_ui(self, feedback: dict[str, typing.Any]) -> None:
        """Update GTK sequential playback widgets and subtitle from feedback."""
        if not self.app.window:
            return

        playback_view = self.app.window.playback
        if playback_view and playback_view.sequential:
            seq = playback_view.sequential
            seq.total_time = feedback.get("next_total_time", 0.0)
            seq.time_in = feedback.get("next_time_in", 0.0)
            seq.time_out = feedback.get("next_time_out", 0.0)
            seq.delay_in = feedback.get("next_delay_in", 0.0)
            seq.delay_out = feedback.get("next_delay_out", 0.0)
            seq.wait = feedback.get("next_wait", 0.0)
            seq.channel_time = feedback.get("next_channel_time", False)
            seq.position_a = 0
            seq.position_b = 0
            seq.queue_draw()

        # Update Window's subtitle
        cue_mem = feedback.get("cue_memory", 0.0)
        cue_txt = feedback.get("cue_text", "")
        next_mem = feedback.get("next_cue_memory", 0.0)
        next_txt = feedback.get("next_cue_text", "")

        subtitle = f"Mem. : {cue_mem} {cue_txt} - Next Mem. : {next_mem} {next_txt}"
        update_ui(subtitle, typing.cast(typing.Any, self.app))
