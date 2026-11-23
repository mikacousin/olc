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
"""Unit tests for subtractive CMY CIE color profile, solver, and device integration."""

from __future__ import annotations

import pytest

from olc.devices.channel import Channel, ChannelType
from olc.devices.color import (
    CIExyY,
    ColorMatcher,
    FixtureColorProfile,
    default_cmy_profile,
)
from olc.devices.color_pick.geometry import effective_color_profile, profile_gamut_xy
from olc.devices.color_pick.solver import ColorSolver
from olc.devices.device import FixtureType, LightingDevice
from olc.devices.gdtf import GDTF_ATTRIBUTE_MAP


def test_gdtf_colorsub_mapping() -> None:
    """Verify GDTF subtractive CMY attributes map to CYAN, MAGENTA, YELLOW."""
    assert GDTF_ATTRIBUTE_MAP["ColorSub_C"] == ChannelType.CYAN
    assert GDTF_ATTRIBUTE_MAP["ColorSub_M"] == ChannelType.MAGENTA
    assert GDTF_ATTRIBUTE_MAP["ColorSub_Y"] == ChannelType.YELLOW


def test_cmy_profile_forward_and_hexagonal_gamut() -> None:
    """Verify open white, pure filters, and 6-vertex gamut polygon in CIE xy."""
    profile = default_cmy_profile("Test CMY")
    assert profile.mixing_mode == "subtractive"
    assert profile.emitter_count == 3

    # Open beam (0, 0, 0) equals white point
    w_xyz = profile.evaluate_subtractive(0.0, 0.0, 0.0)
    w_xyy = w_xyz.to_xyY()
    assert w_xyy.x == pytest.approx(profile.white_point.x, abs=1e-4)
    assert w_xyy.y == pytest.approx(profile.white_point.y, abs=1e-4)

    # Pure Cyan filter matches Cyan FilterProfile
    c_xyy = profile.evaluate_subtractive(1.0, 0.0, 0.0).to_xyY()
    assert c_xyy.x == pytest.approx(0.1500, abs=1e-4)
    assert c_xyy.y == pytest.approx(0.3000, abs=1e-4)

    # Gamut has 6 vertices (C, G, Y, R, M, B) and contains white point
    poly = profile_gamut_xy(profile)
    assert len(poly) == 6
    assert profile.contains_xy(profile.white_point.x, profile.white_point.y)

    # Serialization round-trip
    restored = FixtureColorProfile.from_dict(profile.to_dict())
    assert restored.mixing_mode == "subtractive"
    assert len(restored.filters) == 3
    assert restored.gamut_polygon == poly


def test_cmy_solver_roundtrip_and_min_zero_constraint() -> None:
    """Verify inverse CMY solver accuracy, min(c,m,y)==0, and out-of-gamut."""
    profile = default_cmy_profile("Test CMY")
    matcher = ColorMatcher([profile])

    # Round-trip several combinations (open white, primaries, secondaries, pastels)
    for c_ref, m_ref, y_ref in [
        (0.0, 0.0, 0.0),
        (0.7, 0.0, 0.0),
        (0.0, 0.6, 0.0),
        (0.0, 0.0, 0.8),
        (0.0, 0.85, 0.75),  # Reddish
        (0.8, 0.0, 0.7),  # Greenish
        (0.75, 0.65, 0.0),  # Bluish
    ]:
        target_xyy = profile.evaluate_subtractive(c_ref, m_ref, y_ref).to_xyY()
        res = matcher.match_cie(target_xyy.x, target_xyy.y, target_xyy.Y)["Test CMY"]
        assert res.delta_e < 1.5
        assert res.warning == ""
        assert min(res.normalized_weights) == pytest.approx(0.0, abs=1e-4)
        assert res.normalized_weights == pytest.approx([c_ref, m_ref, y_ref], abs=0.02)

    # Out-of-gamut spectral locus point triggers warning and projects onto boundary
    oog = matcher.match_cie(0.7347, 0.2653, 50.0)["Test CMY"]
    assert oog.warning == "out of gamut"
    assert min(oog.normalized_weights) == pytest.approx(0.0, abs=1e-4)


def test_cmy_solver_cache_and_device_integration() -> None:
    """Verify ColorSolver caching and LightingDevice CMY CIE/sRGB/preview."""
    profile = default_cmy_profile("Spot CMY")
    solver = ColorSolver()

    res1 = solver.solve_cie(profile, 0.42, 0.35, 50.0)
    res2 = solver.solve_cie(profile, 0.42, 0.35, 50.0)
    assert res1 is not None and res1 is res2
    assert solver.solves == 1

    channels = [
        Channel(ChannelType.INTENSITY, 1, 1),
        Channel(ChannelType.CYAN, 1, 2),
        Channel(ChannelType.MAGENTA, 1, 3),
        Channel(ChannelType.YELLOW, 1, 4),
    ]
    dev = LightingDevice(
        fixture_id=1,
        label="Spot CMY",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=channels,
        color_profile=profile,
    )
    assert dev.is_subtractive_cmy is True
    assert effective_color_profile(dev) is profile

    # Red-orange target should use Magenta + Yellow with Cyan == 0
    dev.set_color_srgb(1.0, 0.3, 0.0)
    c_lvl = dev.get_emitter_level(ChannelType.CYAN)
    m_lvl = dev.get_emitter_level(ChannelType.MAGENTA)
    y_lvl = dev.get_emitter_level(ChannelType.YELLOW)
    assert c_lvl == pytest.approx(0.0, abs=1e-3)
    assert m_lvl > 0.3
    assert y_lvl > 0.5

    preview = dev.get_preview_rgb()
    assert preview is not None
    assert preview[0] > preview[1] > preview[2]

    # Device without explicit color_profile still gets default_cmy_profile in geometry
    dev_no_prof = LightingDevice(
        fixture_id=2,
        label="Basic CMY",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 10),
            Channel(ChannelType.CYAN, 1, 11),
            Channel(ChannelType.MAGENTA, 1, 12),
            Channel(ChannelType.YELLOW, 1, 13),
        ],
        color_profile=None,
    )
    eff = effective_color_profile(dev_no_prof)
    assert eff is not None
    assert eff.mixing_mode == "subtractive"
    assert isinstance(CIExyY(0.3127, 0.3290, 100.0), CIExyY)
