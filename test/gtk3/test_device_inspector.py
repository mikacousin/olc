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
from olc.gtk3.widgets.color_picker import ConsoleColorPicker  # noqa: E402

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


def test_inspector_color_is_solved_once_per_profile() -> None:
    """A large mixed selection costs one NNLS solve per distinct color profile."""
    fixtures = [
        create_rgbw_definition().instantiate(i, f"W{i}", 1, 1 + 8 * i)
        for i in range(1, 7)
    ] + [
        create_rgba_definition().instantiate(100 + i, f"A{i}", 2, 1 + 8 * i)
        for i in range(1, 5)
    ]
    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices(fixtures)

    delta_e_map = inspector.apply_color_hex("#FF8800")

    assert len(delta_e_map) == 10
    assert inspector._color_solver.solves == 2  # pylint: disable=protected-access
    inspector.apply_color_hex("#FF8800")
    assert inspector._color_solver.solves == 2  # pylint: disable=protected-access


def test_inspector_color_picker_gamut_and_multi_reticles() -> None:
    """Gamut hull and multi-fixture reticle points track selection and Lead."""
    rgbw = create_rgbw_definition().instantiate(1, "LED RGBW", 1, 1)
    rgba = create_rgba_definition().instantiate(2, "LED RGBA", 1, 10)
    rgbw.set_color_hex("#FF0000")
    rgba.set_color_hex("#0000FF")

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([rgbw, rgba])

    picker = inspector.color_picker
    assert len(picker.gamut_xy) >= 3
    assert len(picker.gamut_hs) >= 3
    assert len(picker.fixture_points) == 2
    assert picker.fixture_points[0].device_id == 1
    assert picker.fixture_points[0].is_lead is True
    assert picker.fixture_points[1].device_id == 2
    assert picker.fixture_points[1].is_lead is False

    # Switch Lead to fixture #2
    inspector.next_lead()
    assert picker.fixture_points[0].is_lead is False
    assert picker.fixture_points[1].is_lead is True


def test_inspector_emitter_faders_relative_color_and_fan() -> None:
    """Test emitter fader visibility, relative HS color shift, and color fan."""
    rgbw = create_rgbw_definition().instantiate(1, "LED RGBW", 1, 1)
    rgba = create_rgba_definition().instantiate(2, "LED RGBA", 1, 10)
    rgbw.set_intensity(1.0)
    rgba.set_intensity(1.0)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([rgbw])
    picker = inspector.color_picker
    assert picker.emitter_rows["red"].get_visible() is True
    assert picker.emitter_rows["white"].get_visible() is True
    assert picker.emitter_rows["amber"].get_visible() is False
    assert picker.emitter_rows["lime"].get_visible() is False

    # Select both RGBW and RGBA -> both W and A rows become visible
    inspector.set_selected_devices([rgbw, rgba])
    assert picker.emitter_rows["white"].get_visible() is True
    assert picker.emitter_rows["amber"].get_visible() is True

    # Direct emitter level control
    inspector.set_edit_mode("absolute")
    inspector.apply_emitter_level(ChannelType.WHITE, 0.8)
    assert rgbw.get_emitter_level(ChannelType.WHITE) == pytest.approx(0.8)

    # Relative HS color shift: fixture 1 Red (#FF0000), fixture 2 Green (#00FF00)
    rgbw.set_color_srgb(1.0, 0.0, 0.0)
    rgba.set_color_srgb(0.0, 1.0, 0.0)
    inspector.set_edit_mode("relative")
    # Move Lead (fixture 1) from Red to Green (+120 deg) -> fixture 2 shifts to Blue
    inspector.apply_color_srgb(0.0, 1.0, 0.0)
    assert rgbw.color_srgb.g > 0.9
    assert rgba.color_srgb.b > 0.9

    # Color Fan across both fixtures
    inspector.fan_color((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), mode="hs_short")
    assert rgbw.color_srgb.r > 0.9
    assert rgba.color_srgb.b > 0.9


