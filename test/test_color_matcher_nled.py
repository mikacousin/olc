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
"""Unit tests for the multi-LED colorimetric engine (N >= 4, 8/16/24 bits)."""

# pylint: disable=missing-function-docstring

import pytest

from olc.devices.builtin import create_rgba_definition, create_rgbw_definition
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType
from olc.devices.color import (
    CIEXYZ,
    CIExyY,
    ColorMatcher,
    EmitterProfile,
    FixtureColorProfile,
    MatchResult,
    convex_hull_2d,
)
from olc.devices.color_pick.conversions import kelvin_to_xy
from olc.devices.gdtf import GDTF_ATTRIBUTE_MAP


def _make_lustr_profile() -> FixtureColorProfile:
    """Build a 7-emitter profile modeled after an ETC Source Four LED Series 2 Lustr."""
    emitters = [
        EmitterProfile("Red", CIExyY(0.690, 0.300, 25.0)),
        EmitterProfile("Green", CIExyY(0.170, 0.700, 60.0)),
        EmitterProfile("Blue", CIExyY(0.140, 0.050, 8.0)),
        EmitterProfile("Amber", CIExyY(0.580, 0.410, 45.0)),
        EmitterProfile("Cyan", CIExyY(0.080, 0.500, 35.0)),
        EmitterProfile("Lime", CIExyY(0.380, 0.560, 80.0)),
        EmitterProfile("Indigo", CIExyY(0.160, 0.020, 5.0)),
    ]
    return FixtureColorProfile(fixture_name="ETC Lustr 2", emitters=emitters)


# ---- Phase 1: Channel Types & DIN SPEC 15800 Attributes --------------------


def test_channel_types_extended() -> None:
    for expected in (
        ChannelType.CYAN,
        ChannelType.INDIGO,
        ChannelType.MAGENTA,
        ChannelType.YELLOW,
    ):
        assert expected in COLOR_CHANNEL_TYPES

    assert GDTF_ATTRIBUTE_MAP["ColorAdd_RY"] == ChannelType.RED
    assert GDTF_ATTRIBUTE_MAP["ColorAdd_C"] == ChannelType.CYAN
    assert GDTF_ATTRIBUTE_MAP["ColorAdd_BC"] == ChannelType.INDIGO
    assert GDTF_ATTRIBUTE_MAP["ColorAdd_M"] == ChannelType.MAGENTA
    assert GDTF_ATTRIBUTE_MAP["ColorAdd_Y"] == ChannelType.YELLOW


# ---- Phase 2: Convex Hull & Gamut Polygon ----------------------------------


def test_convex_hull_and_gamut_area() -> None:
    pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.5, 0.5)]
    hull = convex_hull_2d(pts)
    assert len(hull) == 4
    assert (0.5, 0.5) not in hull

    prof = _make_lustr_profile()
    poly = prof.gamut_polygon
    assert len(poly) >= 5
    assert prof.gamut_area > 0.15

    # Inside target: D65 white point
    assert prof.contains_xy(0.3127, 0.3290) is True
    # Outside target: deep monochromatic violet
    assert prof.contains_xy(0.05, 0.05) is False


# ---- Phase 3 & 4: Multi-LED Solver, 16/24-Bit & MatchResult ----------------


def test_match_result_16_and_24_bit() -> None:
    res = MatchResult(
        fixture_name="Test",
        emitter_names=["Red", "Green", "Blue"],
        coefficients=[50.0, 100.0, 0.0],
        dmx_values=[128, 255, 0],
        achieved_xyz=CIEXYZ(0.0, 0.0, 0.0),
        delta_e=0.0,
        normalized_weights=[0.5, 1.0, 0.0],
    )
    assert res.dmx_values_16 == [32768, 65535, 0]
    assert res.dmx_values_24 == [8388608, 16777215, 0]
    assert res.as_dict_16()["Green"] == 65535
    assert res.as_dict_24()["Red"] == 8388608
    assert res.as_normalized_dict()["Red"] == 0.5


