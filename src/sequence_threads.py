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
"""Background execution threads and state interpolation for sequence playback."""

from __future__ import annotations

import threading
import time
import typing
from typing import Optional

import numpy as np

from olc.core.tracking import DEFAULT_MIB_FADE_TIME, TrackingEngine
from olc.define import MAX_CHANNELS
from olc.step import Step, get_parameter_family

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.patch import PatchManager
    from olc.sequence import Sequence


def get_cue(step: Step) -> typing.Any:  # noqa: ANN401
    """Get the cue object from step as Any to simplify type checking."""
    return step.cue


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
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
            self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
            user_levels = self.backend.dmx.levels.get("user")
            if user_levels is not None:
                user_mask = user_levels != -1
                self.old_channels_levels[user_mask] = user_levels[user_mask]
        else:
            self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
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

    def _sync_dmx_levels(self) -> None:
        """Push final levels to DMX while preserving user overrides."""
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and self.backend.dmx is not None
        ):
            self.backend.dmx.set_levels()

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
        if (
            self.backend
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
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

        self._sync_dmx_levels()

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
                self._stopevent.wait(0.05)

        if self._stopevent.is_set():
            return

        self._finalize_go()

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()
        self.pause.set()

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

        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
            self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0.0, 255.0)
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

        for dev_id, mib_params in resolved.mib_parameters.items():
            has_non_explicit = any(
                not step.has_explicit_family_timing(get_parameter_family(p))
                for p in mib_params
            )
            if not has_non_explicit:
                continue
            if self._was_device_lit(dev_id):
                t_dark_ms = self._get_device_dark_time_ms(step, dev_id)
                if i < t_dark_ms:
                    factor = 0.0
                elif mib_dur_ms <= 0:
                    factor = 1.0
                else:
                    factor = max(0.0, min(1.0, (i - t_dark_ms) / mib_dur_ms))
            else:
                factor = ltp_factor
            mib_factors[dev_id] = factor

        for dev_id in getattr(self.sequence.patch, "devices", {}):
            if (
                self.override_time is None
                and step.channel_time
                and dev_id in step.channel_time
            ):
                ct = step.channel_time[dev_id]
                intensity_out_factors[dev_id] = _window_factor(ct.delay, ct.time)
            else:
                intensity_out_factors[dev_id] = default_out_factor

        return (
            ltp_factor,
            mib_factors,
            intensity_out_factors,
            family_factors,
            explicit_families,
        )

    def _calculate_transitions_go(  # pylint: disable=too-many-locals
        self,
        i: float,
        step: Step,
    ) -> np.ndarray:
        """Calculate channels levels transitions for Go"""
        old_levels = self.old_channels_levels.astype(np.float64)
        next_step_idx = self.sequence.position + 1
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            next_step_idx,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        next_levels = resolved.channels.astype(np.float64)

        if self.override_time is not None:
            time_in = self.override_time * 1000.0
            time_out = self.override_time * 1000.0
            delay_in = 0.0
            delay_out = 0.0
        else:
            time_in = step.time_in * 1000
            time_out = step.time_out * 1000
            delay_in = step.delay_in * 1000
            delay_out = step.delay_out * 1000

        # Precompute progression factors
        factor_in = (
            max(0.0, min(1.0, (i - delay_in - self.wait) / time_in))
            if time_in > 0
            else (1.0 if (i - delay_in - self.wait) >= 0 else 0.0)
        )
        factor_out = (
            max(0.0, min(1.0, (i - delay_out - self.wait) / time_out))
            if time_out > 0
            else (1.0 if (i - delay_out - self.wait) >= 0 else 0.0)
        )

        # Vectorized calculation for In, Out and Stationary channels
        diff = next_levels - old_levels
        factors = np.where(diff > 0, factor_in, factor_out)
        lvls = old_levels + diff * factors

        # Interpolate multi-parameter device values
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
        old_levels = self.old_channels_levels.astype(np.float64)
        next_step_idx = self.sequence.position + 1
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            next_step_idx,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        next_levels = resolved.channels.astype(np.float64)
        for channel, ct in step.channel_time.items():
            o_lvl = old_levels[channel - 1]
            n_lvl = next_levels[channel - 1]
            if n_lvl < o_lvl:  # Decay
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = o_lvl - abs((n_lvl - o_lvl) * factor)
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl
            elif n_lvl > o_lvl:  # Attack
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = (n_lvl - o_lvl) * factor + o_lvl
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl


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
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
            self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
            user_levels = self.backend.dmx.levels.get("user")
            if user_levels is not None:
                user_mask = user_levels != -1
                self.old_channels_levels[user_mask] = user_levels[user_mask]
        else:
            self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = _capture_device_states(self.sequence.patch)

    def _sync_dmx_levels(self) -> None:
        """Push final levels to DMX while preserving user overrides."""
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and self.backend.dmx is not None
        ):
            self.backend.dmx.set_levels()

    def _finalize_goback(self, prev_step: int) -> None:
        """Finish load cue after sequence transition"""
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            prev_step,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )

        # Block-copy levels to sequential dmx levels
        if (
            self.backend
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
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
        self._sync_dmx_levels()

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
                self._stopevent.wait(0.05)
                i = (time.time() * 1000) - (start_time + pause_time)

        if self._stopevent.is_set():
            return

        self._finalize_goback(prev_step)

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()
        self.pause.set()

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
        old_levels = self.old_channels_levels.astype(np.float64)
        next_levels = resolved.channels.astype(np.float64)
        factor = i / go_back_time if go_back_time > 0 else 1.0
        diff = (next_levels - old_levels) * factor
        lvls = old_levels + diff

        if resolved.device_values and self.sequence.patch is not None:
            _interpolate_device_states(
                self.sequence.patch,
                self.old_device_states,
                resolved.device_values,
                factor,
            )

        self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0.0, 255.0)
        self.backend.dmx.set_levels()
