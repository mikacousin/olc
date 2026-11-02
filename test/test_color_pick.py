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
"""Headless tests for the console-style color picker logic."""
# pylint: disable=missing-function-docstring, too-few-public-methods

from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pytest

from olc.devices import color_pick as cp
from olc.devices.builtin import (
    create_dimmer_definition,
    create_rgb_definition,
    create_rgba_definition,
    create_rgbw_definition,
)
from olc.devices.color import (
    CIExyY,
    EmitterProfile,
    FixtureColorProfile,
    profile_from_emitters,
)
from olc.devices.device import (
    Channel,
    ChannelRange,
    ChannelType,
    FixtureType,
    LightingDevice,
)


def _emitters(dev: LightingDevice) -> dict[ChannelType, float]:
    return dict(dev._base_emitters)  # pylint: disable=protected-access


# ---- conversions -----------------------------------------------------------


def test_kelvin_is_warm_to_cool() -> None:
    warm = cp.kelvin_to_srgb(2700.0)
    mid = cp.kelvin_to_srgb(6500.0)
    cool = cp.kelvin_to_srgb(10000.0)
    assert warm[0] > warm[1] > warm[2]  # red dominant
    assert cool[2] > cool[0]  # blue dominant
    assert min(mid) > 0.95  # near white
    assert max(warm) == pytest.approx(1.0)


def test_kelvin_xy_matches_reference_values() -> None:
    x, y = cp.kelvin_to_xy(6500.0)  # D65 neighbourhood
    assert x == pytest.approx(0.3135, abs=0.002)
    assert y == pytest.approx(0.3236, abs=0.002)
    x, y = cp.kelvin_to_xy(2856.0)  # illuminant A
    assert x == pytest.approx(0.4476, abs=0.003)
    assert y == pytest.approx(0.4074, abs=0.003)


def test_kelvin_duv_tint_shifts_green_and_magenta() -> None:  # pylint: disable=too-many-locals
    x0, y0 = cp.kelvin_duv_to_xy(5600.0, 0.0)
    x_plus, y_plus = cp.kelvin_duv_to_xy(5600.0, 0.03)
    _x_minus, y_minus = cp.kelvin_duv_to_xy(5600.0, -0.03)

    # +Duv shifts toward green (higher y), -Duv shifts toward magenta (lower y)
    assert y_plus > y0 > y_minus
    assert (x_plus, y_plus) != (x0, y0)

    # Check orthogonality in CIE 1960 (u, v) space
    u0, v0 = cp.xy_to_uv(x0, y0)
    up, vp = cp.xy_to_uv(x_plus, y_plus)
    u_lo, v_lo = cp.kelvin_to_uv(5590.0)
    u_hi, v_hi = cp.kelvin_to_uv(5610.0)
    dot = (up - u0) * (u_hi - u_lo) + (vp - v0) * (v_hi - v_lo)
    assert dot == pytest.approx(0.0, abs=1e-5)
    assert math.hypot(up - u0, vp - v0) == pytest.approx(0.03, abs=1e-4)

    rgb_neutral = cp.kelvin_to_srgb(5600.0, 0.0)
    rgb_green = cp.kelvin_to_srgb(5600.0, 0.04)
    rgb_magenta = cp.kelvin_to_srgb(5600.0, -0.04)
    # Green tint boosts green relative to red/blue; magenta tint reduces green
    assert rgb_green[1] >= rgb_neutral[1] > rgb_magenta[1]


def test_xy_srgb_round_trip_and_planckian_locus() -> None:
    for r, g, b in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 1.0)):
        x, y = cp.srgb_to_xy(r, g, b)
        r2, g2, b2 = cp.xy_to_srgb(x, y)
        assert (r2, g2, b2) == pytest.approx((r, g, b), abs=0.02)

    # Black falls back to D65 white point
    assert cp.srgb_to_xy(0.0, 0.0, 0.0) == pytest.approx((0.3127, 0.3290))

    locus = cp.planckian_locus_xy(16)
    assert len(locus) == 16
    assert locus[0][0] > locus[-1][0]  # 1800 K has higher x than 12000 K


