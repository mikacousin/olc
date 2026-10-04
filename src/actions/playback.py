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
from olc.cue import Cue
from olc.define import UNIVERSES
from olc.sequence import get_cue
from olc.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


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


class PlaybackStepNavigateAction(Action):
    """Base class for sequence step navigation actions (SEQ+, SEQ-)."""

    can_undo = False
    label: str = ""
    event_name: str = ""
    direction: int = 1

    def execute(self) -> None:
        """Execute the sequence step navigation."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback:
            return

        if self.direction > 0:
            main_playback.sequence_plus()
        else:
            main_playback.sequence_minus()

        if self.event_name:
            self.app.emit(self.event_name, self.get_feedback_state())

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
            "label": self.label,
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


class SequencePlusAction(PlaybackStepNavigateAction):
    """Action to select the next sequence step in the playback.

    Jumps directly to the next cue.
    """

    name = "playback.sequence_plus"
    label = "SEQ+"
    event_name = "playback.sequence_plus_triggered"
    direction = 1


class SequenceMinusAction(PlaybackStepNavigateAction):
    """Action to select the previous sequence step in the playback.

    Jumps directly to the previous cue.
    """

    name = "playback.sequence_minus"
    label = "SEQ-"
    event_name = "playback.sequence_minus_triggered"
    direction = -1


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


class PlaybackGotoAction(Action):
    """Action to go directly to a specific cue or step in the main playback."""

    name = "playback.goto"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.target: str = ""

    def configure(self, target: float | str | int) -> None:
        """Configure the target cue.

        Args:
            target: Cue number (string or number).
        """
        self.target = str(target)

    def execute(self) -> None:
        """Execute the goto transition."""
        main_playback = self.app.lightshow.main_playback
        if not main_playback or not self.target:
            return

        main_playback.goto(self.target)
        self.app.emit("playback.goto_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state for the GOTO action."""
        return {
            "active": False,
            "label": "GOTO",
            "target": self.target,
        }


class PlaybackManualXFadeAction(Action):
    """Action to manually adjust the crossfade sliders A or B."""

    name = "playback.manual_xfade"
    can_undo = False  # Real-time manual fader operation

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.fader: str = "a"
        self.value: int = 0

    def configure(self, fader: str = "a", value: int = 0) -> None:
        """Configure the fader and level value.

        Args:
            fader: 'a' (or 'out') for crossfade_out, 'b' (or 'in') for crossfade_in.
            value: Level value (0-255).
        """
        self.fader = fader
        self.value = value

    def execute(self) -> None:
        """Execute the manual crossfade movement."""
        crossfade = getattr(self.app, "crossfade", None)
        if crossfade is None:
            return

        crossfade.manual = True
        val = min(max(int(self.value), 0), 255)
        fader_key = (
            "a" if str(self.fader).lower() in ("a", "crossfade_out", "out") else "b"
        )
        scale = crossfade.scale_a if fader_key == "a" else crossfade.scale_b
        scale.set_value(val)
        crossfade.scale_moved(scale)

        vc = getattr(self.app, "virtual_console", None)
        if vc is not None:
            vc_scale = vc.scale_a if fader_key == "a" else vc.scale_b
            if hasattr(vc_scale, "set_value"):
                vc_scale.set_value(val)

        self.app.emit("playback.xfade_moved", fader_key, val)


def capture_live_channels(app: CoreApplication) -> dict[int, int]:
    """Capture current stage DMX levels mapped to show channels."""
    channels: dict[int, int] = {}
    patch = app.lightshow.patch
    independents = getattr(app.lightshow, "independents", None)
    inde_channels = independents.channels if independents is not None else set()

    backend = getattr(app, "backend", None)
    backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

    for channel, outputs in patch.channels.items():
        if not patch.is_patched(channel):
            continue
        if channel in inde_channels:
            continue
        for values in outputs:
            output = values[0]
            univ = values[1]
            if output is None or univ is None:
                continue
            level = 0
            if backend_dmx is not None and univ in UNIVERSES:
                idx = UNIVERSES.index(univ)
                if idx < len(backend_dmx.frame):
                    dimmer_idx = output - 1
                    if 0 <= dimmer_idx < len(backend_dmx.frame[idx]):
                        level = int(backend_dmx.frame[idx][dimmer_idx])
            elif app.engine is not None:
                try:
                    level = int(app.engine.universe(univ).array[output - 1])
                except (KeyError, IndexError, AttributeError):
                    pass
            channels[channel] = max(channels.get(channel, 0), level)
    return channels


