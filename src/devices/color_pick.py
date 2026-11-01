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

* ``kelvin_to_srgb`` / ``kelvin_duv_to_xy``: CCT + Tint (Duv) to CIE xy / sRGB.
* ``render_hs_disc``: hue/saturation disc pixels (premultiplied BGRA).
* ``render_cie_xy_diagram``: CIE 1931 xy horseshoe diagram (premultiplied BGRA).
* ``convex_hull_2d`` / ``profile_gamut_xy``: fixture gamut polygon computation.
* ``ColorSolver``: NNLS color matching cached per fixture profile.
* ``apply_color_to_devices``: apply one color to many devices, solving once
  per distinct profile instead of once per device.
* ``Throttle``: coalesce a stream of pointer events to a maximum rate.
"""

# pylint: disable=too-many-lines

from __future__ import annotations

import colorsys
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import numpy as np

from .color import (
    SOLVER_STRATEGIES,
    CIExyY,
    ColorMatcher,
    EmitterProfile,
    FixtureColorProfile,
    MatchResult,
    delta_e76,
    sRGB,
)

RGB = tuple[float, float, float]
XY = tuple[float, float]

KELVIN_MIN = 2000.0
KELVIN_MAX = 10000.0
DUV_MIN = -0.05
DUV_MAX = 0.05

CIE_X_MAX = 0.8
CIE_Y_MAX = 0.9

# CIE 1931 2-degree standard observer spectral locus (380 nm to 700 nm).
SPECTRAL_LOCUS_XY: tuple[XY, ...] = (
    (0.1741, 0.0050),  # 380 nm
    (0.1738, 0.0049),  # 390 nm
    (0.1733, 0.0048),  # 400 nm
    (0.1726, 0.0048),  # 410 nm
    (0.1714, 0.0051),  # 420 nm
    (0.1689, 0.0069),  # 430 nm
    (0.1644, 0.0109),  # 440 nm
    (0.1566, 0.0177),  # 450 nm
    (0.1440, 0.0297),  # 460 nm
    (0.1241, 0.0578),  # 470 nm
    (0.0913, 0.1327),  # 480 nm
    (0.0454, 0.2950),  # 490 nm
    (0.0082, 0.5384),  # 500 nm
    (0.0139, 0.7502),  # 510 nm
    (0.0743, 0.8338),  # 520 nm
    (0.1547, 0.8059),  # 530 nm
    (0.2296, 0.7543),  # 540 nm
    (0.3016, 0.6923),  # 550 nm
    (0.3731, 0.6245),  # 560 nm
    (0.4441, 0.5547),  # 570 nm
    (0.5125, 0.4866),  # 580 nm
    (0.5752, 0.4242),  # 590 nm
    (0.6270, 0.3725),  # 600 nm
    (0.6658, 0.3340),  # 610 nm
    (0.6915, 0.3083),  # 620 nm
    (0.7079, 0.2920),  # 630 nm
    (0.7190, 0.2809),  # 640 nm
    (0.7260, 0.2740),  # 650 nm
    (0.7300, 0.2700),  # 660 nm
    (0.7320, 0.2680),  # 670 nm
    (0.7334, 0.2666),  # 680 nm
    (0.7344, 0.2656),  # 690 nm
    (0.7347, 0.2653),  # 700 nm
)

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
# Color conversions (CCT, Duv, CIE xy, sRGB, HS)
# --------------------------------------------------------------------------


def _gamma_encode(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def kelvin_to_uv(kelvin: float) -> tuple[float, float]:
    """CIE 1960 UCS (u, v) on the Planckian locus (Krystek 1985, 1000-15000 K)."""
    t = max(1000.0, min(15000.0, float(kelvin)))
    u = (0.860117757 + 1.54118254e-4 * t + 1.28641212e-7 * t * t) / (
        1.0 + 8.42420235e-4 * t + 7.08145163e-7 * t * t
    )
    v = (0.317398726 + 4.22806245e-5 * t + 4.20481691e-8 * t * t) / (
        1.0 - 2.89741816e-5 * t + 1.61456053e-7 * t * t
    )
    return u, v


def uv_to_xy(u: float, v: float) -> XY:
    """Convert CIE 1960 (u, v) coordinates to CIE 1931 (x, y)."""
    d = 2.0 * u - 8.0 * v + 4.0
    if abs(d) < 1e-9:
        return 0.3127, 0.3290
    return 3.0 * u / d, 2.0 * v / d


def xy_to_uv(x: float, y: float) -> tuple[float, float]:
    """Convert CIE 1931 (x, y) coordinates to CIE 1960 (u, v)."""
    d = -2.0 * x + 12.0 * y + 3.0
    if abs(d) < 1e-9:
        return 0.1978, 0.3122
    return 4.0 * x / d, 6.0 * y / d


def kelvin_to_xy(kelvin: float) -> XY:
    """CIE 1931 xy of the Planckian locus (Krystek 1985, valid 1000-15000 K)."""
    u, v = kelvin_to_uv(kelvin)
    return uv_to_xy(u, v)


def kelvin_duv_to_xy(  # pylint: disable=too-many-locals
    kelvin: float, duv: float = 0.0
) -> XY:
    """CIE 1931 xy for correlated color temperature and Duv tint offset.

    Positive ``duv`` shifts toward green (+v normal to the Planckian locus in
    CIE 1960 UCS); negative ``duv`` shifts toward magenta (-v).
    """
    t = max(1000.0, min(15000.0, float(kelvin)))
    u0, v0 = kelvin_to_uv(t)
    if abs(duv) < 1e-9:
        return uv_to_xy(u0, v0)
    clamped_duv = max(DUV_MIN, min(DUV_MAX, float(duv)))
    dt = 10.0
    u_minus, v_minus = kelvin_to_uv(max(1000.0, t - dt))
    u_plus, v_plus = kelvin_to_uv(min(15000.0, t + dt))
    du = u_plus - u_minus
    dv = v_plus - v_minus
    norm = math.hypot(du, dv)
    if norm < 1e-12:
        return uv_to_xy(u0, v0)
    # As T increases, u and v decrease (du < 0, dv < 0).
    # Normal (dv / norm, -du / norm) has positive v-component (+Duv -> green).
    n_u = dv / norm
    n_v = -du / norm
    return uv_to_xy(u0 + clamped_duv * n_u, v0 + clamped_duv * n_v)


def xy_to_srgb(x: float, y: float) -> RGB:
    """CIE 1931 (x, y) chromaticity to normalized sRGB (brightest channel = 1)."""
    y_safe = max(float(y), 1e-4)
    x_safe = max(0.0, float(x))
    big_x = x_safe / y_safe
    big_y = 1.0
    big_z = max(0.0, (1.0 - x_safe - y_safe) / y_safe)
    r = 3.2406 * big_x - 1.5372 * big_y - 0.4986 * big_z
    g = -0.9689 * big_x + 1.8758 * big_y + 0.0415 * big_z
    b = 0.0557 * big_x - 0.2040 * big_y + 1.0570 * big_z
    peak = max(r, g, b, 1e-9)
    r_n, g_n, b_n = (max(0.0, c / peak) for c in (r, g, b))
    return _gamma_encode(r_n), _gamma_encode(g_n), _gamma_encode(b_n)


def srgb_to_xy(r: float, g: float, b: float) -> XY:
    """Normalized sRGB to CIE 1931 (x, y) (returns D65 white point when black)."""
    r_n = max(0.0, min(1.0, float(r)))
    g_n = max(0.0, min(1.0, float(g)))
    b_n = max(0.0, min(1.0, float(b)))
    if max(r_n, g_n, b_n) < 1e-6:
        return 0.3127, 0.3290
    cie = sRGB(r_n, g_n, b_n).to_XYZ().to_xyY()
    return cie.x, cie.y


def kelvin_to_srgb(kelvin: float, duv: float = 0.0) -> RGB:
    """Correlated color temperature (+ optional Duv tint) to normalized sRGB."""
    x, y = kelvin_duv_to_xy(kelvin, duv)
    return xy_to_srgb(x, y)


def planckian_locus_xy(steps: int = 32) -> list[XY]:
    """Sampled CIE 1931 (x, y) points along the Planckian locus (1800-12000 K)."""
    count = max(2, int(steps))
    t_min, t_max = 1800.0, 12000.0
    return [
        kelvin_to_xy(t_min + (t_max - t_min) * i / (count - 1)) for i in range(count)
    ]


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
# Gamut hull & polygon geometry
# --------------------------------------------------------------------------


def convex_hull_2d(points: Iterable[XY]) -> list[XY]:
    """Monotone chain 2D convex hull in counter-clockwise order."""
    pts = sorted({(round(float(x), 6), round(float(y), 6)) for x, y in points})
    if len(pts) <= 2:
        return list(pts)

    def cross(o: XY, a: XY, b: XY) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[XY] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0.0:
            lower.pop()
        lower.append(p)

    upper: list[XY] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0.0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


_CHANNEL_DEFAULT_EMITTERS: dict[str, tuple[str, float, float, float, float]] = {
    "red": ("Red", 0.6400, 0.3300, 21.26, 625.0),
    "green": ("Green", 0.3000, 0.6000, 71.52, 525.0),
    "blue": ("Blue", 0.1500, 0.0600, 7.22, 465.0),
    "amber": ("Amber", 0.5600, 0.4200, 40.0, 590.0),
    "lime": ("Lime", 0.3225, 0.3870, 100.0, 560.0),
}


def effective_color_profile(device: object) -> Optional[FixtureColorProfile]:
    """Return device color_profile, completing missing R/G/B emitters from channels."""
    profile: Optional[FixtureColorProfile] = getattr(device, "color_profile", None)
    if profile is None:
        return None
    existing = {e.name.lower() for e in profile.emitters}
    if {"red", "green", "blue"}.issubset(existing):
        return profile

    ch_types = {
        getattr(getattr(ch, "channel_type", None), "value", "")
        for ch in getattr(device, "channels", []) or []
    }
    missing_rgb = [
        _CHANNEL_DEFAULT_EMITTERS[c]
        for c in ("red", "green", "blue")
        if c not in existing and (c in ch_types or 0 < len(profile.emitters) < 3)
    ]
    if not missing_rgb:
        return profile

    prepended = [
        EmitterProfile(name=n, cie=CIExyY(x, y, big_y), dominant_wavelength=wl)
        for n, x, y, big_y, wl in missing_rgb
    ]
    return FixtureColorProfile(
        fixture_name=profile.fixture_name,
        emitters=prepended + list(profile.emitters),
        white_point=profile.white_point,
        color_space_mode=profile.color_space_mode,
    )


def profile_gamut_xy(profile: FixtureColorProfile) -> list[XY]:
    """Convex hull of a fixture profile's emitters in CIE 1931 (x, y) space."""
    return convex_hull_2d((e.cie.x, e.cie.y) for e in profile.emitters)


