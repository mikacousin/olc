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
"""Cached NNLS color solver, wheel snapping, color fanning, and UI throttle."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from olc.devices.color import (
    SOLVER_STRATEGIES,
    ColorMatcher,
    FixtureColorProfile,
    MatchResult,
    delta_e76,
    sRGB,
)

from .conversions import (
    RGB,
    hs_to_rgb,
    parse_hex,
    rgb_to_hs,
    to_24bit,
    xy_max_luminance,
    xy_to_srgb,
)
from .geometry import effective_color_profile


def profile_signature(profile: FixtureColorProfile) -> tuple[Any, ...]:
    """Hashable identity of a color profile (profiles may be copied per device)."""
    return (
        profile.fixture_name,
        tuple(
            (e.name, round(e.cie.x, 5), round(e.cie.y, 5), round(e.cie.Y, 3))
            for e in profile.emitters
        ),
    )


class ColorSolver:
    """NNLS color matching with a per-profile cache.

    Targets retain full floating-point precision (keyed at 24-bit resolution)
    so that 8-bit, 16-bit, and 24-bit fixtures receive unquantized emitter
    ratios.
    """

    def __init__(self, max_entries: int = 2048, strategy: str = "spectral") -> None:
        self.max_entries = max_entries
        self.strategy = strategy if strategy in SOLVER_STRATEGIES else "spectral"
        self.solves = 0
        self._cache: dict[tuple[Any, ...], Optional[MatchResult]] = {}
        self._matchers: dict[tuple[Any, ...], ColorMatcher] = {}

    def solve(
        self,
        profile: FixtureColorProfile,
        r: float,
        g: float,
        b: float,
        strategy: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """Emitter levels reproducing sRGB (r, g, b) on ``profile``."""
        eff_strat = strategy if strategy is not None else self.strategy
        if eff_strat not in SOLVER_STRATEGIES:
            eff_strat = "spectral"
        r_n = max(0.0, min(1.0, float(r)))
        g_n = max(0.0, min(1.0, float(g)))
        b_n = max(0.0, min(1.0, float(b)))
        sig = profile_signature(profile)
        key = (sig, to_24bit(r_n), to_24bit(g_n), to_24bit(b_n), eff_strat)
        if key in self._cache:
            return self._cache[key]

        matcher = self._matchers.get(sig)
        if matcher is None:
            matcher = ColorMatcher([profile])
            self._matchers[sig] = matcher
        cie = sRGB(r_n, g_n, b_n).to_XYZ().to_xyY()
        result = matcher.match_cie(cie.x, cie.y, cie.Y, strategy=eff_strat).get(
            profile.fixture_name
        )
        self.solves += 1

        if len(self._cache) >= self.max_entries:
            self._cache.pop(next(iter(self._cache)))  # FIFO eviction
        self._cache[key] = result
        return result

    def solve_cie(
        self,
        profile: FixtureColorProfile,
        x: float,
        y: float,
        Y: Optional[float] = None,  # pylint: disable=invalid-name
        strategy: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """Emitter levels reproducing CIE (x, y, Y) on ``profile``."""
        eff_strat = strategy if strategy is not None else self.strategy
        if eff_strat not in SOLVER_STRATEGIES:
            eff_strat = "spectral"
        x_n = max(0.0, min(1.0, float(x)))
        y_n = max(0.0, min(1.0, float(y)))
        y_lum = max(0.0, float(Y)) if Y is not None else xy_max_luminance(x_n, y_n)
        sig = profile_signature(profile)
        key = (
            "cie",
            sig,
            to_24bit(x_n),
            to_24bit(y_n),
            to_24bit(y_lum / 100.0),
            eff_strat,
        )
        if key in self._cache:
            return self._cache[key]

        matcher = self._matchers.get(sig)
        if matcher is None:
            matcher = ColorMatcher([profile])
            self._matchers[sig] = matcher
        result = matcher.match_cie(x_n, y_n, y_lum, strategy=eff_strat).get(
            profile.fixture_name
        )
        self.solves += 1

        if len(self._cache) >= self.max_entries:
            self._cache.pop(next(iter(self._cache)))  # FIFO eviction
        self._cache[key] = result
        return result

    def clear(self) -> None:
        """Drop cached results (call when profiles are edited)."""
        self._cache.clear()
        self._matchers.clear()


# Standard dichroic color wheel slot name -> approximate sRGB (0.0..1.0)
WHEEL_SLOT_COLORS: dict[str, RGB] = {
    "open": (1.0, 1.0, 1.0),
    "white": (1.0, 1.0, 1.0),
    "red": (1.0, 0.0, 0.0),
    "deep red": (0.85, 0.0, 0.0),
    "green": (0.0, 1.0, 0.0),
    "deep green": (0.0, 0.75, 0.1),
    "blue": (0.0, 0.2, 1.0),
    "deep blue": (0.0, 0.05, 0.85),
    "light blue": (0.35, 0.75, 1.0),
    "yellow": (1.0, 0.95, 0.0),
    "amber": (1.0, 0.55, 0.0),
    "orange": (1.0, 0.35, 0.0),
    "cyan": (0.0, 1.0, 1.0),
    "aqua": (0.0, 0.9, 0.8),
    "magenta": (1.0, 0.0, 1.0),
    "pink": (1.0, 0.45, 0.75),
    "rose": (1.0, 0.3, 0.6),
    "purple": (0.6, 0.1, 1.0),
    "uv": (0.4, 0.0, 0.9),
    "congo": (0.25, 0.0, 0.75),
    "lavender": (0.75, 0.55, 1.0),
    "lime": (0.65, 1.0, 0.15),
    "cto": (1.0, 0.76, 0.48),
    "ctb": (0.72, 0.85, 1.0),
}


def _slot_label_to_rgb(label: str, description: str = "") -> Optional[RGB]:
    """Resolve a color wheel slot label or #RRGGBB description to sRGB."""
    for text in (description, label):
        if "#" in text:
            idx = text.index("#")
            candidate = text[idx : idx + 7]
            rgb = parse_hex(candidate)
            if rgb is not None:
                return rgb
    low = label.strip().lower()
    if low in WHEEL_SLOT_COLORS:
        return WHEEL_SLOT_COLORS[low]
    # Substring match (longest key first so 'deep blue' wins over 'blue')
    for key in sorted(WHEEL_SLOT_COLORS, key=len, reverse=True):
        if key in low:
            return WHEEL_SLOT_COLORS[key]
    return None


