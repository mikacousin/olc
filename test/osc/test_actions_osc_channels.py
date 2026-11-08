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
"""Unit tests for Lot 2 OSC: paged channels grid, encoders, and color control."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import numpy as np

from olc.core.app import CoreApplication
from olc.core.backends.osc.channels_grid import ChannelsGridManager
from olc.core.backends.osc.delegate import OSCDelegate
from olc.define import MAX_CHANNELS
from olc.devices.channel import ChannelType


def _setup_app_with_patch() -> tuple[CoreApplication, MagicMock]:
    """Create CoreApplication with mock engine, mock backend and patched fixtures."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {
        "user": np.full(MAX_CHANNELS, -1, dtype=np.int16),
        "sequence": np.zeros(MAX_CHANNELS, dtype=np.int16),
        "faders": np.zeros(MAX_CHANNELS, dtype=np.int16),
    }
    mock_dmx.effective_intensity_mult = 1.0

    def mock_get_composite(idx: int) -> tuple[int, dict]:
        user_val = mock_dmx.levels["user"][idx]
        return (int(max(0, user_val)), {})

    mock_dmx.get_composite_level.side_effect = mock_get_composite
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # Patch Dimmer on Ch 1
    dimmer_def = app.lightshow.fixture_library.get_by_key("Generic:Dimmer")
    assert dimmer_def is not None
    app.lightshow.patch.patch_device(1, dimmer_def, 1, 1, label="Face Cour")

    # Patch Moving Head Spot on Ch 2
    spot_def = app.lightshow.fixture_library.get_by_key("Generic:Moving Head Spot")
    assert spot_def is not None
    app.lightshow.patch.patch_device(2, spot_def, 1, 2, label="Spot 1")
    # Center tilt to 0.0 deg for relative tests
    spot = app.lightshow.patch.devices[2]
    spot.set_pan_degrees(0.0)
    spot.set_tilt_degrees(0.0)

    # Patch RGB LED on Ch 3
    rgb_def = app.lightshow.fixture_library.get_by_key("Generic:LED RGB")
    assert rgb_def is not None
    app.lightshow.patch.patch_device(3, rgb_def, 1, 20, label="Wash Cour")

    return app, mock_engine


def test_channels_grid_manager_paging() -> None:
    """Test ChannelsGridManager pagination math and snapshot info."""
    app, _ = _setup_app_with_patch()
    grid = ChannelsGridManager(app, grid_size=24, start_channel=1)

    assert grid.grid_size == 24
    assert grid.start_channel == 1
    assert grid.current_page == 1
    assert grid.total_pages == 43
    assert grid.end_channel == 24
    assert grid.page_info == (1, 43, 1, 24)

    # Next page
    grid.next_page()
    assert grid.start_channel == 25
    assert grid.current_page == 2
    assert grid.end_channel == 48

    # Prev page
    grid.prev_page()
    assert grid.start_channel == 1
    assert grid.current_page == 1

    # Jump to channel 100
    grid.start_channel = 100
    assert grid.start_channel == 100
    assert grid.current_page == 5
    assert grid.get_cell_for_channel(100) == 1
    assert grid.get_cell_for_channel(105) == 6
    assert grid.get_cell_for_channel(1) is None
    assert grid.get_channel_for_cell(1) == 100
    assert grid.get_channel_for_cell(6) == 105

    # Check cell info on page 1
    grid.start_channel = 1
    info1 = grid.get_cell_info(1)
    assert info1["channel"] == 1
    assert info1["label"] == "Face Cour"
    assert info1["selected"] == 0

    snapshot = grid.get_page_snapshot()
    assert len(snapshot) == 24
    assert snapshot[0]["channel"] == 1
    assert snapshot[1]["channel"] == 2
    assert snapshot[2]["channel"] == 3


