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
# pylint: disable=too-many-lines
from __future__ import annotations

import threading
import time
import typing
from typing import Optional

import numpy as np

from olc.core.tracking import DEFAULT_MIB_FADE_TIME, TrackingEngine
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.step import Step, get_parameter_family

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.app import CoreApplication
    from olc.core.lightshow import LightShow
    from olc.patch import PatchManager


def get_cue(step: Step) -> typing.Any:  # noqa: ANN401
    """Get the cue object from step as Any to simplify type checking."""
    return step.cue


# pylint: disable=too-many-instance-attributes
class Sequence:
    """Sequence Object
    A Sequence is a collection of Steps
    """

    index: float
    type_seq: str
    text: str
    thread: Optional[ThreadGo | ThreadGoBack]
    lightshow: typing.Optional[LightShow]
    backend: typing.Any
    _on_go: bool

    def __init__(
        self,
        index: float,
        type_seq: str = "Normal",
        text: str = "",
        lightshow: typing.Optional[LightShow] = None,
    ) -> None:
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.lightshow = lightshow
        self.cues = set()
        self.steps: list[Step] = []
        self.position = 0
        self.last = 0
        # Flag to know if we have a Go in progress
        self._on_go = False
        # Channels present in this sequence
        self.channels: set[int] = set()
        # Flag for chasers
        self.run = False
        # Thread for Go and GoBack
        self.thread = None
        # Tracking mode (False = Cue-Only, True = Tracking for intensity)
        self.tracking_mode = False
        # Move In Black (MIB) pre-positioning and post-extinction fade time (s)
        self.mib_enabled = True
        self.mib_fade_time = DEFAULT_MIB_FADE_TIME

        # Step and Cue 0
        cue = Cue(0, 0.0)
        self.cues.add(cue)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

    @property
    def patch(self) -> Optional[PatchManager]:
        """Get PatchManager from lightshow if available."""
        if self.lightshow is not None:
            return getattr(self.lightshow, "patch", None)
        return None

    def load_step(self, step_index: int) -> None:
        """Directly load and apply a sequence step state to DMX outputs."""
        if not self.steps or step_index < 0 or step_index >= len(self.steps):
            return
        self.position = step_index
        resolved = TrackingEngine.resolve_step_state(
            self, step_index, tracking_mode=self.tracking_mode, patch=self.patch
        )
        if self.backend is not None and hasattr(self.backend, "dmx"):
            n_ch = min(len(self.backend.dmx.levels["sequence"]), len(resolved.channels))
            self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]
            if self.patch is not None:
                for dev_id, params in resolved.device_values.items():
                    dev = self.patch.get_device(dev_id)
                    if dev is not None:
                        dev.apply_device_values(params)
            self.backend.dmx.set_levels()
        self.update_channels()

    @property
    def on_go(self) -> bool:
        """Check if a Go transition is in progress."""
        return getattr(self, "_on_go", False)

    @on_go.setter
    def on_go(self, value: bool) -> None:
        """Set the on_go transition flag and trigger event notifications."""
        if getattr(self, "_on_go", False) != value:
            self._on_go = value
            if self.app is not None:
                core = getattr(self.app, "core", self.app)
                # Update action registry feedback for MIDI bindings
                core.action_registry.trigger_feedback("playback.go")
                # Emit event for GUI (GuiEventBridge)
                core.emit(
                    "playback.go_triggered",
                    core.action_registry.get("playback.go").get_feedback_state(),
                )

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        if self.lightshow:
            return self.lightshow.app
        return None

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        if self.app is not None:
            return typing.cast(typing.Any, self.app).backend
        return None

    def stop(self) -> bool:
        """Stop Go

        Returns:
            True if Go to stop, else False
        """
        if (
            self.on_go
            and self.thread
            and self.app is not None
            and self.app.midi is not None
        ):
            self.app.midi.button_off("playback.go")
            # Switch off Pause Led
            if not self.thread.pause.is_set():
                self.thread.pause.set()
                if self.app is not None and self.app.midi is not None:
                    self.app.midi.button_off("playback.pause")
                if self.app is not None:
                    core = getattr(self.app, "core", self.app)
                    core.action_registry.trigger_feedback("playback.pause")
                    core.emit(
                        "playback.pause_triggered",
                        core.action_registry.get("playback.pause").get_feedback_state(),
                    )
            else:
                self.thread.pause.set()
            self.thread.stop()
            self.thread.join()
            self.on_go = False
            if self.app is not None and self.app.crossfade is not None:
                self.app.crossfade.scale_a.set_value(0)
                self.app.crossfade.scale_b.set_value(0)
            # Stop at the end
            self.position = min(self.position, self.last - 3)
            return True
        return False

    def update_channels(self) -> None:
        """Update channels present in sequence"""
        self.channels.clear()
        for step in self.steps:
            if step.cue is not None:
                for channel in step.cue.channels:
                    self.channels.add(channel)
        if self.app is not None and self.backend is not None:
            for channel, level in enumerate(self.backend.dmx.levels["user"]):
                if level != -1:
                    self.channels.add(channel + 1)

    def add_step(self, step: Step) -> None:
        """Add step at the end

        Args:
            step: Step number
        """
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        if step.cue is not None:
            for channel in step.cue.channels:
                self.channels.add(channel)

    def insert_step(self, index: int, step: Step) -> None:
        """Insert step at index

        Args:
            index: Index
            step: Step
        """
        self.steps.insert(index, step)
        self.last = len(self.steps)
        # Channels used in sequential
        if step.cue is not None:
            for channel in step.cue.channels:
                self.channels.add(channel)

    def get_step(self, cue: Optional[float] = None) -> tuple[bool, int]:
        """Get Cue Step

        Args:
            cue (float): Cue number

        Returns:
            found (bool), step (int)
        """
        found = False
        step = 0
        # Cue already exist ?
        for item in self.steps:
            if item.cue is not None and item.cue.number == cue:
                found = True
                break
            step += 1
        step -= 1
        # If new Cue, find step index
        if not found:
            exist = False
            step = 0
            for item in self.steps:
                if item.cue is not None and cue is not None and item.cue.number > cue:
                    exist = True
                    break
                step += 1
            if not exist:
                step += 1
        elif step:
            step += 1

        return found, step

    def get_next_cue(self, step: Optional[int] = None) -> Optional[float]:
        """Get next free Cue

        Args:
            step: Actual Cue Step number

        Returns:
            Cue number
        """
        if step is None:
            return None
        step_cue = self.steps[step].cue
        number = step_cue.number if step_cue is not None else 0.0
        if step >= self.last - 1:
            return number + 1

        next_step_cue = self.steps[step + 1].cue
        next_number = next_step_cue.number if next_step_cue is not None else 0.0
        return (
            ((next_number - number) / 2) + number
            if next_number != 0.0 and (next_number - number) <= 1
            else number + 1
        )

    def get_next_channel_level(self, channel: int, level: int) -> int:
        """Get channel level in next cue

        Args:
            channel: channel number (1 - MAX_CHANNELS)
            level: level in active cue (0 - 255)

        Returns:
            level in next cue (0 - 255)
        """
        if (
            len(self.steps) > self.position + 1
            and self.last > 1
            and self.position < self.last - 1
        ):
            next_cue = self.steps[self.position + 1].cue
            next_level = (
                next_cue.channels.get(channel, 0) if next_cue is not None else 0
            )
        elif self.last:
            first_cue = self.steps[0].cue
            next_level = (
                first_cue.channels.get(channel, 0) if first_cue is not None else 0
            )
        else:
            next_level = level
        return next_level

    def sequence_plus(self) -> None:
        """Sequence +"""
        self.stop()

        # Jump to next Step
        position = self.position + 1
        if position < self.last - 1:  # Stop on the last cue
            if self.backend is not None and self.backend.dmx is not None:
                self.backend.dmx.levels["user"].fill(-1)
            self.load_step(position)

    def sequence_minus(self) -> None:
        """Sequence -"""
        self.stop()

        # Jump to previous Step
        position = self.position - 1
        if position >= 0:
            if self.backend is not None and self.backend.dmx is not None:
                self.backend.dmx.levels["user"].fill(-1)
            self.load_step(position)

    def goto(self, keystring: str, override_time: Optional[float] = None) -> None:
        """Jump to cue number

        Args:
            keystring: Cue number
            override_time: Optional override fade time in seconds (0 = instant load)
        """
        old_pos = self.position

        if not keystring:
            return

        # Scan all cues
        for i, step in enumerate(self.steps):
            # Until we find the good one
            if float(get_cue(step).number) == float(keystring):
                # Position to the one just before
                self.position = i - 1
                next_step = self.position + 1

                eff_total = (
                    override_time
                    if override_time is not None
                    else self.steps[next_step].total_time
                )
                eff_in = (
                    override_time
                    if override_time is not None
                    else self.steps[next_step].time_in
                )
                eff_out = (
                    override_time
                    if override_time is not None
                    else self.steps[next_step].time_out
                )

                # Emit event for GUI (GuiEventBridge) to setup times and view
                if self.app is not None:
                    core = getattr(self.app, "core", self.app)
                    core.emit(
                        "playback.goto_selected",
                        {
                            "old_pos": old_pos,
                            "next_step": next_step,
                            "keystring": keystring,
                            "total_time": eff_total,
                            "time_in": eff_in,
                            "time_out": eff_out,
                            "delay_in": (
                                0.0
                                if override_time is not None
                                else self.steps[next_step].delay_in
                            ),
                            "delay_out": (
                                0.0
                                if override_time is not None
                                else self.steps[next_step].delay_out
                            ),
                            "wait": (
                                0.0
                                if override_time is not None
                                else self.steps[next_step].wait
                            ),
                            "channel_time": (
                                {}
                                if override_time is not None
                                else self.steps[next_step].channel_time
                            ),
                        },
                    )

                if override_time is not None and override_time <= 0.0:
                    self.stop()
                    if self.backend is not None and self.backend.dmx is not None:
                        self.backend.dmx.levels["user"].fill(-1)
                    self.load_step(i)
                    self.position = i - 1
                    next_after = _next_step(self)
                    if self.app is not None:
                        core = getattr(self.app, "core", self.app)
                        core.emit(
                            "playback.transition_completed",
                            {"next_step": next_after},
                        )
                else:
                    # Launch Go
                    self.do_go(None, True, override_time=override_time)
                break

    def do_go(
        self,
        _action: Optional[Gio.SimpleAction],
        goto: bool = False,
        override_time: Optional[float] = None,
    ) -> None:
        """Go

        Args:
            goto: True if Goto, False if Go (default)
            override_time: Optional override fade time in seconds
        """
        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_on("playback.go")
        # If Go is active, go to next cue
        if self.stop():
            # Launch another Go
            position = self.position
            position += 1
            if position < self.last - 1:
                self.position += 1
            else:
                self.position = 0
                position = 0
            self.on_go = False

            # Set main window's subtitle
            subtitle = (
                f"Mem. : {get_cue(self.steps[position]).number} "
                f"{self.steps[position].text} - Next Mem. : "
                f"{get_cue(self.steps[position + 1]).number} "
                f"{self.steps[position + 1].text}"
            )

            # Emit event for GUI (GuiEventBridge)
            if self.app is not None:
                core = getattr(self.app, "core", self.app)
                core.emit(
                    "playback.go_triggered_direct",
                    {
                        "position": position,
                        "subtitle": subtitle,
                        "total_time": self.steps[position + 1].total_time,
                        "time_in": self.steps[position + 1].time_in,
                        "time_out": self.steps[position + 1].time_out,
                        "delay_in": self.steps[position + 1].delay_in,
                        "delay_out": self.steps[position + 1].delay_out,
                        "wait": self.steps[position + 1].wait,
                        "channel_time": self.steps[position + 1].channel_time,
                    },
                )

            self.do_go(None, override_time=override_time)

        else:
            # Indicates that a Go is in progress
            self.on_go = True
            self.thread = ThreadGo(goto, self, override_time=override_time)
            self.thread.start()

    def go_back(self, _action: Optional[Gio.SimpleAction], _param: None) -> bool:
        """Go Back

        Returns:
            True or False
        """
        # Just return if we are at the beginning
        position = self.position
        if position <= 0:
            return False

        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_on("playback.go_back")

        self.stop()

        goback_time = 0.0
        if self.app is not None:
            goback_time = typing.cast(typing.Any, self.app.settings).get_double(
                "go-back-time"
            )

        subtitle = (
            f"Mem. : {get_cue(self.steps[position]).number} "
            f"{self.steps[position].text}"
            f" - Next Mem. : {get_cue(self.steps[position - 1]).number} "
            f"{self.steps[position - 1].text}"
        )

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.go_back_started",
                {
                    "position": position,
                    "subtitle": subtitle,
                    "goback_time": goback_time,
                },
            )

        self.on_go = True
        self.thread = ThreadGoBack(self)
        self.thread.start()
        return False

    def pause(self, _action: Optional[Gio.SimpleAction], _param: None) -> None:
        """Toggle pause"""
        if self.thread:
            if self.thread.pause.is_set():
                self.thread.pause.clear()
                if self.app is not None and self.app.midi is not None:
                    self.app.midi.button_on("playback.pause")
            else:
                self.thread.pause.set()
                if self.app is not None and self.app.midi is not None:
                    self.app.midi.button_off("playback.pause")
            if self.app is not None:
                core = getattr(self.app, "core", self.app)
                core.action_registry.trigger_feedback("playback.pause")
                core.emit(
                    "playback.pause_triggered",
                    core.action_registry.get("playback.pause").get_feedback_state(),
                )