def extract_color_wheel_slots(device: object) -> list[tuple[Any, RGB]]:
    """Return [(ChannelRange, sRGB)] for a device's COLOR_WHEEL channel."""
    slots: list[tuple[Any, RGB]] = []
    for ch in getattr(device, "channels", ()):
        ct_val = getattr(getattr(ch, "channel_type", None), "value", None)
        if ct_val != "color_wheel":
            continue
        for rng in getattr(ch, "ranges", ()):
            rgb = _slot_label_to_rgb(
                str(getattr(rng, "label", "")),
                str(getattr(rng, "description", "")),
            )
            if rgb is not None:
                slots.append((rng, rgb))
    return slots


def snap_device_color_wheel(  # pylint: disable=too-many-locals
    device: object, r: float, g: float, b: float
) -> Optional[float]:
    """Snap a non-additive device's COLOR_WHEEL to the slot with minimum ΔE.

    Returns the resulting ΔE*76, or None if the device has no color wheel slots.
    """
    slots = extract_color_wheel_slots(device)
    if not slots:
        return None

    target_xyz = sRGB(
        max(0.0, min(1.0, float(r))),
        max(0.0, min(1.0, float(g))),
        max(0.0, min(1.0, float(b))),
    ).to_XYZ()

    best_rng = None
    best_rgb: RGB = (1.0, 1.0, 1.0)
    best_de = float("inf")
    for rng, slot_rgb in slots:
        slot_xyz = sRGB(*slot_rgb).to_XYZ()
        de = delta_e76(target_xyz, slot_xyz)
        if de < best_de:
            best_de = de
            best_rng = rng
            best_rgb = slot_rgb

    if best_rng is None:
        return None

    for ch in getattr(device, "channels", ()):
        ct_val = getattr(getattr(ch, "channel_type", None), "value", None)
        if ct_val == "color_wheel":
            ch.set_value(int(best_rng.activation_value))
            break

    # Update device's target color so reticles show the snapped slot color
    slot_srgb = sRGB(*best_rgb)
    dev_dict = getattr(device, "__dict__", None)
    if isinstance(dev_dict, dict):
        if "_target_color" in dev_dict:
            dev_dict["_target_color"] = slot_srgb
        if "_target_cie" in dev_dict:
            dev_dict["_target_cie"] = slot_srgb.to_XYZ().to_xyY()

    return float(best_de)


