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

import copy
import typing

from olc.core.action import Action
from olc.define import MAX_CHANNELS
from olc.dmx import Dmx
from olc.show.cue import Cue
from olc.show.sequence import get_cue
from olc.show.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.sequence import Sequence


def _get_main_sequence(app: CoreApplication) -> Sequence | None:
    """Resolve the currently configured Main Sequence."""
    engine = getattr(app, "playback_engine", None)
    if engine is not None:
        return engine.main_sequence
    return getattr(getattr(app, "lightshow", None), "main_playback", None)


class GoAction(Action):
    """Action to trigger the GO command on the active sequence."""

    name = "playback.go"
    can_undo = False  # Playback transitions are transient real-time events

    def execute(self) -> None:
        """Execute the action, running the next cue in the active sequence."""
        main_playback = _get_main_sequence(self.app)
        if not main_playback:
            return

        # Trigger sequence transition
        main_playback.do_go(None)

        # Notify event
        self.app.emit("playback.go_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the GO transition."""
        main_playback = _get_main_sequence(self.app)
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
        main_playback = _get_main_sequence(self.app)
        if not main_playback:
            return

        # Toggle pause state
        main_playback.pause(None, None)

        # Notify event
        self.app.emit("playback.pause_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the PAUSE state."""
        main_playback = _get_main_sequence(self.app)
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
        main_playback = _get_main_sequence(self.app)
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
        main_playback = _get_main_sequence(self.app)
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
        main_playback = _get_main_sequence(self.app)
        if not main_playback:
            return

        main_playback.go_back(None, None)

        self.app.emit("playback.go_back_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the GO BACK transition."""
        main_playback = _get_main_sequence(self.app)
        on_go = bool(main_playback.on_go) if main_playback else False
        return {
            "active": on_go,
            "label": "GOBACK",
        }


class PlaybackSetMainSequenceAction(Action):
    """Reversibly choose which Sequence acts as the Main Playback (CrossFade/Header)."""

    name = "playback.set_main_sequence"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.sequence_index: float = 1.0
        self._old_index: float = 1.0

    def configure(self, sequence_index: float) -> None:
        """Configure target sequence index to promote as Main Sequence."""
        self.sequence_index = float(sequence_index)

    def execute(self) -> bool:
        """Set the Main Sequence in PlaybackEngine."""
        engine = getattr(self.app, "playback_engine", None)
        if engine is None:
            self.can_undo = False
            return False
        self._old_index = engine.main_sequence_index
        ok = engine.set_main_sequence(self.sequence_index)
        if not ok or self._old_index == self.sequence_index:
            self.can_undo = False
        return ok

    def undo(self) -> None:
        """Restore previous Main Sequence."""
        engine = getattr(self.app, "playback_engine", None)
        if engine is not None:
            engine.set_main_sequence(self._old_index)

    def redo(self) -> None:
        """Reapply selected Main Sequence."""
        engine = getattr(self.app, "playback_engine", None)
        if engine is not None:
            engine.set_main_sequence(self.sequence_index)

    def get_history_details(self) -> str:
        """Return sequence index for Undo History."""
        idx = (
            int(self.sequence_index)
            if self.sequence_index.is_integer()
            else self.sequence_index
        )
        return f"Main Seq {idx}"


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
        self.override_time: float | None = None

    def configure(
        self,
        target: float | str | int,
        override_time: float | None = None,
    ) -> None:
        """Configure the target cue.

        Args:
            target: Cue number (string or number).
            override_time: Optional override fade time in seconds.
        """
        self.target = str(target)
        self.override_time = float(override_time) if override_time is not None else None

    def execute(self) -> None:
        """Execute the goto transition."""
        main_playback = _get_main_sequence(self.app)
        if not main_playback or not self.target:
            return

        if self.override_time is not None:
            main_playback.goto(self.target, override_time=self.override_time)
        else:
            main_playback.goto(self.target)
        self.app.emit("playback.goto_triggered", self.get_feedback_state())

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state for the GOTO action."""
        state = {
            "active": False,
            "label": "GOTO",
            "target": self.target,
        }
        if self.override_time is not None:
            state["override_time"] = self.override_time
        return state


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
        raw_val = float(self.value)
        norm_val = max(0.0, min(1.0, raw_val / 255.0 if raw_val > 1.0 else raw_val))
        val_255 = round(norm_val * 255.0)
        fader_key = (
            "a" if str(self.fader).lower() in ("a", "crossfade_out", "out") else "b"
        )
        scale = crossfade.scale_a if fader_key == "a" else crossfade.scale_b
        scale.set_value(norm_val)
        crossfade.scale_moved(scale)

        vc = getattr(self.app, "virtual_console", None)
        if vc is not None:
            if hasattr(vc, "update_crossfade_display"):
                vc.update_crossfade_display(
                    val_a=val_255 if fader_key == "a" else None,
                    val_b=val_255 if fader_key == "b" else None,
                )
            else:
                vc_scale = vc.scale_a if fader_key == "a" else vc.scale_b
                if hasattr(vc_scale, "set_value"):
                    vc_scale.set_value(val_255)

        self.app.emit("playback.xfade_moved", fader_key, val_255)


def _is_device_channel_modified(dev: typing.Any, ch_type_val: str) -> bool:  # noqa: ANN401
    """Check if any resolution channel of ch_type_val differs from default_value."""
    for ch in getattr(dev, "channels", []):
        ctype = getattr(ch, "channel_type", None)
        if getattr(ctype, "value", ctype) == ch_type_val:
            if getattr(ch, "value", 0) != getattr(ch, "default_value", 0):
                return True
    return False


def _extract_device_active_values(  # pylint: disable=too-many-branches
    dev: typing.Any,  # noqa: ANN401
) -> dict[str, typing.Any]:
    """Extract active physical parameters from a LightingDevice instance."""
    vals: dict[str, typing.Any] = {}
    if hasattr(dev, "channels"):
        if _is_device_channel_modified(dev, "pan"):
            vals["pan"] = dev.pan_degrees
        if _is_device_channel_modified(dev, "tilt"):
            vals["tilt"] = dev.tilt_degrees
        if _is_device_channel_modified(dev, "zoom") and dev.zoom_degrees is not None:
            vals["zoom"] = dev.zoom_degrees
        if _is_device_channel_modified(dev, "focus") and dev.focus_meters is not None:
            vals["focus"] = dev.focus_meters
        if _is_device_channel_modified(dev, "strobe") and dev.strobe_hz is not None:
            vals["strobe"] = dev.strobe_hz
        if (
            _is_device_channel_modified(dev, "color_temp")
            and dev.color_temp_kelvin is not None
        ):
            vals["cct"] = dev.color_temp_kelvin
        if (
            _is_device_channel_modified(dev, "iris")
            and getattr(dev, "iris", None) is not None
        ):
            vals["iris"] = dev.iris
        if getattr(dev, "gobo", None) is not None:
            vals["gobo"] = dev.gobo
        base_emitters = getattr(dev, "_base_emitters", {})
        if any(v > 0.0 for v in base_emitters.values()):
            vals["color"] = dev.color_srgb.to_hex()
    else:
        if hasattr(dev, "pan_degrees") and getattr(dev, "pan_degrees", 0.0) != 0.0:
            vals["pan"] = dev.pan_degrees
        if hasattr(dev, "tilt_degrees") and getattr(dev, "tilt_degrees", 0.0) != 0.0:
            vals["tilt"] = dev.tilt_degrees
        if hasattr(dev, "zoom_degrees") and dev.zoom_degrees is not None:
            vals["zoom"] = dev.zoom_degrees
        if hasattr(dev, "color_srgb") and hasattr(dev.color_srgb, "to_hex"):
            vals["color"] = dev.color_srgb.to_hex()
    return vals


def capture_live_channels(  # pylint: disable=too-many-locals, too-many-branches
    app: CoreApplication,
) -> dict[int, float]:
    """Capture current stage normalized levels mapped to show channels."""
    channels: dict[int, float] = {}
    patch = app.lightshow.patch
    independents = getattr(app.lightshow, "independents", None)
    inde_channels = independents.channels if independents is not None else set()

    backend = getattr(app, "backend", None)
    backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

    for channel, dev in getattr(patch, "devices", {}).items():
        if not dev.channels or channel in inde_channels:
            continue
        for ch in dev.channels:
            if ch.channel_type.value != "intensity" or ch.fine or ch.ultra_fine:
                continue
            output = ch.address
            univ = ch.universe
            level = 0
            if isinstance(backend_dmx, Dmx):
                level = backend_dmx.get_output_level(univ, output)
            elif backend_dmx is not None and univ in patch.universes:
                idx = patch.universes.index(univ)
                if idx < len(backend_dmx.frame):
                    dimmer_idx = output - 1
                    if 0 <= dimmer_idx < len(backend_dmx.frame[idx]):
                        level = int(backend_dmx.frame[idx][dimmer_idx])
            elif app.engine is not None:
                try:
                    level = app.engine.get_output_level(univ, output)
                except (KeyError, IndexError, AttributeError):
                    pass
            channels[channel] = max(channels.get(channel, 0.0), float(level) / 255.0)

    # Also capture multi-parameter devices (including Virtual Dimmer fixtures)
    user_levels = (
        backend_dmx.levels.get("user", [])
        if backend_dmx is not None and isinstance(backend_dmx.levels, dict)
        else []
    )
    for dev_id, dev in getattr(patch, "devices", {}).items():
        if dev_id in inde_channels:
            continue
        dev_lvl = float(getattr(dev, "intensity", 0.0))
        if 1 <= dev_id <= min(MAX_CHANNELS, len(user_levels)):
            u_lvl = float(user_levels[dev_id - 1])
            if u_lvl >= 0.0:
                dev_lvl = max(dev_lvl, u_lvl)
        channels[dev_id] = max(channels.get(dev_id, 0.0), dev_lvl)

    return channels


def capture_live_devices(
    app: CoreApplication,
    live_channels: dict[int, float] | None = None,
) -> dict[int, dict[str, typing.Any]]:
    """Capture active multi-parameter device attributes and intensities."""
    device_values: dict[int, dict[str, typing.Any]] = {}
    patch = getattr(app.lightshow, "patch", None)
    if patch is None:
        return device_values

    independents = getattr(app.lightshow, "independents", None)
    inde_channels = independents.channels if independents is not None else set()

    for dev_id, dev in getattr(patch, "devices", {}).items():
        if dev_id in inde_channels:
            continue
        vals = _extract_device_active_values(dev)
        dev_int = float(getattr(dev, "intensity", 0.0))
        if live_channels is not None and dev_id in live_channels:
            ch_int = float(live_channels[dev_id])
            dev_int = max(dev_int, ch_int)
        if dev_int > 0.0:
            vals["intensity"] = dev_int
        if vals:
            device_values[dev_id] = vals

    return device_values


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
            else lightshow.get_sequence(self.sequence)
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

        # Capture live stage channels and multi-parameter device values
        live_channels = capture_live_channels(self.app)
        channels = {ch: lvl for ch, lvl in live_channels.items() if lvl > 0}
        device_values = capture_live_devices(self.app, live_channels)

        cue = Cue(
            self.sequence,
            self.number,
            channels,
            device_values=device_values,
        )
        self.created_cue = cue

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
            else lightshow.get_sequence(self.sequence)
        )
        if main_playback is None or self.number is None or self.step is None:
            return

        if self.created_step and self.created_step in main_playback.steps:
            main_playback.steps.remove(self.created_step)
            main_playback.last = len(main_playback.steps)

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
            else lightshow.get_sequence(self.sequence)
        )
        if (
            main_playback is None
            or self.created_cue is None
            or self.created_step is None
            or self.step is None
            or self.number is None
        ):
            return

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
        self.old_channels: dict[int, int | float] = {}
        self.new_channels: dict[int, int | float] = {}
        self.old_device_values: dict[int, dict[str, typing.Any]] = {}
        self.new_device_values: dict[int, dict[str, typing.Any]] = {}

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
        """Execute updating the target cue with live stage levels and device values."""
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_sequence(self.sequence)
        )
        if main_playback is None:
            return

        target_cue: Cue | None = None
        if self.number is not None:
            target_cue = lightshow.get_cue(self.number, self.sequence)
        elif 0 <= main_playback.position < len(main_playback.steps):
            target_cue = main_playback.steps[main_playback.position].cue

        if target_cue is None:
            return

        self.target_cue = target_cue
        self.old_channels = dict(target_cue.channels)
        self.old_device_values = copy.deepcopy(target_cue.device_values)

        live_channels = capture_live_channels(self.app)
        updated_channels = dict(target_cue.channels)
        updated_channels.update(live_channels)
        self.new_channels = updated_channels

        live_devices = capture_live_devices(self.app, live_channels)
        updated_devices = copy.deepcopy(target_cue.device_values)
        for dev_id, vals in live_devices.items():
            updated_devices.setdefault(dev_id, {}).update(vals)
        for dev_id, lvl in live_channels.items():
            if (
                lvl == 0
                and dev_id in updated_devices
                and "intensity" in updated_devices[dev_id]
            ):
                updated_devices[dev_id]["intensity"] = 0.0
        self.new_device_values = updated_devices

        target_cue.channels = dict(self.new_channels)
        target_cue.device_values = copy.deepcopy(self.new_device_values)
        main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.updated", target_cue.sequence, target_cue.number)

    def undo(self) -> None:
        """Undo cue update, restoring previous channel levels and device values."""
        if self.target_cue is None:
            return

        self.target_cue.channels = dict(self.old_channels)
        self.target_cue.device_values = copy.deepcopy(self.old_device_values)
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_sequence(self.sequence)
        )
        if main_playback:
            main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.updated", self.target_cue.sequence, self.target_cue.number)

    def redo(self) -> None:
        """Redo cue update, re-applying captured channel levels and device values."""
        if self.target_cue is None:
            return

        self.target_cue.channels = dict(self.new_channels)
        self.target_cue.device_values = copy.deepcopy(self.new_device_values)
        lightshow = self.app.lightshow
        main_playback = (
            lightshow.main_playback
            if self.sequence == 1
            else lightshow.get_sequence(self.sequence)
        )
        if main_playback:
            main_playback.update_channels()
        lightshow.set_modified()

        self.app.emit("cue.updated", self.target_cue.sequence, self.target_cue.number)


class PlaybackStopAction(Action):
    """Action to stop the main playback sequence."""

    name = "playback.stop"
    can_undo = False

    def execute(self) -> None:
        """Stop all active sequences and the playback engine worker."""
        main_playback = _get_main_sequence(self.app)
        if main_playback:
            main_playback.stop()
        for seq in self.app.lightshow.sequences:
            seq.stop()
        engine = getattr(self.app, "playback_engine", None)
        if engine is not None:
            engine.stop_worker()
        self.app.emit("playback.stopped")