def profile_gamut_hs(profile: FixtureColorProfile) -> list[tuple[float, float]]:
    """Emitter gamut vertices mapped to (hue, sat) coordinates for the HS disc."""
    hull_xy = profile_gamut_xy(profile)
    return [rgb_to_hs(*xy_to_srgb(x, y)) for x, y in hull_xy]


def device_emitters_xy(device: object) -> list[XY]:
    """All emitter (x, y) coordinates of a device (including interior emitters)."""
    profile = effective_color_profile(device)
    pts: list[XY] = []
    if profile is not None:
        pts.extend((e.cie.x, e.cie.y) for e in profile.emitters)
    if len(pts) < 3:
        for ch in getattr(device, "channels", []) or []:
            c_val = getattr(getattr(ch, "channel_type", None), "value", "")
            if c_val in _CHANNEL_DEFAULT_EMITTERS:
                _, x, y, _, _ = _CHANNEL_DEFAULT_EMITTERS[c_val]
                if (x, y) not in pts:
                    pts.append((x, y))
    return pts


def device_gamut_xy(device: object) -> list[XY]:
    """Convex hull of a device's color gamut in CIE 1931 (x, y) space."""
    return convex_hull_2d(device_emitters_xy(device))


def device_gamut_hs(device: object) -> list[tuple[float, float]]:
    """Device gamut hull vertices mapped to (hue, sat) coordinates."""
    return [rgb_to_hs(*xy_to_srgb(x, y)) for x, y in device_gamut_xy(device)]


