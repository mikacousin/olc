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
"""Unit tests for the modern device-centric Patch view and ChannelWidget indicators."""

# pylint: disable=redefined-outer-name, protected-access

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.device_inspector import DeviceInspectorWidget  # noqa: E402
from olc.gtk3.dialogs.patch_device import (  # noqa: E402
    AddDeviceDialog,
    FixtureExchangeDialog,
)
from olc.gtk3.patch_channels import (  # noqa: E402
    COL_ADDRESS,
    COL_FOOTPRINT,
    COL_ID,
    COL_NAME,
    COL_TYPE,
    COL_UNIVERSE,
    PatchChannelsTab,
)
from olc.patch import PatchCollisionError  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_patch_devices_table_and_double_sorting(app_gui: Application) -> None:
    """Test device table population and logical vs physical sorting."""
    app_gui.core.action_registry.execute("patch.clear")
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    # Add 3 devices in non-sequential physical addresses
    patch_tab.add_patched_device(
        device_id=10,
        fixture_key="Generic:Dimmer",
        universe=2,
        address=50,
        label="Back Dimmer",
    )
    patch_tab.add_patched_device(
        device_id=20,
        fixture_key="Generic:LED RGBW",
        universe=1,
        address=100,
        label="Wash Par",
    )
    patch_tab.add_patched_device(
        device_id=5,
        fixture_key="Generic:Moving Head Spot",
        universe=1,
        address=200,
        label="Front Spot",
    )
    process_events()

    # 1. Logical sort (by device_id ascending: 5, 10, 20)
    patch_tab.set_sort_mode("logical")
    n_rows = len(patch_tab.devices_store)
    rows_logical = [patch_tab.devices_store[i] for i in range(n_rows)]
    assert [r[COL_ID] for r in rows_logical] == [5, 10, 20]
    assert rows_logical[0][COL_NAME] == "Front Spot"
    assert rows_logical[0][COL_TYPE] == "MOVING_HEAD"
    assert rows_logical[0][COL_FOOTPRINT] == 8

    # 2. Physical sort (by (universe, address) ascending: U1:100, U1:200, U2:50)
    patch_tab.toggle_sort_mode()
    assert patch_tab.sort_mode == "physical"
    rows_physical = [patch_tab.devices_store[i] for i in range(n_rows)]
    assert [r[COL_ID] for r in rows_physical] == [20, 5, 10]
    assert [(r[COL_UNIVERSE], r[COL_ADDRESS]) for r in rows_physical] == [
        (1, 100),
        (1, 200),
        (2, 50),
    ]


def test_patch_device_collision_and_fixture_exchange(app_gui: Application) -> None:
    """Test collision detection, fixture exchange, and device removal."""
    app_gui.core.action_registry.execute("patch.clear")
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    # Patch RGBW (4 channels: U1:10-13)
    patch_tab.add_patched_device(
        device_id=1,
        fixture_key="Generic:LED RGBW",
        universe=1,
        address=10,
    )

    # Attempting to patch at U1:12 without force raises PatchCollisionError
    with pytest.raises(PatchCollisionError):
        patch_tab.add_patched_device(
            device_id=2,
            fixture_key="Generic:Dimmer",
            universe=1,
            address=12,
            force=False,
        )

    # Exchange Device #1 from LED RGBW to Moving Head Spot (8 channels: U1:10-17)
    exchanged = patch_tab.exchange_device_fixture(
        device_id=1,
        new_fixture_key="Generic:Moving Head Spot",
    )
    assert exchanged.channel_count() == 8
    assert patch_tab.devices_store[0][COL_TYPE] == "MOVING_HEAD"
    assert patch_tab.devices_store[0][COL_FOOTPRINT] == 8

    # Remove Device #1
    assert patch_tab.remove_patched_device(1) is True
    assert len(patch_tab.devices_store) == 0


