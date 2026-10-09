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
"""Unit tests for the devices subsystem."""

# pylint: disable=missing-function-docstring, redefined-outer-name, protected-access

import pytest

from olc.devices import (
    CIEXYZ,
    COLOR_CHANNEL_TYPES,
    GDTF_ATTRIBUTE_MAP,
    HAS_PYGDTF,
    Channel,
    ChannelDefinition,
    ChannelRange,
    ChannelType,
    CIExyY,
    ColorMatcher,
    DmxAddress,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
    FixtureType,
    GdtfImporter,
    LightingDevice,
    create_dimmer_definition,
    create_moving_head_definition,
    create_rgb_definition,
    create_rgba_definition,
    create_rgbw_definition,
    delta_e76,
    populate_builtin_library,
    profile_from_emitters,
    sRGB,
)

# ---------------------------------------------------------------------------
# DmxAddress
# ---------------------------------------------------------------------------


def test_dmx_address_basics() -> None:
    addr = DmxAddress(1, 10)
    assert addr.universe == 1
    assert addr.address == 10
    assert str(addr) == "1.10"
    assert repr(addr) == "DmxAddress(universe=1, address=10)"


def test_dmx_address_parse() -> None:
    addr = DmxAddress.parse("2.512")
    assert addr.universe == 2
    assert addr.address == 512

    with pytest.raises(ValueError):
        DmxAddress.parse("invalid")
    with pytest.raises(ValueError):
        DmxAddress.parse("1.513")


def test_dmx_address_validation() -> None:
    with pytest.raises(ValueError):
        DmxAddress(0, 1)
    with pytest.raises(ValueError):
        DmxAddress(1, 0)
    with pytest.raises(ValueError):
        DmxAddress(1, 513)


def test_dmx_address_ordering_and_hash() -> None:
    a1 = DmxAddress(1, 1)
    a2 = DmxAddress(1, 2)
    b1 = DmxAddress(2, 1)

    assert a1 < a2 < b1
    assert a1 <= a2
    assert b1 > a2
    assert hash(a1) == hash(DmxAddress(1, 1))
    assert a1 == DmxAddress(1, 1)


def test_dmx_address_next_and_offset() -> None:
    a = DmxAddress(1, 511)
    nxt1 = a.next()
    assert nxt1 == DmxAddress(1, 512)

    nxt2 = nxt1.next()
    assert nxt2 == DmxAddress(2, 1)

    off = a.offset(3)
    assert off == DmxAddress(2, 2)

    with pytest.raises(ValueError):
        a.offset(-1)


# ---------------------------------------------------------------------------
# ChannelRange & Channel
# ---------------------------------------------------------------------------


def test_channel_range() -> None:
    rng = ChannelRange(
        "Closed to open",
        ChannelType.INTENSITY,
        0,
        127,
        snap_value=0,
    )
    assert rng.contains(0)
    assert rng.contains(127)
    assert not rng.contains(128)
    assert repr(rng) == "<ChannelRange 'Closed to open' [0-127] type=intensity>"

    with pytest.raises(ValueError):
        ChannelRange("Bad", ChannelType.INTENSITY, 100, 50)


def test_channel_clamping_and_percent() -> None:
    ch = Channel(ChannelType.INTENSITY, universe=1, address=1, default_value=0)
    assert ch.value == 0
    assert ch.percent == 0.0

    ch.set_value(128)
    assert ch.value == 128
    assert abs(ch.percent - (128 / 255 * 100)) < 0.1

    ch.set_percent(50.0)
    assert ch.value == round(50.0 * 255 / 100)

    # Clamping
    ch.set_value(300)
    assert ch.value == 255
    ch.set_value(-10)
    assert ch.value == 0


def test_channel_ranges_and_reset() -> None:
    r1 = ChannelRange("Strobe Off", ChannelType.STROBE, 0, 10)
    r2 = ChannelRange("Strobe Rate", ChannelType.STROBE, 11, 255)
    ch = Channel(
        ChannelType.STROBE,
        universe=1,
        address=2,
        default_value=0,
        ranges=[r1, r2],
    )
    ch.set_value(50)
    assert ch.active_range == r2
    ch.set_value(5)
    assert ch.active_range == r1

    ch.reset()
    assert ch.value == 0


