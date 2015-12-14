import select
from gi.repository import Gtk, GObject, Gdk, GLib
from ola import OlaClient

from olc.customwidgets import ChanelWidget

class Window(Gtk.ApplicationWindow):

    def __init__(self, app, patch):

        self.app = app
        self.patch = patch

        Gtk.Window.__init__(self, title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1000)

        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("Fonctionne avec ola")
        self.header.props.show_close_button = True

        self.set_titlebar(self.header)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_filter_func(self.filter_func, None) # Fonction de filtrage

        self.keystring = ""
        self.last_chan_selected = ""

        #self.grid = []
        self.chanels = []
        #self.levels = []
        #self.progressbar = []

        for i in range(512):
            """
            # Création de la grille
            self.grid.append(Gtk.Grid())
            #self.grid[i].set_column_homogeneous(True)
            self.flowbox.add(self.grid[i])

            # Création de la liste des outputs
            self.chanels.append(Gtk.ToggleButton(str(i+1))) # Le numéro du chanel comme label
            self.chanels[i].connect("toggled", self.on_button_toggled, str(i+1))

            # Création de la liste des niveaux
            self.levels.append(Gtk.Label(label=" 0 "))
            self.levels[i].set_justify(Gtk.Justification.CENTER)

            # Création de la liste des barres de progression
            self.progressbar.append(Gtk.ProgressBar())
            self.progressbar[i].set_orientation(Gtk.Orientation.VERTICAL)
            self.progressbar[i].set_inverted(1)

            # On place nos éléments dans la grille
            self.grid[i].add(self.chanels[i])
            self.grid[i].attach_next_to(self.levels[i], self.chanels[i], Gtk.PositionType.BOTTOM, 1, 1)
            self.grid[i].attach_next_to(self.progressbar[i], self.chanels[i], Gtk.PositionType.RIGHT, 1, 2)
            """
            self.chanels.append(ChanelWidget(i+1, 0, 0))
            self.flowbox.add(self.chanels[i])

        self.scrolled.add(self.flowbox)
        self.add(self.scrolled)

        self.timeout_id = GObject.timeout_add(50, self.on_timeout, None)

        self.connect('key_press_event', self.on_key_press_event)

    def filter_func(self, child, user_data):
        i = child.get_index()
        for j in range(len(self.patch.chanels[i])):
            #print("Chanel:", i+1, "Output:", self.patch.chanels[i][j])
            if self.patch.chanels[i][j] != 0:
                return child
            else:
                return False

    def on_button_toggled(self, button, name):
        if button.get_active():
            state = "on"
        else:
            state = "off"

    def on_timeout(self, user_data):
        readable, writable, exceptional = select.select([self.app.sock], [], [], 0)
        if readable:
            self.app.ola_client.SocketReady()
        return True

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print (keyname)
        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname =="6" or keyname == "7" or keyname =="8" or keyname == "9" or keyname =="0":
            self.keystring += keyname
        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_a(self):
        for i in range(512):
            level = self.app.dmxframe.get_level(i)
            chanel = self.app.patch.outputs[i] - 1
            if level > 0:
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
            else:
                self.app.window.chanels[chanel].clicked = False
                self.app.window.chanels[chanel].queue_draw()

    def keypress_c(self):
        if self.keystring == "" or self.keystring == "0":
            for i in range(512):
                chanel = self.app.patch.outputs[i] - 1
                self.app.window.chanels[chanel].clicked = False
                self.app.window.chanels[chanel].queue_draw()
                self.last_chan_selected = ""
        else:
            chanel = int(self.keystring)-1
            if chanel >= 0 and chanel < 512:
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
                self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_greater(self):
        if self.last_chan_selected:
            for chanel in range(int(self.last_chan_selected), int(self.keystring)):
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
            self.keystring = ""

    def keypress_plus(self):
        chanel = int(self.keystring)-1
        if chanel >= 0 and chanel < 512:
            self.app.window.chanels[chanel].clicked = True
            self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_minus(self):
        chanel = int(self.keystring)-1
        if chanel >= 0 and chanel < 512:
            self.app.window.chanels[chanel].clicked = False
            self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_Right(self):
        for i in range(512):
            chanel = self.app.patch.outputs[i] - 1
            if self.app.window.chanels[chanel].clicked:
                level = self.app.dmxframe.get_level(i)
                if level < 255:
                    self.app.dmxframe.set_level(i, level+1)
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_Left(self):
        for i in range(512):
            chanel = self.app.patch.outputs[i] - 1
            if self.app.window.chanels[chanel].clicked:
                level = self.app.dmxframe.get_level(i)
                if level > 0:
                    self.app.dmxframe.set_level(i, level-1)
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_equal(self):
        for i in range(512):
            chanel = self.app.patch.outputs[i] - 1
            if self.app.window.chanels[chanel].clicked:
                level = int(self.keystring)
                if level >= 0 and level <= 255:
                    self.app.dmxframe.set_level(i, level)
        self.keystring = ""
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_Escape(self):
        self.keystring = ""

    def keypress_Up(self):
        position = self.app.sequence.position
        position -= 1
        if position >= 0:
            self.app.sequence.position -= 1
            self.app.win_seq.sequential.pos_x = 0
            t_in = self.app.sequence.cues[position].time_in
            t_out = self.app.sequence.cues[position].time_out
            self.app.win_seq.sequential.time_in = t_in
            self.app.win_seq.sequential.time_out = t_out
            self.app.win_seq.sequential.queue_draw()
            for chanel in range(512):
                level = self.app.sequence.cues[position].chanels.dmx_frame[chanel]
                self.app.dmxframe.set_level(chanel, level)
            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_Down(self):
        position = self.app.sequence.position
        position += 1
        if position <= 2:
            self.app.sequence.position += 1
            self.app.win_seq.sequential.pos_x = 0
            t_in = self.app.sequence.cues[position].time_in
            t_out = self.app.sequence.cues[position].time_out
            self.app.win_seq.sequential.time_in = t_in
            self.app.win_seq.sequential.time_out = t_out
            self.app.win_seq.sequential.queue_draw()
            for chanel in range(512):
                level = self.app.sequence.cues[position].chanels.dmx_frame[chanel]
                self.app.dmxframe.set_level(chanel, level)
            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_space(self):
        position = self.app.sequence.position
        t_in = self.app.sequence.cues[position].time_in
        t_out = self.app.sequence.cues[position].time_out
        if t_in > t_out:
            t_max = t_in
            t_min = t_out
        else:
            t_max = t_out
            t_min = t_in

        import threading
        import time

        def update_progress(i):
            self.app.win_seq.sequential.pos_x = i
            self.app.win_seq.sequential.queue_draw()
            for chanel in range(512):
                old_level = self.app.sequence.cues[position].chanels.dmx_frame[chanel]
                if position < 2:
                    next_level = self.app.sequence.cues[position+1].chanels.dmx_frame[chanel]
                else:
                    next_level = self.app.sequence.cues[0].chanels.dmx_frame[chanel]
                if next_level > old_level:
                    level = int(((next_level - old_level+1) / (800-32)) * i) + old_level
                else:
                    level = int(((next_level - old_level-1) / (800-32)) * i) + old_level
                self.app.dmxframe.set_level(chanel, level)
            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

        def example_target():
            t_sleep = t_max / (800 - 32)
            for i in range(800 - 32): # Taille définit dans customwidgets
                GLib.idle_add(update_progress, i)
                time.sleep(t_sleep)
            time.sleep(t_sleep)
            position = self.app.sequence.position
            position += 1
            if position <= 2:
                self.app.sequence.position += 1
                t_in = self.app.sequence.cues[position].time_in
                t_out = self.app.sequence.cues[position].time_out
                self.app.win_seq.sequential.time_in = t_in
                self.app.win_seq.sequential.time_out = t_out
                self.app.win_seq.sequential.pos_x = 0
                self.app.win_seq.sequential.queue_draw()

        thread = threading.Thread(target=example_target)
        thread.daemon = True
        thread.start()

    def keypress_w(self):
        self.app.win_seq.sequential.pos_x -= 1
        self.app.win_seq.sequential.queue_draw()

    def keypress_x(self):
        self.app.win_seq.sequential.pos_x += 1
        self.app.win_seq.sequential.queue_draw()

    def keypress_W(self):
        self.app.win_seq.sequential.pos_x -= 10
        self.app.win_seq.sequential.queue_draw()

    def keypress_X(self):
        self.app.win_seq.sequential.pos_x += 10
        self.app.win_seq.sequential.queue_draw()
