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

import typing
from gettext import gettext as _
from typing import Any, Callable, Optional

from gi.repository import Gdk, Gtk

from olc.define import MAX_CHANNELS
from olc.devices.builtin import populate_builtin_library
from olc.devices.gdtf import GdtfImporter
from olc.gtk3.dialogs.patch_device import AddDeviceDialog, FixtureExchangeDialog
from olc.gtk3.widgets.curve import get_curve_display_name
from olc.gtk3.widgets.curve_popover import CurveSelectionPopover

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.backends import DMXBackend
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.devices.device import LightingDevice
    from olc.devices.fixture import FixtureDefinition, FixtureLibrary
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.patch import DMXPatch

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
    patch: DMXPatch
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    backend: DMXBackend
    commandline: CoreCommandLine
    fixture_library: FixtureLibrary
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
    import_gdtf_btn: Gtk.Button
    curve_column: Optional[Gtk.TreeViewColumn]
    curve_popover: CurveSelectionPopover
    _active_curve_device_id: Optional[int]
    tree_columns: dict[int, Gtk.TreeViewColumn]

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
        self.fixture_library = (
            getattr(self.lightshow, "fixture_library", None)
            or populate_builtin_library()
        )
        self.sort_mode = "logical"
        self.scope_mode = "patched"
        self.curve_column = None
        self._active_curve_device_id = None
        self.tree_columns = {}
        self.curve_popover = CurveSelectionPopover(
            self.lightshow, self._on_curve_selected
        )

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self._setup_toolbar()
        self._setup_views()
        self.populate_devices_store()

    def _setup_toolbar(self) -> None:
        """Create top action toolbar for device patch management."""
        self.toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.toolbar.set_margin_start(6)
        self.toolbar.set_margin_end(6)
        self.toolbar.set_margin_top(4)

        self.sort_toggle_btn = Gtk.ToggleButton(label="Sort by Channels")
        self.sort_toggle_btn.connect("toggled", self._on_sort_toggled)
        self.toolbar.pack_start(self.sort_toggle_btn, False, False, 0)

        self.scope_toggle_btn = Gtk.ToggleButton(label="Patched only")
        self.scope_toggle_btn.connect("toggled", self._on_scope_toggled)
        self.toolbar.pack_start(self.scope_toggle_btn, False, False, 0)

        self.add_device_btn = Gtk.Button(label="Add Device")
        self.add_device_btn.connect("clicked", self._on_add_device_clicked)
        self.toolbar.pack_start(self.add_device_btn, False, False, 0)

        self.remove_device_btn = Gtk.Button(label="Remove Device")
        self.remove_device_btn.connect("clicked", self._on_remove_device_clicked)
        self.toolbar.pack_start(self.remove_device_btn, False, False, 0)

        self.exchange_btn = Gtk.Button(label="Fixture Exchange")
        self.exchange_btn.connect("clicked", self._on_exchange_clicked)
        self.toolbar.pack_start(self.exchange_btn, False, False, 0)

        self.import_gdtf_btn = Gtk.Button(label="Import .gdtf")
        self.import_gdtf_btn.connect("clicked", self._on_import_gdtf_clicked)
        self.toolbar.pack_start(self.import_gdtf_btn, False, False, 0)

        # Global patch operations (packed on the right)
        self.unpatch_all_btn = Gtk.Button(label="Unpatch all")
        self.unpatch_all_btn.connect("clicked", self._on_unpatch_all_clicked)
        self.toolbar.pack_end(self.unpatch_all_btn, False, False, 0)

        self.patch_1on1_btn = Gtk.Button(label="Patch 1:1")
        self.patch_1on1_btn.connect("clicked", self._on_patch_1on1_clicked)
        self.toolbar.pack_end(self.patch_1on1_btn, False, False, 0)

        self.pack_start(self.toolbar, False, False, 2)

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
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        selection.connect("changed", self._on_selection_changed)

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
            if col_idx == COL_CURVE:
                self.curve_column = column
            self.tree_columns[col_idx] = column
            self.devices_treeview.append_column(column)

        self._reorder_columns_for_mode(self.sort_mode)

        self.devices_treeview.connect(
            "button-press-event", self._on_treeview_button_press
        )

        self.devices_scroll = Gtk.ScrolledWindow()
        self.devices_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        self.devices_scroll.add(self.devices_treeview)
        self.pack_start(self.devices_scroll, True, True, 0)

    # -------------------------------------------------------------------------
    # Device Table Data & Sorting
    # -------------------------------------------------------------------------

    def populate_devices_store(self) -> None:
        """Populate the devices ListStore according to sort_mode and scope_mode."""
        self.devices_store.clear()
        if self.scope_mode == "all":
            if self.sort_mode == "physical":
                self._populate_all_addresses()
            else:
                self._populate_all_channels()
        else:
            self._populate_patched_devices()

    def _populate_patched_devices(self) -> None:
        """Populate only patched devices, sorted according to sort_mode."""
        devices = list(self.patch.devices.values())
        if self.sort_mode == "physical":
            devices.sort(key=lambda d: (d.universe, d.address, d.device_id))
        else:
            devices.sort(key=lambda d: d.device_id)

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
                    str(dev.device_id),
                    dev.label or f"Device {dev.device_id}",
                    dev.fixture_name,
                    mode_str,
                    str(dev.universe),
                    dev.address_range_str,
                    str(dev.channel_count()),
                    curve_str,
                    "#dedede",
                    True,
                    dev.device_id,
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
                        str(dev.device_id),
                        dev.label or f"Device {dev.device_id}",
                        dev.fixture_name,
                        mode_str,
                        str(dev.universe),
                        dev.address_range_str,
                        str(dev.channel_count()),
                        curve_str,
                        "#dedede",
                        True,
                        dev.device_id,
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
                            f"{dev.label or f'Device {dev.device_id}'}{param_suffix}"
                        )
                        fixture_str = dev.fixture_name
                        mode_str = dev.mode_name if dev.mode_name else "-"
                        footprint_str = str(dev.channel_count())
                        raw_id = dev.device_id
                    else:
                        dim_curve_id = 0
                        if u in self.patch.outputs and addr in self.patch.outputs[u]:
                            dim_curve_id = self.patch.outputs[u][addr][1]
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
        treeview.get_selection().select_path(path)

        rect = treeview.get_cell_area(path, col)
        rect_x, rect_y = treeview.convert_bin_window_to_widget_coords(rect.x, rect.y)
        pointing_rect = Gdk.Rectangle()
        pointing_rect.x = rect_x
        pointing_rect.y = rect_y
        pointing_rect.width = rect.width
        pointing_rect.height = rect.height

        self.curve_popover.open_for_curve(
            dev.curve_id, relative_to=treeview, pointing_to=pointing_rect
        )
        return True

    def _on_treeview_button_press(
        self, treeview: Gtk.TreeView, event: Gdk.EventButton
    ) -> bool:
        """Handle button press on devices TreeView.

        Opens curve popover when clicking the curve column.

        Args:
            treeview: The Gtk.TreeView instance.
            event: The button press event.
        """
        if event.button != 1 or self.curve_column is None:
            return False

        path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
        if not path_info:
            return False

        path, col, _cell_x, _cell_y = path_info
        if path is not None and col is not None and col == self.curve_column:
            model = treeview.get_model()
            if model is not None:
                treeiter = model.get_iter(path)
                if not bool(model.get_value(treeiter, COL_IS_PATCHED)):
                    return False
            return self._open_curve_popover_at_cell(treeview, path, col)
        return False

    def _on_curve_selected(self, curve_id: int) -> None:
        """Handle curve selection from popover."""
        if self._active_curve_device_id is None:
            return
        self.app.core.action_registry.execute(
            "patch.set_device_curve", self._active_curve_device_id, curve_id
        )
        self.refresh()

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
        model, treeiter = selection.get_selected()
        if model is None or treeiter is None:
            self.remove_device_btn.set_sensitive(True)
            self.exchange_btn.set_sensitive(True)
            return
        is_patched = bool(model.get_value(treeiter, COL_IS_PATCHED))
        self.remove_device_btn.set_sensitive(is_patched)
        self.exchange_btn.set_sensitive(is_patched)

    def get_selected_device_id(self) -> Optional[int]:
        """Return currently selected device_id in the devices TreeView, or None."""
        selection = self.devices_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None and model is not None:
            if not bool(model.get_value(treeiter, COL_IS_PATCHED)):
                return None
            return int(model.get_value(treeiter, COL_RAW_ID))
        return None

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

        dev = self.patch.patch_device(
            device_id=device_id,
            fixture_def=fdef,
            universe=universe,
            address=address,
            mode_name=mode_name,
            label=label,
            force=force,
        )
        if curve_id > 0:
            dev.set_curve_id(curve_id)
        self.lightshow.set_modified()
        self.refresh()
        self.app.core.emit("patch.changed")
        return dev

    def remove_patched_device(self, device_id: int) -> bool:
        """Unpatch a device by ID and refresh the table."""
        removed = self.patch.unpatch_device(device_id)
        if removed is not None:
            self.lightshow.set_modified()
            self.refresh()
            self.app.core.emit("patch.changed")
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
        fdef = self.fixture_library.get_by_key(new_fixture_key)
        if fdef is None:
            raise KeyError(f"Fixture profile '{new_fixture_key}' not found in library")

        dev = self.patch.exchange_fixture(
            device_id=device_id,
            new_fixture_def=fdef,
            new_mode_name=new_mode_name,
            universe=universe,
            address=address,
            force=force,
        )
        self.lightshow.set_modified()
        self.refresh()
        self.app.core.emit("patch.changed")
        return dev

    def import_gdtf(self, file_path: str) -> FixtureDefinition:
        """Import a .gdtf file and register it in the local fixture library."""
        importer = GdtfImporter()
        fdef = importer.load(file_path)
        self.fixture_library.register(fdef)
        return fdef

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
        model, treeiter = selection.get_selected()
        if model is None or treeiter is None:
            return self._get_first_unpatched_channel_id(), None, None

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

    def _on_remove_device_clicked(self, _button: Gtk.Button) -> None:
        dev_id = self.get_selected_device_id()
        if dev_id is not None:
            self.remove_patched_device(dev_id)

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

    def _on_import_gdtf_clicked(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserDialog(
            title="Import GDTF Fixture File",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )
        file_filter = Gtk.FileFilter()
        file_filter.set_name("GDTF files (*.gdtf)")
        file_filter.add_pattern("*.gdtf")
        chooser.add_filter(file_filter)

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
            if filename:
                try:
                    self.import_gdtf(filename)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        chooser.destroy()

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
            self.app.core.emit("patch.changed")

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
            self.app.core.emit("patch.changed")

    def refresh(self) -> None:
        """Refresh display."""
        self.populate_devices_store()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked."""
        self.tabs.close("patch_channels")

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Key press events.

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        widget = self.window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.app.core.action_registry.execute("commandline.append_char", keyname)

        if keyname in (
            "KP_1",
            "KP_2",
            "KP_3",
            "KP_4",
            "KP_5",
            "KP_6",
            "KP_7",
            "KP_8",
            "KP_9",
            "KP_0",
        ):
            self.app.core.action_registry.execute(
                "commandline.append_char", keyname[3:]
            )

        if keyname == "period":
            self.app.core.action_registry.execute("commandline.append_char", ".")

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_backspace(self) -> None:
        self.app.core.action_registry.execute("commandline.clear")
