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

import numpy as np

from olc.core.tracking import DEFAULT_MIB_FADE_TIME, ResolvedState, TrackingEngine
from olc.sequence import _capture_device_states, _interpolate_device_states, get_cue

if typing.TYPE_CHECKING:
    from olc.step import Step


class Scale:
    """For crossfade faders with normalized [0.0..1.0] internal representation."""

    def __init__(self) -> None:
        self.value: float = 0.0
        self.moved = False

    def set_value(self, value: int | float) -> None:
        """Set scale value.

        Accepts either normalized float [0.0..1.0] or 8-bit integer [0..255].
        Values > 1.0 are automatically normalized by dividing by 255.0.

        Args:
            value: int | float
        """
        val = float(value)
        if val > 1.0:
            norm_val = max(0.0, min(1.0, val / 255.0))
        else:
            norm_val = max(0.0, min(1.0, val))
        self.value = norm_val

    def get_value(self) -> float:
        """Return normalized scale value [0.0..1.0].

        Returns:
            float in range [0.0..1.0]
        """
        return self.value

    @property
    def value_255(self) -> int:
        """Return scale value as 8-bit integer [0..255] for legacy UI widgets."""
        return round(self.value * 255.0)


class CrossFade:
    """For Manual Crossfade"""

    def __init__(self, app: typing.Any) -> None:  # noqa: ANN401
        self.app = app
        self.scale_a = Scale()
        self.scale_b = Scale()

        self.manual = False
        self._start_device_states: dict[int, dict[str, typing.Any]] | None = None
        self._start_channels: np.ndarray | None = None

    def _get_next_step_idx(self) -> int:
        """Return the target step index for the current transition."""
        main_pb = self.app.core.lightshow.main_playback
        next_step = main_pb.position + 1
        if next_step >= main_pb.last - 1:
            return 0
        return next_step

    def _resolve_step(self, step_idx: int) -> ResolvedState:
        """Resolve full sequential state for step_idx via TrackingEngine."""
        main_pb = self.app.core.lightshow.main_playback
        return TrackingEngine.resolve_step_state(
            main_pb,
            step_idx,
            tracking_mode=main_pb.tracking_mode,
            patch=main_pb.patch,
        )

    def _ensure_start_state(self) -> None:
        """Capture baseline conventional and device states when manual fade starts."""
        main_pb = self.app.core.lightshow.main_playback
        if self._start_channels is None:
            resolved_curr = self._resolve_step(main_pb.position)
            self._start_channels = resolved_curr.channels.astype(np.int32)
        if self._start_device_states is None:
            self._start_device_states = _capture_device_states(main_pb.patch)

    def _reset_start_state(self) -> None:
        """Clear cached baseline states after transition completion or cancel."""
        self._start_device_states = None
        self._start_channels = None

    def _takeover_background_thread(self, main_pb: typing.Any) -> None:  # noqa: ANN401
        """Stop background Go/GoBack transition and inherit its baseline states."""
        if not (self.manual and main_pb.thread and main_pb.thread.is_alive()):
            return

        if getattr(main_pb.thread, "old_device_states", None):
            self._start_device_states = dict(main_pb.thread.old_device_states)
        if getattr(main_pb.thread, "old_channels_levels", None) is not None:
            self._start_channels = main_pb.thread.old_channels_levels.astype(np.int32)

        main_pb.thread.stop()
        main_pb.thread.join(timeout=1.0)
        main_pb.thread = None

        if self.app is not None:
            if getattr(self.app, "midi", None) is not None:
                self.app.midi.button_off("playback.pause")
                self.app.midi.button_off("playback.go")
            core = getattr(self.app, "core", self.app)
            if hasattr(core, "action_registry"):
                core.action_registry.trigger_feedback("playback.pause")
                core.action_registry.trigger_feedback("playback.go")
            if hasattr(core, "emit"):
                core.emit(
                    "playback.pause_triggered",
                    {"active": False, "label": "PAUSE"},
                )

    def scale_moved(self, scale: Scale) -> None:
        """On moved

        Args:
            scale: Scale object
        """
        scale.moved = True
        level = scale.get_value()
        main_pb = self.app.core.lightshow.main_playback

        self._takeover_background_thread(main_pb)

        if level > 0.0 and level < 1.0:
            main_pb.on_go = True

        if scale in (self.scale_a, self.scale_b):
            if main_pb.last == 0:
                # If sequential is empty, don't do anything
                main_pb.on_go = False
                return
            self._ensure_start_state()
            # Update sliders position
            self.update_slider(scale, level)

        if (
            self.scale_a.get_value() >= 1.0
            and self.scale_b.get_value() >= 1.0
            and self.scale_a.moved
            and self.scale_b.moved
        ):
            # In and Out Crossfades at Full
            self.at_full()

        if self.scale_a.get_value() <= 0.0 and self.scale_b.get_value() <= 0.0:
            # Stop crossfade if return to 0
            if not main_pb.on_go:
                return
            self.scale_a.moved = False
            self.scale_b.moved = False
            self.manual = False
            main_pb.on_go = False
            self._reset_start_state()

    def at_full(self) -> None:
        """Slider A and B at Full"""
        main_pb = self.app.core.lightshow.main_playback
        if not main_pb.on_go:
            return
        self.scale_a.moved = False
        self.scale_b.moved = False
        self.manual = False
        main_pb.on_go = False
        self._reset_start_state()

        target_step_idx = self._get_next_step_idx()
        resolved = self._resolve_step(target_step_idx)

        if self.app.backend and self.app.backend.dmx:
            dmx = self.app.backend.dmx
            n_ch = min(len(dmx.levels["sequence"]), len(resolved.channels))
            dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]

        if main_pb.patch is not None:
            for dev_id, params in resolved.device_values.items():
                dev = main_pb.patch.get_device(dev_id)
                if dev is not None:
                    dev.apply_device_values(params)

        if self.app.backend and self.app.backend.dmx:
            self.app.backend.dmx.set_levels()

        main_pb.update_channels()
        # Go to next step
        next_step = main_pb.position + 1
        if next_step < main_pb.last - 1:
            # Next step
            main_pb.position += 1
            next_step += 1
        else:
            # Return to first step
            main_pb.position = 0
            next_step = 1
        # Update user interface
        cue = get_cue(main_pb.steps[main_pb.position]).number
        cue_text = main_pb.steps[main_pb.position].text
        next_cue = get_cue(main_pb.steps[next_step]).number
        subtitle = (
            f"Mem. :{cue} {cue_text} "
            f"- Next Mem. : {next_cue} "
            f"{main_pb.steps[next_step].text}"
        )
        self.app.core.emit("crossfade.at_full", next_step, subtitle)
        # If Wait
        if main_pb.steps[next_step].wait:
            main_pb.on_go = False
            self.app.core.action_registry.execute("playback.go")

    def update_slider(  # pylint: disable=too-many-locals
        self, scale: Scale, level: int | float
    ) -> None:
        """Update sliders position

        Args:
            scale: Scale object
            level: int or float
        """
        main_pb = self.app.core.lightshow.main_playback
        step_idx = main_pb.position + 1
        step = main_pb.steps[step_idx]
        total_time = step.total_time * 1000
        wait = step.wait * 1000
        norm_level = level / 255.0 if float(level) > 1.0 else float(level)
        position = norm_level * total_time

        self._update_ui_transition(scale, position, total_time, step_idx)

        if not (self.app.backend and self.app.backend.dmx):
            return

        self._ensure_start_state()
        target_step_idx = self._get_next_step_idx()
        resolved_next = self._resolve_step(target_step_idx)
        old_levels = (
            self._start_channels
            if self._start_channels is not None
            else self._resolve_step(main_pb.position).channels.astype(np.float64)
        )
        next_levels = resolved_next.channels.astype(np.float64)
        user_levels = self.app.backend.dmx.levels["user"]

        # Update levels
        if position >= wait or norm_level == 0.0:
            sequence_levels = self.app.backend.dmx.levels["sequence"]
            current_lvls = sequence_levels.astype(np.float64)

            # Keep non-transitioning channels at their resolved baseline
            stable_mask = (next_levels == old_levels) & (user_levels == -1)
            current_lvls[stable_mask] = old_levels[stable_mask]

            if scale == self.scale_a:
                lvls_a = self._calculate_scale_a(
                    position, step, old_levels, next_levels
                )
                decay_mask = (next_levels < old_levels) | (
                    (user_levels != -1) & (next_levels < user_levels)
                )
                current_lvls[decay_mask] = lvls_a[decay_mask]
            elif scale == self.scale_b:
                lvls_b = self._calculate_scale_b(
                    position, step, old_levels, next_levels
                )
                attack_mask = (next_levels > old_levels) | (
                    (user_levels != -1) & (next_levels > user_levels)
                )
                current_lvls[attack_mask] = lvls_b[attack_mask]

            sequence_levels[:] = np.clip(current_lvls, 0.0, 255.0)
            self._update_devices_crossfade(step, resolved_next, old_levels, total_time)
            self.app.backend.dmx.set_levels()

    def _update_devices_crossfade(  # pylint: disable=too-many-locals
        self,
        step: Step,
        resolved: ResolvedState,
        old_levels: np.ndarray,
        total_time: float,
    ) -> None:
        """Interpolate multi-parameter devices according to scale_a and scale_b."""
        main_pb = self.app.core.lightshow.main_playback
        if main_pb.patch is None or not resolved.device_values:
            return

        pos_a = self.scale_a.get_value() * total_time
        pos_b = self.scale_b.get_value() * total_time
        wait_ms = step.wait * 1000.0
        start_states = self._start_device_states or {}

        def _window_factor(pos_ms: float, delay_s: float, time_s: float) -> float:
            start_ms = wait_ms + delay_s * 1000.0
            dur_ms = time_s * 1000.0
            if dur_ms <= 0:
                return 1.0 if pos_ms >= start_ms else 0.0
            return max(0.0, min(1.0, (pos_ms - start_ms) / dur_ms))

        ltp_factor = _window_factor(pos_b, step.delay_in, step.time_in)
        default_out_factor = _window_factor(pos_a, step.delay_out, step.time_out)
        family_factors: dict[str, float] = {
            "position": _window_factor(
                pos_b, step.effective_delay_position, step.effective_time_position
            ),
            "color": _window_factor(
                pos_b, step.effective_delay_color, step.effective_time_color
            ),
            "beam": _window_factor(
                pos_b, step.effective_delay_beam, step.effective_time_beam
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
            float(getattr(main_pb, "mib_fade_time", DEFAULT_MIB_FADE_TIME)) * 1000.0,
        )

        for dev_id in resolved.device_values:
            if step.channel_time and dev_id in step.channel_time:
                ct = step.channel_time[dev_id]
                intensity_out_factors[dev_id] = _window_factor(pos_a, ct.delay, ct.time)
                t_dark_ms = wait_ms + (ct.delay + ct.time) * 1000.0
            else:
                intensity_out_factors[dev_id] = default_out_factor
                t_dark_ms = wait_ms + (step.delay_out + step.time_out) * 1000.0

            if dev_id in resolved.mib_parameters and resolved.mib_parameters[dev_id]:
                was_lit = (
                    1 <= dev_id <= len(old_levels) and int(old_levels[dev_id - 1]) > 0
                ) or float(start_states.get(dev_id, {}).get("intensity", 0.0)) > 0.0
                if was_lit:
                    if pos_a < t_dark_ms:
                        mib_factors[dev_id] = 0.0
                    elif mib_dur_ms <= 0:
                        mib_factors[dev_id] = 1.0
                    else:
                        mib_factors[dev_id] = max(
                            0.0, min(1.0, (pos_a - t_dark_ms) / mib_dur_ms)
                        )
                elif step.channel_time and dev_id in step.channel_time:
                    ct = step.channel_time[dev_id]
                    mib_factors[dev_id] = _window_factor(pos_b, ct.delay, ct.time)
                else:
                    mib_factors[dev_id] = ltp_factor

        _interpolate_device_states(
            main_pb.patch,
            start_states,
            resolved.device_values,
            ltp_factor,
            mib_factors=mib_factors,
            mib_parameters=resolved.mib_parameters,
            intensity_out_factors=intensity_out_factors,
            family_factors=family_factors,
            explicit_families=explicit_families,
        )

    def _update_ui_transition(
        self, scale: Scale, position: float, total_time: float, step: int
    ) -> None:
        """Emit scale update events to be handled by the UI bridge."""
        scale_name = "scale_a" if scale == self.scale_a else "scale_b"
        self.app.core.emit(
            "crossfade.scale_updated", scale_name, position, total_time, step
        )

    def _resolve_endpoints(self) -> tuple[np.ndarray, np.ndarray]:
        """Resolve old_levels and next_levels arrays for conventional channels."""
        main_pb = self.app.core.lightshow.main_playback
        old_levels = (
            self._start_channels
            if self._start_channels is not None
            else self._resolve_step(main_pb.position).channels.astype(np.float64)
        )
        next_levels = self._resolve_step(self._get_next_step_idx()).channels.astype(
            np.float64
        )
        return old_levels, next_levels

    def _apply_channel_times_a(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        lvls: np.ndarray,
        position: float,
        step: Step,
        old_levels: np.ndarray | None = None,
        next_levels: np.ndarray | None = None,
    ) -> None:
        """Apply individual channel times for decays."""
        if not step.channel_time:
            return
        if old_levels is None or next_levels is None:
            old_levels, next_levels = self._resolve_endpoints()

        wait = step.wait * 1000
        for channel, ct in step.channel_time.items():
            if next_levels[channel - 1] < old_levels[channel - 1]:
                if position < ct.delay * 1000 + wait:
                    lvl = old_levels[channel - 1]
                elif position < ct.delay * 1000 + ct.time * 1000 + wait:
                    factor = (position - ct.delay * 1000 - wait) / (ct.time * 1000)
                    lvl = old_levels[channel - 1] - abs(
                        (next_levels[channel - 1] - old_levels[channel - 1]) * factor
                    )
                else:
                    lvl = next_levels[channel - 1]
                lvls[channel - 1] = lvl

    def _calculate_scale_a(
        self,
        position: float,
        step: Step,
        old_levels: np.ndarray | None = None,
        next_levels: np.ndarray | None = None,
    ) -> np.ndarray:
        """Calculate fade levels for Scale A (decays)."""
        if old_levels is None or next_levels is None:
            old_levels, next_levels = self._resolve_endpoints()

        user_levels = self.app.backend.dmx.levels["user"]

        # Base levels (no fade or after delay)
        if position <= (step.wait + step.delay_out) * 1000:
            lvls = old_levels.copy()
        elif position < (step.time_out + step.wait + step.delay_out) * 1000:
            factor = (position - step.wait * 1000 - step.delay_out * 1000) / (
                step.time_out * 1000
            )
            # Decays (continuous floating-point)
            diff = (next_levels - old_levels) * factor
            lvls = old_levels - np.abs(diff)
            # User overrides
            user_mask = (user_levels != -1) & (next_levels < user_levels)
            if np.any(user_mask):
                val = user_levels - np.abs((next_levels - user_levels) * factor)
                lvls[user_mask] = val[user_mask]
        else:
            lvls = next_levels.copy()

        self._apply_channel_times_a(lvls, position, step, old_levels, next_levels)
        return lvls

    def _apply_channel_times_b(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        lvls: np.ndarray,
        position: float,
        step: Step,
        old_levels: np.ndarray | None = None,
        next_levels: np.ndarray | None = None,
    ) -> None:
        """Apply individual channel times for attacks."""
        if not step.channel_time:
            return
        if old_levels is None or next_levels is None:
            old_levels, next_levels = self._resolve_endpoints()

        wait = step.wait * 1000
        for channel, ct in step.channel_time.items():
            if next_levels[channel - 1] > old_levels[channel - 1]:
                if position < ct.delay * 1000 + wait:
                    lvl = old_levels[channel - 1]
                elif position < ct.delay * 1000 + ct.time * 1000 + wait:
                    factor = (position - ct.delay * 1000 - wait) / (ct.time * 1000)
                    lvl = (
                        next_levels[channel - 1] - old_levels[channel - 1]
                    ) * factor + old_levels[channel - 1]
                else:
                    lvl = next_levels[channel - 1]
                lvls[channel - 1] = lvl

    def _calculate_scale_b(
        self,
        position: float,
        step: Step,
        old_levels: np.ndarray | None = None,
        next_levels: np.ndarray | None = None,
    ) -> np.ndarray:
        """Calculate fade levels for Scale B (attacks)."""
        if old_levels is None or next_levels is None:
            old_levels, next_levels = self._resolve_endpoints()

        user_levels = self.app.backend.dmx.levels["user"]

        if position <= (step.wait + step.delay_in) * 1000:
            lvls = old_levels.copy()
        elif position < (step.time_in + step.wait + step.delay_in) * 1000:
            factor = (position - step.wait * 1000 - step.delay_in * 1000) / (
                step.time_in * 1000
            )
            # Attacks (continuous floating-point)
            diff = (next_levels - old_levels) * factor
            lvls = old_levels + diff
            # User overrides
            user_mask = (user_levels != -1) & (next_levels > user_levels)
            if np.any(user_mask):
                val = user_levels + (next_levels - user_levels) * factor
                lvls[user_mask] = val[user_mask]
        else:
            lvls = next_levels.copy()

        self._apply_channel_times_b(lvls, position, step, old_levels, next_levels)
        return lvls
