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
# pylint: disable=wrong-spelling-in-comment, wrong-spelling-in-docstring
"""Unit tests for the devices subsystem."""

# pylint: disable=missing-function-docstring, redefined-outer-name

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