def point_in_polygon(x: float, y: float, polygon: tuple[XY, ...] | list[XY]) -> bool:
    """Ray-casting check for whether (x, y) lies inside ``polygon``."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    x1, y1 = polygon[-1]
    for x2, y2 in polygon:
        if ((y2 > y) != (y1 > y)) and (
            x < (x1 - x2) * (y - y2) / ((y1 - y2) or 1e-12) + x2
        ):
            inside = not inside
        x1, y1 = x2, y2
    return inside


def clamp_xy_to_locus(x: float, y: float) -> XY:  # pylint: disable=too-many-locals
    """Return (x, y) if inside the CIE 1931 horseshoe, else closest boundary point."""
    if point_in_polygon(x, y, SPECTRAL_LOCUS_XY):
        return float(x), float(y)
    best_x, best_y = SPECTRAL_LOCUS_XY[0]
    best_d2 = float("inf")
    n = len(SPECTRAL_LOCUS_XY)
    for i in range(n):
        ax, ay = SPECTRAL_LOCUS_XY[i]
        bx, by = SPECTRAL_LOCUS_XY[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        if seg_len2 < 1e-12:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / seg_len2))
        px, py = ax + t * dx, ay + t * dy
        d2 = (x - px) ** 2 + (y - py) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_x, best_y = px, py
    return best_x, best_y


# --------------------------------------------------------------------------
# Hue/saturation disc & CIE 1931 xy diagram rendering
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


def render_cie_xy_diagram(size: int) -> np.ndarray:  # pylint: disable=too-many-locals
    """Render the CIE 1931 xy horseshoe diagram in premultiplied BGRA.

    The diagram spans x in [0, CIE_X_MAX] left-to-right and y in [0, CIE_Y_MAX]
    bottom-to-top, with an anti-aliased spectral locus boundary.
    """
    size = max(4, int(size))
    row_idx, col_idx = np.mgrid[0:size, 0:size].astype(np.float64)
    xs = ((col_idx + 0.5) / size) * CIE_X_MAX
    ys = (1.0 - (row_idx + 0.5) / size) * CIE_Y_MAX

    inside = np.zeros((size, size), dtype=bool)
    min_dist_sq = np.full((size, size), np.inf, dtype=np.float64)
    n = len(SPECTRAL_LOCUS_XY)
    for i in range(n):
        ax, ay = SPECTRAL_LOCUS_XY[i]
        bx, by = SPECTRAL_LOCUS_XY[(i + 1) % n]
        cond = (ay > ys) != (by > ys)
        dy_edge = by - ay if abs(by - ay) > 1e-12 else 1e-12
        x_int = (bx - ax) * (ys - ay) / dy_edge + ax
        inside ^= cond & (xs < x_int)

        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy + 1e-12
        t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / seg_len2, 0.0, 1.0)
        px = ax + t * dx
        py = ay + t * dy
        d2 = (xs - px) ** 2 + (ys - py) ** 2
        min_dist_sq = np.minimum(min_dist_sq, d2)

    px_scale = size / max(CIE_X_MAX, CIE_Y_MAX)
    signed_dist_px = np.sqrt(min_dist_sq) * px_scale * np.where(inside, 1.0, -1.0)
    alpha = np.clip(signed_dist_px + 0.5, 0.0, 1.0)

    y_safe = np.maximum(ys, 1e-4)
    big_x = xs / y_safe
    big_y = np.ones_like(xs)
    big_z = np.maximum(0.0, (1.0 - xs - y_safe) / y_safe)

    r_lin = 3.2406 * big_x - 1.5372 * big_y - 0.4986 * big_z
    g_lin = -0.9689 * big_x + 1.8758 * big_y + 0.0415 * big_z
    b_lin = 0.0557 * big_x - 0.2040 * big_y + 1.0570 * big_z
    peak = np.maximum(np.maximum(r_lin, g_lin), np.maximum(b_lin, 1e-9))

    def _vec_gamma(arr: np.ndarray) -> np.ndarray:
        c = np.clip(arr / peak, 0.0, 1.0)
        return np.where(c <= 0.0031308, 12.92 * c, 1.055 * (c ** (1.0 / 2.4)) - 0.055)

    red = _vec_gamma(r_lin)
    green = _vec_gamma(g_lin)
    blue = _vec_gamma(b_lin)

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
# Professional Gel Swatchbook (Lee Filters & Rosco)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GelSwatch:  # pylint: disable=too-many-instance-attributes
    """Standard lighting gel filter entry (Lee / Rosco) with CIE 1931 xyY."""

    code: str
    manufacturer: str
    number: str
    name: str
    category: str
    cie_x: float
    cie_y: float
    transmission_y: float = 50.0

    @property
    def rgb(self) -> RGB:
        """Approximate sRGB representation of this gel's CIE chromaticity."""
        return xy_to_srgb(self.cie_x, self.cie_y)


