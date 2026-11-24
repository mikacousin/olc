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
"""GUI event bridge handler for cues."""

from __future__ import annotations

import typing

from olc.define import MAX_CHANNELS
from olc.gtk3.widgets.channels_view import VIEW_MODES

from .base import BaseEventBridgeHandler

if typing.TYPE_CHECKING:
    from olc.gtk3.sequence import SequenceTab
    from olc.gtk3.track_channels import TrackChannelsTab


# pylint: disable=too-few-public-methods
class CueBridgeHandler(BaseEventBridgeHandler):
    """Handles cue event synchronization to the GUI."""

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
        """Refresh the cues tab and playback UI safely in the GTK thread.

        Args:
            sequence: Sequence number.
            number: Cue number.

        Returns:
            Always False.
        """
        if self.app.tabs:
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
        if self.app.window and self.app.window.live_view:
            live_cv = self.app.window.live_view.channels_view
            if live_cv.view_mode == VIEW_MODES["Manual"]:
                live_cv.refresh_filter()
        return False

    def _safe_refresh_cue_editor(self, _sequence: int, _number: float) -> bool:
        """Refresh the sequence channels view when temporary overrides change.

        Args:
            _sequence: Sequence number.
            _number: Cue number.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("sequences") is not None:
            sequences_tab = typing.cast("SequenceTab", self.app.tabs.tabs["sequences"])
            sequences_tab.channels_view.update()
        return False

    def _update_live_view_active_cue(self, sequence: int, number: float) -> None:
        """Update live view channels if the modified cue is active in playback.

        Args:
            sequence: Sequence number.
            number: Cue number.
        """
        if not (self.app.window and self.app.window.live_view):
            return
        engine = getattr(self.app.core, "playback_engine", None)
        playback = (
            engine.main_sequence
            if engine is not None and engine.main_sequence is not None
            else self.app.core.lightshow.main_playback
        )
        if not (playback.steps and playback.position + 1 < len(playback.steps)):
            return
        active_cue = playback.steps[playback.position + 1].cue
        if not (
            active_cue
            and active_cue.sequence == sequence
            and active_cue.number == number
        ):
            return

        channels_view = self.app.window.live_view.channels_view
        for channel in range(1, MAX_CHANNELS + 1):
            widget = channels_view.get_channel_widget(channel)
            if widget:
                widget.next_level = active_cue.get_level(channel)
        channels_view.mark_channels_dirty(None, invalidate_step=True)