def test_add_and_exchange_dialogs_preview(app_gui: Application) -> None:
    """Test AddDeviceDialog and FixtureExchangeDialog collision preview."""
    app_gui.core.action_registry.execute("patch.clear")
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    patch_tab.add_patched_device(
        device_id=1,
        fixture_key="Generic:LED RGBW",
        universe=1,
        address=1,
    )

    add_dlg = AddDeviceDialog(
        parent=app_gui.window,
        patch=patch_tab.patch,
        library=patch_tab.fixture_library,
        default_device_id=2,
    )
    add_dlg.universe_spin.set_value(1)
    add_dlg.address_spin.set_value(2)
    assert "Collision" in add_dlg.collision_label.get_text()

    add_dlg.address_spin.set_value(20)
    assert "free" in add_dlg.collision_label.get_text()
    vals = add_dlg.get_values()
    assert vals["device_id"] == 2
    assert vals["address"] == 20
    add_dlg.destroy()

    ex_dlg = FixtureExchangeDialog(
        parent=app_gui.window,
        patch=patch_tab.patch,
        library=patch_tab.fixture_library,
        device_id=1,
    )
    ex_vals = ex_dlg.get_values()
    assert ex_vals["device_id"] == 1
    ex_dlg.destroy()


def test_channel_widget_color_and_moving_head_indicators(app_gui: Application) -> None:
    """Test ChannelWidget color preview and moving head detection."""
    app_gui.core.action_registry.execute("patch.clear")
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    # Patch channel 1 as LED RGBW and channel 2 as Moving Head Spot
    dev_rgbw = patch_tab.add_patched_device(
        device_id=1,
        fixture_key="Generic:LED RGBW",
        universe=1,
        address=1,
    )
    dev_rgbw.set_color_srgb(1.0, 0.2, 0.4)

    patch_tab.add_patched_device(
        device_id=2,
        fixture_key="Generic:Moving Head Spot",
        universe=1,
        address=10,
    )

    assert app_gui.window is not None
    ch1_widget = app_gui.window.live_view.channels_view.get_channel_widget(1)
    ch2_widget = app_gui.window.live_view.channels_view.get_channel_widget(2)
    assert ch1_widget is not None
    assert ch2_widget is not None

    assert ch1_widget.has_color_capability() is True
    assert ch1_widget.is_moving_head() is False
    rgb = ch1_widget.get_preview_rgb()
    assert rgb is not None
    assert rgb[0] == pytest.approx(1.0, abs=0.05)

    assert ch2_widget.is_moving_head() is True
    assert ch2_widget.has_color_capability() is False


def test_patch_device_updates_live_view_and_open_tabs(app_gui: Application) -> None:
    """Test that patching a device in PatchChannelsTab updates LiveView & tabs."""
    app_gui.core.action_registry.execute("patch.clear")
    app_gui.activate_action("patch_channels", None)
    app_gui.activate_action("device_inspector", None)
    process_events()

    assert app_gui.window is not None
    assert app_gui.tabs is not None
    live_channels = app_gui.window.live_view.channels_view
    # Switch LiveChannelsView to "Patched" filter mode (index 1)
    live_channels.combo.set_active(1)
    process_events()

    ch5_child = live_channels.flowbox.get_child_at_index(4)
    assert ch5_child is not None
    assert ch5_child.get_visible() is False

    # Select channel 5 before it is patched
    app_gui.core.selected_channels = [5]
    process_events()

    inspector = app_gui.tabs.tabs.get("device_inspector")
    assert isinstance(inspector, DeviceInspectorWidget)
    assert len(inspector.selected_devices) == 0

    # Patch device 5 in PatchChannelsTab -> should update LiveView and DeviceInspector
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)
    patch_tab.add_patched_device(
        device_id=5,
        fixture_key="Generic:Moving Head Spot",
        universe=1,
        address=1,
        label="Spot 5",
    )
    process_events()

    assert ch5_child.get_visible() is True
    assert len(inspector.selected_devices) == 1
    assert inspector.selected_devices[0].device_id == 5

    # Removing device 5 updates LiveView and DeviceInspector again
    patch_tab.remove_patched_device(5)
    process_events()
    assert ch5_child.get_visible() is False
    assert len(inspector.selected_devices) == 0