def test_device_pan_tilt_actions() -> None:
    """Test DevicePanTiltAdjustAction and DeviceSetPanTiltAction with undo/redo."""
    app, _ = _setup_app_with_patch()
    spot = app.lightshow.patch.devices[2]
    initial_pan = spot.pan_degrees
    initial_tilt = spot.tilt_degrees

    # 1. Relative adjust
    app.action_registry.execute("device.adjust_pan_tilt", 15.0, -10.0, channels=[2])
    assert spot.pan_degrees == initial_pan + 15.0
    assert spot.tilt_degrees == initial_tilt - 10.0

    # Undo
    app.history.undo()
    assert spot.pan_degrees == initial_pan
    assert spot.tilt_degrees == initial_tilt

    # Redo
    app.history.redo()
    assert spot.pan_degrees == initial_pan + 15.0
    assert spot.tilt_degrees == initial_tilt - 10.0

    # 2. Absolute set
    app.action_registry.execute(
        "device.set_pan_tilt", pan=45.0, tilt=30.0, channels=[2]
    )
    assert spot.pan_degrees == 45.0
    assert spot.tilt_degrees == 30.0

    app.history.undo()
    assert spot.pan_degrees == initial_pan + 15.0


def test_device_set_color_action() -> None:
    """Test DeviceSetColorAction with RGB float and 0-255 values, plus undo/redo."""
    app, _ = _setup_app_with_patch()
    rgb_dev = app.lightshow.patch.devices[3]

    # 1. Set normalized float color
    app.action_registry.execute("device.set_color", 1.0, 0.5, 0.2, channels=[3])
    srgb = rgb_dev.color_srgb
    assert abs(srgb.r - 1.0) < 0.01
    assert abs(srgb.g - 0.5) < 0.01
    assert abs(srgb.b - 0.2) < 0.01

    # Undo
    app.history.undo()
    old_srgb = rgb_dev.color_srgb
    assert old_srgb.r != 1.0 or old_srgb.g != 0.5

    # Redo
    app.history.redo()
    assert abs(rgb_dev.color_srgb.g - 0.5) < 0.01

    # 2. Set with 0..255 integer-like values
    app.action_registry.execute("device.set_color", 255, 0, 128, channels=[3])
    assert abs(rgb_dev.color_srgb.r - 1.0) < 0.01
    assert abs(rgb_dev.color_srgb.g - 0.0) < 0.01
    assert abs(rgb_dev.color_srgb.b - (128 / 255.0)) < 0.02


def test_osc_channels_subscription_and_paging_routes() -> None:
    """Test /olc/channels/subscribe, page/+, page/-, start, and dump routes."""
    app, mock_engine = _setup_app_with_patch()
    delegate = OSCDelegate(app)

    # 1. Subscribe to channels
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    mock_engine.publish_osc.reset_mock()

    delegate._channels_subscribe(
        "/olc/channels/subscribe", [24, 1], sender_addr=("10.0.0.1", 9000)
    )
    mock_engine.osc_subscriptions.subscribe.assert_called_with(
        "10.0.0.1", 9000, "channels"
    )
    mock_engine.publish_osc.assert_any_call(
        "channels", "/olc/channels/page/info", 1, 43, 1, 24
    )
    mock_engine.publish_osc.assert_any_call("channels", "/olc/cell/1/channel", 1)
    mock_engine.publish_osc.assert_any_call(
        "channels", "/olc/cell/1/label", "Face Cour"
    )

    # 2. Next page
    mock_engine.publish_osc.reset_mock()
    delegate._channels_page_next("/olc/channels/page/+", [])
    assert delegate.channels_grid.current_page == 2
    mock_engine.publish_osc.assert_any_call(
        "channels", "/olc/channels/page/info", 2, 43, 25, 48
    )

    # 3. Prev page
    mock_engine.publish_osc.reset_mock()
    delegate._channels_page_prev("/olc/channels/page/-", [])
    assert delegate.channels_grid.current_page == 1
    mock_engine.publish_osc.assert_any_call(
        "channels", "/olc/channels/page/info", 1, 43, 1, 24
    )

    # 4. Jump start
    mock_engine.publish_osc.reset_mock()
    delegate._channels_start("/olc/channels/start", [50])
    assert delegate.channels_grid.start_channel == 50
    mock_engine.publish_osc.assert_any_call(
        "channels", "/olc/channels/page/info", 3, 43, 50, 73
    )

    # 5. Dump
    mock_engine.publish_osc.reset_mock()
    delegate._channels_dump("/olc/channels/dump", [], sender_addr=("10.0.0.1", 9000))
    mock_engine.publish_osc.assert_called_once()
    assert mock_engine.publish_osc.call_args[0][0] == "channels"
    assert mock_engine.publish_osc.call_args[0][1] == "/olc/channels/dump"
    parsed = json.loads(mock_engine.publish_osc.call_args[0][2])
    assert len(parsed) == 24


