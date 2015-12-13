import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk
from ola import OlaClient

from olc.window import Window
from olc.patchwindow import PatchWindow
from olc.dmx import PatchDmx, DmxFrame
from olc.cue import Cue
from olc.sequence import Sequence
from olc.sequentialwindow import SequentialWindow

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

        # Create patch (1:1)
        self.patch = PatchDmx()

        # Create a sequential
        self.sequence = Sequence(1)

        # Create OlaClient
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()
        self.universe = 1
        self.ola_client.RegisterUniverse(self.universe, self.ola_client.REGISTER, self.on_dmx)
        # Fetch dmx values on startup
        self.ola_client.FetchDmx(self.universe, self.fetch_dmx)

    def do_activate(self):
        """
        # TODO: A virer, juste pour test
        self.patch.patch_empty()
        self.patch.add_output(10, 20)
        #self.patch.add_output(10, 30)
        self.patch.add_output(11, 21)
        self.patch.add_output(12, 22)
        self.patch.add_output(13, 23)
        self.patch.add_output(14, 24)
        self.patch.add_output(15, 25)
        self.patch.add_output(16, 26)
        self.patch.add_output(510, 10)
        """

        self.window = Window(self, self.patch)
        self.window.show_all()

        # TODO: A virer, juste pour tester le sequentiel
        cue = Cue(1, 1.0, [[1, 255], [2, 128], [10, 30], [11, 30], [12, 30], [0, 0], [0, 0], [0, 0]]*64, text="blabla 1.0", time_in=8, time_out=5)
        self.sequence.add_cue(cue)

        self.win_seq = SequentialWindow(self.sequence)
        self.win_seq.show_all()
        """
        for cue in self.sequence.cues:
            for i in cue.chanels:
                chanel = i[0]
                level = i[1]
                self.window.chanels[chanel - 1].level = level
                self.window.chanels[chanel - 1].queue_draw()
                self.dmxframe.set_level(chanel -1, level)
        self.ola_client.SendDmx(self.universe, self.dmxframe.dmx_frame)
        """

    def do_startup(self):
        Gtk.Application.do_startup(self)

        menu = self.setup_app_menu()
        self.set_app_menu(menu)

    def setup_app_menu(self):
        """ Setup application menu, return Gio.Menu """
        builder = Gtk.Builder()

        builder.add_from_resource('/org/gnome/OpenLightingConsole/app-menu.ui')

        menu = builder.get_object('app-menu')

        patchAction = Gio.SimpleAction.new('patch', None)
        patchAction.connect('activate', self._patch)
        self.add_action(patchAction)

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
            level = dmx[i]
            self.dmxframe.set_level(i, level)
            #print("Chanel:", chanel, "Level:", level)
            self.window.chanels[chanel-1].level = level
            self.window.chanels[chanel-1].queue_draw()

    def fetch_dmx(self, request, univ, dmx):
        for i in range(len(dmx)):
            chanel = self.patch.outputs[i]
            level = dmx[i]
            self.dmxframe.set_level(i, level)
            self.window.chanels[chanel-1].level = level
            self.window.chanels[chanel-1].queue_draw()

    def _patch(self, action, parameter):
        self.patchwindow = PatchWindow(self.patch, self.dmxframe, self.window)
        self.patchwindow.show_all()

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
