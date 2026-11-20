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
"""Unit tests for palette refs, IFCB tracking, transition events, CMY, snapshots."""

# pylint: disable=protected-access, missing-function-docstring

from __future__ import annotations

import typing
from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

import pytest

from olc.actions import register_all_actions
from olc.core.app import CoreApplication
from olc.core.channel_snapshot import (
    build_live_channel_snapshot,
    build_step_channel_snapshot,
    format_family_readout,
    format_short_palette_ref,
)
from olc.core.crossfade import CrossFade
from olc.core.dmx_backend import DMXBackend
from olc.core.parser.executor import CommandExecutor
from olc.core.parser.parser import CommandParser
from olc.core.tracking import TrackingDisplayState, TrackingEngine
from olc.devices.builtin import create_rgb_definition
from olc.devices.channel import Channel, ChannelType, FixtureType
from olc.devices.device import LightingDevice
from olc.devices.fixture import ChannelDefinition, DmxModeDefinition, FixtureDefinition
from olc.show.cue import Cue
from olc.show.palette import Palette, PaletteCategory
from olc.show.sequence import Sequence
from olc.show.sequence_threads import (
    ThreadGo,
    ThreadGoBack,
    _capture_device_states,
    _interpolate_device_states,
)
from olc.show.step import Step


def _make_app() -> CoreApplication:
    settings = MagicMock()
    settings.get_double.return_value = 2.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    register_all_actions(app.action_registry)
    app.backend = DMXBackend(app.lightshow)
    app.lightshow.patch.patch_empty()
    return app


def _make_cmy_spot_def() -> FixtureDefinition:
    mode = DmxModeDefinition(
        name="7ch",
        channel_defs=[
            ChannelDefinition(channel_type=ChannelType.INTENSITY, offset=0),
            ChannelDefinition(
                channel_type=ChannelType.PAN,
                offset=1,
                default_value=128,
                physical_min=-270.0,
                physical_max=270.0,
                physical_unit="°",
            ),
            ChannelDefinition(
                channel_type=ChannelType.TILT,
                offset=2,
                default_value=128,
                physical_min=-135.0,
                physical_max=135.0,
                physical_unit="°",
            ),
            ChannelDefinition(channel_type=ChannelType.CYAN, offset=3, default_value=0),
            ChannelDefinition(
                channel_type=ChannelType.MAGENTA, offset=4, default_value=0
            ),
            ChannelDefinition(
                channel_type=ChannelType.YELLOW, offset=5, default_value=0
            ),
            ChannelDefinition(
                channel_type=ChannelType.ZOOM,
                offset=6,
                default_value=0,
                physical_min=10.0,
                physical_max=50.0,
                physical_unit="°",
            ),
        ],
    )
    return FixtureDefinition(
        manufacturer="Generic",
        model="CMY Spot",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[mode],
    )


def _make_7led_par() -> LightingDevice:
    chans = [
        Channel(ChannelType.RED, universe=1, address=1),
        Channel(ChannelType.GREEN, universe=1, address=2),
        Channel(ChannelType.BLUE, universe=1, address=3),
        Channel(ChannelType.WHITE, universe=1, address=4),
        Channel(ChannelType.AMBER, universe=1, address=5),
        Channel(ChannelType.CYAN, universe=1, address=6),
        Channel(ChannelType.LIME, universe=1, address=7),
        Channel(ChannelType.INDIGO, universe=1, address=8),
    ]
    return LightingDevice(
        fixture_id=10,
        label="7LED",
        fixture_type=FixtureType.LED_PAR,
        channels=chans,
    )