def _capture_device_states(
    patch: Optional[PatchManager],
) -> dict[int, dict[str, typing.Any]]:
    """Capture current physical attribute states of all patched devices."""
    states: dict[int, dict[str, typing.Any]] = {}
    if patch is None:
        return states
    for dev_id, dev in getattr(patch, "devices", {}).items():
        srgb = getattr(dev, "color_srgb", None)
        rgb = (srgb.r, srgb.g, srgb.b) if srgb is not None else (0.0, 0.0, 0.0)
        states[dev_id] = {
            "intensity": getattr(dev, "intensity", 0.0),
            "pan": getattr(dev, "pan_degrees", 0.0),
            "tilt": getattr(dev, "tilt_degrees", 0.0),
            "zoom": getattr(dev, "zoom_degrees", None),
            "focus": getattr(dev, "focus_meters", None),
            "strobe": getattr(dev, "strobe_hz", None),
            "cct": getattr(dev, "color_temp_kelvin", None),
            "iris": getattr(dev, "iris", None),
            "color_rgb": rgb,
        }
    return states


def _parse_rgb_norm(value: typing.Any) -> Optional[tuple[float, float, float]]:  # noqa: ANN401
    """Parse hex color or RGB tuple into normalized (r, g, b) in [0.0, 1.0]."""
    if isinstance(value, str):
        hex_str = value.strip().lstrip("#")
        if len(hex_str) in (6, 8):
            try:
                return (
                    int(hex_str[0:2], 16) / 255.0,
                    int(hex_str[2:4], 16) / 255.0,
                    int(hex_str[4:6], 16) / 255.0,
                )
            except ValueError:
                return None
    elif isinstance(value, (tuple, list)) and len(value) >= 3:
        v0, v1, v2 = float(value[0]), float(value[1]), float(value[2])
        if max(v0, v1, v2) > 1.0:
            return (v0 / 255.0, v1 / 255.0, v2 / 255.0)
        return (v0, v1, v2)
    return None


