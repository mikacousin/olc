import select
import time
import threading
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
        """ All Channels """
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
        """ Channel """
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
        """ Through """
        if self.last_chan_selected:
            for chanel in range(int(self.last_chan_selected), int(self.keystring)):
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
            self.keystring = ""

    def keypress_plus(self):
        """ + """
        chanel = int(self.keystring)-1
        if chanel >= 0 and chanel < 512:
            self.app.window.chanels[chanel].clicked = True
            self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_minus(self):
        """ - """
        chanel = int(self.keystring)-1
        if chanel >= 0 and chanel < 512:
            self.app.window.chanels[chanel].clicked = False
            self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_Right(self):
        """ Level +1 of selected channels """
        for i in range(512):
            chanel = self.app.patch.outputs[i] - 1
            if self.app.window.chanels[chanel].clicked:
                level = self.app.dmxframe.get_level(i)
                if level < 255:
                    self.app.dmxframe.set_level(i, level+1)
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_Left(self):
        """ Level -1 of selected channels """
        for i in range(512):
            chanel = self.app.patch.outputs[i] - 1
            if self.app.window.chanels[chanel].clicked:
                level = self.app.dmxframe.get_level(i)
                if level > 0:
                    self.app.dmxframe.set_level(i, level-1)
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def keypress_equal(self):
        """ @ Level """
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
        """ Seq - """
        self.app.sequence.sequence_minus(self.app)

    def keypress_Down(self):
        """ Seq + """
        self.app.sequence.sequence_plus(self.app)

    def keypress_space(self):
        """ Go """
        self.app.sequence.sequence_go(self.app)

        """
        def update_progress(delay, delay_in, delay_out, i, position):
            # Mise a jour position des sliders
            self.app.win_seq.sequential.pos_x = ((800 - 32) / delay) * i # (800-32): en dur dans customwidgets
            self.app.win_seq.sequential.queue_draw()

            for chanel in range(512):

                old_level = self.app.sequence.cues[position].channels[chanel]

                # On boucle sur les mémoires et on revient à 0
                if position < self.app.sequence.last-1:
                    next_level = self.app.sequence.cues[position+1].channels[chanel]
                else:
                    next_level = self.app.sequence.cues[0].channels[chanel]
                    self.app.sequence.position = 0

                # Si le level augmente, on prend le temps de montée
                if next_level > old_level and i < delay_in:
                    level = int(((next_level - old_level+1) / delay_in) * i) + old_level
                # si le level descend, on prend le temps de descente
                elif next_level < old_level and i < delay_out:
                    level = old_level - abs(int(((next_level - old_level-1) / delay_out) * i))
                # sinon, la valeur est déjà bonne
                else:
                    level = next_level

                #print(old_level, next_level, level, chanel+1)

                outputs = self.app.patch.chanels[chanel]
                for output in outputs:
                    self.app.dmxframe.set_level(output-1, level)

            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

        def example_target():
            # Position dans le séquentiel
            position = self.app.sequence.position

            # On récupère les temps de monté et de descente dans la mémoire suivante
            t_in = self.app.sequence.cues[position+1].time_in
            t_out = self.app.sequence.cues[position+1].time_out

            # Quel est le temps le plus long
            if t_in > t_out:
                t_max = t_in
                t_min = t_out
            else:
                t_max = t_out
                t_min = t_in

            start_time = time.time() * 1000 # actual time in ms
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            # Boucle sur le temps de monté ou de descente (le plus grand)
            while i < delay:
                GLib.idle_add(update_progress, delay, delay_in, delay_out, i, position)    # Mise à jour des niveaux
                time.sleep(0.02)
                i = (time.time() * 1000) - start_time

            # Le Go est terminé
            self.app.sequence.on_go = False
            # On se positionne dans le séquentiel à la cue suivante
            position = self.app.sequence.position
            position += 1
            # Si elle existe
            if position < self.app.sequence.last-1:
                self.app.sequence.position += 1
                t_in = self.app.sequence.cues[position+1].time_in
                t_out = self.app.sequence.cues[position+1].time_out
                self.app.win_seq.sequential.time_in = t_in
                self.app.win_seq.sequential.time_out = t_out
                self.app.win_seq.sequential.pos_x = 0
                #self.app.win_seq.sequential.queue_draw()
                path = Gtk.TreePath.new_from_indices([position])
                self.app.win_seq.treeview.set_cursor(path, None, False)
                self.app.win_seq.grid.queue_draw()

                # Si la mémoire a un wait
                if self.app.sequence.cues[position+1].wait:
                    print("Auto Go after", self.app.sequence.cues[position+1].wait, "seconds")
                    time.sleep(self.app.sequence.cues[position+1].wait)
                    print("GO!")
                    self.keypress_space()

            # Sinon, on revient au début
            else:
                self.app.sequence.position = 0
                position = 0
                t_in = self.app.sequence.cues[position+1].time_in
                t_out = self.app.sequence.cues[position+1].time_out
                self.app.win_seq.sequential.time_in = t_in
                self.app.win_seq.sequential.time_out = t_out
                self.app.win_seq.sequential.pos_x = 0
                self.app.win_seq.sequential.queue_draw()
                print(position, self.app.sequence.cues[position].memory, self.app.sequence.cues[position].text)

        # Un go est dejà lancè ?
        if self.app.sequence.on_go:
            print("Go en cours !")
            self.app.sequence.on_go = False

        # On indique qu'un Go est en cours
        self.app.sequence.on_go = True
        # On utilise un thread pour ne pas tout bloquer pendant le changement de mémoire
        self.thread = threading.Thread(target=example_target)
        self.thread.daemon = True
        self.thread.start()
        """

    def keypress_w(self):

        def update_levels(delay, delay_in, delay_out, i, position):
            for channel in range(512):
                # On ne modifie que les channels présents dans le chaser
                if self.app.chasers[self.chaser].channels[channel] != 0:
                    # Niveau duquel on part
                    old_level = self.app.chasers[self.chaser].cues[position].channels[channel]
                    # Niveau dans le sequentiel
                    seq_level = self.app.sequence.cues[self.app.sequence.position].channels[channel]

                    if old_level < seq_level:
                        old_level = seq_level

                    # On boucle sur les mémoires et on revient au premier pas
                    if position < self.app.chasers[self.chaser].last-1:
                        next_level = self.app.chasers[self.chaser].cues[position+1].channels[channel]
                        if next_level < seq_level:
                            next_level = seq_level
                    else:
                        next_level = self.app.chasers[self.chaser].cues[1].channels[channel]
                        if next_level < seq_level:
                            next_level = seq_level
                        self.app.chasers[self.chaser].position = 1

                    # Si le level augmente, on prend le temps de montée
                    if next_level > old_level and i < delay_in:
                        level = int(((next_level - old_level+1) / delay_in) * i) + old_level
                    # si le level descend, on prend le temps de descente
                    elif next_level < old_level and i < delay_out:
                        level = old_level - abs(int(((next_level - old_level-1) / delay_out) * i))
                    # sinon, la valeur est déjà bonne
                    else:
                        level = next_level

                    #print(old_level, next_level, level, chanel+1)

                    outputs = self.app.patch.chanels[channel]
                    for output in outputs:
                        self.app.dmxframe.set_level(output-1, level)

                    #if self.app.chasers[0].cues[position].channels[channel] != 0:
                    #   print("Channel :", channel+1, "@", self.app.chasers[0].cues[position].channels[channel])

            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

        def time_loop():
            # On boucle sur les mémoires du chaser
            position = 0
            while self.app.chasers[self.chaser].run:
                #for position in range(self.app.chasers[0].last):
                    # On récupère les temps du pas suivant
                    if position != self.app.chasers[self.chaser].last-1:
                        t_in = self.app.chasers[self.chaser].cues[position+1].time_in
                        t_out = self.app.chasers[self.chaser].cues[position+1].time_out
                    else:
                        t_in = self.app.chasers[self.chaser].cues[1].time_in
                        t_out = self.app.chasers[self.chaser].cues[1].time_out

                    # Quel est le temps le plus long
                    if t_in > t_out:
                        t_max = t_in
                        t_min = t_out
                    else:
                        t_max = t_out
                        t_min = t_in

                    start_time = time.time() * 1000 # actual time in ms
                    delay = t_max * 1000
                    delay_in = t_in * 1000
                    delay_out = t_out * 1000
                    i = (time.time() * 1000) - start_time

                    # Boucle sur le temps de monté ou de descente (le plus grand)
                    while i < delay:
                        # Mise à jour des niveaux
                        GLib.idle_add(update_levels, delay, delay_in, delay_out, i, position)
                        time.sleep(0.02)
                        i = (time.time() * 1000) - start_time

                    position += 1
                    if position == self.app.chasers[self.chaser].last:
                        position = 1

        self.chaser = 1
        print("Chaser", self.chaser)

        # Bascule Marche/Arret
        if self.app.chasers[self.chaser].run:
            self.app.chasers[self.chaser].run = False
        else:
            self.app.chasers[self.chaser].run = True

        # On utilise un thread pour ne pas tout bloquer pendant le changement de mémoire
        thread = threading.Thread(target=time_loop)
        thread.daemon = True
        thread.start()

        """
        for i in range(1, self.app.chasers[0].last):
            print("Cue", self.app.chasers[0].cues[i].memory)
            print("In", self.app.chasers[0].cues[i].time_in)
            print("Out", self.app.chasers[0].cues[i].time_out)
            for channel in range(512):
                if self.app.chasers[0].cues[i].channels[channel] != 0:
                    print("Channel :", channel+1, "@", self.app.chasers[0].cues[i].channels[channel])
        """