def test_inspector_apply_gel_and_swatchbook_filter() -> None:
    """Test applying Lee/Rosco gels and filtering the Swatchbook with ΔE badges."""
    rgbw = create_rgbw_definition().instantiate(1, "LED RGBW", 1, 1)
    rgbw.set_intensity(1.0)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([rgbw])
    picker = inspector.color_picker

    # Apply L201 (Full C.T. Blue) by code
    gel = inspector.apply_gel("L201")
    assert gel is not None and gel.code == "L201"
    assert rgbw.color_srgb.b > rgbw.color_srgb.r

    # Search 'congo' in swatchbook -> filters to L181 and R382 with ΔE badges
    picker.gel_search_entry.set_text("congo")
    codes = [sw.code for sw in picker.swatch_widgets]
    assert "L181" in codes and "R382" in codes
    assert all(sw.match_level is not None for sw in picker.swatch_widgets)


def test_inspector_stack_pages_and_permanent_intensity() -> None:
    """Test IFCB Stack pages, dynamic [M/N] page titles, and permanent Intensity bar."""
    dimmer = create_dimmer_definition().instantiate(1, "Dimmer 1", 1, 1)
    rgbw = create_rgbw_definition().instantiate(2, "LED RGBW 2", 1, 10)
    spot1 = create_moving_head_definition().instantiate(3, "Spot 3", 1, 20)
    spot2 = create_moving_head_definition().instantiate(4, "Spot 4", 1, 40)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([dimmer, rgbw, spot1, spot2])

    assert inspector.intensity_header_label.get_text() == "INTENSITY [4/4]"
    assert (
        inspector.stack.child_get_property(inspector.position_page, "title")
        == "POSITION [2/4]"
    )
    assert (
        inspector.stack.child_get_property(inspector.color_page, "title")
        == "COLOR [1/4]"
    )
    assert (
        inspector.stack.child_get_property(inspector.beam_page, "title")
        == "BEAM & GOBOS [2/4]"
    )

    for page_name in ("position", "color", "beam"):
        inspector.stack.set_visible_child_name(page_name)
        assert inspector.stack.get_visible_child_name() == page_name


def test_inspector_rotary_encoders_coarse_and_fine() -> None:
    """Test Pan and Tilt rotary encoders in Coarse and Fine (16-bit) modes."""
    spot1 = create_moving_head_definition().instantiate(1, "Spot 1", 1, 1)
    spot2 = create_moving_head_definition().instantiate(2, "Spot 2", 1, 20)
    spot1.set_pan_degrees(0.0)
    spot1.set_tilt_degrees(0.0)
    spot2.set_pan_degrees(10.0)
    spot2.set_tilt_degrees(-10.0)

    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([spot1, spot2])

    # 1 scroll notch (1/36 turn) in Coarse mode = +1.0° delta
    inspector._on_position_encoder("pan", 1.0 / 36.0, is_shift=False)
    assert spot1.pan_degrees == pytest.approx(1.0, abs=0.1)
    assert spot2.pan_degrees == pytest.approx(11.0, abs=0.1)

    # Toggle Fine 16-bit mode: 1 full turn = +1.8° delta
    inspector.fine_position_btn.set_active(True)
    inspector._on_position_encoder("tilt", 1.0, is_shift=False)
    assert spot1.tilt_degrees == pytest.approx(1.8, abs=0.1)
    assert spot2.tilt_degrees == pytest.approx(-8.2, abs=0.1)


@pytest.mark.gui
def test_inspector_intensity_syncs_with_live_view(app_gui: Application) -> None:
    """Test that changing intensity in DeviceInspector updates LiveView and DMX."""
    app_gui.core.lightshow.patch.patch_device(1, create_rgbw_definition(), 1, 1)
    app_gui.activate_action("device_inspector", None)
    process_events()

    assert app_gui.tabs is not None
    inspector = app_gui.tabs.tabs.get("device_inspector")
    assert isinstance(inspector, DeviceInspectorWidget)

    inspector.set_selected_channels([1])
    inspector.apply_intensity_percent(100.0, force_absolute=True)
    process_events()

    assert app_gui.core.backend is not None
    assert int(app_gui.core.backend.dmx.levels["user"][0]) == 255
    assert app_gui.window is not None
    ch_widget = app_gui.window.live_view.channels_view.get_channel_widget(1)
    assert ch_widget is not None
    assert ch_widget.level == 255

    inspector.on_close_icon(inspector)
    process_events()