def _interpolate_device_states(  # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments, too-many-branches
    patch: Optional[PatchManager],
    start_states: dict[int, dict[str, typing.Any]],
    target_values: dict[int, dict[str, typing.Any]],
    factor: float,
    mib_factors: Optional[dict[int, float]] = None,
    mib_parameters: Optional[dict[int, set[str]]] = None,
    intensity_out_factors: Optional[dict[int, float]] = None,
    family_factors: Optional[dict[str, float]] = None,
    explicit_families: Optional[set[str]] = None,
) -> None:
    """Interpolate continuous physical device parameters at progress factor."""
    if patch is None or not target_values:
        return
    alpha = max(0.0, min(1.0, factor))
    scalar_map = {
        "pan": "pan",
        "tilt": "tilt",
        "zoom": "zoom",
        "focus": "focus",
        "strobe": "strobe",
        "cct": "cct",
        "color_temp": "cct",
        "colortemp": "cct",
        "iris": "iris",
    }
    for dev_id, params in target_values.items():
        dev = patch.get_device(dev_id)
        if dev is None:
            continue
        start = start_states.get(dev_id, {})
        for param_name, target_val in params.items():
            p_lower = param_name.lower()
            if p_lower == "intensity":
                s_val = float(start.get("intensity", getattr(dev, "intensity", 0.0)))
                t_val = float(target_val)
                int_alpha = alpha
                if (
                    t_val < s_val
                    and intensity_out_factors is not None
                    and dev_id in intensity_out_factors
                ):
                    int_alpha = max(0.0, min(1.0, intensity_out_factors[dev_id]))
                dev.set_intensity(s_val + int_alpha * (t_val - s_val))
                continue

            family = get_parameter_family(param_name)
            param_alpha = (
                max(0.0, min(1.0, family_factors.get(family, alpha)))
                if family_factors is not None
                else alpha
            )
            is_explicit_family = (
                explicit_families is not None and family in explicit_families
            )
            if (
                not is_explicit_family
                and mib_factors is not None
                and dev_id in mib_factors
                and (
                    mib_parameters is None
                    or param_name in mib_parameters.get(dev_id, set())
                )
            ):
                param_alpha = max(0.0, min(1.0, mib_factors[dev_id]))

            if p_lower in scalar_map:
                s_key = scalar_map[p_lower]
                s_opt = start.get(s_key)
                if s_opt is not None:
                    interp = float(s_opt) + param_alpha * (
                        float(target_val) - float(s_opt)
                    )
                    dev.apply_device_parameter(p_lower, interp)
                else:
                    dev.apply_device_parameter(p_lower, float(target_val))
            elif p_lower in ("color", "colour"):
                target_rgb = _parse_rgb_norm(target_val)
                if target_rgb is not None and hasattr(dev, "set_color_srgb"):
                    r0, g0, b0 = start.get("color_rgb", (0.0, 0.0, 0.0))
                    dev.set_color_srgb(
                        r0 + param_alpha * (target_rgb[0] - r0),
                        g0 + param_alpha * (target_rgb[1] - g0),
                        b0 + param_alpha * (target_rgb[2] - b0),
                    )
                else:
                    dev.apply_device_parameter(p_lower, target_val)
            elif param_alpha > 0.0:
                dev.apply_device_parameter(p_lower, target_val)


