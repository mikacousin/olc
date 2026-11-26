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

import pathlib

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from olc.devices.builtin import populate_builtin_library  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.device_inspector import DeviceInspectorWidget  # noqa: E402
from olc.gtk3.dialogs.patch_device import (  # noqa: E402
    AddDeviceDialog,
    FixtureExchangeDialog,
)
from olc.gtk3.patch_channels import (  # noqa: E402
    COL_ADDRESS,
    COL_CURVE,
    COL_FOOTPRINT,
    COL_ID,
    COL_MODE,
    COL_NAME,
    COL_TYPE,
    COL_UNIVERSE,
    PatchChannelsTab,
)
from olc.show.patch import PatchCollisionError  # noqa: E402

from test.conftest import DATA_DIR  # noqa: E402 # isort: skip
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
    assert [r[COL_ID] for r in rows_logical] == ["5", "10", "20"]
    assert rows_logical[0][COL_NAME] == "Front Spot"
    assert rows_logical[0][COL_TYPE] == "Moving Head Spot"
    assert rows_logical[0][COL_MODE] == "Standard 8ch"
    assert rows_logical[0][COL_ADDRESS] == "200-207"
    assert rows_logical[0][COL_FOOTPRINT] == "8"
    logical_titles = [
        col.get_title() for col in patch_tab.devices_treeview.get_columns()
    ]
    assert logical_titles == [
        "Channel",
        "Label / Name",
        "Fixture",
        "Mode",
        "Universe",
        "Address",
        "Footprint",
        "Curve",
    ]

    # 2. Physical sort (by (universe, address) ascending: U1:100, U1:200, U2:50)
    patch_tab.toggle_sort_mode()
    assert patch_tab.sort_mode == "physical"
    rows_physical = [patch_tab.devices_store[i] for i in range(n_rows)]
    assert [r[COL_ID] for r in rows_physical] == ["20", "5", "10"]
    assert [(r[COL_UNIVERSE], r[COL_ADDRESS]) for r in rows_physical] == [
        ("1", "100-103"),
        ("1", "200-207"),
        ("2", "50"),
    ]
    physical_titles = [
        col.get_title() for col in patch_tab.devices_treeview.get_columns()
    ]
    assert physical_titles == [
        "Universe",
        "Address",
        "Channel",
        "Label / Name",
        "Fixture",
        "Mode",
        "Footprint",
        "Curve",
    ]

    # 3. Toggle back to logical
    patch_tab.toggle_sort_mode()
    assert patch_tab.sort_mode == "logical"
    assert [
        col.get_title() for col in patch_tab.devices_treeview.get_columns()
    ] == logical_titles


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
    assert patch_tab.devices_store[0][COL_TYPE] == "Moving Head Spot"
    assert patch_tab.devices_store[0][COL_MODE] == "Standard 8ch"
    assert patch_tab.devices_store[0][COL_ADDRESS] == "10-17"
    assert patch_tab.devices_store[0][COL_FOOTPRINT] == "8"

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
    assert inspector.selected_devices[0].fixture_id == 5

    # Removing device 5 updates LiveView and DeviceInspector again
    patch_tab.remove_patched_device(5)
    process_events()
    assert ch5_child.get_visible() is False
    assert len(inspector.selected_devices) == 0


