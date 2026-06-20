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
from olc.sequence import get_cue


class GoAction(Action):
    """Action to trigger the GO command on the active sequence."""

    name = "playback.go"
    can_undo = False  # Playback transitions are transient real-time events

    def execute(self) -> None:
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

    def execute(self) -> None:
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


class SequencePlusAction(Action):
    """Action to select the next sequence step in the playback.

    Jumps directly to the next cue.
    """

    name = "playback.sequence_plus"
    can_undo = False

    def execute(self) -> None:
        """Execute the action, switching to the next step directly."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return

        main_playback.sequence_plus()

        # Notify event with feedback
        self.app.emit("playback.sequence_plus_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the sequence step selection."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return {}

        pos = main_playback.position
        step = main_playback.steps[pos] if pos < len(main_playback.steps) else None
        next_step = (
            main_playback.steps[pos + 1] if pos + 1 < len(main_playback.steps) else None
        )

        return {
            "active": False,
            "timer": 0.1,
            "label": "SEQ+",
            "position": pos,
            "last": main_playback.last,
            "next_total_time": next_step.total_time if next_step else 0.0,
            "next_time_in": next_step.time_in if next_step else 0.0,
            "next_time_out": next_step.time_out if next_step else 0.0,
            "next_delay_in": next_step.delay_in if next_step else 0.0,
            "next_delay_out": next_step.delay_out if next_step else 0.0,
            "next_wait": next_step.wait if next_step else 0.0,
            "next_channel_time": next_step.channel_time if next_step else False,
            "cue_number": get_cue(step).number if (step and get_cue(step)) else 0.0,
            "cue_text": step.text if step else "",
            "next_cue_number": (
                get_cue(next_step).number if (next_step and get_cue(next_step)) else 0.0
            ),
            "next_cue_text": next_step.text if next_step else "",
        }


class SequenceMinusAction(Action):
    """Action to select the previous sequence step in the playback.

    Jumps directly to the previous cue.
    """

    name = "playback.sequence_minus"
    can_undo = False

    def execute(self) -> None:
        """Execute the action, switching to the previous step directly."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return

        main_playback.sequence_minus()

        # Notify event with feedback
        self.app.emit("playback.sequence_minus_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the sequence step selection."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return {}

        pos = main_playback.position
        step = main_playback.steps[pos] if pos < len(main_playback.steps) else None
        next_step = (
            main_playback.steps[pos + 1] if pos + 1 < len(main_playback.steps) else None
        )

        return {
            "active": False,
            "timer": 0.1,
            "label": "SEQ-",
            "position": pos,
            "last": main_playback.last,
            "next_total_time": next_step.total_time if next_step else 0.0,
            "next_time_in": next_step.time_in if next_step else 0.0,
            "next_time_out": next_step.time_out if next_step else 0.0,
            "next_delay_in": next_step.delay_in if next_step else 0.0,
            "next_delay_out": next_step.delay_out if next_step else 0.0,
            "next_wait": next_step.wait if next_step else 0.0,
            "next_channel_time": next_step.channel_time if next_step else False,
            "cue_number": get_cue(step).number if (step and get_cue(step)) else 0.0,
            "cue_text": step.text if step else "",
            "next_cue_number": (
                get_cue(next_step).number if (next_step and get_cue(next_step)) else 0.0
            ),
            "next_cue_text": next_step.text if next_step else "",
        }


class GoBackAction(Action):
    """Action to trigger the GO BACK command on the active sequence."""

    name = "playback.go_back"
    can_undo = False

    def execute(self) -> None:
        """Execute the action, running the previous cue transition."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return

        main_playback.go_back(None, None)

        self.app.emit("playback.go_back_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the GO BACK transition."""
        main_playback = self.app.lightshow.main_playback
        on_go = bool(main_playback.on_go) if main_playback else False
        return {
            "active": on_go,
            "label": "GOBACK",
        }
