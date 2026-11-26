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
        if data.get("gdtf_matches"):
            self._gdtf_matches(box, data)
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

    def _gdtf_matches(self, box: Gtk.Box, data: dict) -> None:
        matches: dict[int, dict[str, typing.Any]] = data.get("gdtf_matches") or {}
        if not matches:
            return
        box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        header_check = Gtk.CheckButton(label=_("Use compatible local GDTF profiles"))
        header_check.set_active(bool(self.actions.get("use_gdtf_matches", True)))
        box.add(header_check)

        rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        combos: list[Gtk.ComboBoxText] = []
        overrides = self.actions.setdefault("gdtf_overrides", {})

        for pers_id in sorted(matches):
            info = matches[pers_id]
            status = str(info.get("status", "no_candidate"))
            eos_label = (
                f"{info.get('eos_manufacturer', '')} "
                f"{info.get('eos_model', '')} ({info.get('eos_footprint', 0)}ch)"
            ).strip()
            g_mfr = info.get("gdtf_manufacturer", "")
            g_mod = info.get("gdtf_model", "")
            g_mode = info.get("gdtf_mode", "")
            gobos = int(info.get("gobo_count", 0))

            if status == "compatible":
                badge = f"✓ {g_mfr} {g_mod} [{g_mode}] ({gobos} gobos)"
            elif status == "warning":
                badge = f"⚠ {g_mfr} {g_mod} [{g_mode}] ({gobos} gobos)"
            elif status == "incompatible":
                badge = f"✗ {_('Incompatible')}: {g_mfr} {g_mod}"
            else:
                badge = f"– {_('No local GDTF')}"

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_eos = Gtk.Label(label=eos_label)
            lbl_eos.set_xalign(0.0)
            lbl_status = Gtk.Label(label=badge)
            lbl_status.set_xalign(0.0)

            issues = info.get("issues") or []
            if issues:
                tip = "\n".join(
                    f"[{iss.get('severity', 'info')}] {iss.get('reason', '')}"
                    for iss in issues[:8]
                )
                row.set_tooltip_text(tip)

            combo = Gtk.ComboBoxText()
            combo.append_text("GDTF")
            combo.append_text("Eos")
            is_usable = status in ("compatible", "warning")
            if is_usable:
                cur_ov = overrides.get(pers_id, "auto")
                combo.set_active(1 if cur_ov == "eos" else 0)
            else:
                combo.set_active(1)
            combo.set_sensitive(is_usable and header_check.get_active())
            combo.connect("changed", self._on_gdtf_override_changed, pers_id)
            if is_usable:
                combos.append(combo)

            row.pack_start(lbl_eos, True, True, 0)
            row.pack_start(lbl_status, True, True, 0)
            row.pack_end(combo, False, False, 0)
            rows_box.add(row)

        header_check.connect("toggled", self._on_use_gdtf_toggled, combos)

        if len(matches) > 4:
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_min_content_height(130)
            scrolled.add(rows_box)
            box.add(scrolled)
        else:
            box.add(rows_box)

    def _on_use_gdtf_toggled(
        self, widget: Gtk.CheckButton, combos: list[Gtk.ComboBoxText]
    ) -> None:
        active = widget.get_active()
        self.actions["use_gdtf_matches"] = active
        for combo in combos:
            combo.set_sensitive(active)

    def _on_gdtf_override_changed(self, widget: Gtk.ComboBoxText, pers_id: int) -> None:
        self.actions.setdefault("gdtf_overrides", {})[pers_id] = (
            "eos" if widget.get_active() == 1 else "auto"
        )
