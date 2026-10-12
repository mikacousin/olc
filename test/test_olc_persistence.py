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
"""Unit and integration tests for Stage 7 (.olc show serialization & persistence)."""

from __future__ import annotations

import gzip
import json
import pathlib
from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.cue import Cue
from olc.curve import LimitCurve
from olc.devices.builtin import create_rgbw_definition
from olc.devices.color import CIExyY, EmitterProfile, FixtureColorProfile
from olc.devices.device import (
    ChannelRange,
    ChannelType,
    FixtureType,
    LightingDevice,
    MergeMode,
)
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
)
from olc.sequence import Sequence
from olc.step import Step


def _create_custom_gdtf_fixture_def() -> FixtureDefinition:
    """Create a rich custom fixture definition simulating an imported GDTF profile."""
    color_profile = FixtureColorProfile(
        fixture_name="CustomCorp HyperSpot 500",
        emitters=[
            EmitterProfile(
                name="Red",
                cie=CIExyY(0.68, 0.31, 21.26),
                dominant_wavelength=625.0,
                diode_part="Osram-R",
                gdtf_attribute="ColorAdd_R",
            ),
            EmitterProfile(
                name="Green",
                cie=CIExyY(0.17, 0.70, 71.52),
                dominant_wavelength=525.0,
                diode_part="Osram-G",
                gdtf_attribute="ColorAdd_G",
            ),
            EmitterProfile(
                name="Blue",
                cie=CIExyY(0.14, 0.06, 7.22),
                dominant_wavelength=460.0,
                diode_part="Osram-B",
                gdtf_attribute="ColorAdd_B",
            ),
            EmitterProfile(
                name="White",
                cie=CIExyY(0.3127, 0.3290, 100.0),
                dominant_wavelength=0.0,
                diode_part="Osram-W",
                gdtf_attribute="ColorAdd_W",
            ),
        ],
        white_point=CIExyY(0.3127, 0.3290, 100.0),
        color_space_mode="Custom",
    )

    mode = DmxModeDefinition(
        name="Extended 24-bit",
        description="Full resolution mode with 24-bit Pan/Tilt",
        channel_defs=[
            ChannelDefinition(
                ChannelType.INTENSITY,
                offset=0,
                fine_offset=1,
                label="Dimmer",
                physical_min=0.0,
                physical_max=100.0,
                physical_unit="%",
            ),
            ChannelDefinition(
                ChannelType.PAN,
                offset=2,
                fine_offset=3,
                ultra_fine_offset=4,
                label="Pan",
                default_value=128,
                physical_min=-270.0,
                physical_max=270.0,
                physical_unit="deg",
            ),
            ChannelDefinition(
                ChannelType.TILT,
                offset=5,
                fine_offset=6,
                label="Tilt",
                default_value=128,
                physical_min=-135.0,
                physical_max=135.0,
                physical_unit="deg",
            ),
            ChannelDefinition(
                ChannelType.RED,
                offset=7,
                label="Red",
            ),
            ChannelDefinition(
                ChannelType.GREEN,
                offset=8,
                label="Green",
            ),
            ChannelDefinition(
                ChannelType.BLUE,
                offset=9,
                label="Blue",
            ),
            ChannelDefinition(
                ChannelType.WHITE,
                offset=10,
                label="White",
            ),
            ChannelDefinition(
                ChannelType.ZOOM,
                offset=11,
                label="Zoom",
                physical_min=5.0,
                physical_max=50.0,
                physical_unit="deg",
            ),
            ChannelDefinition(
                ChannelType.GOBO_WHEEL,
                offset=12,
                label="Gobo1",
                ranges=[
                    ChannelRange("Open", ChannelType.GOBO_WHEEL, 0, 15, snap_value=0),
                    ChannelRange(
                        "Stars", ChannelType.GOBO_WHEEL, 16, 47, snap_value=32
                    ),
                    ChannelRange("Dots", ChannelType.GOBO_WHEEL, 48, 79, snap_value=64),
                ],
            ),
        ],
    )

    return FixtureDefinition(
        manufacturer="CustomCorp",
        model="HyperSpot 500",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[mode],
        color_profile=color_profile,
        gdtf_id="CustomCorp@HyperSpot_500@v1.2",
        thumbnail=b"\x89PNG\r\n\x1a\ndummy",
        notes="Imported from GDTF archive",
    )


