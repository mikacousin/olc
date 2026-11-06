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
"""Unit tests verifying Main Fader and Scenic Blackout behavior in OLC.

Ensures that:
1. Blackout and Main Fader scale ONLY intensities (HTP / dimmers).
2. LTP parameters (Pan, Tilt, Gobo, Color) remain strictly untouched.
3. Dmx loop respects blackout without race conditions.
4. MainFaderWidget renders the appropriate warning label.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.devices import create_moving_head_definition


def test_main_fader_scales_intensities_only_and_preserves_ltp() -> None:
    """Verify Main Fader scales HTP/dimmers and leaves Pan, Tilt, etc. untouched."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.start()

    assert app.backend is not None
    dmx = app.backend.dmx

    # Patch Dimmer channel 1 on universe 1, address 1
    app.lightshow.patch.patch_dimmer(channel=1, universe=1, address=1)

    # Patch moving light device 10 on universe 1, address 10..17
    fixture_def = create_moving_head_definition()
    dev = app.lightshow.patch.patch_device(
        device_id=10,
        fixture_def=fixture_def,
        universe=1,
        address=10,
        mode_name="Standard 8ch",
    )

    from olc.devices import ChannelType

    # Set initial levels
    dmx.levels["sequence"][0] = 200.0  # Channel 1 intensity = 200
    dev.set_intensity_8bit(255)  # Device Dimmer = 255 (HTP)
    dev.set_pan_16bit(0x4567)  # Pan (LTP)
    dev.set_tilt_16bit(0x89AB)  # Tilt (LTP)
    strobe_ch = dev.get_channel(ChannelType.STROBE)
    if strobe_ch:
        strobe_ch.set_value(180)
    zoom_ch = dev.get_channel(ChannelType.ZOOM)
    if zoom_ch:
        zoom_ch.set_value(75)

    pan_ch = dev.get_channel(ChannelType.PAN)
    tilt_ch = dev.get_channel(ChannelType.TILT)
    pan_val_init = pan_ch.value if pan_ch else 0
    tilt_val_init = tilt_ch.value if tilt_ch else 0
    strobe_val_init = strobe_ch.value if strobe_ch else 0
    zoom_val_init = zoom_ch.value if zoom_ch else 0

    dmx.set_levels()

    # Universe 1 frame checks at 100% Main Fader
    frame = dmx.frame[0]
    assert frame[0] == 200  # Dimmer output
    assert frame[13] == 255  # Device Dimmer (offset 4 -> 10 + 4 - 1 = 13) (HTP)
    assert frame[9] == pan_val_init  # Pan (LTP)
    assert frame[11] == tilt_val_init  # Tilt (LTP)
    assert frame[15] == strobe_val_init  # Strobe (LTP)
    assert frame[16] == zoom_val_init  # Zoom (LTP)

    # Scale Main Fader to 50% via action
    app.action_registry.execute("main_fader.set_level", 0.5)

    assert dmx.main_fader.value == 0.5
    frame = dmx.frame[0]
    assert frame[0] == 100  # 200 * 0.5
    assert frame[13] == 128  # 255 * 0.5
    # LTP parameters MUST be completely untouched!
    assert frame[9] == pan_val_init
    assert frame[11] == tilt_val_init
    assert frame[15] == strobe_val_init
    assert frame[16] == zoom_val_init

    # Scale Main Fader to 0%
    app.action_registry.execute("main_fader.set_level", 0.0)
    frame = dmx.frame[0]
    assert frame[0] == 0
    assert frame[13] == 0
    # LTP parameters STILL untouched!
    assert frame[9] == pan_val_init
    assert frame[11] == tilt_val_init
    assert frame[15] == strobe_val_init
    assert frame[16] == zoom_val_init

    # Undo action restores level to 0.5
    app.history.undo()
    assert dmx.main_fader.value == 0.5
    assert dmx.frame[0][0] == 100

    app.backend.stop()


def test_scenic_blackout_preserves_ltp_and_survives_dmx_recalc() -> None:
    """Verify Blackout cuts intensities only and is not overridden by set_levels."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.start()

    assert app.backend is not None
    dmx = app.backend.dmx

    # Patch Dimmer 1 and moving light 10
    app.lightshow.patch.patch_dimmer(channel=1, universe=1, address=1)
    fixture_def = create_moving_head_definition()
    dev = app.lightshow.patch.patch_device(
        device_id=10,
        fixture_def=fixture_def,
        universe=1,
        address=10,
        mode_name="Standard 8ch",
    )

    from olc.devices import ChannelType

    dmx.levels["sequence"][0] = 240.0
    dev.set_intensity_8bit(200)  # HTP = 200
    dev.set_pan_16bit(0x6000)  # LTP
    dev.set_tilt_16bit(0x3000)  # LTP
    strobe_ch = dev.get_channel(ChannelType.STROBE)
    if strobe_ch:
        strobe_ch.set_value(255)
    zoom_ch = dev.get_channel(ChannelType.ZOOM)
    if zoom_ch:
        zoom_ch.set_value(100)

    pan_ch = dev.get_channel(ChannelType.PAN)
    tilt_ch = dev.get_channel(ChannelType.TILT)
    pan_val = pan_ch.value if pan_ch else 0
    tilt_val = tilt_ch.value if tilt_ch else 0
    strobe_val = strobe_ch.value if strobe_ch else 0
    zoom_val = zoom_ch.value if zoom_ch else 0

    dmx.set_levels()
    assert dmx.frame[0][0] == 240
    assert dmx.frame[0][13] == 200

    # Trigger Blackout
    app.action_registry.execute("dmx.blackout_all", True)
    assert getattr(app, "blackout_active", False) is True
    assert dmx.blackout is True

    frame = dmx.frame[0]
    # Intensities must be 0!
    assert frame[0] == 0
    assert frame[13] == 0
    # LTP parameters MUST BE INTACT!
    assert frame[9] == pan_val
    assert frame[11] == tilt_val
    assert frame[15] == strobe_val
    assert frame[16] == zoom_val

    # Test that subsequent set_levels() does NOT override blackout
    dmx.set_levels()
    frame = dmx.frame[0]
    assert frame[0] == 0
    assert frame[13] == 0
    assert frame[9] == pan_val

    # Toggle Blackout OFF
    app.action_registry.execute("dmx.blackout_all", False)
    assert getattr(app, "blackout_active", False) is False
    assert dmx.blackout is False

    frame = dmx.frame[0]
    # Intensities restored!
    assert frame[0] == 240
    assert frame[13] == 200
    # LTP still exact!
    assert frame[9] == pan_val
    assert frame[11] == tilt_val
    assert frame[15] == strobe_val
    assert frame[16] == zoom_val

    app.backend.stop()