def test_cmy_subtractive_preview_and_non_regression() -> None:
    app = _make_app()
    cmy_def = _make_cmy_spot_def()
    dev = app.lightshow.patch.patch_device(1, cmy_def, 1, 1, label="Spot CMY")

    assert dev.is_subtractive_cmy is True
    assert dev.has_color_capability is True
    assert dev.uses_virtual_dimmer is False
    assert dev.get_preview_rgb() == (1.0, 1.0, 1.0)

    # Set cyan/green mix via sRGB (r=0, g=1, b=0.5 -> C=1, M=0, Y=0.5)
    dev.set_color_srgb(0.0, 1.0, 0.5)
    c_ch = dev.get_channel(ChannelType.CYAN)
    m_ch = dev.get_channel(ChannelType.MAGENTA)
    y_ch = dev.get_channel(ChannelType.YELLOW)
    assert c_ch is not None and c_ch.value == 255
    assert m_ch is not None and m_ch.value == 0
    assert y_ch is not None and y_ch.value == 128
    preview = dev.get_preview_rgb()
    assert preview is not None
    assert preview[0] == pytest.approx(0.0, abs=0.01)
    assert preview[1] == pytest.approx(1.0, abs=0.01)
    assert preview[2] == pytest.approx(127 / 255.0, abs=0.01)

    # Direct normalized CMY channels update preview
    dev.set_parameter_normalized(ChannelType.CYAN, 0.5)
    dev.set_parameter_normalized(ChannelType.MAGENTA, 0.25)
    dev.set_parameter_normalized(ChannelType.YELLOW, 0.0)
    assert dev.get_preview_rgb() == pytest.approx((0.5, 0.75, 1.0), abs=0.01)

    # Home color restores open white (1, 1, 1)
    dev.home("color")
    assert dev.get_preview_rgb() == (1.0, 1.0, 1.0)

    # Multi-emitter additive LED fixture stays additive
    nled = _make_7led_par()
    assert nled.is_subtractive_cmy is False
    assert nled.uses_virtual_dimmer is True


def test_live_palette_refs_partial_break_undo_redo_and_record_update() -> None:
    app = _make_app()
    pm = app.lightshow.patch
    mh_def = _make_cmy_spot_def()
    pm.patch_device(1, mh_def, 1, 1, label="Spot 1")

    fp1 = Palette(
        category=PaletteCategory.FOCUS,
        number=1.0,
        text="Downstage",
        device_values={1: {"pan": 45.0, "tilt": 20.0}},
    )
    cp2 = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Steel Blue",
        device_values={1: {"color": "#4488ff"}},
    )
    bp1 = Palette(
        category=PaletteCategory.BEAM,
        number=1.0,
        text="Narrow",
        device_values={1: {"zoom": 14.0}},
    )
    app.lightshow.palettes.add(fp1)
    app.lightshow.palettes.add(cp2)
    app.lightshow.palettes.add(bp1)

    app.action_registry.execute("palette.apply", "focus", 1.0, channels=[1])
    app.action_registry.execute("palette.apply", "color", 2.0, channels=[1])
    app.action_registry.execute("palette.apply", "beam", 1.0, channels=[1])

    assert app.live_state.get_palette_ref(1, "pan") == ("focus", 1.0)
    assert app.live_state.get_palette_ref(1, "tilt") == ("focus", 1.0)
    assert app.live_state.get_palette_ref(1, "color") == ("color", 2.0)
    assert app.live_state.get_palette_ref(1, "zoom") == ("beam", 1.0)

    # Record Preset 10 from live should preserve palette refs
    res_pr = typing.cast(
        dict[str, typing.Any],
        app.action_registry.execute("palette.record", "preset", 10.0, "Look 10", [1]),
    )
    preset10 = res_pr["palette"]
    assert preset10.palette_refs[1]["color"] == ("color", 2.0)
    assert preset10.palette_refs[1]["pan"] == ("focus", 1.0)

    # Manual color change breaks only Color ref; Focus and Beam stay intact
    app.action_registry.execute("device.set_color", 1.0, 0.5, 0.0, channels=[1])
    assert app.live_state.get_palette_ref(1, "color") is None
    assert app.live_state.is_param_manual(1, "color") is True
    assert app.live_state.get_palette_ref(1, "pan") == ("focus", 1.0)
    assert app.live_state.get_palette_ref(1, "zoom") == ("beam", 1.0)

    # Undo restores Color ref, Redo breaks it again
    app.history.undo()
    assert app.live_state.get_palette_ref(1, "color") == ("color", 2.0)
    app.history.redo()
    assert app.live_state.get_palette_ref(1, "color") is None

    # Undo back to having CP 2 cleanly before partial Focus test
    app.history.undo()
    assert app.live_state.get_palette_ref(1, "color") == ("color", 2.0)

    # Adjust only Pan -> breaks pan, keeps tilt -> Focus ref becomes partial (FP 1+)
    app.action_registry.execute("device.adjust_pan_tilt", pan_delta=5.0, channels=[1])
    snap_partial = build_live_channel_snapshot(app, 1)
    assert snap_partial.focus.palette_ref is not None
    assert snap_partial.focus.palette_ref.short_ref == "FP 1"
    assert snap_partial.focus.palette_ref.is_partial is True
    assert format_family_readout(snap_partial.focus, "ref") == "FP 1+"

    # Undo pan adjustment -> Focus ref is complete again
    app.history.undo()
    snap_full = build_live_channel_snapshot(app, 1)
    assert snap_full.focus.palette_ref is not None
    assert snap_full.focus.palette_ref.is_partial is False

    # Record Cue 1 while active, break Color manually and Record Cue 2
    app.action_registry.execute("channel.set_level", 1, 0.9)
    parser = CommandParser()
    executor = CommandExecutor(app)
    assert executor.execute(parser.parse("RECORD CUE 1")).success is True

    cue1 = app.lightshow.cues.get(1.0, 1)
    assert cue1 is not None
    assert cue1.palette_refs[1]["color"] == ("color", 2.0)
    assert cue1.palette_refs[1]["pan"] == ("focus", 1.0)
    assert cue1.palette_refs[1]["zoom"] == ("beam", 1.0)

    # Load Cue 1, then manually change color and RECORD CUE 2
    main_pb = app.lightshow.main_playback
    main_pb.load_step(1)
    app.live_state.clear_channel(1)
    app.action_registry.execute("device.set_color", 0.2, 0.9, 0.1, channels=[1])
    assert executor.execute(parser.parse("RECORD CUE 2")).success is True
    cue2 = app.lightshow.cues.get(2.0, 1)
    assert cue2 is not None
    assert "color" not in cue2.palette_refs.get(1, {})
    assert cue2.palette_refs.get(1, {}).get("pan") == ("focus", 1.0)