# ---------------------------------------------------------------------------
# LightingDevice
# ---------------------------------------------------------------------------


def test_lighting_device_instantiation() -> None:
    c1 = Channel(ChannelType.INTENSITY, universe=1, address=1)
    c2 = Channel(ChannelType.RED, universe=1, address=2)
    dev = LightingDevice(
        fixture_id=1,
        label="Spot 1",
        fixture_type=FixtureType.LED_PAR,
        channels=[c1, c2],
    )

    assert dev.fixture_id == 1
    assert dev.label == "Spot 1"
    assert dev.channel_count() == 2
    assert dev.footprint() == {1: (1, 2)}
    assert dev.universes() == [1]
    assert dev.patch_summary() == "U1:1-2"


def test_lighting_device_channel_access() -> None:
    c_int = Channel(ChannelType.INTENSITY, universe=1, address=1)
    c_r = Channel(ChannelType.RED, universe=1, address=2)
    c_g = Channel(ChannelType.GREEN, universe=1, address=3)
    c_b = Channel(ChannelType.BLUE, universe=1, address=4)
    dev = LightingDevice(
        fixture_id=10,
        label="LED 10",
        fixture_type=FixtureType.LED_PAR,
        channels=[c_int, c_r, c_g, c_b],
    )

    assert dev.get_channel(ChannelType.INTENSITY) is c_int
    assert dev.get_channel(ChannelType.WHITE) is None
    assert dev.get_channel(ChannelType.RED) is c_r

    dev.set_intensity(200)
    assert c_int.value == 200


def test_lighting_device_color_and_position() -> None:
    c_r = Channel(ChannelType.RED, universe=1, address=1)
    c_g = Channel(ChannelType.GREEN, universe=1, address=2)
    c_b = Channel(ChannelType.BLUE, universe=1, address=3)
    c_pan = Channel(ChannelType.PAN, universe=1, address=4)
    c_tilt = Channel(ChannelType.TILT, universe=1, address=5)
    dev = LightingDevice(
        fixture_id=3,
        label="Mover 1",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[c_r, c_g, c_b, c_pan, c_tilt],
    )

    dev.set_color(255, 128, 64)
    assert c_r.value == 255
    assert c_g.value == 128
    assert c_b.value == 64

    dev.set_position(200, 150)
    assert c_pan.value == 200
    assert c_tilt.value == 150

    dev.reset_all()
    assert c_r.value == 0
    assert c_g.value == 0
    assert c_b.value == 0
    assert c_pan.value == 0
    assert c_tilt.value == 0


def test_lighting_device_osc_and_serialization() -> None:
    c_int = Channel(ChannelType.INTENSITY, universe=1, address=1, label="Dimmer")
    dev = LightingDevice(
        fixture_id=4,
        label="D4",
        fixture_type=FixtureType.DIMMER,
        channels=[c_int],
        group="Front",
        notes="Key light",
    )
    dev.set_intensity(204)

    osc_messages = dev.to_osc_bundle()
    assert len(osc_messages) >= 1
    assert any(addr == "/fixture/4/Dimmer" for addr, _ in osc_messages)

    # Serialization
    data = dev.to_dict()
    assert data["fixture_id"] == 4
    assert data["label"] == "D4"
    assert data["group"] == "Front"

    restored = LightingDevice.from_dict(data)
    assert restored.fixture_id == 4
    assert restored.label == "D4"
    assert restored.channel_count() == 1
    int_ch = restored.get_channel(ChannelType.INTENSITY)
    assert int_ch is not None
    assert int_ch.value == c_int.value
    assert restored.intensity_8bit == 204


