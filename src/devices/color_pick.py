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
"""Toolkit-independent logic behind the console-style color picker.

Nothing here imports GTK, so everything can be unit tested headless:

* ``kelvin_to_srgb``: correlated color temperature to sRGB.
* ``render_hs_disc``: hue/saturation disc pixels (premultiplied BGRA).
* ``ColorSolver``: NNLS color matching cached per fixture profile.
* ``apply_color_to_devices``: apply one color to many devices, solving once
  per distinct profile instead of once per device.
* ``Throttle``: coalesce a stream of pointer events to a maximum rate.
"""

from __future__ import annotations

import colorsys
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import numpy as np

from .color import ColorMatcher, FixtureColorProfile, MatchResult, sRGB

RGB = tuple[float, float, float]

KELVIN_MIN = 2000.0
KELVIN_MAX = 10000.0

# Generic swatches (no manufacturer gel library is embedded here).
PRESETS: tuple[tuple[str, RGB], ...] = (
    ("Red", (1.0, 0.0, 0.0)),
    ("Orange", (1.0, 0.5, 0.0)),
    ("Amber", (1.0, 0.75, 0.0)),
    ("Yellow", (1.0, 1.0, 0.0)),
    ("Lime", (0.5, 1.0, 0.0)),
    ("Green", (0.0, 1.0, 0.0)),
    ("Cyan", (0.0, 1.0, 1.0)),
    ("Blue", (0.0, 0.0, 1.0)),
    ("Violet", (0.5, 0.0, 1.0)),
    ("Magenta", (1.0, 0.0, 1.0)),
    ("Pink", (1.0, 0.5, 0.75)),
    ("White", (1.0, 1.0, 1.0)),
)


# --------------------------------------------------------------------------
# Color conversions
# --------------------------------------------------------------------------


def _gamma_encode(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def kelvin_to_xy(kelvin: float) -> tuple[float, float]:
    """CIE 1931 xy of the Planckian locus (Krystek 1985, valid 1000-15000 K)."""
    t = max(1000.0, min(15000.0, float(kelvin)))
    u = (0.860117757 + 1.54118254e-4 * t + 1.28641212e-7 * t * t) / (
        1.0 + 8.42420235e-4 * t + 7.08145163e-7 * t * t
    )
    v = (0.317398726 + 4.22806245e-5 * t + 4.20481691e-8 * t * t) / (
        1.0 - 2.89741816e-5 * t + 1.61456053e-7 * t * t
    )
    d = 2.0 * u - 8.0 * v + 4.0
    return 3.0 * u / d, 2.0 * v / d


def kelvin_to_srgb(kelvin: float) -> RGB:
    """Correlated color temperature to normalized sRGB (brightest channel = 1)."""
    x, y = kelvin_to_xy(kelvin)
    big_x, big_y, big_z = x / y, 1.0, (1.0 - x - y) / y
    r = 3.2406 * big_x - 1.5372 * big_y - 0.4986 * big_z
    g = -0.9689 * big_x + 1.8758 * big_y + 0.0415 * big_z
    b = 0.0557 * big_x - 0.2040 * big_y + 1.0570 * big_z
    peak = max(r, g, b, 1e-9)
    r, g, b = (max(0.0, c / peak) for c in (r, g, b))
    return _gamma_encode(r), _gamma_encode(g), _gamma_encode(b)


def rgb_to_hs(
    r: float, g: float, b: float, hue_hint: float = 0.0
) -> tuple[float, float]:
    """Hue and saturation in [0, 1]; keeps ``hue_hint`` when the color is gray."""
    h, s, _v = colorsys.rgb_to_hsv(r, g, b)
    if s < 1e-6:
        return hue_hint, 0.0
    return h, s


def hs_to_rgb(h: float, s: float) -> RGB:
    """Fully bright color for a hue/saturation pair."""
    return colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), 1.0)


def to_8bit(value: float) -> int:
    """Normalized [0, 1] to 8-bit integer, clamped."""
    return max(0, min(255, round(float(value) * 255.0)))


def to_24bit(value: float) -> int:
    """Normalized [0, 1] to 24-bit integer, clamped."""
    return max(0, min(16777215, round(float(value) * 16777215.0)))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """Normalized sRGB to ``#RRGGBB``."""
    return f"#{to_8bit(r):02X}{to_8bit(g):02X}{to_8bit(b):02X}"