def test_sneak_device_color_timed_and_instant_restores_cue_and_ref() -> None:
    app = _make_app()
    pm = app.lightshow.patch
    dev = pm.patch_device(1, create_rgb_definition(), 1, 1, label="LED 1")

    cp_blue = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Blue",
        device_values={1: {"color": "#0000ff"}},
    )
    app.lightshow.palettes.add(cp_blue)

    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={1: 1.0},
        device_values={1: {"intensity": 1.0, "color": "#0000ff"}},
        palette_refs={1: {"color": ("color", 2.0)}},
    )
    app.lightshow.cues.add(cue1)
    seq = app.lightshow.main_playback
    seq.insert_step(1, Step(sequence=1, cue=cue1))
    seq.load_step(1)

    # Manual red overrides blue cue
    app.action_registry.execute("device.set_color", 1.0, 0.0, 0.0, channels=[1])
    assert app.live_state.is_param_manual(1, "color") is True

    color_events: list[list[int]] = []
    app.subscribe(
        "device.color_changed", lambda chs, _col=None: color_events.append(list(chs))
    )

    # Timed Sneak 1.0s back to Cue 1 blue
    affected = app.sneak_controller.sneak_channels([1], duration=1.0)
    assert affected == [1]
    assert 1 in app.sneak_controller._device_fades
    fade = app.sneak_controller._device_fades[1]
    fade.start_time = 0.0

    with mock_patch("time.monotonic", return_value=0.5):
        cont = app.sneak_controller._on_tick()
        assert cont is True
        rgb_mid = dev.get_preview_rgb()
        assert rgb_mid is not None
        assert rgb_mid[0] == pytest.approx(0.5, abs=0.05)
        assert rgb_mid[2] == pytest.approx(0.5, abs=0.05)
        assert [1] in color_events

    with mock_patch("time.monotonic", return_value=1.0):
        cont = app.sneak_controller._on_tick()
        assert cont is False
        rgb_end = dev.get_preview_rgb()
        assert rgb_end == pytest.approx((0.0, 0.0, 1.0), abs=0.02)
        assert app.live_state.get_manual_params(1) == set()

    snap = build_live_channel_snapshot(app, 1)
    assert snap.is_manual is False
    assert snap.color.palette_ref is not None
    assert snap.color.palette_ref.short_ref == "CP 2"

    # Immediate SNEAK 0 restores cue values too
    app.action_registry.execute("device.set_color", 0.0, 1.0, 0.0, channels=[1])
    app.sneak_controller.sneak_channels([1], duration=0.0)
    assert app.live_state.get_manual_params(1) == set()
    assert dev.get_preview_rgb() == pytest.approx((0.0, 0.0, 1.0), abs=0.02)


