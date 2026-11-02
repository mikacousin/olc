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
"""Professional Gel Swatchbook (Lee Filters & Rosco) and Delta E classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from olc.devices.color import FixtureColorProfile

from .conversions import (
    RGB,
    xy_to_srgb,
)

if TYPE_CHECKING:
    from .solver import ColorSolver


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


def classify_match(delta_e: float, warning: str = "") -> str:
    """Bucket a color match for display: exact, close, approx or out."""
    if warning or delta_e >= 6.0:
        return "out"
    if delta_e >= 3.0:
        return "approx"
    if delta_e >= 1.0:
        return "close"
    return "exact"


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