@pytest.mark.parametrize(
    "text,expected",
    [
        ("#FF8800", (1.0, 136 / 255, 0.0)),
        ("ff8800", (1.0, 136 / 255, 0.0)),
        ("#f80", (1.0, 136 / 255, 0.0)),
    ],
)
def test_parse_hex_valid(text: str, expected: tuple[float, float, float]) -> None:
    assert cp.parse_hex(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "#12", "#GGGGGG", "#1234567", "red"])
def test_parse_hex_invalid(text: str) -> None:
    assert cp.parse_hex(text) is None


def test_hex_round_trip() -> None:
    for value in ("#000000", "#FFFFFF", "#12AB9F", "#FF8800"):
        parsed = cp.parse_hex(value)
        assert parsed is not None
        assert cp.rgb_to_hex(*parsed) == value


def test_hue_is_kept_for_gray() -> None:
    assert cp.rgb_to_hs(0.5, 0.5, 0.5, hue_hint=0.7) == (0.7, 0.0)
    hue, sat = cp.rgb_to_hs(1.0, 0.0, 0.0)
    assert (hue, sat) == (0.0, 1.0)


# ---- disc ------------------------------------------------------------------


def test_disc_geometry_and_orientation() -> None:
    size = 101
    disc = cp.render_hs_disc(size)
    assert disc.shape == (size, size, 4)
    assert disc[0, 0, 3] == 0  # corners are transparent
    assert disc[size // 2, size // 2, 3] == 255
    # Center is white (saturation 0)
    b, g, r, _a = (int(v) for v in disc[size // 2, size // 2])
    assert min(r, g, b) >= 250
    # Right edge is hue 0 (red); pointer math: hue = atan2(dy, dx) / 2pi
    b, g, r, a = (int(v) for v in disc[size // 2, size - 4])
    assert a == 255 and r > 240 and g < 40 and b < 40
    # Straight down (+y on screen) is hue 0.25 -> chartreuse/green side
    b, g, r, a = (int(v) for v in disc[size - 4, size // 2])
    assert g > 240 and b < 100 and a == 255


def test_disc_matches_pointer_hue_formula() -> None:
    size = 121
    disc = cp.render_hs_disc(size)
    c = size / 2.0
    for angle_deg in (0, 45, 100, 200, 300):
        a = math.radians(angle_deg)
        px = int(c + math.cos(a) * c * 0.8)
        py = int(c + math.sin(a) * c * 0.8)
        b, g, r, _ = (int(v) / 255.0 for v in disc[py, px])
        hue, sat = cp.rgb_to_hs(r, g, b)
        expected = (angle_deg / 360.0) % 1.0
        assert min(abs(hue - expected), 1 - abs(hue - expected)) < 0.02
        assert sat == pytest.approx(0.8, abs=0.04)


def test_render_cie_xy_diagram_horseshoe() -> None:
    size = 100
    diag = cp.render_cie_xy_diagram(size)
    assert diag.shape == (size, size, 4)

    # Top-right corner (x ~ 0.79, y ~ 0.89) is outside the spectral horseshoe
    assert diag[2, size - 2, 3] == 0
    # Bottom-left corner (x ~ 0.01, y ~ 0.01) is also outside
    assert diag[size - 2, 2, 3] == 0

    # D65 white point (x=0.3127, y=0.3290) is well inside the horseshoe
    col_d65 = int((0.3127 / cp.CIE_X_MAX) * size)
    row_d65 = int((1.0 - 0.3290 / cp.CIE_Y_MAX) * size)
    b, g, r, a = (int(v) for v in diag[row_d65, col_d65])
    assert a == 255
    assert min(r, g, b) > 235

    # Clamping outside point (0.78, 0.88) brings it onto the locus boundary
    cx, cy = cp.clamp_xy_to_locus(0.78, 0.88)
    assert (cx, cy) != (0.78, 0.88)
    # Point already inside stays unchanged
    assert cp.clamp_xy_to_locus(0.3127, 0.3290) == pytest.approx((0.3127, 0.3290))


def test_convex_hull_and_profile_gamut() -> None:
    rgb_prof = create_rgb_definition().color_profile
    rgba_prof = create_rgba_definition().color_profile
    assert rgb_prof is not None and rgba_prof is not None

    hull_rgb = cp.profile_gamut_xy(rgb_prof)
    assert len(hull_rgb) == 3
    assert len(cp.profile_gamut_hs(rgb_prof)) == 3

    # RGBW has white inside the RGB triangle -> convex hull still has 3 outer vertices
    rgbw_prof = create_rgbw_definition().color_profile
    assert rgbw_prof is not None
    assert len(cp.profile_gamut_xy(rgbw_prof)) == 3

    # RGBA has amber near the R-G edge -> 3 or 4 hull vertices
    assert len(cp.profile_gamut_xy(rgba_prof)) >= 3


# ---- solver / apply --------------------------------------------------------


def test_solver_matches_direct_device_solve() -> None:
    shared = create_rgba_definition().instantiate(1, "A", 1, 1)
    direct = create_rgba_definition().instantiate(2, "B", 1, 10)
    solver = cp.ColorSolver()

    cp.apply_color_to_devices([shared], 1.0, 136 / 255, 0.0, solver)
    direct.set_color_srgb(1.0, 136 / 255, 0.0)

    for ctype, value in _emitters(direct).items():
        assert _emitters(shared)[ctype] == pytest.approx(value, abs=1e-9)


def test_apply_solves_once_per_profile() -> None:
    fixtures = [
        create_rgbw_definition().instantiate(i, f"W{i}", 1, 1 + 8 * i)
        for i in range(1, 31)
    ]
    fixtures += [
        create_rgba_definition().instantiate(100 + i, f"A{i}", 2, 1 + 8 * i)
        for i in range(1, 11)
    ]
    solver = cp.ColorSolver()

    result = cp.apply_color_to_devices(fixtures, 0.9, 0.3, 0.6, solver)

    assert solver.solves == 2  # one RGBW profile + one RGBA profile
    assert len(result.delta_e) == 40
    assert result.worst_delta_e >= result.mean_delta_e >= 0.0

    cp.apply_color_to_devices(fixtures, 0.9, 0.3, 0.6, solver)
    assert solver.solves == 2  # fully cached on the second pass


def test_cache_is_bounded_and_clearable() -> None:
    dev = create_rgbw_definition().instantiate(1, "W", 1, 1)
    solver = cp.ColorSolver(max_entries=8)
    for i in range(40):
        cp.apply_color_to_devices([dev], i / 40.0, 0.2, 0.4, solver)
    assert len(solver._cache) <= 8  # pylint: disable=protected-access
    solver.clear()
    assert not solver._cache  # pylint: disable=protected-access


def test_builtin_rgb_goes_through_its_profile() -> None:
    led = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    assert led.color_profile is not None
    solver = cp.ColorSolver()
    result = cp.apply_color_to_devices([led], 1.0, 0.0, 0.5, solver)
    assert solver.solves == 1
    assert cp.classify_match(result.delta_e[1]) == "exact"


def test_devices_without_profile_get_rgb_directly() -> None:
    led = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    led.color_profile = None
    solver = cp.ColorSolver()
    result = cp.apply_color_to_devices([led], 1.0, 0.0, 0.5, solver)
    assert solver.solves == 0
    assert result.delta_e == {1: 0.0}
    emitters = _emitters(led)
    assert emitters[ChannelType.RED] == pytest.approx(1.0)
    assert emitters[ChannelType.GREEN] == pytest.approx(0.0)
    assert emitters[ChannelType.BLUE] == pytest.approx(0.5, abs=1e-9)


def test_16bit_and_24bit_color_channels_preserve_sub_8bit_precision() -> None:
    """16-bit and 24-bit color channels preserve sub-8-bit precision."""
    rgb_profile = create_rgb_definition().color_profile
    assert rgb_profile is not None

    # 16-bit RGB fixture (coarse + fine) with physical dimmer
    dev_16 = LightingDevice(
        fixture_id=10,
        label="RGB 16-bit",
        fixture_type=FixtureType.LED_PAR,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 1),
            Channel(ChannelType.RED, 1, 2, fine=False),
            Channel(ChannelType.RED, 1, 3, fine=True),
            Channel(ChannelType.GREEN, 1, 4, fine=False),
            Channel(ChannelType.GREEN, 1, 5, fine=True),
            Channel(ChannelType.BLUE, 1, 6, fine=False),
            Channel(ChannelType.BLUE, 1, 7, fine=True),
        ],
        color_profile=rgb_profile,
    )
    dev_16.set_intensity(1.0)

    # 24-bit RGB fixture (coarse + fine + ultra_fine) with virtual dimmer
    dev_24 = LightingDevice(
        fixture_id=20,
        label="RGB 24-bit",
        fixture_type=FixtureType.LED_PAR,
        channels=[
            Channel(ChannelType.RED, 1, 10, fine=False),
            Channel(ChannelType.RED, 1, 11, fine=True),
            Channel(ChannelType.RED, 1, 12, ultra_fine=True),
            Channel(ChannelType.GREEN, 1, 13, fine=False),
            Channel(ChannelType.GREEN, 1, 14, fine=True),
            Channel(ChannelType.GREEN, 1, 15, ultra_fine=True),
            Channel(ChannelType.BLUE, 1, 16, fine=False),
            Channel(ChannelType.BLUE, 1, 17, fine=True),
            Channel(ChannelType.BLUE, 1, 18, ultra_fine=True),
        ],
        color_profile=rgb_profile,
    )
    dev_24.set_intensity(1.0)

    solver = cp.ColorSolver()
    # Two colors within the same 8-bit bucket (both round to 100 in 0..255)
    c1 = 100.15 / 255.0
    c2 = 100.40 / 255.0
    assert cp.to_8bit(c1) == cp.to_8bit(c2) == 100

    cp.apply_color_to_devices([dev_16, dev_24], c1, 0.0, 0.0, solver)
    r16_1 = (dev_16.channels[1].value << 8) | dev_16.channels[2].value
    r24_1 = (
        (dev_24.channels[0].value << 16)
        | (dev_24.channels[1].value << 8)
        | dev_24.channels[2].value
    )

    cp.apply_color_to_devices([dev_16, dev_24], c2, 0.0, 0.0, solver)
    r16_2 = (dev_16.channels[1].value << 8) | dev_16.channels[2].value
    r24_2 = (
        (dev_24.channels[0].value << 16)
        | (dev_24.channels[1].value << 8)
        | dev_24.channels[2].value
    )

    assert r16_2 > r16_1
    assert r24_2 > r24_1


def test_dimmer_without_color_is_not_reported() -> None:
    # Callers filter non color-capable devices; a bare dimmer yields no match.
    dimmer = create_dimmer_definition().instantiate(1, "D", 1, 1)
    assert getattr(dimmer, "color_profile", None) is None


@pytest.mark.parametrize(
    "delta_e,warning,expected",
    [
        (0.2, "", "exact"),
        (1.5, "", "close"),
        (4.0, "", "approx"),
        (9.0, "", "out"),
        (0.5, "out of gamut — brightness reduced", "out"),
    ],
)
def test_classify_match(delta_e: float, warning: str, expected: str) -> None:
    assert cp.classify_match(delta_e, warning) == expected


# ---- throttle --------------------------------------------------------------


class _FakeLoop:
    """Deterministic clock + scheduler to test Throttle without GLib."""

    def __init__(self) -> None:
        self.now = 0.0
        self.timers: dict[int, tuple[float, Callable[[], bool]]] = {}
        self._next = 1

    def clock(self) -> float:
        return self.now

    def schedule(self, delay_ms: int, fn: Callable[[], bool]) -> int:
        handle = self._next
        self._next += 1
        self.timers[handle] = (self.now + delay_ms / 1000.0, fn)
        return handle

    def cancel(self, handle: int) -> None:
        self.timers.pop(handle, None)

    def advance(self, seconds: float) -> None:
        target = self.now + seconds
        while True:
            due = [(t, h) for h, (t, _f) in self.timers.items() if t <= target]
            if not due:
                break
            t, h = min(due)
            self.now = t
            _t, fn = self.timers.pop(h)
            fn()
        self.now = target


def _throttle(loop: _FakeLoop, out: list, interval_ms: int = 33) -> cp.Throttle:
    return cp.Throttle(
        lambda *a: out.append(a), interval_ms, loop.schedule, loop.cancel, loop.clock
    )


def test_throttle_fires_first_event_immediately() -> None:
    loop, out = _FakeLoop(), []
    th = _throttle(loop, out)
    th.submit(1)
    assert out == [(1,)]


def test_throttle_coalesces_burst_and_keeps_latest() -> None:
    loop, out = _FakeLoop(), []
    th = _throttle(loop, out)
    th.submit(1)
    for i in range(2, 12):
        loop.advance(0.002)
        th.submit(i)
    assert out == [(1,)]  # still inside the interval
    loop.advance(0.05)
    assert out == [(1,), (11,)]  # only the latest value delivered
    loop.advance(1.0)
    assert out == [(1,), (11,)]  # nothing left pending


def test_throttle_rate_is_bounded() -> None:
    loop, out = _FakeLoop(), []
    th = _throttle(loop, out, interval_ms=33)
    for _ in range(1000):  # 1 kHz pointer for 1 s
        th.submit(len(out))
        loop.advance(0.001)
    loop.advance(0.1)
    assert len(out) <= 32  # ~30 Hz, never the 1000 events


def test_throttle_flush_delivers_exact_final_value() -> None:
    loop, out = _FakeLoop(), []
    th = _throttle(loop, out)
    th.submit("a")
    th.submit("b")
    th.flush()
    assert out == [("a",), ("b",)]
    loop.advance(1.0)
    assert out == [("a",), ("b",)]  # timer was cancelled, no duplicate


def test_throttle_cancel_discards_pending() -> None:
    loop, out = _FakeLoop(), []
    th = _throttle(loop, out)
    th.submit("a")
    th.submit("b")
    th.cancel()
    loop.advance(1.0)
    assert out == [("a",)]


def test_throttle_idle_then_event_is_immediate_again() -> None:
    loop, out = _FakeLoop(), []
    th = _throttle(loop, out)
    th.submit(1)
    loop.advance(1.0)
    th.submit(2)
    assert out == [(1,), (2,)]


def test_numpy_disc_is_deterministic() -> None:
    assert np.array_equal(cp.render_hs_disc(40), cp.render_hs_disc(40))


# ---- gamut warning ----------------------------------------------------------


@pytest.mark.parametrize(
    "rgb", [(1.0, 0.0, 0.0), (1.0, 136 / 255, 0.0), (1.0, 1.0, 1.0)]
)
def test_saturated_colors_do_not_warn_on_rgb_fixture(
    rgb: tuple[float, float, float],
) -> None:
    # NNLS overshoots by ~1e-4 here: numerical noise, not a gamut problem.
    dev = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    assert dev.color_profile is not None
    match = cp.ColorSolver().solve(dev.color_profile, *rgb)
    assert match is not None
    assert match.warning == ""
    assert cp.classify_match(match.delta_e, match.warning) == "exact"


def test_real_gamut_overshoot_still_warns() -> None:
    # A color truly outside the fixture's gamut polygon must warn.
    narrow_profile = profile_from_emitters(
        "Narrow",
        [
            ("Red", 0.50, 0.35, 25.0, 610.0),
            ("Green", 0.35, 0.45, 60.0, 540.0),
            ("Blue", 0.25, 0.20, 15.0, 480.0),
        ],
    )
    match = cp.ColorSolver().solve(narrow_profile, 0.0, 1.0, 0.0)
    assert match is not None
    assert "out of gamut" in match.warning
    assert match.delta_e > 0.5


def test_rgba_white_no_longer_warns_false_out_of_gamut() -> None:
    # RGBA white is inside the physical gamut and must not trigger false warnings.
    dev = create_rgba_definition().instantiate(1, "RGBA", 1, 1)
    assert dev.color_profile is not None
    match = cp.ColorSolver().solve(dev.color_profile, 1.0, 1.0, 1.0)
    assert match is not None
    assert match.warning == ""
    assert match.delta_e < 0.2
    assert cp.classify_match(match.delta_e, match.warning) == "exact"


def test_partial_gdtf_profile_and_lime_emitter() -> None:
    """Fixtures with partial <Emitters> (e.g. only Lime) get RGB completed."""
    partial_profile = FixtureColorProfile(
        fixture_name="RGBL Partial",
        emitters=[EmitterProfile("Lime", CIExyY(0.3225, 0.3870, 100.0))],
    )
    dev = LightingDevice(
        fixture_id=1,
        label="RGBL",
        fixture_type=FixtureType.LED_PAR,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 1),
            Channel(ChannelType.RED, 1, 2),
            Channel(ChannelType.GREEN, 1, 3),
            Channel(ChannelType.BLUE, 1, 4),
            Channel(ChannelType.LIME, 1, 5),
        ],
        color_profile=partial_profile,
    )
    dev.set_intensity(1.0)
    eff = cp.effective_color_profile(dev)
    assert eff is not None
    assert [e.name for e in eff.emitters] == ["Red", "Green", "Blue", "Lime"]
    assert len(cp.device_gamut_xy(dev)) == 3
    assert len(cp.device_emitters_xy(dev)) == 4

    results = cp.apply_color_to_devices([dev], 0.5, 1.0, 0.2, cp.ColorSolver())
    assert len(results.delta_e) == 1
    assert any(ch.value > 0 for ch in dev.channels[1:])


def test_solver_strategies_spectral_punch_rgb_only() -> None:
    """Verify spectral, punch (max brightness), and rgb_only solver strategies."""
    rgbw = create_rgbw_definition().instantiate(1, "RGBW", 1, 1)
    assert rgbw.color_profile is not None
    solver = cp.ColorSolver()

    # 1. rgb_only keeps White at 0 even for pure white (1.0, 1.0, 1.0)
    res_rgb_only = solver.solve(rgbw.color_profile, 1.0, 1.0, 1.0, strategy="rgb_only")
    assert res_rgb_only is not None
    norm_rgb = res_rgb_only.as_normalized_dict()
    assert norm_rgb["White"] == pytest.approx(0.0, abs=1e-6)
    assert norm_rgb["Red"] == pytest.approx(1.0, abs=1e-2)
    assert norm_rgb["Green"] == pytest.approx(1.0, abs=1e-2)
    assert norm_rgb["Blue"] == pytest.approx(1.0, abs=1e-2)

    # 2. punch drives both RGB and White higher than spectral for white
    res_spectral = solver.solve(rgbw.color_profile, 1.0, 1.0, 1.0, strategy="spectral")
    res_punch = solver.solve(rgbw.color_profile, 1.0, 1.0, 1.0, strategy="punch")
    assert res_spectral is not None and res_punch is not None
    assert res_punch.achieved_xyz.Y > res_spectral.achieved_xyz.Y
    norm_punch = res_punch.as_normalized_dict()
    assert norm_punch["White"] > 0.9
    assert norm_punch["Red"] > 0.9


def test_set_emitter_level_updates_cie_and_dmx_16_24bit() -> None:
    """Direct emitter fader adjustment updates 16-bit DMX and forward CIE/sRGB."""
    rgba_prof = create_rgba_definition().color_profile
    dev = LightingDevice(
        fixture_id=1,
        label="RGBA 16b",
        fixture_type=FixtureType.LED_PAR,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 1),
            Channel(ChannelType.RED, 1, 2, fine=False),
            Channel(ChannelType.RED, 1, 3, fine=True),
            Channel(ChannelType.GREEN, 1, 4, fine=False),
            Channel(ChannelType.GREEN, 1, 5, fine=True),
            Channel(ChannelType.BLUE, 1, 6, fine=False),
            Channel(ChannelType.BLUE, 1, 7, fine=True),
            Channel(ChannelType.AMBER, 1, 8, fine=False),
            Channel(ChannelType.AMBER, 1, 9, fine=True),
        ],
        color_profile=rgba_prof,
    )
    dev.set_intensity(1.0)
    dev.set_color_srgb(0.0, 0.0, 0.0)
    dev.set_emitter_level(ChannelType.AMBER, 0.75)

    assert dev.get_emitter_level(ChannelType.AMBER) == pytest.approx(0.75)
    amber_16 = (dev.channels[7].value << 8) | dev.channels[8].value
    assert amber_16 == round(0.75 * 65535.0)
    # Forward CIE synthesis matches Amber chromaticity (0.59, 0.40)
    assert dev.color_cie.x == pytest.approx(0.59, abs=0.01)
    assert dev.color_cie.y == pytest.approx(0.40, abs=0.01)
    assert dev.color_srgb.r > dev.color_srgb.g > dev.color_srgb.b


def test_relative_color_shift_hs() -> None:
    """shift_color_hs shifts hue circularly and clamps saturation."""
    red: cp.RGB = (1.0, 0.0, 0.0)
    blue: cp.RGB = (0.0, 0.0, 1.0)
    # Shift by +1/3 turn (+120 deg): Red -> Green, Blue -> Red
    r_shifted = cp.shift_color_hs(red, 1.0 / 3.0, 0.0)
    b_shifted = cp.shift_color_hs(blue, 1.0 / 3.0, 0.0)
    assert r_shifted == pytest.approx((0.0, 1.0, 0.0), abs=1e-4)
    assert b_shifted == pytest.approx((1.0, 0.0, 0.0), abs=1e-4)


def test_fan_colors_to_devices_short_and_rainbow() -> None:
    """fan_colors_to_devices spreads distinct colors across fixtures."""
    devs = [
        create_rgb_definition().instantiate(i, f"P{i}", 1, 1 + 4 * i)
        for i in range(1, 5)
    ]
    solver = cp.ColorSolver()
    outcome = cp.fan_colors_to_devices(
        devs, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), solver, mode="hs_short"
    )
    assert len(outcome.delta_e) == 4
    distinct_hex = {
        cp.rgb_to_hex(d.color_srgb.r, d.color_srgb.g, d.color_srgb.b) for d in devs
    }
    assert len(distinct_hex) == 4

    # Rainbow fan when start == end still produces 4 distinct hues
    cp.fan_colors_to_devices(
        devs, (1.0, 0.0, 0.0), (1.0, 0.0, 0.0), solver, mode="hs_long"
    )
    rainbow_hex = {
        cp.rgb_to_hex(d.color_srgb.r, d.color_srgb.g, d.color_srgb.b) for d in devs
    }
    assert len(rainbow_hex) == 4


