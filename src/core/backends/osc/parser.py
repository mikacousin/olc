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
"""OSC argument parsing and normalization utilities."""

from __future__ import annotations


def parse_osc_normalized(arg: object) -> float:
    """Normalize any OSC level argument into a float in range [0.0, 1.0].

    - Floats in range [0.0, 1.0] are preserved directly.
    - Values > 1.0 (legacy 8-bit DMX scale 0..255) are normalized by dividing by 255.0.
    - Negative values are treated as release signals (-1.0).
    - Booleans evaluate to 1.0 for True, 0.0 for False.
    - Keywords 'full' -> 1.0, 'out'/'zero'/'off' -> 0.0, 'release' -> -1.0.

    Args:
        arg: Raw OSC argument (float, int, bool, str, or None).

    Returns:
        A normalized float in [0.0, 1.0], or -1.0 for release.
    """
    if arg is None:
        return 0.0

    if isinstance(arg, bool):
        return 1.0 if arg else 0.0

    if isinstance(arg, (int, float)):
        val = float(arg)
        if val < 0.0:
            return -1.0
        if val <= 1.0:
            return max(0.0, val)
        # Value > 1.0: treat as legacy 0..255 DMX scale
        return min(1.0, val / 255.0)

    if isinstance(arg, str):
        cleaned = arg.strip().lower()
        if cleaned == "full":
            return 1.0
        if cleaned in {"out", "zero", "off"}:
            return 0.0
        if cleaned == "release":
            return -1.0
        try:
            numeric_val = float(cleaned)
            return parse_osc_normalized(numeric_val)
        except ValueError:
            return 0.0

    return 0.0


def parse_osc_level_dmx(arg: object, dmx_max: int = 255) -> int:
    """Convert an OSC argument to an integer DMX level [0..dmx_max].

    Args:
        arg: Raw OSC argument.
        dmx_max: Maximum DMX value (typically 255).

    Returns:
        Integer level in range [0, dmx_max], or -1 if releasing override.
    """
    norm = parse_osc_normalized(arg)
    if norm < 0.0:
        return -1
    return round(norm * dmx_max)


def parse_osc_bool(arg: object) -> bool:
    """Parse an OSC argument as a boolean trigger or toggle state.

    Supports native bools, float/int thresholding (> 0.5 or != 0),
    and common trigger string keywords ('true', 'on', 'down', 'press').

    Args:
        arg: Raw OSC argument.

    Returns:
        True if the argument indicates an active/pressed state, False otherwise.
    """
    if arg is None:
        return False

    if isinstance(arg, bool):
        return arg

    if isinstance(arg, (int, float)):
        # For floating point touch controls, values > 0.0 (typically 1.0) mean pressed
        return float(arg) > 0.0

    if isinstance(arg, str):
        cleaned = arg.strip().lower()
        return cleaned in {"true", "1", "on", "press", "down", "push", "yes"}

    return bool(arg)