def parse_hex(text: str) -> Optional[RGB]:
    """Parse ``#RGB``, ``#RRGGBB`` (leading ``#`` optional); None if invalid."""
    clean = text.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(ch * 2 for ch in clean)
    if len(clean) != 6:
        return None
    try:
        vals = [int(clean[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
        return vals[0], vals[1], vals[2]
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Hue/saturation disc
# --------------------------------------------------------------------------


def render_hs_disc(size: int) -> np.ndarray:  # pylint: disable=too-many-locals
    """Render a hue/saturation disc at full brightness.

    Returns:
        ``(size, size, 4)`` uint8 array in cairo ``ARGB32`` byte order on
        little-endian machines (B, G, R, A), alpha-premultiplied, with an
        anti-aliased edge. Hue 0 is at the right and increases clockwise,
        matching the pointer math of the widget.
    """
    size = max(2, int(size))
    radius = size / 2.0
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float64)
    dx = xs + 0.5 - radius
    dy = ys + 0.5 - radius
    dist_px = np.hypot(dx, dy)
    sat = np.clip(dist_px / radius, 0.0, 1.0)
    hue = (np.arctan2(dy, dx) / (2.0 * np.pi)) % 1.0

    h6 = hue * 6.0
    sector = np.floor(h6).astype(np.int64) % 6
    frac = h6 - np.floor(h6)
    p = 1.0 - sat
    q = 1.0 - sat * frac
    t = 1.0 - sat * (1.0 - frac)
    ones = np.ones_like(sat)
    red = np.choose(sector, [ones, q, p, p, t, ones])
    green = np.choose(sector, [t, ones, ones, q, p, p])
    blue = np.choose(sector, [p, p, t, ones, ones, q])

    alpha = np.clip(radius - dist_px + 0.5, 0.0, 1.0)
    out = np.empty((size, size, 4), dtype=np.uint8)
    out[..., 0] = np.round(blue * alpha * 255.0)
    out[..., 1] = np.round(green * alpha * 255.0)
    out[..., 2] = np.round(red * alpha * 255.0)
    out[..., 3] = np.round(alpha * 255.0)
    return out


# --------------------------------------------------------------------------
# Solving and applying colors
# --------------------------------------------------------------------------


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

    def __init__(self, max_entries: int = 2048) -> None:
        self.max_entries = max_entries
        self.solves = 0
        self._cache: dict[tuple[Any, ...], Optional[MatchResult]] = {}
        self._matchers: dict[tuple[Any, ...], ColorMatcher] = {}

    def solve(
        self, profile: FixtureColorProfile, r: float, g: float, b: float
    ) -> Optional[MatchResult]:
        """Emitter levels reproducing sRGB (r, g, b) on ``profile``."""
        r_n = max(0.0, min(1.0, float(r)))
        g_n = max(0.0, min(1.0, float(g)))
        b_n = max(0.0, min(1.0, float(b)))
        sig = profile_signature(profile)
        key = (sig, to_24bit(r_n), to_24bit(g_n), to_24bit(b_n))
        if key in self._cache:
            return self._cache[key]

        matcher = self._matchers.get(sig)
        if matcher is None:
            matcher = ColorMatcher([profile])
            self._matchers[sig] = matcher
        cie = sRGB(r_n, g_n, b_n).to_XYZ().to_xyY()
        result = matcher.match_cie(cie.x, cie.y, cie.Y).get(profile.fixture_name)
        self.solves += 1

        if len(self._cache) >= self.max_entries:
            self._cache.pop(next(iter(self._cache)))  # FIFO eviction
        self._cache[key] = result
        return result

    def clear(self) -> None:
        """Drop cached results (call when profiles are edited)."""
        self._cache.clear()
        self._matchers.clear()


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
        profile = getattr(dev, "color_profile", None)
        if profile is None:
            dev.set_color_srgb(r_n, g_n, b_n)
            result.delta_e[dev.device_id] = 0.0
            continue
        match = solver.solve(profile, r_n, g_n, b_n)
        dev.set_color_srgb(r_n, g_n, b_n, solved=match)
        result.delta_e[dev.device_id] = match.delta_e if match else 0.0
        if match and match.warning:
            result.warnings[dev.device_id] = match.warning
    return result


def classify_match(delta_e: float, warning: str = "") -> str:
    """Bucket a color match for display: exact, close, approx or out."""
    if warning or delta_e >= 6.0:
        return "out"
    if delta_e >= 3.0:
        return "approx"
    if delta_e >= 1.0:
        return "close"
    return "exact"


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


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
        schedule: Callable[[int, Callable[[], bool]], Any],
        cancel: Callable[[Any], None],
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
