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
        switch_percent.set_state(Gio.Application.get_default().settings.get_boolean('percent'))

        self.spin_percent_level = builder.get_object('spin_percent_level')
        adjustment = Gtk.Adjustment(0, 0, 100, 1, 10, 0)
        self.spin_percent_level.set_adjustment(adjustment)
        self.spin_percent_level.set_value(Gio.Application.get_default().settings.get_int('percent-level'))

        self.entry_client_ip = builder.get_object('entry_client_ip')
        self.entry_client_ip.set_text(Gio.Application.get_default().settings.get_string('osc-host'))

        self.spin_client_port = builder.get_object('spin_client_port')
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_client_port.set_adjustment(adjustment)
        self.spin_client_port.set_value(Gio.Application.get_default().settings.get_int('osc-client-port'))

        self.spin_server_port = builder.get_object('spin_server_port')
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_server_port.set_adjustment(adjustment)
        self.spin_server_port.set_value(Gio.Application.get_default().settings.get_int('osc-server-port'))

        self.spin_univers = builder.get_object('spin_univers')
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10, 0)
        self.spin_univers.set_adjustment(adjustment)
        self.spin_univers.set_value(Gio.Application.get_default().settings.get_int('universe'))

        builder.connect_signals(self)

    def _update_ui_percent(self, widget, state):
        """ Change levels view (0-100) or (0-255) """
        Gio.Application.get_default().settings.set_value('percent', GLib.Variant('b', state))

        # Force redraw of main window
        Gio.Application.get_default().window.flowbox.invalidate_filter()

        # Redraw Groups Window if exist
        try:
            Gio.Application.get_default().win_groups.flowbox1.invalidate_filter()
        except:
            pass

        # Redraw Masters Window if exist
        try:
            for i in range(len(Gio.Application.get_default().win_masters.masters)):
                val = Gio.Application.get_default().win_masters.scale[i].get_value()
                if state:
                    ad = Gtk.Adjustment((val/255)*100, 0, 100, 1, 10, 0)
                else:
                    ad = Gtk.Adjustment((val/100)*255, 0, 255, 1, 10, 0)
                Gio.Application.get_default().win_masters.scale[i].set_adjustment(ad)
        except:
            pass

    def _on_btn_clicked(self, button):
        ip = self.entry_client_ip.get_text()
        client_port = self.spin_client_port.get_value_as_int()
        server_port = self.spin_server_port.get_value_as_int()

        print("Relancer OSC :")
        print("Client IP :", ip, "Port :", client_port)
        print("Server Port :", server_port)

        Gio.Application.get_default().settings.set_value('osc-host', GLib.Variant('s', ip))
        Gio.Application.get_default().settings.set_value('osc-client-port', GLib.Variant('i', client_port))
        Gio.Application.get_default().settings.set_value('osc-server-port', GLib.Variant('i', server_port))
