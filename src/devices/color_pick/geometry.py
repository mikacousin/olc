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
"""Geometry and rendering for fixture color gamuts, spectral locus and chromaticity."""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from olc.devices.color import CIExyY, EmitterProfile, FixtureColorProfile

from .conversions import (
    XY,
    rgb_to_hs,
    xy_to_srgb,
)

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

_CHANNEL_DEFAULT_EMITTERS: dict[str, tuple[str, float, float, float, float]] = {
    "red": ("Red", 0.6400, 0.3300, 21.26, 625.0),
    "green": ("Green", 0.3000, 0.6000, 71.52, 525.0),
    "blue": ("Blue", 0.1500, 0.0600, 7.22, 465.0),
    "amber": ("Amber", 0.5600, 0.4200, 40.0, 590.0),
    "lime": ("Lime", 0.3225, 0.3870, 100.0, 560.0),
}


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