GEL_LIBRARY: tuple[GelSwatch, ...] = (
    # Correction (CTB / CTO / Plus & Minus Green)
    GelSwatch("L201", "Lee", "201", "Full C.T. Blue", "Correction", 0.246, 0.254, 36.0),
    GelSwatch("L202", "Lee", "202", "Half C.T. Blue", "Correction", 0.276, 0.289, 55.0),
    GelSwatch(
        "L203", "Lee", "203", "Quarter C.T. Blue", "Correction", 0.295, 0.310, 72.0
    ),
    GelSwatch(
        "L204", "Lee", "204", "Full C.T. Orange", "Correction", 0.440, 0.405, 58.0
    ),
    GelSwatch(
        "L205", "Lee", "205", "Half C.T. Orange", "Correction", 0.382, 0.377, 71.0
    ),
    GelSwatch(
        "L206", "Lee", "206", "Quarter C.T. Orange", "Correction", 0.348, 0.355, 81.0
    ),
    GelSwatch("L244", "Lee", "244", "Lee Plus Green", "Correction", 0.335, 0.405, 74.0),
    GelSwatch(
        "L247", "Lee", "247", "Lee Minus Green", "Correction", 0.345, 0.285, 55.0
    ),
    GelSwatch(
        "R3202", "Rosco", "3202", "Full Blue (CTB)", "Correction", 0.248, 0.256, 36.0
    ),
    GelSwatch(
        "R3407", "Rosco", "3407", "Roscosun CTO", "Correction", 0.438, 0.404, 58.0
    ),
    # Warm / Amber / Red / Cosmetic
    GelSwatch("L002", "Lee", "002", "Rose Pink", "Cosmetic", 0.425, 0.245, 32.0),
    GelSwatch(
        "L004", "Lee", "004", "Medium Bastard Amber", "Cosmetic", 0.372, 0.348, 66.0
    ),
    GelSwatch("L009", "Lee", "009", "Pale Amber Gold", "Warm", 0.388, 0.382, 74.0),
    GelSwatch("L017", "Lee", "017", "Surprise Peach", "Warm", 0.448, 0.365, 42.0),
    GelSwatch("L021", "Lee", "021", "Gold Amber", "Warm", 0.565, 0.405, 31.0),
    GelSwatch("L026", "Lee", "026", "Bright Red", "Saturated", 0.680, 0.308, 9.5),
    GelSwatch("L103", "Lee", "103", "Straw", "Warm", 0.368, 0.385, 81.0),
    GelSwatch("L106", "Lee", "106", "Primary Red", "Saturated", 0.692, 0.302, 9.3),
    GelSwatch("L128", "Lee", "128", "Bright Pink", "Saturated", 0.450, 0.210, 15.0),
    GelSwatch("L135", "Lee", "135", "Deep Golden Amber", "Warm", 0.618, 0.375, 19.0),
    GelSwatch("L152", "Lee", "152", "Pale Gold", "Cosmetic", 0.375, 0.362, 72.0),
    GelSwatch("L162", "Lee", "162", "Bastard Amber", "Cosmetic", 0.362, 0.352, 78.0),
    GelSwatch("L164", "Lee", "164", "Flame Red", "Saturated", 0.665, 0.322, 15.0),
    GelSwatch("R02", "Rosco", "02", "Bastard Amber", "Cosmetic", 0.365, 0.350, 78.0),
    GelSwatch("R21", "Rosco", "21", "Golden Amber", "Warm", 0.562, 0.406, 32.0),
    GelSwatch("R26", "Rosco", "26", "Light Red", "Saturated", 0.678, 0.310, 11.0),
    GelSwatch("R33", "Rosco", "33", "No Color Pink", "Cosmetic", 0.352, 0.322, 68.0),
    # Cool / Blue / Cyan / Green / Lavender
    GelSwatch("L068", "Lee", "068", "Sky Blue", "Cool", 0.165, 0.215, 14.0),
    GelSwatch("L079", "Lee", "079", "Just Blue", "Cool", 0.145, 0.125, 6.5),
    GelSwatch("L115", "Lee", "115", "Peacock Blue", "Cool", 0.175, 0.345, 32.0),
    GelSwatch("L116", "Lee", "116", "Medium Blue-Green", "Cool", 0.155, 0.375, 16.0),
    GelSwatch("L117", "Lee", "117", "Steel Blue", "Cool", 0.245, 0.295, 55.0),
    GelSwatch("L119", "Lee", "119", "Dark Blue", "Saturated", 0.140, 0.085, 3.1),
    GelSwatch("L120", "Lee", "120", "Deep Blue", "Saturated", 0.142, 0.062, 1.5),
    GelSwatch("L124", "Lee", "124", "Dark Green", "Saturated", 0.215, 0.565, 22.0),
    GelSwatch("L126", "Lee", "126", "Mauve", "Saturated", 0.335, 0.155, 4.5),
    GelSwatch("L132", "Lee", "132", "Medium Blue", "Cool", 0.148, 0.142, 8.2),
    GelSwatch("L136", "Lee", "136", "Pale Lavender", "Cosmetic", 0.305, 0.285, 52.0),
    GelSwatch("L139", "Lee", "139", "Primary Green", "Saturated", 0.225, 0.655, 12.0),
    GelSwatch("L170", "Lee", "170", "Deep Lavender", "Cool", 0.265, 0.215, 24.0),
    GelSwatch("L181", "Lee", "181", "Congo Blue", "Saturated", 0.152, 0.048, 0.8),
    GelSwatch("L195", "Lee", "195", "Zenith Blue", "Saturated", 0.144, 0.068, 2.8),
    GelSwatch("L728", "Lee", "728", "Steel Green", "Cool", 0.262, 0.338, 48.0),
    GelSwatch("R68", "Rosco", "68", "Parry Sky Blue", "Cool", 0.168, 0.205, 13.5),
    GelSwatch("R80", "Rosco", "80", "Primary Blue", "Saturated", 0.146, 0.115, 7.0),
    GelSwatch("R382", "Rosco", "382", "Congo Blue", "Saturated", 0.154, 0.050, 0.9),
)


