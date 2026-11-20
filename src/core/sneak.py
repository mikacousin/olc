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
"""Sneak controller for gradual release of manual overrides and independents."""

from __future__ import annotations

import time
import typing
from dataclasses import dataclass

from olc.core.scheduler import ThreadingScheduler, TimerScheduler
from olc.core.tracking import DEFAULT_PHYSICAL_VALUES, TrackingEngine
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType
from olc.show.sequence_threads import (
    _capture_device_states,
    _emit_device_changes,
    _has_device_changed,
    _interpolate_device_states,
    _snapshot_dev_diff_state,
)
from olc.show.step import get_parameter_family

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication

_PARAM_ALIASES: dict[str, tuple[str, ...]] = {
    "color": ("color", "colour"),
    "colour": ("color", "colour"),
    "cct": ("cct", "color_temp", "colortemp"),
    "color_temp": ("cct", "color_temp", "colortemp"),
    "colortemp": ("cct", "color_temp", "colortemp"),
    "strobe": ("strobe", "shutter"),
    "shutter": ("strobe", "shutter"),
    "gobo": ("gobo", "gobo_wheel"),
    "gobo_wheel": ("gobo", "gobo_wheel"),
}

_PARAM_TO_CTYPE: dict[str, ChannelType] = {
    "pan": ChannelType.PAN,
    "tilt": ChannelType.TILT,
    "zoom": ChannelType.ZOOM,
    "focus": ChannelType.FOCUS,
    "iris": ChannelType.IRIS,
    "strobe": ChannelType.STROBE,
    "shutter": ChannelType.STROBE,
    "cct": ChannelType.COLOR_TEMP,
    "color_temp": ChannelType.COLOR_TEMP,
    "colortemp": ChannelType.COLOR_TEMP,
}


@dataclass
class DeviceSneakFade:
    """Active sneak fade interpolation state for non-intensity device attributes."""

    channel: int
    start_state: dict[str, typing.Any]
    target_values: dict[str, typing.Any]
    duration: float
    start_time: float


@dataclass
class ChannelSneakFade:
    """Active sneak fade interpolation state for a single channel."""

    channel: int  # 1-indexed
    start_level: float
    target_level: float
    duration: float
    start_time: float


@dataclass
class IndependentSneakFade:
    """Active sneak fade interpolation state for a single independent."""

    number: int  # 1-indexed
    start_level: float
    target_level: float
    duration: float
    start_time: float


