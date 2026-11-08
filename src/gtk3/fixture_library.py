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
"""Fixture Library & Definition Editor tab for GTK3."""

from __future__ import annotations

import typing
from gettext import gettext as _
from typing import Optional

from gi.repository import GdkPixbuf, Gtk

from olc.devices.channel import ChannelRange, ChannelType, MergeMode
from olc.devices.color import EmitterProfile, FixtureColorProfile
from olc.devices.device import FixtureType
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
)

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application

# Columns in left TreeView (catalogue)
COL_CAT_MANUFACTURER = 0
COL_CAT_MODEL = 1
COL_CAT_TYPE = 2
COL_CAT_MODES = 3
COL_CAT_SOURCE = 4
COL_CAT_USED = 5
COL_CAT_IS_BUILTIN = 6

# Columns in Mode Channels TreeView
COL_CH_INDEX = 0
COL_CH_OFFSET = 1
COL_CH_FINE = 2
COL_CH_ULTRA = 3
COL_CH_LABEL = 4
COL_CH_TYPE = 5
COL_CH_HOME = 6
COL_CH_LOCATE = 7
COL_CH_MIN = 8
COL_CH_MAX = 9
COL_CH_UNIT = 10
COL_CH_MERGE = 11

# Columns in Channel Ranges TreeView
COL_RNG_LABEL = 0
COL_RNG_MIN = 1
COL_RNG_MAX = 2
COL_RNG_SNAP = 3

# Columns in Color Emitters TreeView
COL_EM_NAME = 0
COL_EM_ATTR = 1
COL_EM_X = 2
COL_EM_Y = 3
COL_EM_LUM = 4
COL_EM_NM = 5