def test_lighting_device_virtual_dimmer() -> None:
    c_r = Channel(ChannelType.RED, universe=1, address=1)
    c_g = Channel(ChannelType.GREEN, universe=1, address=2)
    c_b = Channel(ChannelType.BLUE, universe=1, address=3)
    dev = LightingDevice(
        fixture_id=20,
        label="LED Bar",
        fixture_type=FixtureType.LED_PAR,
        channels=[c_r, c_g, c_b],
    )

    assert not dev.has_physical_dimmer
    assert dev.uses_virtual_dimmer
    assert len(COLOR_CHANNEL_TYPES) >= 3

    # Default virtual dimmer is 1.0 (open)
    assert dev.intensity == 1.0
    assert dev.intensity_percent == 100.0

    # Setting color at full intensity outputs full DMX values
    dev.set_color_rgb(255, 128, 0)
    assert c_r.value == 255
    assert c_g.value == 128
    assert c_b.value == 0
    assert dev.color_rgb == (255, 128, 0)

    # Dimming down to 50% scales outputs but preserves base color
    dev.set_intensity(0.5)
    assert dev.intensity == 0.5
    assert dev.intensity_percent == 50.0
    assert c_r.value == 128
    assert c_g.value == 64
    assert c_b.value == 0
    assert dev.color_rgb == (255, 128, 0)

    # Dimming down to 0% zeroes DMX outputs while keeping base color
    dev.set_intensity(0.0)
    assert c_r.value == 0
    assert c_g.value == 0
    assert c_b.value == 0
    assert dev.color_rgb == (255, 128, 0)

    # Restoring intensity restores exact DMX output
    dev.set_intensity(1.0)
    assert c_r.value == 255
    assert c_g.value == 128
    assert c_b.value == 0

    # Setting color while dimmed scales correctly
    dev.set_intensity(0.5)
    dev.set_color_hex("#00FF00")
    assert dev.color_rgb == (0, 255, 0)
    assert c_r.value == 0
    assert c_g.value == 128
    assert c_b.value == 0

    # Blackout zeroes output
    dev.blackout()
    assert dev.intensity == 0.0
    assert c_g.value == 0


def test_lighting_device_normalized_intensity() -> None:
    c_coarse = Channel(ChannelType.INTENSITY, universe=1, address=1, fine=False)
    c_fine = Channel(ChannelType.INTENSITY, universe=1, address=2, fine=True)
    dev = LightingDevice(
        fixture_id=21,
        label="Dim 16b",
        fixture_type=FixtureType.DIMMER,
        channels=[c_coarse, c_fine],
    )

    assert dev.has_physical_dimmer
    assert dev.has_16bit_dimmer
    assert not dev.uses_virtual_dimmer

    # Set normalized float [0.0, 1.0]
    dev.set_intensity(0.5)
    assert dev.intensity == 0.5
    assert dev.intensity_percent == 50.0
    assert c_coarse.value == 0x80
    assert c_fine.value == 0x00

    # Set 16-bit integer directly
    dev.set_intensity_16bit(0xABCD)
    assert c_coarse.value == 0xAB
    assert c_fine.value == 0xCD
    assert dev.intensity_16bit == 0xABCD

    # Set 8-bit integer compatibility (> 1 auto-detection)
    dev.set_intensity(128)
    assert dev.intensity == pytest.approx(128 / 255.0, abs=1e-3)


def test_lighting_device_with_color_profile() -> None:
    profile = profile_from_emitters(
        "RGB_Calibrated",
        [
            ("Red", 0.640, 0.330, 21.26, 625.0),
            ("Green", 0.300, 0.600, 71.52, 525.0),
            ("Blue", 0.150, 0.060, 7.22, 465.0),
        ],
    )
    c_r = Channel(ChannelType.RED, universe=1, address=1)
    c_g = Channel(ChannelType.GREEN, universe=1, address=2)
    c_b = Channel(ChannelType.BLUE, universe=1, address=3)
    dev = LightingDevice(
        fixture_id=22,
        label="Calibrated PAR",
        fixture_type=FixtureType.LED_PAR,
        channels=[c_r, c_g, c_b],
        color_profile=profile,
    )

    dev.set_intensity(1.0)
    dev.set_color_cie(0.640, 0.330, 21.26)
    assert c_r.value > 200
    assert c_g.value == 0
    assert c_b.value == 0