def shift_color_hs(
    rgb: RGB,
    delta_hue: float,
    delta_sat: float,
    hue_hint: float = 0.0,
) -> RGB:
    """Shift an sRGB color by (delta_hue, delta_sat) on the HS wheel."""
    h, s = rgb_to_hs(rgb[0], rgb[1], rgb[2], hue_hint=hue_hint)
    new_h = (h + float(delta_hue)) % 1.0
    new_s = max(0.0, min(1.0, s + float(delta_sat)))
    return hs_to_rgb(new_h, new_s)


def compute_color_fan(
    count: int,
    start_rgb: RGB,
    end_rgb: RGB,
    mode: str = "hs_short",
) -> list[RGB]:
    """Interpolate ``count`` colors between ``start_rgb`` and ``end_rgb``.

    Modes:
        - ``"hs_short"``: shortest angular path on the HS hue circle.
        - ``"hs_long"``: longest angular path (rainbow) on the HS hue circle.
        - ``"linear"``: linear interpolation in sRGB space.
    """
    if count <= 0:
        return []
    if count == 1:
        return [start_rgb]

    if mode == "linear":
        out: list[RGB] = []
        for idx in range(count):
            t = idx / (count - 1)
            out.append(
                (
                    start_rgb[0] + t * (end_rgb[0] - start_rgb[0]),
                    start_rgb[1] + t * (end_rgb[1] - start_rgb[1]),
                    start_rgb[2] + t * (end_rgb[2] - start_rgb[2]),
                )
            )
        return out

    h1, s1 = rgb_to_hs(*start_rgb)
    h2, s2 = rgb_to_hs(*end_rgb, hue_hint=h1)
    dh = (h2 - h1) % 1.0
    if mode == "hs_long":
        if abs(dh) < 1e-6:
            dh = 1.0 - (1.0 / count)
        elif dh < 0.5:
            dh -= 1.0
    else:  # hs_short
        if dh > 0.5:
            dh -= 1.0

    return [
        hs_to_rgb(
            (h1 + (idx / (count - 1)) * dh) % 1.0, s1 + (idx / (count - 1)) * (s2 - s1)
        )
        for idx in range(count)
    ]


@dataclass
class ColorApplyResult:
    """Outcome of applying one color to a set of devices."""

    delta_e: dict[int, float] = field(default_factory=dict)
    warnings: dict[int, str] = field(default_factory=dict)

    @property
    def mean_delta_e(self) -> float:
        """Average ΔE over matched devices (0 when none)."""
        if not self.delta_e:
            return 0.0
        return sum(self.delta_e.values()) / len(self.delta_e)

    @property
    def worst_delta_e(self) -> float:
        """Largest ΔE over matched devices (0 when none)."""
        return max(self.delta_e.values(), default=0.0)

    @property
    def warning(self) -> str:
        """First gamut warning, or an empty string."""
        return next(iter(self.warnings.values()), "")


def apply_color_to_devices(
    devices: Iterable[Any],
    r: float,
    g: float,
    b: float,
    solver: ColorSolver,
) -> ColorApplyResult:
    """Apply sRGB (r, g, b) to color-capable devices, solving once per profile."""
    r_n = max(0.0, min(1.0, float(r)))
    g_n = max(0.0, min(1.0, float(g)))
    b_n = max(0.0, min(1.0, float(b)))
    result = ColorApplyResult()
    for dev in devices:
        profile = effective_color_profile(dev)
        if profile is None:
            has_rgb = any(
                getattr(getattr(ch, "channel_type", None), "value", None)
                in ("red", "green", "blue")
                for ch in getattr(dev, "channels", ())
            )
            if not has_rgb:
                wheel_de = snap_device_color_wheel(dev, r_n, g_n, b_n)
                if wheel_de is not None:
                    result.delta_e[dev.device_id] = wheel_de
                    continue
            dev.set_color_srgb(r_n, g_n, b_n)
            result.delta_e[dev.device_id] = 0.0
            continue
        match = solver.solve(profile, r_n, g_n, b_n)
        dev.set_color_srgb(r_n, g_n, b_n, solved=match)
        result.delta_e[dev.device_id] = match.delta_e if match else 0.0
        if match and match.warning:
            result.warnings[dev.device_id] = match.warning
    return result


