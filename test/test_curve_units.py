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
"""Unit tests for curve unit conversion and formatting."""

from __future__ import annotations

import pytest

from olc.gtk3.widgets.curve_units import (
    CurveUnitMode,
    format_curve_value,
    parse_curve_value,
)


def test_curve_unit_labels() -> None:
    """Verify all unit modes have descriptive labels."""
    for mode in CurveUnitMode:
        assert len(mode.label) > 0


@pytest.mark.parametrize(
    ("val", "mode", "expected"),
    [
        (0.0, CurveUnitMode.PERCENT, "0 %"),
        (0.5, CurveUnitMode.PERCENT, "50 %"),
        (0.255, CurveUnitMode.PERCENT, "25.5 %"),
        (1.0, CurveUnitMode.PERCENT, "100 %"),
        (0.0, CurveUnitMode.NORMALIZED, "0.000"),
        (0.5, CurveUnitMode.NORMALIZED, "0.500"),
        (1.0, CurveUnitMode.NORMALIZED, "1.000"),
        (0.0, CurveUnitMode.DMX_8BIT, "0"),
        (0.5, CurveUnitMode.DMX_8BIT, "128"),
        (1.0, CurveUnitMode.DMX_8BIT, "255"),
        (0.0, CurveUnitMode.DMX_16BIT, "0"),
        (0.5, CurveUnitMode.DMX_16BIT, "32768"),
        (1.0, CurveUnitMode.DMX_16BIT, "65535"),
    ],
)
def test_format_curve_value(val: float, mode: CurveUnitMode, expected: str) -> None:
    """Verify formatting for various values and modes."""
    assert format_curve_value(val, mode) == expected


@pytest.mark.parametrize(
    ("text", "mode", "expected"),
    [
        ("0", CurveUnitMode.PERCENT, 0.0),
        ("50%", CurveUnitMode.PERCENT, 0.5),
        ("25.5 %", CurveUnitMode.PERCENT, 0.255),
        ("25,5", CurveUnitMode.PERCENT, 0.255),
        ("100", CurveUnitMode.PERCENT, 1.0),
        ("120", CurveUnitMode.PERCENT, 1.0),  # clamped
        ("-5", CurveUnitMode.PERCENT, 0.0),  # clamped
        ("0.5", CurveUnitMode.NORMALIZED, 0.5),
        ("0,75", CurveUnitMode.NORMALIZED, 0.75),
        ("128", CurveUnitMode.DMX_8BIT, 128 / 255.0),
        ("255", CurveUnitMode.DMX_8BIT, 1.0),
        ("32768", CurveUnitMode.DMX_16BIT, 32768 / 65535.0),
        ("65535", CurveUnitMode.DMX_16BIT, 1.0),
        ("invalid", CurveUnitMode.PERCENT, None),
        ("", CurveUnitMode.PERCENT, None),
        ("   ", CurveUnitMode.PERCENT, None),
    ],
)
def test_parse_curve_value(
    text: str, mode: CurveUnitMode, expected: float | None
) -> None:
    """Verify parsing for various inputs and modes."""
    res = parse_curve_value(text, mode)
    if expected is None:
        assert res is None
    else:
        assert res is not None
        assert abs(res - expected) < 1e-4