# ---------------------------------------------------------------------------
# FixtureDefinition & FixtureLibrary
# ---------------------------------------------------------------------------


def test_fixture_definition_and_modes() -> None:
    ch_int = ChannelDefinition(ChannelType.INTENSITY, 0, "Dimmer")
    mode_1ch = DmxModeDefinition("1-Channel", [ch_int])

    ch_r = ChannelDefinition(ChannelType.RED, 1, "Red")
    ch_g = ChannelDefinition(ChannelType.GREEN, 2, "Green")
    ch_b = ChannelDefinition(ChannelType.BLUE, 3, "Blue")
    mode_4ch = DmxModeDefinition("4-Channel", [ch_int, ch_r, ch_g, ch_b])

    fix_def = FixtureDefinition(
        manufacturer="Generic",
        model="RGB PAR",
        fixture_type=FixtureType.LED_PAR,
        dmx_modes=[mode_1ch, mode_4ch],
    )

    assert fix_def.full_name == "Generic RGB PAR"
    assert fix_def.mode_names() == ["1-Channel", "4-Channel"]
    assert fix_def.default_mode() is mode_1ch
    assert fix_def.get_mode("4-Channel") is mode_4ch

    with pytest.raises(KeyError):
        fix_def.get_mode("Unknown")

    # Instantiate
    device = fix_def.instantiate(
        fixture_id=1,
        label="PAR 1",
        universe=1,
        address=10,
        mode_name="4-Channel",
    )
    assert device.channel_count() == 4
    blue_ch = device.get_channel(ChannelType.BLUE)
    assert blue_ch is not None
    assert blue_ch.address == 13


def test_fixture_definition_universe_boundary_wrap() -> None:
    ch_defs = [
        ChannelDefinition(ChannelType.INTENSITY, offset=i, label=f"Ch {i}")
        for i in range(5)
    ]
    mode = DmxModeDefinition("5ch", ch_defs)
    fix_def = FixtureDefinition("Brand", "Spanner", dmx_modes=[mode])

    # Patch at address 510: channels 0, 1, 2 at 510, 511, 512 in univ 1;
    # channels 3, 4 wrap to univ 2
    device = fix_def.instantiate(
        fixture_id=10, label="Wrap Dev", universe=1, address=510
    )
    assert device.channels[0].universe == 1 and device.channels[0].address == 510
    assert device.channels[2].universe == 1 and device.channels[2].address == 512
    assert device.channels[3].universe == 2 and device.channels[3].address == 1
    assert device.channels[4].universe == 2 and device.channels[4].address == 2
    assert device.universes() == [1, 2]


def test_fixture_library() -> None:
    lib = FixtureLibrary()
    populate_builtin_library(lib)

    assert len(lib.list_fixtures()) >= 5
    dimmer_def = lib.get("Generic", "Dimmer")
    assert dimmer_def.manufacturer == "Generic"

    # Search
    matches = lib.search("rgb")
    assert len(matches) >= 3

    # Instantiate through library
    dev = lib.instantiate(
        "Generic", "LED RGB", fixture_id=5, label="L5", universe=1, address=1
    )
    assert dev.fixture_id == 5
    assert dev.channel_count() == 3


# ---------------------------------------------------------------------------
# Builtin Fixtures
# ---------------------------------------------------------------------------


def test_builtin_definitions() -> None:
    dim8 = create_dimmer_definition(fine=False)
    assert dim8.default_mode().channel_count() == 1
    assert dim8.fixture_type == FixtureType.DIMMER

    dim16 = create_dimmer_definition(fine=True)
    assert dim16.default_mode().channel_count() == 2

    rgb = create_rgb_definition()
    assert rgb.default_mode().channel_count() == 3
    assert rgb.color_profile is not None

    rgbw = create_rgbw_definition()
    assert rgbw.default_mode().channel_count() == 4
    assert rgbw.color_profile is not None

    rgba = create_rgba_definition()
    assert rgba.default_mode().channel_count() == 4
    assert rgba.color_profile is not None


# ---------------------------------------------------------------------------
# Color Science & Matching
# ---------------------------------------------------------------------------


