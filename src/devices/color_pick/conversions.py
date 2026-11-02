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
"""Color space conversions and formatting utilities (CCT, Duv, CIE xy, sRGB, HS)."""

from __future__ import annotations

import colorsys
import math
from typing import Optional

from olc.devices.color import sRGB

RGB = tuple[float, float, float]
XY = tuple[float, float]

KELVIN_MIN = 2000.0
KELVIN_MAX = 10000.0
DUV_MIN = -0.05
DUV_MAX = 0.05

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


def xy_max_luminance(x: float, y: float) -> float:
    """Maximum achievable relative luminance Y (0..100) for chromaticity (x, y)."""
    y_safe = max(1e-4, float(y))
    x_safe = max(0.0, float(x))
    big_x = x_safe / y_safe
    big_y = 1.0
    big_z = max(0.0, (1.0 - x_safe - y_safe) / y_safe)
    r = 3.2406 * big_x - 1.5372 * big_y - 0.4986 * big_z
    g = -0.9689 * big_x + 1.8758 * big_y + 0.0415 * big_z
    b = 0.0557 * big_x - 0.2040 * big_y + 1.0570 * big_z
    peak = max(r, g, b)
    if peak <= 0.0:
        return 100.0
    return max(0.0, min(100.0, 100.0 / peak))


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
