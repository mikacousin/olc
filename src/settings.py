import mido

from gi.repository import Gio, Gtk, GLib


class Settings(Gio.Settings):
    def __init__(self):

        Gio.Settings.__init__(self)

    def new():

        settings = Gio.Settings.new('org.gnome.olc')
        settings.__class__ = Settings
        return settings


class SettingsDialog:
    def __init__(self):

        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/OpenLightingConsole/settings.ui')

        self.settings_dialog = builder.get_object('settings_dialog')

        switch_percent = builder.get_object('switch_percent')
        switch_percent.set_state(
            Gio.Application.get_default().settings.get_boolean('percent'))

        self.spin_percent_level = builder.get_object('spin_percent_level')
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        self.spin_percent_level.set_adjustment(adjustment)
        self.spin_percent_level.set_value(
            Gio.Application.get_default().settings.get_int('percent-level'))

        self.spin_default_time = builder.get_object('spin_default_time')
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        self.spin_default_time.set_adjustment(adjustment)
        self.spin_default_time.set_value(
            Gio.Application.get_default().settings.get_double('default-time'))

        self.spin_go_back_time = builder.get_object('spin_go_back_time')
        adjustment = Gtk.Adjustment(0, 1, 100, 1, 10, 0)
        self.spin_go_back_time.set_adjustment(adjustment)
        self.spin_go_back_time.set_value(
            Gio.Application.get_default().settings.get_double('go-back-time'))

        self.entry_client_ip = builder.get_object('entry_client_ip')
        self.entry_client_ip.set_text(
            Gio.Application.get_default().settings.get_string('osc-host'))

        self.spin_client_port = builder.get_object('spin_client_port')
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_client_port.set_adjustment(adjustment)
        self.spin_client_port.set_value(
            Gio.Application.get_default().settings.get_int('osc-client-port'))

        self.spin_server_port = builder.get_object('spin_server_port')
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_server_port.set_adjustment(adjustment)
        self.spin_server_port.set_value(
            Gio.Application.get_default().settings.get_int('osc-server-port'))

        self.spin_univers = builder.get_object('spin_univers')
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_univers.set_adjustment(adjustment)
        self.spin_univers.set_value(
            Gio.Application.get_default().settings.get_int('universe'))

        self.midi_in = builder.get_object('midi_in')
        self.midi_in.connect('changed', self._on_midi_in_changed)
        default = Gio.Application.get_default().settings.get_string('midi-in')
        self.midi_in.append_text(default)
        for midi_in in mido.get_input_names():
            self.midi_in.append_text(midi_in)
        self.midi_in.set_entry_text_column(0)
        self.midi_in.set_active(0)

        builder.connect_signals(self)

    def _on_change_percent(self, widget):
        lvl = self.spin_percent_level.get_value_as_int()
        Gio.Application.get_default().settings.set_value(
            'percent-level', GLib.Variant('i', lvl))

    def _on_change_default_time(self, widget):
        time = self.spin_default_time.get_value()
        Gio.Application.get_default().settings.set_value(
            'default-time', GLib.Variant('d', time))

    def _on_change_go_back_time(self, widget):
        time = self.spin_go_back_time.get_value()
        Gio.Application.get_default().settings.set_value(
            'go-back-time', GLib.Variant('d', time))

    def _update_ui_percent(self, widget, state):
        """ Change levels view (0-100) or (0-255) """
        Gio.Application.get_default().settings.set_value(
            'percent', GLib.Variant('b', state))

        # Force redraw of main window
        Gio.Application.get_default().window.flowbox.invalidate_filter()

        # Redraw Sequences Tab if open
        if Gio.Application.get_default().sequences_tab:
            Gio.Application.get_default().sequences_tab.flowbox.invalidate_filter()

        # Redraw Groups Tab if exist
        if Gio.Application.get_default().group_tab:
            Gio.Application.get_default().group_tab.flowbox1.invalidate_filter()

        # Redraw Memories Tab if exist
        if Gio.Application.get_default().memories_tab:
            Gio.Application.get_default().memories_tab.flowbox.invalidate_filter()

    def _on_btn_clicked(self, button):
        ip = self.entry_client_ip.get_text()
        client_port = self.spin_client_port.get_value_as_int()
        server_port = self.spin_server_port.get_value_as_int()

        print("Relancer OSC :")
        print("Client IP :", ip, "Port :", client_port)
        print("Server Port :", server_port)

        Gio.Application.get_default().settings.set_value(
            'osc-host', GLib.Variant('s', ip))
        Gio.Application.get_default().settings.set_value(
            'osc-client-port', GLib.Variant('i', client_port))
        Gio.Application.get_default().settings.set_value(
            'osc-server-port', GLib.Variant('i', server_port))

    def _on_midi_in_changed(self, combo):
        text = combo.get_active_text()
        if text is not None:
            Gio.Application.get_default().settings.set_value(
                'midi-in', GLib.Variant('s', text))
            Gio.Application.get_default().midi.close_input()
            Gio.Application.get_default().midi.open_input(text)