class SneakController:
    """Manages timed gradual release (Sneak) of manual overrides and independents."""

    def __init__(
        self, app: CoreApplication, scheduler: TimerScheduler | None = None
    ) -> None:
        self.app = app
        self._scheduler: TimerScheduler = (
            scheduler if scheduler is not None else ThreadingScheduler()
        )
        self._channel_fades: dict[int, ChannelSneakFade] = {}
        self._device_fades: dict[int, DeviceSneakFade] = {}
        self._inde_fades: dict[int, IndependentSneakFade] = {}
        self._timer_id: typing.Any = None

    def get_default_sneak_time(self) -> float:
        """Return default sneak time from settings or 5.0 seconds."""
        settings = getattr(self.app, "settings", None)
        if settings is not None and hasattr(settings, "get_double"):
            try:
                val = float(settings.get_double("sneak-time"))
                if val >= 0.0:
                    return val
            except Exception:  # pylint: disable=broad-except
                pass
        return 5.0

    def get_channel_background_level(self, channel: int) -> float:
        """Calculate the underlying target background level [0.0..1.0] for a channel.

        Takes into account sequential playback, active faders, and independents.
        """
        backend = getattr(self.app, "backend", None)
        if not backend or not getattr(backend, "dmx", None):
            return 0.0
        idx = channel - 1
        seq_lvl = 0.0
        if "sequence" in backend.dmx.levels and idx < len(
            backend.dmx.levels["sequence"]
        ):
            seq_lvl = float(backend.dmx.levels["sequence"][idx])
        fader_lvl = 0.0
        if "faders" in backend.dmx.levels and idx < len(backend.dmx.levels["faders"]):
            fader_lvl = float(backend.dmx.levels["faders"][idx])
        inde_lvl = 0.0
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow and getattr(lightshow, "independents", None):
            if idx < len(lightshow.independents.dmx):
                inde_lvl = float(lightshow.independents.dmx[idx])
        return max(seq_lvl, fader_lvl, inde_lvl)

    def cancel_channel(self, channel: int) -> None:
        """Cancel an in-progress sneak fade on a specific channel."""
        self._channel_fades.pop(channel, None)
        self._check_timer()

    def cancel_independent(self, number: int) -> None:
        """Cancel an in-progress sneak fade on an independent."""
        self._inde_fades.pop(number, None)
        self._check_timer()

    def sneak_channels(
        self,
        channels: list[int] | None = None,
        duration: float | None = None,
    ) -> list[int]:
        """Start a sneak fade on specified channels (or all manual channels).

        Args:
            channels: List of 1-indexed channel numbers, or None for all
                manual channels.
            duration: Fade time in seconds (None uses settings default).

        Returns:
            List of affected channel numbers.
        """
        backend = getattr(self.app, "backend", None)
        dmx = getattr(backend, "dmx", None) if backend is not None else None
        if not dmx:
            return []

        user_levels = dmx.levels.get("user")
        if user_levels is None:
            return []

        if duration is None:
            duration = self.get_default_sneak_time()

        now = time.monotonic()
        live_state = getattr(self.app, "live_state", None)
        lightshow = getattr(self.app, "lightshow", None)
        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        target_channels: list[int] = []

        if channels is None:
            seen: set[int] = {
                idx + 1 for idx, lvl in enumerate(user_levels) if lvl >= 0.0
            }
            if live_state is not None:
                seen.update(
                    ch
                    for ch in live_state.get_manual_channels()
                    if 1 <= ch <= len(user_levels)
                )
            target_channels = sorted(seen)
        else:
            for ch in channels:
                if 1 <= ch <= len(user_levels):
                    target_channels.append(ch)

        if not target_channels:
            return []

        # If duration is 0 or negative, immediate cut
        if duration <= 0.0:
            changed_devs: set[int] = set()
            color_devs: set[int] = set()
            for ch in target_channels:
                self._channel_fades.pop(ch, None)
                self._device_fades.pop(ch, None)
                user_levels[ch - 1] = -1.0
                if live_state is not None and patch is not None:
                    manual_params = live_state.get_manual_params(ch)
                    non_int = {
                        p for p in manual_params if str(p).lower() != "intensity"
                    }
                    dev = patch.get_device(ch) if non_int else None
                    if dev is not None and non_int:
                        targets, home_fams = self._resolve_device_sneak_targets(
                            ch, non_int
                        )
                        before = _snapshot_dev_diff_state(dev)
                        if home_fams and hasattr(dev, "home"):
                            dev.home(home_fams)
                        if targets and hasattr(dev, "apply_device_values"):
                            dev.apply_device_values(targets)
                        any_moved, col_moved = _has_device_changed(
                            before,
                            dev,
                            touched_color_param=(
                                "color" in home_fams
                                or any(
                                    get_parameter_family(str(k)) == "color"
                                    for k in targets
                                )
                            ),
                        )
                        if any_moved:
                            changed_devs.add(ch)
                            if col_moved:
                                color_devs.add(ch)
                if live_state is not None:
                    live_state.clear_channel(ch)
            dmx.set_levels()
            _emit_device_changes(self.app, changed_devs, color_devs)
            self._emit_updated(target_channels)
            return target_channels

        dev_start_states = _capture_device_states(patch) if patch is not None else {}
        for ch in target_channels:
            current_lvl = float(user_levels[ch - 1])
            if current_lvl >= 0.0:
                bg_lvl = self.get_channel_background_level(ch)
                self._channel_fades[ch] = ChannelSneakFade(
                    channel=ch,
                    start_level=current_lvl,
                    target_level=bg_lvl,
                    duration=duration,
                    start_time=now,
                )
            if live_state is not None and patch is not None:
                manual_params = live_state.get_manual_params(ch)
                non_int = {p for p in manual_params if str(p).lower() != "intensity"}
                if non_int and patch.get_device(ch) is not None:
                    targets, _ = self._resolve_device_sneak_targets(ch, non_int)
                    if targets:
                        self._device_fades[ch] = DeviceSneakFade(
                            channel=ch,
                            start_state=dev_start_states.get(ch, {}),
                            target_values=targets,
                            duration=duration,
                            start_time=now,
                        )

        self._ensure_timer()
        return target_channels

    def _resolve_device_sneak_targets(
        self,
        channel: int,
        manual_params: set[str],
    ) -> tuple[dict[str, typing.Any], set[str]]:
        """Resolve cue background or home targets for manual non-intensity params."""
        lightshow = getattr(self.app, "lightshow", None)
        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        dev = patch.get_device(channel) if patch is not None else None
        if dev is None:
            return {}, set()

        cue_params: dict[str, typing.Any] = {}
        main_pb = (
            getattr(lightshow, "main_playback", None) if lightshow is not None else None
        )
        steps = getattr(main_pb, "steps", None) if main_pb is not None else None
        pos = getattr(main_pb, "position", -1) if main_pb is not None else -1
        if isinstance(steps, list) and 0 <= pos < len(steps):
            resolved = TrackingEngine.resolve_step_state(
                main_pb,
                pos,
                tracking_mode=bool(getattr(main_pb, "tracking_mode", False)),
                patch=patch,
            )
            cue_params = dict(resolved.device_values.get(channel, {}))

        emitter_names = {ct.value for ct in COLOR_CHANNEL_TYPES}
        targets: dict[str, typing.Any] = {}
        home_families: set[str] = set()

        for raw_param in sorted(manual_params):
            p_low = str(raw_param).lower()
            if p_low == "intensity":
                continue

            found_cue_key: str | None = None
            for cand in (p_low, *_PARAM_ALIASES.get(p_low, ())):
                if cand in cue_params:
                    found_cue_key = cand
                    break
            if found_cue_key is None and p_low in emitter_names:
                for cand in ("color", "colour"):
                    if cand in cue_params:
                        found_cue_key = cand
                        break

            if found_cue_key is not None:
                targets[found_cue_key] = cue_params[found_cue_key]
                continue

            home_families.add(get_parameter_family(p_low))
            if p_low in ("color", "colour") or p_low in emitter_names:
                if getattr(dev, "is_subtractive_cmy", False):
                    targets["color"] = "#ffffff"
                else:
                    any_def_255 = any(
                        c.channel_type in COLOR_CHANNEL_TYPES and c.default_value > 0
                        for c in getattr(dev, "channels", ())
                    )
                    targets["color"] = "#ffffff" if any_def_255 else "#000000"
            elif p_low in _PARAM_TO_CTYPE:
                ctype = _PARAM_TO_CTYPE[p_low]
                coarse = dev.get_channel(ctype) if hasattr(dev, "get_channel") else None
                if coarse is not None:
                    norm_def = coarse.default_value / 255.0
                    targets[p_low] = coarse.physical_min + norm_def * (
                        coarse.physical_max - coarse.physical_min
                    )
                else:
                    targets[p_low] = DEFAULT_PHYSICAL_VALUES.get(p_low, 0.0)
            else:
                try:
                    ctype = ChannelType(p_low)
                except ValueError:
                    continue
                ch_obj = dev.get_channel(ctype) if hasattr(dev, "get_channel") else None
                targets[p_low] = (
                    ch_obj.default_value / 255.0 if ch_obj is not None else 0.0
                )

        return targets, home_families

    def sneak_independents(
        self,
        numbers: list[int] | None = None,
        duration: float | None = None,
    ) -> list[int]:
        """Start a sneak fade on specified independents (fades master level to 0.0).

        Args:
            numbers: List of 1-indexed independent numbers, or None for all active.
            duration: Fade time in seconds (None uses settings default).

        Returns:
            List of affected independent numbers.
        """
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow or not getattr(lightshow, "independents", None):
            return []

        if duration is None:
            duration = self.get_default_sneak_time()

        now = time.monotonic()
        target_numbers: list[int] = []

        all_indes = lightshow.independents.independents
        if numbers is None:
            for inde in all_indes:
                if inde.level > 0.0:
                    target_numbers.append(inde.number)
        else:
            for num in numbers:
                if 1 <= num <= len(all_indes):
                    target_numbers.append(num)

        if not target_numbers:
            return []

        if duration <= 0.0:
            for num in target_numbers:
                self._inde_fades.pop(num, None)
                all_indes[num - 1].set_level(0.0, cancel_sneak=False)
            return target_numbers

        for num in target_numbers:
            inde = all_indes[num - 1]
            self._inde_fades[num] = IndependentSneakFade(
                number=num,
                start_level=float(inde.level),
                target_level=0.0,
                duration=duration,
                start_time=now,
            )

        self._ensure_timer()
        return target_numbers

    def _ensure_timer(self) -> None:
        if self._timer_id is None:
            self._timer_id = self._scheduler.timeout_add(20, self._on_tick)

    def _check_timer(self) -> None:
        if not self._channel_fades and not self._device_fades and not self._inde_fades:
            if self._timer_id is not None:
                self._scheduler.source_remove(self._timer_id)
                self._timer_id = None

    def _on_tick(self) -> bool:
        """Timer callback running at 50Hz (20ms interval)."""
        now = time.monotonic()
        finished_channels: list[int] = []
        backend = getattr(self.app, "backend", None)
        user_levels = (
            backend.dmx.levels.get("user") if backend and backend.dmx else None
        )
        live_state = getattr(self.app, "live_state", None)

        if user_levels is not None:
            for ch, fade in list(self._channel_fades.items()):
                elapsed = now - fade.start_time
                fraction = (
                    min(1.0, elapsed / fade.duration) if fade.duration > 0 else 1.0
                )
                curr_val = (
                    fade.start_level + (fade.target_level - fade.start_level) * fraction
                )
                if fraction >= 1.0:
                    user_levels[ch - 1] = -1.0
                    finished_channels.append(ch)
                    self._channel_fades.pop(ch, None)
                else:
                    user_levels[ch - 1] = curr_val

        lightshow = getattr(self.app, "lightshow", None)
        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        changed_devs: set[int] = set()
        color_devs: set[int] = set()
        for ch, dev_fade in list(self._device_fades.items()):
            elapsed = now - dev_fade.start_time
            fraction = (
                min(1.0, elapsed / dev_fade.duration) if dev_fade.duration > 0 else 1.0
            )
            col_chg: set[int] = set()
            changed = _interpolate_device_states(
                patch,
                {ch: dev_fade.start_state},
                {ch: dev_fade.target_values},
                fraction,
                color_changed_out=col_chg,
            )
            changed_devs.update(changed)
            color_devs.update(col_chg)
            if fraction >= 1.0:
                finished_channels.append(ch)
                self._device_fades.pop(ch, None)

        if live_state is not None:
            for ch in finished_channels:
                if ch not in self._channel_fades and ch not in self._device_fades:
                    live_state.clear_channel(ch)

        finished_indes: list[int] = []
        all_indes = (
            lightshow.independents.independents
            if lightshow and lightshow.independents
            else []
        )

        for num, fade in list(self._inde_fades.items()):
            if 1 <= num <= len(all_indes):
                inde = all_indes[num - 1]
                elapsed = now - fade.start_time
                fraction = (
                    min(1.0, elapsed / fade.duration) if fade.duration > 0 else 1.0
                )
                curr_val = fade.start_level * (1.0 - fraction)
                if fraction >= 1.0:
                    inde.set_level(0.0, cancel_sneak=False)
                    finished_indes.append(num)
                    self._inde_fades.pop(num, None)
                else:
                    inde.set_level(curr_val, cancel_sneak=False)

        if backend and backend.dmx:
            backend.dmx.set_levels()

        _emit_device_changes(self.app, changed_devs, color_devs)
        notified_channels = sorted(
            set(self._channel_fades.keys())
            | set(self._device_fades.keys())
            | set(finished_channels)
        )
        self._emit_updated(notified_channels)

        if not self._channel_fades and not self._device_fades and not self._inde_fades:
            self._timer_id = None
            return False
        return True

    def _emit_updated(self, channels: list[int]) -> None:
        if hasattr(self.app, "emit"):
            self.app.emit("dmx.updated")
            self.app.emit("channels.updated", channels)