class FixtureLibraryTab(Gtk.Box):
    """Tab to manage, inspect, and edit fixture definitions."""

    def __init__(self, app: Application) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.app = app
        self.core = app.core
        self.lightshow = app.core.lightshow
        self.patch = self.lightshow.patch

        self.active_definition: Optional[FixtureDefinition] = None
        self.original_definition_key: Optional[tuple[str, str]] = None
        self._updating_ui: bool = False
        self._pending_select_key: Optional[tuple[str, str]] = None

        self._build_ui()
        self._subscribe_events()
        self.refresh_catalog()

    @property
    def fixture_library(self) -> FixtureLibrary:
        return getattr(self.lightshow, "fixture_library", None) or FixtureLibrary()

    def _subscribe_events(self) -> None:
        self.core.subscribe("fixture_library.changed", self._on_library_changed)
        self.core.subscribe("patch.changed", self._on_patch_changed)

    def cleanup(self) -> None:
        """Unsubscribe from Core events when the tab is closed."""
        self.core.unsubscribe("fixture_library.changed", self._on_library_changed)
        self.core.unsubscribe("patch.changed", self._on_patch_changed)

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Handler for tab close button."""
        if self.app.tabs:
            self.app.tabs.close("fixtures")

    def _on_library_changed(self, *_args: object) -> None:
        self.refresh_catalog()

    def _on_patch_changed(self, *_args: object) -> None:
        self.refresh_catalog()

    # -------------------------------------------------------------------------
    # UI Layout Construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(220)

        left_box = self._build_catalog_pane()
        right_box = self._build_editor_pane()

        paned.pack1(left_box, False, False)
        paned.pack2(right_box, True, False)
        self.pack_start(paned, True, True, 0)
        self.show_all()

    def _build_catalog_pane(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        # Search bar
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search fixtures..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        box.pack_start(self.search_entry, False, False, 2)

        # Catalog ListStore & TreeView
        self.cat_store = Gtk.ListStore(
            str,  # Manufacturer
            str,  # Model
            str,  # Type
            str,  # Modes
            str,  # Source ("Built-in" / "User")
            int,  # Used count
            bool,  # Is built-in
        )
        self.cat_filter = self.cat_store.filter_new()
        self.cat_filter.set_visible_func(self._filter_catalog)

        self.cat_tree = Gtk.TreeView(model=self.cat_filter)
        self.cat_tree.set_headers_visible(True)
        sel = self.cat_tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)
        sel.connect("changed", self._on_catalog_selection_changed)

        cols = [
            ("Mfg", COL_CAT_MANUFACTURER, 75),
            ("Model", COL_CAT_MODEL, 90),
            ("Type", COL_CAT_TYPE, 65),
            ("Used", COL_CAT_USED, 35),
        ]
        for title, col_idx, width in cols:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer)
            column.add_attribute(renderer, "text", col_idx)
            column.set_resizable(True)
            column.set_min_width(width)
            self.cat_tree.append_column(column)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.cat_tree)
        box.pack_start(scroll, True, True, 2)

        # Catalog Action Toolbar (compact buttons)
        tbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.btn_import_gdtf = Gtk.Button(label=_("GDTF"))
        self.btn_import_gdtf.set_tooltip_text(_("Import GDTF File"))
        self.btn_import_gdtf.connect("clicked", self._on_import_gdtf_clicked)
        tbar.pack_start(self.btn_import_gdtf, False, False, 0)

        self.btn_new = Gtk.Button(label=_("New"))
        self.btn_new.set_tooltip_text(_("Create New Custom Fixture"))
        self.btn_new.connect("clicked", self._on_new_clicked)
        tbar.pack_start(self.btn_new, False, False, 0)

        self.btn_duplicate = Gtk.Button(label=_("Duplicate"))
        self.btn_duplicate.set_tooltip_text(_("Duplicate Selected Profile to Edit"))
        self.btn_duplicate.connect("clicked", self._on_duplicate_clicked)
        tbar.pack_start(self.btn_duplicate, False, False, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.set_tooltip_text(_("Delete Selected User Profile"))
        self.btn_delete.connect("clicked", self._on_delete_clicked)
        tbar.pack_end(self.btn_delete, False, False, 0)

        box.pack_start(tbar, False, False, 2)
        return box

    def _build_editor_pane(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        # Top Header Box (Compact Grid)
        header_grid = Gtk.Grid(column_spacing=6, row_spacing=4)
        box.pack_start(header_grid, False, False, 0)

        # Thumbnail
        self.thumbnail_image = Gtk.Image.new_from_icon_name(
            "applications-multimedia", Gtk.IconSize.DND
        )
        self.thumbnail_image.set_size_request(38, 38)
        header_grid.attach(self.thumbnail_image, 0, 0, 1, 2)

        # Manufacturer Entry
        header_grid.attach(Gtk.Label(label=_("Mfg:"), xalign=0), 1, 0, 1, 1)
        self.entry_mfg = Gtk.Entry()
        self.entry_mfg.set_width_chars(12)
        header_grid.attach(self.entry_mfg, 2, 0, 1, 1)

        # Model Entry
        header_grid.attach(Gtk.Label(label=_("Model:"), xalign=0), 3, 0, 1, 1)
        self.entry_model = Gtk.Entry()
        self.entry_model.set_width_chars(14)
        header_grid.attach(self.entry_model, 4, 0, 1, 1)

        # Type Combo
        header_grid.attach(Gtk.Label(label=_("Type:"), xalign=0), 1, 1, 1, 1)
        self.combo_type = Gtk.ComboBoxText()
        for ft in FixtureType:
            self.combo_type.append(ft.value, ft.value.replace("_", " ").title())
        header_grid.attach(self.combo_type, 2, 1, 1, 1)

        # Notes Entry
        header_grid.attach(Gtk.Label(label=_("Notes:"), xalign=0), 3, 1, 1, 1)
        self.entry_notes = Gtk.Entry()
        self.entry_notes.set_hexpand(True)
        header_grid.attach(self.entry_notes, 4, 1, 1, 1)

        # Status Banner & Actions
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lbl_status = Gtk.Label(label="", xalign=0)
        action_bar.pack_start(self.lbl_status, True, True, 0)

        self.btn_apply = Gtk.Button(label=_("Apply to Show"))
        self.btn_apply.get_style_context().add_class("suggested-action")
        self.btn_apply.connect("clicked", self._on_apply_clicked)
        action_bar.pack_end(self.btn_apply, False, False, 0)

        box.pack_start(action_bar, False, False, 2)

        # Stack Notebook for Sub-views
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        box.pack_start(stack_switcher, False, False, 2)

        # Sub-views
        page_modes = self._build_modes_page()
        page_ranges = self._build_ranges_page()
        page_color = self._build_color_page()

        self.stack.add_titled(page_modes, "modes", _("Modes & Channels"))
        self.stack.add_titled(page_ranges, "ranges", _("Channel Ranges"))
        self.stack.add_titled(page_color, "color", _("Color Profile"))

        box.pack_start(self.stack, True, True, 2)
        return box

    # -------------------------------------------------------------------------
    # Sub-View 1: Modes & Channels (Paned: Channels List | Channel Inspector)
    # -------------------------------------------------------------------------

    def _build_modes_page(self) -> Gtk.Box:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Mode Selection & Management Toolbar
        mode_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        mode_bar.pack_start(Gtk.Label(label=_("Mode:"), xalign=0), False, False, 0)

        self.combo_modes = Gtk.ComboBoxText()
        self.combo_modes.connect("changed", self._on_mode_combo_changed)
        mode_bar.pack_start(self.combo_modes, False, False, 0)

        self.lbl_mode_footprint = Gtk.Label(label="", xalign=0)
        mode_bar.pack_start(self.lbl_mode_footprint, False, False, 4)

        self.btn_add_mode = Gtk.Button(label=_("+ Mode"))
        self.btn_add_mode.set_tooltip_text(_("Add New DMX Mode"))
        self.btn_add_mode.connect("clicked", self._on_add_mode_clicked)
        mode_bar.pack_start(self.btn_add_mode, False, False, 0)

        self.btn_dup_mode = Gtk.Button(label=_("Duplicate"))
        self.btn_dup_mode.set_tooltip_text(_("Duplicate Active Mode"))
        self.btn_dup_mode.connect("clicked", self._on_duplicate_mode_clicked)
        mode_bar.pack_start(self.btn_dup_mode, False, False, 0)

        self.btn_del_mode = Gtk.Button(label=_("Delete"))
        self.btn_del_mode.set_tooltip_text(_("Delete Active Mode"))
        self.btn_del_mode.connect("clicked", self._on_delete_mode_clicked)
        mode_bar.pack_start(self.btn_del_mode, False, False, 0)

        mode_bar.pack_start(Gtk.Label(label=_("Name:"), xalign=0), False, False, 2)
        self.entry_mode_name = Gtk.Entry()
        self.entry_mode_name.set_width_chars(10)
        mode_bar.pack_start(self.entry_mode_name, False, False, 0)

        self.entry_mode_desc = Gtk.Entry()
        self.entry_mode_desc.set_placeholder_text(_("Mode description"))
        self.entry_mode_desc.set_hexpand(True)
        mode_bar.pack_start(self.entry_mode_desc, True, True, 0)

        page_box.pack_start(mode_bar, False, False, 2)

        # Paned: Channels Table (Left) | Channel Inspector (Right)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(360)

        # Left: Channels Table
        left_ch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self.channels_store = Gtk.ListStore(
            int,  # COL_CH_INDEX (index in channel_defs)
            str,  # COL_CH_OFFSET (1-based relative DMX offset)
            str,  # COL_CH_FINE
            str,  # COL_CH_ULTRA
            str,  # COL_CH_LABEL
            str,  # COL_CH_TYPE
            str,  # COL_CH_HOME
            str,  # COL_CH_LOCATE
            str,  # COL_CH_MIN
            str,  # COL_CH_MAX
            str,  # COL_CH_UNIT
            str,  # COL_CH_MERGE
        )
        self.channels_tree = Gtk.TreeView(model=self.channels_store)
        self.channels_tree.set_headers_visible(True)
        sel = self.channels_tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)
        sel.connect("changed", self._on_channel_selection_changed)

        ch_cols = [
            ("#", COL_CH_OFFSET, 35),
            ("Label", COL_CH_LABEL, 95),
            ("Type", COL_CH_TYPE, 75),
            ("Home", COL_CH_HOME, 50),
            ("Locate", COL_CH_LOCATE, 50),
            ("Min", COL_CH_MIN, 45),
            ("Max", COL_CH_MAX, 45),
        ]
        for title, col_idx, min_w in ch_cols:
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer)
            col.add_attribute(renderer, "text", col_idx)
            col.set_resizable(True)
            col.set_min_width(min_w)
            self.channels_tree.append_column(col)

        scroll_tree = Gtk.ScrolledWindow()
        scroll_tree.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll_tree.add(self.channels_tree)
        left_ch_box.pack_start(scroll_tree, True, True, 0)

        ch_actions_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_add_ch = Gtk.Button(label=_("+ Add Channel"))
        self.btn_add_ch.connect("clicked", self._on_add_channel_clicked)
        ch_actions_bar.pack_start(self.btn_add_ch, False, False, 0)

        self.btn_del_ch = Gtk.Button(label=_("- Remove Channel"))
        self.btn_del_ch.connect("clicked", self._on_delete_channel_clicked)
        ch_actions_bar.pack_start(self.btn_del_ch, False, False, 0)

        left_ch_box.pack_start(ch_actions_bar, False, False, 2)
        paned.pack1(left_ch_box, True, False)

        # Right: Channel Inspector Form
        inspector_scroll = Gtk.ScrolledWindow()
        inspector_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        inspector_scroll.set_min_content_width(230)

        insp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        insp_box.set_margin_start(8)
        insp_box.set_margin_end(8)
        insp_box.set_margin_top(4)
        insp_box.set_margin_bottom(4)

        lbl_insp_title = Gtk.Label(xalign=0)
        lbl_insp_title.set_markup("<b>" + _("Channel Properties") + "</b>")
        insp_box.pack_start(lbl_insp_title, False, False, 2)

        grid = Gtk.Grid(column_spacing=6, row_spacing=4)

        # Label
        grid.attach(Gtk.Label(label=_("Label:"), xalign=0), 0, 0, 1, 1)
        self.entry_ch_label = Gtk.Entry()
        self.entry_ch_label.set_hexpand(True)
        grid.attach(self.entry_ch_label, 1, 0, 1, 1)

        # Type
        grid.attach(Gtk.Label(label=_("Type:"), xalign=0), 0, 1, 1, 1)
        self.combo_ch_type = Gtk.ComboBoxText()
        for ct in ChannelType:
            self.combo_ch_type.append(ct.value, ct.value.replace("_", " ").title())
        self.combo_ch_type.set_hexpand(True)
        grid.attach(self.combo_ch_type, 1, 1, 1, 1)

        # Offset & Fine
        grid.attach(Gtk.Label(label=_("Offset:"), xalign=0), 0, 2, 1, 1)
        self.spin_ch_offset = Gtk.SpinButton.new_with_range(1, 512, 1)
        grid.attach(self.spin_ch_offset, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Fine (16b):"), xalign=0), 0, 3, 1, 1)
        self.spin_ch_fine = Gtk.SpinButton.new_with_range(0, 512, 1)
        self.spin_ch_fine.set_tooltip_text(_("0 = None (8-bit single channel)"))
        grid.attach(self.spin_ch_fine, 1, 3, 1, 1)

        # Merge Rule
        grid.attach(Gtk.Label(label=_("Merge:"), xalign=0), 0, 4, 1, 1)
        self.combo_ch_merge = Gtk.ComboBoxText()
        self.combo_ch_merge.append("htp", "HTP")
        self.combo_ch_merge.append("ltp", "LTP")
        grid.attach(self.combo_ch_merge, 1, 4, 1, 1)

        # Home & Locate
        grid.attach(Gtk.Label(label=_("Home:"), xalign=0), 0, 5, 1, 1)
        self.spin_ch_home = Gtk.SpinButton.new_with_range(0, 16777215, 1)
        grid.attach(self.spin_ch_home, 1, 5, 1, 1)

        grid.attach(Gtk.Label(label=_("Locate:"), xalign=0), 0, 6, 1, 1)
        self.spin_ch_locate = Gtk.SpinButton.new_with_range(-1, 16777215, 1)
        self.spin_ch_locate.set_tooltip_text(_("-1 = Same as Home"))
        grid.attach(self.spin_ch_locate, 1, 6, 1, 1)

        # Physical Min, Max & Unit
        grid.attach(Gtk.Label(label=_("Phys Min:"), xalign=0), 0, 7, 1, 1)
        self.spin_ch_min = Gtk.SpinButton.new_with_range(-10000.0, 10000.0, 0.5)
        self.spin_ch_min.set_digits(1)
        grid.attach(self.spin_ch_min, 1, 7, 1, 1)

        grid.attach(Gtk.Label(label=_("Phys Max:"), xalign=0), 0, 8, 1, 1)
        self.spin_ch_max = Gtk.SpinButton.new_with_range(-10000.0, 10000.0, 0.5)
        self.spin_ch_max.set_digits(1)
        grid.attach(self.spin_ch_max, 1, 8, 1, 1)

        grid.attach(Gtk.Label(label=_("Unit:"), xalign=0), 0, 9, 1, 1)
        self.entry_ch_unit = Gtk.Entry()
        self.entry_ch_unit.set_placeholder_text(_("deg, %, lux..."))
        grid.attach(self.entry_ch_unit, 1, 9, 1, 1)

        insp_box.pack_start(grid, False, False, 4)

        self.btn_update_ch = Gtk.Button(label=_("Update Channel"))
        self.btn_update_ch.connect("clicked", self._on_update_channel_clicked)
        insp_box.pack_start(self.btn_update_ch, False, False, 4)

        inspector_scroll.add(insp_box)
        paned.pack2(inspector_scroll, False, False)

        page_box.pack_start(paned, True, True, 2)
        return page_box

    # -------------------------------------------------------------------------
    # Sub-View 2: Channel Ranges (Paned: Slots Table | Slot Inspector)
    # -------------------------------------------------------------------------

    def _build_ranges_page(self) -> Gtk.Box:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lbl_range_context = Gtk.Label(
            label=_("Select a channel in Modes & Channels to view/edit its ranges"),
            xalign=0,
        )
        page_box.pack_start(self.lbl_range_context, False, False, 2)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(360)

        # Left: Ranges Table
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.ranges_store = Gtk.ListStore(
            str,  # COL_RNG_LABEL
            int,  # COL_RNG_MIN
            int,  # COL_RNG_MAX
            int,  # COL_RNG_SNAP
        )
        self.ranges_tree = Gtk.TreeView(model=self.ranges_store)
        sel = self.ranges_tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)
        sel.connect("changed", self._on_range_selection_changed)

        range_cols = [
            ("Label / Slot", 120),
            ("Min", 50),
            ("Max", 50),
            ("Snap", 50),
        ]
        for idx, (title, w) in enumerate(range_cols):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer)
            col.add_attribute(renderer, "text", idx)
            col.set_min_width(w)
            self.ranges_tree.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.ranges_tree)
        left_box.pack_start(scroll, True, True, 0)

        r_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_add_rng = Gtk.Button(label=_("+ Add Range"))
        self.btn_add_rng.connect("clicked", self._on_add_range_clicked)
        r_actions.pack_start(self.btn_add_rng, False, False, 0)

        self.btn_del_rng = Gtk.Button(label=_("- Remove Range"))
        self.btn_del_rng.connect("clicked", self._on_delete_range_clicked)
        r_actions.pack_start(self.btn_del_rng, False, False, 0)

        left_box.pack_start(r_actions, False, False, 2)
        paned.pack1(left_box, True, False)

        # Right: Range Inspector
        insp_scroll = Gtk.ScrolledWindow()
        insp_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        insp_scroll.set_min_content_width(220)

        insp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        insp_box.set_margin_start(8)
        insp_box.set_margin_end(8)
        insp_box.set_margin_top(4)
        insp_box.set_margin_bottom(4)

        lbl_title = Gtk.Label(xalign=0)
        lbl_title.set_markup("<b>" + _("Slot / Range Properties") + "</b>")
        insp_box.pack_start(lbl_title, False, False, 2)

        grid = Gtk.Grid(column_spacing=6, row_spacing=4)
        grid.attach(Gtk.Label(label=_("Slot Label:"), xalign=0), 0, 0, 1, 1)
        self.entry_rng_label = Gtk.Entry()
        self.entry_rng_label.set_hexpand(True)
        grid.attach(self.entry_rng_label, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("DMX Min:"), xalign=0), 0, 1, 1, 1)
        self.spin_rng_min = Gtk.SpinButton.new_with_range(0, 255, 1)
        grid.attach(self.spin_rng_min, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("DMX Max:"), xalign=0), 0, 2, 1, 1)
        self.spin_rng_max = Gtk.SpinButton.new_with_range(0, 255, 1)
        grid.attach(self.spin_rng_max, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Snap Value:"), xalign=0), 0, 3, 1, 1)
        self.spin_rng_snap = Gtk.SpinButton.new_with_range(0, 255, 1)
        grid.attach(self.spin_rng_snap, 1, 3, 1, 1)

        insp_box.pack_start(grid, False, False, 4)

        self.btn_update_rng = Gtk.Button(label=_("Update Range"))
        self.btn_update_rng.connect("clicked", self._on_update_range_clicked)
        insp_box.pack_start(self.btn_update_rng, False, False, 4)

        insp_scroll.add(insp_box)
        paned.pack2(insp_scroll, False, False)

        page_box.pack_start(paned, True, True, 2)
        return page_box

    # -------------------------------------------------------------------------
    # Sub-View 3: Color Profile (Paned: Emitters Table | Emitter Inspector)
    # -------------------------------------------------------------------------

    def _build_color_page(self) -> Gtk.Box:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lbl_color_info = Gtk.Label(
            label=_("CIE 1931 xyY Color Calibration & Emitters"), xalign=0
        )
        top_bar.pack_start(self.lbl_color_info, True, True, 0)

        self.btn_preset_rgb = Gtk.Button(label=_("Preset sRGB"))
        self.btn_preset_rgb.connect(
            "clicked", lambda _b: self._apply_color_preset("rgb")
        )
        top_bar.pack_end(self.btn_preset_rgb, False, False, 0)

        self.btn_preset_rgbw = Gtk.Button(label=_("Preset RGBW"))
        self.btn_preset_rgbw.connect(
            "clicked", lambda _b: self._apply_color_preset("rgbw")
        )
        top_bar.pack_end(self.btn_preset_rgbw, False, False, 0)

        page_box.pack_start(top_bar, False, False, 2)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(360)

        # Left: Emitters Table
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.emitters_store = Gtk.ListStore(
            str,  # COL_EM_NAME
            str,  # COL_EM_ATTR
            float,  # COL_EM_X
            float,  # COL_EM_Y
            float,  # COL_EM_LUM
            float,  # COL_EM_NM
        )
        self.emitters_tree = Gtk.TreeView(model=self.emitters_store)
        sel = self.emitters_tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)
        sel.connect("changed", self._on_emitter_selection_changed)

        em_cols = [
            ("Emitter", COL_EM_NAME, 80),
            ("GDTF Attr", COL_EM_ATTR, 90),
            ("x", COL_EM_X, 45),
            ("y", COL_EM_Y, 45),
            ("Y", COL_EM_LUM, 45),
        ]
        for title, idx, w in em_cols:
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer)
            col.add_attribute(renderer, "text", idx)
            col.set_min_width(w)
            self.emitters_tree.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.emitters_tree)
        left_box.pack_start(scroll, True, True, 0)

        em_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_add_em = Gtk.Button(label=_("+ Add Emitter"))
        self.btn_add_em.connect("clicked", self._on_add_emitter_clicked)
        em_actions.pack_start(self.btn_add_em, False, False, 0)

        self.btn_del_em = Gtk.Button(label=_("- Remove Emitter"))
        self.btn_del_em.connect("clicked", self._on_delete_emitter_clicked)
        em_actions.pack_start(self.btn_del_em, False, False, 0)

        left_box.pack_start(em_actions, False, False, 2)
        paned.pack1(left_box, True, False)

        # Right: Emitter Inspector
        insp_scroll = Gtk.ScrolledWindow()
        insp_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        insp_scroll.set_min_content_width(220)

        insp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        insp_box.set_margin_start(8)
        insp_box.set_margin_end(8)
        insp_box.set_margin_top(4)
        insp_box.set_margin_bottom(4)

        lbl_title = Gtk.Label(xalign=0)
        lbl_title.set_markup("<b>" + _("Emitter Calibration") + "</b>")
        insp_box.pack_start(lbl_title, False, False, 2)

        grid = Gtk.Grid(column_spacing=6, row_spacing=4)
        grid.attach(Gtk.Label(label=_("Name:"), xalign=0), 0, 0, 1, 1)
        self.entry_em_name = Gtk.Entry()
        self.entry_em_name.set_hexpand(True)
        grid.attach(self.entry_em_name, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("CIE x:"), xalign=0), 0, 1, 1, 1)
        self.spin_em_x = Gtk.SpinButton.new_with_range(0.0, 1.0, 0.01)
        self.spin_em_x.set_digits(4)
        grid.attach(self.spin_em_x, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("CIE y:"), xalign=0), 0, 2, 1, 1)
        self.spin_em_y = Gtk.SpinButton.new_with_range(0.0, 1.0, 0.01)
        self.spin_em_y.set_digits(4)
        grid.attach(self.spin_em_y, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Luminance (Y):"), xalign=0), 0, 3, 1, 1)
        self.spin_em_lum = Gtk.SpinButton.new_with_range(0.0, 1000.0, 1.0)
        self.spin_em_lum.set_digits(1)
        grid.attach(self.spin_em_lum, 1, 3, 1, 1)

        insp_box.pack_start(grid, False, False, 4)

        self.btn_update_em = Gtk.Button(label=_("Update Emitter"))
        self.btn_update_em.connect("clicked", self._on_update_emitter_clicked)
        insp_box.pack_start(self.btn_update_em, False, False, 4)

        insp_scroll.add(insp_box)
        paned.pack2(insp_scroll, False, False)

        page_box.pack_start(paned, True, True, 2)
        return page_box

    # -------------------------------------------------------------------------
    # Catalog Loading & Filtering
    # -------------------------------------------------------------------------

    def refresh_catalog(self, select_key: Optional[tuple[str, str]] = None) -> None:
        """Reload catalogue list from lightshow fixture library."""
        if select_key is None:
            if self._pending_select_key:
                select_key = self._pending_select_key
                self._pending_select_key = None
            elif self.active_definition:
                select_key = (
                    self.active_definition.manufacturer,
                    self.active_definition.model,
                )

        self._updating_ui = True
        self.cat_store.clear()
        target_iter = None

        for fdef in self.fixture_library.all():
            used = self.patch.count_devices_using_definition(
                fdef.manufacturer, fdef.model
            )
            src_label = _("Built-in") if fdef.is_builtin else _("User")
            fprint = fdef.default_mode().footprint()
            modes_summary = f"{len(fdef.dmx_modes)} ({fprint}ch)"
            row_iter = self.cat_store.append(
                [
                    fdef.manufacturer,
                    fdef.model,
                    fdef.fixture_type.value,
                    modes_summary,
                    src_label,
                    used,
                    fdef.is_builtin,
                ]
            )
            if select_key and (fdef.manufacturer, fdef.model) == select_key:
                target_iter = row_iter

        self._updating_ui = False

        if target_iter is not None and select_key is not None:
            path = self.cat_store.get_path(target_iter)
            filtered_path = self.cat_filter.convert_child_path_to_path(path)
            if filtered_path:
                self.cat_tree.set_cursor(filtered_path)
                self.cat_tree.get_selection().select_path(filtered_path)
            try:
                fdef = self.fixture_library.get(select_key[0], select_key[1])
                self.load_definition(fdef)
            except KeyError:
                pass
            return

        # Select first row if nothing selected
        has_sel = bool(self.cat_tree.get_selection().get_selected()[1])
        if len(self.cat_store) > 0 and not has_sel:
            first_path = Gtk.TreePath.new_first()
            self.cat_tree.set_cursor(first_path)
            self.cat_tree.get_selection().select_path(first_path)

    def _filter_catalog(
        self, model: Gtk.TreeModel, tree_iter: Gtk.TreeIter, _data: object
    ) -> bool:
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        mfg = str(model.get_value(tree_iter, COL_CAT_MANUFACTURER)).lower()
        model_name = str(model.get_value(tree_iter, COL_CAT_MODEL)).lower()
        ftype = str(model.get_value(tree_iter, COL_CAT_TYPE)).lower()
        return query in mfg or query in model_name or query in ftype

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self.cat_filter.refilter()

    def _on_catalog_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        if self._updating_ui:
            return
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return
        assert isinstance(model, Gtk.TreeModelFilter)
        child_iter = model.convert_iter_to_child_iter(tree_iter)
        mfg = str(self.cat_store.get_value(child_iter, COL_CAT_MANUFACTURER))
        mod = str(self.cat_store.get_value(child_iter, COL_CAT_MODEL))
        try:
            fdef = self.fixture_library.get(mfg, mod)
            self.load_definition(fdef)
        except KeyError:
            pass

    # -------------------------------------------------------------------------
    # Definition Loading into Editor
    # -------------------------------------------------------------------------

    def load_definition(self, fdef: FixtureDefinition) -> None:
        """Load a FixtureDefinition into the editor fields."""
        self._updating_ui = True
        self.active_definition = fdef.clone()
        # retain is_builtin status for UI permission checks
        self.active_definition.is_builtin = fdef.is_builtin
        self.original_definition_key = (fdef.manufacturer, fdef.model)

        self.entry_mfg.set_text(self.active_definition.manufacturer)
        self.entry_model.set_text(self.active_definition.model)
        self.combo_type.set_active_id(self.active_definition.fixture_type.value)
        self.entry_notes.set_text(self.active_definition.notes)

        # Thumbnail display
        if self.active_definition.thumbnail:
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(self.active_definition.thumbnail)
                loader.close()
                pixbuf = loader.get_pixbuf()
                if pixbuf:
                    scaled = pixbuf.scale_simple(56, 56, GdkPixbuf.InterpType.BILINEAR)
                    self.thumbnail_image.set_from_pixbuf(scaled)
            except Exception:
                self.thumbnail_image.set_from_icon_name(
                    "applications-multimedia", Gtk.IconSize.DIALOG
                )
        else:
            self.thumbnail_image.set_from_icon_name(
                "applications-multimedia", Gtk.IconSize.DIALOG
            )

        used = self.patch.count_devices_using_definition(fdef.manufacturer, fdef.model)
        if fdef.is_builtin:
            self.lbl_status.set_markup(
                "<span foreground='#888888'>🔒 "
                + _("Built-in profile (Read-Only). Click 'Duplicate' to edit.")
                + "</span>"
            )
            self.btn_apply.set_sensitive(False)
            self.btn_delete.set_sensitive(False)
            self._set_editor_sensitive(False)
        else:
            used_txt = f" — Used by {used} device(s)" if used > 0 else " — Not patched"
            self.lbl_status.set_markup(
                "<span foreground='#55CC55'>✏ "
                + _("User profile (Editable)")
                + f"{used_txt}</span>"
            )
            self.btn_apply.set_sensitive(True)
            self.btn_delete.set_sensitive(used == 0)
            self._set_editor_sensitive(True)

        self._refresh_modes_combo()
        self._refresh_color_emitters()
        self._updating_ui = False

    def _set_editor_sensitive(self, sensitive: bool) -> None:
        self.entry_mfg.set_sensitive(sensitive)
        self.entry_model.set_sensitive(sensitive)
        self.combo_type.set_sensitive(sensitive)
        self.entry_notes.set_sensitive(sensitive)
        self.btn_add_mode.set_sensitive(sensitive)
        self.btn_dup_mode.set_sensitive(sensitive)
        self.btn_del_mode.set_sensitive(sensitive)
        self.entry_mode_name.set_sensitive(sensitive)
        self.entry_mode_desc.set_sensitive(sensitive)
        self.btn_add_ch.set_sensitive(sensitive)
        self.btn_del_ch.set_sensitive(sensitive)
        self.btn_update_ch.set_sensitive(sensitive)
        self.spin_ch_offset.set_sensitive(sensitive)
        self.spin_ch_fine.set_sensitive(sensitive)
        self.entry_ch_label.set_sensitive(sensitive)
        self.combo_ch_type.set_sensitive(sensitive)
        self.combo_ch_merge.set_sensitive(sensitive)
        self.spin_ch_home.set_sensitive(sensitive)
        self.spin_ch_locate.set_sensitive(sensitive)
        self.spin_ch_min.set_sensitive(sensitive)
        self.spin_ch_max.set_sensitive(sensitive)
        self.entry_ch_unit.set_sensitive(sensitive)
        self.btn_add_rng.set_sensitive(sensitive)
        self.btn_del_rng.set_sensitive(sensitive)
        self.btn_update_rng.set_sensitive(sensitive)
        self.entry_rng_label.set_sensitive(sensitive)
        self.spin_rng_min.set_sensitive(sensitive)
        self.spin_rng_max.set_sensitive(sensitive)
        self.spin_rng_snap.set_sensitive(sensitive)
        self.btn_add_em.set_sensitive(sensitive)
        self.btn_del_em.set_sensitive(sensitive)
        self.btn_update_em.set_sensitive(sensitive)
        self.entry_em_name.set_sensitive(sensitive)
        self.spin_em_x.set_sensitive(sensitive)
        self.spin_em_y.set_sensitive(sensitive)
        self.spin_em_lum.set_sensitive(sensitive)
        self.btn_preset_rgb.set_sensitive(sensitive)
        self.btn_preset_rgbw.set_sensitive(sensitive)

    def _refresh_modes_combo(self) -> None:
        self.combo_modes.remove_all()
        if not self.active_definition or not self.active_definition.dmx_modes:
            return
        for mode in self.active_definition.dmx_modes:
            self.combo_modes.append(mode.name, mode.name)
        self.combo_modes.set_active(0)

    def _on_mode_combo_changed(self, combo: Gtk.ComboBoxText) -> None:
        if not self.active_definition:
            return
        mode_name = combo.get_active_text()
        if not mode_name:
            return
        try:
            mode = self.active_definition.get_mode(mode_name)
            self.entry_mode_name.set_text(mode.name)
            self.entry_mode_desc.set_text(mode.description)
            self.lbl_mode_footprint.set_text(
                f"Footprint: {mode.footprint()}ch ({mode.channel_count()} logical)"
            )
            self._load_mode_channels(mode)
        except KeyError:
            pass

    def _load_mode_channels(self, mode: DmxModeDefinition) -> None:
        self.channels_store.clear()
        for idx, ch_def in enumerate(mode.channel_defs):
            fine_str = (
                str(ch_def.fine_offset + 1) if ch_def.fine_offset is not None else "-"
            )
            ultra_str = (
                str(ch_def.ultra_fine_offset + 1)
                if ch_def.ultra_fine_offset is not None
                else "-"
            )
            locate_str = (
                str(ch_def.highlight_value)
                if ch_def.highlight_value is not None
                else "-"
            )
            merge_str = ch_def.merge_mode.value.upper() if ch_def.merge_mode else "HTP"

            self.channels_store.append(
                [
                    idx,
                    str(ch_def.offset + 1),
                    fine_str,
                    ultra_str,
                    ch_def.label,
                    ch_def.channel_type.value,
                    str(ch_def.default_value),
                    locate_str,
                    f"{ch_def.physical_min:.1f}",
                    f"{ch_def.physical_max:.1f}",
                    ch_def.physical_unit,
                    merge_str,
                ]
            )

        if len(self.channels_store) > 0:
            self.channels_tree.get_selection().select_path(Gtk.TreePath.new_first())

    def _on_channel_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        model, tree_iter = selection.get_selected()
        if tree_iter is None or not self.active_definition:
            return
        idx = int(model.get_value(tree_iter, COL_CH_INDEX))
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        mode = self.active_definition.get_mode(mode_name)
        if idx >= len(mode.channel_defs):
            return

        ch_def = mode.channel_defs[idx]
        self.spin_ch_offset.set_value(ch_def.offset + 1)
        self.spin_ch_fine.set_value(
            ch_def.fine_offset + 1 if ch_def.fine_offset is not None else 0
        )
        self.entry_ch_label.set_text(ch_def.label)
        self.combo_ch_type.set_active_id(ch_def.channel_type.value)
        self.combo_ch_merge.set_active_id(
            ch_def.merge_mode.value if ch_def.merge_mode else "htp"
        )
        self.spin_ch_home.set_value(ch_def.default_value)
        self.spin_ch_locate.set_value(
            ch_def.highlight_value if ch_def.highlight_value is not None else -1
        )
        self.spin_ch_min.set_value(ch_def.physical_min)
        self.spin_ch_max.set_value(ch_def.physical_max)
        self.entry_ch_unit.set_text(ch_def.physical_unit)

        self._load_channel_ranges(ch_def)

    def _load_channel_ranges(self, ch_def: ChannelDefinition) -> None:
        self.ranges_store.clear()
        c_type = ch_def.channel_type.value
        self.lbl_range_context.set_text(
            f"Channel #{ch_def.offset + 1} '{ch_def.label}' ({c_type}) Ranges:"
        )
        for rng in ch_def.ranges:
            snap = rng.snap_value or rng.value_min
            self.ranges_store.append([rng.label, rng.value_min, rng.value_max, snap])
        if len(self.ranges_store) > 0:
            self.ranges_tree.get_selection().select_path(Gtk.TreePath.new_first())

    def _refresh_color_emitters(self) -> None:
        self.emitters_store.clear()
        if not self.active_definition or not self.active_definition.color_profile:
            return
        for em in self.active_definition.color_profile.emitters:
            self.emitters_store.append(
                [
                    em.name,
                    em.gdtf_attribute,
                    float(em.cie.x),
                    float(em.cie.y),
                    float(em.cie.Y),
                    float(em.dominant_wavelength),
                ]
            )
        if len(self.emitters_store) > 0:
            self.emitters_tree.get_selection().select_path(Gtk.TreePath.new_first())

    # -------------------------------------------------------------------------
    # Channel and Mode Manipulation Handlers
    # -------------------------------------------------------------------------

    def _on_update_channel_clicked(self, _button: Gtk.Button) -> None:
        model, tree_iter = self.channels_tree.get_selection().get_selected()
        if tree_iter is None or not self.active_definition:
            return
        idx = int(model.get_value(tree_iter, COL_CH_INDEX))
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        mode = self.active_definition.get_mode(mode_name)
        if idx >= len(mode.channel_defs):
            return

        ch_def = mode.channel_defs[idx]
        ch_def.offset = int(self.spin_ch_offset.get_value()) - 1
        fine_val = int(self.spin_ch_fine.get_value())
        ch_def.fine_offset = fine_val - 1 if fine_val > 0 else None
        ch_def.label = self.entry_ch_label.get_text().strip() or ch_def.label
        ctype_id = self.combo_ch_type.get_active_id()
        if ctype_id:
            ch_def.channel_type = ChannelType(ctype_id)
        merge_id = self.combo_ch_merge.get_active_id()
        if merge_id:
            ch_def.merge_mode = MergeMode(merge_id)
        ch_def.default_value = int(self.spin_ch_home.get_value())
        loc_val = int(self.spin_ch_locate.get_value())
        ch_def.highlight_value = loc_val if loc_val >= 0 else None
        ch_def.physical_min = float(self.spin_ch_min.get_value())
        ch_def.physical_max = float(self.spin_ch_max.get_value())
        ch_def.physical_unit = self.entry_ch_unit.get_text().strip()

        self._load_mode_channels(mode)

    def _on_add_channel_clicked(self, _button: Gtk.Button) -> None:
        if not self.active_definition:
            return
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        mode = self.active_definition.get_mode(mode_name)
        next_offset = mode.footprint()
        new_ch = ChannelDefinition(
            channel_type=ChannelType.GENERIC,
            offset=next_offset,
            label=f"Channel {next_offset + 1}",
        )
        mode.channel_defs.append(new_ch)
        self._load_mode_channels(mode)

    def _on_delete_channel_clicked(self, _button: Gtk.Button) -> None:
        model, tree_iter = self.channels_tree.get_selection().get_selected()
        if tree_iter is None or not self.active_definition:
            return
        idx = int(model.get_value(tree_iter, COL_CH_INDEX))
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        mode = self.active_definition.get_mode(mode_name)
        if idx < len(mode.channel_defs):
            mode.channel_defs.pop(idx)
            self._load_mode_channels(mode)

    def _on_add_mode_clicked(self, _button: Gtk.Button) -> None:
        if not self.active_definition:
            return
        base_name = "New Mode"
        count = 1
        name = base_name
        existing_names = self.active_definition.mode_names()
        while name in existing_names:
            count += 1
            name = f"{base_name} {count}"
        new_mode = DmxModeDefinition(
            name=name,
            channel_defs=[
                ChannelDefinition(ChannelType.INTENSITY, offset=0, label="Dimmer")
            ],
            description="Custom mode",
        )
        self.active_definition.dmx_modes.append(new_mode)
        self._refresh_modes_combo()
        self.combo_modes.set_active_id(name)

    def _on_duplicate_mode_clicked(self, _button: Gtk.Button) -> None:
        if not self.active_definition:
            return
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        src_mode = self.active_definition.get_mode(mode_name)
        dup_name = f"{src_mode.name} (Copy)"
        dup_mode = DmxModeDefinition.from_dict(src_mode.to_dict())
        dup_mode.name = dup_name
        self.active_definition.dmx_modes.append(dup_mode)
        self._refresh_modes_combo()
        self.combo_modes.set_active_id(dup_name)

    def _on_delete_mode_clicked(self, _button: Gtk.Button) -> None:
        if not self.active_definition or len(self.active_definition.dmx_modes) <= 1:
            return
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        self.active_definition.dmx_modes = [
            m for m in self.active_definition.dmx_modes if m.name != mode_name
        ]
        self._refresh_modes_combo()

    # -------------------------------------------------------------------------
    # Range and Color Manipulation Handlers
    # -------------------------------------------------------------------------

    def _on_add_range_clicked(self, _button: Gtk.Button) -> None:
        model, tree_iter = self.channels_tree.get_selection().get_selected()
        if tree_iter is None or not self.active_definition:
            return
        idx = int(model.get_value(tree_iter, COL_CH_INDEX))
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        mode = self.active_definition.get_mode(mode_name)
        if idx >= len(mode.channel_defs):
            return
        ch_def = mode.channel_defs[idx]
        lbl = self.entry_rng_label.get_text().strip() or "Slot"
        min_v = int(self.spin_rng_min.get_value())
        max_v = int(self.spin_rng_max.get_value())
        snap_v = int(self.spin_rng_snap.get_value())
        ch_def.ranges.append(
            ChannelRange(
                label=lbl,
                channel_type=ch_def.channel_type,
                value_min=min_v,
                value_max=max_v,
                snap_value=snap_v,
            )
        )
        self._load_channel_ranges(ch_def)

    def _on_delete_range_clicked(self, _button: Gtk.Button) -> None:
        r_model, r_iter = self.ranges_tree.get_selection().get_selected()
        ch_model, ch_iter = self.channels_tree.get_selection().get_selected()
        if r_iter is None or ch_iter is None or not self.active_definition:
            return
        ch_idx = int(ch_model.get_value(ch_iter, COL_CH_INDEX))
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        ch_def = self.active_definition.get_mode(mode_name).channel_defs[ch_idx]
        path = r_model.get_path(r_iter)
        if path:
            r_idx = path.get_indices()[0]
            if r_idx < len(ch_def.ranges):
                ch_def.ranges.pop(r_idx)
                self._load_channel_ranges(ch_def)

    def _on_range_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return
        lbl = str(model.get_value(tree_iter, COL_RNG_LABEL))
        min_v = int(model.get_value(tree_iter, COL_RNG_MIN))
        max_v = int(model.get_value(tree_iter, COL_RNG_MAX))
        snap_v = int(model.get_value(tree_iter, COL_RNG_SNAP))
        self.entry_rng_label.set_text(lbl)
        self.spin_rng_min.set_value(min_v)
        self.spin_rng_max.set_value(max_v)
        self.spin_rng_snap.set_value(snap_v)

    def _on_update_range_clicked(self, _button: Gtk.Button) -> None:
        r_model, r_iter = self.ranges_tree.get_selection().get_selected()
        ch_model, ch_iter = self.channels_tree.get_selection().get_selected()
        if r_iter is None or ch_iter is None or not self.active_definition:
            return
        ch_idx = int(ch_model.get_value(ch_iter, COL_CH_INDEX))
        mode_name = self.combo_modes.get_active_text()
        if not mode_name:
            return
        ch_def = self.active_definition.get_mode(mode_name).channel_defs[ch_idx]
        path = r_model.get_path(r_iter)
        if path:
            r_idx = path.get_indices()[0]
            if r_idx < len(ch_def.ranges):
                rng = ch_def.ranges[r_idx]
                rng.label = self.entry_rng_label.get_text().strip() or rng.label
                rng.value_min = int(self.spin_rng_min.get_value())
                rng.value_max = int(self.spin_rng_max.get_value())
                rng.snap_value = int(self.spin_rng_snap.get_value())
                self._load_channel_ranges(ch_def)

    def _apply_color_preset(self, preset: str) -> None:
        if not self.active_definition:
            return
        from olc.devices.builtin import (
            create_rgb_definition,
            create_rgbw_definition,
        )

        template = (
            create_rgbw_definition() if preset == "rgbw" else create_rgb_definition()
        )
        self.active_definition.color_profile = template.color_profile
        self._refresh_color_emitters()

    def _on_add_emitter_clicked(self, _button: Gtk.Button) -> None:
        if not self.active_definition:
            return
        name = self.entry_em_name.get_text().strip() or "Emitter"
        x = float(self.spin_em_x.get_value())
        y = float(self.spin_em_y.get_value())
        lum = float(self.spin_em_lum.get_value())
        from olc.devices.color import CIExyY

        new_em = EmitterProfile(name=name, cie=CIExyY(x, y, lum))
        if self.active_definition.color_profile is None:
            self.active_definition.color_profile = FixtureColorProfile(
                fixture_name=self.active_definition.full_name,
                emitters=[new_em],
            )
        else:
            self.active_definition.color_profile.emitters.append(new_em)
        self._refresh_color_emitters()

    def _on_delete_emitter_clicked(self, _button: Gtk.Button) -> None:
        model, tree_iter = self.emitters_tree.get_selection().get_selected()
        if (
            tree_iter is None
            or not self.active_definition
            or not self.active_definition.color_profile
        ):
            return
        path = model.get_path(tree_iter)
        if path:
            em_idx = path.get_indices()[0]
            if em_idx < len(self.active_definition.color_profile.emitters):
                self.active_definition.color_profile.emitters.pop(em_idx)
                self._refresh_color_emitters()

    def _on_emitter_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return
        name = str(model.get_value(tree_iter, COL_EM_NAME))
        x = float(model.get_value(tree_iter, COL_EM_X))
        y = float(model.get_value(tree_iter, COL_EM_Y))
        lum = float(model.get_value(tree_iter, COL_EM_LUM))
        self.entry_em_name.set_text(name)
        self.spin_em_x.set_value(x)
        self.spin_em_y.set_value(y)
        self.spin_em_lum.set_value(lum)

    def _on_update_emitter_clicked(self, _button: Gtk.Button) -> None:
        model, tree_iter = self.emitters_tree.get_selection().get_selected()
        if (
            tree_iter is None
            or not self.active_definition
            or not self.active_definition.color_profile
        ):
            return
        path = model.get_path(tree_iter)
        if path:
            em_idx = path.get_indices()[0]
            if em_idx < len(self.active_definition.color_profile.emitters):
                em = self.active_definition.color_profile.emitters[em_idx]
                em.name = self.entry_em_name.get_text().strip() or em.name
                em.cie.x = float(self.spin_em_x.get_value())
                em.cie.y = float(self.spin_em_y.get_value())
                em.cie.Y = float(self.spin_em_lum.get_value())
                self._refresh_color_emitters()

    # -------------------------------------------------------------------------
    # Action Toolbar Callbacks (Import, New, Duplicate, Delete, Apply)
    # -------------------------------------------------------------------------

    def refresh(self) -> None:
        """Refresh tab contents."""
        self.refresh_catalog()

    def _on_import_gdtf_clicked(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative.new(
            _("Import GDTF Fixture File"),
            self.app.window if self.app is not None else None,
            Gtk.FileChooserAction.OPEN,
            _("_Open"),
            _("_Cancel"),
        )
        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("GDTF files (*.gdtf)"))
        file_filter.add_pattern("*.gdtf")
        chooser.add_filter(file_filter)

        res = chooser.run()
        if res == Gtk.ResponseType.ACCEPT:
            filename = chooser.get_filename()
            if filename:
                try:
                    self.core.action_registry.execute("fixture.import_gdtf", filename)
                except Exception:
                    pass
        chooser.destroy()

    def _on_new_clicked(self, _button: Gtk.Button) -> None:
        """Create a new custom fixture definition."""
        base_name = "New Fixture"
        count = 1
        model_name = base_name
        existing_keys = self.fixture_library.keys()
        while f"Custom:{model_name}" in existing_keys:
            count += 1
            model_name = f"{base_name} {count}"

        new_fdef = FixtureDefinition(
            manufacturer="Custom",
            model=model_name,
            fixture_type=FixtureType.GENERIC,
            dmx_modes=[
                DmxModeDefinition(
                    name="Standard 1ch",
                    channel_defs=[
                        ChannelDefinition(
                            ChannelType.INTENSITY, offset=0, label="Dimmer"
                        )
                    ],
                )
            ],
            notes="Custom user created fixture",
            is_builtin=False,
        )
        self._pending_select_key = ("Custom", model_name)
        self.core.action_registry.execute("fixture.upsert", new_fdef)
        self.refresh_catalog(select_key=("Custom", model_name))

    def _on_duplicate_clicked(self, _button: Gtk.Button) -> None:
        """Duplicate selected profile into an editable user profile."""
        if not self.active_definition:
            return
        src = self.active_definition
        dup_mfg = src.manufacturer if src.manufacturer != "Generic" else "Custom"
        base_mod = f"{src.model} (Copy)"
        dup_mod = base_mod
        count = 1
        existing_keys = self.fixture_library.keys()
        while f"{dup_mfg}:{dup_mod}" in existing_keys:
            count += 1
            dup_mod = f"{base_mod} {count}"

        clone_def = src.clone(new_manufacturer=dup_mfg, new_model=dup_mod)
        self._pending_select_key = (dup_mfg, dup_mod)
        self.core.action_registry.execute("fixture.upsert", clone_def)
        self.refresh_catalog(select_key=(dup_mfg, dup_mod))

    def _on_delete_clicked(self, _button: Gtk.Button) -> None:
        """Delete selected custom profile."""
        if not self.active_definition or self.active_definition.is_builtin:
            return
        mfg = self.active_definition.manufacturer
        mod = self.active_definition.model
        try:
            self.core.action_registry.execute("fixture.delete", mfg, mod)
            self.refresh_catalog()
        except Exception:
            pass

    def _on_apply_clicked(self, _button: Gtk.Button) -> None:
        """Apply edited fields back to the FixtureDefinition and Show."""
        if not self.active_definition or self.active_definition.is_builtin:
            return

        new_mfg = (
            self.entry_mfg.get_text().strip() or self.active_definition.manufacturer
        )
        new_mod = self.entry_model.get_text().strip() or self.active_definition.model
        self.active_definition.manufacturer = new_mfg
        self.active_definition.model = new_mod
        ftype_id = self.combo_type.get_active_id()
        if ftype_id:
            self.active_definition.fixture_type = FixtureType(ftype_id)
        self.active_definition.notes = self.entry_notes.get_text().strip()

        # Update current mode name & desc if edited
        curr_mode_name = self.combo_modes.get_active_text()
        if curr_mode_name:
            try:
                curr_mode = self.active_definition.get_mode(curr_mode_name)
                curr_mode.name = (
                    self.entry_mode_name.get_text().strip() or curr_mode.name
                )
                curr_mode.description = self.entry_mode_desc.get_text().strip()
            except KeyError:
                pass

        old_mfg, old_mod = (
            self.original_definition_key
            if self.original_definition_key
            else (new_mfg, new_mod)
        )
        self._pending_select_key = (new_mfg, new_mod)
        self.core.action_registry.execute(
            "fixture.upsert",
            self.active_definition,
            old_manufacturer=old_mfg,
            old_model=old_mod,
        )
        self.refresh_catalog(select_key=(new_mfg, new_mod))
