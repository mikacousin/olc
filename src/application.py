import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk
from ola import OlaClient

from olc.window import Window
from olc.patchwindow import PatchWindow
from olc.dmx import PatchDmx, DmxFrame

class Application(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self,
                application_id='org.gnome.olc',
                flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name('OpenLightingConsole')
        GLib.set_prgname('olc')

        # Change to dark theme
        settings = Gtk.Settings.get_default()
        settings.set_property('gtk-application-prefer-dark-theme', True)

        # Create DMX Frame
        self.dmxframe = DmxFrame()

        # Create OlaClient
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()
        self.universe = 1
        self.ola_client.RegisterUniverse(self.universe, self.ola_client.REGISTER, self.on_dmx)

    def do_activate(self):
        self.patch = PatchDmx()
        self.patch.patch_empty()
        self.patch.add_output(10, 10)
        self.patch.add_output(510, 20)

        self.window = Window(self, self.patch)
        self.window.show_all()

        # TODO: Remove open patch window
        self.patchwindow = PatchWindow(self.patch)
        self.patchwindow.show_all()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        menu = self.setup_app_menu()
        self.set_app_menu(menu)

    def setup_app_menu(self):
        """ Setup application menu, return Gio.Menu """
        builder = Gtk.Builder()

        builder.add_from_resource('/org/gnome/OpenLightingConsole/app-menu.ui')

        menu = builder.get_object('app-menu')

        aboutAction = Gio.SimpleAction.new('about', None)
        aboutAction.connect('activate', self._about)
        self.add_action(aboutAction)

        quitAction = Gio.SimpleAction.new('quit', None)
        quitAction.connect('activate', self._exit)
        self.add_action(quitAction)

        return menu

    def on_dmx(self, dmx):
        for i in range(len(dmx)):
            chanel = self.patch.outputs[i]
            Gdk.ProgressBar.set_fraction(win.progressbar[chanel-1], dmx[i]/255)
            win.levels[chanel-1].set_text(str(dmx[i]))
            self.dmxframe[i] = dmx[i]

    def _about(self, action, parameter):
        """
            Setup about dialog
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/OpenLightingConsole/AboutDialog.ui')
        about = builder.get_object('about_dialog')
        about.set_transient_for(self.window)
        about.connect("response", self._about_response)
        about.show()

    def _about_response(self, dialog, response):
        """
            Destroy about dialog when closed
            @param dialog as Gtk.Dialog
            @param response as int
        """
        dialog.destroy()

    def _exit(self, action, parameter):
        self.quit()


if __name__ == "__main__":
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