def test_color_profile_and_fixture_definition_roundtrip() -> None:
    """Test to_dict / from_dict round-trip for color profiles and fixture defs."""
    orig_def = _create_custom_gdtf_fixture_def()
    serialized = orig_def.to_dict()

    # Verify JSON serializability
    json_str = json.dumps(serialized)
    deserialized_data = json.loads(json_str)

    restored_def = FixtureDefinition.from_dict(deserialized_data)

    assert restored_def.manufacturer == "CustomCorp"
    assert restored_def.model == "HyperSpot 500"
    assert restored_def.fixture_type == FixtureType.MOVING_HEAD
    assert restored_def.gdtf_id == "CustomCorp@HyperSpot_500@v1.2"
    assert restored_def.thumbnail == b"\x89PNG\r\n\x1a\ndummy"
    assert restored_def.notes == "Imported from GDTF archive"

    # Check color profile
    assert restored_def.color_profile is not None
    assert restored_def.color_profile.fixture_name == "CustomCorp HyperSpot 500"
    assert restored_def.color_profile.color_space_mode == "Custom"
    assert restored_def.color_profile.emitter_count == 4
    red_em = restored_def.color_profile.get_emitter("Red")
    assert red_em is not None
    assert red_em.cie.x == pytest.approx(0.68)
    assert red_em.dominant_wavelength == pytest.approx(625.0)
    assert red_em.diode_part == "Osram-R"

    # Check DMX mode and channel definitions
    mode = restored_def.get_mode("Extended 24-bit")
    assert mode.description == "Full resolution mode with 24-bit Pan/Tilt"
    assert mode.footprint() == 13
    pan_def = mode.channel_defs[1]
    assert pan_def.channel_type == ChannelType.PAN
    assert pan_def.offset == 2
    assert pan_def.fine_offset == 3
    assert pan_def.ultra_fine_offset == 4
    assert pan_def.physical_min == pytest.approx(-270.0)
    assert pan_def.physical_max == pytest.approx(270.0)
    assert pan_def.physical_unit == "deg"
    assert pan_def.merge_mode == MergeMode.LTP

    gobo_def = mode.channel_defs[-1]
    assert len(gobo_def.ranges) == 3
    assert gobo_def.ranges[1].label == "Stars"
    assert gobo_def.ranges[1].snap_value == 32


def test_lighting_device_full_serialization_roundtrip() -> None:
    """Test LightingDevice.to_dict / from_dict preserves metadata and color profile."""
    fdef = _create_custom_gdtf_fixture_def()
    dev = fdef.instantiate(
        fixture_id=101,
        label="Lead Spot",
        universe=2,
        address=10,
        mode_name="Extended 24-bit",
        group="Front Truss",
    )
    dev.set_curve_id(3)
    dev.set_intensity(0.75)
    dev.set_pan_degrees(90.0)
    dev.set_tilt_degrees(-45.0)
    dev.set_zoom_degrees(25.0)
    dev.set_color_hex("#FF8000")
    dev.lock()

    dev_dict = dev.to_dict()
    restored = LightingDevice.from_dict(dev_dict)

    assert restored.fixture_id == 101
    assert restored.label == "Lead Spot"
    assert restored.fixture_type == FixtureType.MOVING_HEAD
    assert restored.manufacturer == "CustomCorp"
    assert restored.model == "HyperSpot 500"
    assert restored.mode_name == "Extended 24-bit"
    assert restored.gdtf_id == "CustomCorp@HyperSpot_500@v1.2"
    assert restored.group == "Front Truss"
    assert restored.locked is True
    assert restored.curve_id == 3
    assert restored.color_profile is not None
    assert restored.color_profile.emitter_count == 4
    assert restored.intensity == pytest.approx(0.75, abs=1e-3)
    assert restored.pan_degrees == pytest.approx(90.0, abs=0.05)
    assert restored.tilt_degrees == pytest.approx(-45.0, abs=0.05)
    assert restored.zoom_degrees == pytest.approx(25.0, abs=0.2)
    assert restored.color_srgb.to_hex() == "#FF8000"


