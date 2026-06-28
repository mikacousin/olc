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

from gi.repository import GLib, Gtk, Pango
from olc.curve import LimitCurve, PointsCurve
from olc.define import MAX_CHANNELS
from olc.fader import FaderType
from olc.gtk3.channel_time import ChanneltimeTab
from olc.gtk3.fader import FaderTab
from olc.gtk3.patch_outputs import PatchOutputsTab
from olc.gtk3.widgets.channel import ChannelWidget
from olc.gtk3.widgets.channels_view import ChannelsView
from olc.independent import IndependentType

if typing.TYPE_CHECKING:
    from olc.group import Group
    from olc.gtk3.application import Application
    from olc.gtk3.cue import CuesEditionTab
    from olc.gtk3.curve import CurvesTab
    from olc.gtk3.group import GroupTab
    from olc.gtk3.patch_channels import PatchChannelsTab
    from olc.gtk3.sequence import SequenceTab
    from olc.gtk3.track_channels import TrackChannelsTab
    from olc.gtk3.widgets.group import GroupWidget
    from olc.sequence import Sequence


# pylint: disable=too-few-public-methods, too-many-lines
class GuiEventBridge:
    """GuiEventBridge maps core events to GTK main-thread UI operations.

    It subscribes to various Core events and triggers the corresponding
    UI refreshes safely on the GTK main loop using GLib.idle_add.
    """

    # pylint: disable=too-many-statements
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
            "group.updated", lambda g: self._run_idle(self._on_group_updated, g)
        )
        self.app.core.subscribe(
            "cue.created",
            lambda sequence, number: self._run_idle(
                self._safe_refresh_cues, sequence, number
            ),
        )
        self.app.core.subscribe(
            "cue.deleted",
            lambda sequence, number: self._run_idle(
                self._safe_refresh_cues, sequence, number
            ),
        )
        self.app.core.subscribe(
            "cue.updated",
            lambda sequence, number: self._run_idle(
                self._safe_refresh_cues, sequence, number
            ),
        )
        self.app.core.subscribe(
            "cue_editor.changed",
            lambda sequence, number: self._run_idle(
                self._safe_refresh_cue_editor, sequence, number
            ),
        )
        self.app.core.subscribe(
            "group_editor.changed",
            lambda index: self._run_idle(self._safe_refresh_group_editor, index),
        )
        self.app.core.subscribe(
            "patch.changed", lambda: self._run_idle(self._safe_refresh_patch)
        )
        self.app.core.subscribe(
            "patch.selected_outputs_changed",
            lambda: self._run_idle(self._on_selected_outputs_changed),
        )
        self.app.core.subscribe(
            "curve.changed",
            lambda curve_nb: self._run_idle(self._safe_refresh_curves, curve_nb),
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
        self.app.core.subscribe(
            "channels.selected_changed",
            lambda selected: self._run_idle(
                self._on_channels_selected_changed, selected
            ),
        )
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
            "independent.level_changed",
            lambda number, level: self._run_idle(
                self._on_independent_level_changed, number, level
            ),
        )
        self.app.core.subscribe(
            "independent.channels_changed",
            lambda number: self._run_idle(
                self._on_independent_channels_changed, number
            ),
        )
        self.app.core.subscribe(
            "independent.text_changed",
            lambda number, text: self._run_idle(
                self._on_independent_text_changed, number, text
            ),
        )
        self.app.core.subscribe(
            "independent.type_changed",
            lambda number, inde_type: self._run_idle(
                self._on_independent_type_changed, number, inde_type
            ),
        )
        self.app.core.subscribe(
            "group.selected_changed",
            lambda group_nb: self._run_idle(self._on_group_selected_changed, group_nb),
        )
        self.app.core.subscribe(
            "cue.selected_changed",
            lambda cue_id: self._run_idle(self._on_cue_selected_changed, cue_id),
        )
        self.app.core.subscribe(
            "button.pressed",
            lambda name, pressed: self._run_idle(
                self._on_button_pressed, name, pressed
            ),
        )
        self.app.core.subscribe(
            "gui.zoom_changed",
            lambda level: self._run_idle(self._on_zoom_changed, level),
        )
        self.app.core.subscribe(
            "gui.active_tab_changed",
            lambda tab_name: self._run_idle(self._on_active_tab_changed, tab_name),
        )
        self.app.core.subscribe(
            "sequence.created",
            lambda seq: self._run_idle(self._on_sequence_created, seq),
        )
        self.app.core.subscribe(
            "sequence.deleted",
            lambda seq: self._run_idle(self._on_sequence_deleted, seq),
        )
        self.app.core.subscribe(
            "step.inserted",
            lambda seq_idx, step_idx: self._run_idle(
                self._on_step_changed, seq_idx, step_idx
            ),
        )
        self.app.core.subscribe(
            "step.deleted",
            lambda seq_idx, step_idx: self._run_idle(
                self._on_step_changed, seq_idx, step_idx
            ),
        )
        self.app.core.subscribe(
            "step.updated",
            lambda seq_idx, step_idx: self._run_idle(
                self._on_step_changed, seq_idx, step_idx
            ),
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

    def _on_group_updated(self, group: Group) -> bool:
        """Update group UI, fader text, virtual console, and midi LCD on group update.

        Returns:
            Always False.
        """
        self._safe_refresh_groups()

        # Update fader text, virtual console and MIDI LCD if needed
        text = group.text
        fader_bank = self.app.core.lightshow.fader_bank
        for page, faders in fader_bank.faders.items():
            for fader in faders.values():
                if fader.contents is group:
                    fader.text = text
                    # Update Virtual Console
                    if self.app.virtual_console and page == fader_bank.active_page:
                        self.app.virtual_console.flashes[fader.index - 1].label = text
        if self.app.midi:
            self.app.midi.messages.lcd.show_faders()

        # Update the widgets in the GroupTab if we renamed
        if self.app.tabs and self.app.tabs.tabs.get("groups") is not None:
            group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
            for child in group_tab.flowbox.get_children():
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                group_widget = fb_child.get_child()
                # Use duck typing or getattr to read number/name safely
                if (
                    group_widget
                    and getattr(group_widget, "number", None) == group.index
                ):
                    typing.cast("GroupWidget", group_widget).name = text
                    group_widget.queue_draw()
        return False

    def _safe_refresh_cues(self, sequence: int, number: float) -> bool:
        """Refresh the cues (memories) tab and playback UI safely in the GTK thread.

        Returns:
            Always False.
        """
        if self.app.tabs:
            if self.app.tabs.tabs.get("memories") is not None:
                memories_tab = typing.cast(
                    "CuesEditionTab", self.app.tabs.tabs["memories"]
                )
                path, _ = memories_tab.treeview.get_cursor()
                if path:
                    row = path.get_indices()[0]
                    if 0 <= row < len(memories_tab.lightshow.cues):
                        selected_cue = memories_tab.lightshow.cues[row]
                        if (
                            selected_cue.sequence == sequence
                            and selected_cue.number == number
                        ):
                            memories_tab.lightshow.cues.cue_editor.clear(
                                number, sequence
                            )
                memories_tab.refresh()
            if self.app.tabs.tabs.get("sequences") is not None:
                sequences_tab = typing.cast(
                    "SequenceTab", self.app.tabs.tabs["sequences"]
                )
                sequences_tab.refresh()
            if self.app.tabs.tabs.get("track_channels") is not None:
                track_tab = typing.cast(
                    "TrackChannelsTab", self.app.tabs.tabs["track_channels"]
                )
                track_tab.refresh()
        if self.app.window and self.app.window.playback:
            self.app.window.playback.update_sequence_display()

        # Update Live View if the modified cue is active
        self._update_live_view_active_cue(sequence, number)
        return False

    def _on_sequence_created(self, _sequence: Sequence) -> bool:
        """Handle sequence creation event to refresh UI."""
        if self.app.tabs and self.app.tabs.tabs.get("sequences") is not None:
            sequences_tab = typing.cast("SequenceTab", self.app.tabs.tabs["sequences"])
            sequences_tab.refresh()
        return False

    def _on_sequence_deleted(self, _sequence: Sequence) -> bool:
        """Handle sequence deletion event to refresh UI."""
        if self.app.tabs and self.app.tabs.tabs.get("sequences") is not None:
            sequences_tab = typing.cast("SequenceTab", self.app.tabs.tabs["sequences"])
            sequences_tab.refresh()
        return False

    def _on_step_changed(self, sequence_idx: float, step_idx: int) -> bool:
        """Handle step changes (insert, delete, update) to refresh UI tabs."""
        if self.app.tabs:
            if self.app.tabs.tabs.get("sequences") is not None:
                sequences_tab = typing.cast(
                    "SequenceTab", self.app.tabs.tabs["sequences"]
                )
                selected_seq = sequences_tab.get_selected_sequence()
                if selected_seq and selected_seq.index == sequence_idx:
                    sequences_tab.on_sequence_changed(step_idx=step_idx)
            if self.app.tabs.tabs.get("channel_time") is not None:
                ct_tab = typing.cast(ChanneltimeTab, self.app.tabs.tabs["channel_time"])
                if (
                    ct_tab.sequence.index == sequence_idx
                    and int(ct_tab.position) == step_idx
                ):
                    ct_tab.repopulate_liststore()
                    ct_tab.channels_view.update()
        if sequence_idx == 1.0 and self.app.window:
            if self.app.window.playback:
                self.app.window.playback.update_sequence_display()
                lightshow = self.app.core.lightshow
                if 0 <= step_idx < len(lightshow.main_playback.steps):
                    if lightshow.main_playback.position + 1 == step_idx:
                        step_obj = lightshow.main_playback.steps[step_idx]
                        self.app.window.playback.sequential.wait = step_obj.wait
                        self.app.window.playback.sequential.time_in = step_obj.time_in
                        self.app.window.playback.sequential.time_out = step_obj.time_out
                        self.app.window.playback.sequential.delay_in = step_obj.delay_in
                        self.app.window.playback.sequential.delay_out = (
                            step_obj.delay_out
                        )
                        self.app.window.playback.sequential.total_time = (
                            step_obj.total_time
                        )
                        self.app.window.playback.sequential.queue_draw()

            # Update header subtitle if needed
            lightshow = self.app.core.lightshow
            sequence = lightshow.main_playback
            if step_idx in (sequence.position, sequence.position + 1):
                if 0 <= sequence.position < len(
                    sequence.steps
                ) and 0 <= sequence.position + 1 < len(sequence.steps):
                    cue_step = sequence.steps[sequence.position].cue
                    cue_next = sequence.steps[sequence.position + 1].cue
                    number_step = cue_step.number if cue_step is not None else 0.0
                    number_next = cue_next.number if cue_next is not None else 0.0
                    subtitle = (
                        f"Mem. : {number_step} "
                        f"{sequence.steps[sequence.position].text} - Next Mem. : "
                        f"{number_next} "
                        f"{sequence.steps[sequence.position + 1].text}"
                    )
                    self.app.window.header.set_subtitle(subtitle)
        return False

    def _safe_refresh_cue_editor(self, sequence: int, number: float) -> bool:
        """Refresh the channel view in memories tab when temporary overrides change.

        Returns:
            Always False.
        """
        if self.app.tabs:
            if self.app.tabs.tabs.get("memories") is not None:
                memories_tab = typing.cast(
                    "CuesEditionTab", self.app.tabs.tabs["memories"]
                )
                path, _ = memories_tab.treeview.get_cursor()
                if path:
                    row = path.get_indices()[0]
                    if 0 <= row < len(memories_tab.lightshow.cues):
                        selected_cue = memories_tab.lightshow.cues[row]
                        if (
                            selected_cue.sequence == sequence
                            and selected_cue.number == number
                        ):
                            memories_tab.channels_view.update()
        return False

    def _safe_refresh_group_editor(self, index: float) -> bool:
        """Refresh the channel view in groups tab when temporary overrides change.

        Returns:
            Always False.
        """
        if self.app.tabs:
            if self.app.tabs.tabs.get("groups") is not None:
                group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
                if getattr(group_tab, "selected_group_number", None) == index:
                    group_tab.channels_view.update()
        return False

    def _update_live_view_active_cue(self, sequence: int, number: float) -> None:
        """Update live view channels if the modified cue is active in playback."""
        if not (self.app.window and self.app.window.live_view):
            return
        playback = self.app.core.lightshow.main_playback
        if not (playback.steps and playback.position + 1 < len(playback.steps)):
            return
        active_cue = playback.steps[playback.position + 1].cue
        if not (
            active_cue
            and active_cue.sequence == sequence
            and active_cue.number == number
        ):
            return

        for channel in range(1, MAX_CHANNELS + 1):
            widget = self.app.window.live_view.channels_view.get_channel_widget(channel)
            if widget:
                widget.next_level = active_cue.get_level(channel)
                widget.queue_draw()

    def _safe_refresh_patch(self) -> bool:
        """Refresh patch UI tabs and live channels view safely in the GTK thread.

        Returns:
            Always False.
        """
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.channels_view.update()
        if self.app.tabs:
            if self.app.tabs.tabs.get("patch_outputs") is not None:
                patch_outputs = typing.cast(
                    "PatchOutputsTab", self.app.tabs.tabs["patch_outputs"]
                )
                patch_outputs.refresh()
            if self.app.tabs.tabs.get("patch_channels") is not None:
                patch_channels = typing.cast(
                    "PatchChannelsTab", self.app.tabs.tabs["patch_channels"]
                )
                patch_channels.refresh()
        return False

    def _on_selected_outputs_changed(self) -> bool:
        """Refresh selected outputs UI and reset command line in the GTK thread.

        Returns:
            Always False.
        """
        if self.app.tabs:
            if self.app.tabs.tabs.get("patch_outputs") is not None:
                patch_outputs = typing.cast(
                    "PatchOutputsTab", self.app.tabs.tabs["patch_outputs"]
                )
                patch_outputs.select_outputs()
        self.app.core.commandline.set_string("")
        return False

    def _safe_refresh_curves(self, curve_nb: int) -> bool:
        """Refresh curves tab UI safely in the GTK thread.

        Args:
            curve_nb: The active curve number.

        Returns:
            Always False.
        """
        if not self.app.tabs:
            return False
        curves_tab_obj = self.app.tabs.tabs.get("curves")
        if curves_tab_obj is None:
            return False

        curves_tab = typing.cast("CurvesTab", curves_tab_obj)
        is_active_curve = curves_tab.curve_edition.curve_nb == curve_nb
        curves_count = len(curves_tab.lightshow.curves.curves)
        flowbox_count = 0
        if curves_tab.flowbox is not None:
            flowbox_count = len(
                [
                    c
                    for c in curves_tab.flowbox.get_children()
                    if isinstance(c, Gtk.FlowBoxChild)
                ]
            )

        if is_active_curve and curves_count == flowbox_count:
            self._fast_refresh_active_curve(curves_tab, curve_nb)
        else:
            self._slow_refresh_curves(curves_tab, curve_nb)
        return False

    def _fast_refresh_active_curve(
        self, curves_tab: "CurvesTab", curve_nb: int
    ) -> None:
        """Perform a fast local UI update on the currently active curve."""
        curve = curves_tab.lightshow.curves.get_curve(curve_nb)
        if curve is None:
            return

        # Update title
        text = curve.name
        if isinstance(curve, LimitCurve):
            text += f" {round((curve.limit / 255) * 100)}%"
        curves_tab.curve_edition.header.set_title(text)

        # Update scale slider value (safely using updating flag to avoid loops)
        if (
            isinstance(curve, LimitCurve)
            and curves_tab.curve_edition.scale_widget is not None
        ):
            curves_tab.curve_edition.updating_slider = True
            try:
                curves_tab.curve_edition.scale_widget.set_value(curve.limit)
            finally:
                curves_tab.curve_edition.updating_slider = False

        # Update points if it's a PointsCurve
        if isinstance(curve, PointsCurve):
            curves_tab.curve_edition.points_curve()

        # Redraw Cairo widgets
        curves_tab.curve_edition.values.queue_draw()
        if curves_tab.curve_edition.edit_curve is not None:
            curves_tab.curve_edition.edit_curve.queue_draw()

        # Redraw the button preview in the curves list
        if curves_tab.flowbox is not None:
            for child in curves_tab.flowbox.get_children():
                if not isinstance(child, Gtk.FlowBoxChild):
                    continue
                child_btn = child.get_child()
                if child_btn and getattr(child_btn, "curve_nb", None) == curve_nb:
                    child_btn.queue_draw()
                    break

    def _slow_refresh_curves(self, curves_tab: "CurvesTab", curve_nb: int) -> None:
        """Perform a full rebuild of the curves tab UI."""
        curves_tab.refresh()
        curves_tab.curve_edition.change_curve(curve_nb)
        if curves_tab.flowbox is not None:
            for child in curves_tab.flowbox.get_children():
                if not isinstance(child, Gtk.FlowBoxChild):
                    continue
                child_btn = child.get_child()
                if child_btn and getattr(child_btn, "curve_nb", None) == curve_nb:
                    curves_tab.flowbox.select_child(child)
                    break

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
        cue_mem = feedback.get("cue_number", 0.0)
        cue_txt = feedback.get("cue_text", "")
        next_mem = feedback.get("next_cue_number", 0.0)
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

    def _on_channels_selected_changed(self, selected_channels: list[int]) -> bool:
        """Synchronize the logical channel selection to the GUI's FlowBox."""
        if self.app.window and self.app.window.live_view:
            channels_view = self.app.window.live_view.channels_view
            channels_view.sync_selection_to_gui(selected_channels)

            # Update Track Channels if opened
            if self.app.tabs and self.app.tabs.tabs.get("track_channels") is not None:
                track_channels = typing.cast(
                    "TrackChannelsTab", self.app.tabs.tabs["track_channels"]
                )
                track_channels.update_display()
        return False

    def _on_group_selected_changed(self, group_nb: float | None) -> bool:
        """Synchronize the logical group selection to the GUI."""
        if self.app.tabs and self.app.tabs.tabs.get("groups") is not None:
            group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
            group_tab.select_group_graphically(group_nb)
        return False

    def _on_cue_selected_changed(self, cue_id: tuple[float, int] | None) -> bool:
        """Synchronize the logical cue selection to the GUI."""
        if self.app.tabs and self.app.tabs.tabs.get("memories") is not None:
            memories_tab = typing.cast("CuesEditionTab", self.app.tabs.tabs["memories"])
            memories_tab.select_cue_graphically(cue_id)
        return False

    def _on_fader_page_changed(self, _page: int) -> bool:
        """Synchronize fader page changes to the GUI and MIDI controller."""
        if self.app.virtual_console:
            self.app.virtual_console.update_page_display()
        else:
            if self.app.midi is not None:
                self.app.midi.update_faders()
        return False

    def _on_fader_level_changed(self, fader_index: int, level: float) -> bool:
        """Synchronize fader level to GUI or MIDI controller."""
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
        """Queue a redraw on the virtual console flash button."""
        if self.app.virtual_console:
            self.app.virtual_console.flashes[fader_index - 1].queue_draw()
        return False

    def _on_fader_assignment_changed(self, _page: int, _index: int) -> bool:
        """Refresh the FaderTab when a fader assignment changes
        (assign/clear/undo/redo).

        Args:
            _page: Fader page number (unused, full refresh is simpler).
            _index: Fader index within the page (unused).

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        if self.app.tabs and self.app.tabs.tabs.get("faders") is not None:
            fader_tab = typing.cast(FaderTab, self.app.tabs.tabs["faders"])
            fader_tab.refresh()
        return False

    def _on_independent_level_changed(self, number: int, level: float) -> bool:
        """Synchronize independent level changes to GUI and MIDI."""
        if self.app.virtual_console:
            self.app.virtual_console.update_independent_display(number, level)
        if self.app.midi is not None:
            if number <= 6:
                midi_fader = self.app.midi.faders.inde_faders[number - 1]
                midi_fader.set_state(round(level * 255))
                self.app.midi.messages.control_change.send(
                    f"inde_led_{number}", 32 + int(level * 12)
                )
            else:
                velocity = 0 if level < 0.5 else 127
                self.app.midi.messages.notes.send(f"inde_{number}", velocity)
        return False

    def _on_independent_channels_changed(self, _number: int) -> bool:
        """Refresh independent edit tab on channels configuration changes."""
        if self.app.tabs and self.app.tabs.tabs.get("indes") is not None:
            indes_tab = typing.cast(typing.Any, self.app.tabs.tabs["indes"])
            indes_tab.channels_view.flowbox.queue_draw()
            indes_tab.channels_view.update()
        return False

    def _on_independent_text_changed(self, _number: int, _text: str) -> bool:
        """Refresh independent edit tab treeview on label changes."""
        if self.app.tabs and self.app.tabs.tabs.get("indes") is not None:
            indes_tab = typing.cast(typing.Any, self.app.tabs.tabs["indes"])
            indes_tab.refresh()
        return False

    def _on_independent_type_changed(
        self, _number: int, _inde_type: IndependentType
    ) -> bool:
        """Refresh independent edit tab treeview and Virtual Console on type changes."""
        if self.app.tabs and self.app.tabs.tabs.get("indes") is not None:
            indes_tab = typing.cast(typing.Any, self.app.tabs.tabs["indes"])
            indes_tab.refresh()
        if self.app.virtual_console:
            self.app.virtual_console.rebuild_independent(_number)
        return False

    def _on_button_pressed(self, name: str, pressed: bool) -> bool:
        """Handle visual button pressed/released state feedback on Virtual Console."""
        vc = self.app.virtual_console
        if vc and hasattr(vc, name):
            widget = getattr(vc, name)
            if hasattr(widget, "pressed"):
                widget.pressed = pressed
                widget.queue_draw()
        return False

    def _on_zoom_changed(self, level: float) -> bool:
        """Handle zoom change event in the active tab/view."""
        if not self.app.window:
            return False
        tab = self.app.window.get_active_tab()
        if not tab:
            return False

        view = None
        if isinstance(tab, (ChannelsView, PatchOutputsTab)):
            view = tab
        else:
            for child in tab.get_children():
                if isinstance(child, ChannelsView):
                    view = child

        if view:
            for flowboxchild in view.flowbox.get_children():
                flowbox_child = typing.cast(Gtk.FlowBoxChild, flowboxchild)
                child_widget = flowbox_child.get_child()
                if child_widget and isinstance(child_widget, ChannelWidget):
                    child_widget.scale = level
                    flowboxchild.queue_draw()
        return False

    def _on_active_tab_changed(self, tab_name: str) -> bool:
        """Handle active tab change event by switching active tab page."""
        if tab_name in ("channels", "playback"):
            if self.app.window:
                self.app.window.playback.set_current_page(0)
                self.app.window.playback.grab_focus()
            return False

        mapping = {
            "patch_outputs": lambda: self.app.patch_outputs(None, None),
            "patch_channels": lambda: self.app.patch_channels(None, None),
            "track_channels": lambda: self.app.track_channels(None, None),
            "memories": lambda: self.app.memories_cb(None, None),
            "sequences": lambda: self.app.sequences(None, None),
            "groups": lambda: self.app.groups_cb(None, None),
            "indes": lambda: self.app.independents(None, None),
            "curves": lambda: self.app.curves(None, None),
            "faders": lambda: self.app.faders(None, None),
            "settings": lambda: self.app.settings_cb(None, None),
        }

        if tab_name in mapping:
            mapping[tab_name]()
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
