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
"""Unit tests for Effect model, 10 built-in templates, phase math, and EffectsEngine."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from olc.core.app import CoreApplication
from olc.core.dmx_backend import DMXBackend
from olc.core.effects_engine import (
    EffectsEngine,
    compute_channel_phase_offsets,
    evaluate_waveform,
)
from olc.devices.channel import Channel, ChannelType, FixtureType
from olc.devices.device import LightingDevice
from olc.show.curve import LimitCurve
from olc.show.effect import (
    BUILTIN_EFFECT_TEMPLATES,
    ActiveEffectInstance,
    DistributeDirection,
    EffectDefinition,
    EffectEnvelopeMode,
    EffectLayer,
    EffectMode,
    WaveformType,
)
from olc.show.palette import Palette, PaletteCategory


class _ManualScheduler:
    """Deterministic no-thread timer scheduler for unit testing."""

    def __init__(self) -> None:
        self.active_handles: list[int] = []
        self._next_id = 1

    def timeout_add(
        self,
        interval_ms: int,
        callback: Any,  # noqa: ANN401
    ) -> int:
        _ = (interval_ms, callback)
        handle = self._next_id
        self._next_id += 1
        self.active_handles.append(handle)
        return handle

    def source_remove(self, handle: Any) -> None:  # noqa: ANN401
        if handle in self.active_handles:
            self.active_handles.remove(handle)


def _make_headless_app() -> tuple[CoreApplication, _ManualScheduler]:
    settings = MagicMock()
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    app.backend = DMXBackend(app.lightshow)
    sched = _ManualScheduler()
    app.effects_engine = EffectsEngine(
        app=app, lightshow=app.lightshow, scheduler=sched
    )
    return app, sched


def _patch_moving_head(
    app: CoreApplication,
    fixture_id: int,
    address: int,
    *,
    cmy: bool = False,
) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.MOVING_HEAD,
        label=f"Spot {fixture_id}",
        manufacturer="OLC",
        model="TestSpot",
    )
    dev.add_channel(
        Channel(universe=1, address=address, channel_type=ChannelType.INTENSITY)
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 1,
            channel_type=ChannelType.PAN,
            physical_min=-270.0,
            physical_max=270.0,
            physical_unit="deg",
        )
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 2,
            channel_type=ChannelType.TILT,
            physical_min=-135.0,
            physical_max=135.0,
            physical_unit="deg",
        )
    )
    if cmy:
        dev.add_channel(
            Channel(universe=1, address=address + 3, channel_type=ChannelType.CYAN)
        )
        dev.add_channel(
            Channel(universe=1, address=address + 4, channel_type=ChannelType.MAGENTA)
        )
        dev.add_channel(
            Channel(universe=1, address=address + 5, channel_type=ChannelType.YELLOW)
        )
    else:
        dev.add_channel(
            Channel(universe=1, address=address + 3, channel_type=ChannelType.RED)
        )
        dev.add_channel(
            Channel(universe=1, address=address + 4, channel_type=ChannelType.GREEN)
        )
        dev.add_channel(
            Channel(universe=1, address=address + 5, channel_type=ChannelType.BLUE)
        )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 6,
            channel_type=ChannelType.ZOOM,
            physical_min=5.0,
            physical_max=50.0,
            physical_unit="deg",
        )
    )
    app.lightshow.patch.restore_device(dev)
    return dev


def test_ten_builtin_templates_and_effect_manager_serialization() -> None:
    """Verify all 10 built-in effect templates, CRUD, and JSON round-trip."""
    app, _ = _make_headless_app()
    mgr = app.lightshow.effects

    templates = mgr.list_templates()
    assert len(templates) == 10
    expected_ids = {
        "sine_dimmer",
        "chase_cancan",
        "candle_flicker",
        "circle",
        "figure_8",
        "tilt_wave",
        "fly_in_out",
        "two_color_chase",
        "rainbow",
        "zoom_pulse",
    }
    assert set(BUILTIN_EFFECT_TEMPLATES.keys()) == expected_ids

    for idx, t_id in enumerate(sorted(expected_ids), start=1):
        eff = mgr.create_from_template(t_id, number=idx)
        assert eff.number == float(idx)
        assert eff.template_id == t_id
        assert len(eff.layers) >= 1
        rebuilt = EffectDefinition.from_dict(eff.to_dict())
        assert rebuilt.to_dict() == eff.to_dict()

    assert len(mgr) == 10
    assert mgr.rename(1, "Custom Sine") is True
    eff1 = mgr.get(1)
    assert eff1 is not None and eff1.label == "Custom Sine"

    serialized = mgr.to_list()
    mgr.clear()
    assert len(mgr) == 0
    mgr.from_list(serialized)
    assert len(mgr) == 10
    assert mgr.delete(10) is not None
    assert len(mgr) == 9

    with pytest.raises(ValueError, match="Unknown effect template"):
        mgr.create_from_template("non_existent_fx")


def test_phase_distribution_blocks_wings_groups_and_direction() -> None:
    """Verify Blocks, Wings, Groups, Direction, and channel selection order."""
    channels = [1, 2, 3, 4, 5, 6, 7, 8]

    # 1. Full spread (groups=0): 8 distinct evenly-spaced phases in [0, 1[
    full = compute_channel_phase_offsets(channels, groups=0, blocks=1, wings=1)
    np.testing.assert_allclose(full, np.arange(8) / 8.0)

    # 2. Reversed selection order reverses phase assignment
    rev = compute_channel_phase_offsets(
        list(reversed(channels)), groups=0, blocks=1, wings=1
    )
    assert full[0] == rev[0]  # Channel 8 is now first in the selection

    # 3. Unison (groups=1): all channels at phase 0.0
    unison = compute_channel_phase_offsets(channels, groups=1)
    np.testing.assert_allclose(unison, np.zeros(8))

    # 4. Groups=2 (even/odd alternation): 0.0, 0.5, 0.0, 0.5...
    g2 = compute_channel_phase_offsets(channels, groups=2)
    np.testing.assert_allclose(g2, np.array([0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5]))

    # 5. Blocks=2 (pairs of adjacent fixtures share identical phase)
    b2 = compute_channel_phase_offsets(channels, groups=0, blocks=2)
    np.testing.assert_allclose(
        b2, np.array([0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 0.75, 0.75])
    )

    # 6. Wings=2 (left/right mirror symmetry: ch 1 == ch 8, ch 2 == ch 7, etc.)
    w2 = compute_channel_phase_offsets(channels, groups=0, wings=2)
    np.testing.assert_allclose(
        w2, np.array([0.0, 0.25, 0.5, 0.75, 0.75, 0.5, 0.25, 0.0])
    )
    # Odd fixture count with Wings=2 (5 fixtures: 1==5, 2==4, 3 is center apex)
    w2_odd = compute_channel_phase_offsets([1, 2, 3, 4, 5], groups=0, wings=2)
    assert w2_odd[0] == pytest.approx(w2_odd[4])
    assert w2_odd[1] == pytest.approx(w2_odd[3])

    # 7. Combined Blocks=2 + Wings=2 on 8 fixtures -> [0, 0, 0.5, 0.5, 0.5, 0.5, 0, 0]
    bw = compute_channel_phase_offsets(channels, groups=0, blocks=2, wings=2)
    np.testing.assert_allclose(bw, np.array([0.0, 0.0, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0]))

    # 8. Directions: BACKWARD, BOUNCE, RANDOM
    bwd = compute_channel_phase_offsets(
        [1, 2, 3, 4], direction=DistributeDirection.BACKWARD
    )
    np.testing.assert_allclose(bwd, np.array([0.75, 0.5, 0.25, 0.0]))

    bnc = compute_channel_phase_offsets(
        [1, 2, 3, 4, 5], direction=DistributeDirection.BOUNCE
    )
    assert bnc[0] == pytest.approx(bnc[4])
    assert bnc[1] == pytest.approx(bnc[3])
    assert bnc[2] == pytest.approx(0.5)

    rnd1 = compute_channel_phase_offsets(
        channels, direction=DistributeDirection.RANDOM, effect_seed=42
    )
    rnd2 = compute_channel_phase_offsets(
        channels, direction=DistributeDirection.RANDOM, effect_seed=42
    )
    np.testing.assert_allclose(rnd1, rnd2)
    assert len(set(np.round(rnd1, 4))) > 4


def test_waveforms_including_custom_olc_curve() -> None:
    """Verify all WaveformTypes in RELATIVE and ABSOLUTE modes and OLC Curve link."""
    phases = np.array([0.0, 0.25, 0.5, 0.75], dtype=np.float64)

    sin_rel = evaluate_waveform(WaveformType.SINE, phases, mode=EffectMode.RELATIVE)
    np.testing.assert_allclose(sin_rel, [0.0, 1.0, 0.0, -1.0], atol=1e-7)

    sin_abs = evaluate_waveform(WaveformType.SINE, phases, mode=EffectMode.ABSOLUTE)
    np.testing.assert_allclose(sin_abs, [0.5, 1.0, 0.5, 0.0], atol=1e-7)

    cos_rel = evaluate_waveform(WaveformType.COSINE, phases, mode=EffectMode.RELATIVE)
    np.testing.assert_allclose(cos_rel, [1.0, 0.0, -1.0, 0.0], atol=1e-7)

    tri_rel = evaluate_waveform(WaveformType.TRIANGLE, phases, mode=EffectMode.RELATIVE)
    np.testing.assert_allclose(tri_rel, [0.0, 1.0, 0.0, -1.0], atol=1e-7)

    sq_rel = evaluate_waveform(
        WaveformType.SQUARE, phases, mode=EffectMode.RELATIVE, duty_cycle=0.5
    )
    np.testing.assert_allclose(sq_rel, [1.0, 1.0, -1.0, -1.0])

    pulse_hard = evaluate_waveform(
        WaveformType.PULSE,
        np.array([0.1, 0.2, 0.6]),
        mode=EffectMode.ABSOLUTE,
        duty_cycle=0.5,
        softness=0.0,
    )
    np.testing.assert_allclose(pulse_hard, [1.0, 1.0, 0.0])

    pulse_soft = evaluate_waveform(
        WaveformType.PULSE,
        np.array([0.0, 0.25, 0.5, 0.75]),
        mode=EffectMode.ABSOLUTE,
        duty_cycle=0.5,
        softness=1.0,
    )
    assert pulse_soft[0] == pytest.approx(0.0, abs=1e-6)
    assert pulse_soft[1] == pytest.approx(1.0, abs=1e-6)
    assert pulse_soft[2] == pytest.approx(0.0, abs=1e-6)
    assert pulse_soft[3] == pytest.approx(0.0, abs=1e-6)

    # Custom OLC Curve (LimitCurve capped at 50% -> normalized ~0.498)
    lim_curve = LimitCurve(limit=127)
    curve_abs = evaluate_waveform(
        WaveformType.CURVE,
        np.array([0.0, 0.5, 0.999]),
        mode=EffectMode.ABSOLUTE,
        curve_evaluator=lim_curve.evaluate_normalized,
    )
    assert curve_abs[0] == pytest.approx(0.0, abs=1e-3)
    assert curve_abs[1] == pytest.approx(0.5 * (127.0 / 255.0), abs=1e-2)
    assert curve_abs[2] == pytest.approx(127.0 / 255.0, abs=1e-2)


def test_non_destructive_intensity_modulation_main_fader_and_park() -> None:
    """Verify HTP intensity effects preserve base levels and obey Park."""
    app, sched = _make_headless_app()
    assert app.backend is not None
    dmx = app.backend.dmx
    _patch_moving_head(app, 1, 1)
    _patch_moving_head(app, 2, 10)

    # Set base sequence level to 50% on channels 1 and 2
    dmx.levels["sequence"][0] = 0.5
    dmx.levels["sequence"][1] = 0.5

    eff = app.lightshow.effects.create_from_template("sine_dimmer", number=1)
    eff.cycle_time = 4.0  # Period = 4s
    eff.layers[0].size = 40.0  # +/- 40% around 50% -> [10%..90%]

    app.effects_engine.start_effect(1.0, [1, 2], now=0.0)
    assert len(sched.active_handles) == 1

    # At t = 1.0s (quarter cycle): ch 1 is at +1.0 -> 0.9; ch 2 is at -1.0 -> 0.1
    comp = dmx.get_all_composite_levels()
    assert comp[0] == pytest.approx(0.5, abs=0.5)  # sanity check live clock
    mod = app.effects_engine.apply_intensity_modulation(dmx.levels["sequence"], now=1.0)
    assert mod[0] == pytest.approx(0.9, abs=1e-4)
    assert mod[1] == pytest.approx(0.1, abs=1e-4)

    # Underlying sequence level is completely untouched (non-destructive!)
    assert dmx.levels["sequence"][0] == pytest.approx(0.5)
    assert dmx.levels["sequence"][1] == pytest.approx(0.5)

    # Parked channel must ignore effect oscillation
    app.lightshow.park.park_channel(1, 0.75)
    lvl1, _ = dmx.get_composite_level(0)
    assert lvl1 == pytest.approx(0.75)
    app.lightshow.park.unpark_channel(1)

    # Stopping the effect removes timer and returns composite to exact 0.5 base
    app.effects_engine.stop_all()
    assert len(sched.active_handles) == 0
    assert dmx.get_all_composite_levels()[0] == pytest.approx(0.5)


def test_2d_pan_tilt_circle_axis_rotation_and_base_restoration() -> None:
    """Verify 2D Pan/Tilt circle, 90-deg axis rotation, and base restore."""
    app, _ = _make_headless_app()
    spot1 = _patch_moving_head(app, 1, 1)
    spot1.set_pan_degrees(20.0)
    spot1.set_tilt_degrees(-10.0)

    eff = app.lightshow.effects.create_from_template("circle", number=4)
    eff.cycle_time = 4.0
    eff.layers[0].size = 15.0  # Pan: 15 * sin(2*pi*t/4)
    eff.layers[1].size = 10.0  # Tilt: 10 * cos(2*pi*t/4)

    app.effects_engine.start_effect(4.0, [1], now=0.0)

    # t = 0.0s: sin(0)=0, cos(0)=1 -> Pan = 20.0°, Tilt = -10.0 + 10.0 = 0.0°
    app.effects_engine.tick(now=0.0)
    assert spot1.pan_degrees == pytest.approx(20.0, abs=0.5)
    assert spot1.tilt_degrees == pytest.approx(0.0, abs=0.5)
    assert app.effects_engine.get_base_device_value(1, "pan") == pytest.approx(
        20.0, abs=0.5
    )
    assert app.effects_engine.get_base_device_value(1, "tilt") == pytest.approx(
        -10.0, abs=0.5
    )

    # t = 1.0s (quarter period): sin(pi/2)=1, cos(pi/2)=0 -> Pan = 35.0°, Tilt = -10.0°
    app.effects_engine.tick(now=1.0)
    assert spot1.pan_degrees == pytest.approx(35.0, abs=0.5)
    assert spot1.tilt_degrees == pytest.approx(-10.0, abs=0.5)

    # Rotate 2D axis by +90 degrees: at t=1.0s (d_pan=15, d_tilt=0),
    # rot_pan = 0, rot_tilt = +15 -> Pan = 20.0°, Tilt = +5.0°
    eff.axis_deg = 90.0
    app.effects_engine.tick(now=1.0)
    assert spot1.pan_degrees == pytest.approx(20.0, abs=0.5)
    assert spot1.tilt_degrees == pytest.approx(5.0, abs=0.5)
    eff.axis_deg = 0.0

    # External base position change while effect is running (Focus Palette = 50°)
    spot1.set_pan_degrees(50.0)
    app.effects_engine.tick(now=1.0)
    assert app.effects_engine.get_base_device_value(1, "pan") == pytest.approx(
        50.0, abs=0.5
    )
    assert spot1.pan_degrees == pytest.approx(65.0, abs=0.5)

    # Stopping the effect restores exact unmodulated base (Pan=50.0°, Tilt=-10.0°)
    app.effects_engine.stop_effect(4.0, [1])
    assert spot1.pan_degrees == pytest.approx(50.0, abs=0.5)
    assert spot1.tilt_degrees == pytest.approx(-10.0, abs=0.5)


def test_color_palette_chase_rainbow_cmy_and_fade_by_size() -> None:
    """Verify Two-Color Palette Chase, live cascade, Rainbow CMY, and size fade."""
    app, _ = _make_headless_app()
    rgb_dev = _patch_moving_head(app, 1, 1, cmy=False)
    cmy_dev = _patch_moving_head(app, 2, 20, cmy=True)
    rgb_dev.set_color_srgb(0.2, 0.2, 0.2)

    # Create Color Palette 1 (Pure Red) and Color Palette 2 (Pure Blue)
    app.lightshow.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            1.0,
            "Red",
            device_values={1: {"color": "#FF0000"}},
        )
    )
    app.lightshow.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            2.0,
            "Blue",
            device_values={1: {"color": "#0000FF"}},
        )
    )

    color_events: list[list[int]] = []
    app.subscribe("device.color_changed", lambda chs, *_: color_events.append(chs))

    chase = app.lightshow.effects.create_from_template("two_color_chase", number=8)
    chase.cycle_time = 2.0
    chase.layers[0].softness = 0.0  # crisp snap between CP 1 and CP 2

    app.effects_engine.start_effect(8.0, [1], now=0.0)
    # At t = 0.2s (inside duty_cycle 0.5 -> high_palette CP 2 = Blue)
    app.effects_engine.tick(now=0.2)
    assert rgb_dev.get_preview_rgb() == pytest.approx((0.0, 0.0, 1.0), abs=0.02)
    assert [1] in color_events

    # At t = 1.2s (outside duty_cycle -> low_palette CP 1 = Red)
    app.effects_engine.tick(now=1.2)
    assert rgb_dev.get_preview_rgb() == pytest.approx((1.0, 0.0, 0.0), abs=0.02)

    # Updating Color Palette 1 to Pure Green dynamically updates the running effect!
    pal1 = app.lightshow.palettes.get("color", 1.0)
    assert pal1 is not None
    pal1.device_values[1]["color"] = "#00FF00"
    app.effects_engine.tick(now=1.2)
    assert rgb_dev.get_preview_rgb() == pytest.approx((0.0, 1.0, 0.0), abs=0.02)

    # Rainbow on subtractive CMY fixture
    app.lightshow.effects.create_from_template("rainbow", number=9)
    app.effects_engine.start_effect(9.0, [2], now=0.0)
    app.effects_engine.tick(now=0.0)  # Hue 0.0 = Red -> C=0, M=1, Y=1
    assert cmy_dev.get_preview_rgb() == pytest.approx((1.0, 0.0, 0.0), abs=0.02)

    # Fade-out by size over 2.0 seconds on channel 1
    app.effects_engine.stop_effect(8.0, [1], fade_out=2.0, now=2.0)
    # Halfway through fade-out (t = 3.0s -> size_scale = 0.5): blends 50%
    app.effects_engine.tick(now=3.2)
    mid_rgb = rgb_dev.get_preview_rgb()
    assert mid_rgb is not None
    assert 0.3 < mid_rgb[1] < 0.8

    # End of fade-out (t = 4.1s): effect removed and base color (0.2, 0.2, 0.2) restored
    app.effects_engine.tick(now=4.1)
    assert rgb_dev.get_preview_rgb() == pytest.approx((0.2, 0.2, 0.2), abs=0.02)


def test_tap_tempo_and_instance_serialization() -> None:
    """Verify tap_tempo BPM synchronization and ActiveEffectInstance round-trip."""
    app, _ = _make_headless_app()
    eff = app.lightshow.effects.create_from_template("circle", number=1)
    inst = app.effects_engine.start_effect(
        1.0,
        [1, 2, 3, 4],
        rate_scale=1.5,
        size_scale=0.8,
        groups_override=2,
        blocks_override=2,
        wings_override=2,
        direction_override=DistributeDirection.BOUNCE,
        now=0.0,
    )
    assert inst is not None
    rebuilt = ActiveEffectInstance.from_dict(inst.to_dict())
    assert rebuilt.to_dict() == inst.to_dict()

    # Tap tempo at 120 BPM (0.5s intervals)
    assert app.effects_engine.tap_tempo(1.0, now=10.0) is None
    bpm = app.effects_engine.tap_tempo(1.0, now=10.5)
    assert bpm == pytest.approx(120.0, abs=0.1)
    assert eff.bpm == pytest.approx(120.0, abs=0.1)
    assert eff.cycle_time == pytest.approx(0.5, abs=0.01)


def test_effect_envelope_modes_immediate_rate_and_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify IMMEDIATE, FADE_BY_RATE, FADE_BY_SIZE_AND_RATE, and cascade envelopes."""
    now_box = [0.0]
    monkeypatch.setattr("olc.core.effects_engine.time.monotonic", lambda: now_box[0])
    app, _ = _make_headless_app()

    # 1. IMMEDIATE skips size/rate ramps on both start and stop
    imm = EffectDefinition(
        number=10.0,
        label="Immediate",
        layers=[EffectLayer(parameter="intensity", waveform=WaveformType.SQUARE)],
        entry_mode=EffectEnvelopeMode.IMMEDIATE,
        exit_mode=EffectEnvelopeMode.IMMEDIATE,
    )
    app.lightshow.effects.add(imm)
    inst_imm = app.effects_engine.start_effect(
        10.0, [1, 2], size_scale=1.0, fade_in=2.0, now=0.0
    )
    assert inst_imm is not None
    assert inst_imm.effective_size_scale(0.0) == pytest.approx(1.0)
    assert inst_imm.fade_duration == 0.0
    now_box[0] = 1.0
    app.effects_engine.stop_effect(10.0, fade_out=2.0, now=1.0)
    assert app.effects_engine.get_active_instances() == []

    # 2. FADE_BY_RATE & FADE_BY_SIZE_AND_RATE ramp rate_scale over fade duration
    rated = EffectDefinition(
        number=11.0,
        label="RateRamp",
        layers=[EffectLayer(parameter="intensity", waveform=WaveformType.SINE)],
        entry_mode=EffectEnvelopeMode.FADE_BY_RATE,
        exit_mode=EffectEnvelopeMode.FADE_BY_SIZE_AND_RATE,
    )
    app.lightshow.effects.add(rated)
    now_box[0] = 0.0
    inst_rate = app.effects_engine.start_effect(
        11.0, [3], rate_scale=2.0, size_scale=1.0, fade_in=2.0, now=0.0
    )
    assert inst_rate is not None
    assert inst_rate.effective_size_scale(0.0) == pytest.approx(1.0)
    assert 0.5 < inst_rate.effective_rate_scale(1.0) < 1.5
    assert inst_rate.effective_rate_scale(2.0) == pytest.approx(2.0)

    now_box[0] = 3.0
    app.effects_engine.stop_effect(11.0, fade_out=2.0, now=3.0)
    now_box[0] = 4.0
    app.effects_engine.tick(now=4.0)
    active = app.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].effective_size_scale(4.0) == pytest.approx(0.5, abs=0.01)
    assert 0.8 < active[0].effective_rate_scale(4.0) < 1.2
    now_box[0] = 5.1
    app.effects_engine.tick(now=5.1)
    assert app.effects_engine.get_active_instances() == []

    # 3. cascade=True staggers channel envelopes across phase order
    casc = EffectDefinition(
        number=12.0,
        label="Cascade",
        layers=[EffectLayer(parameter="intensity", waveform=WaveformType.PULSE)],
        entry_mode=EffectEnvelopeMode.FADE_BY_SIZE,
        exit_mode=EffectEnvelopeMode.FADE_BY_SIZE,
        cascade=True,
    )
    app.lightshow.effects.add(casc)
    now_box[0] = 0.0
    inst_c = app.effects_engine.start_effect(
        12.0, [1, 2, 3, 4], size_scale=1.0, fade_in=2.0, now=0.0
    )
    assert inst_c is not None
    thetas = app.effects_engine._compute_instance_thetas(casc, inst_c)
    mid_scales = inst_c.effective_channel_size_scales(1.0, thetas)
    assert mid_scales[0] == pytest.approx(1.0)
    assert mid_scales[-1] == pytest.approx(0.0)
    end_scales = inst_c.effective_channel_size_scales(2.0, thetas)
    assert np.allclose(end_scales, 1.0)

    now_box[0] = 3.0
    app.effects_engine.stop_effect(12.0, fade_out=2.0, now=3.0)
    now_box[0] = 4.0
    mid_out = inst_c.effective_channel_size_scales(4.0, thetas)
    assert mid_out[0] == pytest.approx(0.0)
    assert mid_out[-1] == pytest.approx(1.0)
    now_box[0] = 5.1
    app.effects_engine.tick(now=5.1)
    assert app.effects_engine.get_active_instances() == []