def filter_gels(query: str = "", manufacturer: str = "All") -> list[GelSwatch]:
    """Filter GEL_LIBRARY by manufacturer ('All', 'Lee', 'Rosco') and search query."""
    mfg = manufacturer.strip().lower()
    pool = [
        g for g in GEL_LIBRARY if mfg in ("", "all") or g.manufacturer.lower() == mfg
    ]
    q = query.strip().lower()
    if not q:
        return pool

    q_num = q.lstrip("lr0")
    scored: list[tuple[int, int, GelSwatch]] = []
    for idx, g in enumerate(pool):
        code_low = g.code.lower()
        num_low = g.number.lower()
        num_trim = num_low.lstrip("0") or "0"
        name_low = g.name.lower()
        cat_low = g.category.lower()

        if q in (code_low, num_low) or (q_num and q_num == num_trim and q[0].isdigit()):
            scored.append((0, idx, g))
        elif code_low.startswith(q) or num_low.startswith(q):
            scored.append((1, idx, g))
        elif q in code_low or q in name_low or q in cat_low:
            scored.append((2, idx, g))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in scored]


def find_gel(query: str) -> Optional[GelSwatch]:
    """Return the best-matching GelSwatch for ``query``, or None."""
    matches = filter_gels(query=query, manufacturer="All")
    return matches[0] if matches else None


def evaluate_gel_for_profile(
    gel: GelSwatch,
    profile: Optional[FixtureColorProfile],
    solver: ColorSolver,
) -> tuple[float, str, str]:
    """Evaluate how closely ``profile`` can reproduce ``gel``.

    Returns:
        ``(delta_e, warning, match_level)`` where ``match_level`` is one of
        ``"exact"``, ``"close"``, ``"approx"``, ``"out"``.
    """
    if profile is None:
        return 0.0, "", "exact"
    r, g, b = gel.rgb
    match = solver.solve(profile, r, g, b)
    if match is None:
        return 0.0, "", "exact"
    level = classify_match(match.delta_e, match.warning)
    return float(match.delta_e), str(match.warning), level


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