def test_tracking_engine_ifcb_refs_block_and_mib() -> None:
    seq = Sequence(index=1, text="Seq")
    seq.tracking_mode = True
    seq.mib_enabled = True
    seq.steps.clear()
    seq.steps.append(Step(sequence=1))

    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={1: 1.0},
        device_values={
            1: {"intensity": 1.0, "color": "#ff0000", "pan": 45.0, "tilt": 10.0}
        },
        palette_refs={
            1: {
                "color": ("color", 1.0),
                "pan": ("focus", 1.0),
                "tilt": ("focus", 1.0),
            }
        },
    )
    cue2 = Cue(
        sequence=1,
        number=2.0,
        channels={1: 0.0},
        device_values={1: {"intensity": 0.0}},
    )
    cue3 = Cue(
        sequence=1,
        number=3.0,
        channels={1: 1.0},
        device_values={1: {"intensity": 1.0, "color": "#00ff00", "pan": 90.0}},
        # pan has NO ref -> breaks Focus partially
        palette_refs={1: {"color": ("color", 3.0)}},
    )
    cue4 = Cue(
        sequence=1,
        number=4.0,
        channels={1: 1.0},
        device_values={1: {"intensity": 1.0, "color": "#0000ff"}},
        palette_refs={1: {"color": ("color", 4.0)}},
        is_block=True,
    )
    for num, c in enumerate((cue1, cue2, cue3, cue4), start=1):
        seq.steps.append(Step(sequence=float(num), cue=c))

    # Step 2: dark cue -> MIB pre-positions color (#00ff00, CP 3) and pan (90, no ref)
    st2 = TrackingEngine.resolve_step_state(seq, 2, tracking_mode=True)
    assert st2.is_mib(1) is True
    assert st2.parameter_states[1]["color"] == TrackingDisplayState.MIB
    assert st2.palette_refs[1]["color"] == ("color", 3.0)
    assert "pan" not in st2.palette_refs.get(1, {})

    # Step 3: Focus is partial (pan hard without ref, tilt tracked with FP 1)
    st3 = TrackingEngine.resolve_step_state(seq, 3, tracking_mode=True)
    assert st3.has_move_on_family(1, "position") is True
    assert st3.has_move_on_family(1, "color") is True
    f_ref, f_partial = st3.get_family_palette_ref(1, "position")
    assert f_ref == ("focus", 1.0)
    assert f_partial is True

    # Step 4: Block cue
    st4 = TrackingEngine.resolve_step_state(seq, 4, tracking_mode=True)
    assert st4.family_states[1]["color"] == TrackingDisplayState.BLOCK
    c_ref, c_partial = st4.get_family_palette_ref(1, "color")
    assert c_ref == ("color", 4.0)
    assert c_partial is False


def test_realtime_events_during_pure_color_transitions_and_mib() -> None:
    app = _make_app()
    pm = app.lightshow.patch
    pm.patch_device(1, create_rgb_definition(), 1, 1, label="LED 1")
    dev2 = pm.patch_device(2, _make_cmy_spot_def(), 1, 10, label="CMY 2")

    seq = app.lightshow.main_playback
    seq.tracking_mode = True
    seq.mib_enabled = True
    seq.steps.clear()
    seq.steps.append(Step(sequence=1))

    # Pure color fade at constant 100% intensity + MIB at 0% intensity for CMY ch2
    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={1: 1.0, 2: 0.0},
        device_values={
            1: {"intensity": 1.0, "color": "#ff0000"},
            2: {"intensity": 0.0, "pan": 0.0, "color": "#ffffff"},
        },
    )
    cue2 = Cue(
        sequence=1,
        number=2.0,
        channels={1: 1.0, 2: 0.0},
        device_values={
            1: {"intensity": 1.0, "color": "#0000ff"},
            2: {"intensity": 0.0, "color": "#00ffff"},
        },
    )
    seq.add_step(Step(sequence=1, cue=cue1, time_in=2.0, time_out=2.0))
    seq.add_step(Step(sequence=2, cue=cue2, time_in=2.0, time_out=2.0))
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))
    seq.load_step(1)

    color_events: list[list[int]] = []
    param_events: list[list[int]] = []
    app.subscribe(
        "device.color_changed", lambda chs, _c=None: color_events.append(list(chs))
    )
    app.subscribe(
        "device.parameters_changed", lambda chs: param_events.append(list(chs))
    )

    # 1. ThreadGo pure color tick emits device.color_changed
    tg = ThreadGo(goto=False, sequence=seq, override_time=2.0)
    tg._capture_start_levels()
    tg._do_go(1000.0)
    assert any(1 in chs and 2 in chs for chs in color_events)

    # 2. Interpolating ONLY pan emits parameters change, NOT color_changed
    color_events.clear()
    param_events.clear()
    starts = _capture_device_states(pm)
    col_out: set[int] = set()
    changed = _interpolate_device_states(
        pm, starts, {2: {"pan": 90.0}}, 0.5, color_changed_out=col_out
    )
    assert changed == {2}
    assert col_out == set()

    # 3. ThreadGoBack pure color tick emits device.color_changed
    color_events.clear()
    tgb = ThreadGoBack(seq)
    tgb._capture_start_levels()
    seq.position = 2
    tgb.update_levels(go_back_time=2000.0, i=1000.0, position=2)
    assert any(1 in chs for chs in color_events)

    # 4. CrossFade slider pure color transition emits device.color_changed
    color_events.clear()
    seq.position = 1
    seq.on_go = True
    xf = CrossFade(app)
    xf.scale_b.set_value(128)
    xf.update_slider(xf.scale_b, 128)
    assert any(1 in chs for chs in color_events)

    # 5. Dmx.send() at constant intensity detects direct preview color change
    dmx = typing.cast(typing.Any, app.backend).dmx
    dmx.send()  # Prime baseline
    updated_events: list[list[int]] = []
    app.subscribe("channels.updated", lambda chs: updated_events.append(list(chs)))
    dev2.set_color_srgb(1.0, 0.25, 0.0)
    dmx.send()
    assert any(2 in chs for chs in updated_events)