def test_osc_cell_and_channel_touch_and_level_routes() -> None:
    """Test interactive /olc/cell/*/touch, /level and /olc/channel/*/touch, /level."""
    app, mock_engine = _setup_app_with_patch()
    delegate = OSCDelegate(app)
    delegate.channels_grid.start_channel = 1

    # 1. Touch cell 1 -> Selects channel 1
    delegate._cell_touch("/olc/cell/1/touch", [1])
    assert 1 in app.selected_channels

    # 2. Touch cell 1 again -> Deselects channel 1
    delegate._cell_touch("/olc/cell/1/touch", [1])
    assert 1 not in app.selected_channels

    # 3. Set level via cell 1
    delegate._cell_level("/olc/cell/1/level", [0.8])
    assert app.backend is not None and app.backend.dmx is not None
    assert app.backend.dmx.levels["user"][0] == round(0.8 * 255)

    # 4. Touch channel 3 directly
    delegate._channel_touch("/olc/channel/3/touch", [1])
    assert 3 in app.selected_channels

    # 5. Set level via channel 3 directly (using 0..255)
    delegate._channel_level("/olc/channel/3/level", [150])
    assert app.backend is not None and app.backend.dmx is not None
    assert app.backend.dmx.levels["user"][2] == 150


def test_osc_wheels_and_color_control_routes() -> None:
    """Test /olc/wheel/*, /olc/selected/pan, tilt and /olc/selected/color/*."""
    app, mock_engine = _setup_app_with_patch()
    delegate = OSCDelegate(app)

    # Select Spot on Ch 2
    app.selected_channels = [2]
    spot = app.lightshow.patch.devices[2]
    init_pan = spot.pan_degrees
    init_tilt = spot.tilt_degrees

    # Wheel Pan & Tilt
    delegate._wheel_pan("/olc/wheel/pan", [5.0])
    assert spot.pan_degrees == init_pan + 5.0

    delegate._wheel_tilt("/olc/wheel/tilt", [-3.0])
    assert spot.tilt_degrees == init_tilt - 3.0

    # Absolute Pan & Tilt
    delegate._selected_pan("/olc/selected/pan", [90.0])
    assert spot.pan_degrees == 90.0

    delegate._selected_tilt("/olc/selected/tilt", [-45.0])
    assert spot.tilt_degrees == -45.0

    # Normalized Pan & Tilt [0.0..1.0]
    delegate._selected_pan_norm("/olc/selected/pan/norm", [0.5])
    assert abs((spot.get_parameter_normalized(ChannelType.PAN) or 0.0) - 0.5) < 0.01

    delegate._selected_tilt_norm("/olc/selected/tilt/norm", [0.75])
    assert abs((spot.get_parameter_normalized(ChannelType.TILT) or 0.0) - 0.75) < 0.01

    # Select RGB LED on Ch 3
    app.selected_channels = [3]
    rgb_dev = app.lightshow.patch.devices[3]

    # Color RGB
    delegate._selected_color_rgb("/olc/selected/color/rgb", [0.8, 0.4, 0.2])
    assert abs(rgb_dev.color_srgb.r - 0.8) < 0.02
    assert abs(rgb_dev.color_srgb.g - 0.4) < 0.02

    # Color HSV (Cyan: H=180 deg, S=1.0, V=1.0 -> R=0, G=1, B=1)
    delegate._selected_color_hsv("/olc/selected/color/hsv", [180.0, 1.0, 1.0])
    assert abs(rgb_dev.color_srgb.r - 0.0) < 0.02
    assert abs(rgb_dev.color_srgb.g - 1.0) < 0.02
    assert abs(rgb_dev.color_srgb.b - 1.0) < 0.02

    # Wheel intensity
    delegate._wheel_intensity("/olc/wheel/intensity", [10])
    assert app.backend is not None and app.backend.dmx is not None
    assert app.backend.dmx.levels["user"][2] >= 0


