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
"""Unit conversion and formatting for transfer curves."""

from __future__ import annotations

from enum import Enum
from gettext import gettext as _


class CurveUnitMode(str, Enum):
    """Display and input unit modes for curves."""

    PERCENT = "percent"
    NORMALIZED = "normalized"
    DMX_8BIT = "dmx_8bit"
    DMX_16BIT = "dmx_16bit"

    @property
    def label(self) -> str:
        """User-facing localized label for unit selector."""
        labels = {
            CurveUnitMode.PERCENT: _("% (0 - 100)"),
            CurveUnitMode.NORMALIZED: _("Normalized (0.0 - 1.0)"),
            CurveUnitMode.DMX_8BIT: _("DMX 8-bit (0 - 255)"),
            CurveUnitMode.DMX_16BIT: _("DMX 16-bit (0 - 65535)"),
        }
        return labels.get(self, self.value)


def format_curve_value(norm_val: float, mode: CurveUnitMode) -> str:
    """Format a normalized [0.0, 1.0] value according to unit mode.

    Args:
        norm_val: Value in [0.0, 1.0]
        mode: Target unit mode

    Returns:
        Formatted string representation
    """
    clamped = max(0.0, min(1.0, float(norm_val)))
    if mode == CurveUnitMode.PERCENT:
        pct = clamped * 100.0
        # If integer percentage, format without decimals, else with 1 decimal
        if abs(pct - round(pct)) < 1e-4:
            return f"{round(pct)} %"
        return f"{pct:.1f} %"
    if mode == CurveUnitMode.NORMALIZED:
        return f"{clamped:.3f}"
    if mode == CurveUnitMode.DMX_8BIT:
        return str(int(round(clamped * 255.0)))
    if mode == CurveUnitMode.DMX_16BIT:
        return str(int(round(clamped * 65535.0)))
    return f"{clamped:.3f}"


def parse_curve_value(text: str, mode: CurveUnitMode) -> float | None:
    """Parse user text input into a normalized [0.0, 1.0] value.

    Args:
        text: Input string
        mode: Expected unit mode

    Returns:
        Normalized float in [0.0, 1.0], or None if input is invalid
    """
    cleaned = text.strip().rstrip("%").strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        val = float(cleaned)
    except ValueError:
        return None

    if mode == CurveUnitMode.PERCENT:
        norm = val / 100.0
    elif mode == CurveUnitMode.NORMALIZED:
        norm = val
    elif mode == CurveUnitMode.DMX_8BIT:
        norm = val / 255.0
    elif mode == CurveUnitMode.DMX_16BIT:
        norm = val / 65535.0
    else:
        norm = val

    return max(0.0, min(1.0, norm))
