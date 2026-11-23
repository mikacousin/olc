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

from types import SimpleNamespace

import pytest

from olc.devices.channel import Channel, ChannelType
from olc.devices.color import (
    DEFAULT_D65_SPD,
    SPECTRAL_WAVELENGTHS,
    CIExyY,
    ColorMatcher,
    FilterProfile,
    FixtureColorProfile,
    default_cmy_profile,
    extract_color_profile,
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


def _synthetic_cmy_spectra() -> tuple[
    list[tuple[float, float]],
    list[tuple[float, float]],
    list[tuple[float, float]],
]:
    """Build smooth dichroic transmission curves for Cyan, Magenta, Yellow."""
    wls = SPECTRAL_WAVELENGTHS
    c_curve = [(float(w), 0.95 if w < 580 else 0.05) for w in wls]
    m_curve = [(float(w), 0.05 if 490 <= w <= 585 else 0.95) for w in wls]
    y_curve = [(float(w), 0.05 if w < 495 else 0.95) for w in wls]
    return c_curve, m_curve, y_curve


def test_spectral_cmy_forward_and_solver() -> None:
    """Verify spectral forward model, gamut polygon, and inverse solver."""
    c_spec, m_spec, y_spec = _synthetic_cmy_spectra()
    src_spec = [
        (float(w), float(v))
        for w, v in zip(SPECTRAL_WAVELENGTHS, DEFAULT_D65_SPD, strict=True)
    ]
    profile = FixtureColorProfile(
        fixture_name="Spectral CMY",
        mixing_mode="subtractive",
        filters=[
            FilterProfile("Cyan", CIExyY(0.15, 0.30, 60.0), "ColorSub_C", 1.0, c_spec),
            FilterProfile(
                "Magenta", CIExyY(0.38, 0.175, 28.0), "ColorSub_M", 1.0, m_spec
            ),
            FilterProfile(
                "Yellow", CIExyY(0.455, 0.495, 88.0), "ColorSub_Y", 1.0, y_spec
            ),
        ],
        source_spectrum=src_spec,
    )
    assert profile.has_spectral_filters is True
    assert len(profile.gamut_polygon) == 6

    matcher = ColorMatcher([profile])
    for c_ref, m_ref, y_ref in [
        (0.0, 0.7, 0.8),
        (0.6, 0.0, 0.7),
        (0.75, 0.6, 0.0),
    ]:
        target = profile.evaluate_subtractive(c_ref, m_ref, y_ref).to_xyY()
        res = matcher.match_cie(target.x, target.y, target.Y)["Spectral CMY"]
        assert res.delta_e < 1.5
        assert min(res.normalized_weights) == pytest.approx(0.0, abs=1e-4)
        assert res.normalized_weights == pytest.approx([c_ref, m_ref, y_ref], abs=0.03)

    # Serialization round-trip preserves spectral curves
    restored = FixtureColorProfile.from_dict(profile.to_dict())
    assert restored.has_spectral_filters is True
    assert len(restored.source_spectrum) == 81
    assert len(restored.filters[0].spectral_transmission) == 81


def test_gdtf_filter_measurement_extraction() -> None:
    """Verify extract_color_profile reads GDTF <Filters> and <Measurement>."""
    c_spec, m_spec, y_spec = _synthetic_cmy_spectra()

    def _make_meas(pts: list[tuple[float, float]], scale: float = 1.0) -> object:
        return SimpleNamespace(
            physical=100.0,
            measurement_points=[
                SimpleNamespace(wave_length=w, energy=e * scale) for w, e in pts
            ],
        )

    src_pts = [
        (float(w), float(v))
        for w, v in zip(SPECTRAL_WAVELENGTHS, DEFAULT_D65_SPD, strict=True)
    ]
    gdtf_mock = SimpleNamespace(
        manufacturer="Robolight",
        name="CMY Spot 1000",
        emitters=[
            SimpleNamespace(
                name="White",
                color=SimpleNamespace(x=0.3127, y=0.3290, Y=100.0),
                dominant_wave_length=0.0,
                diode_part="",
                measurements=[_make_meas(src_pts)],
            )
        ],
        filters=[
            SimpleNamespace(
                name="Cyan",
                color=SimpleNamespace(x=0.15, y=0.30, Y=60.0),
                measurements=[_make_meas(c_spec, scale=100.0)],
            ),
            SimpleNamespace(
                name="Magenta",
                color=SimpleNamespace(x=0.38, y=0.175, Y=28.0),
                measurements=[_make_meas(m_spec, scale=100.0)],
            ),
            SimpleNamespace(
                name="Yellow",
                color=SimpleNamespace(x=0.455, y=0.495, Y=88.0),
                measurements=[_make_meas(y_spec, scale=100.0)],
            ),
        ],
        dmx_modes=[],
        color_space=None,
    )
    prof = extract_color_profile(gdtf_mock)
    assert prof.mixing_mode == "subtractive"
    assert prof.has_spectral_filters is True
    assert len(prof.source_spectrum) == 81


def test_cmy_cto_solver_prefers_cto_for_warm_white() -> None:
    """Verify CMY+CTO solver prefers CTO over M+Y for warm white (~3200K)."""
    profile = default_cmy_profile("Spot CMY+CTO", include_cto=True)
    assert profile.has_cto_filter is True
    matcher = ColorMatcher([profile])

    # ~3200K warm white inside CTO reach
    warm_white = profile.evaluate_subtractive(0.0, 0.0, 0.0, cto=0.75).to_xyY()
    res = matcher.match_cie(warm_white.x, warm_white.y, warm_white.Y)["Spot CMY+CTO"]
    assert res.emitter_names == ["Cyan", "Magenta", "Yellow", "CTO"]
    c_v, m_v, y_v, cto_v = res.normalized_weights
    assert res.delta_e < 1.5
    assert cto_v > 0.5
    assert m_v < 0.15
    assert y_v < 0.15
    assert min(c_v, m_v, y_v) == pytest.approx(0.0, abs=1e-4)

    # LightingDevice applies CTO weight to ChannelType.COLOR_TEMP
    dev = LightingDevice(
        fixture_id=3,
        label="Spot CTO",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 20),
            Channel(ChannelType.CYAN, 1, 21),
            Channel(ChannelType.MAGENTA, 1, 22),
            Channel(ChannelType.YELLOW, 1, 23),
            Channel(ChannelType.COLOR_TEMP, 1, 24),
        ],
        color_profile=profile,
    )
    dev.set_color_cie(warm_white.x, warm_white.y, warm_white.Y)
    cto_param = dev.get_parameter_normalized(ChannelType.COLOR_TEMP)
    assert cto_param is not None and cto_param > 0.5
    assert GDTF_ATTRIBUTE_MAP["CTO"] == ChannelType.COLOR_TEMP