def test_olc_save_and_open_autonomous_show_with_devices_and_gdtf(  # pylint: disable=too-many-locals, too-many-statements
    tmp_path: pathlib.Path,
) -> None:
    """Test saving and reopening an .olc show with custom GDTF fixtures and cues."""
    settings = MagicMock()
    app1 = CoreApplication(settings)
    show1 = app1.lightshow

    # 1. Configure custom curve 10
    show1.curves.curves[10] = LimitCurve(limit=200)
    show1.curves.curves[10].name = "Soft Limit"

    # 2. Patch a 16-bit dimmer, an RGBW LED PAR, and a custom GDTF Moving Head
    show1.patch.patch_empty()
    dim1 = show1.patch.patch_dimmer(
        channel=1, universe=1, address=1, curve=10, fine=True, label="Warm Front"
    )
    assert dim1.has_16bit_dimmer is True

    rgbw_def = create_rgbw_definition()
    led_dev = show1.patch.patch_device(
        device_id=50,
        fixture_def=rgbw_def,
        universe=1,
        address=20,
        label="Cyc LED 1",
    )
    led_dev.set_color_hex("#00FF88")
    led_dev.set_intensity(0.6)

    custom_fdef = _create_custom_gdtf_fixture_def()
    spot_dev = show1.patch.patch_device(
        device_id=101,
        fixture_def=custom_fdef,
        universe=2,
        address=1,
        mode_name="Extended 24-bit",
        label="HyperSpot 1",
    )
    spot_dev.set_position_degrees(120.0, -30.0)
    spot_dev.set_zoom_degrees(18.0)

    # 3. Configure Main Playback in Tracking Mode with device_values and Block Cue
    show1.main_playback.tracking_mode = True
    show1.main_playback.mib_enabled = False
    show1.main_playback.mib_fade_time = 3.5
    cue1 = Cue(0, 1.0, channels={1: 200}, text="Opening")
    cue1.device_values = {
        50: {"intensity": 0.6, "color": "#00FF88"},
        101: {
            "intensity": 1.0,
            "pan": 120.0,
            "tilt": -30.0,
            "zoom": 18.0,
            "gobo": "Stars",
        },
    }
    show1.cues.add(cue1)
    step1 = Step(1, cue=cue1, time_in=3.0, time_out=3.0, text="Opening Step")
    show1.main_playback.insert_step(1, step1)

    cue2 = Cue(0, 2.0, channels={1: 100}, text="Blackout Barrier")
    cue2.is_block = True
    cue2.device_values = {101: {"intensity": 0.0}}
    show1.cues.add(cue2)
    step2 = Step(1, cue=cue2, time_in=2.0, time_out=2.0, text="Block Step")
    show1.main_playback.insert_step(2, step2)

    # 4. Add a Chaser sequence with tracking_mode=True
    chaser = Sequence(2, type_seq="Chaser", text="Effect Chase", lightshow=show1)
    chaser.tracking_mode = True
    chaser.mib_enabled = False
    chaser.mib_fade_time = 1.5
    del chaser.steps[1:]
    ch_cue = Cue(2, 1.0, channels={1: 255}, text="Flash 1")
    ch_cue.device_values = {50: {"color": "#FF0000"}}
    chaser.cues.add(ch_cue)
    chaser.add_step(Step(2, cue=ch_cue, time_in=1.0, time_out=1.0))
    show1.chasers.append(chaser)

    # 5. Save to .olc
    olc_path = str(tmp_path / "autonomous_show.olc")
    app1.action_registry.execute("show.save", olc_path)
    assert pathlib.Path(olc_path).exists()

    # 6. Open in a brand-new CoreApplication instance (no GDTF file on disk)
    app2 = CoreApplication(settings)
    app2.action_registry.execute("show.open", olc_path)
    show2 = app2.lightshow

    # Verify custom GDTF fixture definition was restored into show2.fixture_library
    restored_fdef = show2.fixture_library.get("CustomCorp", "HyperSpot 500")
    assert restored_fdef is not None
    assert restored_fdef.gdtf_id == "CustomCorp@HyperSpot_500@v1.2"
    assert restored_fdef.color_profile is not None
    assert restored_fdef.color_profile.emitter_count == 4

    # Verify patched devices
    r_dim = show2.patch.get_device(1)
    assert r_dim is not None
    assert r_dim.label == "Warm Front"
    assert r_dim.has_16bit_dimmer is True
    assert r_dim.curve_id == 10
    assert show2.patch.is_patched(1) is True

    r_led = show2.patch.get_device(50)
    assert r_led is not None
    assert r_led.label == "Cyc LED 1"
    assert r_led.uses_virtual_dimmer is True
    assert r_led.color_srgb.to_hex() == "#00FF88"
    assert r_led.intensity == pytest.approx(0.6, abs=1e-2)

    r_spot = show2.patch.get_device(101)
    assert r_spot is not None
    assert r_spot.label == "HyperSpot 1"
    assert r_spot.manufacturer == "CustomCorp"
    assert r_spot.model == "HyperSpot 500"
    assert r_spot.mode_name == "Extended 24-bit"
    assert r_spot.has_24bit_dimmer is False
    assert r_spot.pan_degrees == pytest.approx(120.0, abs=0.05)
    assert r_spot.tilt_degrees == pytest.approx(-30.0, abs=0.05)
    assert r_spot.zoom_degrees == pytest.approx(18.0, abs=0.2)
    assert r_spot.color_profile is not None

    # Verify Main Playback tracking_mode, mib_enabled, mib_fade_time, and cues
    assert show2.main_playback.tracking_mode is True
    assert show2.main_playback.mib_enabled is False
    assert show2.main_playback.mib_fade_time == pytest.approx(3.5)
    r_cue1 = show2.cues.get(1.0, 0)
    assert r_cue1 is not None
    assert r_cue1.device_values[101]["pan"] == 120.0
    assert r_cue1.device_values[101]["gobo"] == "Stars"

    r_cue2 = show2.cues.get(2.0, 0)
    assert r_cue2 is not None
    assert r_cue2.is_block is True
    assert r_cue2.device_values[101]["intensity"] == 0.0

    # Verify Chaser sequence tracking_mode, mib settings, and cue metadata
    r_chaser = show2.get_chaser(2)
    assert r_chaser is not None
    assert r_chaser.tracking_mode is True
    assert r_chaser.mib_enabled is False
    assert r_chaser.mib_fade_time == pytest.approx(1.5)


