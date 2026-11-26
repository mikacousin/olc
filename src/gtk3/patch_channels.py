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
"""Device-centric DMX patch view for GTK3."""

from __future__ import annotations

import re
import typing
from gettext import gettext as _
from typing import Any, Optional

from gi.repository import Gdk, GLib, Gtk

from olc.define import MAX_CHANNELS
from olc.devices.builtin import create_dimmer_definition, populate_builtin_library
from olc.devices.device import FixtureType
from olc.gtk3.dialogs.patch_device import AddDeviceDialog, FixtureExchangeDialog
from olc.gtk3.widgets.curve import get_curve_display_name
from olc.gtk3.widgets.curve_popover import CurveSelectionPopover
from olc.gtk3.widgets.patch_popovers import (
    FixtureSelectionPopover,
    ModeSelectionPopover,
)
from olc.show.patch import PatchCollisionError

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.commandline import CoreCommandLine
    from olc.core.dmx_backend import DMXBackend
    from olc.devices.device import LightingDevice
    from olc.devices.fixture import FixtureLibrary
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow
    from olc.show.patch import PatchManager

# Column indices for the devices ListStore
COL_ID = 0
COL_NAME = 1
COL_TYPE = 2
COL_MODE = 3
COL_UNIVERSE = 4
COL_ADDRESS = 5
COL_FOOTPRINT = 6
COL_CURVE = 7
COL_COLOR = 8
COL_IS_PATCHED = 9
COL_RAW_ID = 10
COL_RAW_UNIV = 11
COL_RAW_ADDR = 12