def test_srgb_to_xyz_and_back() -> None:
    rgb = sRGB(1.0, 0.0, 0.0)
    xyz = rgb.to_XYZ()
    # Pure red XYZ
    assert xyz.X > 0.0
    assert xyz.Y > 0.0

    restored_rgb = xyz.to_sRGB()
    assert pytest.approx(restored_rgb.r, abs=1e-3) == 1.0
    assert pytest.approx(restored_rgb.g, abs=1e-3) == 0.0
    assert pytest.approx(restored_rgb.b, abs=1e-3) == 0.0


def test_cie_xyy_to_xyz_and_back() -> None:
    # Standard D65 white point
    cie = CIExyY(0.3127, 0.3290, 100.0)
    xyz = cie.to_XYZ()
    assert pytest.approx(xyz.Y, abs=1e-2) == 100.0

    restored_cie = xyz.to_xyY()
    assert pytest.approx(restored_cie.x, abs=1e-3) == 0.3127
    assert pytest.approx(restored_cie.y, abs=1e-3) == 0.3290


def test_srgb_hex_and_clamping() -> None:
    rgb = sRGB.from_hex("#00ff00")
    assert rgb.r == 0.0
    assert rgb.g == 1.0
    assert rgb.b == 0.0
    assert rgb.to_hex() == "#00FF00"


def test_delta_e76() -> None:
    xyz1 = CIEXYZ(95.04, 100.0, 108.88)
    xyz2 = CIEXYZ(95.04, 100.0, 108.88)
    assert delta_e76(xyz1, xyz2) == pytest.approx(0.0)

    xyz3 = CIEXYZ(20.0, 20.0, 20.0)
    assert delta_e76(xyz1, xyz3) > 10.0


def test_color_matcher_nnls() -> None:
    # Build RGB profile
    profile = profile_from_emitters(
        "TestRGB",
        [
            ("Red", 0.64, 0.33, 21.26, 625.0),
            ("Green", 0.30, 0.60, 71.52, 525.0),
            ("Blue", 0.15, 0.06, 7.22, 465.0),
        ],
    )
    matcher = ColorMatcher([profile])

    # Match pure red
    res_red = matcher.match_srgb(255, 0, 0)["TestRGB"]
    assert res_red.dmx_values[0] == pytest.approx(255, abs=5)
    assert res_red.dmx_values[1] == 0
    assert res_red.dmx_values[2] == 0
    assert res_red.delta_e < 3.0

    # Match white
    res_white = matcher.match_srgb(255, 255, 255)["TestRGB"]
    for val in res_white.dmx_values:
        assert val > 200

    # Match hex
    res_hex = matcher.match_hex("#0000ff")["TestRGB"]
    assert res_hex.dmx_values[2] == pytest.approx(255, abs=5)


# ---------------------------------------------------------------------------
# GDTF Importer
# ---------------------------------------------------------------------------


def test_gdtf_importer_sanity() -> None:
    importer = GdtfImporter()
    assert GDTF_ATTRIBUTE_MAP["Dimmer"] == ChannelType.INTENSITY
    assert GDTF_ATTRIBUTE_MAP["Pan"] == ChannelType.PAN
    assert GDTF_ATTRIBUTE_MAP["ColorAdd_R"] == ChannelType.RED

    if not HAS_PYGDTF:
        with pytest.raises(ImportError):
            importer.load("non_existent.gdtf")
        with pytest.raises(ImportError):
            importer.load_from_bytes(b"dummy")


# ---------------------------------------------------------------------------
# Physical Parameters and Moving Head Tests
# ---------------------------------------------------------------------------


