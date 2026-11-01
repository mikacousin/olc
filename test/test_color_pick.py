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
from olc.devices.device import Channel, ChannelType, FixtureType, LightingDevice


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
    # RGBA white needs ~103 % of the emitters: a real (small) brightness loss.
    dev = create_rgba_definition().instantiate(1, "RGBA", 1, 1)
    assert dev.color_profile is not None
    match = cp.ColorSolver().solve(dev.color_profile, 1.0, 1.0, 1.0)
    assert match is not None
    assert "out of gamut" in match.warning
    assert match.delta_e > 0.5
