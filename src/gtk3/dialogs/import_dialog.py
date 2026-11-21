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
from __future__ import annotations

import typing
from gettext import gettext as _

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from olc.files.import_types import Action  # noqa: E402


class DialogData(Gtk.Dialog):
    """Dialog to choose data to import"""

    actions: dict[str, typing.Any]

    def __init__(
        self,
        parent: Gtk.Window,
        data: dict[str, typing.Any],
        actions: dict[str, typing.Any],
    ) -> None:
        super().__init__(title=_("Data to import"), transient_for=parent)

        self.actions = actions

        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )
        box = self.get_content_area()
        box.set_spacing(6)
        # If you change actions order, you have to modify combo callbacks
        act = ["Replace", "Merge", "Ignore"]
        if data.get("curves"):
            self._curves(act, box)
        if data.get("patch") or data.get("devices"):
            self._patch(act, box)
        if data["sequences"]:
            self._sequences(act, box, data)
        if data["groups"]:
            self._groups(act, box)
        if data.get("palettes"):
            self._palettes(act, box)
        if data.get("effects"):
            self._effects(act, box)
        if data["independents"]:
            self._independents(act, box)
        if data["faders"]:
            self._faders(act, box)
        self.show_all()

    def _curves(self, actions: list, box: Gtk.Box) -> None:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Curves:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_curves_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _patch(self, actions: list, box: Gtk.Box) -> None:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Patch:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_patch_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _sequences(self, actions: list, box: Gtk.Box, data: dict) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Sequences:")
        hbox.pack_start(label, False, True, 0)
        box.add(hbox)
        combos = {}
        for sequence in data["sequences"].keys():
            self.actions["sequences"][sequence] = Action.REPLACE
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            if sequence == 1:
                name = "MainPlayback"
            elif data["sequences"][sequence].get("label"):
                name = data["sequences"][sequence]["label"]
            else:
                name = str(sequence)
            label = Gtk.Label(label=name)
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
        label = Gtk.Label(label="Groups:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_groups_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _palettes(self, actions: list, box: Gtk.Box) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Palettes:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_palettes_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _effects(self, actions: list, box: Gtk.Box) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Effects:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_effects_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _faders(self, actions: list, box: Gtk.Box) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Faders:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_faders_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _independents(self, actions: list, box: Gtk.Box) -> None:
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="Independents:")
        combo = Gtk.ComboBoxText()
        combo.connect("changed", self._on_independents_changed)
        for action in actions:
            combo.append_text(action)
        combo.set_active(0)
        hbox.pack_start(label, True, True, 0)
        hbox.add(combo)
        box.add(hbox)

    def _on_curves_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["curves"] = Action.REPLACE
        elif active == 1:
            self.actions["curves"] = Action.MERGE
        elif active == 2:
            self.actions["curves"] = Action.IGNORE

    def _on_patch_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["patch"] = Action.REPLACE
        elif active == 1:
            self.actions["patch"] = Action.MERGE
        elif active == 2:
            self.actions["patch"] = Action.IGNORE

    def _on_seq_changed(self, widget: Gtk.ComboBoxText, sequence: int) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["sequences"][sequence] = Action.REPLACE
        elif active == 1:
            self.actions["sequences"][sequence] = Action.MERGE
        elif active == 2:
            self.actions["sequences"][sequence] = Action.IGNORE

    def _on_groups_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["groups"] = Action.REPLACE
        elif active == 1:
            self.actions["groups"] = Action.MERGE
        elif active == 2:
            self.actions["groups"] = Action.IGNORE

    def _on_palettes_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["palettes"] = Action.REPLACE
        elif active == 1:
            self.actions["palettes"] = Action.MERGE
        elif active == 2:
            self.actions["palettes"] = Action.IGNORE

    def _on_effects_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["effects"] = Action.REPLACE
        elif active == 1:
            self.actions["effects"] = Action.MERGE
        elif active == 2:
            self.actions["effects"] = Action.IGNORE

    def _on_faders_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["faders"] = Action.REPLACE
        elif active == 1:
            self.actions["faders"] = Action.MERGE
        elif active == 2:
            self.actions["faders"] = Action.IGNORE

    def _on_independents_changed(self, widget: Gtk.ComboBoxText) -> None:
        active = widget.get_active()
        if active == 0:
            self.actions["independents"] = Action.REPLACE
        elif active == 1:
            self.actions["independents"] = Action.MERGE
        elif active == 2:
            self.actions["independents"] = Action.IGNORE
