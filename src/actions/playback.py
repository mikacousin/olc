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


class GoAction(Action):
    """Action to trigger the GO command on the active sequence."""

    name = "playback.go"
    can_undo = False  # Playback transitions are transient real-time events

    def execute(self) -> None:  # ty: ignore[invalid-method-override]
        """Execute the action, running the next cue in the active sequence."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return

        # Trigger sequence transition
        main_playback.do_go(None)

        # Notify event
        self.app.emit("playback.go_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the GO transition."""
        main_playback = self.app.lightshow.main_playback
        on_go = bool(main_playback.on_go) if main_playback else False
        return {
            "active": on_go,
            "label": "GO",
        }


class PauseAction(Action):
    """Action to toggle the PAUSE command on the active sequence."""

    name = "playback.pause"
    can_undo = False  # Playback transitions are transient real-time events

    def execute(self) -> None:  # ty: ignore[invalid-method-override]
        """Execute the action, toggling the pause state of the crossfade."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return

        # Toggle pause state
        main_playback.pause(None, None)

        # Notify event
        self.app.emit("playback.pause_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the PAUSE state."""
        main_playback = self.app.lightshow.main_playback
        is_paused = False
        if main_playback and main_playback.on_go and main_playback.thread:
            is_paused = not main_playback.thread.pause.is_set()
        return {
            "active": is_paused,
            "label": "PAUSE",
        }