def test_legacy_olc_file_without_devices_key(tmp_path: pathlib.Path) -> None:
    """Test backward compatibility with legacy .olc files having only 'patch'."""
    legacy_data = {
        "application": "olc",
        "version": "0.8.0",
        "patch": {
            "1": [{"output": 10, "universe": 1}],
            "2": [{"output": 20, "universe": 1, "curve": 1}],
        },
        "sequences": {
            "1": {
                "label": "Main",
                "steps": {"1": {"cue": 1.0, "time_in": 2.0, "time_out": 2.0}},
                "cues": {"1.0": {"label": "Cue 1", "channels": {"1": 255}}},
            }
        },
        "cues": {"1.0": {"label": "Cue 1", "channels": {"1": 255}}},
    }
    legacy_path = tmp_path / "legacy.olc"
    with gzip.open(legacy_path, "wt", encoding="utf-8") as f:
        json.dump(legacy_data, f)

    settings = MagicMock()
    app = CoreApplication(settings)
    app.action_registry.execute("show.open", str(legacy_path))

    assert app.lightshow.patch.outputs[1][10] == [1, 0]
    assert app.lightshow.patch.outputs[1][20] == [2, 1]
    dev1 = app.lightshow.patch.get_device(1)
    assert dev1 is not None
    assert dev1.address == 10
    dev2 = app.lightshow.patch.get_device(2)
    assert dev2 is not None
    assert dev2.curve_id == 1


