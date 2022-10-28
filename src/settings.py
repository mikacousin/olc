# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from gettext import gettext as _
import mido
from gi.repository import GLib, Gtk
from olc.define import App


class SettingsDialog:
    """Edit settings"""

    def __init__(self):

        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/settings.ui")

        self.settings_dialog = builder.get_object("settings_dialog")

        switch_percent = builder.get_object("switch_percent")
        switch_percent.set_state(App().settings.get_boolean("percent"))

        self.spin_percent_level = builder.get_object("spin_percent_level")
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        self.spin_percent_level.set_adjustment(adjustment)
        self.spin_percent_level.set_value(App().settings.get_int("percent-level"))

        self.spin_default_time = builder.get_object("spin_default_time")
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        self.spin_default_time.set_adjustment(adjustment)
        self.spin_default_time.set_value(App().settings.get_double("default-time"))

        self.spin_go_back_time = builder.get_object("spin_go_back_time")
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        self.spin_go_back_time.set_adjustment(adjustment)
        self.spin_go_back_time.set_value(App().settings.get_double("go-back-time"))

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

    def _on_change_percent(self, _widget):
        lvl = self.spin_percent_level.get_value_as_int()
        App().settings.set_value("percent-level", GLib.Variant("i", lvl))

    def _on_change_default_time(self, _widget):
        time = self.spin_default_time.get_value()
        App().settings.set_value("default-time", GLib.Variant("d", time))

    def _on_change_go_back_time(self, _widget):
        time = self.spin_go_back_time.get_value()
        App().settings.set_value("go-back-time", GLib.Variant("d", time))

    def _update_ui_percent(self, _widget, state):
        """Change levels view (0-100) or (0-255)

        Args:
            state: State of the toggle
        """
        App().settings.set_value("percent", GLib.Variant("b", state))

        # Force redraw of main window
        App().window.channels_view.flowbox.invalidate_filter()

        # Redraw Sequences Tab if open
        if App().sequences_tab:
            App().sequences_tab.flowbox.invalidate_filter()

        # Redraw Groups Tab if exist
        if App().group_tab:
            App().group_tab.channels_view.flowbox.invalidate_filter()

        # Redraw Memories Tab if exist
        if App().memories_tab:
            App().memories_tab.flowbox.invalidate_filter()

    def _on_btn_clicked(self, _button):
        address_ip = self.entry_client_ip.get_text()
        client_port = self.spin_client_port.get_value_as_int()
        server_port = self.spin_server_port.get_value_as_int()

        print("Relancer OSC :")
        print("Client IP :", address_ip, "Port :", client_port)
        print("Server Port :", server_port)

        App().settings.set_value("osc-host", GLib.Variant("s", address_ip))
        App().settings.set_value("osc-client-port", GLib.Variant("i", client_port))
        App().settings.set_value("osc-server-port", GLib.Variant("i", server_port))