def test_channel_physical_conversion() -> None:
    ch = Channel(
        channel_type=ChannelType.PAN,
        universe=1,
        address=1,
        physical_min=-270.0,
        physical_max=270.0,
        physical_unit="deg",
    )
    assert ch.physical_value == pytest.approx(-270.0)

    # Convert center (0 deg) -> 128 (approx)
    dmx_center = ch.physical_to_dmx(0.0)
    assert dmx_center == 128
    ch.set_physical_value(0.0)
    assert ch.value == 128
    assert ch.physical_value == pytest.approx(0.88, abs=1.5)  # 8-bit resolution

    # Min and max bounds
    assert ch.physical_to_dmx(-270.0) == 0
    assert ch.physical_to_dmx(270.0) == 255
    # Clamping
    assert ch.physical_to_dmx(-300.0) == 0
    assert ch.physical_to_dmx(500.0) == 255


def test_lighting_device_pan_tilt_physical_16bit() -> None:
    fix_def = create_moving_head_definition()
    dev = fix_def.instantiate(fixture_id=1, label="Spot1", universe=1, address=1)

    assert dev.pan_degrees == pytest.approx(-270.0)
    assert dev.tilt_degrees == pytest.approx(-135.0)

    # Set center positions
    dev.set_position_degrees(0.0, 0.0)
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.01)
    assert dev.tilt_degrees == pytest.approx(0.0, abs=0.01)

    # Check 16-bit values at center
    assert dev.pan_16bit == pytest.approx(32768, abs=2)
    assert dev.tilt_16bit == pytest.approx(32768, abs=2)

    # Check exact positive angle
    dev.set_pan_degrees(135.0)  # 3/4 of range -> ~49151
    assert dev.pan_degrees == pytest.approx(135.0, abs=0.01)
    assert dev.pan_16bit == pytest.approx(49151, abs=2)

    # Clamping beyond physical range
    dev.set_pan_degrees(360.0)
    assert dev.pan_degrees == pytest.approx(270.0, abs=0.01)
    dev.set_tilt_degrees(-200.0)
    assert dev.tilt_degrees == pytest.approx(-135.0, abs=0.01)

    # Raw 16-bit setters
    dev.set_pan_16bit(0)
    assert dev.pan_degrees == pytest.approx(-270.0, abs=0.01)
    dev.set_pan_16bit(65535)
    assert dev.pan_degrees == pytest.approx(270.0, abs=0.01)

    # Legacy 8-bit setters
    dev.set_pan(128)
    assert dev.pan_16bit == 32768
    tilt_ch = dev.get_channel(ChannelType.TILT)
    assert tilt_ch is not None
    assert dev.pan_tilt == (128, tilt_ch.value)


def test_lighting_device_pan_tilt_non_contiguous_and_inverted() -> None:
    # Mode with Fine in front of Coarse (Fine @ offset 0, Coarse @ offset 5)
    mode = DmxModeDefinition(
        name="InvertedPan",
        channel_defs=[
            ChannelDefinition(
                ChannelType.PAN,
                offset=5,
                fine_offset=0,
                label="Pan",
                physical_min=-180.0,
                physical_max=180.0,
                physical_unit="deg",
            )
        ],
    )
    fix_def = FixtureDefinition("Test", "InvertedPanSpot", dmx_modes=[mode])
    dev = fix_def.instantiate(fixture_id=2, label="InvertedDev", universe=1, address=1)

    # Set +90 degrees -> 3/4 of 360 deg range -> val_16 = 49151 (0xBFFF)
    dev.set_pan_degrees(90.0)
    assert dev.pan_degrees == pytest.approx(90.0, abs=0.01)

    dmx = dev.dmx_values()
    # Fine is @ addr 1 (offset 0), Coarse is @ addr 6 (offset 5)
    coarse_val = dmx[(1, 6)]
    fine_val = dmx[(1, 1)]
    reconstructed = (coarse_val << 8) | fine_val
    assert reconstructed == pytest.approx(49151, abs=2)