class PlaybackRecordCueAction(Action):
    """Action to capture live stage output and record a new Cue and step."""

    name = "playback.record_cue"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float | None = None
        self.step: int | None = None
        self.sequence: int = 1
        self.created_cue: Cue | None = None
        self.created_step: Step | None = None
        self.old_position: int = 0

    def configure(
        self,
        number: float | None = None,
        step: int | None = None,
        sequence: int = 1,
    ) -> None:
        """Configure parameters for recording cue.

        Args:
            number: Target cue number, or None to auto-compute next available number.
            step: Insertion step index in sequence, or None for position + 1.
            sequence: Sequence identifier (default 1 for main playback).
        """
        self.number = float(number) if number is not None else None
        self.step = int(step) if step is not None else None
        self.sequence = sequence

    def execute(self) -> None:
        """Execute recording of the live stage into a cue and step."""
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_chaser(self.sequence)
        )
        if main_playback is None:
            return

        self.old_position = main_playback.position

        # Determine target step and cue number
        if self.number is None:
            next_cue = main_playback.get_next_cue(step=self.old_position)
            self.number = next_cue if next_cue is not None else 1.0
            if self.step is None:
                self.step = self.old_position + 1
        elif self.step is None:
            _found, step_idx = main_playback.get_step(cue=self.number)
            self.step = step_idx

        # Capture live stage channels (non-zero levels for new cue)
        live_channels = capture_live_channels(self.app)
        channels = {ch: lvl for ch, lvl in live_channels.items() if lvl > 0}

        cue = Cue(self.sequence, self.number, channels)
        self.created_cue = cue
        lightshow.cues.insert(self.step - 1, cue)

        step_object = Step(self.sequence, cue=cue)
        self.created_step = step_object
        main_playback.insert_step(self.step, step_object)
        main_playback.position = self.step

        main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.created", self.sequence, self.number)
        self.app.emit("step.inserted", float(self.sequence), self.step)
        self.app.emit(
            "playback.cue_recorded",
            float(self.sequence),
            self.step,
            self.number,
        )

    def undo(self) -> None:
        """Undo cue recording, removing step and cue and restoring position."""
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_chaser(self.sequence)
        )
        if main_playback is None or self.number is None or self.step is None:
            return

        if self.created_step and self.created_step in main_playback.steps:
            main_playback.steps.remove(self.created_step)
            main_playback.last = len(main_playback.steps)

        if self.created_cue:
            lightshow.cues.remove(self.created_cue)

        main_playback.position = self.old_position
        main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.deleted", self.sequence, self.number)
        self.app.emit("step.deleted", float(self.sequence), self.step)
        self.app.emit(
            "playback.cue_recorded",
            float(self.sequence),
            self.old_position,
            0.0,
        )

    def redo(self) -> None:
        """Redo cue recording."""
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_chaser(self.sequence)
        )
        if (
            main_playback is None
            or self.created_cue is None
            or self.created_step is None
            or self.step is None
            or self.number is None
        ):
            return

        lightshow.cues.insert(self.step - 1, self.created_cue)
        main_playback.insert_step(self.step, self.created_step)
        main_playback.position = self.step
        main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.created", self.sequence, self.number)
        self.app.emit("step.inserted", float(self.sequence), self.step)
        self.app.emit(
            "playback.cue_recorded",
            float(self.sequence),
            self.step,
            self.number,
        )


class PlaybackUpdateActiveStepAction(Action):
    """Action to capture live stage output and update an existing cue."""

    name = "playback.update_active_step"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float | None = None
        self.sequence: int = 1
        self.target_cue: Cue | None = None
        self.old_channels: dict[int, int] = {}
        self.new_channels: dict[int, int] = {}

    def configure(
        self,
        number: float | None = None,
        sequence: int = 1,
    ) -> None:
        """Configure parameters for updating cue.

        Args:
            number: Target cue number, or None to use active playback step's cue.
            sequence: Sequence identifier (default 1 for main playback).
        """
        self.number = float(number) if number is not None else None
        self.sequence = sequence

    def execute(self) -> None:
        """Execute updating the target cue with live stage levels."""
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_chaser(self.sequence)
        )
        if main_playback is None:
            return

        target_cue: Cue | None = None
        if self.number is not None:
            target_cue = lightshow.cues.get(self.number, self.sequence)
        elif 0 <= main_playback.position < len(main_playback.steps):
            target_cue = main_playback.steps[main_playback.position].cue

        if target_cue is None:
            return

        self.target_cue = target_cue
        self.old_channels = dict(target_cue.channels)

        live_channels = capture_live_channels(self.app)
        updated_channels = dict(target_cue.channels)
        updated_channels.update(live_channels)
        self.new_channels = updated_channels

        target_cue.channels = self.new_channels
        main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.updated", target_cue.sequence, target_cue.number)

    def undo(self) -> None:
        """Undo cue update, restoring previous channel levels."""
        if self.target_cue is None:
            return

        self.target_cue.channels = dict(self.old_channels)
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_chaser(self.sequence)
        )
        if main_playback:
            main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.updated", self.target_cue.sequence, self.target_cue.number)

    def redo(self) -> None:
        """Redo cue update, re-applying captured channel levels."""
        if self.target_cue is None:
            return

        self.target_cue.channels = dict(self.new_channels)
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_chaser(self.sequence)
        )
        if main_playback:
            main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.updated", self.target_cue.sequence, self.target_cue.number)
