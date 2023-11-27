# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
import mido
from gi.repository import GLib, Gtk
from olc.define import App
from olc.osc import Osc


class SettingsDialog:
    """Edit settings"""

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/settings.ui")
        self.settings_dialog = builder.get_object("settings_dialog")

        # Appearence
        switch_percent = builder.get_object("switch_percent")
        switch_percent.set_state(App().settings.get_boolean("percent"))

        spin = builder.get_object("spin_percent_level")
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        spin.set_adjustment(adjustment)
        spin.set_value(App().settings.get_int("percent-level"))

        spin = builder.get_object("spin_default_time")
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        spin.set_adjustment(adjustment)
        spin.set_value(App().settings.get_double("default-time"))

        spin = builder.get_object("spin_go_back_time")
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        spin.set_adjustment(adjustment)
        spin.set_value(App().settings.get_double("go-back-time"))

        # OSC
        switch_osc = builder.get_object("switch_osc")
        switch_osc.set_state(App().settings.get_boolean("osc"))

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

        # List of MIDI Controllers (In)
        liststore_modes = Gtk.ListStore(str)
        for item in ["Absolute", "Relative1", "Relative2", "Relative3 (Makie)"]:
            liststore_modes.append([item])
        midi_grid = builder.get_object("midi_in_grid")
        midi_grid.set_orientation(Gtk.Orientation.VERTICAL)
        default = App().settings.get_strv("midi-in")
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
        self.liststore_midi_in = Gtk.ListStore(str, bool, str, str)
        treeview = Gtk.TreeView(model=self.liststore_midi_in)
        for midi_in in sorted(list(set(mido.get_input_names()))):
            if midi_in in default:
                if midi_in in relative1:
                    self.liststore_midi_in.append(
                        [midi_in.split(":")[0], True, "Relative1", midi_in]
                    )
                elif midi_in in relative2:
                    self.liststore_midi_in.append(
                        [midi_in.split(":")[0], True, "Relative2", midi_in]
                    )
                elif midi_in in makies:
                    self.liststore_midi_in.append(
                        [midi_in.split(":")[0], True, "Relative3 (Makie)", midi_in]
                    )
                elif midi_in in absolutes:
                    self.liststore_midi_in.append(
                        [midi_in.split(":")[0], True, "Absolute", midi_in]
                    )
                else:
                    # Default: Makie mode
                    self.liststore_midi_in.append(
                        [midi_in.split(":")[0], True, "Relative3 (Makie)", midi_in]
                    )
                    makies.append(midi_in)
                    if midi_in in absolutes:
                        absolutes.remove(midi_in)
                    elif midi_in in relative1:
                        relative1.remove(midi_in)
                    elif midi_in in relative2:
                        relative2.remove(midi_in)
                    App().settings.set_strv("relative1", relative1)
                    App().settings.set_strv("relative2", relative2)
                    App().settings.set_strv("makie", makies)
                    App().settings.set_strv("absolute", absolutes)
            else:
                self.liststore_midi_in.append(
                    [midi_in.split(":")[0], False, "", midi_in]
                )
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn(_("MIDI Port"), renderer_text, text=0)
        treeview.append_column(column_text)
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_midi_in_toggle)
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
        # List of MIDI Controllers (Out)
        midi_grid = builder.get_object("midi_out_grid")
        midi_grid.set_orientation(Gtk.Orientation.VERTICAL)
        default = App().settings.get_strv("midi-out")
        self.liststore_midi_out = Gtk.ListStore(str, bool, str)
        treeview = Gtk.TreeView(model=self.liststore_midi_out)
        for midi_out in sorted(list(set(mido.get_output_names()))):
            if midi_out in default:
                self.liststore_midi_out.append([midi_out.split(":")[0], True, midi_out])
            else:
                self.liststore_midi_out.append(
                    [midi_out.split(":")[0], False, midi_out]
                )
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("MIDI Port", renderer_text, text=0)
        treeview.append_column(column_text)
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_midi_out_toggle)
        column_toggle = Gtk.TreeViewColumn("Active", renderer_toggle, active=1)
        treeview.append_column(column_toggle)
        midi_grid.add(treeview)

        builder.connect_signals(self)

        self.settings_dialog.connect("delete-event", self.close)

    def close(self, widget, _param):
        """Mark window as closed

        Args:
            widget: Widget to destroy

        Returns:
            True
        """
        App().win_settings = None
        widget.destroy()
        return True

    def on_combo_change(self, _widget, path, text):
        """Change rotatives mode

        Args:
            _widget: Widget clicked
            path: Path to combo
            text: New combo's text
        """
        self.liststore_midi_in[path][2] = text
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
        if text == "Relative1":
            relative1.append(self.liststore_midi_in[path][3])
            if self.liststore_midi_in[path][3] in makies:
                makies.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in relative2:
                relative2.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in absolutes:
                absolutes.remove(self.liststore_midi_in[path][3])
        elif text == "Relative2":
            relative2.append(self.liststore_midi_in[path][3])
            if self.liststore_midi_in[path][3] in relative1:
                relative1.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in makies:
                makies.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in absolutes:
                absolutes.remove(self.liststore_midi_in[path][3])
        elif text == "Relative3 (Makie)":
            makies.append(self.liststore_midi_in[path][3])
            if self.liststore_midi_in[path][3] in relative1:
                relative1.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in relative2:
                relative2.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in absolutes:
                absolutes.remove(self.liststore_midi_in[path][3])
        elif text == "Absolute":
            absolutes.append(self.liststore_midi_in[path][3])
            if self.liststore_midi_in[path][3] in relative1:
                relative1.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in relative2:
                relative2.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in makies:
                makies.remove(self.liststore_midi_in[path][3])
        App().settings.set_strv("relative1", relative1)
        App().settings.set_strv("relative2", relative2)
        App().settings.set_strv("makie", makies)
        App().settings.set_strv("absolute", absolutes)

    def on_midi_in_toggle(self, _widget, path):
        """Active / Unactive MIDI controllers

        Args:
            _widget: Widget clicked
            path: button number
        """
        midi_ports = App().settings.get_strv("midi-in")
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
        self.liststore_midi_in[path][1] = not self.liststore_midi_in[path][1]
        if self.liststore_midi_in[path][1]:
            midi_ports.append(self.liststore_midi_in[path][3])
            if self.liststore_midi_in[path][2] == "Relative1":
                relative1.append(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][2] == "Relative2":
                relative2.append(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][2] == "Relative3 (Makie)":
                makies.append(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][2] == "Absolute":
                absolutes.append(self.liststore_midi_in[path][3])
            else:
                self.liststore_midi_in.set_value(
                    self.liststore_midi_in.get_iter(path), 2, "Relative3 (Makie)"
                )
                makies.append(self.liststore_midi_in[path][3])

        else:
            midi_ports.remove(self.liststore_midi_in[path][3])
            if self.liststore_midi_in[path][3] in relative1:
                relative1.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in relative2:
                relative2.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in makies:
                makies.remove(self.liststore_midi_in[path][3])
            elif self.liststore_midi_in[path][3] in absolutes:
                absolutes.remove(self.liststore_midi_in[path][3])
            self.liststore_midi_in.set_value(
                self.liststore_midi_in.get_iter(path), 2, ""
            )
        midi_ports = list(set(midi_ports))
        App().settings.set_strv("midi-in", midi_ports)
        App().settings.set_strv("relative1", relative1)
        App().settings.set_strv("relative2", relative2)
        App().settings.set_strv("makie", makies)
        App().settings.set_strv("absolute", absolutes)
        GLib.idle_add(App().midi.ports.close_input)
        GLib.idle_add(App().midi.ports.open_input, midi_ports)

    def on_midi_out_toggle(self, _widget, path):
        """Active / Unactive MIDI controllers (output)

        Args:
            _widget: Widget clicked
            path: Path to button clicked
        """
        midi_ports = App().settings.get_strv("midi-out")
        self.liststore_midi_out[path][1] = not self.liststore_midi_out[path][1]
        if self.liststore_midi_out[path][1]:
            midi_ports.append(self.liststore_midi_out[path][2])
        else:
            midi_ports.remove(self.liststore_midi_out[path][2])
        midi_ports = list(set(midi_ports))
        App().settings.set_strv("midi-out", midi_ports)
        GLib.idle_add(App().midi.ports.close_output)
        GLib.idle_add(App().midi.ports.open_output, midi_ports)
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
        else:
            widget.set_text(App().settings.get_string("osc-host"))

    def _is_ip(self, string: str) -> bool:
        try:
            ipaddress.ip_address(string)
            return True
        except ValueError:
            return False
