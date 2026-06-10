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

import ipaddress
import socket
import typing
from gettext import gettext as _
from typing import Callable

import serial.tools.list_ports
from gi.repository import Gdk, GLib, GObject, Gtk
from olc.core.backends.osc.delegate import GUIOSCDelegate
from olc.core.universe_config import Protocol

if typing.TYPE_CHECKING:
    from olc.application import Application


# pylint: disable=too-many-instance-attributes
class SettingsTab(Gtk.Box):
    """Settings"""

    def __init__(
        self,
        app: Application,
    ) -> None:
        self.app = app
        self.settings = app.settings
        self.tabs = app.tabs
        self.midi = app.midi
        self.backend = app.backend
        self.window = app.window

        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._last_artnet_state: list[list[str]] | None = None
        self.universe_widgets = {}

        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/settings.ui")
        settings_dialog = typing.cast(Gtk.Notebook, builder.get_object("settings"))

        self._setup_appearance(builder)
        self._setup_osc(builder)

        # MIDI
        self._midi(builder)

        # Art-Net Discovery Page
        self._artnet(builder)

        # Universes Tab
        universes_tab = self._create_universes_tab()
        settings_dialog.append_page(universes_tab, Gtk.Label(label=_("Universes")))

        builder.connect_signals(self)
        self.pack_start(settings_dialog, True, True, 0)

    def _setup_appearance(self, builder: Gtk.Builder) -> None:
        widget1 = typing.cast(Gtk.Switch, builder.get_object("switch_percent"))
        widget1.set_state(self.settings.get_boolean("percent"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget2 = typing.cast(Gtk.SpinButton, builder.get_object("spin_percent_level"))
        widget2.set_adjustment(adjustment)
        widget2.set_value(self.settings.get_int("percent-level"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget3 = typing.cast(Gtk.SpinButton, builder.get_object("spin_default_time"))
        widget3.set_adjustment(adjustment)
        widget3.set_value(self.settings.get_double("default-time"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget4 = typing.cast(Gtk.SpinButton, builder.get_object("spin_go_back_time"))
        widget4.set_adjustment(adjustment)
        widget4.set_value(self.settings.get_double("go-back-time"))

    def _setup_osc(self, builder: Gtk.Builder) -> None:
        widget = typing.cast(Gtk.Switch, builder.get_object("switch_osc"))
        widget.set_state(self.settings.get_boolean("osc"))

        self.entry_client_ip = typing.cast(
            Gtk.Entry, builder.get_object("entry_client_ip")
        )
        self.entry_client_ip.set_text(self.settings.get_string("osc-host"))

        self.spin_client_port = typing.cast(
            Gtk.SpinButton, builder.get_object("spin_client_port")
        )
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_client_port.set_adjustment(adjustment)
        self.spin_client_port.set_value(self.settings.get_int("osc-client-port"))

        self.spin_server_port = typing.cast(
            Gtk.SpinButton, builder.get_object("spin_server_port")
        )
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_server_port.set_adjustment(adjustment)
        self.spin_server_port.set_value(self.settings.get_int("osc-server-port"))

        local_ip = typing.cast(Gtk.Label, builder.get_object("local_ip"))
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        local_ip.set_label(ip_addr)

    def _midi(self, builder: Gtk.Builder) -> None:
        # List of MIDI Controllers
        liststore_modes = Gtk.ListStore(str)
        for item in ["Absolute", "Relative1", "Relative2", "Relative3 (Makie)"]:
            liststore_modes.append([item])
        midi_grid = typing.cast(Gtk.Grid, builder.get_object("midi_io_grid"))
        midi_grid.set_orientation(Gtk.Orientation.VERTICAL)
        self.liststore_midi = Gtk.ListStore(str, bool, str, str)
        treeview = Gtk.TreeView(model=self.liststore_midi)
        self._populate_midi_ports()
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn(_("MIDI Port"), renderer_text, text=0)
        treeview.append_column(column_text)
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_midi_toggle)
        column_toggle = Gtk.TreeViewColumn(_("Active"), renderer_toggle, active=1)
        treeview.append_column(column_toggle)
        renderer_combo = Gtk.CellRendererCombo()
        renderer_combo.set_property("editable", True)
        renderer_combo.set_property("model", liststore_modes)
        renderer_combo.set_property("text-column", 0)
        renderer_combo.set_property("has-entry", False)
        renderer_combo.connect("edited", self.on_combo_change)
        column_combo = Gtk.TreeViewColumn(
            _("Rotary encoder Mode"), renderer_combo, text=2
        )
        treeview.append_column(column_combo)
        midi_grid.add(treeview)

    def _populate_midi_ports(self) -> None:
        default = self.settings.get_strv("midi-ports")
        relative1 = self.settings.get_strv("relative1")
        relative2 = self.settings.get_strv("relative2")
        makies = self.settings.get_strv("makie")
        absolutes = self.settings.get_strv("absolute")
        ports_list = []
        if self.midi is not None and self.midi.ports is not None:
            ports_list = self.midi.ports.mido_ports or []
        for midi_port in sorted(list(set(ports_list))):
            if midi_port in default:
                if midi_port in relative1:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative1", midi_port]
                    )
                elif midi_port in relative2:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative2", midi_port]
                    )
                elif midi_port in makies:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative3 (Makie)", midi_port]
                    )
                elif midi_port in absolutes:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Absolute", midi_port]
                    )
                else:
                    # Default: Mackie mode
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative3 (Makie)", midi_port]
                    )
                    makies.append(midi_port)
                    if midi_port in absolutes:
                        absolutes.remove(midi_port)
                    elif midi_port in relative1:
                        relative1.remove(midi_port)
                    elif midi_port in relative2:
                        relative2.remove(midi_port)
                    self.settings.set_strv("relative1", relative1)
                    self.settings.set_strv("relative2", relative2)
                    self.settings.set_strv("makie", makies)
                    self.settings.set_strv("absolute", absolutes)
            else:
                self.liststore_midi.append(
                    [midi_port.split(":")[0], False, "", midi_port]
                )

    def refresh(self) -> None:
        """Refresh MIDI ports"""
        self.liststore_midi.clear()
        self._populate_midi_ports()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        if self.tabs is not None:
            self.tabs.close("settings")

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Key has been pressed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
        keyname = Gdk.keyval_name(event.keyval)
        if not keyname:
            return False

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        if self.tabs is not None:
            self.tabs.close("settings")

    def on_combo_change(self, _widget: Gtk.Widget, path: str, text: str) -> None:
        """Change rotatives mode

        Args:
            _widget: Widget clicked
            path: Path to combo
            text: New combo's text
        """
        self.liststore_midi[path][2] = text
        relative1 = self.settings.get_strv("relative1")
        relative2 = self.settings.get_strv("relative2")
        makies = self.settings.get_strv("makie")
        absolutes = self.settings.get_strv("absolute")
        if self.liststore_midi[path][3] in relative1:
            relative1.remove(self.liststore_midi[path][3])
        elif self.liststore_midi[path][3] in relative2:
            relative2.remove(self.liststore_midi[path][3])
        elif self.liststore_midi[path][3] in absolutes:
            absolutes.remove(self.liststore_midi[path][3])
        elif self.liststore_midi[path][3] in makies:
            makies.remove(self.liststore_midi[path][3])
        if text == "Relative1":
            relative1.append(self.liststore_midi[path][3])
        elif text == "Relative2":
            relative2.append(self.liststore_midi[path][3])
        elif text == "Relative3 (Makie)":
            makies.append(self.liststore_midi[path][3])
        elif text == "Absolute":
            absolutes.append(self.liststore_midi[path][3])
        self.settings.set_strv("relative1", relative1)
        self.settings.set_strv("relative2", relative2)
        self.settings.set_strv("makie", makies)
        self.settings.set_strv("absolute", absolutes)

    def on_midi_toggle(self, _widget: Gtk.Widget, path: str) -> None:
        """Active / Inactive MIDI controllers

        Args:
            _widget: Widget clicked
            path: button number
        """
        midi_ports = self.settings.get_strv("midi-ports")
        relative1 = self.settings.get_strv("relative1")
        relative2 = self.settings.get_strv("relative2")
        makies = self.settings.get_strv("makie")
        absolutes = self.settings.get_strv("absolute")
        self.liststore_midi[path][1] = not self.liststore_midi[path][1]
        if self.liststore_midi[path][1]:
            midi_ports.append(self.liststore_midi[path][3])
            if self.liststore_midi[path][2] == "Relative1":
                relative1.append(self.liststore_midi[path][3])
            elif self.liststore_midi[path][2] == "Relative2":
                relative2.append(self.liststore_midi[path][3])
            elif self.liststore_midi[path][2] == "Relative3 (Makie)":
                makies.append(self.liststore_midi[path][3])
            elif self.liststore_midi[path][2] == "Absolute":
                absolutes.append(self.liststore_midi[path][3])
            else:
                self.liststore_midi.set_value(
                    self.liststore_midi.get_iter(path), 2, "Relative3 (Makie)"
                )
                makies.append(self.liststore_midi[path][3])

        else:
            midi_ports.remove(self.liststore_midi[path][3])
            if self.liststore_midi[path][3] in relative1:
                relative1.remove(self.liststore_midi[path][3])
            elif self.liststore_midi[path][3] in relative2:
                relative2.remove(self.liststore_midi[path][3])
            elif self.liststore_midi[path][3] in makies:
                makies.remove(self.liststore_midi[path][3])
            elif self.liststore_midi[path][3] in absolutes:
                absolutes.remove(self.liststore_midi[path][3])
            self.liststore_midi.set_value(self.liststore_midi.get_iter(path), 2, "")
        midi_ports = list(set(midi_ports))
        self.settings.set_strv("midi-ports", midi_ports)
        self.settings.set_strv("relative1", relative1)
        self.settings.set_strv("relative2", relative2)
        self.settings.set_strv("makie", makies)
        self.settings.set_strv("absolute", absolutes)
        if self.midi is not None:
            GLib.idle_add(self.midi.ports.close)
            GLib.idle_add(self.midi.ports.open, midi_ports)
            self.midi.update_faders()

    def _artnet(self, builder: Gtk.Builder) -> None:
        # pylint: disable=too-many-locals,protected-access
        self.liststore_artnet = Gtk.ListStore(str, str, str, str)
        treeview = Gtk.TreeView(model=self.liststore_artnet)

        renderer_text_name = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn(_("Name"), renderer_text_name, text=0)
        treeview.append_column(column_name)

        renderer_text_ip = Gtk.CellRendererText()
        column_ip = Gtk.TreeViewColumn(_("IP Address"), renderer_text_ip, text=1)
        treeview.append_column(column_ip)

        renderer_text_type = Gtk.CellRendererText()
        column_type = Gtk.TreeViewColumn(_("Type"), renderer_text_type, text=2)
        treeview.append_column(column_type)

        renderer_text_univ = Gtk.CellRendererText()
        column_univ = Gtk.TreeViewColumn(_("Universes"), renderer_text_univ, text=3)
        treeview.append_column(column_univ)

        artnet_grid = typing.cast(Gtk.Grid, builder.get_object("artnet_grid"))
        if artnet_grid:
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_hexpand(True)
            scrolled_window.set_vexpand(True)
            scrolled_window.add(treeview)
            artnet_grid.attach(scrolled_window, 0, 1, 1, 1)
            scrolled_window.show_all()

            GLib.timeout_add_seconds(1, self._refresh_artnet)

    def _collect_devices(
        self,
        devices: dict,
        device_type: str,
        grouped: dict,
        active_universes: list[int] | None = None,
    ) -> None:
        """Helper to collect and merge devices"""
        for device in devices.values():
            key = (device.mac, device_type)
            dev_univs = set(device.universes)
            if active_universes is not None:
                dev_univs &= set(active_universes)
            if key not in grouped:
                grouped[key] = {
                    "name": device.names.get("long", ""),
                    "ip": device.ip,
                    "type": device_type,
                    "universes": dev_univs,
                }
            else:
                grouped[key]["universes"].update(dev_univs)

    def _refresh_artnet(self) -> bool:
        if not self.tabs or not self.tabs.tabs.get("settings"):
            return False

        if not self.backend:
            return True

        artnet = getattr(self.backend, "artnet", None)
        if artnet is None:
            return True

        grouped = {}
        self._collect_devices(
            artnet.discovery.nodes,
            "Node",
            grouped,
            artnet.universes,
        )
        self._collect_devices(
            artnet.discovery.consoles,
            "Controller",
            grouped,
            artnet.universes,
        )

        new_state = [
            [g["name"], g["ip"], g["type"], ", ".join(map(str, sorted(g["universes"])))]
            for g in grouped.values()
        ]

        if any(((0, 0, 0, 0, 0, 0), 0) in s.nodes for s in artnet.senders.values()):
            univs = ", ".join(str(u) for u in sorted(artnet.senders.keys()))
            new_state.append(
                ["Virtual Node (Local Loopback)", "127.0.0.1", "Node", univs]
            )

        type_prio = {"Virtual": 0, "Node": 1, "Controller": 2}
        new_state.sort(key=lambda x: (type_prio.get(x[2], 99), x[1], x[0]))

        if self._last_artnet_state != new_state:
            self.liststore_artnet.clear()
            for row in new_state:
                self.liststore_artnet.append(row)
            self._last_artnet_state = new_state

        return True

    def _on_change_percent(self, widget: Gtk.SpinButton) -> None:
        lvl = widget.get_value_as_int()
        self.settings.set_value("percent-level", GLib.Variant("i", lvl))

    def _on_change_default_time(self, widget: Gtk.SpinButton) -> None:
        time = widget.get_value()
        self.settings.set_value("default-time", GLib.Variant("d", time))

    def _on_change_go_back_time(self, widget: Gtk.SpinButton) -> None:
        time = widget.get_value()
        self.settings.set_value("go-back-time", GLib.Variant("d", time))

    def _update_ui_percent(self, _widget: Gtk.Switch, state: bool) -> None:
        """Change levels view (0-100) or (0-255)

        Args:
            state: State of the toggle
        """
        self.settings.set_value("percent", GLib.Variant("b", state))

        # Force redraw of main window
        if self.window is not None:
            self.window.live_view.channels_view.update()

        # Redraw Sequences Tab if open
        if self.tabs is not None and self.tabs.tabs["sequences"]:
            typing.cast(typing.Any, self.tabs.tabs["sequences"]).channels_view.update()

        # Redraw Groups Tab if exist
        if self.tabs is not None and self.tabs.tabs["groups"]:
            typing.cast(typing.Any, self.tabs.tabs["groups"]).channels_view.update()

        # Redraw Memories Tab if exist
        if self.tabs is not None and self.tabs.tabs["memories"]:
            typing.cast(typing.Any, self.tabs.tabs["memories"]).channels_view.update()

    def _switch_osc(self, _widget: Gtk.Switch, state: bool) -> None:
        self.settings.set_value("osc", GLib.Variant("b", state))
        engine = self.app.engine
        if engine is not None:
            if state:
                engine.start_osc(
                    host=self.settings.get_string("osc-host"),
                    client_port=self.settings.get_int("osc-client-port"),
                    server_port=self.settings.get_int("osc-server-port"),
                )
                self.app.osc_delegate = GUIOSCDelegate(self.app)
                engine.register_osc_delegate(self.app.osc_delegate)
            else:
                engine.stop_osc()
                self.app.osc_delegate = None

    def _client_port_changed(self, widget: Gtk.SpinButton) -> None:
        port = widget.get_value_as_int()
        self.settings.set_value("osc-client-port", GLib.Variant("i", port))
        engine = self.app.engine
        if engine is not None:
            engine.update_osc_client(port=port)

    def _server_port_changed(self, widget: Gtk.SpinButton) -> None:
        port = widget.get_value_as_int()
        self.settings.set_value("osc-server-port", GLib.Variant("i", port))
        engine = self.app.engine
        if engine is not None:
            engine.update_osc_server(port)

    def _client_ip_changed(self, widget: Gtk.Entry) -> None:
        ip_addr = widget.get_text()
        if self._is_ip(ip_addr):
            self.settings.set_value("osc-host", GLib.Variant("s", ip_addr))
            engine = self.app.engine
            if engine is not None:
                engine.update_osc_client(host=ip_addr)
            parent = self.get_parent()
            if parent:
                parent.grab_focus()
        else:
            widget.set_text(self.settings.get_string("osc-host"))

    def _is_ip(self, string: str) -> bool:
        try:
            ipaddress.ip_address(string)
            return True
        except ValueError:
            return False

    def _get_serial_ports(self, current_port: str) -> list[str]:
        """Scan system for available serial ports and ensure current_port is present."""
        serial_ports = ["Auto-detect"]
        try:
            for p in serial.tools.list_ports.comports():
                if p.vid == 0x0403 and p.pid == 0x6001:
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

    def _create_universes_tab(self) -> Gtk.Box:
        # pylint: disable=too-many-locals,too-many-statements
        engine = getattr(self.app, "engine", None)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(15)
        main_box.set_margin_end(15)
        main_box.set_margin_top(15)
        main_box.set_margin_bottom(15)

        # We wrap everything in a ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(main_box)

        for u in [1, 2, 3, 4]:
            frame = Gtk.Frame()
            frame.set_label(_("Universe {universe}").format(universe=u))
            frame_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
            frame_box.set_margin_start(10)
            frame_box.set_margin_end(10)
            frame_box.set_margin_top(10)
            frame_box.set_margin_bottom(10)
            frame.add(frame_box)
            main_box.pack_start(frame, False, False, 0)

            config = engine.universe_map[u] if engine is not None else None

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
            net_adj = Gtk.Adjustment(0, 0, 127, 1, 10, 0)
            net_spin = Gtk.SpinButton()
            net_spin.set_adjustment(net_adj)
            artnet_params.attach(net_spin, 1, 0, 1, 1)

            # Sub
            sub_label = Gtk.Label(label=_("Sub:"))
            sub_label.set_halign(Gtk.Align.START)
            artnet_params.attach(sub_label, 2, 0, 1, 1)
            sub_adj = Gtk.Adjustment(0, 0, 15, 1, 5, 0)
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
            prio_adj = Gtk.Adjustment(100, 1, 200, 1, 10, 0)
            prio_spin = Gtk.SpinButton()
            prio_spin.set_adjustment(prio_adj)
            sacn_params.attach(prio_spin, 1, 0, 1, 1)

            # Sync Address
            sacn_sync_label = Gtk.Label(label=_("Sync Address:"))
            sacn_sync_label.set_halign(Gtk.Align.START)
            sacn_params.attach(sacn_sync_label, 0, 1, 1, 1)
            sacn_sync_adj = Gtk.Adjustment(0, 0, 63999, 1, 10, 0)
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

        scrolled.show_all()
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        container.pack_start(scrolled, True, True, 0)
        container.show_all()
        return container

    def _on_universe_settings_changed(
        self,
        _widget: Gtk.Widget,
        universe: int,
    ) -> None:
        engine = getattr(self.app, "engine", None)
        if engine is None:
            return

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

            # Mutual exclusion conflict check
            for other_u, w in self.universe_widgets.items():
                if other_u == universe:
                    continue
                other_check = w["dmx_usb_pro_check"]
                other_combo = w["port_combo"]

                if other_check.get_active():
                    other_selected = other_combo.get_active_text() or "Auto-detect"
                    other_port_name = other_selected.split(" ")[0]

                    if port_name == other_port_name:
                        # Deactivate other conflict
                        other_check.set_active(False)

            protocols.add(Protocol.DMX_USB_PRO)

        config.set_protocols(protocols)

        # 2. Update Art-Net parameters
        config.artnet.net = int(widgets["net_spin"].get_value())
        config.artnet.sub = int(widgets["sub_spin"].get_value())
        config.artnet.sync_active = widgets["sync_switch"].get_active()

        # 3. Update sACN parameters
        config.sacn.priority = int(widgets["prio_spin"].get_value())
        config.sacn.sync_address = int(widgets["sacn_sync_spin"].get_value())

        # 4. Update DMX USB Pro parameters
        selected_text = widgets["port_combo"].get_active_text() or "Auto-detect"
        config.dmx_usb_pro.port = selected_text.split(" ")[0]

        # 5. Hot-reload engine senders/listeners
        engine.reload_universe(universe)

        # 6. Mark show file as modified
        if self.app is not None:
            self.app.core.lightshow.set_modified()

    def _on_universe_switch_changed(
        self,
        _widget: Gtk.Switch,
        _state: bool,
        universe: int,
    ) -> bool:
        self._on_universe_settings_changed(_widget, universe)
        return False
