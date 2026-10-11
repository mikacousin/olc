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
"""Unit tests for DeviceInspectorWidget multi-device selection and ColorMatcher."""

# pylint: disable=redefined-outer-name, protected-access

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")

from olc.devices.builtin import (  # noqa: E402
    create_dimmer_definition,
    create_moving_head_definition,
    create_rgba_definition,
    create_rgbw_definition,
)
from olc.devices.device import ChannelRange, ChannelType  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.device_inspector import DeviceInspectorWidget  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order


def test_inspector_heterogeneous_selection_and_ifcb_counts() -> None:
    """Test IFCB scope counts [M/N], Lead Fixture navigation, and disparity."""
    dimmer = create_dimmer_definition().instantiate(1, "Dimmer 1", 1, 1)
    rgbw = create_rgbw_definition().instantiate(2, "LED RGBW 2", 1, 10)
    spot1 = create_moving_head_definition().instantiate(3, "Spot 3", 1, 20)
    spot2 = create_moving_head_definition().instantiate(4, "Spot 4", 1, 40)

    dimmer.set_intensity_percent(50.0)
    rgbw.set_intensity_percent(80.0)
    spot1.set_intensity_percent(50.0)
    spot2.set_intensity_percent(50.0)
    spot1.set_pan_degrees(-30.0)
    spot2.set_pan_degrees(45.0)
    spot1.set_tilt_degrees(15.0)
    spot2.set_tilt_degrees(15.0)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([dimmer, rgbw, spot1, spot2])

    # 1. Check IFCB section counts:
    # Intensity: all 4 devices (dimmer, virtual dimmer on rgbw, physical on spots)
    # Position: 2/4 (spot1, spot2)
    # Color: 1/4 (rgbw)
    # Beam: 2/4 (spot1, spot2)
    counts = inspector.get_section_counts()
    assert counts["intensity"] == (4, 4)
    assert counts["position"] == (2, 4)
    assert counts["color"] == (1, 4)
    assert counts["beam"] == (2, 4)

    # 2. Check disparity detection:
    # Intensity differs (50% vs 80%) -> True
    # Pan differs (-30° vs +45°) -> True
    # Tilt is identical (15° vs 15°) -> False
    assert inspector.is_parameter_disparate("intensity") is True
    assert inspector.is_parameter_disparate("pan") is True
    assert inspector.is_parameter_disparate("tilt") is False

    assert "~ 50.0% [Multi]" in inspector.format_parameter_display("intensity")
    assert "~ -30.0° [Multi]" in inspector.format_parameter_display("pan")
    assert inspector.format_parameter_display("tilt") == "15.0°"

    # 3. Lead Fixture navigation
    assert inspector.lead_device is dimmer
    inspector.next_lead()
    assert inspector.lead_device is rgbw
    inspector.set_lead_device_id(3)
    assert inspector.lead_device is spot1
    inspector.prev_lead()
    assert inspector.lead_device is rgbw


