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
import ipaddress
import socket
import typing
from gettext import gettext as _
from typing import Callable

from gi.repository import Gdk, GLib, Gtk
from olc.osc import Osc

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.backends import DMXBackend
    from olc.midi import Midi
    from olc.tabs_manager import Tabs


# pylint: disable=too-many-instance-attributes
class SettingsTab(Gtk.Box):
    """Settings"""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        settings: Gio.Settings,
        tabs: Tabs,
        midi: Midi,
        backnd: DMXBackend,
        window: Gtk.Window,
        osc: Osc,
    ) -> None:
        self.settings = settings
        self.tabs = tabs
        self.midi = midi
        self.backend = backnd
        self.window = window
        self.osc = osc

        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._last_artnet_state: list[list[str]] | None = None

        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/settings.ui")
        settings_dialog = builder.get_object("settings")

        self._setup_appearance(builder)
        self._setup_osc(builder)

        # MIDI
        self._midi(builder)

        # Art-Net Tab Visibility
        backend = self.settings.get_string("backend")
        if "artnet" not in backend:
            artnet_grid = builder.get_object("artnet_grid")
            if artnet_grid:
                page_num = settings_dialog.page_num(artnet_grid)
                if page_num >= 0:
                    settings_dialog.remove_page(page_num)
        else:
            self._artnet(builder)

        builder.connect_signals(self)
        self.pack_start(settings_dialog, True, True, 0)

    def _setup_appearance(self, builder: Gtk.Builder) -> None:
        widget = builder.get_object("switch_percent")
        widget.set_state(self.settings.get_boolean("percent"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget = builder.get_object("spin_percent_level")
        widget.set_adjustment(adjustment)
        widget.set_value(self.settings.get_int("percent-level"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget = builder.get_object("spin_default_time")
        widget.set_adjustment(adjustment)
        widget.set_value(self.settings.get_double("default-time"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget = builder.get_object("spin_go_back_time")
        widget.set_adjustment(adjustment)
        widget.set_value(self.settings.get_double("go-back-time"))

    def _setup_osc(self, builder: Gtk.Builder) -> None:
        widget = builder.get_object("switch_osc")
        widget.set_state(self.settings.get_boolean("osc"))

        self.entry_client_ip = builder.get_object("entry_client_ip")
        self.entry_client_ip.set_text(self.settings.get_string("osc-host"))

        self.spin_client_port = builder.get_object("spin_client_port")
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_client_port.set_adjustment(adjustment)
        self.spin_client_port.set_value(self.settings.get_int("osc-client-port"))

        self.spin_server_port = builder.get_object("spin_server_port")
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_server_port.set_adjustment(adjustment)
        self.spin_server_port.set_value(self.settings.get_int("osc-server-port"))

        local_ip = builder.get_object("local_ip")
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        local_ip.set_label(ip_addr)

    def _midi(self, builder: Gtk.builder) -> None:
        # List of MIDI Controllers
        liststore_modes = Gtk.ListStore(str)
        for item in ["Absolute", "Relative1", "Relative2", "Relative3 (Makie)"]:
            liststore_modes.append([item])
        midi_grid = builder.get_object("midi_io_grid")
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
        for midi_port in sorted(list(set(self.midi.ports.mido_ports))):
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
        self.tabs.close("settings")

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.Event
    ) -> Callable | bool:
        """Key has been pressed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
        keyname = Gdk.keyval_name(event.keyval)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
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
        GLib.idle_add(self.midi.ports.close)
        GLib.idle_add(self.midi.ports.open, midi_ports)
        self.midi.update_faders()

    def _artnet(self, builder: Gtk.Builder) -> None:
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

        artnet_grid = builder.get_object("artnet_grid")
        if artnet_grid:
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_hexpand(True)
            scrolled_window.set_vexpand(True)
            scrolled_window.add(treeview)
            artnet_grid.attach(scrolled_window, 0, 1, 1, 1)
            scrolled_window.show_all()

            GLib.timeout_add_seconds(1, self._refresh_artnet)

    def _collect_devices(self, devices: dict, device_type: str, grouped: dict) -> None:
        """Helper to collect and merge devices"""
        for device in devices.values():
            key = (device.mac, device_type)
            if key not in grouped:
                grouped[key] = {
                    "name": device.names.get("long", ""),
                    "ip": device.ip,
                    "type": device_type,
                    "universes": set(device.universes),
                }
            else:
                grouped[key]["universes"].update(device.universes)

    def _refresh_artnet(self) -> bool:
        if not self.tabs.tabs.get("settings"):
            return False

        if "artnet" not in self.settings.get_string("backend"):
            return True

        if not self.backend or not hasattr(self.backend, "artnet"):
            return True

        grouped = {}
        self._collect_devices(self.backend.artnet.discovery.nodes, "Node", grouped)
        self._collect_devices(
            self.backend.artnet.discovery.consoles, "Controller", grouped
        )

        new_state = [
            [g["name"], g["ip"], g["type"], ", ".join(map(str, sorted(g["universes"])))]
            for g in grouped.values()
        ]

        if any(
            ((0, 0, 0, 0, 0, 0), 0) in s.nodes
            for s in self.backend.artnet.senders.values()
        ):
            univs = ", ".join(
                str(u) for u in sorted(self.backend.artnet.senders.keys())
            )
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

    def _on_change_go_back_time(self, widget: Gtk.Widget) -> None:
        time = widget.get_value()
        self.settings.set_value("go-back-time", GLib.Variant("d", time))

    def _update_ui_percent(self, _widget: Gtk.Switch, state: bool) -> None:
        """Change levels view (0-100) or (0-255)

        Args:
            state: State of the toggle
        """
        self.settings.set_value("percent", GLib.Variant("b", state))

        # Force redraw of main window
        self.window.live_view.channels_view.update()

        # Redraw Sequences Tab if open
        if self.tabs.tabs["sequences"]:
            self.tabs.tabs["sequences"].channels_view.update()

        # Redraw Groups Tab if exist
        if self.tabs.tabs["groups"]:
            self.tabs.tabs["groups"].channels_view.update()

        # Redraw Memories Tab if exist
        if self.tabs.tabs["memories"]:
            self.tabs.tabs["memories"].channels_view.update()

    def _switch_osc(self, _widget: Gtk.Switch, state: bool) -> None:
        self.settings.set_value("osc", GLib.Variant("b", state))
        if state:
            self.osc = Osc()
        else:
            self.osc.stop()
            self.osc = None

    def _client_port_changed(self, widget: Gtk.SpinButton) -> None:
        port = widget.get_value_as_int()
        self.settings.set_value("osc-client-port", GLib.Variant("i", port))
        self.osc.client.target_changed(port=port)

    def _server_port_changed(self, widget: Gtk.SpinButton) -> None:
        port = widget.get_value_as_int()
        self.settings.set_value("osc-server-port", GLib.Variant("i", port))
        self.osc.restart_server()

    def _client_ip_changed(self, widget: Gtk.Entry) -> None:
        ip_addr = widget.get_text()
        if self._is_ip(ip_addr):
            self.settings.set_value("osc-host", GLib.Variant("s", ip_addr))
            self.osc.client.target_changed(host=ip_addr)
            self.get_parent().grab_focus()
        else:
            widget.set_text(self.settings.get_string("osc-host"))

    def _is_ip(self, string: str) -> bool:
        try:
            ipaddress.ip_address(string)
            return True
        except ValueError:
            return False