# Visual column order depending on sort mode
_LOGICAL_COL_ORDER = [
    COL_ID,
    COL_NAME,
    COL_TYPE,
    COL_MODE,
    COL_UNIVERSE,
    COL_ADDRESS,
    COL_FOOTPRINT,
    COL_CURVE,
]
_PHYSICAL_COL_ORDER = [
    COL_UNIVERSE,
    COL_ADDRESS,
    COL_ID,
    COL_NAME,
    COL_TYPE,
    COL_MODE,
    COL_FOOTPRINT,
    COL_CURVE,
]


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class PatchChannelsTab(Gtk.Box):
    """Tab to patch lighting devices."""

    app: Application
    patch: PatchManager
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    backend: DMXBackend
    commandline: CoreCommandLine
    _fallback_fixture_library: FixtureLibrary
    sort_mode: str
    scope_mode: str
    devices_store: Gtk.ListStore
    devices_treeview: Gtk.TreeView
    devices_scroll: Gtk.ScrolledWindow
    toolbar: Gtk.Box
    sort_toggle_btn: Gtk.ToggleButton
    scope_toggle_btn: Gtk.ToggleButton
    add_device_btn: Gtk.Button
    remove_device_btn: Gtk.Button
    exchange_btn: Gtk.Button
    curve_column: Optional[Gtk.TreeViewColumn]
    mode_column: Optional[Gtk.TreeViewColumn]
    type_column: Optional[Gtk.TreeViewColumn]
    curve_popover: CurveSelectionPopover
    mode_popover: ModeSelectionPopover
    fixture_popover: FixtureSelectionPopover
    _active_curve_device_id: Optional[int]
    _active_popover_device_id: Optional[int]
    tree_columns: dict[int, Gtk.TreeViewColumn]
    cell_renderers: dict[int, Gtk.CellRendererText]

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(self, app: Application) -> None:
        self.app = app
        self.patch = app.core.lightshow.patch
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.backend = (
            app.core.backend
            if app.core.backend is not None
            else typing.cast(typing.Any, None)
        )
        self.commandline = app.core.commandline
        self._fallback_fixture_library = (
            getattr(self.lightshow, "fixture_library", None)
            or populate_builtin_library()
        )
        self.sort_mode = "logical"
        self.scope_mode = "patched"
        self.curve_column = None
        self.mode_column = None
        self.type_column = None
        self._active_curve_device_id = None
        self._active_popover_device_id = None
        self._needs_idle_refresh: bool = False
        self.tree_columns = {}
        self.cell_renderers = {}
        self.curve_popover = CurveSelectionPopover(
            self.lightshow, self._on_curve_selected
        )
        self.mode_popover = ModeSelectionPopover(self._on_mode_selected)
        self.fixture_popover = FixtureSelectionPopover(
            self.fixture_library,
            self._on_fixture_selected,
            self._on_fixture_advanced_selected,
        )

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self._setup_toolbar()
        self._setup_views()
        self.populate_devices_store()

    @property
    def fixture_library(self) -> FixtureLibrary:
        """Return the active lightshow FixtureLibrary dynamically."""
        return (
            getattr(self.lightshow, "fixture_library", None)
            or self._fallback_fixture_library
        )

    def _setup_toolbar(self) -> None:
        """Create top action toolbar for device patch management."""
        self.toolbar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.toolbar.set_margin_start(6)
        self.toolbar.set_margin_end(6)
        self.toolbar.set_margin_top(4)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.sort_toggle_btn = Gtk.ToggleButton(label="Sort by Channels")
        self.sort_toggle_btn.connect("toggled", self._on_sort_toggled)
        row1.pack_start(self.sort_toggle_btn, False, False, 0)

        self.scope_toggle_btn = Gtk.ToggleButton(label="Patched only")
        self.scope_toggle_btn.connect("toggled", self._on_scope_toggled)
        row1.pack_start(self.scope_toggle_btn, False, False, 0)

        self.add_device_btn = Gtk.Button(label="Add Device")
        self.add_device_btn.connect("clicked", self._on_add_device_clicked)
        row1.pack_start(self.add_device_btn, False, False, 0)

        self.remove_device_btn = Gtk.Button(label="Remove Device")
        self.remove_device_btn.connect("clicked", self._on_remove_device_clicked)
        row1.pack_start(self.remove_device_btn, False, False, 0)

        self.exchange_btn = Gtk.Button(label="Fixture Exchange")
        self.exchange_btn.connect("clicked", self._on_exchange_clicked)
        row1.pack_start(self.exchange_btn, False, False, 0)
        self.toolbar.pack_start(row1, False, False, 0)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.edit_3d_btn = Gtk.Button(label=_("3D / Focus…"))
        self.edit_3d_btn.set_tooltip_text(
            _("Edit 3D position, focus point, orientation, and beam angle")
        )
        self.edit_3d_btn.connect("clicked", self._on_edit_3d_clicked)
        row2.pack_start(self.edit_3d_btn, False, False, 0)

        self.stage_3d_btn = Gtk.Button(label=_("Stage / Fog…"))
        self.stage_3d_btn.set_tooltip_text(
            _("Configure 3D stage floor dimensions, grid, color, and fog")
        )
        self.stage_3d_btn.connect("clicked", self._on_stage_3d_clicked)
        row2.pack_start(self.stage_3d_btn, False, False, 0)

        # Global patch operations (packed on the right)
        self.unpatch_all_btn = Gtk.Button(label="Unpatch all")
        self.unpatch_all_btn.connect("clicked", self._on_unpatch_all_clicked)
        row2.pack_end(self.unpatch_all_btn, False, False, 0)

        self.patch_1on1_btn = Gtk.Button(label="Patch 1:1")
        self.patch_1on1_btn.connect("clicked", self._on_patch_1on1_clicked)
        row2.pack_end(self.patch_1on1_btn, False, False, 0)
        self.toolbar.pack_start(row2, False, False, 0)

        toolbar_scroll = Gtk.ScrolledWindow()
        toolbar_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        toolbar_scroll.set_propagate_natural_width(False)
        toolbar_scroll.set_propagate_natural_height(True)
        toolbar_scroll.add(self.toolbar)
        self.pack_start(toolbar_scroll, False, False, 2)

    def _setup_views(self) -> None:
        """Create the Devices TreeView and add it to the tab."""
        self.devices_store = Gtk.ListStore(
            str,  # COL_ID (Channel / Device ID string or "-")
            str,  # COL_NAME
            str,  # COL_TYPE
            str,  # COL_MODE
            str,  # COL_UNIVERSE
            str,  # COL_ADDRESS
            str,  # COL_FOOTPRINT
            str,  # COL_CURVE
            str,  # COL_COLOR ("#dedede" or "#777777")
            bool,  # COL_IS_PATCHED
            int,  # COL_RAW_ID
            int,  # COL_RAW_UNIV
            int,  # COL_RAW_ADDR
        )
        self.devices_treeview = Gtk.TreeView(model=self.devices_store)
        self.devices_treeview.set_enable_search(True)
        selection = self.devices_treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self._on_selection_changed)

        edit_callbacks = {
            COL_ID: self._on_channel_edited,
            COL_NAME: self._on_label_edited,
            COL_UNIVERSE: self._on_universe_edited,
            COL_ADDRESS: self._on_address_edited,
        }

        columns_spec = [
            ("Channel", COL_ID, 70),
            ("Label / Name", COL_NAME, 180),
            ("Fixture", COL_TYPE, 150),
            ("Mode", COL_MODE, 120),
            ("Universe", COL_UNIVERSE, 80),
            ("Address", COL_ADDRESS, 90),
            ("Footprint", COL_FOOTPRINT, 80),
            ("Curve", COL_CURVE, 100),
        ]
        for title, col_idx, min_width in columns_spec:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer)
            column.add_attribute(renderer, "text", col_idx)
            column.add_attribute(renderer, "foreground", COL_COLOR)
            column.set_min_width(min_width)
            column.set_resizable(True)
            if col_idx in edit_callbacks:
                column.set_cell_data_func(renderer, self._cell_data_func, col_idx)
                renderer.connect("edited", edit_callbacks[col_idx])
                renderer.connect(
                    "editing-started", self._on_cell_editing_started, col_idx
                )
            if col_idx == COL_CURVE:
                self.curve_column = column
            elif col_idx == COL_MODE:
                self.mode_column = column
            elif col_idx == COL_TYPE:
                self.type_column = column
            self.cell_renderers[col_idx] = renderer
            self.tree_columns[col_idx] = column
            self.devices_treeview.append_column(column)

        self._reorder_columns_for_mode(self.sort_mode)

        self.devices_treeview.connect(
            "button-press-event", self._on_treeview_button_press
        )
        self.devices_treeview.connect("key-press-event", self._on_treeview_key_press)

        self.devices_scroll = Gtk.ScrolledWindow()
        self.devices_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        self.devices_scroll.add(self.devices_treeview)
        self.pack_start(self.devices_scroll, True, True, 0)

    # -------------------------------------------------------------------------
    # Device Table Data & Sorting
    # -------------------------------------------------------------------------

    def select_row_index(self, index: int) -> None:
        """Set cursor to the specified row index and scroll into view."""
        if 0 <= index < len(self.devices_store):
            path = Gtk.TreePath.new_from_indices([index])
            self.devices_treeview.set_cursor(path)
            self.devices_treeview.scroll_to_cell(path, None, False, 0.0, 0.0)

    def grab_focus(self) -> None:
        """Delegate focus to the devices TreeView."""
        self.devices_treeview.grab_focus()

    def populate_devices_store(self, restore_index: Optional[int] = None) -> None:
        """Populate the devices ListStore according to sort_mode and scope_mode."""
        prev_idx = restore_index
        if prev_idx is None:
            curr_path, _ = self.devices_treeview.get_cursor()
            if curr_path is not None:
                prev_idx = curr_path.get_indices()[0]

        self.devices_treeview.set_model(None)
        try:
            self.devices_store.clear()
            if self.scope_mode == "all":
                if self.sort_mode == "physical":
                    self._populate_all_addresses()
                else:
                    self._populate_all_channels()
            else:
                self._populate_patched_devices()
        finally:
            self.devices_treeview.set_model(self.devices_store)

        if len(self.devices_store) > 0:
            target_idx = (
                prev_idx
                if (prev_idx is not None and prev_idx < len(self.devices_store))
                else 0
            )
            self.select_row_index(target_idx)

    def _populate_patched_devices(self) -> None:
        """Populate only patched devices, sorted according to sort_mode."""
        devices = list(self.patch.devices.values())
        if self.sort_mode == "physical":
            devices.sort(key=lambda d: (d.universe, d.address, d.fixture_id))
        else:
            devices.sort(key=lambda d: d.fixture_id)

        for dev in devices:
            curve = self.lightshow.curves.get_curve(dev.curve_id)
            curve_str = (
                get_curve_display_name(curve)
                if curve is not None
                else (_("Linear") if dev.curve_id == 0 else f"Curve #{dev.curve_id}")
            )
            mode_str = dev.mode_name if dev.mode_name else "-"
            self.devices_store.append(
                [
                    str(dev.fixture_id),
                    dev.label or f"Device {dev.fixture_id}",
                    dev.fixture_name,
                    mode_str,
                    str(dev.universe_display_str),
                    dev.address_range_str,
                    str(dev.channel_count()),
                    curve_str,
                    "#dedede",
                    True,
                    dev.fixture_id,
                    dev.universe,
                    dev.address,
                ]
            )

    def _populate_all_channels(self) -> None:
        """Populate channels 1..MAX_CHANNELS with patched devices or vacant slots."""
        for ch in range(1, MAX_CHANNELS + 1):
            dev = self.patch.get_device(ch)
            if dev is not None:
                curve = self.lightshow.curves.get_curve(dev.curve_id)
                curve_str = (
                    get_curve_display_name(curve)
                    if curve is not None
                    else (
                        _("Linear") if dev.curve_id == 0 else f"Curve #{dev.curve_id}"
                    )
                )
                mode_str = dev.mode_name if dev.mode_name else "-"
                self.devices_store.append(
                    [
                        str(dev.fixture_id),
                        dev.label or f"Device {dev.fixture_id}",
                        dev.fixture_name,
                        mode_str,
                        str(dev.universe_display_str),
                        dev.address_range_str,
                        str(dev.channel_count()),
                        curve_str,
                        "#dedede",
                        True,
                        dev.fixture_id,
                        dev.universe,
                        dev.address,
                    ]
                )
            else:
                self.devices_store.append(
                    [
                        str(ch),
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        "#777777",
                        False,
                        ch,
                        0,
                        0,
                    ]
                )

    def _populate_all_addresses(self) -> None:
        """Populate all 512 DMX addresses per active universe."""
        for u in self.patch.universes:
            for addr in range(1, 513):
                info = self.patch.get_address_parameter_info(u, addr)
                if info is not None:
                    dev = self.patch.get_device(info.device_id)
                    if dev is not None:
                        curve = self.lightshow.curves.get_curve(dev.curve_id)
                        curve_str = (
                            get_curve_display_name(curve)
                            if curve is not None
                            else (
                                _("Linear")
                                if dev.curve_id == 0
                                else f"Curve #{dev.curve_id}"
                            )
                        )
                        param_suffix = (
                            f" ({info.short_name})"
                            if not info.is_simple_dimmer and info.short_name
                            else ""
                        )
                        label_str = (
                            f"{dev.label or f'Device {dev.fixture_id}'}{param_suffix}"
                        )
                        fixture_str = dev.fixture_name
                        mode_str = dev.mode_name if dev.mode_name else "-"
                        footprint_str = str(dev.channel_count())
                        raw_id = dev.fixture_id
                    else:
                        output_info = self.patch.get_output_info(u, addr)
                        dim_curve_id = output_info[1] if output_info is not None else 0
                        curve = self.lightshow.curves.get_curve(dim_curve_id)
                        curve_str = (
                            get_curve_display_name(curve)
                            if curve is not None
                            else (
                                _("Linear")
                                if dim_curve_id == 0
                                else f"Curve #{dim_curve_id}"
                            )
                        )
                        label_str = f"Channel {info.device_id}"
                        fixture_str = "Dimmer" if info.is_simple_dimmer else "-"
                        mode_str = "-"
                        footprint_str = "1"
                        raw_id = info.device_id

                    self.devices_store.append(
                        [
                            str(raw_id),
                            label_str,
                            fixture_str,
                            mode_str,
                            str(u),
                            str(addr),
                            footprint_str,
                            curve_str,
                            "#dedede",
                            True,
                            raw_id,
                            u,
                            addr,
                        ]
                    )
                else:
                    self.devices_store.append(
                        [
                            "-",
                            "-",
                            "-",
                            "-",
                            str(u),
                            str(addr),
                            "-",
                            "-",
                            "#777777",
                            False,
                            0,
                            u,
                            addr,
                        ]
                    )

    def _get_cell_pointing_rect(
        self, treeview: Gtk.TreeView, path: Gtk.TreePath, col: Gtk.TreeViewColumn
    ) -> Gdk.Rectangle:
        rect = treeview.get_cell_area(path, col)
        rect_x, rect_y = treeview.convert_bin_window_to_widget_coords(rect.x, rect.y)
        pointing_rect = Gdk.Rectangle()
        pointing_rect.x = rect_x
        pointing_rect.y = rect_y
        pointing_rect.width = rect.width
        pointing_rect.height = rect.height
        return pointing_rect

    def _open_curve_popover_at_cell(
        self, treeview: Gtk.TreeView, path: Gtk.TreePath, col: Gtk.TreeViewColumn
    ) -> bool:
        """Open curve popover pointing to the specified cell."""
        model = treeview.get_model()
        if model is None:
            return False
        treeiter = model.get_iter(path)
        if not bool(model.get_value(treeiter, COL_IS_PATCHED)):
            return False
        device_id = int(model.get_value(treeiter, COL_RAW_ID))
        dev = self.patch.devices.get(device_id)
        if dev is None:
            return False

        self._active_curve_device_id = device_id
        selection = treeview.get_selection()
        if not selection.path_is_selected(path):
            selection.unselect_all()
            selection.select_path(path)

        pointing_rect = self._get_cell_pointing_rect(treeview, path, col)
        self.curve_popover.open_for_curve(
            dev.curve_id, relative_to=treeview, pointing_to=pointing_rect
        )
        return True

    def _open_mode_popover_at_cell(
        self, treeview: Gtk.TreeView, path: Gtk.TreePath, col: Gtk.TreeViewColumn
    ) -> bool:
        """Open mode selection popover pointing to the specified cell."""
        model = treeview.get_model()
        if model is None:
            return False
        treeiter = model.get_iter(path)
        if not bool(model.get_value(treeiter, COL_IS_PATCHED)):
            return False
        device_id = int(model.get_value(treeiter, COL_RAW_ID))
        dev = self.patch.devices.get(device_id)
        if dev is None:
            return False
        fdef = self.fixture_library.get(dev.manufacturer, dev.model)
        if fdef is None:
            return False

        self._active_popover_device_id = device_id
        selection = treeview.get_selection()
        selection.unselect_all()
        selection.select_path(path)

        pointing_rect = self._get_cell_pointing_rect(treeview, path, col)
        self.mode_popover.open_for_device(
            dev, fdef, relative_to=treeview, pointing_to=pointing_rect
        )
        return True

    def _open_fixture_popover_at_cell(
        self, treeview: Gtk.TreeView, path: Gtk.TreePath, col: Gtk.TreeViewColumn
    ) -> bool:
        """Open fixture selection popover pointing to the specified cell."""
        model = treeview.get_model()
        if model is None:
            return False
        treeiter = model.get_iter(path)
        if not bool(model.get_value(treeiter, COL_IS_PATCHED)):
            return False
        device_id = int(model.get_value(treeiter, COL_RAW_ID))
        dev = self.patch.devices.get(device_id)
        if dev is None:
            return False

        self._active_popover_device_id = device_id
        selection = treeview.get_selection()
        selection.unselect_all()
        selection.select_path(path)

        pointing_rect = self._get_cell_pointing_rect(treeview, path, col)
        self.fixture_popover.set_library(self.fixture_library)
        self.fixture_popover.open_for_device(
            dev, relative_to=treeview, pointing_to=pointing_rect
        )
        return True

    def _on_treeview_button_press(
        self, treeview: Gtk.TreeView, event: Gdk.EventButton
    ) -> bool:
        """Handle button press on devices TreeView.

        Opens popovers when clicking Curve, Mode, or Fixture columns on patched rows.
        """
        if event.button != 1:
            return False

        path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
        if not path_info:
            return False

        path, col, _cell_x, _cell_y = path_info
        if path is None or col is None:
            return False

        model = treeview.get_model()
        if model is not None:
            treeiter = model.get_iter(path)
            if not bool(model.get_value(treeiter, COL_IS_PATCHED)):
                return False

        if col == self.curve_column:
            return self._open_curve_popover_at_cell(treeview, path, col)
        if col == self.mode_column:
            return self._open_mode_popover_at_cell(treeview, path, col)
        if col == self.type_column:
            return self._open_fixture_popover_at_cell(treeview, path, col)
        return False

    def _on_curve_selected(self, curve_id: int) -> None:
        """Handle curve selection from popover (single or multi-selection)."""
        if self._active_curve_device_id is None:
            return
        selected_ids = self.get_selected_device_ids()
        targets = (
            selected_ids
            if len(selected_ids) > 1 and self._active_curve_device_id in selected_ids
            else [self._active_curve_device_id]
        )
        for dev_id in targets:
            self.app.core.action_registry.execute(
                "patch.set_device_curve", dev_id, curve_id
            )
        self.refresh()

    def _on_mode_selected(self, mode_name: str) -> None:
        """Handle mode selection from popover."""
        dev_id = self._active_popover_device_id
        if dev_id is None:
            return
        dev = self.patch.get_device(dev_id)
        if dev is None or dev.mode_name == mode_name:
            return
        fixture_key = f"{dev.manufacturer}:{dev.model}"
        self._apply_exchange_fixture(dev_id, fixture_key, mode_name)

    def _on_fixture_selected(self, fixture_key: str) -> None:
        """Handle fixture selection from popover."""
        dev_id = self._active_popover_device_id
        if dev_id is None:
            return
        self._apply_exchange_fixture(dev_id, fixture_key, None)

    def _on_fixture_advanced_selected(self) -> None:
        """Open FixtureExchangeDialog for the active popover device."""
        dev_id = self._active_popover_device_id
        if dev_id is None:
            return
        dialog = FixtureExchangeDialog(
            parent=self.window,
            patch=self.patch,
            library=self.fixture_library,
            device_id=dev_id,
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            vals = dialog.get_values()
            try:
                self.exchange_device_fixture(
                    device_id=vals["device_id"],
                    new_fixture_key=vals["fixture_key"],
                    new_mode_name=vals["mode_name"],
                    universe=vals["universe"],
                    address=vals["address"],
                    force=vals["force"],
                )
                warnings = getattr(self.patch, "last_exchange_warnings", [])
                if warnings:
                    self._show_clamping_warning_dialog(warnings)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        dialog.destroy()

    def _is_device_address_editable(self, device_id: int) -> bool:
        """Return True if the device's address can be edited inline."""
        dev = self.patch.get_device(device_id)
        if dev is None:
            return False
        if dev.fixture_type == FixtureType.DIMMER and len(dev.channels) > 1:
            univs = {ch.universe for ch in dev.channels}
            if len(univs) > 1:
                return False
            addrs = sorted(ch.address for ch in dev.channels)
            if addrs != list(range(addrs[0], addrs[0] + len(addrs))):
                return False
        return True

    def _is_cell_editable(
        self, model: Gtk.TreeModel, treeiter: Gtk.TreeIter, col_idx: int
    ) -> bool:
        """Determine if the specified cell is inline-editable."""
        is_patched = bool(model.get_value(treeiter, COL_IS_PATCHED))
        if col_idx == COL_NAME:
            return is_patched
        if col_idx == COL_UNIVERSE:
            if not is_patched:
                return False
            return self._is_device_address_editable(
                int(model.get_value(treeiter, COL_RAW_ID))
            )
        if col_idx == COL_ADDRESS:
            if is_patched:
                return self._is_device_address_editable(
                    int(model.get_value(treeiter, COL_RAW_ID))
                )
            return self.scope_mode == "all" and self.sort_mode == "logical"
        if col_idx == COL_ID:
            return (
                not is_patched
                and self.scope_mode == "all"
                and self.sort_mode == "physical"
            )
        return False

    def _cell_data_func(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        treeiter: Gtk.TreeIter,
        col_idx: int,
    ) -> None:
        """Set per-row editable property on CellRendererText."""
        cell.set_property("editable", self._is_cell_editable(model, treeiter, col_idx))

    def _editable_column_order(self) -> list[int]:
        """Return inline-editable column indices in current visual order."""
        order = (
            _PHYSICAL_COL_ORDER if self.sort_mode == "physical" else _LOGICAL_COL_ORDER
        )
        return [c for c in order if c in (COL_ID, COL_NAME, COL_UNIVERSE, COL_ADDRESS)]

    def _start_editing_cell(self, row_idx: int, col_idx: int) -> bool:
        """Start inline editing at *row_idx* and *col_idx*."""
        if not 0 <= row_idx < len(self.devices_store):
            return False
        col = self.tree_columns.get(col_idx)
        if col is None:
            return False
        path = Gtk.TreePath.new_from_indices([row_idx])
        self.devices_treeview.set_cursor(path, col, True)
        return False

    def _on_cell_editing_started(
        self,
        _renderer: Gtk.CellRendererText,
        editable: Gtk.CellEditable,
        path_str: str,
        col_idx: int,
    ) -> None:
        """Handle Tab / Shift+Tab navigation during inline cell editing."""
        if not isinstance(editable, Gtk.Widget):
            return
        editable.grab_focus()
        editable.connect(
            "key-press-event", self._on_cell_entry_key_press, path_str, col_idx
        )

    def _on_cell_entry_key_press(
        self,
        editable: Gtk.Widget,
        event: Gdk.EventKey,
        path_str: str,
        col_idx: int,
    ) -> bool:
        """Commit and move to next/previous editable column on Tab / Shift+Tab."""
        if event.keyval not in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            return False

        row_idx = int(path_str)
        treeiter = self.devices_store.get_iter(Gtk.TreePath.new_from_string(path_str))
        editable_cols = [
            c
            for c in self._editable_column_order()
            if self._is_cell_editable(self.devices_store, treeiter, c)
        ]
        if col_idx not in editable_cols:
            return False

        pos = editable_cols.index(col_idx)
        step = -1 if event.keyval == Gdk.KEY_ISO_Left_Tab else 1
        next_pos = (pos + step) % len(editable_cols)
        next_col = editable_cols[next_pos]

        if isinstance(editable, Gtk.Entry):
            editable.activate()
        GLib.idle_add(self._start_editing_cell, row_idx, next_col)
        return True

    def _on_treeview_key_press(
        self, _treeview: Gtk.TreeView, event: Gdk.EventKey
    ) -> bool:
        """Handle F2 (edit cell) and Delete (unpatch selected) in TreeView."""
        if event.keyval == Gdk.KEY_F2:
            path, focus_col = self.devices_treeview.get_cursor()
            if path is None:
                return False
            treeiter = self.devices_store.get_iter(path)
            col_idx = next(
                (idx for idx, c in self.tree_columns.items() if c == focus_col),
                COL_NAME,
            )
            if col_idx == COL_CURVE and self.curve_column is not None:
                return self._open_curve_popover_at_cell(
                    self.devices_treeview, path, self.curve_column
                )
            if col_idx == COL_MODE and self.mode_column is not None:
                return self._open_mode_popover_at_cell(
                    self.devices_treeview, path, self.mode_column
                )
            if col_idx == COL_TYPE and self.type_column is not None:
                return self._open_fixture_popover_at_cell(
                    self.devices_treeview, path, self.type_column
                )
            if not self._is_cell_editable(self.devices_store, treeiter, col_idx):
                if self._is_cell_editable(self.devices_store, treeiter, COL_NAME):
                    col_idx = COL_NAME
                elif self._is_cell_editable(self.devices_store, treeiter, COL_ADDRESS):
                    col_idx = COL_ADDRESS
                elif self._is_cell_editable(self.devices_store, treeiter, COL_ID):
                    col_idx = COL_ID
                else:
                    return False
            target_col = self.tree_columns.get(col_idx)
            if target_col is not None:
                self.devices_treeview.set_cursor(path, target_col, True)
                return True
            return False

        if event.keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
            ids = self.get_selected_device_ids()
            if ids:
                self._remove_device_ids(ids)
                return True
        return False

    def _confirm_collision(self, message: str) -> bool:
        """Prompt confirmation to overwrite colliding DMX addresses."""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=message,
        )
        dialog.set_title(_("Address Collision"))
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def _apply_move_address(self, device_id: int, universe: int, address: int) -> None:
        """Execute patch.move_device_address with collision confirmation."""
        try:
            self.app.core.action_registry.execute(
                "patch.move_device_address", device_id, universe, address, force=False
            )
            self.refresh()
        except PatchCollisionError as err:
            if self._confirm_collision(
                f"{err}\n\n{_('Overwrite colliding DMX address(es)?')}"
            ):
                self.app.core.action_registry.execute(
                    "patch.move_device_address",
                    device_id,
                    universe,
                    address,
                    force=True,
                )
                self.refresh()
        except ValueError:
            pass

    def _apply_exchange_fixture(
        self,
        device_id: int,
        fixture_key: str,
        mode_name: Optional[str],
    ) -> None:
        """Execute patch.exchange_fixture with collision confirmation and warnings."""
        try:
            self.exchange_device_fixture(
                device_id=device_id,
                new_fixture_key=fixture_key,
                new_mode_name=mode_name,
                force=False,
            )
        except PatchCollisionError as err:
            if not self._confirm_collision(
                f"{err}\n\n{_('Overwrite colliding DMX address(es)?')}"
            ):
                return
            self.exchange_device_fixture(
                device_id=device_id,
                new_fixture_key=fixture_key,
                new_mode_name=mode_name,
                force=True,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return

        warnings = getattr(self.patch, "last_exchange_warnings", [])
        if warnings:
            self._show_clamping_warning_dialog(warnings)

    def _patch_vacant_dimmer(self, device_id: int, universe: int, address: int) -> None:
        """Patch an 8-bit Dimmer on the fly from a vacant row."""
        if device_id < 1 or device_id > MAX_CHANNELS:
            return
        if address < 1 or address > 512:
            return
        if self.patch.universes and universe not in self.patch.universes:
            return
        dim_def = create_dimmer_definition(fine=False)
        try:
            self.app.core.action_registry.execute(
                "patch.device",
                device_id,
                dim_def,
                universe,
                address,
                force=False,
            )
            self.refresh()
        except PatchCollisionError as err:
            if self._confirm_collision(
                f"{err}\n\n{_('Overwrite colliding DMX address(es)?')}"
            ):
                self.app.core.action_registry.execute(
                    "patch.device",
                    device_id,
                    dim_def,
                    universe,
                    address,
                    force=True,
                )
                self.refresh()

    @staticmethod
    def _parse_universe_address(
        text: str, default_universe: int
    ) -> Optional[tuple[int, int]]:
        """Parse '101' or '2/101' or '2.101' into (universe, address)."""
        cleaned = text.strip()
        if not cleaned:
            return None
        match = re.match(r"^(\d+)\s*[/.]\s*(\d+)$", cleaned)
        if match:
            return int(match.group(1)), int(match.group(2))
        if cleaned.isdigit():
            return default_universe, int(cleaned)
        return None

    def _on_label_edited(
        self, _renderer: Gtk.CellRendererText, path_str: str, new_text: str
    ) -> None:
        """Handle inline label editing with incremental multi-selection naming."""
        treeiter = self.devices_store.get_iter(Gtk.TreePath.new_from_string(path_str))
        if not bool(self.devices_store.get_value(treeiter, COL_IS_PATCHED)):
            return
        device_id = int(self.devices_store.get_value(treeiter, COL_RAW_ID))
        cleaned = new_text.strip()
        if not cleaned:
            return

        selected_ids = self.get_selected_device_ids()
        if len(selected_ids) > 1 and device_id in selected_ids:
            num_match = re.match(r"^(.*?)(\d+)$", cleaned)
            for idx, dev_id in enumerate(selected_ids):
                if num_match:
                    prefix, digits = num_match.group(1), num_match.group(2)
                    label = f"{prefix}{int(digits) + idx:0{len(digits)}d}"
                else:
                    label = cleaned
                self.app.core.action_registry.execute(
                    "patch.set_device_label", dev_id, label
                )
        else:
            self.app.core.action_registry.execute(
                "patch.set_device_label", device_id, cleaned
            )
        self.refresh()

    def _on_universe_edited(
        self, _renderer: Gtk.CellRendererText, path_str: str, new_text: str
    ) -> None:
        """Handle inline universe editing."""
        treeiter = self.devices_store.get_iter(Gtk.TreePath.new_from_string(path_str))
        if not bool(self.devices_store.get_value(treeiter, COL_IS_PATCHED)):
            return
        cleaned = new_text.strip()
        if not cleaned.isdigit():
            return
        device_id = int(self.devices_store.get_value(treeiter, COL_RAW_ID))
        address = int(self.devices_store.get_value(treeiter, COL_RAW_ADDR))
        self._apply_move_address(device_id, int(cleaned), address)

    def _on_address_edited(
        self, _renderer: Gtk.CellRendererText, path_str: str, new_text: str
    ) -> None:
        """Handle inline address editing (or on-the-fly dimmer patch on vacant row)."""
        treeiter = self.devices_store.get_iter(Gtk.TreePath.new_from_string(path_str))
        is_patched = bool(self.devices_store.get_value(treeiter, COL_IS_PATCHED))
        raw_id = int(self.devices_store.get_value(treeiter, COL_RAW_ID))
        raw_univ = int(self.devices_store.get_value(treeiter, COL_RAW_UNIV))
        default_univ = (
            raw_univ
            if raw_univ > 0
            else (self.patch.universes[0] if self.patch.universes else 1)
        )

        parsed = self._parse_universe_address(new_text, default_univ)
        if parsed is None:
            return
        univ, addr = parsed
        if is_patched:
            self._apply_move_address(raw_id, univ, addr)
        elif raw_id > 0:
            self._patch_vacant_dimmer(raw_id, univ, addr)

    def _on_channel_edited(
        self, _renderer: Gtk.CellRendererText, path_str: str, new_text: str
    ) -> None:
        """Handle inline channel ID editing on vacant physical address rows."""
        treeiter = self.devices_store.get_iter(Gtk.TreePath.new_from_string(path_str))
        if bool(self.devices_store.get_value(treeiter, COL_IS_PATCHED)):
            return
        cleaned = new_text.strip()
        if not cleaned.isdigit():
            return
        device_id = int(cleaned)
        univ = int(self.devices_store.get_value(treeiter, COL_RAW_UNIV))
        addr = int(self.devices_store.get_value(treeiter, COL_RAW_ADDR))
        self._patch_vacant_dimmer(device_id, univ, addr)

    def _reorder_columns_for_mode(self, mode: str) -> None:
        """Reorder TreeView columns visually according to sort mode."""
        col_order = _PHYSICAL_COL_ORDER if mode == "physical" else _LOGICAL_COL_ORDER
        prev_col: Optional[Gtk.TreeViewColumn] = None
        for col_idx in col_order:
            col = self.tree_columns.get(col_idx)
            if col is not None:
                self.devices_treeview.move_column_after(col, prev_col)
                prev_col = col

    def set_sort_mode(self, mode: str) -> None:
        """Set device table sort mode ('logical' or 'physical')."""
        if mode not in ("logical", "physical"):
            raise ValueError(f"Unsupported sort mode: {mode}")
        self.sort_mode = mode
        is_phys = mode == "physical"
        if self.sort_toggle_btn.get_active() != is_phys:
            self.sort_toggle_btn.set_active(is_phys)
        self.sort_toggle_btn.set_label(
            "Sort by Addresses" if is_phys else "Sort by Channels"
        )
        self._reorder_columns_for_mode(mode)
        self.populate_devices_store()

    def toggle_sort_mode(self) -> str:
        """Toggle between logical and physical sort modes and return the new mode."""
        new_mode = "physical" if self.sort_mode == "logical" else "logical"
        self.set_sort_mode(new_mode)
        return new_mode

    def set_scope_mode(self, mode: str) -> None:
        """Set device table scope mode ('patched' or 'all')."""
        if mode not in ("patched", "all"):
            raise ValueError(f"Unsupported scope mode: {mode}")
        self.scope_mode = mode
        is_all = mode == "all"
        if self.scope_toggle_btn.get_active() != is_all:
            self.scope_toggle_btn.set_active(is_all)
        self.scope_toggle_btn.set_label("Show All" if is_all else "Patched only")
        self.populate_devices_store()

    def toggle_scope_mode(self) -> str:
        """Toggle between patched and all scope modes and return the new mode."""
        new_mode = "all" if self.scope_mode == "patched" else "patched"
        self.set_scope_mode(new_mode)
        return new_mode

    def _on_scope_toggled(self, button: Gtk.ToggleButton) -> None:
        mode = "all" if button.get_active() else "patched"
        if self.scope_mode != mode:
            self.set_scope_mode(mode)

    def _on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        """Update button sensitivity depending on whether selection is patched."""
        model, paths = selection.get_selected_rows()
        if model is None or not paths:
            self.remove_device_btn.set_sensitive(True)
            self.exchange_btn.set_sensitive(True)
            return
        patched_count = sum(
            1 for p in paths if bool(model.get_value(model.get_iter(p), COL_IS_PATCHED))
        )
        self.remove_device_btn.set_sensitive(patched_count > 0)
        self.exchange_btn.set_sensitive(patched_count == 1)

    def get_selected_device_ids(self) -> list[int]:
        """Return list of currently selected patched device IDs in the TreeView."""
        selection = self.devices_treeview.get_selection()
        model, paths = selection.get_selected_rows()
        if model is None or not paths:
            return []
        ids: list[int] = []
        for path in paths:
            treeiter = model.get_iter(path)
            if bool(model.get_value(treeiter, COL_IS_PATCHED)):
                ids.append(int(model.get_value(treeiter, COL_RAW_ID)))
        return ids

    def get_selected_device_id(self) -> Optional[int]:
        """Return currently selected device_id in the devices TreeView, or None."""
        ids = self.get_selected_device_ids()
        return ids[0] if ids else None

    # -------------------------------------------------------------------------
    # Device Patch Operations (Programmatic & Interactive)
    # -------------------------------------------------------------------------

    def add_patched_device(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_id: int,
        fixture_key: str,
        universe: int,
        address: int,
        mode_name: Optional[str] = None,
        label: str = "",
        curve_id: int = 0,
        force: bool = False,
    ) -> LightingDevice:
        """Patch a new LightingDevice from the fixture library and refresh display."""
        fdef = self.fixture_library.get_by_key(fixture_key)
        if fdef is None:
            raise KeyError(f"Fixture profile '{fixture_key}' not found in library")

        self.app.core.action_registry.execute(
            "patch.device",
            device_id,
            fdef,
            universe,
            address,
            mode_name,
            label,
            force=force,
        )
        if curve_id > 0:
            self.app.core.action_registry.execute(
                "patch.set_device_curve", device_id, curve_id
            )
        dev = self.patch.get_device(device_id)
        if dev is None:
            raise RuntimeError(f"Device {device_id} could not be patched")
        self.refresh()
        return dev

    def remove_patched_device(self, device_id: int) -> bool:
        """Unpatch a device by ID and refresh the table."""
        existed = self.patch.get_device(device_id) is not None
        if existed:
            self.app.core.action_registry.execute("patch.unpatch_device", device_id)
            self.refresh()
            return True
        self.refresh()
        return False

    def exchange_device_fixture(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_id: int,
        new_fixture_key: str,
        new_mode_name: Optional[str] = None,
        universe: Optional[int] = None,
        address: Optional[int] = None,
        force: bool = False,
    ) -> LightingDevice:
        """Replace the fixture definition for an existing device (Fixture Exchange)."""
        self.app.core.action_registry.execute(
            "patch.exchange_fixture",
            device_id,
            new_fixture_key,
            new_mode_name=new_mode_name,
            universe=universe,
            address=address,
            force=force,
        )
        dev = self.patch.get_device(device_id)
        if dev is None:
            raise RuntimeError(f"Device {device_id} not found after fixture exchange")
        self.refresh()
        return dev

    # -------------------------------------------------------------------------
    # Toolbar Callbacks
    # -------------------------------------------------------------------------

    def _on_sort_toggled(self, button: Gtk.ToggleButton) -> None:
        mode = "physical" if button.get_active() else "logical"
        if self.sort_mode != mode:
            self.set_sort_mode(mode)

    def _get_first_unpatched_channel_id(self) -> int:
        """Find the lowest available channel ID <= MAX_CHANNELS, or 1."""
        next_id = 1
        while next_id <= MAX_CHANNELS and self.patch.is_patched(next_id):
            next_id += 1
        return 1 if next_id > MAX_CHANNELS else next_id

    def _get_add_device_defaults(
        self,
    ) -> tuple[int, Optional[int], Optional[int]]:
        """Determine default device_id, universe and address from selection."""
        selection = self.devices_treeview.get_selection()
        model, paths = selection.get_selected_rows()
        if model is None or not paths:
            return self._get_first_unpatched_channel_id(), None, None
        treeiter = model.get_iter(paths[0])

        raw_id = int(model.get_value(treeiter, COL_RAW_ID))
        raw_univ = int(model.get_value(treeiter, COL_RAW_UNIV))
        raw_addr = int(model.get_value(treeiter, COL_RAW_ADDR))
        is_patched = bool(model.get_value(treeiter, COL_IS_PATCHED))

        default_univ = raw_univ if raw_univ > 0 else None
        default_addr = raw_addr if raw_addr > 0 else None

        if self.sort_mode == "physical":
            if is_patched and raw_id > 0:
                next_id = raw_id
            else:
                next_id = self._get_first_unpatched_channel_id()
        else:
            if not is_patched and raw_id > 0:
                next_id = raw_id
            else:
                next_id = self._get_first_unpatched_channel_id()

        return next_id, default_univ, default_addr

    def _on_add_device_clicked(self, _button: Gtk.Button) -> None:
        next_id, default_univ, default_addr = self._get_add_device_defaults()
        dialog = AddDeviceDialog(
            parent=self.window,
            patch=self.patch,
            library=self.fixture_library,
            default_device_id=next_id,
            default_universe=default_univ,
            default_address=default_addr,
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            vals = dialog.get_values()
            try:
                self.add_patched_device(
                    device_id=vals["device_id"],
                    fixture_key=vals["fixture_key"],
                    universe=vals["universe"],
                    address=vals["address"],
                    mode_name=vals["mode_name"],
                    label=vals["label"],
                    curve_id=vals["curve_id"],
                    force=vals["force"],
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        dialog.destroy()

    def _remove_device_ids(self, ids: list[int]) -> None:
        """Unpatch one or multiple selected devices."""
        if len(ids) == 1:
            self.remove_patched_device(ids[0])
        elif len(ids) > 1:
            self.app.core.action_registry.execute("patch.unpatch_batch", device_ids=ids)
            self.refresh()

    def _on_remove_device_clicked(self, _button: Gtk.Button) -> None:
        ids = self.get_selected_device_ids()
        if ids:
            self._remove_device_ids(ids)

    def _on_exchange_clicked(self, _button: Gtk.Button) -> None:
        dev_id = self.get_selected_device_id()
        if dev_id is None:
            return
        dialog = FixtureExchangeDialog(
            parent=self.window,
            patch=self.patch,
            library=self.fixture_library,
            device_id=dev_id,
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            vals = dialog.get_values()
            try:
                self.exchange_device_fixture(
                    device_id=vals["device_id"],
                    new_fixture_key=vals["fixture_key"],
                    new_mode_name=vals["mode_name"],
                    universe=vals["universe"],
                    address=vals["address"],
                    force=vals["force"],
                )
                warnings = getattr(self.patch, "last_exchange_warnings", [])
                if warnings:
                    self._show_clamping_warning_dialog(warnings)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        dialog.destroy()

    def _show_clamping_warning_dialog(self, warnings: list[Any]) -> None:
        """Display an informational dialog summarizing clamped cue parameters."""
        count = len(warnings)
        preview_lines = [w.format_message() for w in warnings[:6]]
        if count > 6:
            preview_lines.append(f"... et {count - 6} autre(s) paramètre(s)")
        body = "\n".join(preview_lines)

        msg_dialog = Gtk.MessageDialog(
            transient_for=self.window,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=f"Avertissement : {count} valeur(s) dépassent la course mécanique",
        )
        msg_dialog.format_secondary_text(body)
        msg_dialog.run()
        msg_dialog.destroy()

    def _on_patch_1on1_clicked(self, _button: Gtk.Button) -> None:
        """Prompt confirmation and execute 1:1 patch."""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Do you really want to reset and set patch to 1:1?\n"
            "All current devices and custom patch settings will be replaced.",
        )
        dialog.set_title("Patch 1:1 confirmation")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self.app.core.action_registry.execute("patch.set_1on1")
            self.refresh()

    def _on_unpatch_all_clicked(self, _button: Gtk.Button) -> None:
        """Prompt confirmation and clear all patch allocations."""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Do you really want to unpatch all devices and outputs?",
        )
        dialog.set_title("Unpatch all confirmation")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self.app.core.action_registry.execute("patch.clear")
            self.refresh()

    def refresh(self) -> None:
        """Refresh display."""
        self._needs_idle_refresh = False
        if self.fixture_popover._library is not self.fixture_library:
            self.fixture_popover.set_library(self.fixture_library)
        self.populate_devices_store()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked."""
        self.tabs.close("patch_channels")

    def _keypress_backspace(self) -> None:
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_down(self) -> None:
        """Navigate to the next row in the devices TreeView, or select first row."""
        sel = self.devices_treeview.get_selection()
        path, _col = self.devices_treeview.get_cursor()
        if path is None or sel.count_selected_rows() == 0:
            self.select_row_index(0)
        else:
            curr = path.get_indices()[0]
            if curr + 1 < len(self.devices_store):
                self.select_row_index(curr + 1)
        self.devices_treeview.grab_focus()

    def _keypress_up(self) -> None:
        """Navigate to the previous row in the devices TreeView, or select first row."""
        sel = self.devices_treeview.get_selection()
        path, _col = self.devices_treeview.get_cursor()
        if path is None or sel.count_selected_rows() == 0:
            self.select_row_index(0)
        else:
            curr = path.get_indices()[0]
            if curr - 1 >= 0:
                self.select_row_index(curr - 1)
        self.devices_treeview.grab_focus()

    def _keypress_page_down(self) -> None:
        """Jump forward by a page of rows (15 rows)."""
        sel = self.devices_treeview.get_selection()
        path, _col = self.devices_treeview.get_cursor()
        curr = (
            path.get_indices()[0]
            if (path is not None and sel.count_selected_rows() > 0)
            else -1
        )
        target = min(len(self.devices_store) - 1, curr + 15)
        self.select_row_index(max(0, target))
        self.devices_treeview.grab_focus()

    def _keypress_page_up(self) -> None:
        """Jump backward by a page of rows (15 rows)."""
        sel = self.devices_treeview.get_selection()
        path, _col = self.devices_treeview.get_cursor()
        curr = (
            path.get_indices()[0]
            if (path is not None and sel.count_selected_rows() > 0)
            else 0
        )
        target = max(0, curr - 15)
        self.select_row_index(target)
        self.devices_treeview.grab_focus()

    def _on_edit_3d_clicked(self, _button: Gtk.Button) -> None:
        """Open dialog to edit 3D position, focus point, orientation, and beam."""
        dev_id = self.get_selected_device_id()
        if dev_id is None:
            return
        dev = self.patch.devices.get(dev_id)
        if dev is None:
            return

        dialog = Gtk.Dialog(
            title=_("3D & Focus — #{id} {label}").format(id=dev_id, label=dev.label),
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, margin=12)

        def _make_spin(
            val: float, lo: float, hi: float, step: float, digits: int
        ) -> Gtk.SpinButton:
            sb = Gtk.SpinButton.new_with_range(lo, hi, step)
            sb.set_digits(digits)
            sb.set_value(val)
            return sb

        pos_spins = [_make_spin(dev.position[i], -50.0, 50.0, 0.1, 2) for i in range(3)]
        foc_spins = [
            _make_spin(dev.focus_point[i], -50.0, 50.0, 0.1, 2) for i in range(3)
        ]
        ori_spins = [
            _make_spin(dev.orientation[i], -360.0, 360.0, 1.0, 1) for i in range(3)
        ]
        beam_spin = _make_spin(dev.beam_angle, 1.0, 180.0, 1.0, 1)

        for col, axis in enumerate(("X (m)", "Y (m)", "Z (m)"), start=1):
            grid.attach(Gtk.Label(label=axis), col, 0, 1, 1)
        grid.attach(Gtk.Label(label=_("Position"), xalign=0.0), 0, 1, 1, 1)
        grid.attach(Gtk.Label(label=_("Focus"), xalign=0.0), 0, 2, 1, 1)
        grid.attach(Gtk.Label(label=_("Orientation (°)"), xalign=0.0), 0, 3, 1, 1)
        for col in range(3):
            grid.attach(pos_spins[col], col + 1, 1, 1, 1)
            grid.attach(foc_spins[col], col + 1, 2, 1, 1)
            grid.attach(ori_spins[col], col + 1, 3, 1, 1)
        grid.attach(Gtk.Label(label=_("Beam Angle (°)"), xalign=0.0), 0, 4, 1, 1)
        grid.attach(beam_spin, 1, 4, 1, 1)

        dialog.get_content_area().add(grid)
        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            self.app.core.action_registry.execute(
                "device.set_3d",
                dev_id,
                position=tuple(s.get_value() for s in pos_spins),
                focus_point=tuple(s.get_value() for s in foc_spins),
                orientation=tuple(s.get_value() for s in ori_spins),
                beam_angle=beam_spin.get_value(),
            )
        dialog.destroy()

    def _on_stage_3d_clicked(self, _button: Gtk.Button) -> None:
        """Open dialog to configure 3D stage floor and atmospheric fog."""
        stage = self.lightshow.stage
        dialog = Gtk.Dialog(
            title=_("Stage & Fog Settings"),
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, margin=12)

        width_spin = Gtk.SpinButton.new_with_range(1.0, 100.0, 0.5)
        width_spin.set_digits(1)
        width_spin.set_value(stage.width)

        depth_spin = Gtk.SpinButton.new_with_range(1.0, 100.0, 0.5)
        depth_spin.set_digits(1)
        depth_spin.set_value(stage.depth)

        grid_spin = Gtk.SpinButton.new_with_range(0.0, 10.0, 0.25)
        grid_spin.set_digits(2)
        grid_spin.set_value(stage.grid_spacing)

        rgba = Gdk.RGBA()
        if not rgba.parse(stage.color):
            rgba.parse("#222226")
        color_btn = Gtk.ColorButton.new_with_rgba(rgba)

        fog_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.01)
        fog_scale.set_value(stage.fog_density)
        fog_scale.set_hexpand(True)

        rows: list[tuple[str, Gtk.Widget]] = [
            (_("Width (m)"), width_spin),
            (_("Depth (m)"), depth_spin),
            (_("Grid Spacing (m)"), grid_spin),
            (_("Floor Color"), color_btn),
            (_("Fog Density"), fog_scale),
        ]
        for idx, (lbl, widget) in enumerate(rows):
            grid.attach(Gtk.Label(label=lbl, xalign=0.0), 0, idx, 1, 1)
            grid.attach(widget, 1, idx, 1, 1)

        dialog.get_content_area().add(grid)
        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            chosen = color_btn.get_rgba()
            hex_color = (
                f"#{round(chosen.red * 255):02x}"
                f"{round(chosen.green * 255):02x}"
                f"{round(chosen.blue * 255):02x}"
            )
            self.app.core.action_registry.execute(
                "stage.update",
                width=width_spin.get_value(),
                depth=depth_spin.get_value(),
                grid_spacing=grid_spin.get_value(),
                color=hex_color,
                fog_density=fog_scale.get_value(),
            )
        dialog.destroy()
