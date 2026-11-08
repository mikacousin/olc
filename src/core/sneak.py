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

from gi.repository import GLib

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


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

    def __init__(self, app: CoreApplication) -> None:
        self.app = app
        self._channel_fades: dict[int, ChannelSneakFade] = {}
        self._inde_fades: dict[int, IndependentSneakFade] = {}
        self._timer_id: int | None = None

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

    def get_channel_background_level(self, channel: int) -> int:
        """Calculate the underlying target background level for a channel (1-indexed).

        Takes into account sequential playback, active faders, and independents.
        """
        backend = getattr(self.app, "backend", None)
        if not backend or not getattr(backend, "dmx", None):
            return 0
        idx = channel - 1
        seq_lvl = 0
        if "sequence" in backend.dmx.levels and idx < len(
            backend.dmx.levels["sequence"]
        ):
            seq_lvl = int(backend.dmx.levels["sequence"][idx])
        fader_lvl = 0
        if "faders" in backend.dmx.levels and idx < len(backend.dmx.levels["faders"]):
            fader_lvl = int(backend.dmx.levels["faders"][idx])
        inde_lvl = 0
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow and getattr(lightshow, "independents", None):
            if idx < len(lightshow.independents.dmx):
                inde_lvl = int(round(lightshow.independents.dmx[idx]))
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
        if not backend or not getattr(backend, "dmx", None):
            return []

        user_levels = backend.dmx.levels.get("user")
        if user_levels is None:
            return []

        if duration is None:
            duration = self.get_default_sneak_time()

        now = time.monotonic()
        target_channels: list[int] = []

        if channels is None:
            # All channels currently having an override (user != -1)
            for idx, lvl in enumerate(user_levels):
                if lvl != -1:
                    target_channels.append(idx + 1)
        else:
            for ch in channels:
                if 1 <= ch <= len(user_levels):
                    target_channels.append(ch)

        if not target_channels:
            return []

        # If duration is 0 or negative, immediate cut
        if duration <= 0.0:
            for ch in target_channels:
                self._channel_fades.pop(ch, None)
                user_levels[ch - 1] = -1
            backend.dmx.set_levels()
            self._emit_updated(target_channels)
            return target_channels

        for ch in target_channels:
            current_lvl = int(user_levels[ch - 1])
            if current_lvl == -1:
                current_lvl = self.get_channel_background_level(ch)
            bg_lvl = self.get_channel_background_level(ch)
            self._channel_fades[ch] = ChannelSneakFade(
                channel=ch,
                start_level=float(current_lvl),
                target_level=float(bg_lvl),
                duration=duration,
                start_time=now,
            )

        self._ensure_timer()
        return target_channels

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
            self._timer_id = GLib.timeout_add(20, self._on_tick)

    def _check_timer(self) -> None:
        if not self._channel_fades and not self._inde_fades:
            if self._timer_id is not None:
                GLib.source_remove(self._timer_id)
                self._timer_id = None

    def _on_tick(self) -> bool:
        """Timer callback running at 50Hz (20ms interval)."""
        now = time.monotonic()
        finished_channels: list[int] = []
        backend = getattr(self.app, "backend", None)
        user_levels = (
            backend.dmx.levels.get("user") if backend and backend.dmx else None
        )

        if user_levels is not None:
            for ch, fade in list(self._channel_fades.items()):
                elapsed = now - fade.start_time
                fraction = (
                    min(1.0, elapsed / fade.duration) if fade.duration > 0 else 1.0
                )
                curr_val = round(
                    fade.start_level + (fade.target_level - fade.start_level) * fraction
                )
                if fraction >= 1.0:
                    user_levels[ch - 1] = -1
                    finished_channels.append(ch)
                    self._channel_fades.pop(ch, None)
                else:
                    user_levels[ch - 1] = int(curr_val)

        finished_indes: list[int] = []
        lightshow = getattr(self.app, "lightshow", None)
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

        self._emit_updated(list(self._channel_fades.keys()) + finished_channels)

        if not self._channel_fades and not self._inde_fades:
            self._timer_id = None
            return False
        return True

    def _emit_updated(self, channels: list[int]) -> None:
        if hasattr(self.app, "emit"):
            self.app.emit("dmx.updated")
            self.app.emit("channels.updated", channels)