def test_lighting_device_optical_strobe_cct_physical() -> None:
    fix_def = create_moving_head_definition()
    dev = fix_def.instantiate(fixture_id=3, label="OpticSpot", universe=1, address=1)

    # Zoom (10 deg to 35 deg)
    assert dev.zoom_degrees == pytest.approx(10.0, abs=0.1)
    dev.set_zoom_degrees(22.5)  # exact midpoint
    assert dev.zoom_degrees == pytest.approx(22.5, abs=0.2)
    dev.set_zoom_degrees(50.0)  # clamped to max
    assert dev.zoom_degrees == pytest.approx(35.0, abs=0.1)

    # Shutter / Strobe (1 Hz to 25 Hz)
    assert dev.strobe_hz == pytest.approx(1.0, abs=0.1)
    dev.set_strobe_hz(13.0)  # midpoint
    assert dev.strobe_hz == pytest.approx(13.0, abs=0.2)

    # Add a CCT channel to test color temperature
    cct_ch = Channel(
        channel_type=ChannelType.COLOR_TEMP,
        universe=1,
        address=10,
        physical_min=2700.0,
        physical_max=6500.0,
        physical_unit="K",
    )
    dev.add_channel(cct_ch)
    assert dev.color_temp_kelvin == pytest.approx(2700.0, abs=10.0)
    dev.set_color_temp_kelvin(4600.0)
    assert dev.color_temp_kelvin == pytest.approx(4600.0, abs=30.0)


def test_moving_head_builtin_library() -> None:
    lib = populate_builtin_library()
    spot_def = lib.get("Generic", "Moving Head Spot")
    assert spot_def is not None
    assert spot_def.fixture_type == FixtureType.MOVING_HEAD
    assert spot_def.default_mode().footprint() == 8


def test_physical_serialization() -> None:
    fix_def = create_moving_head_definition()
    dev = fix_def.instantiate(
        fixture_id=10, label="SerializedHead", universe=1, address=1
    )
    dev.set_position_degrees(45.0, -30.0)
    dev.set_zoom_degrees(20.0)

    data = dev.to_dict()
    # Verify physical metadata exists in serialized dictionary
    pan_dict = [
        c for c in data["channels"] if c["channel_type"] == "pan" and not c["fine"]
    ][0]
    assert pan_dict["physical_min"] == -270.0
    assert pan_dict["physical_max"] == 270.0
    assert pan_dict["physical_unit"] == "deg"

    # Restore from dict
    restored = LightingDevice.from_dict(data)
    assert restored.pan_degrees == pytest.approx(45.0, abs=0.05)
    assert restored.tilt_degrees == pytest.approx(-30.0, abs=0.05)
    assert restored.zoom_degrees == pytest.approx(20.0, abs=0.2)


def test_gdtf_physical_adaptation() -> None:
    importer = GdtfImporter()
    gdtf_channel = {
        "attribute": "Pan",
        "offset": [1, 2],
        "default": 0,
        "logical_channels": [
            {
                "channel_functions": [
                    {
                        "attribute": "Pan",
                        "dmx_from": 0,
                        "dmx_to": 65535,
                        "physical_from": -270.0,
                        "physical_to": 270.0,
                    }
                ]
            }
        ],
    }
    cd = importer._adapt_channel(gdtf_channel)
    assert cd is not None
    assert cd.physical_min == -270.0
    assert cd.physical_max == 270.0
    assert cd.physical_unit == "deg"


def test_channel_definition_24bit() -> None:
    cd = ChannelDefinition(
        ChannelType.PAN,
        offset=0,
        fine_offset=1,
        ultra_fine_offset=2,
        label="Pan",
        physical_min=-270.0,
        physical_max=270.0,
        physical_unit="deg",
    )
    channels = cd.to_channel(universe=1, base_address=1)
    assert len(channels) == 3
    coarse, fine, ultra = channels[0], channels[1], channels[2]
    assert coarse.is_coarse and not coarse.is_fine and not coarse.is_ultra_fine
    assert coarse.resolution_byte_index == 0
    assert fine.is_fine and not fine.is_coarse and not fine.is_ultra_fine
    assert fine.resolution_byte_index == 1
    assert ultra.is_ultra_fine and not ultra.is_coarse and not ultra.is_fine
    assert ultra.resolution_byte_index == 2
    assert ultra.label == "Pan_ultra_fine"
    assert ultra.address == 3


