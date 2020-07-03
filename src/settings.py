import mido

from olc.define import App

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, GLib  # noqa: E402


class Settings(Gio.Settings):
    def __init__(self):

        Gio.Settings.__init__(self)

    def new():

        settings = Gio.Settings.new("org.gnome.olc")
        settings.__class__ = Settings
        return settings


class SettingsDialog:
    def __init__(self):

        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/OpenLightingConsole/settings.ui")

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

        self.spin_univers = builder.get_object("spin_univers")
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_univers.set_adjustment(adjustment)
        self.spin_univers.set_value(App().settings.get_int("universe"))

        self.midi_in = builder.get_object("midi_in")
        self.midi_in.connect("changed", self._on_midi_in_changed)
        default = App().settings.get_string("midi-in")
        self.midi_in.append_text(default)
        for midi_in in mido.get_input_names():
            self.midi_in.append_text(midi_in)
        self.midi_in.set_entry_text_column(0)
        self.midi_in.set_active(0)

        builder.connect_signals(self)

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
        """ Change levels view (0-100) or (0-255) """
        App().settings.set_value("percent", GLib.Variant("b", state))

        # Force redraw of main window
        App().window.flowbox.invalidate_filter()

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

    def _on_midi_in_changed(self, combo):
        text = combo.get_active_text()
        if text is not None:
            App().settings.set_value("midi-in", GLib.Variant("s", text))
            App().midi.close_input()
            App().midi.open_input(text)
