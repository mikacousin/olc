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
"""Unit tests for semantic HTP/LTP merge modes, curve routing,
and Grand Master isolation.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

from olc.core.app import CoreApplication
from olc.curve import LimitCurve, LinearCurve, SquareRootCurve
from olc.devices.builtin import (
    create_dimmer_definition,
    create_moving_head_definition,
    create_rgb_definition,
)
from olc.devices.device import (
    Channel,
    ChannelType,
    LightingDevice,
    MergeMode,
    get_default_merge_mode,
)
from olc.dmx import Dmx


def test_merge_mode_defaults_and_properties() -> None:
    """Test default merge modes: INTENSITY is HTP, other attributes are LTP."""
    assert get_default_merge_mode(ChannelType.INTENSITY) == MergeMode.HTP
    assert get_default_merge_mode(ChannelType.PAN) == MergeMode.LTP
    assert get_default_merge_mode(ChannelType.TILT) == MergeMode.LTP
    assert get_default_merge_mode(ChannelType.COLOR_WHEEL) == MergeMode.LTP
    assert get_default_merge_mode(ChannelType.GOBO_WHEEL) == MergeMode.LTP
    assert get_default_merge_mode(ChannelType.ZOOM) == MergeMode.LTP
    assert get_default_merge_mode(ChannelType.FOCUS) == MergeMode.LTP
    assert get_default_merge_mode(ChannelType.STROBE) == MergeMode.LTP

    dim_ch = Channel(channel_type=ChannelType.INTENSITY, universe=1, address=1)
    assert dim_ch.merge_mode == MergeMode.HTP
    assert dim_ch.is_htp
    assert not dim_ch.is_ltp

    pan_ch = Channel(channel_type=ChannelType.PAN, universe=1, address=2)
    assert pan_ch.merge_mode == MergeMode.LTP
    assert pan_ch.is_ltp
    assert not pan_ch.is_htp


def test_channel_and_device_serialization_with_merge_mode_and_curve() -> None:
    """Test serialization/deserialization of merge_mode and curve_id."""
    mh_def = create_moving_head_definition()
    dev = mh_def.instantiate(
        fixture_id=10, label="Spot 10", universe=1, address=1, mode_name="Standard 8ch"
    )
    dev.set_curve_id(3)

    data = dev.to_dict()
    assert data["curve_id"] == 3
    dim_dict = next(
        c for c in data["channels"] if c["channel_type"] == ChannelType.INTENSITY.value
    )
    pan_dict = next(
        c for c in data["channels"] if c["channel_type"] == ChannelType.PAN.value
    )
    assert dim_dict["merge_mode"] == "htp"
    assert pan_dict["merge_mode"] == "ltp"

    restored = LightingDevice.from_dict(data)
    assert restored.curve_id == 3
    restored_dim = restored.get_channel(ChannelType.INTENSITY)
    restored_pan = restored.get_channel(ChannelType.PAN)
    assert restored_dim is not None and restored_dim.is_htp
    assert restored_pan is not None and restored_pan.is_ltp


def test_grand_master_isolation_moving_head() -> None:
    """Test that Grand Master (Main Fader) ONLY affects HTP channels,
    leaving LTP channels untouched.
    """
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch
    patch.patch_empty()

    # Patch moving head on device_id 1, universe 1, address 10 (8 channels)
    # Offsets: 0: Pan Coarse, 1: Pan Fine, 2: Tilt Coarse, 3: Tilt Fine,
    #          4: Dimmer, 5: Color Wheel, 6: Gobo Wheel, 7: Shutter/Strobe
    mh_def = create_moving_head_definition()
    spot = patch.patch_device(
        device_id=1,
        fixture_def=mh_def,
        universe=1,
        address=10,
        mode_name="Standard 8ch",
    )

    spot.set_pan_16bit(0x1234)
    spot.set_tilt_16bit(0x5678)
    zoom_ch = spot.get_channel(ChannelType.ZOOM)
    assert zoom_ch is not None
    zoom_ch.set_value(42)
    spot.set_intensity_8bit(200)

    with mock_patch("olc.dmx.RepeatedTimer"):
        dmx = Dmx(backend=None, lightshow=app.lightshow)

        # 1. Main Fader at 100%
        dmx.main_fader.value = 1.0
        dmx.set_levels()

        u1 = dmx.frame[0]
        assert u1[9] == 0x12  # Pan coarse (LTP)
        assert u1[10] == 0x34  # Pan fine (LTP)
        assert u1[11] == 0x56  # Tilt coarse (LTP)
        assert u1[12] == 0x78  # Tilt fine (LTP)
        assert u1[13] == 200  # Dimmer coarse (HTP)
        assert u1[16] == 42  # Zoom (LTP)

        # 2. Main Fader scaled to 50%
        dmx.main_fader.value = 0.5
        dmx.set_levels()

        assert u1[9] == 0x12  # Pan coarse UNCHANGED
        assert u1[10] == 0x34  # Pan fine UNCHANGED
        assert u1[11] == 0x56  # Tilt coarse UNCHANGED
        assert u1[12] == 0x78  # Tilt fine UNCHANGED
        assert u1[13] == 100  # Dimmer SCALED (200 * 0.5 = 100)
        assert u1[16] == 42  # Zoom UNCHANGED

        # 3. Main Fader at 0% (Full Blackout)
        dmx.main_fader.value = 0.0
        dmx.set_levels()

        assert u1[9] == 0x12  # Pan coarse STILL UNCHANGED
        assert u1[10] == 0x34  # Pan fine STILL UNCHANGED
        assert u1[11] == 0x56  # Tilt coarse STILL UNCHANGED
        assert u1[12] == 0x78  # Tilt fine STILL UNCHANGED
        assert u1[13] == 0  # Dimmer BLACKOUT (0)
        assert u1[16] == 42  # Zoom STILL UNCHANGED


def test_device_with_8bit_curve() -> None:
    """Test LightingDevice intensity transfer using an assigned 8-bit curve."""
    dim_def = create_dimmer_definition(fine=False)
    dev = dim_def.instantiate(
        fixture_id=1, label="Dimmer 1", universe=1, address=1, mode_name="8-bit"
    )

    # Attach limit curve capping at 50% (128 / 255)
    limit_curve = LimitCurve(limit=128)
    dev.set_curve(limit_curve)

    dev.set_intensity(1.0)
    # Intensity command is 1.0 (100%), but physical DMX channel is capped at 128
    assert dev.intensity == 1.0
    assert dev.channels[0].value == 128


def test_device_with_16bit_curve() -> None:
    """Test LightingDevice intensity transfer using an assigned 16-bit curve."""
    dim_def = create_dimmer_definition(fine=True)
    dev = dim_def.instantiate(
        fixture_id=1,
        label="Dimmer 16b",
        universe=1,
        address=1,
        mode_name="16-bit",
    )

    sqrt_curve = SquareRootCurve()
    dev.set_curve(sqrt_curve)

    # At 50% normalized input (0.5), sqrt curve gives sqrt(0.5) ≈ 0.7071
    # 0.7071 * 65535 ≈ 46340 (0xB504)
    dev.set_intensity(0.5)

    coarse_ch = dev.channels[0]
    fine_ch = dev.channels[1]
    val_16 = (coarse_ch.value << 8) | fine_ch.value

    expected_16 = sqrt_curve.get_level_16bit(round(0.5 * 65535))
    assert val_16 == expected_16


def test_device_with_24bit_curve() -> None:
    """Test LightingDevice intensity transfer using an assigned 24-bit curve."""
    mh_def = create_moving_head_definition()
    dev = mh_def.instantiate(
        fixture_id=1,
        label="Spot 24b",
        universe=1,
        address=1,
        mode_name="Extended 24-bit 11ch",
    )

    linear_curve = LinearCurve()
    dev.set_curve(linear_curve)

    dev.set_intensity_24bit(0x123456)
    assert dev.intensity_24bit == 0x123456


def test_virtual_dimmer_with_curve() -> None:
    """Test virtual dimmer on RGB fixture applying curve to emitter levels."""
    rgb_def = create_rgb_definition()
    par = rgb_def.instantiate(
        fixture_id=5, label="LED Par", universe=1, address=1, mode_name="RGB 3ch"
    )
    assert par.uses_virtual_dimmer

    limit_curve = LimitCurve(limit=128)
    par.set_curve(limit_curve)

    # Set pure white RGB at 100% intensity
    par.set_color_rgb(255, 255, 255)
    par.set_intensity(1.0)

    # Emitters should be limited to 128
    r_ch = par.get_channel(ChannelType.RED)
    g_ch = par.get_channel(ChannelType.GREEN)
    b_ch = par.get_channel(ChannelType.BLUE)
    assert r_ch is not None and r_ch.value == 128
    assert g_ch is not None and g_ch.value == 128
    assert b_ch is not None and b_ch.value == 128


def test_patch_dimmer_attaches_curve() -> None:
    """Test that PatchManager.patch_dimmer connects curve_id and provider."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch
    patch.patch_empty()

    limit_curve = LimitCurve(limit=128)
    app.lightshow.curves.curves[4] = limit_curve

    dev = patch.patch_dimmer(channel=1, universe=1, address=1, curve=4, fine=False)
    assert dev.curve_id == 4

    dev.set_intensity(1.0)
    assert dev.channels[0].value == 128