def test_channel_display_snapshots_and_readouts() -> None:
    app = _make_app()
    pm = app.lightshow.patch
    pm.patch_dimmer(1, 1, 1)
    pm.patch_device(2, _make_cmy_spot_def(), 1, 2, label="Wash CMY")

    cp1 = Palette(
        category=PaletteCategory.COLOR,
        number=2.5,
        text="Deep Cyan",
        device_values={2: {"color": "#00ffff"}},
    )
    app.lightshow.palettes.add(cp1)
    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={1: 0.75, 2: 0.5},
        device_values={
            2: {
                "intensity": 0.5,
                "pan": 45.0,
                "tilt": -10.0,
                "color": "#00ffff",
                "zoom": 20.0,
            }
        },
        palette_refs={2: {"color": ("color", 2.5)}},
    )
    app.lightshow.cues.add(cue1)
    seq = app.lightshow.main_playback
    seq.insert_step(1, Step(sequence=1, cue=cue1))
    seq.load_step(1)
    app.selected_channels = [2]

    snap_dim = build_live_channel_snapshot(app, 1)
    assert snap_dim.is_patched is True
    assert snap_dim.has_device is False
    assert snap_dim.has_color is False
    assert snap_dim.intensity == pytest.approx(0.75, abs=0.01)

    snap_cmy = build_live_channel_snapshot(app, 2)
    assert snap_cmy.is_selected is True
    assert snap_cmy.has_device is True
    assert snap_cmy.is_moving_head is True
    assert snap_cmy.has_color is True
    assert snap_cmy.preview_rgb == pytest.approx((0.0, 1.0, 1.0), abs=0.02)
    assert snap_cmy.color.palette_ref is not None
    assert snap_cmy.color.palette_ref.short_ref == "CP 2.5"
    assert snap_cmy.color.palette_ref.label == "Deep Cyan"
    assert format_short_palette_ref("preset", 4.0) == "P 4"
    assert format_family_readout(snap_cmy.color, "auto") == "Deep Cyan"
    assert format_family_readout(snap_cmy.color, "label") == "Deep Cyan"
    assert format_family_readout(snap_cmy.color, "ref") == "CP 2.5"
    assert "#" in format_family_readout(snap_cmy.color, "value")
    assert "%" in format_family_readout(snap_cmy.color, "percent")
    assert format_family_readout(snap_cmy.color, "dmx") != ""

    # Step snapshot stays isolated from subsequent live manual changes
    app.action_registry.execute("device.set_color", 1.0, 0.0, 0.0, channels=[2])
    step_snap = build_step_channel_snapshot(app.lightshow, seq, 1, 2)
    assert step_snap.is_manual is False
    assert step_snap.preview_rgb == pytest.approx((0.0, 1.0, 1.0), abs=0.02)
    assert step_snap.color.palette_ref is not None
    assert step_snap.color.palette_ref.short_ref == "CP 2.5"
