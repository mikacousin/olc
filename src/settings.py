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
import ipaddress
import socket
from gettext import gettext as _
from typing import Any
from gi.repository import Gdk, GLib, Gtk
from olc.define import App
from olc.osc import Osc


class SettingsTab(Gtk.Box):
    """Settings"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/settings.ui")
        settings_dialog = builder.get_object("settings")

        # Appearance
        widget = builder.get_object("switch_percent")
        widget.set_state(App().settings.get_boolean("percent"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget = builder.get_object("spin_percent_level")
        widget.set_adjustment(adjustment)
        widget.set_value(App().settings.get_int("percent-level"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget = builder.get_object("spin_default_time")
        widget.set_adjustment(adjustment)
        widget.set_value(App().settings.get_double("default-time"))
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        widget = builder.get_object("spin_go_back_time")
        widget.set_adjustment(adjustment)
        widget.set_value(App().settings.get_double("go-back-time"))

        # OSC
        widget = builder.get_object("switch_osc")
        widget.set_state(App().settings.get_boolean("osc"))

        self.entry_client_ip = builder.get_object("entry_client_ip")
        self.entry_client_ip.set_text(App().settings.get_string("osc-host"))

        self.spin_client_port = builder.get_object("spin_client_port")
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_client_port.set_adjustment(adjustment)
        self.spin_client_port.set_value(App().settings.get_int("osc-client-port"))

        self.spin_server_port = builder.get_object("spin_server_port")
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_server_port.set_adjustment(adjustment)
        self.spin_server_port.set_value(App().settings.get_int("osc-server-port"))

        local_ip = builder.get_object("local_ip")
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        local_ip.set_label(ip_addr)

        # MIDI
        self._midi(builder)

        builder.connect_signals(self)
        self.pack_start(settings_dialog, True, True, 0)

    def _midi(self, builder):
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
        column_combo = Gtk.TreeViewColumn(_("Rotatives Mode"), renderer_combo, text=2)
        treeview.append_column(column_combo)
        midi_grid.add(treeview)

    def _populate_midi_ports(self) -> None:
        default = App().settings.get_strv("midi-ports")
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
        for midi_port in sorted(list(set(App().midi.ports.mido_ports))):
            if midi_port in default:
                if midi_port in relative1:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative1", midi_port])
                elif midi_port in relative2:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative2", midi_port])
                elif midi_port in makies:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative3 (Makie)", midi_port])
                elif midi_port in absolutes:
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Absolute", midi_port])
                else:
                    # Default: Mackie mode
                    self.liststore_midi.append(
                        [midi_port.split(":")[0], True, "Relative3 (Makie)", midi_port])
                    makies.append(midi_port)
                    if midi_port in absolutes:
                        absolutes.remove(midi_port)
                    elif midi_port in relative1:
                        relative1.remove(midi_port)
                    elif midi_port in relative2:
                        relative2.remove(midi_port)
                    App().settings.set_strv("relative1", relative1)
                    App().settings.set_strv("relative2", relative2)
                    App().settings.set_strv("makie", makies)
                    App().settings.set_strv("absolute", absolutes)
            else:
                self.liststore_midi.append(
                    [midi_port.split(":")[0], False, "", midi_port])

    def refresh(self) -> None:
        """Refresh MIDI ports"""
        self.liststore_midi.clear()
        self._populate_midi_ports()

    def on_close_icon(self, _widget) -> None:
        """Close Tab on close clicked"""
        App().tabs.close("settings")

    def on_key_press_event(self, _widget, event: Gdk.Event) -> Any:
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
        App().tabs.close("settings")

    def on_combo_change(self, _widget, path, text):
        """Change rotatives mode

        Args:
            _widget: Widget clicked
            path: Path to combo
            text: New combo's text
        """
        self.liststore_midi[path][2] = text
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
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
        App().settings.set_strv("relative1", relative1)
        App().settings.set_strv("relative2", relative2)
        App().settings.set_strv("makie", makies)
        App().settings.set_strv("absolute", absolutes)

    def on_midi_toggle(self, _widget, path):
        """Active / Inactive MIDI controllers

        Args:
            _widget: Widget clicked
            path: button number
        """
        midi_ports = App().settings.get_strv("midi-ports")
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
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
                self.liststore_midi.set_value(self.liststore_midi.get_iter(path), 2,
                                              "Relative3 (Makie)")
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
        App().settings.set_strv("midi-ports", midi_ports)
        App().settings.set_strv("relative1", relative1)
        App().settings.set_strv("relative2", relative2)
        App().settings.set_strv("makie", makies)
        App().settings.set_strv("absolute", absolutes)
        GLib.idle_add(App().midi.ports.close)
        GLib.idle_add(App().midi.ports.open, midi_ports)
        App().midi.update_masters()
        App().midi.gm_init()

    def _on_change_percent(self, widget: Gtk.SpinButton) -> None:
        lvl = widget.get_value_as_int()
        App().settings.set_value("percent-level", GLib.Variant("i", lvl))

    def _on_change_default_time(self, widget: Gtk.SpinButton) -> None:
        time = widget.get_value()
        App().settings.set_value("default-time", GLib.Variant("d", time))

    def _on_change_go_back_time(self, widget) -> None:
        time = widget.get_value()
        App().settings.set_value("go-back-time", GLib.Variant("d", time))

    def _update_ui_percent(self, _widget, state):
        """Change levels view (0-100) or (0-255)

        Args:
            state: State of the toggle
        """
        App().settings.set_value("percent", GLib.Variant("b", state))

        # Force redraw of main window
        App().window.live_view.channels_view.update()

        # Redraw Sequences Tab if open
        if App().tabs.tabs["sequences"]:
            App().tabs.tabs["sequences"].channels_view.update()

        # Redraw Groups Tab if exist
        if App().tabs.tabs["groups"]:
            App().tabs.tabs["groups"].channels_view.update()

        # Redraw Memories Tab if exist
        if App().tabs.tabs["memories"]:
            App().tabs.tabs["memories"].channels_view.update()

    def _switch_osc(self, _widget, state):
        App().settings.set_value("osc", GLib.Variant("b", state))
        if state:
            App().osc = Osc()
        else:
            App().osc.stop()
            App().osc = None

    def _client_port_changed(self, widget: Gtk.SpinButton) -> None:
        port = widget.get_value_as_int()
        App().settings.set_value("osc-client-port", GLib.Variant("i", port))
        App().osc.client.target_changed(port=port)

    def _server_port_changed(self, widget: Gtk.SpinButton) -> None:
        port = widget.get_value_as_int()
        App().settings.set_value("osc-server-port", GLib.Variant("i", port))
        App().osc.restart_server()

    def _client_ip_changed(self, widget: Gtk.Entry) -> None:
        ip_addr = widget.get_text()
        if self._is_ip(ip_addr):
            App().settings.set_value("osc-host", GLib.Variant("s", ip_addr))
            App().osc.client.target_changed(host=ip_addr)
            self.get_parent().grab_focus()
        else:
            widget.set_text(App().settings.get_string("osc-host"))

    def _is_ip(self, string: str) -> bool:
        try:
            ipaddress.ip_address(string)
            return True
        except ValueError:
            return False
