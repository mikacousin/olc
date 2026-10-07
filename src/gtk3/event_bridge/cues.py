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
"""GUI event bridge handler for cues and memories."""

from __future__ import annotations

import typing

from olc.define import MAX_CHANNELS

from .base import BaseEventBridgeHandler

if typing.TYPE_CHECKING:
    from olc.gtk3.cue import CuesEditionTab
    from olc.gtk3.sequence import SequenceTab
    from olc.gtk3.track_channels import TrackChannelsTab


# pylint: disable=too-few-public-methods
class CueBridgeHandler(BaseEventBridgeHandler):
    """Handles cue and memory event synchronization to the GUI."""

    def register(self) -> None:
        """Subscribe to Core events for cues and cue editor."""
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
            "cue.selected_changed",
            lambda cue_id: self._run_idle(self._on_cue_selected_changed, cue_id),
        )
        self.app.core.subscribe(
            "playback.cue_recorded",
            lambda seq_idx, step_idx, cue_nb: self._run_idle(
                self._on_cue_recorded, seq_idx, step_idx, cue_nb
            ),
        )

    def _on_cue_recorded(self, seq_idx: float, step: int, _cue_nb: float) -> bool:
        """Handle cue recorded in playback sequence.

        Args:
            seq_idx: Sequence identifier.
            step: Step index.
            _cue_nb: Cue number.

        Returns:
            Always False.
        """
        if seq_idx == 1.0 and self.app.window:
            if self.app.window.playback:
                self.app.window.playback.update_xfade_display(step)
            self.app.window.update_channels_display(step)
        return False

    def _safe_refresh_cues(self, sequence: int, number: float) -> bool:
        """Refresh the cues (memories) tab and playback UI safely in the GTK thread.

        Args:
            sequence: Sequence number.
            number: Cue number.

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

    def _safe_refresh_cue_editor(self, sequence: int, number: float) -> bool:
        """Refresh the channel view in memories tab when temporary overrides change.

        Args:
            sequence: Sequence number.
            number: Cue number.

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

    def _update_live_view_active_cue(self, sequence: int, number: float) -> None:
        """Update live view channels if the modified cue is active in playback.

        Args:
            sequence: Sequence number.
            number: Cue number.
        """
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

    def _on_cue_selected_changed(self, cue_id: tuple[float, int] | None) -> bool:
        """Synchronize the logical cue selection to the GUI.

        Args:
            cue_id: (cue_number, sequence_number) tuple or None.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("memories") is not None:
            memories_tab = typing.cast("CuesEditionTab", self.app.tabs.tabs["memories"])
            memories_tab.select_cue_graphically(cue_id)
        return False