def test_color_wheel_auto_snap() -> None:
    """Spot fixture with COLOR_WHEEL ranges snaps to the closest slot."""
    wheel_ch = Channel(
        ChannelType.COLOR_WHEEL,
        1,
        1,
        ranges=[
            ChannelRange("Open", ChannelType.COLOR_WHEEL, 0, 19, snap_value=0),
            ChannelRange("Red", ChannelType.COLOR_WHEEL, 20, 39, snap_value=25),
            ChannelRange("Green", ChannelType.COLOR_WHEEL, 40, 59, snap_value=45),
            ChannelRange("Blue", ChannelType.COLOR_WHEEL, 60, 79, snap_value=65),
        ],
    )
    spot = LightingDevice(
        fixture_id=99,
        label="Spot Wheel",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[wheel_ch],
    )
    slots = cp.extract_color_wheel_slots(spot)
    assert len(slots) == 4

    solver = cp.ColorSolver()
    # Target near Red -> snaps to Red slot (DMX 25)
    cp.apply_color_to_devices([spot], 0.95, 0.05, 0.05, solver)
    assert wheel_ch.value == 25
    assert spot.color_srgb.r == pytest.approx(1.0)
    assert spot.color_srgb.g == pytest.approx(0.0)

    # Target near Blue -> snaps to Blue slot (DMX 65)
    cp.apply_color_to_devices([spot], 0.0, 0.1, 0.95, solver)
    assert wheel_ch.value == 65