# pylint: disable=too-many-instance-attributes
class ThreadGo(threading.Thread):
    """Thread object for Go"""

    sequence: Sequence
    old_channels_levels: np.ndarray
    old_device_states: dict[int, dict[str, typing.Any]]
    total_time: float
    time_in: float
    time_out: float
    wait: float
    delay_in: float
    delay_out: float
    goto: bool
    override_time: Optional[float]
    backend: typing.Any

    def __init__(
        self,
        goto: bool,
        sequence: Sequence,
        override_time: Optional[float] = None,
    ) -> None:
        threading.Thread.__init__(self, name="ThreadGo", daemon=True)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        self.override_time = override_time
        # To save channels levels when user sends Go
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = {}
        next_step = self.sequence.position + 1
        if override_time is not None:
            self.total_time = override_time * 1000.0
            self.time_in = override_time * 1000.0
            self.time_out = override_time * 1000.0
            self.wait = 0.0
            self.delay_in = 0.0
            self.delay_out = 0.0
        else:
            self.total_time = self.sequence.steps[next_step].total_time * 1000
            self.time_in = self.sequence.steps[next_step].time_in * 1000
            self.time_out = self.sequence.steps[next_step].time_out * 1000
            self.wait = self.sequence.steps[next_step].wait * 1000
            self.delay_in = self.sequence.steps[next_step].delay_in * 1000
            self.delay_out = self.sequence.steps[next_step].delay_out * 1000
        self.goto = goto

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.sequence.app

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        return self.sequence.backend

    def _was_device_lit(self, dev_id: int) -> bool:
        """Return True if dev_id had non-zero intensity when Go was triggered."""
        if (
            1 <= dev_id <= len(self.old_channels_levels)
            and int(self.old_channels_levels[dev_id - 1]) > 0
        ):
            return True
        old_int = float(self.old_device_states.get(dev_id, {}).get("intensity", 0.0))
        return old_int > 0.0

    def _get_device_dark_time_ms(self, step: Step, dev_id: int) -> float:
        """Return elapsed time (ms) when a fading-out device reaches 0% intensity."""
        if (
            self.override_time is None
            and step.channel_time
            and dev_id in step.channel_time
        ):
            ct = step.channel_time[dev_id]
            return self.wait + (ct.delay + ct.time) * 1000.0
        return self.wait + self.delay_out + self.time_out

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels and device states when Go is sent"""
        self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
        user_levels = self.backend.dmx.levels["user"]
        user_mask = user_levels != -1
        self.old_channels_levels[user_mask] = user_levels[user_mask]
        self.old_device_states = _capture_device_states(self.sequence.patch)

        next_step_idx = self.sequence.position + 1
        if 0 <= next_step_idx < len(self.sequence.steps):
            step = self.sequence.steps[next_step_idx]
            resolved = TrackingEngine.resolve_step_state(
                self.sequence,
                next_step_idx,
                tracking_mode=self.sequence.tracking_mode,
                patch=self.sequence.patch,
            )
            mib_dur_ms = max(
                0.0,
                float(getattr(self.sequence, "mib_fade_time", DEFAULT_MIB_FADE_TIME))
                * 1000.0,
            )
            for dev_id, mib_params in resolved.mib_parameters.items():
                has_non_explicit_mib = any(
                    not step.has_explicit_family_timing(get_parameter_family(p))
                    for p in mib_params
                )
                if has_non_explicit_mib and self._was_device_lit(dev_id):
                    t_dark_ms = self._get_device_dark_time_ms(step, dev_id)
                    self.total_time = max(self.total_time, t_dark_ms + mib_dur_ms)

    def _finalize_go(self) -> None:
        """Finish load cue after sequence transition"""
        if self.sequence.position < self.sequence.last - 1:
            target_step_idx = self.sequence.position + 1
        else:
            target_step_idx = 0

        # Resolve full sequential state via TrackingEngine
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            target_step_idx,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )

        # Block-copy levels to sequential dmx levels
        n_ch = min(len(self.backend.dmx.levels["sequence"]), len(resolved.channels))
        self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]

        # Apply multi-parameter device values
        if self.sequence.patch is not None:
            for dev_id, params in resolved.device_values.items():
                dev = self.sequence.patch.get_device(dev_id)
                if dev is not None:
                    dev.apply_device_values(params)

        self.sequence.on_go = False
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(0)
            self.app.crossfade.scale_b.set_value(0)
        self.backend.dmx.levels["user"].fill(-1)

        # Distribute DMX levels to frames
        self.backend.dmx.set_levels()

        self.sequence.update_channels()
        next_step = _next_step(self.sequence)

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.transition_completed",
                {
                    "next_step": next_step,
                },
            )

        if self.sequence.steps[next_step].wait:
            self.sequence.do_go(None)
        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_off("playback.go")

    def run(self) -> None:
        self._capture_start_levels()
        start_pause = None
        pause_time = 0.0
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time
        while i < self.total_time and not self._stopevent.is_set():
            if not self.pause.is_set():
                if not start_pause:
                    start_pause = time.time() * 1000
                self.pause.wait()
                pause_time += (time.time() * 1000) - start_pause
            else:
                start_pause = None
                i = (time.time() * 1000) - (start_time + pause_time)
                self.update_levels(i)
                time.sleep(0.05)

        if self._stopevent.is_set():
            return

        self._finalize_go()

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()

    def update_levels(self, i: float) -> None:
        """Update levels

        Args:
            i: Time spent
        """
        val = round((255 / self.total_time) * i)
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(val)
            self.app.crossfade.scale_b.set_value(val)

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.transition_progress",
                {
                    "time_spent": i,
                    "total_time": self.total_time,
                    "progress_val": val,
                    "sequence_position": self.sequence.position,
                },
            )

        # Wait for wait time
        if i > self.wait:
            if self.goto:
                self._do_goto(i)
            else:
                self._do_go(i)

    def _do_goto(self, i: float) -> None:
        """Goto

        Args:
            i: Time spent
        """
        self._do_go(i)

    def _do_go(self, i: float) -> None:
        """Go

        Args:
            i: Time spent
        """
        next_step = self.sequence.position + 1
        step = self.sequence.steps[next_step]

        lvls = self._calculate_transitions_go(i, step)
        self._apply_channel_times_go(lvls, i, step)

        self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0, 255).astype(np.uint8)
        self.backend.dmx.set_levels()

    def _compute_device_factors_go(  # pylint: disable=too-many-locals, too-many-branches
        self,
        i: float,
        step: Step,
        resolved: typing.Any,  # noqa: ANN401
    ) -> tuple[
        float,
        dict[int, float],
        dict[int, float],
        dict[str, float],
        set[str],
    ]:
        """Compute LTP, MIB, intensity-out, and IFCB family factors at elapsed ms i."""

        def _window_factor(delay_s: float, time_s: float) -> float:
            start_ms = self.wait + delay_s * 1000.0
            dur_ms = time_s * 1000.0
            if dur_ms <= 0:
                return 1.0 if i >= start_ms else 0.0
            return max(0.0, min(1.0, (i - start_ms) / dur_ms))

        if self.override_time is not None:
            ltp_factor = _window_factor(0.0, self.override_time)
            default_out_factor = ltp_factor
            family_factors: dict[str, float] = {
                "position": ltp_factor,
                "color": ltp_factor,
                "beam": ltp_factor,
            }
            explicit_families: set[str] = set()
        else:
            ltp_factor = _window_factor(step.delay_in, step.time_in)
            default_out_factor = _window_factor(step.delay_out, step.time_out)
            family_factors = {
                "position": _window_factor(
                    step.effective_delay_position, step.effective_time_position
                ),
                "color": _window_factor(
                    step.effective_delay_color, step.effective_time_color
                ),
                "beam": _window_factor(
                    step.effective_delay_beam, step.effective_time_beam
                ),
            }
            explicit_families = {
                fam
                for fam in ("position", "color", "beam")
                if step.has_explicit_family_timing(fam)
            }

        mib_factors: dict[int, float] = {}
        intensity_out_factors: dict[int, float] = {}
        mib_dur_ms = max(
            0.0,
            float(getattr(self.sequence, "mib_fade_time", DEFAULT_MIB_FADE_TIME))
            * 1000.0,
        )

        for dev_id in resolved.device_values:
            if (
                self.override_time is None
                and step.channel_time
                and dev_id in step.channel_time
            ):
                ct = step.channel_time[dev_id]
                intensity_out_factors[dev_id] = _window_factor(ct.delay, ct.time)
            else:
                intensity_out_factors[dev_id] = default_out_factor

            if dev_id in resolved.mib_parameters and resolved.mib_parameters[dev_id]:
                if self._was_device_lit(dev_id):
                    t_dark_ms = self._get_device_dark_time_ms(step, dev_id)
                    if i < t_dark_ms:
                        mib_factors[dev_id] = 0.0
                    elif mib_dur_ms <= 0:
                        mib_factors[dev_id] = 1.0
                    else:
                        mib_factors[dev_id] = max(
                            0.0, min(1.0, (i - t_dark_ms) / mib_dur_ms)
                        )
                elif (
                    self.override_time is None
                    and step.channel_time
                    and dev_id in step.channel_time
                ):
                    mib_factors[dev_id] = intensity_out_factors[dev_id]
                else:
                    mib_factors[dev_id] = ltp_factor

        return (
            ltp_factor,
            mib_factors,
            intensity_out_factors,
            family_factors,
            explicit_families,
        )

    def _calculate_transitions_go(  # pylint: disable=too-many-locals
        self, i: float, step: Step
    ) -> np.ndarray:
        """Calculate fade levels using array operations."""
        old_levels = self.old_channels_levels.astype(np.int32)
        next_step_idx = self.sequence.position + 1
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            next_step_idx,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        next_levels = resolved.channels.astype(np.int32)
        lvls = old_levels.copy()

        # Decays (channels going down)
        decay_mask = next_levels < old_levels
        if np.any(decay_mask):
            progress_mask = (i > self.wait + self.delay_out) & (
                i < self.time_out + self.wait + self.delay_out
            )
            if np.any(progress_mask & decay_mask) and self.time_out > 0:
                factor = (i - self.wait - self.delay_out) / self.time_out
                diff = (next_levels - old_levels) * factor
                decay_lvls = np.round(old_levels - np.abs(diff)).astype(np.int32)
                lvls[progress_mask & decay_mask] = decay_lvls[
                    progress_mask & decay_mask
                ]

            end_mask = i >= self.time_out + self.wait + self.delay_out
            lvls[end_mask & decay_mask] = next_levels[end_mask & decay_mask]

        # Attacks (channels going up)
        attack_mask = next_levels > old_levels
        if np.any(attack_mask):
            progress_mask = (i > self.wait + self.delay_in) & (
                i < self.time_in + self.wait + self.delay_in
            )
            if np.any(progress_mask & attack_mask) and self.time_in > 0:
                factor = (i - self.wait - self.delay_in) / self.time_in
                diff = (next_levels - old_levels) * factor
                attack_lvls = np.round(old_levels + diff).astype(np.int32)
                lvls[progress_mask & attack_mask] = attack_lvls[
                    progress_mask & attack_mask
                ]

            end_mask = i >= self.time_in + self.wait + self.delay_in
            lvls[end_mask & attack_mask] = next_levels[end_mask & attack_mask]

        # Continuous interpolation of multi-parameter LTP and MIB attributes
        if resolved.device_values and self.sequence.patch is not None:
            (
                ltp_factor,
                mib_factors,
                intensity_out_factors,
                family_factors,
                explicit_families,
            ) = self._compute_device_factors_go(i, step, resolved)
            _interpolate_device_states(
                self.sequence.patch,
                self.old_device_states,
                resolved.device_values,
                ltp_factor,
                mib_factors=mib_factors,
                mib_parameters=resolved.mib_parameters,
                intensity_out_factors=intensity_out_factors,
                family_factors=family_factors,
                explicit_families=explicit_families,
            )

        return lvls

    def _apply_channel_times_go(self, lvls: np.ndarray, i: float, step: Step) -> None:
        """Apply individual channel times."""
        if not step.channel_time or self.override_time is not None:
            return
        old_levels = self.old_channels_levels.astype(np.int32)
        next_step_idx = self.sequence.position + 1
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            next_step_idx,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        next_levels = resolved.channels.astype(np.int32)
        for channel, ct in step.channel_time.items():
            o_lvl = old_levels[channel - 1]
            n_lvl = next_levels[channel - 1]
            if n_lvl < o_lvl:  # Decay
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = o_lvl - abs(int((n_lvl - o_lvl) * factor))
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl
            elif n_lvl > o_lvl:  # Attack
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = int((n_lvl - o_lvl) * factor + o_lvl)
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl


def _next_step(sequence: Sequence) -> int:
    """Next Step after Go

    Args:
        sequence: Main Playback

    Returns:
        Step
    """
    next_step = sequence.position + 1
    # If there is a next step
    if next_step < sequence.last - 1:
        sequence.position += 1
        next_step += 1
    # If no next step, go to beginning
    else:
        sequence.position = 0
        next_step = 1

    # Main window's subtitle
    subtitle = (
        f"Mem. : {get_cue(sequence.steps[sequence.position]).number} "
        f"{sequence.steps[sequence.position].text} - Next Mem. : "
        f"{get_cue(sequence.steps[next_step]).number} "
        f"{sequence.steps[next_step].text}"
    )

    # Emit event for GUI (GuiEventBridge)
    if sequence.app is not None:
        core = getattr(sequence.app, "core", sequence.app)
        core.emit(
            "playback.step_changed",
            {
                "position": sequence.position,
                "next_step": next_step,
                "subtitle": subtitle,
                "total_time": sequence.steps[next_step].total_time,
                "time_in": sequence.steps[next_step].time_in,
                "time_out": sequence.steps[next_step].time_out,
                "delay_in": sequence.steps[next_step].delay_in,
                "delay_out": sequence.steps[next_step].delay_out,
                "wait": sequence.steps[next_step].wait,
                "channel_time": sequence.steps[next_step].channel_time,
            },
        )
    return next_step


class ThreadGoBack(threading.Thread):
    """Thread Object for Go Back"""

    sequence: Sequence
    old_channels_levels: np.ndarray
    old_device_states: dict[int, dict[str, typing.Any]]
    backend: typing.Any

    def __init__(self, sequence: Sequence) -> None:
        threading.Thread.__init__(self, name="ThreadGoBack", daemon=True)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        # To save channels levels when Go Back starts
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = {}

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.sequence.app

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        return self.sequence.backend

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels and device states when Go Back starts"""
        self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
        user_levels = self.backend.dmx.levels["user"]
        user_mask = user_levels != -1
        self.old_channels_levels[user_mask] = user_levels[user_mask]
        self.old_device_states = _capture_device_states(self.sequence.patch)

    def _finalize_goback(self, prev_step: int) -> None:
        """Finish load cue after sequence transition"""
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            prev_step,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )

        # Block-copy levels to sequential dmx levels
        n_ch = min(len(self.backend.dmx.levels["sequence"]), len(resolved.channels))
        self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]

        # Apply multi-parameter device values
        if self.sequence.patch is not None:
            for dev_id, params in resolved.device_values.items():
                dev = self.sequence.patch.get_device(dev_id)
                if dev is not None:
                    dev.apply_device_values(params)

        self.sequence.on_go = False
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(0)
            self.app.crossfade.scale_b.set_value(0)
        self.backend.dmx.levels["user"].fill(-1)

        # Distribute DMX levels to frames
        self.backend.dmx.set_levels()

        self.sequence.update_channels()
        self.sequence.position = prev_step

        subtitle = (
            f"Mem. : {get_cue(self.sequence.steps[prev_step]).number} "
            f"{self.sequence.steps[prev_step].text} - Next Mem. : "
            f"{get_cue(self.sequence.steps[prev_step + 1]).number} "
            f"{self.sequence.steps[prev_step + 1].text}"
        )

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.goback_completed",
                {
                    "prev_step": prev_step,
                    "subtitle": subtitle,
                    "time_in": self.sequence.steps[prev_step + 1].time_in,
                    "time_out": self.sequence.steps[prev_step + 1].time_out,
                    "delay_in": self.sequence.steps[prev_step + 1].delay_in,
                    "delay_out": self.sequence.steps[prev_step + 1].delay_out,
                    "wait": self.sequence.steps[prev_step + 1].wait,
                    "total_time": self.sequence.steps[prev_step + 1].total_time,
                    "channel_time": self.sequence.steps[prev_step + 1].channel_time,
                },
            )

        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_off("playback.go_back")

    def run(self) -> None:
        if self.sequence.last == 2:
            return

        prev_step = self.sequence.position - 1
        self._capture_start_levels()

        go_back_time = 0.0
        if self.app is not None:
            go_back_time = (
                typing.cast(typing.Any, self.app.settings).get_double("go-back-time")
                * 1000
            )
        pause_time = 0.0
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time
        start_pause = None
        while i < go_back_time and not self._stopevent.is_set():
            if not self.pause.is_set():
                if not start_pause:
                    start_pause = time.time() * 1000
                self.pause.wait()
                pause_time += (time.time() * 1000) - start_pause
            else:
                start_pause = None
                self.update_levels(go_back_time, i, self.sequence.position)
                time.sleep(0.05)
                i = (time.time() * 1000) - (start_time + pause_time)

        self._finalize_goback(prev_step)

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()

    def update_levels(self, go_back_time: float, i: float, position: int) -> None:
        """Update levels

        Args:
            go_back_time: Default GoBack time
            i: Time spent
            position: Step
        """
        val = round((255 / go_back_time) * i)
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(val)
            self.app.crossfade.scale_b.set_value(val)

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.goback_progress",
                {
                    "time_spent": i,
                    "goback_time": go_back_time,
                    "position": position,
                    "progress_val": val,
                },
            )

        # Resolve previous step state via TrackingEngine
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            position - 1,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = resolved.channels.astype(np.int32)
        factor = i / go_back_time if go_back_time > 0 else 1.0
        diff = (next_levels - old_levels) * factor
        lvls = np.round(old_levels + diff).astype(np.int32)

        if resolved.device_values and self.sequence.patch is not None:
            _interpolate_device_states(
                self.sequence.patch,
                self.old_device_states,
                resolved.device_values,
                factor,
            )

        self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0, 255).astype(np.uint8)
        self.backend.dmx.set_levels()