def apply_color_cie_to_devices(
    devices: Iterable[Any],
    x: float,
    y: float,
    solver: ColorSolver,
    Y: Optional[float] = None,  # pylint: disable=invalid-name
) -> ColorApplyResult:
    """Apply CIE (x, y, Y) to color-capable devices, evaluating exact chromaticity."""
    x_n = max(0.0, min(1.0, float(x)))
    y_n = max(0.0, min(1.0, float(y)))
    y_lum = max(0.0, float(Y)) if Y is not None else xy_max_luminance(x_n, y_n)
    result = ColorApplyResult()
    for dev in devices:
        profile = effective_color_profile(dev)
        if profile is None:
            rgb = xy_to_srgb(x_n, y_n)
            dev.set_color_srgb(rgb[0], rgb[1], rgb[2])
            result.delta_e[dev.device_id] = 0.0
            continue
        match = solver.solve_cie(profile, x_n, y_n, Y=y_lum)
        if match is not None:
            if hasattr(dev, "set_color_cie"):
                dev.set_color_cie(x_n, y_n, Y=y_lum, solved=match)
            else:
                rgb_achieved = match.achieved_xyz.to_srgb()
                dev.set_color_srgb(
                    rgb_achieved.r, rgb_achieved.g, rgb_achieved.b, solved=match
                )
            result.delta_e[dev.device_id] = match.delta_e
            if match.warning:
                result.warnings[dev.device_id] = match.warning
        else:
            result.delta_e[dev.device_id] = 0.0
    return result


def fan_colors_to_devices(
    devices: Iterable[Any],
    start_rgb: RGB,
    end_rgb: RGB,
    solver: ColorSolver,
    mode: str = "hs_short",
) -> ColorApplyResult:
    """Distribute a color gradient across ``devices`` and return aggregate match."""
    dev_list = list(devices)
    colors = compute_color_fan(len(dev_list), start_rgb, end_rgb, mode=mode)
    combined = ColorApplyResult()
    for dev, (r, g, b) in zip(dev_list, colors, strict=False):
        sub = apply_color_to_devices([dev], r, g, b, solver)
        combined.delta_e.update(sub.delta_e)
        combined.warnings.update(sub.warnings)
    return combined


class Throttle:  # pylint: disable=too-many-instance-attributes
    """Leading + trailing throttle: at most one call per ``interval_ms``.

    The first event fires immediately, events arriving faster than the
    interval are coalesced and only the latest one is delivered when the
    interval has elapsed. ``flush`` delivers the pending value right away
    (use it on button release so the final value is always exact).

    ``schedule(delay_ms, fn)`` must call ``fn`` later and return a handle;
    ``cancel(handle)`` must revoke it. With GLib: ``GLib.timeout_add`` and
    ``GLib.source_remove``. ``fn`` returns False so GLib drops the source.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        callback: Callable[..., None],
        interval_ms: int,
        schedule: Callable[..., Any],
        cancel: Callable[..., Any],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._callback = callback
        self._interval = interval_ms / 1000.0
        self._schedule = schedule
        self._cancel = cancel
        self._clock = clock
        self._pending: Optional[tuple[Any, ...]] = None
        self._handle: Any = None
        self._last_fire = float("-inf")

    def submit(self, *args: Any) -> None:  # noqa: ANN401
        """Queue a value; fires now, or at the end of the current interval."""
        self._pending = args
        if self._handle is not None:
            return
        wait = self._interval - (self._clock() - self._last_fire)
        if wait <= 0.0:
            self._fire()
        else:
            delay_ms = max(1, math.ceil(wait * 1000.0))
            self._handle = self._schedule(delay_ms, self._on_timer)

    def flush(self) -> None:
        """Deliver the pending value immediately, if any."""
        self._drop_timer()
        self._fire()

    def cancel(self) -> None:
        """Discard the pending value and any scheduled call."""
        self._drop_timer()
        self._pending = None

    def _drop_timer(self) -> None:
        if self._handle is not None:
            self._cancel(self._handle)
            self._handle = None

    def _on_timer(self) -> bool:
        self._handle = None
        self._fire()
        return False

    def _fire(self) -> None:
        if self._pending is None:
            return
        args, self._pending = self._pending, None
        self._last_fire = self._clock()
        self._callback(*args)