def test_show_import_olc_devices_and_undo_redo(tmp_path: pathlib.Path) -> None:
    """Test show.import with an .olc file containing custom devices and Undo/Redo."""
    settings = MagicMock()

    # Build source show to import from
    src_app = CoreApplication(settings)
    src_app.lightshow.patch.patch_empty()
    custom_fdef = _create_custom_gdtf_fixture_def()
    src_app.lightshow.patch.patch_device(
        device_id=101,
        fixture_def=custom_fdef,
        universe=2,
        address=1,
        label="Imported HyperSpot",
    )
    src_app.lightshow.main_playback.tracking_mode = True
    c1 = Cue(0, 1.0, channels={101: 255}, text="Imported Cue")
    c1.device_values = {101: {"pan": 45.0, "tilt": 15.0}}
    c1.is_block = True
    src_app.lightshow.cues.add(c1)
    src_app.lightshow.main_playback.insert_step(
        1, Step(1, cue=c1, time_in=2.0, time_out=2.0)
    )

    import_path = str(tmp_path / "source_import.olc")
    src_app.action_registry.execute("show.save", import_path)

    # Target show with initial state
    dst_app = CoreApplication(settings)
    dst_app.lightshow.patch.patch_empty()
    dst_app.lightshow.patch.patch_dimmer(1, 1, 5, label="Initial Dimmer")
    dst_app.lightshow.main_playback.tracking_mode = False
    init_cue = Cue(0, 10.0, channels={1: 128}, text="Initial Cue")
    init_cue.device_values = {1: {"intensity": 0.5}}
    dst_app.lightshow.cues.add(init_cue)
    dst_app.lightshow.main_playback.insert_step(
        1, Step(1, cue=init_cue, time_in=1.0, time_out=1.0)
    )
    dst_app.lightshow.set_not_modified()

    # Execute import
    dst_app.action_registry.execute("show.import", import_path)

    assert dst_app.lightshow.patch.has_device(101) is True
    assert dst_app.lightshow.patch.has_device(1) is False
    assert (
        dst_app.lightshow.fixture_library.get_by_key("CustomCorp:HyperSpot 500")
        is not None
    )
    assert dst_app.lightshow.main_playback.tracking_mode is True
    imp_cue = dst_app.lightshow.cues.get(1.0, 0)
    assert imp_cue is not None
    assert imp_cue.is_block is True
    assert imp_cue.device_values[101]["pan"] == 45.0

    # Undo import
    dst_app.history.undo()

    assert dst_app.lightshow.patch.has_device(101) is False
    assert dst_app.lightshow.patch.has_device(1) is True
    assert dst_app.lightshow.patch.get_device(1).label == "Initial Dimmer"
    assert (
        dst_app.lightshow.fixture_library.get_by_key("CustomCorp:HyperSpot 500") is None
    )
    assert dst_app.lightshow.main_playback.tracking_mode is False
    restored_init_cue = dst_app.lightshow.cues.get(10.0, 0)
    assert restored_init_cue is not None
    assert restored_init_cue.device_values == {1: {"intensity": 0.5}}
    assert dst_app.lightshow.modified is False

    # Redo import
    dst_app.history.redo()

    assert dst_app.lightshow.patch.has_device(101) is True
    assert dst_app.lightshow.main_playback.tracking_mode is True
    assert dst_app.lightshow.modified is True
