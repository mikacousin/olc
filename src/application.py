import sys
import array
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, GObject
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

        self.window = Window(self, self.patch)
        self.window.show_all()

        # TODO: A virer, juste pour tester le sequentiel
        """
        dmx = DmxFrame()
        for i in range(512):
            dmx.set_level(i, int(i/2))
        cue = Cue(1, 1.0, dmx, text="blabla 1.0", time_in=5, time_out=20)
        self.sequence.add_cue(cue)
        dmx = DmxFrame()
        for i in range(512):
            dmx.set_level(i, 30)
        cue = Cue(2, 2.0, dmx, text="2.0", time_in=1, time_out=1)
        self.sequence.add_cue(cue)
        """

        self.win_seq = SequentialWindow(self, self.sequence)
        self.win_seq.show_all()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        menu = self.setup_app_menu()
        self.set_app_menu(menu)

    def setup_app_menu(self):
        """ Setup application menu, return Gio.Menu """
        builder = Gtk.Builder()

        builder.add_from_resource('/org/gnome/OpenLightingConsole/app-menu.ui')

        menu = builder.get_object('app-menu')

        openAction = Gio.SimpleAction.new('open', None)
        openAction.connect('activate', self._open)
        self.add_action(openAction)

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
        #for i in range(512):
        for i in range(len(dmx)):
            chanel = self.patch.outputs[i]
            level = dmx[i]
            self.dmxframe.set_level(i, level)
            self.window.chanels[chanel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[chanel-1]
            else:
                next_level = self.sequence.cues[0].channels[chanel-1]
            self.window.chanels[chanel-1].next_level = next_level
            self.window.chanels[chanel-1].queue_draw()

    def fetch_dmx(self, request, univ, dmx):
        for i in range(len(dmx)):
            chanel = self.patch.outputs[i]
            level = dmx[i]
            self.dmxframe.set_level(i, level)
            self.window.chanels[chanel-1].level = level
            self.window.chanels[chanel-1].queue_draw()

    def _open(self, action, parameter):
        # create a filechooserdialog to open:
        # the arguments are: title of the window, parent_window, action,
        # (buttons, response)
        open_dialog = Gtk.FileChooserDialog("Open ASCII File", self.window,
                Gtk.FileChooserAction.OPEN,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))

        # not only local files can be selected in the file selector
        open_dialog.set_local_only(False)
        # dialog always on top of the textview window
        open_dialog.set_modal(True)
        # connect the dialog with the callback function open_response_cb()
        open_dialog.connect("response", self.open_response_cb)
        # show the dialog
        open_dialog.show()

    def open_response_cb(self, dialog, response_id):
        # callback function for the dialog open_dialog
        open_dialog = dialog

        # if response is "ACCEPT" (the button "Open" has been clicked)
        if response_id == Gtk.ResponseType.ACCEPT:
            # self.file is the file that we get from the FileChooserDialog
            self.file = open_dialog.get_file()

            try:
                fstream = self.file.read(None)
                dstream = Gio.DataInputStream.new(fstream)

                flag_seq = False
                in_cue = False
                flag_patch = False
                flag_group = False

                type_seq = "Normal"
                txt = False
                t_in = False
                t_out = False
                channels = False
                mem = False

                while True:

                    line, size = dstream.read_line(None)
                    line = str(line)[2:-1]
                    line = line.replace('\\t', '\t')

                    # Marker for end of file
                    if "ENDDATA" in line:
                        break

                    if line[:9] == "$SEQUENCE" or line[:9] == "$Sequence":
                        p = line[10:].split(" ")
                        if p[1] == "0":
                            type_seq = "Normal"
                        elif p[1] == "1":
                            type_seq = "Chaser"
                        print ("Sequence :", p[0], "Type :", type_seq)
                        i = 1
                        flag_seq = True
                        flag_patch = False
                        flag_group = False
                    if flag_seq and type_seq == "Normal":
                        if line[:0] == "!":
                            flag_seq = False
                            print(line)
                        if line[:3] == "CUE":
                            in_cue = True
                            channels = array.array('B', [0] * 512)
                            i += 1
                            #print ("        Mémoire :", line[4:])
                            mem = line[4:]
                        if line[:4] == "$CUE":
                            in_cue = True
                            channels = array.array('B', [0] * 512)
                            i += 1
                            #print ("        Mémoire :", line[5:])
                            mem = line[4:]

                        if in_cue:
                            if line[:4] == "TEXT":
                                #print ("        Text :", line[5:])
                                txt = line[5:]
                            if line[:6] == "$$TEXT":
                                #print ("        $$Text :", line[7:])
                                txt = line[7:]
                            if line[:12] == "$$PRESETTEXT":
                                #print ("        $$PrestText :", line[13:])
                                txt = line[13:]
                            if line[:4] == 'DOWN':
                                #print ("        Time Out :", line[5:])
                                p = line[5:]
                                t_out = float(p.split(" ")[0])
                                if t_out == 0:
                                    t_out = 0.1
                            if line[:2] == 'UP':
                                #print ("        Time In :", line[3:])
                                p = line[3:]
                                t_in = float(p.split(" ")[0])
                                if t_in == 0:
                                    t_in = 0.1
                            if line[:6] == '$$WAIT':                # TODO
                                #print ("        Wait :", line[7:])
                                wait = float(line[7:].split(" ")[0])
                            if line[:4] == 'CHAN':
                                #print ("        Chanels :")
                                p = line[5:-1].split(" ")
                                for q in p:
                                    r = q.split("/")
                                    #print ("            ", r[0], "@", int(r[1][1:], 16))
                                    chanel = int(r[0])
                                    level = int(r[1][1:], 16)
                                    channels[chanel-1] = level
                            #if txt and t_out and t_in and channels:
                            if line == "":
                                #print("Fin Cue", mem)
                                cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, text=txt)

                                #print("StepId :", cue.index, "Memory :", cue.memory)
                                #print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
                                #print("Text :", cue.text)
                                #print("")
                                #for channel in range(512):
                                #    print("Channel :", channel+1, "@", cue.channels[channel])

                                self.sequence.add_cue(cue)
                                in_cue = False
                                txt = False
                                t_out = False
                                t_in = False
                                mem = False
                                channels = False

                    if line[:11] == 'CLEAR PATCH':
                        flag_seq = False
                        flag_patch = True
                        flag_group = False
                         #print ("\nPatch :")
                        self.patch.patch_empty()    # Empty patch
                        self.window.flowbox.invalidate_filter()
                    if flag_patch:
                        if line[:0] == "!":
                            flag_patch = False
                    if line[:7] == 'PATCH 1':
                        for p in line[8:-1].split(" "):
                            q = p.split("<")
                            r = q[1].split("@")
                             #print ("Chanel :", q[0], "-> Output :", r[0], "@", r[1])
                            self.patch.add_output(int(q[0]), int(r[0]))
                            self.window.flowbox.invalidate_filter()

                    if line[:6] == '$GROUP':
                        flag_seq = False
                        flag_patch = False
                        flag_group = True
                        print ("Group :", line[7:])
                    if line[:5] == 'GROUP':
                        flag_seq = False
                        flag_patch = False
                        flag_group = True
                        print ("Group :", line[6:])
                    if flag_group:
                        if line[:1] == "!":
                            flag_group = False
                        if line[:4] == 'TEXT':
                            print ("    Text :", line[5:])
                        if line[:4] == 'CHAN':
                            print ("    Chanels :")
                            p = line[5:-1].split(" ")
                            for q in p:
                                r = q.split("/")
                                print ("        ", r[0], "@", int(r[1][1:], 16))

                fstream.close()

                # Redraw crossfade :
                # On se place au début de la séquence
                self.sequence.position = 0
                # On récupère les temps de la mémoire suivante
                t_in = self.sequence.cues[1].time_in
                t_out = self.sequence.cues[1].time_out
                self.win_seq.sequential.time_in = t_in
                self.win_seq.sequential.time_out = t_out
                # On redessine
                self.win_seq.sequential.queue_draw()

            except GObject.GError as e:
                print("Error: " + e.message)

        elif response_id == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.OPEN")

        # destroy the FileChooserDialog
        dialog.destroy()

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