def test_patch_channels_toolbar_global_operations(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Patch 1:1 and Unpatch all toolbar buttons with confirmation dialogs."""
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    # 1. Clear patch initially
    app_gui.core.action_registry.execute("patch.clear")
    process_events()
    assert len(patch_tab.devices_store) == 0

    # 2. Test Patch 1:1 CANCEL
    monkeypatch.setattr(Gtk.MessageDialog, "run", lambda _self: Gtk.ResponseType.CANCEL)
    patch_tab.patch_1on1_btn.clicked()
    process_events()
    assert len(patch_tab.devices_store) == 0

    # 3. Test Patch 1:1 OK
    monkeypatch.setattr(Gtk.MessageDialog, "run", lambda _self: Gtk.ResponseType.OK)
    patch_tab.patch_1on1_btn.clicked()
    process_events()
    assert len(patch_tab.devices_store) > 0

    # 4. Test Unpatch all CANCEL
    monkeypatch.setattr(Gtk.MessageDialog, "run", lambda _self: Gtk.ResponseType.CANCEL)
    patch_tab.unpatch_all_btn.clicked()
    process_events()
    assert len(patch_tab.devices_store) > 0

    # 5. Test Unpatch all OK
    monkeypatch.setattr(Gtk.MessageDialog, "run", lambda _self: Gtk.ResponseType.OK)
    patch_tab.unpatch_all_btn.clicked()
    process_events()
    assert len(patch_tab.devices_store) == 0


def test_patch_channels_curve_popover_interaction(
    app_gui: Application,
) -> None:
    """Test clicking curve column opens popover and selecting curve updates device."""
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    # Patch a dimmer
    app_gui.core.action_registry.execute("patch.clear")
    patch_tab.patch.patch_dimmer(channel=5, universe=1, address=10, curve=0)
    patch_tab.refresh()
    process_events()

    assert len(patch_tab.devices_store) == 1
    row_curve = patch_tab.devices_store[0][COL_CURVE]
    assert "Linear" in row_curve or "0" in row_curve

    # Trigger curve cell opening
    assert patch_tab.curve_column is not None
    opened = patch_tab._open_curve_popover_at_cell(
        patch_tab.devices_treeview,
        Gtk.TreePath.new_from_string("0"),
        patch_tab.curve_column,
    )
    assert opened is True
    assert patch_tab._active_curve_device_id == 5

    # Test popover navigation
    popover = patch_tab.curve_popover
    assert popover.stack.get_visible_child_name() == "0"

    # Simulate navigation next button
    next_btn = Gtk.Button.new_with_label(">")
    popover._on_nav_clicked(next_btn)
    new_child = popover.stack.get_visible_child_name()
    assert new_child != "0"

    # Select curve
    popover.select_curve(1)
    process_events()

    dev = patch_tab.patch.get_device(5)
    assert dev is not None
    assert dev.curve_id == 1
    assert patch_tab.patch.get_output_info(1, 10) == (5, 1)

    # Check that treeview refreshed
    updated_curve_name = patch_tab.devices_store[0][COL_CURVE]
    assert updated_curve_name != row_curve


@pytest.mark.gui
def test_patch_table_inline_editing_popovers_and_multiselect(
    app_gui: Application,
) -> None:
    """Test inline editing, popovers, vacant dimmer patch, and multiselect."""
    from olc.gtk3.patch_channels import (
        COL_ADDRESS,
        COL_ID,
        COL_NAME,
        COL_UNIVERSE,
        PatchChannelsTab,
    )

    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    app_gui.core.action_registry.execute("patch.clear")
    patch_tab.patch.add_universe(2)
    patch_tab.add_patched_device(
        device_id=1,
        fixture_key="Generic:LED RGBW",
        universe=1,
        address=10,
        label="Wash A",
    )
    patch_tab.add_patched_device(
        device_id=2,
        fixture_key="Generic:LED RGBW",
        universe=1,
        address=20,
        label="Wash B",
    )
    patch_tab.set_scope_mode("patched")
    patch_tab.set_sort_mode("logical")
    process_events()

    # 1. Inline label edit on single row
    patch_tab._on_label_edited(patch_tab.cell_renderers[COL_NAME], "0", "Front Wash")
    process_events()
    dev1 = patch_tab.patch.get_device(1)
    assert dev1 is not None and dev1.label == "Front Wash"

    # 2. Inline U/A address edit
    patch_tab._on_address_edited(patch_tab.cell_renderers[COL_ADDRESS], "0", "2/101")
    process_events()
    assert patch_tab.patch.get_address_occupant(2, 101) == 1
    assert patch_tab.patch.get_address_occupant(1, 10) is None

    # 3. Inline universe edit
    patch_tab._on_universe_edited(patch_tab.cell_renderers[COL_UNIVERSE], "0", "1")
    process_events()
    assert patch_tab.patch.get_address_occupant(1, 101) == 1

    # 4. Mode popover selection
    assert patch_tab.mode_column is not None
    opened_mode = patch_tab._open_mode_popover_at_cell(
        patch_tab.devices_treeview,
        Gtk.TreePath.new_from_string("0"),
        patch_tab.mode_column,
    )
    assert opened_mode is True
    assert patch_tab._active_popover_device_id == 1
    fdef1 = patch_tab.fixture_library.get(dev1.manufacturer, dev1.model)
    assert fdef1 is not None
    modes = fdef1.mode_names()
    if len(modes) > 1:
        other_mode = next(m for m in modes if m != dev1.mode_name)
        patch_tab._on_mode_selected(other_mode)
        process_events()
        dev1_after = patch_tab.patch.get_device(1)
        assert dev1_after is not None and dev1_after.mode_name == other_mode
    patch_tab.mode_popover.popdown()

    # 5. Fixture popover selection
    assert patch_tab.type_column is not None
    opened_fix = patch_tab._open_fixture_popover_at_cell(
        patch_tab.devices_treeview,
        Gtk.TreePath.new_from_string("1"),
        patch_tab.type_column,
    )
    assert opened_fix is True
    patch_tab._on_fixture_selected("Generic:Dimmer")
    process_events()
    dev2_after = patch_tab.patch.get_device(2)
    assert dev2_after is not None and dev2_after.fixture_name == "Dimmer"
    patch_tab.fixture_popover.popdown()

    # 6. Multi-selection incremental label edit
    sel = patch_tab.devices_treeview.get_selection()
    sel.select_all()
    process_events()
    assert patch_tab.get_selected_device_ids() == [1, 2]
    patch_tab._on_label_edited(patch_tab.cell_renderers[COL_NAME], "0", "Spot 10")
    process_events()
    d1 = patch_tab.patch.get_device(1)
    d2 = patch_tab.patch.get_device(2)
    assert d1 is not None and d1.label == "Spot 10"
    assert d2 is not None and d2.label == "Spot 11"

    # 7. Vacant row dimmer patch on the fly in Show All
    patch_tab.set_scope_mode("all")
    process_events()
    # Channel 3 is at index 2 (logical order)
    patch_tab._on_address_edited(patch_tab.cell_renderers[COL_ADDRESS], "2", "1/300")
    process_events()
    assert patch_tab.patch.get_address_occupant(1, 300) == 3

    # 8. Delete key unpatches selected devices
    patch_tab.set_scope_mode("patched")
    process_events()
    sel.unselect_all()
    sel.select_path(Gtk.TreePath.new_from_string("2"))  # device 3
    key_ev = Gdk.EventKey()
    key_ev.type = Gdk.EventType.KEY_PRESS
    key_ev.keyval = Gdk.KEY_Delete
    handled = patch_tab._on_treeview_key_press(patch_tab.devices_treeview, key_ev)
    assert handled is True
    assert patch_tab.patch.get_device(3) is None

    # 9. Channel edit on vacant physical row
    patch_tab.set_scope_mode("all")
    patch_tab.set_sort_mode("physical")
    process_events()
    # Find row for universe 1, address 305
    target_row = next(
        idx
        for idx in range(len(patch_tab.devices_store))
        if patch_tab.devices_store[idx][COL_UNIVERSE] == "1"
        and patch_tab.devices_store[idx][COL_ADDRESS] == "305"
    )
    patch_tab._on_channel_edited(patch_tab.cell_renderers[COL_ID], str(target_row), "4")
    process_events()
    assert patch_tab.patch.get_address_occupant(1, 305) == 4


@pytest.mark.gui
def test_fixture_popover_arrow_navigation_keeps_popover_open(
    app_gui: Application,
) -> None:
    """Test Down/Up arrows in FixtureSelectionPopover scroll list without closing it."""
    from olc.gtk3.patch_channels import PatchChannelsTab

    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    app_gui.core.action_registry.execute("patch.clear")
    patch_tab.add_patched_device(
        device_id=1,
        fixture_key="Generic:Dimmer",
        universe=1,
        address=1,
        label="Ch 1",
    )
    patch_tab.add_patched_device(
        device_id=2,
        fixture_key="Generic:Dimmer",
        universe=1,
        address=2,
        label="Ch 2",
    )
    patch_tab.set_scope_mode("patched")
    patch_tab.select_row_index(0)
    process_events()

    assert patch_tab.type_column is not None
    opened = patch_tab._open_fixture_popover_at_cell(
        patch_tab.devices_treeview,
        Gtk.TreePath.new_from_string("0"),
        patch_tab.type_column,
    )
    assert opened is True
    process_events()

    pop = patch_tab.fixture_popover
    assert pop.get_visible() is True
    first_row = pop._listbox.get_selected_row()
    assert first_row is not None and first_row.get_index() == 0

    down_ev = Gdk.EventKey()
    down_ev.type = Gdk.EventType.KEY_PRESS
    down_ev.keyval = Gdk.KEY_Down

    # Press Down multiple times from search entry: selection advances, device stays 1
    assert pop._on_search_key_press(pop._search_entry, down_ev) is True
    assert pop._on_search_key_press(pop._search_entry, down_ev) is True
    process_events()
    selected_after = pop._listbox.get_selected_row()
    assert selected_after is not None and selected_after.get_index() == 2
    assert pop.get_visible() is True
    assert patch_tab.get_selected_device_id() == 1

    # Also verify Window's key controller does not intercept Down when focus in Popover
    assert app_gui.window is not None
    selected_after.grab_focus()
    process_events()
    handled = app_gui.window._on_key_controller_pressed(
        app_gui.window.key_controller, Gdk.KEY_Down, 0, Gdk.ModifierType(0)
    )
    assert handled is False
    assert patch_tab.get_selected_device_id() == 1

    pop.popdown()


def test_patch_tab_refreshes_fixture_library_after_ascii_import(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Verify open PatchChannelsTab and its popover see imported Eos fixtures."""
    asc_path = DATA_DIR / "eos_show.asc"

    monkeypatch.setenv("OLC_USER_FIXTURES_DIR", str(tmp_path))

    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)
    old_lib = patch_tab.fixture_library

    try:
        imported = ImportFile(
            app_gui.core.lightshow,
            Gio.File.new_for_path(str(asc_path)),
            FileType.ASCII,
            tabs=app_gui.tabs,
        )
        imported.parse_sync(auto_import=True)
        process_events()

        assert patch_tab.fixture_library is app_gui.core.lightshow.fixture_library
        assert patch_tab.fixture_library is not old_lib
        assert patch_tab.fixture_library.get("Ayrton", "Ghibli_Extended") is not None
        assert (
            patch_tab.fixture_library.get("GLP", "Fusion_XPAR_12Z_M3_Adv") is not None
        )

        active_lib = app_gui.core.lightshow.fixture_library
        assert patch_tab.fixture_popover._library is active_lib
        patch_tab.fixture_popover._populate_list("Ghibli")
        process_events()
        assert "Ayrton:Ghibli_Extended" in patch_tab.fixture_popover._row_keys.values()
    finally:
        app_gui.core.lightshow.fixture_library = populate_builtin_library()
        app_gui.core.lightshow.patch.patch_empty()
        app_gui.core.lightshow.palettes.clear()
        app_gui.core.lightshow.groups.clear()
        app_gui.core.lightshow.sequences.clear()
        app_gui.core.lightshow.curves.reset()
        app_gui.core.lightshow.fader_bank.reset_faders()
        app_gui.core.emit("fixture_library.changed")
        app_gui.core.emit("patch.changed")
        process_events()


def test_patch_channels_tab_minimum_width_is_compact(app_gui: Application) -> None:
    """Verify PatchChannelsTab does not force sibling tabs to over-expand."""
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_tab, PatchChannelsTab)

    min_w, _nat_w = patch_tab.get_preferred_width()
    assert min_w <= 500
