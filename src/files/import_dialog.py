# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from __future__ import annotations

import typing
from enum import Enum, auto
from gettext import gettext as _

from gi.repository import Gtk

if typing.TYPE_CHECKING:
    from olc.files.parsed_data import ParsedData


class Action(Enum):
    """Action type"""

    REPLACE = auto()
    MERGE = auto()
    IGNORE = auto()


class DialogData(Gtk.Dialog):
    """Dialog to choose data to import"""

    actions: dict

    def __init__(self, parent, data, actions):
        super().__init__(title=_("Data to import"), transient_for=parent, flags=0)

        self.actions = actions

        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK,
                         Gtk.ResponseType.OK)
        box = self.get_content_area()
        box.set_spacing(6)
        # If you change actions order, you have to modify combo callbacks
        actions = ["Replace", "Merge", "Ignore"]
        if data.patch:
            self._patch(actions, box)
        if data.sequences:
            self._sequences(actions, box, data)
        if data.groups:
            self._groups(actions, box)
        if data.independents:
            self._independents(actions, box)
        self.show_all()

    def _patch(self, actions: list, box: Gtk.Box) -> None:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label("Patch:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_patch_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _sequences(self, actions: list, box: Gtk.Box, data: ParsedData) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label("Sequences:")
        hbox.pack_start(label, False, True, 0)
        box.add(hbox)
        combos = {}
        for sequence in data.sequences.keys():
            self.actions["sequences"][sequence] = Action.REPLACE
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            if sequence == 1:
                name = "MainPlayback"
            elif data.sequences[sequence].get("text"):
                name = data.sequences[sequence]["text"]
            else:
                name = str(sequence)
            label = Gtk.Label(name)
            combos[sequence] = Gtk.ComboBoxText()
            combos[sequence].connect("changed", self._on_seq_changed, sequence)
            for action in actions:
                combos[sequence].append_text(action)
            combos[sequence].set_active(0)
            hbox.pack_start(label, True, True, 0)
            hbox.add(combos[sequence])
            box.add(hbox)

    def _groups(self, actions: list, box: Gtk.Box) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label("Groups:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_groups_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _independents(self, actions: list, box: Gtk.Box) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label("Independents:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_independents_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _on_patch_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            self.actions["patch"] = Action.REPLACE
        elif active == 1:
            self.actions["patch"] = Action.MERGE
        elif active == 2:
            self.actions["patch"] = Action.IGNORE

    def _on_seq_changed(self, widget, sequence):
        active = widget.get_active()
        if active == 0:
            self.actions["sequences"][sequence] = Action.REPLACE
        elif active == 1:
            self.actions["sequences"][sequence] = Action.MERGE
        elif active == 2:
            self.actions["sequences"][sequence] = Action.IGNORE

    def _on_groups_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            self.actions["groups"] = Action.REPLACE
        elif active == 1:
            self.actions["groups"] = Action.MERGE
        elif active == 2:
            self.actions["groups"] = Action.IGNORE

    def _on_independents_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            self.actions["independents"] = Action.REPLACE
        elif active == 1:
            self.actions["independents"] = Action.MERGE
        elif active == 2:
            self.actions["independents"] = Action.IGNORE
