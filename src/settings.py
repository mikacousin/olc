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
import gi
import mido
from olc.define import App

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402


class Settings(Gio.Settings):
    """Open Lighting Console settings"""

    def __init__(self):

        Gio.Settings.__init__(self)

    def new():

        settings = Gio.Settings.new("com.github.mikacousin.olc")
        settings.__class__ = Settings
        return settings


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

        # List of MIDI Controllers
        midi_grid = builder.get_object("midi_grid")
        midi_grid.set_orientation(Gtk.Orientation.VERTICAL)
        default = App().settings.get_strv("midi-in")
        for midi_in in list(set(mido.get_input_names())):
            check_button = Gtk.CheckButton()
            check_button.set_label(midi_in)
            check_button.connect("toggled", self.on_midi_toggle)
            if midi_in in default:
                check_button.set_active(True)
            midi_grid.add(check_button)

        builder.connect_signals(self)

        self.settings_dialog.connect("delete-event", self.close)

    def close(self, widget, _param):  # pylint: disable=no-self-use
        """Mark window as closed

        Args:
            widget: Widget to destroy

        Returns:
            True
        """
        App().win_settings = None
        widget.destroy()
        return True

    def on_midi_toggle(self, button):  # pylint: disable=no-self-use
        """Active / Unactive MIDI controllers

        Args:
            button: Button clicked
        """
        midi_ports = App().settings.get_strv("midi-in")
        if button.get_active():
            midi_ports.append(button.get_label())
        else:
            midi_ports.remove(button.get_label())
        midi_ports = list(set(midi_ports))
        App().settings.set_strv("midi-in", midi_ports)
        App().midi.close_input()
        App().midi.open_input(midi_ports)

    def _on_change_percent(self, _widget):
        lvl = self.spin_percent_level.get_value_as_int()
        App().settings.set_value("percent-level", GLib.Variant("i", lvl))

    def _on_change_default_time(self, _widget):
        time = self.spin_default_time.get_value()
        App().settings.set_value("default-time", GLib.Variant("d", time))

    def _on_change_go_back_time(self, _widget):
        time = self.spin_go_back_time.get_value()
        App().settings.set_value("go-back-time", GLib.Variant("d", time))

    def _update_ui_percent(self, _widget, state):  # pylint: disable=no-self-use
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
            App().group_tab.flowbox1.invalidate_filter()

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
