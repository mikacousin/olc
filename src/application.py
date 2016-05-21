import sys
import array
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, GObject
from ola import OlaClient

from olc.settings import Settings
from olc.window import Window
from olc.patchwindow import PatchWindow
from olc.dmx import Dmx, PatchDmx
from olc.cue import Cue
from olc.sequence import Sequence
from olc.sequentialwindow import SequentialWindow
from olc.group import Group
from olc.groupswindow import GroupsWindow
from olc.master import Master, MastersWindow
from olc.customwidgets import GroupWidget
from olc.osc import OscServer

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

        # To store settings
        self.settings = Settings.new()

        # TODO: Choisir son univers
        #self.universe = 0
        #self.universe = Gio.Application.get_default().settings.get_value('universe')
        self.universe = self.settings.get_int('universe')

        # Create patch (1:1)
        self.patch = PatchDmx()

        # Create OlaClient
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()
        self.ola_client.RegisterUniverse(self.universe, self.ola_client.REGISTER, self.on_dmx)

        # Create Main Sequential
        self.sequence = Sequence(1, self.patch)

        # Create List for Chasers
        self.chasers = []

        # Create List of Groups
        self.groups = []

        # Create List of Masters
        self.masters = []

    def do_activate(self):

        # Create Main Window
        self.window = Window(self, self.patch)
        self.window.show_all()

        # Create several DMX arrays
        self.dmx = Dmx(self.universe, self.patch, self.ola_client, self.sequence, self.masters, self.window)

        # Fetch dmx values on startup
        self.ola_client.FetchDmx(self.universe, self.fetch_dmx)

        self.win_seq = SequentialWindow(self, self.sequence)
        self.win_seq.show_all()
        self.sequence.window = self.win_seq

        self.win_groups = GroupsWindow(self, self.groups)
        #self.win_groups.show_all()

        # TODO: Test manual crossfade, must be deleted
        self.win_crossfade = CrossfadeWindow()
        self.win_crossfade.show_all()

        # Create and launch OSC server
        self.osc_server = OscServer(self.window)

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

        groupsAction = Gio.SimpleAction.new('groups', None)
        groupsAction.connect('activate', self._groups)
        self.add_action(groupsAction)

        mastersAction = Gio.SimpleAction.new('masters', None)
        mastersAction.connect('activate', self._masters)
        self.add_action(mastersAction)

        settingsAction = Gio.SimpleAction.new('settings', None)
        settingsAction.connect('activate', self._settings)
        self.add_action(settingsAction)

        shortcutsAction = Gio.SimpleAction.new('shortcuts', None)
        shortcutsAction.connect('activate', self._shortcuts)
        self.add_action(shortcutsAction)

        aboutAction = Gio.SimpleAction.new('about', None)
        aboutAction.connect('activate', self._about)
        self.add_action(aboutAction)

        quitAction = Gio.SimpleAction.new('quit', None)
        quitAction.connect('activate', self._exit)
        self.add_action(quitAction)

        return menu

    def on_dmx(self, dmxframe):
        #for i in range(512):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[output]
            level = dmxframe[output]
            self.dmx.frame[output] = level
            self.window.channels[channel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
            else:
                next_level = self.sequence.cues[0].channels[channel-1]
            self.window.channels[channel-1].next_level = next_level
            self.window.channels[channel-1].queue_draw()

    def fetch_dmx(self, request, univ, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[output]
            level = dmxframe[output]
            self.dmx.frame[output] = level
            self.window.channels[channel-1].level = level
            self.window.channels[channel-1].queue_draw()

    def _open(self, action, parameter):
        # create a filechooserdialog to open:
        # the arguments are: title of the window, parent_window, action,
        # (buttons, response)
        open_dialog = Gtk.FileChooserDialog("Open ASCII File", self.window,
                Gtk.FileChooserAction.OPEN,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text Files")
        filter_text.add_mime_type("text/plain")
        open_dialog.add_filter(filter_text)

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

            # TODO: Créer un fichier ascii.py pour alléger ce fichier
            # TODO: permettre de charger un fichier après un autre (tout réinitialiser)

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
                wait = False
                channels = False
                mem = False

                while True:

                    line, size = dstream.read_line(None)
                    line = str(line)[2:-1]
                    line = line.replace('\\t', '\t')
                    line = line.replace('\\r', '')

                    # Marker for end of file
                    if "ENDDATA" in line:
                        break

                    if line[:9] == "$SEQUENCE" or line[:9] == "$Sequence":
                        p = line[10:].split(" ")
                        if int(p[0]) < 2:
                            type_seq = "Normal"
                        else:
                            type_seq = "Chaser"
                            index_seq = int(p[0])
                            self.chasers.append(Sequence(index_seq, self.patch))
                        """
                        try:
                            test_type = p[1]
                            print("try:", p[1])
                            if p[1] == "0":
                                type_seq = "Normal"
                            elif p[1] == "1":
                                type_seq = "Chaser"
                                index_seq = int(p[0])
                                self.chasers.append(Sequence(index_seq, self.patch))
                                #print ("Sequence :", index_seq, "Type :", type_seq)
                        except:
                            print("except:", p[0])
                            if p[0] == "0":
                                type_seq = "Normal"
                            else:
                                type_seq = "Chaser"
                                index_seq = int(p[0])
                                self.chasers.append(Sequence(index_seq, self.patch))
                        """
                        #print ("Sequence :", p[0], "Type :", type_seq)
                        i = 1
                        flag_seq = True
                        flag_patch = False
                        flag_group = False

                    if flag_seq and type_seq == "Chaser":
                        if line[:4] == 'TEXT':
                            self.chasers[-1].text = line[5:]

                        if line[:4] == "$CUE":
                            in_cue = True
                            channels = array.array('B', [0] * 512)
                            i += 1
                            p = line[5:].split(" ")
                            seq = p[0]
                            mem = p[1]
                            #print ("CUE in Sequence", seq, "Memory", mem)

                        if in_cue:
                            if line[:4] == 'DOWN':
                                p = line[5:]
                                time = p.split(" ")[0]
                                if ":" in time:
                                    t_out = float(time.split(":")[0])*60 + float(time.split(":")[1])
                                else:
                                    t_out = float(time)
                                if t_out == 0:
                                    t_out = 0.1
                                #print("Time Out:", t_out)
                            if line[:2] == 'UP':
                                p = line[3:]
                                time = p.split(" ")[0]
                                if ":" in time:
                                    t_in = float(time.split(":")[0])*60 + float(time.split(":")[1])
                                else:
                                    t_in = float(time)
                                if t_in == 0:
                                    t_in = 0.1
                                #print("Time In:", t_in)
                            if line[:4] == 'CHAN':
                                #print ("        Chanels :")
                                p = line[5:].split(" ")
                                for q in p:
                                    r = q.split("/")
                                    if r[0] != "":
                                        channel = int(r[0])
                                        level = int(r[1][1:], 16)
                                        channels[channel-1] = level
                                        #print ("            ", r[0], "@", int(r[1][1:], 16))

                            if line == "":
                                #print("Fin de la Cue")

                                if not wait:
                                    wait = 0.0
                                if not txt:
                                    txt = ""
                                if not t_out:
                                    t_out = 5.0
                                if not t_in:
                                    t_in = 5.0
                                cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, wait=wait, text=txt)

                                self.chasers[-1].add_cue(cue)

                                in_cue = False
                                t_out = False
                                t_in = False
                                channels = False

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
                            mem = line[5:]

                        if in_cue:
                            if line[:4] == "TEXT":
                                #print ("        Text :", line[5:])
                                txt = line[5:]
                            if line[:6] == "$$TEXT" and not txt:
                                #print ("        $$Text :", line[7:])
                                txt = line[7:]
                            if (line[:12] == "$$PRESETTEXT" or line[:12] == "$$PresetText") and not txt:
                                #print ("        $$PrestText :", line[13:])
                                txt = line[13:]
                            if line[:4] == 'DOWN':
                                #print ("        Time Out :", line[5:])
                                p = line[5:]
                                time = p.split(" ")[0]
                                # Si on a un tps avec ":" on est en minutes
                                if ":" in time:
                                    t_out = float(time.split(":")[0])*60 + float(time.split(":")[1])
                                else:
                                    t_out = float(time)
                                if t_out == 0:
                                    t_out = 0.1
                            if line[:2] == 'UP':
                                #print ("        Time In :", line[3:])
                                p = line[3:]
                                time = p.split(" ")[0]
                                # Si on a un tps avec ":" on est en minutes
                                if ":" in time:
                                    t_in = float(time.split(":")[0])*60 + float(time.split(":")[1])
                                else:
                                    t_in = float(time)
                                if t_in == 0:
                                    t_in = 0.1
                            if line[:6] == '$$WAIT' or line[:6] == '$$Wait':
                                #print ("        Wait :", line[7:])
                                #wait = float(line[7:].split(" ")[0])
                                time = line[7:].split(" ")[0]
                                # Si on a un tps avec ":" on est en minutes
                                if ":" in time:
                                    wait = float(time.split(":")[0])*60 + float(time.split(":")[1])
                                else:
                                    wait = float(time)
                            if line[:4] == 'CHAN':
                                #print ("        Chanels :")
                                #p = line[5:-1].split(" ")
                                p = line[5:].split(" ")
                                for q in p:
                                    r = q.split("/")
                                    #print ("            ", r[0], "@", int(r[1][1:], 16))
                                    if r[0] != "":
                                        channel = int(r[0])
                                        level = int(r[1][1:], 16)
                                        channels[channel-1] = level
                            #if txt and t_out and t_in and channels:
                            if line == "":
                                #print("Fin Cue", mem)
                                if not wait:
                                    wait = 0.0
                                if not txt:
                                    txt = ""
                                if not t_out:
                                    t_out = 5.0
                                if not t_in:
                                    t_in = 5.0
                                cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, wait=wait, text=txt)

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
                                wait = False
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
                            if int(q[0]) <= 512 and int(r[0]) <=512:
                                #print ("Chanel :", q[0], "-> Output :", r[0], "@", r[1])
                                self.patch.add_output(int(q[0]), int(r[0]))
                                self.window.flowbox.invalidate_filter()
                            else:
                                print("Attention ! PLusieurs univers !!!")

                    if line[:6] == '$GROUP':
                        flag_seq = False
                        flag_patch = False
                        flag_group = True
                        #print ("Group :", line[7:])
                        channels = array.array('B', [0] * 512)
                        group_nb = int(line[7:])
                    if line[:5] == 'GROUP':
                        flag_seq = False
                        flag_patch = False
                        flag_group = True
                        #print ("Group :", line[6:])
                        channels = array.array('B', [0] * 512)
                        group_nb = int(line[6:])
                    if flag_group:
                        if line[:1] == "!":
                            flag_group = False
                        if line[:4] == 'TEXT':
                            #print ("    Text :", line[5:])
                            txt = line[5:]
                        if line[:4] == 'CHAN':
                            #print ("    Chanels :")
                            p = line[5:].split(" ")
                            for q in p:
                                r = q.split("/")
                                #print ("        ", r[0], "@", int(r[1][1:], 16))
                                if r[0] != "":
                                    channel = int(r[0])
                                    level = int(r[1][1:], 16)
                                    if channel <= 512:
                                        channels[channel-1] = level
                        if line == "":
                            #print("Group", group_nb, txt, "channels", channels)
                            self.groups.append(Group(group_nb, channels, txt))
                            flag_group = False
                            txt = ""

                    if line[:13] == '$MASTPAGEITEM':
                        #print("Master!")
                        p = line[14:].split(" ")
                        #print("Page :", p[0], "Master :", p[1], "Type :", p[2], "Contient :", p[3])
                        self.masters.append(Master(p[0], p[1], p[2], p[3], self.groups, self.chasers))

                fstream.close()

                # Set main window's title with the file name
                self.window.header.set_title(self.file.get_basename())
                # Set main window's subtitle
                subtitle = "Mem. : 0 - Next Mem. : "+self.sequence.cues[1].memory+" "+self.sequence.cues[1].text
                self.window.header.set_subtitle(subtitle)

                # Add an empty cue at the end
                cue = Cue(self.sequence.last+1, "0", text="Last Cue")
                self.sequence.add_cue(cue)

                # Redraw crossfade :
                # On se place au début de la séquence
                self.sequence.position = 0
                # On récupère les temps de la mémoire suivante
                t_in = self.sequence.cues[1].time_in
                t_out = self.sequence.cues[1].time_out
                t_wait = self.sequence.cues[1].wait
                self.win_seq.sequential.time_in = t_in
                self.win_seq.sequential.time_out = t_out
                self.win_seq.sequential.wait = t_wait

                # On met à jour la liste des mémoires
                self.win_seq.cues_liststore = Gtk.ListStore(str, str, str, str, str, str, str)
                # 2 lignes vides au début
                #for i in range(2):
                #    self.win_seq.cues_liststore.append(["", "", "", "", "", "", ""])
                for i in range(self.sequence.last):
                    # Si on a des entiers, on les affiche comme tels
                    if self.sequence.cues[i].wait.is_integer():
                        wait = str(int(self.sequence.cues[i].wait))
                        if wait == "0":
                            wait = ""
                    else:
                        wait = str(self.sequence.cues[i].wait)
                    if self.sequence.cues[i].time_out.is_integer():
                        t_out = int(self.sequence.cues[i].time_out)
                    else:
                        t_out = self.sequence.cues[i].time_out
                    if self.sequence.cues[i].time_in.is_integer():
                        t_in = int(self.sequence.cues[i].time_in)
                    else:
                        t_in = self.sequence.cues[i].time_in
                    self.win_seq.cues_liststore.append([str(i), str(self.sequence.cues[i].memory),
                            str(self.sequence.cues[i].text), wait,
                            str(t_out), str(t_in),
                            ""])
                self.win_seq.step_filter = self.win_seq.cues_liststore.filter_new()
                self.win_seq.step_filter.set_visible_func(self.win_seq.step_filter_func)

                self.win_seq.treeview.set_model(self.win_seq.cues_liststore)
                #self.win_seq.treeview.set_model(self.win_seq.step_filter)
                #self.win_seq.step_filter.refilter()

                path = Gtk.TreePath.new_from_indices([0])
                self.win_seq.treeview.set_cursor(path, None, False)

                self.win_seq.grid.queue_draw()

                # On met à jour la fenêtre des groupes
                self.win_groups.grps = []
                for i in range(len(self.groups)):
                    #print(self.groups[i].index, self.groups[i].text, self.groups[i].channels)
                    self.win_groups.grps.append(GroupWidget(self.win_groups, self.groups[i].index, self.groups[i].text, self.win_groups.grps))
                    self.win_groups.flowbox2.add(self.win_groups.grps[i])
                    """
                    self.win_groups.ad.append(Gtk.Adjustment(0, 0, 255, 1, 10, 0))
                    self.win_groups.scale.append(Gtk.Scale(orientation=Gtk.Orientation.VERTICAL,
                        adjustment=self.win_groups.ad[i]))
                    self.win_groups.scale[i].set_digits(0)
                    self.win_groups.scale[i].set_vexpand(True)
                    self.win_groups.scale[i].set_value_pos(Gtk.PositionType.BOTTOM)
                    self.win_groups.scale[i].set_inverted(True)
                    self.win_groups.scale[i].connect("value-changed", self.win_groups.scale_moved)
                    self.win_groups.label.append(Gtk.Label())
                    self.win_groups.label[i].set_text(self.groups[i].text)

                    if i == 0:
                        self.win_groups.grid.attach(self.win_groups.label[i], 0, 0, 1, 1)
                        self.win_groups.grid.attach_next_to(self.win_groups.scale[i],
                                self.win_groups.label[i], Gtk.PositionType.BOTTOM, 1, 1)
                    else:
                        self.win_groups.grid.attach_next_to(self.win_groups.label[i],
                                self.win_groups.label[i-1], Gtk.PositionType.RIGHT, 1, 1)
                        self.win_groups.grid.attach_next_to(self.win_groups.scale[i],
                                self.win_groups.label[i], Gtk.PositionType.BOTTOM, 1, 1)
                    """
                self.win_groups.flowbox1.invalidate_filter()


            except GObject.GError as e:
                print("Error: " + e.message)

        elif response_id == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.OPEN")

        # destroy the FileChooserDialog
        dialog.destroy()

    def _patch(self, action, parameter):
        self.patchwindow = PatchWindow(self.patch, self.dmx, self.window)
        self.patchwindow.show_all()

    def _groups(self, action, parameter):
        self.win_groups = GroupsWindow(self, self.groups)
        self.win_groups.show_all()

    def _masters(self, action, parameter):
        self.win_masters = MastersWindow(self, self.masters)
        self.win_masters.show_all()

    def _settings(self, actions, parameter):
        pass

    def _shortcuts(self, action, parameter):
        """
            Create Shortcuts Window
        """
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/OpenLightingConsole/Shortcuts.ui')
        self.shortcuts = builder.get_object('shortcuts-olc')
        #self.shortcuts.set_transient_for(self.window)
        self.shortcuts.show()

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
        # Stop Chasers Threads
        for i in range(len(self.chasers)):
            if self.chasers[i].run:
                self.chasers[i].run = False
                self.win_masters.thread.stop()
                self.win_masters.thread.join()
        self.quit()

#######################################################################
#TODO: Must be deleted, just for testing manual crosfade
#######################################################################


class CrossfadeWindow(Gtk.Window):
    def __init__(self):

        self.link = True

        Gtk.Window.__init__(self, title='Crossfade')
        self.set_default_size(200, 400)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)

        self.adA = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleA = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adA)
        self.scaleA.set_draw_value(False)
        self.scaleA.set_vexpand(True)
        #self.scaleA.set_value_pos(Gtk.PositionType.BOTTOM)
        self.scaleA.set_inverted(True)
        self.scaleA.connect('value-changed', self.scale_moved)

        self.adB = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleB = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adB)
        self.scaleB.set_draw_value(False)
        self.scaleB.set_vexpand(True)
        #self.scaleB.set_value_pos(Gtk.PositionType.BOTTOM)
        self.scaleB.set_inverted(True)
        self.scaleB.connect('value-changed', self.scale_moved)

        self.button = Gtk.CheckButton('Link crossfade')
        self.button.set_active(True)
        self.button.connect('toggled', self.on_button_toggled)

        self.grid.attach(self.button, 0, 0, 2, 1)
        self.grid.attach_next_to(self.scaleA, self.button, Gtk.PositionType.BOTTOM, 1, 1)
        self.grid.attach_next_to(self.scaleB, self.scaleA, Gtk.PositionType.RIGHT, 1, 1)

        self.add(self.grid)

    def on_button_toggled(self, button):
        if button.get_active():
            self.link = True
        else:
            self.link = False

    def scale_moved(self, scale):
        # TODO: Bug avec In monté puis après monter Out (les levels des channels tombent à 0)
        # TODO: Bug si on arrive sur un wait
        app = Gio.Application.get_default()
        level = scale.get_value()
        position = app.sequence.position

        if level != 255 and level != 0:
            app.sequence.on_go = True

        if self.link:
            # Update scales position
            if scale == self.scaleA:
                self.scaleB.set_value(level)
            else:
                self.scaleA.set_value(level)

            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return

            # Update sliders position
            delay = app.sequence.cues[position+1].time_out * 1000
            wait = app.sequence.cues[position+1].wait * 1000
            pos = (level / 255) * delay
            # Get SequentialWindow's width to place cursor
            allocation = app.win_seq.sequential.get_allocation()
            app.win_seq.sequential.pos_xA = ((allocation.width - 32) / delay) * pos
            app.win_seq.sequential.pos_xB = app.win_seq.sequential.pos_xA
            app.win_seq.sequential.queue_draw()
            # Update levels
            for output in range(512):

                channel = app.patch.outputs[output]

                old_level = app.sequence.cues[position].channels[channel-1]

                if channel:
                    if position < app.sequence.last - 1:
                        next_level = app.sequence.cues[position+1].channels[channel-1]
                    else:
                        next_level = app.sequence.cues[0].channels[channel-1]

                    if app.dmx.user[channel-1] != -1:
                        user_level = app.dmx.user[channel-1]
                        if next_level < user_level:
                            lvl = user_level - abs(int(((next_level - user_level) / (delay + wait)) * (pos - wait)))
                        elif next_level > user_level:
                            lvl = int(((next_level - user_level) / (delay + wait)) * (pos - wait)) + user_level
                        else:
                            lvl = user_level
                    else:
                        if next_level < old_level:
                            lvl = old_level - abs(int(((next_level - old_level) / (delay + wait)) * (pos - wait)))
                        elif next_level > old_level:
                            lvl = int(((next_level - old_level) / (delay + wait)) * (pos - wait)) + old_level
                        else:
                            lvl = old_level

                    app.dmx.sequence[channel-1] = lvl

            app.dmx.send()
        elif scale == self.scaleA:
            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return
            # Update slider A position
            delay = app.sequence.cues[position+1].time_out * 1000
            wait = app.sequence.cues[position+1].wait * 1000
            pos = (level / 255) * delay
            # Get SequentialWindow's width to place cursor
            allocation = app.win_seq.sequential.get_allocation()
            app.win_seq.sequential.pos_xA = ((allocation.width - 32) / delay) * pos
            app.win_seq.sequential.queue_draw()
            # Update levels
            for output in range(512):

                channel = app.patch.outputs[output]

                old_level = app.sequence.cues[position].channels[channel-1]

                if channel:
                    if position < app.sequence.last - 1:
                        next_level = app.sequence.cues[position+1].channels[channel-1]
                    else:
                        next_level = app.sequence.cues[0].channels[channel-1]

                    if app.dmx.user[channel-1] != -1:
                        user_level = app.dmx.user[channel-1]
                        if next_level < user_level:
                            lvl = user_level - abs(int(((next_level - user_level) / (delay + wait)) * (pos - wait)))
                        else:
                            lvl = user_level
                    else:
                        if next_level < old_level:
                            lvl = old_level - abs(int(((next_level - old_level) / (delay + wait)) * (pos - wait)))
                        else:
                            lvl = old_level

                    app.dmx.sequence[channel-1] = lvl

            app.dmx.send()
        elif scale == self.scaleB:
            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return
            # Update slider B position
            delay = app.sequence.cues[position+1].time_in * 1000
            wait = app.sequence.cues[position+1].wait * 1000
            pos = (level / 255) * delay
            # Get SequentialWindow's width to place cursor
            allocation = app.win_seq.sequential.get_allocation()
            app.win_seq.sequential.pos_xB = ((allocation.width - 32) / delay) * pos
            app.win_seq.sequential.queue_draw()
            # Update levels
            for output in range(512):

                channel = app.patch.outputs[output]

                old_level = app.sequence.cues[position].channels[channel-1]

                if channel:
                    if position < app.sequence.last - 1:
                        next_level = app.sequence.cues[position+1].channels[channel-1]
                    else:
                        next_level = app.sequence.cues[0].channels[channel-1]

                    if app.dmx.user[channel-1] != -1:
                        user_level = app.dmx.user[channel-1]
                        if next_level > user_level:
                            lvl = int(((next_level - user_level) / (delay + wait)) * (pos - wait)) + user_level
                        else:
                            lvl = user_level
                    else:
                        if next_level > old_level:
                            lvl = int(((next_level - old_level) / (delay + wait)) * (pos - wait)) + old_level
                        else:
                            lvl = old_level

                    app.dmx.sequence[channel-1] = lvl

            app.dmx.send()

        if self.scaleA.get_value() == 255 and self.scaleB.get_value() == 255:
            if app.sequence.on_go == True:
                app.sequence.on_go = False
                if self.scaleA.get_inverted():
                    self.scaleA.set_inverted(False)
                    self.scaleB.set_inverted(False)
                else:
                    self.scaleA.set_inverted(True)
                    self.scaleB.set_inverted(True)
                self.scaleA.set_value(0)
                self.scaleB.set_value(0)
                # Empty array of levels enter by user
                app.dmx.user = array.array('h', [-1] * 512)
                # Go to next cue
                position = app.sequence.position
                position += 1
                # If exist
                if position < app.sequence.last - 1:
                    app.sequence.position += 1
                    t_in = app.sequence.cues[position+1].time_in
                    t_out = app.sequence.cues[position+1].time_out
                    t_wait = app.sequence.cues[position+1].wait
                    app.win_seq.sequential.time_in = t_in
                    app.win_seq.sequential.time_out = t_out
                    app.win_seq.sequential.wait = t_wait
                    app.win_seq.sequential.pos_xA = 0
                    app.win_seq.sequential.pos_xB = 0
                    path = Gtk.TreePath.new_from_indices([position])
                    app.win_seq.treeview.set_cursor(path, None, False)
                    app.win_seq.grid.queue_draw()
                    # If Wait
                    if app.sequence.cues[position+1].wait:
                        app.window.keypress_space()
                # Else, we return to first cue
                else:
                    app.sequence.position = 0
                    position = 0
                    t_in = app.sequence.cues[position+1].time_in
                    t_out = app.sequence.cues[position+1].time_out
                    t_wait = app.sequence.cues[position+1].wait
                    app.win_seq.sequential.time_in = t_in
                    app.win_seq.sequential.time_out = t_out
                    app.win_seq.sequential.wait = t_wait
                    app.win_seq.sequential.pos_xA = 0
                    app.win_seq.sequential.pos_xB = 0
                    app.win_seq.sequential.queue_draw()

if __name__ == "__main__":
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
