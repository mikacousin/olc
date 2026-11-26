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
"""Popovers for quick inline selection of fixture modes and profiles in Patch."""

from __future__ import annotations

import typing
from gettext import gettext as _
from typing import Callable

from gi.repository import Gdk, Gtk

if typing.TYPE_CHECKING:
    from olc.devices.device import LightingDevice
    from olc.devices.fixture import FixtureDefinition, FixtureLibrary


class ModeSelectionPopover(Gtk.Popover):
    """Popover listing DMX modes of a fixture definition for quick switching."""

    def __init__(self, on_mode_selected: Callable[[str], None]) -> None:
        super().__init__()
        self._on_mode_selected = on_mode_selected
        self._row_modes: dict[Gtk.ListBoxRow, str] = {}
        self.set_position(Gtk.PositionType.BOTTOM)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)
        box.pack_start(self._listbox, True, True, 0)

        self.add(box)

    def open_for_device(
        self,
        device: LightingDevice,
        fdef: FixtureDefinition,
        relative_to: Gtk.Widget,
        pointing_to: Gdk.Rectangle,
    ) -> None:
        """Populate modes for *device* and open the popover at *pointing_to*."""
        for child in self._listbox.get_children():
            child.destroy()
        self._row_modes.clear()

        current_mode = device.mode_name
        selected_row: Gtk.ListBoxRow | None = None
        for mode_name in fdef.mode_names():
            mode = fdef.get_mode(mode_name)
            row = Gtk.ListBoxRow()
            self._row_modes[row] = mode_name
            lbl = Gtk.Label(
                label=f"{mode_name} ({mode.footprint()} DMX)",
                xalign=0.0,
            )
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(4)
            lbl.set_margin_bottom(4)
            row.add(lbl)
            self._listbox.add(row)
            if mode_name == current_mode:
                selected_row = row

        self.set_relative_to(relative_to)
        self.set_pointing_to(pointing_to)
        self.show_all()
        if selected_row is not None:
            self._listbox.select_row(selected_row)
            selected_row.grab_focus()

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        mode_name = self._row_modes.get(row)
        self.popdown()
        if mode_name:
            self._on_mode_selected(mode_name)


class FixtureSelectionPopover(Gtk.Popover):
    """Searchable popover for quick fixture profile selection from library."""

    def __init__(
        self,
        library: FixtureLibrary,
        on_fixture_selected: Callable[[str], None],
        on_advanced_clicked: Callable[[], None],
    ) -> None:
        super().__init__()
        self._library = library
        self._on_fixture_selected = on_fixture_selected
        self._on_advanced_clicked = on_advanced_clicked
        self._row_keys: dict[Gtk.ListBoxRow, str] = {}
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_size_request(300, 320)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(_("Search fixture..."))
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", self._on_search_activate)
        self._search_entry.connect("key-press-event", self._on_search_key_press)
        box.pack_start(self._search_entry, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)
        scroll.add(self._listbox)
        box.pack_start(scroll, True, True, 0)

        adv_btn = Gtk.Button(label=_("Advanced Exchange..."))
        adv_btn.connect("clicked", self._on_advanced_btn_clicked)
        box.pack_end(adv_btn, False, False, 0)

        self.add(box)

    def set_library(self, library: FixtureLibrary) -> None:
        """Update the FixtureLibrary instance used for fixture lookups."""
        self._library = library

    def _populate_list(self, query: str) -> None:
        for child in self._listbox.get_children():
            child.destroy()
        self._row_keys.clear()

        matches: list[FixtureDefinition] = sorted(
            self._library.search(query),
            key=lambda d: (d.manufacturer.casefold(), d.model.casefold()),
        )
        for fdef in matches[:50]:
            row = Gtk.ListBoxRow()
            key = f"{fdef.manufacturer}:{fdef.model}"
            self._row_keys[row] = key
            footprint = fdef.default_mode().footprint()
            lbl = Gtk.Label(
                label=f"{fdef.full_name} ({footprint} DMX)",
                xalign=0.0,
            )
            lbl.set_margin_start(6)
            lbl.set_margin_end(6)
            lbl.set_margin_top(3)
            lbl.set_margin_bottom(3)
            row.add(lbl)
            self._listbox.add(row)
        self._listbox.show_all()
        first_row = self._listbox.get_row_at_index(0)
        if first_row is not None:
            self._listbox.select_row(first_row)

    def open_for_device(
        self,
        _device: LightingDevice,
        relative_to: Gtk.Widget,
        pointing_to: Gdk.Rectangle,
    ) -> None:
        """Reset search, populate fixtures, and open popover at *pointing_to*."""
        self._search_entry.set_text("")
        self._populate_list("")
        self.set_relative_to(relative_to)
        self.set_pointing_to(pointing_to)
        self.show_all()
        self._search_entry.grab_focus()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._populate_list(entry.get_text().strip())

    def _on_search_activate(self, _entry: Gtk.SearchEntry) -> None:
        row = self._listbox.get_selected_row()
        if row is not None:
            self._on_row_activated(self._listbox, row)

    def _on_search_key_press(
        self, _entry: Gtk.SearchEntry, event: Gdk.EventKey
    ) -> bool:
        if event.keyval not in (Gdk.KEY_Down, Gdk.KEY_Up):
            return False
        rows = self._listbox.get_children()
        if not rows:
            return True
        selected = self._listbox.get_selected_row()
        curr_idx = selected.get_index() if selected is not None else -1
        step = 1 if event.keyval == Gdk.KEY_Down else -1
        next_idx = max(0, min(len(rows) - 1, curr_idx + step))
        target_row = self._listbox.get_row_at_index(next_idx)
        if target_row is not None:
            self._listbox.select_row(target_row)
            adj = self._listbox.get_adjustment()
            if adj is not None:
                alloc = target_row.get_allocation()
                if alloc.y < adj.get_value():
                    adj.set_value(alloc.y)
                elif alloc.y + alloc.height > adj.get_value() + adj.get_page_size():
                    adj.set_value(alloc.y + alloc.height - adj.get_page_size())
        return True

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        fixture_key = self._row_keys.get(row)
        self.popdown()
        if fixture_key:
            self._on_fixture_selected(fixture_key)

    def _on_advanced_btn_clicked(self, _btn: Gtk.Button) -> None:
        self.popdown()
        self._on_advanced_clicked()