def test_device_parameter_actions_undo_redo() -> None:
    """Test DeviceSetParameterAction and DeviceAdjustParameterAction with Undo/Redo."""
    app, _ = _setup_app_with_patch()
    spot = app.lightshow.patch.devices[2]

    # 1. Set normalized zoom on channel 2
    init_zoom = spot.get_parameter_normalized(ChannelType.ZOOM) or 0.0
    app.action_registry.execute("device.set_parameter", "zoom", 0.75, channels=[2])
    norm_val = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_val is not None
    assert abs(norm_val - 0.75) < 0.01

    # Undo
    app.history.undo()
    norm_val_undo = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_val_undo is not None
    assert abs(norm_val_undo - init_zoom) < 0.01

    # Redo
    app.history.redo()
    norm_val_redo = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_val_redo is not None
    assert abs(norm_val_redo - 0.75) < 0.01

    # 2. Adjust parameter relatively (delta = +0.1)
    app.action_registry.execute("device.adjust_parameter", "zoom", 0.1, channels=[2])
    norm_val_adj = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_val_adj is not None
    assert abs(norm_val_adj - 0.85) < 0.01

    # Undo relative adjust
    app.history.undo()
    norm_val_revert = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_val_revert is not None
    assert abs(norm_val_revert - 0.75) < 0.01


def test_osc_additional_parameters_routes() -> None:
    """Test OSC delegate routes for beam wheels, selected and device endpoints."""
    app, _ = _setup_app_with_patch()
    delegate = OSCDelegate(app)
    spot = app.lightshow.patch.devices[2]
    rgb_dev = app.lightshow.patch.devices[3]

    # Select spot (ch 2)
    app.selected_channels = [2]
    spot.set_parameter_normalized(ChannelType.ZOOM, 0.0)
    spot.set_parameter_normalized(ChannelType.STROBE, 0.0)

    # 1. Wheels
    delegate._wheel_zoom("/olc/wheel/zoom", [0.2])
    norm_zoom = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_zoom is not None
    assert abs(norm_zoom - 0.2) < 0.01

    delegate._wheel_strobe("/olc/wheel/strobe", [0.3])
    norm_strobe = spot.get_parameter_normalized(ChannelType.STROBE)
    assert norm_strobe is not None
    assert abs(norm_strobe - 0.3) < 0.01

    # Generic wheel
    delegate._wheel_param_generic("/olc/wheel/param/zoom", [-0.05])
    norm_zoom2 = spot.get_parameter_normalized(ChannelType.ZOOM)
    assert norm_zoom2 is not None
    assert abs(norm_zoom2 - 0.15) < 0.01

    # 2. Selected absolute
    delegate._selected_zoom("/olc/selected/zoom", [0.6])
    assert abs((spot.get_parameter_normalized(ChannelType.ZOOM) or 0.0) - 0.6) < 0.01

    delegate._selected_zoom_degrees("/olc/selected/zoom/degrees", [25.0])
    assert spot.zoom_degrees is not None
    assert abs(spot.zoom_degrees - 25.0) < 0.5

    delegate._selected_strobe("/olc/selected/strobe", [0.5])
    assert abs((spot.get_parameter_normalized(ChannelType.STROBE) or 0.0) - 0.5) < 0.01

    delegate._selected_strobe_hz("/olc/selected/strobe/hz", [15.0])
    assert spot.strobe_hz is not None
    assert abs(spot.strobe_hz - 15.0) < 0.5

    # 3. Direct device targeting without selection
    app.selected_channels = []  # Clear selection
    delegate._device_zoom("/olc/device/2/zoom", [0.8])
    assert abs((spot.get_parameter_normalized(ChannelType.ZOOM) or 0.0) - 0.8) < 0.01

    delegate._device_pan("/olc/device/2/pan", [120.0])
    assert abs(spot.pan_degrees - 120.0) < 0.01

    delegate._device_tilt("/olc/device/2/tilt", [-30.0])
    assert abs(spot.tilt_degrees - (-30.0)) < 0.01

    delegate._device_color_rgb("/olc/device/3/color/rgb", [0.2, 0.4, 0.6])
    assert abs(rgb_dev.color_srgb.r - 0.2) < 0.02
    assert abs(rgb_dev.color_srgb.g - 0.4) < 0.02
    assert abs(rgb_dev.color_srgb.b - 0.6) < 0.02

    delegate._device_param_generic("/olc/device/2/param/zoom", [0.45])
    assert abs((spot.get_parameter_normalized(ChannelType.ZOOM) or 0.0) - 0.45) < 0.01