def test_inspector_apply_color_cie_out_of_gamut_and_in_gamut() -> None:
    """Inspector updates delta_e, warning, and badge on out-of-gamut CIE pick."""
    rgbw = create_rgbw_definition().instantiate(1, "LED RGBW", 1, 1)
    inspector = DeviceInspectorWidget()
    inspector.set_selected_devices([rgbw])

    # Out of gamut pick on CIE 1931 xy
    res_out = inspector.apply_color_cie(0.10, 0.80)
    assert 1 in res_out
    assert inspector.last_worst_delta_e > 50.0
    assert "out of gamut" in inspector.last_color_warning
    badge_text = inspector.color_picker.match_label.get_text()
    assert "out of gamut" in badge_text
    tooltip = inspector.color_picker.match_label.get_tooltip_text()
    assert tooltip == inspector.last_color_warning

    # In gamut pick on CIE 1931 xy (D65 white)
    res_in = inspector.apply_color_cie(0.3127, 0.3290)
    assert 1 in res_in
    assert inspector.last_worst_delta_e < 1.0
    assert not inspector.last_color_warning
    badge_text_in = inspector.color_picker.match_label.get_text()
    assert "exact" in badge_text_in or "close" in badge_text_in


def test_color_picker_emits_cie_when_configured() -> None:
    """ConsoleColorPicker routes CIE pointer changes to on_cie_color when provided."""
    emitted_cie: list[tuple[float, float]] = []
    picker = ConsoleColorPicker(
        on_color=lambda r, g, b: None,
        on_cie_color=lambda x, y: emitted_cie.append((x, y)),
    )
    picker._on_cie_xy_change(0.12, 0.34)
    picker._on_cie_xy_release()
    assert emitted_cie == [(0.12, 0.34)]


def test_inspector_realtime_sync_with_osc_and_core_events() -> None:
    """Test real-time two-way sync between Core/OSC events and DeviceInspectorWidget."""
    from types import SimpleNamespace
    from typing import cast
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication

    core = CoreApplication(MagicMock())
    spot_def = create_moving_head_definition()
    rgb_def = create_rgbw_definition()
    core.lightshow.patch.patch_device(1, spot_def, 1, 1, label="Spot 1")
    core.lightshow.patch.patch_device(2, rgb_def, 1, 20, label="RGBW 2")
    core.selected_channels = [1, 2]

    fake_app = cast(Application, SimpleNamespace(core=core, window=None, tabs=None))
    inspector = DeviceInspectorWidget(app=fake_app)

    # 1. Simulate TouchOSC Pan/Tilt modification via Core action
    core.action_registry.execute("device.set_pan_tilt", 45.0, -30.0, channels=[1])
    assert "45.0°" in inspector.position_value_label.get_text()
    assert "-30.0°" in inspector.position_value_label.get_text()

    # 2. Simulate TouchOSC Color modification via Core action
    core.action_registry.execute("device.set_color", 1.0, 0.0, 0.0, channels=[2])
    assert "#FF0000" in inspector.color_value_label.get_text()

    # 3. Simulate TouchOSC Beam parameter (Zoom & Strobe) modification
    core.action_registry.execute(
        "device.set_parameter", "zoom", 30.0, channels=[1], is_physical=True
    )
    assert inspector.zoom_scale.get_value() == pytest.approx(30.0, abs=0.5)
    assert "30.0°" in inspector.zoom_value_label.get_text()

    core.action_registry.execute(
        "device.set_parameter", "strobe", 10.0, channels=[1], is_physical=True
    )
    assert inspector.strobe_scale.get_value() == pytest.approx(10.0, abs=0.5)
    assert "10.0 Hz" in inspector.strobe_value_label.get_text()

    # 4. Simulate TouchOSC Intensity level modification via Core event
    core.emit("channel.level_changed", 1, 128)
    assert inspector.intensity_scale.get_value() == pytest.approx(
        128 / 255.0 * 100.0, abs=1.0
    )

    # 5. Reverse direction: modifying parameters in Inspector emits Core events
    params_events: list[list[int]] = []
    color_events: list[tuple[list[int], tuple[float, float, float]]] = []
    core.subscribe(
        "device.parameters_changed", lambda chs: params_events.append(list(chs))
    )
    core.subscribe(
        "device.color_changed",
        lambda chs, col: color_events.append((list(chs), col)),
    )

    inspector.set_pad_position(-90.0, 20.0)
    assert [1] in params_events

    inspector.apply_color_srgb(0.0, 1.0, 0.0)
    assert len(color_events) == 1
    assert color_events[0][0] == [2]

    inspector.cleanup()