def test_moving_head_24bit_mode() -> None:
    fix_def = create_moving_head_definition()
    assert len(fix_def.dmx_modes) == 2
    mode_24 = fix_def.get_mode("Extended 24-bit 11ch")
    assert mode_24.channel_count() == 11
    assert mode_24.footprint() == 11

    dev = fix_def.instantiate(
        fixture_id=1,
        label="MH24",
        universe=1,
        address=1,
        mode_name="Extended 24-bit 11ch",
    )
    assert dev.channel_count() == 11
    assert dev.has_physical_dimmer
    assert dev.has_16bit_dimmer
    assert dev.has_24bit_dimmer


def test_lighting_device_24bit_controls() -> None:
    fix_def = create_moving_head_definition()
    dev = fix_def.instantiate(
        fixture_id=1,
        label="MH24",
        universe=1,
        address=1,
        mode_name="Extended 24-bit 11ch",
    )

    # 1. Intensity 24-bit
    dev.set_intensity_24bit(0)
    assert dev.intensity_24bit == 0
    dim_coarse = dev.get_channel(ChannelType.INTENSITY)
    assert dim_coarse is not None
    dim_fine = [
        c for c in dev.channels if c.channel_type == ChannelType.INTENSITY and c.fine
    ][0]
    dim_ultra = [
        c
        for c in dev.channels
        if c.channel_type == ChannelType.INTENSITY and c.ultra_fine
    ][0]
    assert dim_coarse.value == 0
    assert dim_fine.value == 0
    assert dim_ultra.value == 0

    # Half intensity in 24-bit: 8388608 -> coarse=128, fine=0, ultra=0
    dev.set_intensity_24bit(8388608)
    assert dim_coarse.value == 128
    assert dim_fine.value == 0
    assert dim_ultra.value == 0
    assert dev.intensity_24bit == 8388608

    # Arbitrary 24-bit value: 0x123456 = 1193046
    dev.set_intensity_24bit(0x123456)
    assert dim_coarse.value == 0x12
    assert dim_fine.value == 0x34
    assert dim_ultra.value == 0x56
    assert dev.intensity_24bit == 0x123456

    # 2. Pan and Tilt 24-bit
    dev.set_position_24bit(0xABCDEF, 0x112233)
    assert dev.pan_24bit == 0xABCDEF
    assert dev.tilt_24bit == 0x112233
    assert dev.position_24bit == (0xABCDEF, 0x112233)

    # 3. 24-bit physical degrees
    # Center 0.0 deg for Pan (-270 to +270) -> norm=0.5 -> 0x800000 = 8388608
    dev.set_position_degrees(0.0, 0.0)
    assert dev.pan_24bit == 8388608
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.0001)
    assert dev.tilt_degrees == pytest.approx(0.0, abs=0.0001)

    # Micro-angle shift: +1.0 deg
    dev.set_pan_degrees(1.0)
    assert dev.pan_degrees == pytest.approx(1.0, abs=0.0001)


def test_24bit_serialization() -> None:
    fix_def = create_moving_head_definition()
    dev = fix_def.instantiate(
        fixture_id=5,
        label="Spot24",
        universe=1,
        address=1,
        mode_name="Extended 24-bit 11ch",
    )
    dev.set_pan_24bit(0xFEDCBA)
    dev.set_intensity_24bit(0x654321)

    data = dev.to_dict()
    restored = LightingDevice.from_dict(data)
    assert restored.has_24bit_dimmer
    assert restored.pan_24bit == 0xFEDCBA
    assert restored.intensity_24bit == 0x654321


def test_gdtf_24bit_adaptation() -> None:
    importer = GdtfImporter()
    gdtf_channel = {
        "attribute": "Pan",
        "offset": [1, 2, 3],
        "default": 0,
        "logical_channels": [
            {
                "channel_functions": [
                    {
                        "attribute": "Pan",
                        "dmx_from": 0,
                        "dmx_to": 16777215,
                        "physical_from": -270.0,
                        "physical_to": 270.0,
                    }
                ]
            }
        ],
    }
    cd = importer._adapt_channel(gdtf_channel)
    assert cd is not None
    assert cd.offset == 0
    assert cd.fine_offset == 1
    assert cd.ultra_fine_offset == 2