def test_gel_library_lookup_and_search() -> None:
    """Verify lookup by exact code, bare number, name substring, and manufacturer."""
    l201 = cp.find_gel("L201")
    assert l201 is not None and l201.code == "L201"
    assert l201.name == "Full C.T. Blue"

    # Lookup by bare number without leading 'L' or '0'
    by_num = cp.find_gel("201")
    assert by_num == l201
    l021 = cp.find_gel("21")
    assert l021 is not None and l021.code in ("L021", "R21")

    # Lookup by name substring
    congo = cp.filter_gels("congo")
    assert len(congo) >= 2
    assert {g.code for g in congo} >= {"L181", "R382"}

    # Filter by manufacturer
    rosco_only = cp.filter_gels("", manufacturer="Rosco")
    assert rosco_only and all(g.manufacturer == "Rosco" for g in rosco_only)


def test_evaluate_gel_feasibility_on_profiles() -> None:
    """Verify evaluate_gel_for_profile returns valid ΔE and match level."""
    rgbw_prof = create_rgbw_definition().color_profile
    solver = cp.ColorSolver()
    gel = cp.find_gel("L201")
    assert gel is not None

    de, _warn, level = cp.evaluate_gel_for_profile(gel, rgbw_prof, solver)
    assert de >= 0.0
    assert level in ("exact", "close", "approx", "out")

    # None profile -> exact (0.0)
    assert cp.evaluate_gel_for_profile(gel, None, solver) == (0.0, "", "exact")