def test_inspector_relative_vs_absolute_mode_and_pad_2d() -> None:
    """Test 2D Pan/Tilt pad target points, relative/absolute mode, and Fan."""
    spot1 = create_moving_head_definition().instantiate(10, "Spot 10", 1, 1)
    spot2 = create_moving_head_definition().instantiate(11, "Spot 11", 1, 20)
    spot3 = create_moving_head_definition().instantiate(12, "Spot 12", 1, 40)

    spot1.set_position_degrees(-20.0, 10.0)
    spot2.set_position_degrees(20.0, -10.0)
    spot3.set_position_degrees(40.0, 0.0)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([spot1, spot2, spot3])

    # Check 2D Pad target points
    pts = inspector.get_target_points()
    assert len(pts) == 3
    assert pts[0]["is_lead"] is True
    assert pts[1]["is_lead"] is False

    # 1. Relative (Delta) mode: move Lead (spot1) from (-20°, +10°) to (0°, +20°)
    # Delta is (+20°, +10°). Spot2 should move from (+20°, -10°) to (+40°, 0°)
    inspector.set_edit_mode("relative")
    inspector.set_pad_position(0.0, 20.0)
    assert spot1.pan_degrees == pytest.approx(0.0, abs=0.5)
    assert spot1.tilt_degrees == pytest.approx(20.0, abs=0.5)
    assert spot2.pan_degrees == pytest.approx(40.0, abs=0.5)
    assert spot2.tilt_degrees == pytest.approx(0.0, abs=0.5)

    # 2. Absolute mode: move all spots to (-45°, -30°)
    inspector.toggle_edit_mode()
    assert inspector.edit_mode == "absolute"
    inspector.set_pad_position(-45.0, -30.0)
    for s in (spot1, spot2, spot3):
        assert s.pan_degrees == pytest.approx(-45.0, abs=0.5)
        assert s.tilt_degrees == pytest.approx(-30.0, abs=0.5)

    # 3. Invert Pan & Center
    inspector.invert_pan()
    assert spot1.pan_degrees == pytest.approx(45.0, abs=0.5)
    inspector.center_position()
    assert spot1.pan_degrees == pytest.approx(0.0, abs=0.5)
    assert spot1.tilt_degrees == pytest.approx(0.0, abs=0.5)

    # 4. Fan Pan across the 3 spots from -60° to +60° -> [-60°, 0°, +60°]
    inspector.fan_pan(-60.0, 60.0)
    assert spot1.pan_degrees == pytest.approx(-60.0, abs=0.5)
    assert spot2.pan_degrees == pytest.approx(0.0, abs=0.5)
    assert spot3.pan_degrees == pytest.approx(60.0, abs=0.5)

    # 5. Align to Lead (#10 at -60°)
    inspector.align_to_lead()
    assert spot2.pan_degrees == pytest.approx(-60.0, abs=0.5)
    assert spot3.pan_degrees == pytest.approx(-60.0, abs=0.5)


def test_inspector_scientific_color_picker_multi_spectrum() -> None:
    """Test ColorMatcher NNLS translation across RGBW and RGBA fixtures."""
    rgbw = create_rgbw_definition().instantiate(1, "LED RGBW", 1, 1)
    rgba = create_rgba_definition().instantiate(2, "LED RGBA", 1, 10)
    dimmer = create_dimmer_definition().instantiate(3, "Dimmer", 1, 20)

    rgbw.set_intensity(1.0)
    rgba.set_intensity(1.0)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([rgbw, rgba, dimmer])

    # Apply warm amber-orange hex color (#FF8800)
    delta_e_map = inspector.apply_color_hex("#FF8800")

    # Both RGBW and RGBA should be matched, while Dimmer is untouched
    assert 1 in delta_e_map
    assert 2 in delta_e_map
    assert 3 not in delta_e_map
    assert inspector.last_delta_e >= 0.0

    # RGBA has dedicated Amber emitter so its Amber channel should be active
    amber_ch = rgba.get_channel(ChannelType.AMBER)
    assert amber_ch is not None
    assert amber_ch.value > 0


def test_inspector_physical_and_discrete_parameters() -> None:
    """Test Zoom physical parameter and discrete Gobo ChannelRange activation."""
    spot1 = create_moving_head_definition().instantiate(1, "Spot 1", 1, 1)
    spot2 = create_moving_head_definition().instantiate(2, "Spot 2", 1, 20)

    # Add a Gobo channel with discrete ranges to spot1
    gobo_ch = spot1.channels[0]
    gobo_ch.ranges = [
        ChannelRange("Open", ChannelType.PAN, 0, 15, snap_value=0),
        ChannelRange("Gobo 1 Star", ChannelType.PAN, 16, 50, snap_value=32),
    ]

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([spot1, spot2])
    inspector.set_edit_mode("absolute")

    inspector.apply_physical_parameter(ChannelType.ZOOM, 25.0)
    assert spot1.zoom_degrees == pytest.approx(25.0, abs=0.5)
    assert spot2.zoom_degrees == pytest.approx(25.0, abs=0.5)

    activated = inspector.apply_discrete_range(ChannelType.PAN, "Gobo 1 Star")
    assert activated == 1
    assert gobo_ch.value == 32


@pytest.mark.gui
def test_device_inspector_tab_menu_action(app_gui: Application) -> None:
    """Test opening and closing Device Inspector tab from the menu action."""
    app_gui.activate_action("device_inspector", None)
    process_events()

    assert app_gui.tabs is not None
    inspector_tab = app_gui.tabs.tabs.get("device_inspector")
    assert isinstance(inspector_tab, DeviceInspectorWidget)

    # Close the tab via its close callback
    inspector_tab.on_close_icon(inspector_tab)
    process_events()
    assert app_gui.tabs.tabs.get("device_inspector") is None
