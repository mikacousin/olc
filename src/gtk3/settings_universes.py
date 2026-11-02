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
"""DMX Universes settings UI tab and frame builders for the Settings window."""

from __future__ import annotations

import os
import typing
from gettext import gettext as _
from typing import Any

import serial.tools.list_ports
from gi.repository import GObject, Gtk

from olc.core.backends.enttec import resolve_port
from olc.core.universe_config import Protocol
from olc.define import DEFAULT_UNIVERSES

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


class UniversesSettingsMixin:
    """Mixin implementing DMX universes configuration UI for SettingsTab."""

    app: Application
    window: Gtk.Window | None
    universe_widgets: dict[int, dict[str, Any]]
    universe_frames: dict[int, Gtk.Frame]
    delete_universe_buttons: dict[int, Gtk.Button]
    universes_box: Gtk.Box | None
    _updating_settings: bool

    def _get_serial_ports(self, current_port: str) -> list[str]:
        """Scan system for available serial ports and ensure current_port is present."""
        serial_ports = ["Auto-detect"]
        try:
            for p in serial.tools.list_ports.comports():
                if p.vid == 0x0403 and p.pid == 0x6001:
                    desc = (p.description or "").upper()
                    prod = (p.product or "").upper()
                    if (
                        "MK2" in desc
                        or "MK2" in prod
                        or "MK II" in desc
                        or "MK II" in prod
                    ):
                        serial_ports.append(f"{p.device} (DMX USB PRO MK2)")
                    else:
                        serial_ports.append(f"{p.device} (DMX USB PRO)")
                else:
                    serial_ports.append(p.device)
        except Exception:  # pylint: disable=broad-exception-caught
            serial_ports.extend(["/dev/ttyUSB0", "/dev/ttyUSB1"])

        if current_port != "Auto-detect":
            found = False
            for sp in serial_ports:
                if sp == current_port or sp.startswith(f"{current_port} "):
                    found = True
                    break
            if not found:
                serial_ports.append(current_port)

        return serial_ports

    def update_universe_ui(self, universe: int) -> None:
        """Update widgets for given universe from core/engine state."""
        if universe not in self.universe_widgets:
            return
        engine = getattr(self.app, "engine", None)
        if engine is None or universe not in engine.universe_map:
            return
        config = engine.universe_map[universe]
        widgets = self.universe_widgets[universe]

        self._updating_settings = True
        try:
            widgets["artnet_check"].set_active(Protocol.ARTNET in config.protocols)
            widgets["net_spin"].set_value(config.artnet.net)
            widgets["sub_spin"].set_value(config.artnet.sub)
            widgets["sync_switch"].set_active(config.artnet.sync_active)

            widgets["sacn_check"].set_active(Protocol.SACN in config.protocols)
            widgets["prio_spin"].set_value(config.sacn.priority)
            widgets["sacn_sync_spin"].set_value(config.sacn.sync_address)

            widgets["dmx_usb_pro_check"].set_active(
                Protocol.DMX_USB_PRO in config.protocols
            )

            current_port = config.dmx_usb_pro.port
            model = widgets["port_combo"].get_model()
            active_idx = 0
            if model:
                for idx, row in enumerate(model):
                    sp = row[0]
                    if sp == current_port or sp.startswith(f"{current_port} "):
                        active_idx = idx
                        break
            widgets["port_combo"].set_active(active_idx)

            widgets["port_index_combo"].set_active_id(
                str(config.dmx_usb_pro.port_index)
            )
            widgets["model_combo"].set_active_id(config.dmx_usb_pro.model)
        finally:
            self._updating_settings = False

    def _get_active_universes(self) -> list[int]:
        """Get list of active universe IDs."""
        core = getattr(self.app, "core", None)
        lightshow = getattr(core, "lightshow", None)
        patch = getattr(lightshow, "patch", None)
        if patch is not None and hasattr(patch, "universes"):
            return list(patch.universes)
        engine = getattr(self.app, "engine", None)
        if engine is not None and hasattr(engine, "universe_map"):
            umap = engine.universe_map
            if hasattr(umap, "keys"):
                return list(umap.keys())
            return [univ.universe_id for univ in umap]
        return list(DEFAULT_UNIVERSES)

    def _update_delete_buttons_sensitivity(self) -> None:
        """Update sensitivity of delete universe buttons (disabled if only 1)."""
        can_delete = len(self.universe_frames) > 1
        for btn in self.delete_universe_buttons.values():
            btn.set_sensitive(can_delete)

    def _on_add_universe_clicked(self, _widget: Gtk.Widget) -> None:
        """Handle Add Universe button click."""
        active = set(self._get_active_universes())
        next_univ = 1
        while next_univ in active:
            next_univ += 1

        dialog = Gtk.Dialog(
            title=_("Add Universe"),
            transient_for=(
                self.window if isinstance(self.window, Gtk.Window) else None
            ),
            modal=True,
        )
        dialog.add_buttons(
            _("Cancel"),
            Gtk.ResponseType.CANCEL,
            _("Add"),
            Gtk.ResponseType.OK,
        )

        content = dialog.get_content_area()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(15)
        box.set_margin_bottom(15)

        label = Gtk.Label(label=_("Universe Number:"))
        box.pack_start(label, False, False, 0)

        spin_adj = Gtk.Adjustment(
            value=next_univ,
            lower=1,
            upper=63999,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        spin = Gtk.SpinButton()
        spin.set_adjustment(spin_adj)
        box.pack_start(spin, False, False, 0)
        content.add(box)

        btn_ok = dialog.get_widget_for_response(Gtk.ResponseType.OK)

        def _on_spin_changed(s: Gtk.SpinButton) -> None:
            val = s.get_value_as_int()
            if btn_ok is not None:
                btn_ok.set_sensitive(val not in active and 1 <= val <= 63999)

        spin.connect("value-changed", _on_spin_changed)
        _on_spin_changed(spin)

        dialog.show_all()
        response = dialog.run()
        chosen = spin.get_value_as_int()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and chosen not in active:
            if self.app.core is not None and hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute("universe.add", universe=chosen)
            else:
                engine = getattr(self.app, "engine", None)
                if engine is not None:
                    engine.add_universe(chosen)
                self.add_universe_ui(chosen)

    def _on_remove_universe_clicked(self, _widget: Gtk.Widget, universe: int) -> None:
        """Handle Remove Universe button click."""
        active = self._get_active_universes()
        if len(active) <= 1:
            return

        patch = getattr(getattr(self.app, "core", None), "lightshow", None)
        patched_count = 0
        if patch is not None and hasattr(patch, "patch"):
            patched_outputs = patch.patch.outputs.get(universe, {})
            patched_count = len(patched_outputs)

        if patched_count > 0:
            dialog = Gtk.MessageDialog(
                transient_for=(
                    self.window if isinstance(self.window, Gtk.Window) else None
                ),
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text=_("Delete Universe {universe}").format(universe=universe),
            )
            dialog.format_secondary_text(
                _(
                    "Universe {universe} has {count} patched output(s).\n"
                    "Deleting it will unpatch these outputs. Continue?"
                ).format(universe=universe, count=patched_count)
            )
            dialog.show_all()
            response = dialog.run()
            dialog.destroy()
            if response != Gtk.ResponseType.OK:
                return

        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("universe.remove", universe=universe)
        else:
            engine = getattr(self.app, "engine", None)
            if engine is not None:
                engine.remove_universe(universe)
            self.remove_universe_ui(universe)

    def add_universe_ui(self, universe: int) -> None:
        """Add universe frame to UI."""
        if universe in self.universe_frames or self.universes_box is None:
            return
        existing_univs = sorted(self.universe_frames.keys())
        pos = 0
        for u in existing_univs:
            if u < universe:
                pos += 1
            else:
                break
        frame = self._create_universe_frame(universe)
        self.universe_frames[universe] = frame
        self.universes_box.pack_start(frame, False, False, 0)
        self.universes_box.reorder_child(frame, pos)
        frame.show_all()
        self._update_delete_buttons_sensitivity()

    def remove_universe_ui(self, universe: int) -> None:
        """Remove universe frame from UI."""
        if universe not in self.universe_frames or self.universes_box is None:
            return
        frame = self.universe_frames.pop(universe)
        self.universe_widgets.pop(universe, None)
        self.delete_universe_buttons.pop(universe, None)
        self.universes_box.remove(frame)
        frame.destroy()
        self._update_delete_buttons_sensitivity()

    # pylint: disable=too-many-locals,too-many-statements
    def _create_universe_frame(self, u: int) -> Gtk.Frame:
        """Create configuration frame widget for a specific universe."""
        engine = getattr(self.app, "engine", None)
        frame = Gtk.Frame()

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_label = Gtk.Label(label=_("Universe {universe}").format(universe=u))
        header_box.pack_start(header_label, False, False, 0)

        del_btn = Gtk.Button.new_from_icon_name(
            "edit-delete-symbolic", Gtk.IconSize.BUTTON
        )
        del_btn.set_relief(Gtk.ReliefStyle.NONE)
        del_btn.set_tooltip_text(_("Delete Universe {universe}").format(universe=u))
        del_btn.connect("clicked", self._on_remove_universe_clicked, u)
        header_box.pack_start(del_btn, False, False, 0)
        header_box.show_all()
        frame.set_label_widget(header_box)
        self.delete_universe_buttons[u] = del_btn

        frame_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        frame_box.set_margin_start(10)
        frame_box.set_margin_end(10)
        frame_box.set_margin_top(10)
        frame_box.set_margin_bottom(10)
        frame.add(frame_box)

        umap = getattr(engine, "universe_map", None)
        config = None
        if umap is not None:
            if hasattr(umap, "get"):
                config = umap.get(u)
            elif u in umap:
                config = umap[u]

        # --- Column 1: Art-Net ---
        artnet_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        artnet_box.set_hexpand(True)
        frame_box.pack_start(artnet_box, True, True, 0)

        artnet_check = Gtk.CheckButton(label=_("Enable Art-Net"))
        artnet_box.pack_start(artnet_check, False, False, 0)

        artnet_params = Gtk.Grid()
        artnet_params.set_column_spacing(10)
        artnet_params.set_row_spacing(6)
        artnet_box.pack_start(artnet_params, False, False, 0)

        # Net
        net_label = Gtk.Label(label=_("Net:"))
        net_label.set_halign(Gtk.Align.START)
        artnet_params.attach(net_label, 0, 0, 1, 1)
        net_adj = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=127,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        net_spin = Gtk.SpinButton()
        net_spin.set_adjustment(net_adj)
        artnet_params.attach(net_spin, 1, 0, 1, 1)

        # Sub
        sub_label = Gtk.Label(label=_("Sub:"))
        sub_label.set_halign(Gtk.Align.START)
        artnet_params.attach(sub_label, 2, 0, 1, 1)
        sub_adj = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=15,
            step_increment=1,
            page_increment=5,
            page_size=0,
        )
        sub_spin = Gtk.SpinButton()
        sub_spin.set_adjustment(sub_adj)
        artnet_params.attach(sub_spin, 3, 0, 1, 1)

        # Sync
        sync_label = Gtk.Label(label=_("ArtSync:"))
        sync_label.set_halign(Gtk.Align.START)
        artnet_params.attach(sync_label, 0, 1, 1, 1)
        sync_switch = Gtk.Switch()
        sync_switch.set_halign(Gtk.Align.START)
        artnet_params.attach(sync_switch, 1, 1, 1, 1)

        # --- Column 2: sACN ---
        sacn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sacn_box.set_hexpand(True)
        frame_box.pack_start(sacn_box, True, True, 0)

        sacn_check = Gtk.CheckButton(label=_("Enable sACN"))
        sacn_box.pack_start(sacn_check, False, False, 0)

        sacn_params = Gtk.Grid()
        sacn_params.set_column_spacing(10)
        sacn_params.set_row_spacing(6)
        sacn_box.pack_start(sacn_params, False, False, 0)

        # Priority
        prio_label = Gtk.Label(label=_("Priority:"))
        prio_label.set_halign(Gtk.Align.START)
        sacn_params.attach(prio_label, 0, 0, 1, 1)
        prio_adj = Gtk.Adjustment(
            value=100,
            lower=1,
            upper=200,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        prio_spin = Gtk.SpinButton()
        prio_spin.set_adjustment(prio_adj)
        sacn_params.attach(prio_spin, 1, 0, 1, 1)

        # Sync Address
        sacn_sync_label = Gtk.Label(label=_("Sync Address:"))
        sacn_sync_label.set_halign(Gtk.Align.START)
        sacn_params.attach(sacn_sync_label, 0, 1, 1, 1)
        sacn_sync_adj = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=63999,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        sacn_sync_spin = Gtk.SpinButton()
        sacn_sync_spin.set_adjustment(sacn_sync_adj)
        sacn_params.attach(sacn_sync_spin, 1, 1, 1, 1)

        # --- Column 3: DMX USB PRO ---
        dmx_usb_pro_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dmx_usb_pro_box.set_hexpand(True)
        frame_box.pack_start(dmx_usb_pro_box, True, True, 0)

        dmx_usb_pro_check = Gtk.CheckButton(label=_("Enable DMX USB Pro"))
        dmx_usb_pro_box.pack_start(dmx_usb_pro_check, False, False, 0)

        dmx_usb_pro_params = Gtk.Grid()
        dmx_usb_pro_params.set_column_spacing(10)
        dmx_usb_pro_params.set_row_spacing(6)
        dmx_usb_pro_box.pack_start(dmx_usb_pro_params, False, False, 0)

        # Port Label
        port_label = Gtk.Label(label=_("Port:"))
        port_label.set_halign(Gtk.Align.START)
        dmx_usb_pro_params.attach(port_label, 0, 0, 1, 1)

        # Port Combo Box
        port_combo = Gtk.ComboBoxText()
        port_combo.set_hexpand(True)
        dmx_usb_pro_params.attach(port_combo, 1, 0, 1, 1)

        # Populate combo box with ports using helper
        current_port = config.dmx_usb_pro.port if config else "Auto-detect"
        serial_ports = self._get_serial_ports(current_port)

        for sp in serial_ports:
            port_combo.append_text(sp)

        # Select active item
        active_idx = 0
        for idx, sp in enumerate(serial_ports):
            if sp == current_port or sp.startswith(f"{current_port} "):
                active_idx = idx
                break
        port_combo.set_active(active_idx)

        # Port Index Label
        port_index_label = Gtk.Label(label=_("Output Port:"))
        port_index_label.set_halign(Gtk.Align.START)
        dmx_usb_pro_params.attach(port_index_label, 0, 1, 1, 1)

        # Port Index Combo Box
        port_index_combo = Gtk.ComboBoxText()
        port_index_combo.set_hexpand(True)
        port_index_combo.append("1", _("Port 1 (DMX 1)"))
        port_index_combo.append("2", _("Port 2 (DMX 2 / Mk2)"))
        dmx_usb_pro_params.attach(port_index_combo, 1, 1, 1, 1)

        current_port_index = str(config.dmx_usb_pro.port_index) if config else "1"
        port_index_combo.set_active_id(current_port_index)

        # Model Label
        model_label = Gtk.Label(label=_("Model:"))
        model_label.set_halign(Gtk.Align.START)
        dmx_usb_pro_params.attach(model_label, 0, 2, 1, 1)

        # Model Combo Box
        model_combo = Gtk.ComboBoxText()
        model_combo.set_hexpand(True)
        model_combo.append("Auto-detect", _("Auto-detect"))
        model_combo.append("Pro V1", _("Force Pro V1 (Standard)"))
        model_combo.append("Pro Mk2", _("Force Pro Mk2"))
        dmx_usb_pro_params.attach(model_combo, 1, 2, 1, 1)

        current_model = config.dmx_usb_pro.model if config else "Auto-detect"
        model_combo.set_active_id(current_model)

        # Store widgets for conflict management and callbacks
        self.universe_widgets[u] = {
            "artnet_check": artnet_check,
            "net_spin": net_spin,
            "sub_spin": sub_spin,
            "sync_switch": sync_switch,
            "sacn_check": sacn_check,
            "prio_spin": prio_spin,
            "sacn_sync_spin": sacn_sync_spin,
            "dmx_usb_pro_check": dmx_usb_pro_check,
            "port_combo": port_combo,
            "port_index_combo": port_index_combo,
            "model_combo": model_combo,
        }

        # Populate initial values
        if config is not None:
            artnet_check.set_active(Protocol.ARTNET in config.protocols)
            net_spin.set_value(config.artnet.net)
            sub_spin.set_value(config.artnet.sub)
            sync_switch.set_active(config.artnet.sync_active)

            sacn_check.set_active(Protocol.SACN in config.protocols)
            prio_spin.set_value(config.sacn.priority)
            sacn_sync_spin.set_value(config.sacn.sync_address)

            dmx_usb_pro_check.set_active(Protocol.DMX_USB_PRO in config.protocols)

        # Bind sensitiveness
        artnet_check.bind_property(
            "active", net_spin, "sensitive", GObject.BindingFlags.SYNC_CREATE
        )
        artnet_check.bind_property(
            "active", sub_spin, "sensitive", GObject.BindingFlags.SYNC_CREATE
        )
        artnet_check.bind_property(
            "active", sync_switch, "sensitive", GObject.BindingFlags.SYNC_CREATE
        )

        sacn_check.bind_property(
            "active", prio_spin, "sensitive", GObject.BindingFlags.SYNC_CREATE
        )
        sacn_check.bind_property(
            "active",
            sacn_sync_spin,
            "sensitive",
            GObject.BindingFlags.SYNC_CREATE,
        )

        dmx_usb_pro_check.bind_property(
            "active", port_combo, "sensitive", GObject.BindingFlags.SYNC_CREATE
        )
        dmx_usb_pro_check.bind_property(
            "active",
            port_index_combo,
            "sensitive",
            GObject.BindingFlags.SYNC_CREATE,
        )
        dmx_usb_pro_check.bind_property(
            "active", model_combo, "sensitive", GObject.BindingFlags.SYNC_CREATE
        )

        # Bind callbacks
        args = (u,)
        cb = self._on_universe_settings_changed
        scb = self._on_universe_switch_changed
        artnet_check.connect("toggled", cb, *args)
        net_spin.connect("value-changed", cb, *args)
        sub_spin.connect("value-changed", cb, *args)
        sync_switch.connect("state-set", scb, *args)
        sacn_check.connect("toggled", cb, *args)
        prio_spin.connect("value-changed", cb, *args)
        sacn_sync_spin.connect("value-changed", cb, *args)
        dmx_usb_pro_check.connect("toggled", cb, *args)
        port_combo.connect("changed", cb, *args)
        port_index_combo.connect("changed", cb, *args)
        model_combo.connect("changed", cb, *args)

        self.universe_frames[u] = frame
        return frame

    def _create_universes_tab(self) -> Gtk.Box:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(15)
        main_box.set_margin_end(15)
        main_box.set_margin_top(15)
        main_box.set_margin_bottom(15)

        # Top bar with Add Universe button
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_add = Gtk.Button(label=_("Add Universe"))
        btn_add.set_image(
            Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        )
        btn_add.set_always_show_image(True)
        btn_add.connect("clicked", self._on_add_universe_clicked)
        top_bar.pack_start(btn_add, False, False, 0)
        main_box.pack_start(top_bar, False, False, 0)

        # Container for universe frames
        self.universes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.pack_start(self.universes_box, True, True, 0)

        active_universes = self._get_active_universes()
        for u in active_universes:
            frame = self._create_universe_frame(u)
            self.universes_box.pack_start(frame, False, False, 0)

        self._update_delete_buttons_sensitivity()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(main_box)
        scrolled.show_all()

        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        container.pack_start(scrolled, True, True, 0)
        container.show_all()
        return container

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks
    def _on_universe_settings_changed(
        self,
        _widget: Gtk.Widget,
        universe: int,
    ) -> None:
        if getattr(self, "_updating_settings", False):
            return

        engine = getattr(self.app, "engine", None)
        if engine is None:
            return

        self._updating_settings = True
        try:
            config = engine.universe_map[universe]
            widgets = self.universe_widgets[universe]

            # 1. Update protocols
            protocols = set()
            if widgets["artnet_check"].get_active():
                protocols.add(Protocol.ARTNET)
            if widgets["sacn_check"].get_active():
                protocols.add(Protocol.SACN)

            if widgets["dmx_usb_pro_check"].get_active():
                selected_text = widgets["port_combo"].get_active_text() or "Auto-detect"
                port_name = selected_text.split(" ")[0]

                # Smart default port allocation for MK2 if newly activated
                if Protocol.DMX_USB_PRO not in config.protocols:
                    resolved_port = resolve_port(port_name)
                    is_mk2 = False
                    try:
                        resolved_real = os.path.realpath(resolved_port)
                        for p in serial.tools.list_ports.comports():
                            p_real = os.path.realpath(p.device)
                            if p_real == resolved_real or p.device == resolved_port:
                                desc = (p.description or "").upper()
                                prod = (p.product or "").upper()
                                if (
                                    "MK2" in desc
                                    or "MK2" in prod
                                    or "MK II" in desc
                                    or "MK II" in prod
                                ):
                                    is_mk2 = True
                                    break
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                    if is_mk2:
                        # Check which ports are in use by other active universes on
                        # this same resolved device
                        port1_in_use = False
                        port2_in_use = False
                        for other_u, w in self.universe_widgets.items():
                            if other_u == universe:
                                continue
                            if w["dmx_usb_pro_check"].get_active():
                                other_sel = (
                                    w["port_combo"].get_active_text() or "Auto-detect"
                                )
                                other_port_resolved = resolve_port(
                                    other_sel.split(" ")[0]
                                )
                                if other_port_resolved == resolved_port:
                                    other_idx = int(
                                        w["port_index_combo"].get_active_id() or "1"
                                    )
                                    if other_idx == 1:
                                        port1_in_use = True
                                    elif other_idx == 2:
                                        port2_in_use = True
                        # Smart default: use Port 2 only if Port 1 is in use
                        # AND Port 2 is free
                        if port1_in_use and not port2_in_use:
                            widgets["port_index_combo"].set_active_id("2")

                port_idx = int(widgets["port_index_combo"].get_active_id() or "1")

                # Mutual exclusion conflict check
                for other_u, w in self.universe_widgets.items():
                    if other_u == universe:
                        continue
                    other_check = w["dmx_usb_pro_check"]
                    other_combo = w["port_combo"]
                    other_idx_combo = w["port_index_combo"]

                    if other_check.get_active():
                        other_selected = other_combo.get_active_text() or "Auto-detect"
                        other_port_name = other_selected.split(" ")[0]
                        other_port_idx = int(other_idx_combo.get_active_id() or "1")

                        if port_name == other_port_name and port_idx == other_port_idx:
                            # Deactivate other conflict
                            other_check.set_active(False)
                            if (
                                self.app is not None
                                and hasattr(self.app, "core")
                                and self.app.core is not None
                                and hasattr(self.app.core, "action_registry")
                            ):
                                self.app.core.action_registry.execute(
                                    "universe.set_protocol",
                                    universe=other_u,
                                    protocol=Protocol.DMX_USB_PRO,
                                    enabled=False,
                                )

                protocols.add(Protocol.DMX_USB_PRO)

            selected_text = widgets["port_combo"].get_active_text() or "Auto-detect"
            port_name = selected_text.split(" ")[0]
            port_idx = int(widgets["port_index_combo"].get_active_id() or "1")
            model_name = widgets["model_combo"].get_active_id() or "Auto-detect"

            settings_dict: dict[str, typing.Any] = {
                "protocols": protocols,
                "artnet_net": int(widgets["net_spin"].get_value()),
                "artnet_sub": int(widgets["sub_spin"].get_value()),
                "artnet_sync_active": widgets["sync_switch"].get_active(),
                "sacn_priority": int(widgets["prio_spin"].get_value()),
                "sacn_sync_address": int(widgets["sacn_sync_spin"].get_value()),
                "dmx_usb_pro_port": port_name,
                "dmx_usb_pro_port_index": port_idx,
                "dmx_usb_pro_model": model_name,
            }

            if (
                self.app is not None
                and hasattr(self.app, "core")
                and self.app.core is not None
                and hasattr(self.app.core, "action_registry")
            ):
                self.app.core.action_registry.execute(
                    "universe.set_config",
                    universe=universe,
                    settings=settings_dict,
                )
            else:
                config.set_protocols(protocols)
                config.artnet.net = settings_dict["artnet_net"]
                config.artnet.sub = settings_dict["artnet_sub"]
                config.artnet.sync_active = settings_dict["artnet_sync_active"]
                config.sacn.priority = settings_dict["sacn_priority"]
                config.sacn.sync_address = settings_dict["sacn_sync_address"]
                config.dmx_usb_pro.port = settings_dict["dmx_usb_pro_port"]
                config.dmx_usb_pro.port_index = settings_dict["dmx_usb_pro_port_index"]
                config.dmx_usb_pro.model = settings_dict["dmx_usb_pro_model"]
                engine.reload_universe(universe)
                if self.app is not None:
                    self.app.core.lightshow.set_modified()
        finally:
            self._updating_settings = False

    def _on_universe_switch_changed(
        self,
        _widget: Gtk.Switch,
        _state: bool,
        universe: int,
    ) -> bool:
        self._on_universe_settings_changed(_widget, universe)
        return False


__all__ = ["UniversesSettingsMixin"]