def test_device_gamut_hs_boundary_sampling() -> None:
    """Device gamut boundary in HS space samples edges to follow the outer circle."""
    rgb_dev = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    pts = cp.device_gamut_hs(rgb_dev, samples_per_edge=16)
    assert len(pts) == 48
    sats = [s for _, s in pts]
    assert min(sats) > 0.99
    assert max(sats) <= 1.0001
    # Yellow (hue ~ 1/6 ~ 0.166) stays at s ~ 1.0 instead of Cartesian chord dip (0.5)
    yellow_pts = [s for h, s in pts if 0.14 <= h <= 0.19]
    assert yellow_pts
    for s in yellow_pts:
        assert s > 0.99


def test_color_solver_solve_cie_out_of_gamut() -> None:
    """Solving CIE (x, y) outside fixture gamut returns large delta_e and warning."""
    rgb_dev = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    profile = cp.effective_color_profile(rgb_dev)
    assert profile is not None
    solver = cp.ColorSolver()

    # D65 white point (in gamut)
    match_in = solver.solve_cie(profile, 0.3127, 0.3290)
    assert match_in is not None
    assert match_in.delta_e < 1.0
    assert not match_in.warning

    # Saturated laser green (outside sRGB gamut)
    match_out = solver.solve_cie(profile, 0.10, 0.80)
    assert match_out is not None
    assert match_out.delta_e > 50.0
    assert match_out.warning == "out of gamut — brightness reduced"


