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
"""GTK3 dialogs for adding a LightingDevice and performing Fixture Exchange."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from gi.repository import Gtk

from olc.define import MAX_CHANNELS

if TYPE_CHECKING:
    from olc.devices.fixture import FixtureDefinition, FixtureLibrary
    from olc.patch import PatchManager


# pylint: disable=too-many-instance-attributes
class AddDeviceDialog(Gtk.Dialog):
    """Interactive dialog to patch a new LightingDevice with collision preview."""

    def __init__(
        self,
        parent: Optional[Gtk.Window],
        patch: PatchManager,
        library: FixtureLibrary,
        default_device_id: int = 1,
    ) -> None:
        super().__init__(
            title="Add Lighting Device",
            transient_for=parent,
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        self.patch = patch
        self.library = library

        box = self.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8, margin=12)
        box.add(grid)

        # Device ID
        grid.attach(Gtk.Label(label="Device ID:", xalign=0), 0, 0, 1, 1)
        self.id_spin = Gtk.SpinButton.new_with_range(1, MAX_CHANNELS, 1)
        self.id_spin.set_value(default_device_id)
        grid.attach(self.id_spin, 1, 0, 1, 1)

        # Label
        grid.attach(Gtk.Label(label="Label:", xalign=0), 0, 1, 1, 1)
        self.label_entry = Gtk.Entry()
        self.label_entry.set_placeholder_text("Optional custom name")
        grid.attach(self.label_entry, 1, 1, 1, 1)

        # Fixture profile
        grid.attach(Gtk.Label(label="Fixture Profile:", xalign=0), 0, 2, 1, 1)
        self.profile_combo = Gtk.ComboBoxText()
        for key in self.library.keys():
            self.profile_combo.append_text(key)
        self.profile_combo.set_active(0)
        self.profile_combo.connect("changed", self._on_profile_changed)
        grid.attach(self.profile_combo, 1, 2, 1, 1)

        # DMX Mode
        grid.attach(Gtk.Label(label="DMX Mode:", xalign=0), 0, 3, 1, 1)
        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.connect("changed", self._update_collision_preview)
        grid.attach(self.mode_combo, 1, 3, 1, 1)

        # Universe
        grid.attach(Gtk.Label(label="Universe:", xalign=0), 0, 4, 1, 1)
        max_univ = max(self.patch.universes) if self.patch.universes else 4
        self.universe_spin = Gtk.SpinButton.new_with_range(1, max(16, max_univ), 1)
        self.universe_spin.set_value(
            self.patch.universes[0] if self.patch.universes else 1
        )
        self.universe_spin.connect("value-changed", self._update_collision_preview)
        grid.attach(self.universe_spin, 1, 4, 1, 1)

        # Address
        grid.attach(Gtk.Label(label="DMX Address:", xalign=0), 0, 5, 1, 1)
        self.address_spin = Gtk.SpinButton.new_with_range(1, 512, 1)
        self.address_spin.set_value(1)
        self.address_spin.connect("value-changed", self._update_collision_preview)
        grid.attach(self.address_spin, 1, 5, 1, 1)

        # Curve ID
        grid.attach(Gtk.Label(label="Curve ID (0=Linear):", xalign=0), 0, 6, 1, 1)
        self.curve_spin = Gtk.SpinButton.new_with_range(0, 99, 1)
        self.curve_spin.set_value(0)
        grid.attach(self.curve_spin, 1, 6, 1, 1)

        # Force overwrite
        self.force_check = Gtk.CheckButton(label="Force overwrite on address collision")
        self.force_check.connect("toggled", self._update_collision_preview)
        grid.attach(self.force_check, 0, 7, 2, 1)

        # Collision status label
        self.collision_label = Gtk.Label(label="", xalign=0)
        grid.attach(self.collision_label, 0, 8, 2, 1)

        self.id_spin.connect("value-changed", self._update_collision_preview)
        self._populate_modes()
        self._update_collision_preview()
        self.show_all()

    def _get_selected_definition(self) -> Optional[FixtureDefinition]:
        key = self.profile_combo.get_active_text()
        if not key:
            return None
        return self.library.get_by_key(key)

    def _populate_modes(self) -> None:
        self.mode_combo.remove_all()
        fdef = self._get_selected_definition()
        if fdef is not None:
            for mode in fdef.dmx_modes:
                self.mode_combo.append_text(mode.name)
            self.mode_combo.set_active(0)

    def _on_profile_changed(self, _widget: Gtk.Widget) -> None:
        self._populate_modes()
        self._update_collision_preview()

    def _update_collision_preview(self, *_args: object) -> None:
        fdef = self._get_selected_definition()
        if fdef is None:
            self.collision_label.set_text("")
            return
        mode_name = self.mode_combo.get_active_text()
        mode = fdef.get_mode(mode_name) if mode_name else fdef.default_mode()
        footprint = mode.footprint()
        dev_id = int(self.id_spin.get_value())
        univ = int(self.universe_spin.get_value())
        addr = int(self.address_spin.get_value())

        collisions = self.patch.check_collision(
            univ, addr, footprint, ignore_device_id=dev_id
        )
        if collisions:
            c_univ, c_addr, occ_id = collisions[0]
            self.collision_label.set_markup(
                f"<span foreground='#FF5555'>Collision at U{c_univ}:{c_addr} "
                f"(occupied by Device #{occ_id})</span>"
            )
        else:
            self.collision_label.set_markup(
                f"<span foreground='#55CC55'>Address range U{univ}:{addr}-"
                f"{addr + footprint - 1} is free ({footprint} ch)</span>"
            )
        self.set_response_sensitive(
            Gtk.ResponseType.OK, not collisions or self.force_check.get_active()
        )

    def get_values(self) -> dict[str, Any]:
        """Return user-configured device patch parameters."""
        return {
            "device_id": int(self.id_spin.get_value()),
            "label": self.label_entry.get_text().strip(),
            "fixture_key": self.profile_combo.get_active_text() or "Generic:Dimmer",
            "mode_name": self.mode_combo.get_active_text(),
            "universe": int(self.universe_spin.get_value()),
            "address": int(self.address_spin.get_value()),
            "curve_id": int(self.curve_spin.get_value()),
            "force": self.force_check.get_active(),
        }


# pylint: disable=too-many-instance-attributes
class FixtureExchangeDialog(Gtk.Dialog):
    """Interactive dialog to replace an existing device's fixture profile."""

    def __init__(
        self,
        parent: Optional[Gtk.Window],
        patch: PatchManager,
        library: FixtureLibrary,
        device_id: int,
    ) -> None:
        super().__init__(
            title=f"Fixture Exchange — Device #{device_id}",
            transient_for=parent,
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        self.patch = patch
        self.library = library
        self.device_id = device_id

        existing = self.patch.devices.get(device_id)
        default_univ = existing.universe if existing else 1
        default_addr = existing.address if existing else 1

        box = self.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8, margin=12)
        box.add(grid)

        info_text = (
            f"Exchanging profile for #{device_id} "
            f"({existing.label if existing else 'Unknown'})"
        )
        grid.attach(Gtk.Label(label=info_text, xalign=0), 0, 0, 2, 1)

        # New Fixture Profile
        grid.attach(Gtk.Label(label="New Profile:", xalign=0), 0, 1, 1, 1)
        self.profile_combo = Gtk.ComboBoxText()
        for key in self.library.keys():
            self.profile_combo.append_text(key)
        self.profile_combo.set_active(0)
        self.profile_combo.connect("changed", self._on_profile_changed)
        grid.attach(self.profile_combo, 1, 1, 1, 1)

        # New DMX Mode
        grid.attach(Gtk.Label(label="New DMX Mode:", xalign=0), 0, 2, 1, 1)
        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.connect("changed", self._update_collision_preview)
        grid.attach(self.mode_combo, 1, 2, 1, 1)

        # Universe
        grid.attach(Gtk.Label(label="Universe:", xalign=0), 0, 3, 1, 1)
        max_univ = max(self.patch.universes) if self.patch.universes else 4
        self.universe_spin = Gtk.SpinButton.new_with_range(1, max(16, max_univ), 1)
        self.universe_spin.set_value(default_univ)
        self.universe_spin.connect("value-changed", self._update_collision_preview)
        grid.attach(self.universe_spin, 1, 3, 1, 1)

        # Address
        grid.attach(Gtk.Label(label="DMX Address:", xalign=0), 0, 4, 1, 1)
        self.address_spin = Gtk.SpinButton.new_with_range(1, 512, 1)
        self.address_spin.set_value(default_addr)
        self.address_spin.connect("value-changed", self._update_collision_preview)
        grid.attach(self.address_spin, 1, 4, 1, 1)

        # Force overwrite
        self.force_check = Gtk.CheckButton(label="Force overwrite on address collision")
        self.force_check.connect("toggled", self._update_collision_preview)
        grid.attach(self.force_check, 0, 5, 2, 1)

        # Collision preview
        self.collision_label = Gtk.Label(label="", xalign=0)
        grid.attach(self.collision_label, 0, 6, 2, 1)

        # Clamping warning preview
        self.clamping_warning_label = Gtk.Label(label="", xalign=0)
        grid.attach(self.clamping_warning_label, 0, 7, 2, 1)

        self._populate_modes()
        self._update_collision_preview()
        self.show_all()

    def _get_selected_definition(self) -> Optional[FixtureDefinition]:
        key = self.profile_combo.get_active_text()
        if not key:
            return None
        return self.library.get_by_key(key)

    def _populate_modes(self) -> None:
        self.mode_combo.remove_all()
        fdef = self._get_selected_definition()
        if fdef is not None:
            for mode in fdef.dmx_modes:
                self.mode_combo.append_text(mode.name)
            self.mode_combo.set_active(0)

    def _on_profile_changed(self, _widget: Gtk.Widget) -> None:
        self._populate_modes()
        self._update_collision_preview()

    def _update_collision_preview(self, *_args: object) -> None:
        fdef = self._get_selected_definition()
        if fdef is None:
            self.collision_label.set_text("")
            return
        mode_name = self.mode_combo.get_active_text()
        mode = fdef.get_mode(mode_name) if mode_name else fdef.default_mode()
        footprint = mode.footprint()
        univ = int(self.universe_spin.get_value())
        addr = int(self.address_spin.get_value())

        collisions = self.patch.check_collision(
            univ, addr, footprint, ignore_device_id=self.device_id
        )
        if collisions:
            c_univ, c_addr, occ_id = collisions[0]
            self.collision_label.set_markup(
                f"<span foreground='#FF5555'>Collision at U{c_univ}:{c_addr} "
                f"(occupied by Device #{occ_id})</span>"
            )
        else:
            self.collision_label.set_markup(
                f"<span foreground='#55CC55'>Address range U{univ}:{addr}-"
                f"{addr + footprint - 1} is free ({footprint} ch)</span>"
            )

        # Clamping preview
        if hasattr(self.patch, "check_clamped_cue_parameters"):
            clamp_warnings = self.patch.check_clamped_cue_parameters(
                self.device_id, fdef, mode.name
            )
            if clamp_warnings:
                count = len(clamp_warnings)
                self.clamping_warning_label.set_markup(
                    f"<span foreground='#FF8000'>⚠ {count} cue value(s) "
                    f"exceed physical bounds and will be clamped</span>"
                )
            else:
                self.clamping_warning_label.set_markup(
                    "<span foreground='#888888'>No cue physical bounds exceeded</span>"
                )
        else:
            self.clamping_warning_label.set_text("")

        self.set_response_sensitive(
            Gtk.ResponseType.OK, not collisions or self.force_check.get_active()
        )

    def get_values(self) -> dict[str, Any]:
        """Return user-configured fixture exchange parameters."""
        return {
            "device_id": self.device_id,
            "fixture_key": self.profile_combo.get_active_text() or "Generic:Dimmer",
            "mode_name": self.mode_combo.get_active_text(),
            "universe": int(self.universe_spin.get_value()),
            "address": int(self.address_spin.get_value()),
            "force": self.force_check.get_active(),
        }
