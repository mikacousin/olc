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

from gi.repository import GLib, Pango
from olc.define import MAX_CHANNELS
from olc.fader import FaderType
from olc.fader_edition import FaderTab

if typing.TYPE_CHECKING:
    from olc.application import Application
    from olc.core.group import Group
    from olc.group import GroupTab


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
        self._pause_blink_state: bool = False
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
        self.app.core.subscribe(
            "crossfade.at_full",
            lambda next_step, subtitle: self._run_idle(
                self._on_crossfade_at_full, next_step, subtitle
            ),
        )
        self.app.core.subscribe(
            "crossfade.scale_updated",
            lambda scale_name, position, total_time, step: self._run_idle(
                self._on_crossfade_scale_updated, scale_name, position, total_time, step
            ),
        )
        self.app.core.subscribe(
            "playback.step_changed",
            lambda data: self._run_idle(self._on_playback_step_changed, data),
        )
        self.app.core.subscribe(
            "playback.goto_selected",
            lambda data: self._run_idle(self._on_playback_goto_selected, data),
        )
        self.app.core.subscribe(
            "playback.go_triggered_direct",
            lambda data: self._run_idle(self._on_playback_go_triggered_direct, data),
        )
        self.app.core.subscribe(
            "playback.go_back_started",
            lambda data: self._run_idle(self._on_playback_go_back_started, data),
        )
        self.app.core.subscribe(
            "playback.transition_progress",
            lambda data: self._run_idle(self._on_playback_transition_progress, data),
        )
        self.app.core.subscribe(
            "playback.transition_completed",
            lambda data: self._run_idle(self._on_playback_transition_completed, data),
        )
        self.app.core.subscribe(
            "playback.goback_progress",
            lambda data: self._run_idle(self._on_playback_goback_progress, data),
        )
        self.app.core.subscribe(
            "playback.goback_completed",
            lambda data: self._run_idle(self._on_playback_goback_completed, data),
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

    def _on_go_triggered(self, feedback: dict[str, typing.Any]) -> bool:
        """Handle the go triggered event by updating the active state of the Go button.

        Args:
            feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        vc = self.app.virtual_console
        if vc and hasattr(vc, "go_button") and vc.go_button:
            if self._go_timeout_id is not None:
                GLib.source_remove(self._go_timeout_id)
                self._go_timeout_id = None
            active = bool(feedback.get("active", False))
            go_btn = typing.cast(typing.Any, vc.go_button)
            go_btn.go_active = active
            go_btn.queue_draw()
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
        """Handle the pause triggered event by blinking the Pause button.

        Args:
            feedback: Feedback state dictionary.

        Returns:
            Always False.
        """
        active = bool(feedback.get("active", False))
        vc = self.app.virtual_console
        if self._pause_timeout_id is not None:
            GLib.source_remove(self._pause_timeout_id)
            self._pause_timeout_id = None

        if active:
            self._pause_blink_state = True
            if vc and hasattr(vc, "pause") and vc.pause:
                vc.pause.btn_pressed = True
                vc.pause.queue_draw()
            self._pause_timeout_id = GLib.timeout_add(500, self._on_pause_blink)
        else:
            if vc and hasattr(vc, "pause") and vc.pause:
                vc.pause.btn_pressed = False
                vc.pause.queue_draw()
        return False

    def _on_pause_blink(self) -> bool:
        """Toggle pause button state for blinking effect on the GUI."""
        self._pause_blink_state = not getattr(self, "_pause_blink_state", False)
        vc = self.app.virtual_console
        if vc and hasattr(vc, "pause") and vc.pause:
            vc.pause.btn_pressed = self._pause_blink_state
            vc.pause.queue_draw()
        return True

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

    def sync_virtual_console(self) -> None:
        """Sync the state of virtual console buttons with the core states."""
        vc = self.app.virtual_console
        if not vc:
            return

        main_playback = self.app.core.lightshow.main_playback
        if not main_playback:
            return

        # 1. Sync GO button
        if hasattr(vc, "go_button") and vc.go_button:
            vc.go_button.go_active = bool(main_playback.on_go)
            vc.go_button.queue_draw()

        # 2. Sync PAUSE button
        is_paused = False
        if main_playback.on_go and main_playback.thread:
            is_paused = not main_playback.thread.pause.is_set()

        self._on_pause_triggered({"active": is_paused})

        # 3. Sync Crossfade sliders
        if hasattr(self.app, "crossfade") and self.app.crossfade:
            if hasattr(vc, "scale_a") and vc.scale_a:
                vc.scale_a.set_value(self.app.crossfade.scale_a.get_value())
            if hasattr(vc, "scale_b") and vc.scale_b:
                vc.scale_b.set_value(self.app.crossfade.scale_b.get_value())

    def _on_crossfade_at_full(self, next_step: int, subtitle: str) -> bool:
        """Safely update crossfade UI values when crossfade reaches full."""
        if self.app.window and self.app.window.playback:
            self.app.window.playback.sequential.total_time = (
                self.app.core.lightshow.main_playback.steps[next_step].total_time
            )
            self.app.window.playback.sequential.time_in = (
                self.app.core.lightshow.main_playback.steps[next_step].time_in
            )
            self.app.window.playback.sequential.time_out = (
                self.app.core.lightshow.main_playback.steps[next_step].time_out
            )
            self.app.window.playback.sequential.delay_in = (
                self.app.core.lightshow.main_playback.steps[next_step].delay_in
            )
            self.app.window.playback.sequential.delay_out = (
                self.app.core.lightshow.main_playback.steps[next_step].delay_out
            )
            self.app.window.playback.sequential.wait = (
                self.app.core.lightshow.main_playback.steps[next_step].wait
            )
            self.app.window.playback.sequential.channel_time = (
                self.app.core.lightshow.main_playback.steps[next_step].channel_time
            )
            self.app.window.playback.sequential.position_a = 0
            self.app.window.playback.sequential.position_b = 0
        update_ui(subtitle, typing.cast(typing.Any, self.app))
        return False

    def _on_crossfade_scale_updated(
        self, scale_name: str, position: float, total_time: float, step: int
    ) -> bool:
        """Safely update progress sliders and redraw sequential display."""
        if not (self.app.window and self.app.window.playback):
            return False

        alloc_width = self.app.window.playback.sequential.get_allocation().width
        ratio = (alloc_width - 32) / total_time * position

        if scale_name == "scale_a":
            self.app.window.playback.sequential.position_a = int(ratio)
            self.app.window.playback.show_timeleft_out(position)
        elif scale_name == "scale_b":
            self.app.window.playback.sequential.position_b = int(ratio)
            self.app.window.playback.show_timeleft_in(position)

        if self.app.crossfade:
            value = min(
                self.app.crossfade.scale_a.get_value(),
                self.app.crossfade.scale_b.get_value(),
            )
            progress = min(max(value / 255.0, 0.0), 1.0)
            self.app.window.playback.update_cue_crossfade_color(step, progress)
            self.app.window.playback.sequential.queue_draw()
        return False

    def _on_playback_step_changed(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            seq = self.app.window.playback.sequential
            seq.total_time = data["total_time"]
            seq.time_in = data["time_in"]
            seq.time_out = data["time_out"]
            seq.delay_in = data["delay_in"]
            seq.delay_out = data["delay_out"]
            seq.wait = data["wait"]
            seq.channel_time = data["channel_time"]
            seq.position_a = 0
            seq.position_b = 0
        update_ui(data["subtitle"], self.app)
        return False

    def _on_playback_goto_selected(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            playback = self.app.window.playback
            old_pos = data["old_pos"]
            playback.sequential.total_time = data["total_time"]
            playback.sequential.time_in = data["time_in"]
            playback.sequential.time_out = data["time_out"]
            playback.sequential.delay_in = data["delay_in"]
            playback.sequential.delay_out = data["delay_out"]
            playback.sequential.wait = data["wait"]
            playback.sequential.channel_time = data["channel_time"]
            playback.sequential.position_a = 0
            playback.sequential.position_b = 0

            playback.cues_liststore1[old_pos][9] = "#232729"
            playback.cues_liststore1[old_pos][10] = Pango.Weight.NORMAL
            playback.update_active_cues_display()
            playback.grid.queue_draw()
        return False

    def _on_playback_go_triggered_direct(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            playback = self.app.window.playback
            playback.sequential.total_time = data["total_time"]
            playback.sequential.time_in = data["time_in"]
            playback.sequential.time_out = data["time_out"]
            playback.sequential.delay_in = data["delay_in"]
            playback.sequential.delay_out = data["delay_out"]
            playback.sequential.wait = data["wait"]
            playback.sequential.channel_time = data["channel_time"]
            playback.sequential.position_a = 0
            playback.sequential.position_b = 0

            playback.update_active_cues_display()
            playback.grid.queue_draw()
            playback.display_times()
        if self.app.window:
            self.app.window.header.set_subtitle(data["subtitle"])
        return False

    def _on_playback_go_back_started(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            playback = self.app.window.playback
            goback_time = data["goback_time"]
            playback.sequential.total_time = goback_time
            playback.sequential.time_in = goback_time
            playback.sequential.time_out = goback_time
            playback.sequential.delay_in = 0
            playback.sequential.delay_out = 0
            playback.sequential.wait = 0
            playback.sequential.channel_time = {}
            playback.sequential.position_a = 0
            playback.sequential.position_b = 0

            playback.grid.queue_draw()
        if self.app.window:
            self.app.window.header.set_subtitle(data["subtitle"])
        return False

    def _on_playback_transition_progress(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            playback = self.app.window.playback
            time_spent = data["time_spent"]
            total_time = data["total_time"]
            val = data["progress_val"]
            alloc_width = playback.sequential.get_allocation().width
            ratio = ((alloc_width - 32) / total_time) * time_spent
            playback.sequential.position_a = ratio
            playback.sequential.position_b = ratio
            playback.sequential.queue_draw()
            playback.show_timeleft(time_spent)

            vc = self.app.virtual_console
            if vc and vc.props.visible:
                vc.scale_a.set_value(val)
                vc.scale_b.set_value(val)
        return False

    def _on_playback_transition_completed(self, _data: dict[str, typing.Any]) -> bool:
        return False

    def _on_playback_goback_progress(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            playback = self.app.window.playback
            time_spent = data["time_spent"]
            goback_time = data["goback_time"]
            position = data["position"]
            val = data["progress_val"]
            alloc_width = playback.sequential.get_allocation().width
            ratio = ((alloc_width - 32) / goback_time) * time_spent
            playback.sequential.position_a = ratio
            playback.sequential.position_b = ratio
            playback.sequential.queue_draw()
            playback.goback_countdown(time_spent, goback_time, position)

            vc = self.app.virtual_console
            if vc and vc.props.visible:
                vc.scale_a.set_value(val)
                vc.scale_b.set_value(val)
        return False

    def _on_playback_goback_completed(self, data: dict[str, typing.Any]) -> bool:
        if self.app.window and self.app.window.playback:
            playback = self.app.window.playback
            playback.sequential.time_in = data["time_in"]
            playback.sequential.time_out = data["time_out"]
            playback.sequential.delay_in = data["delay_in"]
            playback.sequential.delay_out = data["delay_out"]
            playback.sequential.wait = data["wait"]
            playback.sequential.total_time = data["total_time"]
            playback.sequential.channel_time = data["channel_time"]
            playback.sequential.position_a = 0
            playback.sequential.position_b = 0
        update_ui(data["subtitle"], self.app)
        return False


def update_ui(subtitle: str, app: Application | None = None) -> None:
    """Update user interface when Step is in scene. (Relocated to GUI Bridge)"""
    if not app:
        return
    # Update Sequential Tab
    if app.window:
        app.window.playback.update_active_cues_display()
        app.window.playback.grid.queue_draw()
        # Cue times
        app.window.playback.display_times()
        # Update Main Window's Subtitle
        app.window.header.set_subtitle(subtitle)

        # Update Channels display
        if app.window.live_view:
            main_playback = app.core.lightshow.main_playback
            step = main_playback.steps[main_playback.position]
            for channel in range(1, MAX_CHANNELS + 1):
                seq_level = 0
                if step.cue is not None:
                    seq_level = step.cue.channels.get(channel, 0)
                seq_next_level = main_playback.get_next_channel_level(
                    channel, seq_level
                )
                app.window.live_view.update_channel_widget(channel, seq_next_level)
    # Virtual Console crossfade
    if app.virtual_console and app.virtual_console.props.visible:
        if app.virtual_console.scale_a.get_inverted():
            app.virtual_console.scale_a.set_inverted(False)
            app.virtual_console.scale_b.set_inverted(False)
        else:
            app.virtual_console.scale_a.set_inverted(True)
            app.virtual_console.scale_b.set_inverted(True)
        app.virtual_console.scale_a.set_value(0)
        app.virtual_console.scale_b.set_value(0)