def test_apply_color_cie_to_devices() -> None:
    """apply_color_cie_to_devices updates targets and reports out-of-gamut correctly."""
    rgb_dev = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    solver = cp.ColorSolver()

    # Apply out-of-gamut chromaticity
    res_out = cp.apply_color_cie_to_devices([rgb_dev], 0.10, 0.80, solver)
    assert res_out.delta_e[1] > 50.0
    assert res_out.worst_delta_e > 50.0
    assert res_out.warning == "out of gamut — brightness reduced"
    assert rgb_dev.color_cie.x == pytest.approx(0.10, abs=1e-4)
    assert rgb_dev.color_cie.y == pytest.approx(0.80, abs=1e-4)

    # Apply in-gamut chromaticity
    res_in = cp.apply_color_cie_to_devices([rgb_dev], 0.3127, 0.3290, solver)
    assert res_in.delta_e[1] < 1.0
    assert res_in.worst_delta_e < 1.0
    assert not res_in.warning


def test_cie_chromaticity_gamut_behavior_rgb_vs_rgba() -> None:
    """CIE chromaticities evaluate exact on primaries and respect gamut."""
    rgb = create_rgb_definition().instantiate(1, "RGB", 1, 1)
    rgba = create_rgba_definition().instantiate(2, "RGBA", 1, 10)
    solver = cp.ColorSolver()

    # Saturated Red primary (0.64, 0.33) -> exact on RGB
    res_red = cp.apply_color_cie_to_devices([rgb], 0.640, 0.330, solver)
    assert res_red.delta_e[1] < 0.1
    assert not res_red.warning

    # Saturated Green primary (0.30, 0.60) -> exact on RGB
    res_green = cp.apply_color_cie_to_devices([rgb], 0.300, 0.600, solver)
    assert res_green.delta_e[1] < 0.1
    assert not res_green.warning

    # Saturated Blue primary (0.15, 0.06) -> exact on RGB
    res_blue = cp.apply_color_cie_to_devices([rgb], 0.150, 0.060, solver)
    assert res_blue.delta_e[1] < 0.1
    assert not res_blue.warning

    # Saturated Amber point (0.56, 0.40):
    # Outside standard sRGB triangle -> out-of-gamut for RGB
    res_amber_rgb = cp.apply_color_cie_to_devices([rgb], 0.560, 0.400, solver)
    assert res_amber_rgb.delta_e[1] > 2.0
    assert "out of gamut" in res_amber_rgb.warning

    # Inside RGBA quad (has 590nm Amber emitter) -> exact for RGBA
    res_amber_rgba = cp.apply_color_cie_to_devices([rgba], 0.560, 0.400, solver)
    assert res_amber_rgba.delta_e[2] < 0.1
    assert not res_amber_rgba.warning