def test_rgba_white_no_false_out_of_gamut() -> None:
    dev = create_rgba_definition().instantiate(1, "RGBA", 1, 1)
    assert dev.color_profile is not None
    matcher = ColorMatcher([dev.color_profile])
    res = matcher.match_srgb(255, 255, 255)["Generic LED RGBA"]
    assert res.warning == ""
    assert res.delta_e < 0.2
    assert max(res.normalized_weights) <= 1.0


def test_rgbw_white_recruits_white_emitter() -> None:
    dev = create_rgbw_definition().instantiate(1, "RGBW", 1, 1)
    assert dev.color_profile is not None
    matcher = ColorMatcher([dev.color_profile])
    res = matcher.match_srgb(255, 255, 255)["Generic LED RGBW"]
    white_weight = res.as_normalized_dict()["White"]
    assert white_weight > 0.7  # White diode delivers majority of luminance
    assert res.warning == ""
    assert res.delta_e < 0.2


def test_seven_led_cct_white_recruits_all_emitters() -> None:
    prof = _make_lustr_profile()
    matcher = ColorMatcher([prof])

    # Test 3200 K warm white
    x_3200, y_3200 = kelvin_to_xy(3200.0)
    res_3200 = matcher.match_cie(x_3200, y_3200, Y=100.0)["ETC Lustr 2"]
    assert res_3200.warning == ""
    # At least 5 emitters active above 2%
    active_3200 = [w for w in res_3200.normalized_weights if w > 0.02]
    assert len(active_3200) >= 5

    # Test 5600 K daylight
    x_5600, y_5600 = kelvin_to_xy(5600.0)
    res_5600 = matcher.match_cie(x_5600, y_5600, Y=100.0)["ETC Lustr 2"]
    assert res_5600.warning == ""
    active_5600 = [w for w in res_5600.normalized_weights if w > 0.02]
    assert len(active_5600) >= 5


def test_continuity_during_cct_sweep() -> None:
    prof = _make_lustr_profile()
    matcher = ColorMatcher([prof])

    kelvins = list(range(2800, 6500, 200))
    prev_weights: list[float] | None = None
    max_step_diff = 0.0

    for k in kelvins:
        x, y = kelvin_to_xy(float(k))
        res = matcher.match_cie(x, y, Y=100.0)["ETC Lustr 2"]
        weights = res.normalized_weights
        if prev_weights is not None:
            step_diff = max(
                abs(w - pw) for w, pw in zip(weights, prev_weights, strict=True)
            )
            max_step_diff = max(max_step_diff, step_diff)
        prev_weights = weights

    # Smooth C^1 variation: no emitter jumps by more than 8% per 200 K step
    assert max_step_diff < 0.08


def test_saturated_primaries_no_false_warning() -> None:
    dev = create_rgbw_definition().instantiate(1, "RGBW", 1, 1)
    assert dev.color_profile is not None
    matcher = ColorMatcher([dev.color_profile])

    for r, g, b in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        res = matcher.match_srgb(r, g, b)["Generic LED RGBW"]
        assert res.warning == ""
        assert max(res.dmx_values) == 255


def test_rgb_only_strategy_on_nled() -> None:
    prof = _make_lustr_profile()
    matcher = ColorMatcher([prof])
    res = matcher.match_srgb(255, 255, 255, strategy="rgb_only")["ETC Lustr 2"]
    d = res.as_normalized_dict()
    assert d["Amber"] == pytest.approx(0.0)
    assert d["Cyan"] == pytest.approx(0.0)
    assert d["Lime"] == pytest.approx(0.0)
    assert d["Indigo"] == pytest.approx(0.0)
    assert d["Red"] > 0.5
    assert d["Green"] > 0.5
    assert d["Blue"] > 0.5
