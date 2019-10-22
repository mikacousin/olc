import array
import threading
import time
from gi.repository import Gtk, GLib, Gio, Gdk, Pango

from olc.define import NB_UNIVERSES
from olc.cue import Cue
from olc.dmx import PatchDmx
from olc.customwidgets import ChannelWidget

class Sequence(object):
    def __init__(self, index, patch, type_seq="Normal", text=""):
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.cues = []
        self.position = 0
        self.last = 0
        # Flag pour savoir si on a un Go en cours
        self.on_go = False
        # Liste des channels présent dans le sequentiel
        self.channels = array.array('B', [0] * 512)
        # Flag for chasers
        self.run = False
        # Thread for chasers
        self.thread = None
        # Pour accéder à la fenêtre du séquentiel
        self.window = None
        # On a besoin de connaitre le patch
        self.patch = patch

        # create an empty cue 0
        cue = Cue(1, "0.0", text="Start")
        self.add_cue(cue)

    def add_cue(self, cue):
        self.cues.append(cue)
        self.last = cue.index
        # On enregistre la liste des circuits présents dans la mémoire
        for i in range(512):
            if cue.channels[i] != 0:
                self.channels[i] = 1  # Si présent on le note

    def sequence_plus(self, app):
        self.app = app

        if self.on_go:
            # Stop actual Thread
            self.thread.stop()
            self.on_go = False
            # Stop at the end
            if self.position > self.last - 3:
                self.position = self.last - 3

        position = self.position
        position += 1
        if position < self.last-1:     # Stop on the last cue
            self.position += 1
            t_in = self.cues[position+1].time_in
            t_out = self.cues[position+1].time_out
            d_in = self.cues[position+1].delay_in
            d_out = self.cues[position+1].delay_out
            t_wait = self.cues[position+1].wait
            self.window.sequential.total_time = self.cues[position+1].total_time
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            self.window.sequential.delay_in = d_in
            self.window.sequential.delay_out = d_out
            self.window.sequential.wait = t_wait
            self.window.sequential.channel_time = self.cues[position+1].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Update ui
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position+1][9] = "#232729"
            self.app.window.cues_liststore1[position+2][9] = "#997004"
            self.app.window.cues_liststore1[position+3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position+3][10] = Pango.Weight.HEAVY  # Next Cue in Bold
            self.window.step_filter1.refilter()
            self.window.step_filter2.refilter()
            path = Gtk.TreePath.new_first()
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)
            self.window.seq_grid.queue_draw()

            # Set main window's subtitle
            subtitle = "Mem. : "+self.cues[position].memory+" "+self.cues[position].text+" - Next Mem. : "+self.cues[position+1].memory+" "+self.cues[position+1].text
            self.app.window.header.set_subtitle(subtitle)

            # On vide le tableau des valeurs entrées par l'utilisateur
            self.app.dmx.user = array.array('h', [-1] * 512)

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = self.patch.outputs[univ][output]
                    if channel:
                        level = self.cues[position].channels[channel-1]
                        self.app.dmx.sequence[channel-1] = level

            self.app.dmx.send()

    def sequence_minus(self, app):
        self.app = app

        if self.on_go:
            # Stop actual Thread
            self.thread.stop()
            self.on_go = False
            # Stop at the begining
            if self.position < 1:
                self.position = 1

        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1
            t_in = self.cues[position+1].time_in   # Always use times for next cue
            t_out = self.cues[position+1].time_out
            d_in = self.cues[position+1].delay_in
            d_out = self.cues[position+1].delay_out
            t_wait = self.cues[position+1].wait
            self.window.sequential.total_time = self.cues[position+1].total_time
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            self.window.sequential.delay_in = d_in
            self.window.sequential.delay_out = d_out
            self.window.sequential.wait = t_wait
            self.window.sequential.channel_time = self.cues[position+1].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Set main window's subtitle
            subtitle = "Mem. : "+self.cues[position].memory+" "+self.cues[position].text+" - Next Mem. : "+self.cues[position+1].memory+" "+self.cues[position+1].text
            self.app.window.header.set_subtitle(subtitle)

            # Update ui
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position+1][9] = "#232729"
            self.app.window.cues_liststore1[position+2][9] = "#997004"
            self.app.window.cues_liststore1[position+3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position+3][10] = Pango.Weight.HEAVY  # Next Cue in Bold
            self.window.step_filter1.refilter()
            self.window.step_filter2.refilter()
            path = Gtk.TreePath.new_first()
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)
            self.window.seq_grid.queue_draw()

            # On vide le tableau des valeurs entrées par l'utilisateur
            self.app.dmx.user = array.array('h', [-1] * 512)

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = self.patch.outputs[univ][output]
                    if channel:
                        level = self.cues[position].channels[channel-1]
                        self.app.dmx.sequence[channel-1] = level

            self.app.dmx.send()

    def sequence_goto(self, app, keystring):
        """ Jump to cue number """
        self.app = app
        old_pos = self.app.sequence.position
        # Scan all cues
        for i in range(len(self.cues)):
            # Until we find the good one
            if float(self.cues[i].memory) == float(keystring):
                # Position to the one just before
                self.app.sequence.position = i - 1
                position = self.app.sequence.position
                # Redraw Sequential window with new times
                t_in = self.app.sequence.cues[position+1].time_in
                t_out = self.app.sequence.cues[position+1].time_out
                d_in = self.cues[position+1].delay_in
                d_out = self.cues[position+1].delay_out
                t_wait = self.app.sequence.cues[position+1].wait
                self.window.sequential.total_time = self.cues[position+1].total_time
                self.app.window.sequential.time_in = t_in
                self.app.window.sequential.time_out = t_out
                self.window.sequential.delay_in = d_in
                self.window.sequential.delay_out = d_out
                self.app.window.sequential.wait = t_wait
                self.window.sequential.channel_time = self.cues[position+1].channel_time
                self.app.window.sequential.pos_xA = 0
                self.app.window.sequential.pos_xB = 0

                # Update ui
                self.app.window.cues_liststore1[old_pos][9] = "#232729"
                self.app.window.cues_liststore1[position][9] = "#232729"
                self.app.window.cues_liststore1[position+1][9] = "#232729"
                self.app.window.cues_liststore1[position+2][9] = "#997004"
                self.app.window.cues_liststore1[position+3][9] = "#555555"
                self.app.window.cues_liststore1[old_pos][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position+1][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position+2][10] = Pango.Weight.HEAVY
                self.app.window.cues_liststore1[position+3][10] = Pango.Weight.HEAVY
                self.app.window.step_filter1.refilter()
                self.app.window.step_filter2.refilter()
                path = Gtk.TreePath.new_from_indices([0])
                self.app.window.treeview1.set_cursor(path, None, False)
                self.app.window.treeview2.set_cursor(path, None, False)
                self.app.window.seq_grid.queue_draw()

                # Launch Go
                self.sequence_go(None, None)
                break

    def sequence_go(self, action, param):
        self.app = Gio.Application.get_default()
        # Si un Go est en cours, on bascule sur la mémoire suivante
        if self.on_go:
            # Stop actual Thread
            self.thread.stop()
            self.thread.join()
            self.on_go = False
            # Launch another Go
            self.sequence_go(None, None)
        else:
            # On indique qu'un Go est en cours
            self.on_go = True
            self.thread = ThreadGo(self.app)
            self.thread.start()

# Objet Thread pour gérer les Go
class ThreadGo(threading.Thread):
    def __init__(self, app, name=''):
        threading.Thread.__init__(self)
        self.app = app
        self.name = name
        self._stopevent = threading.Event()
        # To save dmx levels when user send Go
        self.dmxlevels = []
        for univ in range(NB_UNIVERSES):
            self.dmxlevels.append(array.array('B', [0] * 512))

    def run(self):
        # Position dans le séquentiel
        position = self.app.sequence.position

        # Levels when Go is sent
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.dmxlevels[univ][output] = self.app.dmx.frame[univ][output]

        # If sequential is empty, just return
        if self.app.sequence.last == 0:
            return

        # On récupère les temps de montée et de descente de la mémoire suivante
        t_in = self.app.sequence.cues[position+1].time_in
        t_out = self.app.sequence.cues[position+1].time_out
        d_in = self.app.sequence.cues[position+1].delay_in
        d_out = self.app.sequence.cues[position+1].delay_out
        t_wait = self.app.sequence.cues[position+1].wait
        t_total = self.app.sequence.cues[position+1].total_time

        # Quel est le temps le plus long
        if t_in + d_in > t_out + d_out:
            t_max = t_in + d_in
            t_min = t_out + d_out
        else:
            t_max = t_out + d_out
            t_min = t_in + d_in

        t_max = t_max + t_wait
        t_min = t_min + t_wait

        start_time = time.time() * 1000  # actual time in ms
        delay = t_total * 1000
        delay_in = t_in * 1000
        delay_out = t_out * 1000
        delay_wait = t_wait * 1000
        delay_d_in = d_in * 1000
        delay_d_out = d_out * 1000
        i = (time.time() * 1000) - start_time

        # Boucle sur le temps de montée ou de descente (le plus grand)
        while i < delay and not self._stopevent.isSet():
            # Update DMX levels
            self.update_levels(delay, delay_in, delay_out, delay_d_in, delay_d_out, delay_wait, i, position)
            # Sleep for 20ms TODO: find godd value for sleeping
            time.sleep(0.02)
            i = (time.time() * 1000) - start_time

        # Stop thread if we send stop message
        if self._stopevent.isSet():
            return

        # Finish to load memory
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = self.app.patch.outputs[univ][output]
                if channel:
                    if position < self.app.sequence.last - 1:
                        level = self.app.sequence.cues[position+1].channels[channel-1]
                    else:
                        level = self.app.sequence.cues[0].channels[channel-1]
                    self.app.dmx.sequence[channel-1] = level
        self.app.dmx.send()

        # Le Go est terminé
        self.app.sequence.on_go = False
        # On vide le tableau des valeurs entrées par l'utilisateur
        self.app.dmx.user = array.array('h', [-1] * 512)

        # On se positionne à la mémoire suivante
        position = self.app.sequence.position
        position += 1

        # Si elle existe
        if position < self.app.sequence.last-1:
            self.app.sequence.position += 1
            t_in = self.app.sequence.cues[position+1].time_in
            t_out = self.app.sequence.cues[position+1].time_out
            d_in = self.app.sequence.cues[position+1].delay_in
            d_out = self.app.sequence.cues[position+1].delay_out
            t_wait = self.app.sequence.cues[position+1].wait
            self.app.window.sequential.total_time = self.app.sequence.cues[position+1].total_time
            self.app.window.sequential.time_in = t_in
            self.app.window.sequential.time_out = t_out
            self.app.window.sequential.delay_in = d_in
            self.app.window.sequential.delay_out = d_out
            self.app.window.sequential.wait = t_wait
            self.app.window.sequential.channel_time = self.app.sequence.cues[position+1].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Set main window's subtitle
            subtitle = "Mem. : "+self.app.sequence.cues[position].memory+" "+self.app.sequence.cues[position].text+" - Next Mem. : "+self.app.sequence.cues[position+1].memory+" "+self.app.sequence.cues[position+1].text

            # Update Gtk in the main thread
            GLib.idle_add(self.update_ui, position, subtitle)

            # Si la mémoire a un Wait
            if self.app.sequence.cues[position+1].wait:
                self.app.sequence.sequence_go(None, None)

        # Sinon, on revient au début
        else:
            self.app.sequence.position = 0
            position = 0
            t_in = self.app.sequence.cues[position+1].time_in
            t_out = self.app.sequence.cues[position+1].time_out
            d_in = self.app.sequence.cues[position+1].delay_in
            d_out = self.app.sequence.cues[position+1].delay_out
            t_wait = self.app.sequence.cues[position+1].wait
            self.app.window.sequential.total_time = self.app.sequence.cues[position+1].total_time
            self.app.window.sequential.time_in = t_in
            self.app.window.sequential.time_out = t_out
            self.app.window.sequential.delay_in = d_in
            self.app.window.sequential.delay_out = d_out
            self.app.window.sequential.wait = t_wait
            self.app.window.sequential.channel_time = self.app.sequence.cues[position+1].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Set main window's subtitle
            subtitle = "Mem. : "+self.app.sequence.cues[position].memory+" "+self.app.sequence.cues[position].text+" - Next Mem. : "+self.app.sequence.cues[position+1].memory+" "+self.app.sequence.cues[position+1].text

            # Update Gtk in the main thread
            GLib.idle_add(self.update_ui, position, subtitle)

    def stop(self):
        self._stopevent.set()

    def update_levels(self, delay, delay_in, delay_out, delay_d_in, delay_d_out, delay_wait, i, position):
        # Update sliders position
        # Get width of the sequential widget to place cursors correctly
        allocation = self.app.window.sequential.get_allocation()
        self.app.window.sequential.pos_xA = ((allocation.width - 32) / delay) * i
        self.app.window.sequential.pos_xB = ((allocation.width - 32) / delay) * i
        GLib.idle_add(self.app.window.sequential.queue_draw)

        # On attend que le temps d'un éventuel wait soit passé pour changer les levels
        if i > delay_wait:

            for univ in range(NB_UNIVERSES):

                for output in range(512):

                    # On utilise les valeurs dmx comme valeurs de départ
                    old_level = self.dmxlevels[univ][output]

                    channel = self.app.patch.outputs[univ][output]

                    if channel:

                        channel_time = self.app.sequence.cues[position+1].channel_time

                        # If channel is in a channel time
                        # TODO: If Time is 0, use TimeIn or TimeOut
                        if channel in channel_time:
                            #print(channel_time[channel].delay, channel_time[channel].time)
                            ct_delay = channel_time[channel].delay * 1000
                            ct_time = channel_time[channel].time * 1000
                            if i > ct_delay+delay_wait and i < ct_delay+ct_time+delay_wait:
                                next_level = self.app.sequence.cues[position+1].channels[channel-1]
                                if next_level > old_level:
                                    level = int(((next_level - old_level+1) / ct_time) * (i-ct_delay-delay_wait)) + old_level
                                else:
                                    level = old_level - abs(int(((next_level - old_level-1) / ct_time) * (i-ct_delay-delay_wait)))
                                self.app.dmx.sequence[channel-1] = level
                        # Else channel is normal
                        else:
                            # On boucle sur les mémoires et on revient à 0
                            if position < self.app.sequence.last - 1:
                                next_level = self.app.sequence.cues[position+1].channels[channel-1]
                            else:
                                next_level = self.app.sequence.cues[0].channels[channel-1]
                                self.app.sequence.position = 0

                            # Si le level augmente, on prends le temps de montée
                            if next_level > old_level and i < delay_in+delay_wait+delay_d_in and i > delay_wait+delay_d_in:
                                level = int(((next_level - old_level+1) / delay_in) * (i-delay_wait-delay_d_in)) + old_level
                            elif next_level > old_level and i > delay_in+delay_wait+delay_d_in:
                                level = next_level
                            # Si le level descend, on prend le temps de descente
                            elif next_level < old_level and i < delay_out+delay_wait+delay_d_out and i > delay_wait+delay_d_out:
                                level = old_level - abs(int(((next_level - old_level-1) / delay_out) * (i-delay_wait-delay_d_out)))
                            elif next_level < old_level and i > delay_out+delay_wait+delay_d_out:
                                level = next_level
                            # Sinon, la valeur est déjà bonne
                            else:
                                level = old_level

                            self.app.dmx.sequence[channel-1] = level

            self.app.dmx.send()

            if self.app.patch_outputs_tab != None:
                GLib.idle_add(self.app.patch_outputs_tab.flowbox.queue_draw)


    def update_ui(self, position, subtitle):
        # Update Sequential Tab
        if position == 0:
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position+1][9] = "#232729"
            self.app.window.cues_liststore1[position+2][9] = "#997004"
            self.app.window.cues_liststore1[position+3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position+3][10] = Pango.Weight.HEAVY
        else:
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position+1][9] = "#232729"
            self.app.window.cues_liststore1[position+2][9] = "#997004"
            self.app.window.cues_liststore1[position+3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position+2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position+3][10] = Pango.Weight.HEAVY
        self.app.window.step_filter1.refilter()
        self.app.window.step_filter2.refilter()
        path = Gtk.TreePath.new_from_indices([0])
        self.app.window.treeview1.set_cursor(path, None, False)
        self.app.window.treeview2.set_cursor(path, None, False)
        self.app.window.seq_grid.queue_draw()
        # Update Main Window's Subtitle
        self.app.window.header.set_subtitle(subtitle)

class SequenceTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ""
        self.last_chan_selected = ""

        # To stock user modification on channels
        self.user_channels = array.array('h', [-1] * 512)

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        #self.set_row_homogeneous(True)

        # List of Sequences
        self.liststore1 = Gtk.ListStore(int, str, str)

        self.liststore1.append([self.app.sequence.index, self.app.sequence.type_seq, self.app.sequence.text])

        for chaser in range(len(self.app.chasers)):
            self.liststore1.append([self.app.chasers[chaser].index, self.app.chasers[chaser].type_seq, self.app.chasers[chaser].text])

        self.treeview1 = Gtk.TreeView(model=self.liststore1)
        self.treeview1.set_enable_search(False)
        selection = self.treeview1.get_selection()
        selection.connect('changed', self.on_sequence_changed)

        for i, column_title in enumerate(["Seq", "Type", "Name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview1.append_column(column)

        self.attach(self.treeview1, 0, 0, 1, 1)

        # We put channels and memories list in a paned
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Channels in the selected cue
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []
        for i in range(512):
            self.channels.append(ChannelWidget(i+1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)
        self.paned.add1(self.scrolled)

        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)

        # Selected Sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]

            # Find it
            for i in range(len(self.liststore1)):
                #print(i, path.get_indices()[0])
                if i == selected:
                    #print("Index :", self.liststore1[i][0])
                    if self.liststore1[i][0] == self.app.sequence.index:
                        self.seq = self.app.sequence
                    else:
                        for j in range(len(self.app.chasers)):
                            if self.liststore1[i][0] == self.app.chasers[j].index:
                                self.seq = self.app.chasers[j]
            # Liststore with infos from the sequence
            for i in range(self.seq.last)[1:]:
                if self.seq.cues[i].wait.is_integer():
                    wait = str(int(self.seq.cues[i].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.cues[i].wait)
                if self.seq.cues[i].time_out.is_integer():
                    t_out = str(int(self.seq.cues[i].time_out))
                else:
                    t_out = str(self.seq.cues[i].time_out)
                if self.seq.cues[i].delay_out.is_integer():
                    d_out = str(int(self.seq.cues[i].delay_out))
                    if d_out == "0":
                        d_out = ""
                else:
                    d_out = str(self.seq.cues[i].delay_out)
                if self.seq.cues[i].time_in.is_integer():
                    t_in = str(int(self.seq.cues[i].time_in))
                else:
                    t_in = str(self.seq.cues[i].time_in)
                if self.seq.cues[i].delay_in.is_integer():
                    d_in = str(int(self.seq.cues[i].delay_in))
                    if d_in == "0":
                        d_in = ""
                else:
                    d_in = str(self.seq.cues[i].delay_in)
                channel_time = str(len(self.seq.cues[i].channel_time))
                if channel_time == "0":
                    channel_time = ""
                self.liststore2.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                    wait, d_out, t_out, d_in, t_in, channel_time])

        self.filter2 = self.liststore2.filter_new()
        self.filter2.set_visible_func(self.filter_cue_func)

        self.treeview2 = Gtk.TreeView(model=self.filter2)
        self.treeview2.set_enable_search(False)
        #self.treeview2.set_activate_on_single_click(True)
        self.treeview2.connect('cursor-changed', self.on_memory_changed)
        self.treeview2.connect('row-activated', self.on_row_activated)

        # Display selected sequence
        for i, column_title in enumerate(["Step", "Memory", "Text", "Wait", "Delay Out", "Out", "Delay In", "In", "Channel Time"]):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            if i == 3:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.wait_edited)
            if i == 4:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.delay_out_edited)
            if i == 5:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.out_edited)
            if i == 6:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.delay_in_edited)
            if i == 7:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.in_edited)
            if i == 2:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.text_edited)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)

            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)

            self.treeview2.append_column(column)

        # Put Cues List in a scrolled window
        self.scrollable2 = Gtk.ScrolledWindow()
        self.scrollable2.set_vexpand(True)
        self.scrollable2.set_hexpand(True)
        self.scrollable2.add(self.treeview2)

        self.paned.add2(self.scrollable2)

        self.attach_next_to(self.paned, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1)

        self.flowbox.set_filter_func(self.filter_func, None)

        # Select Main Playback
        path = Gtk.TreePath.new_first()
        self.treeview1.set_cursor(path, None, False)

    def on_row_activated(self, treeview, path, column):
        # Find the double clicked cell
        itr = self.liststore2.get_iter(path)
        columns = self.treeview2.get_columns()
        for col_nb, col in enumerate(columns):
            if col == column:
                break
        # Double click on Channel Time
        if col_nb == 8:

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        seq = self.app.chasers[i]

            # Edit Channel Time
            step = self.liststore2[path][0]
            self.app._channeltime(seq, step)

    def wait_edited(self, widget, path, text):

        if text == '':
            text = '0'

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            if text == "0":
                self.liststore2[path][3] = ""
            else:
                self.liststore2[path][3] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Wait value
            self.seq.cues[step].wait = float(text)
            # Update Total Time
            if self.seq.cues[step].time_in + self.seq.cues[step].delay_in > self.seq.cues[step].time_out + self.seq.cues[step].delay_out:
                self.seq.cues[step].total_time = self.seq.cues[step].time_in + self.seq.cues[step].wait + self.seq.cues[step].delay_in
            else:
                self.seq.cues[step].total_time = self.seq.cues[step].time_out + self.seq.cues[step].wait + self.seq.cues[step].delay_out
            for channel in self.seq.cues[step].channel_time.keys():
                t = self.seq.cues[step].channel_time[channel].delay + self.seq.cues[step].channel_time[channel].time + self.seq.cues[step].wait
                if t > self.seq.cues[step].total_time:
                    self.seq.cues[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                if text == "0":
                    self.app.window.cues_liststore1[path][3] = ""
                    self.app.window.cues_liststore2[path][3] = ""
                else:
                    self.app.window.cues_liststore1[path][3] = text
                    self.app.window.cues_liststore2[path][3] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.wait = float(text)
                    self.app.window.sequential.total_time = self.seq.cues[step].total_time
                    self.app.window.sequential.queue_draw()

    def out_edited(self, widget, path, text):

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            self.liststore2[path][5] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Time Out value
            self.seq.cues[step].time_out = float(text)
            # Update Total Time
            if self.seq.cues[step].time_in + self.seq.cues[step].delay_in > self.seq.cues[step].time_out + self.seq.cues[step].delay_out:
                self.seq.cues[step].total_time = self.seq.cues[step].time_in + self.seq.cues[step].wait + self.seq.cues[step].delay_in
            else:
                self.seq.cues[step].total_time = self.seq.cues[step].time_out + self.seq.cues[step].wait + self.seq.cues[step].delay_out
            for channel in self.seq.cues[step].channel_time.keys():
                t = self.seq.cues[step].channel_time[channel].delay + self.seq.cues[step].channel_time[channel].time + self.seq.cues[step].wait
                if t > self.seq.cues[step].total_time:
                    self.seq.cues[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                self.app.window.cues_liststore1[path][5] = text
                self.app.window.cues_liststore2[path][5] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.time_out = float(text)
                    self.app.window.sequential.total_time = self.seq.cues[step].total_time
                    self.app.window.sequential.queue_draw()

    def in_edited(self, widget, path, text):

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            self.liststore2[path][6] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Time In value
            self.seq.cues[step].time_in = float(text)
            # Update Total Time
            if self.seq.cues[step].time_in + self.seq.cues[step].delay_in > self.seq.cues[step].time_out + self.seq.cues[step].delay_out:
                self.seq.cues[step].total_time = self.seq.cues[step].time_in + self.seq.cues[step].wait + self.seq.cues[step].delay_in
            else:
                self.seq.cues[step].total_time = self.seq.cues[step].time_out + self.seq.cues[step].wait + self.seq.cues[step].delay_out
            for channel in self.seq.cues[step].channel_time.keys():
                t = self.seq.cues[step].channel_time[channel].delay + self.seq.cues[step].channel_time[channel].time + self.seq.cues[step].wait
                if t > self.seq.cues[step].total_time:
                    self.seq.cues[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                self.app.window.cues_liststore1[path][6] = text
                self.app.window.cues_liststore2[path][6] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.time_in = float(text)
                    self.app.window.sequential.total_time = self.seq.cues[step].total_time
                    self.app.window.sequential.queue_draw()

    def delay_out_edited(self, widget, path, text):

        if text == '':
            text = '0'

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            if text == "0":
                self.liststore2[path][4] = ""
            else:
                self.liststore2[path][4] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            self.seq.cues[step].delay_out = float(text)
            # Update Total Time
            if self.seq.cues[step].time_in + self.seq.cues[step].delay_in > self.seq.cues[step].time_out + self.seq.cues[step].delay_out:
                self.seq.cues[step].total_time = self.seq.cues[step].time_in + self.seq.cues[step].wait + self.seq.cues[step].delay_in
            else:
                self.seq.cues[step].total_time = self.seq.cues[step].time_out + self.seq.cues[step].wait + self.seq.cues[step].delay_out
            for channel in self.seq.cues[step].channel_time.keys():
                t = self.seq.cues[step].channel_time[channel].delay + self.seq.cues[step].channel_time[channel].time + self.seq.cues[step].wait
                if t > self.seq.cues[step].total_time:
                    self.seq.cues[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                if text == "0":
                    self.app.window.cues_liststore1[path][4] = ""
                    self.app.window.cues_liststore2[path][4] = ""
                else:
                    self.app.window.cues_liststore1[path][4] = text
                    self.app.window.cues_liststore2[path][4] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.delay_out = float(text)
                    self.app.window.sequential.total_time = self.seq.cues[step].total_time
                    self.app.window.sequential.queue_draw()

    def delay_in_edited(self, widget, path, text):

        if text == '':
            text = '0'

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            if text == "0":
                self.liststore2[path][6] = ""
            else:
                self.liststore2[path][6] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            self.seq.cues[step].delay_in = float(text)
            # Update Total Time
            if self.seq.cues[step].time_in + self.seq.cues[step].delay_in > self.seq.cues[step].time_out + self.seq.cues[step].delay_out:
                self.seq.cues[step].total_time = self.seq.cues[step].time_in + self.seq.cues[step].wait + self.seq.cues[step].delay_in
            else:
                self.seq.cues[step].total_time = self.seq.cues[step].time_out + self.seq.cues[step].wait + self.seq.cues[step].delay_out
            for channel in self.seq.cues[step].channel_time.keys():
                t = self.seq.cues[step].channel_time[channel].delay + self.seq.cues[step].channel_time[channel].time + self.seq.cues[step].wait
                if t > self.seq.cues[step].total_time:
                    self.seq.cues[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                if text == "0":
                    self.app.window.cues_liststore1[path][6] = ""
                    self.app.window.cues_liststore2[path][6] = ""
                else:
                    self.app.window.cues_liststore1[path][6] = text
                    self.app.window.cues_liststore2[path][6] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.delay_in = float(text)
                    self.app.window.sequential.total_time = self.seq.cues[step].total_time
                    self.app.window.sequential.queue_draw()

    def text_edited(self, widget, path, text):

        self.liststore2[path][2] = text

        # Find selected sequence
        seq_path, focus_column = self.treeview1.get_cursor()
        selected = seq_path.get_indices()[0]
        sequence = self.liststore1[selected][0]
        if sequence == self.app.sequence.index:
            self.seq = self.app.sequence
        else:
            for i in range(len(self.app.chasers)):
                if sequence == self.app.chasers[i].index:
                    self.seq = self.app.chasers[i]
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update text value
        self.seq.cues[step].text = text

        # Tag filename as modified
        self.app.ascii.modified = True
        self.app.window.header.set_title(self.app.ascii.basename + '*')

        # Update Main Playback
        if self.seq == self.app.sequence:
            path = str(int(path) + 1)
            self.app.window.cues_liststore1[path][2] = text
            self.app.window.cues_liststore2[path][2] = text

            # Update window's subtitle if needed
            if self.app.sequence.position == step:
                subtitle = "Mem. : " + self.seq.cues[step].memory + " " + self.seq.cues[step].text + " - Next Mem. : " + self.seq.cues[step + 1].memory + " " + self.seq.cues[step + 1].text
                self.app.window.header.set_subtitle(subtitle)

            if self.app.sequence.position + 1 == step:
                subtitle = "Mem. : " + self.seq.cues[step - 1].memory + " " + self.seq.cues[step - 1].text + " - Next Mem. : " + self.seq.cues[step].memory + " " + self.seq.cues[step].text
                self.app.window.header.set_subtitle(subtitle)

    def on_memory_changed(self, treeview):
        """ Select memory """
        for channel in range(512):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def filter_cue_func(self, model, iter, data):
        return True

    def filter_func(self, child, user_data):
        """ Filter channels """
        # Find selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
        # Find Step
        i = child.get_index()
        selection = self.treeview2.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter != None:
            step = int(model[treeiter][0])
            # Display channels in step
            channels = self.seq.cues[step].channels

            if channels[i] != 0 or self.channels[i].clicked:
                if self.user_channels[i] == -1:
                    self.channels[i].level = channels[i]
                    self.channels[i].next_level = channels[i]
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                return child
            else:
                if self.user_channels[i] == -1:
                    self.channels[i].level = 0
                    self.channels[i].next_level = 0
                    return False
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                    return child

        if self.user_channels[i] != -1 or self.channels[i].clicked:
            if self.user_channels[i] == -1:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
            else:
                self.channels[i].level = self.user_channels[i]
                self.channels[i].next_level = self.user_channels[i]
            return child

        return False

    def on_sequence_changed(self, selection):
        """ Select Sequence """

        # TODO: voir pourquoi clear declanche un scan de toute la liststore
        #self.liststore2.clear()
        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str,str)

        model, treeiter = selection.get_selected()

        if treeiter != None:
            selected = model[treeiter][0]
            # Find it
            for i in range(len(self.liststore1)):
                if i + 1 == selected:
                    if self.liststore1[i][0] == self.app.sequence.index:
                        self.seq = self.app.sequence
                    else:
                        for j in range(len(self.app.chasers)):
                            if self.liststore1[i][0] == self.app.chasers[j].index:
                                self.seq = self.app.chasers[j]
            # Liststore with infos from the sequence
            if self.seq == self.app.sequence:
                for i in range(self.seq.last)[1:-1]:
                    if self.seq.cues[i].wait.is_integer():
                        wait = str(int(self.seq.cues[i].wait))
                        if wait == "0":
                            wait = ""
                    else:
                        wait = str(self.seq.cues[i].wait)
                    if self.seq.cues[i].time_out.is_integer():
                        t_out = str(int(self.seq.cues[i].time_out))
                    else:
                        t_out = str(self.seq.cues[i].time_out)
                    if self.seq.cues[i].delay_out.is_integer():
                        d_out = str(int(self.seq.cues[i].delay_out))
                        if d_out == "0":
                            d_out = ""
                    else:
                        d_out = str(self.seq.cues[i].delay_out)
                    if self.seq.cues[i].time_in.is_integer():
                        t_in = str(int(self.seq.cues[i].time_in))
                    else:
                        t_in = str(self.seq.cues[i].time_in)
                    if self.seq.cues[i].delay_in.is_integer():
                        d_in = str(int(self.seq.cues[i].delay_in))
                        if d_in == "0":
                            d_in = ""
                    else:
                        d_in = str(self.seq.cues[i].delay_in)
                    channel_time = str(len(self.seq.cues[i].channel_time))
                    if channel_time == "0":
                        channel_time = ""
                    self.liststore2.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                        wait, d_out, t_out, d_in, t_in, channel_time])
            else:
                for i in range(self.seq.last)[1:]:
                    if self.seq.cues[i].wait.is_integer():
                        wait = str(int(self.seq.cues[i].wait))
                        if wait == "0":
                            wait = ""
                    else:
                        wait = str(self.seq.cues[i].wait)
                    if self.seq.cues[i].time_out.is_integer():
                        t_out = str(int(self.seq.cues[i].time_out))
                    else:
                        t_out = str(self.seq.cues[i].time_out)
                    if self.seq.cues[i].delay_out.is_integer():
                        d_out = str(int(self.seq.cues[i].delay_out))
                        if d_out == "0":
                            d_out = ""
                    else:
                        d_out = str(self.seq.cues[i].delay_out)
                    if self.seq.cues[i].time_in.is_integer():
                        t_in = str(int(self.seq.cues[i].time_in))
                    else:
                        t_in = str(self.seq.cues[i].time_in)
                    if self.seq.cues[i].delay_in.is_integer():
                        d_in = str(int(self.seq.cues[i].delay_in))
                        if d_in == "0":
                            d_in = ""
                    else:
                        d_in = str(self.seq.cues[i].delay_in)
                    channel_time = str(len(self.seq.cues[i].channel_time))
                    if channel_time == "0":
                        channel_time = ""
                    self.liststore2.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                        wait, d_out, t_out, d_in, t_in, channel_time])

            self.treeview2.set_model(self.liststore2)
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

            self.app.window.show_all()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.sequences_tab)
        self.app.window.notebook.remove_page(page)
        self.app.sequences_tab = None

    def on_key_press_event(self, widget, event):

        # TODO: Hack to know if user is editing something
        widget = self.app.window.get_focus()
        #print(widget.get_path().is_type(Gtk.Entry))
        if not widget:
            return
        if widget.get_path().is_type(Gtk.Entry):
            return

        keyname = Gdk.keyval_name(event.keyval)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'period':
            self.keystring += '.'
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.sequences_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Q(self):
        """ Cycle Sequences """
        # TODO: Update Shortcuts window
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            path.next()
            self.treeview1.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview1.set_cursor(path)
        path = Gtk.TreePath.new_first()
        self.treeview2.set_cursor(path)
        # Reset user modifications
        self.user_channels = array.array('h', [-1] * 512)

    def keypress_q(self):
        """ Prev Memory """

        # Reset user modifications
        self.user_channels = array.array('h', [-1] * 512)

        path, focus_column = self.treeview2.get_cursor()
        if path != None:
            if path.prev():
                self.treeview2.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

    def keypress_w(self):
        """ Next Memory """

        # Reset user modifications
        self.user_channels = array.array('h', [-1] * 512)

        path, focus_column = self.treeview2.get_cursor()
        if path != None:
            path.next()
            self.treeview2.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

    def keypress_a(self):
        """ All Channels """

        self.flowbox.unselect_all()

        # Find selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Step
            path, focus_column = self.treeview2.get_cursor()
            if path != None:
                selected = path.get_indices()[0]
                step = int(self.liststore2[selected][0])
                channels = self.seq.cues[step].channels

                for channel in range(512):
                    if channels[channel] != 0:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.app.window.set_focus(child)
                        self.flowbox.select_child(child)
                    else:
                        self.channels[channel].clicked = False
                self.flowbox.invalidate_filter()

    def keypress_c(self):
        """ Channel """

        self.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < 512:

                # Only patched channel
                if self.app.patch.channels[channel][0] != 0:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring
        else:
            for channel in range(512):
                self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        sel = self.flowbox.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(self.last_chan_selected):
                for channel in range(int(self.last_chan_selected) - 1, to_chan):
                    # Only patched channels
                    if self.app.patch.channels[channel][0] != 0:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.app.window.set_focus(child)
                        self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()
            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):
                    # Only patched channels
                    if self.app.patch.channels[channel][0] != 0:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.app.window.set_focus(child)
                        self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_plus(self):
        """ Channel + """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if channel >= 0 and channel < 512:
            self.channels[channel].clicked = True
            self.flowbox.invalidate_filter()

            child = self.flowbox.get_child_at_index(channel)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_minus(self):
        """ Channel - """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if channel >= 0 and channel < 512:
            self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

            child = self.flowbox.get_child_at_index(channel)
            self.app.window.set_focus(child)
            self.flowbox.unselect_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_equal(self):
        """ @ Level """
        level = int(self.keystring)
        if Gio.Application.get_default().settings.get_boolean('percent'):
            if level >= 0 and level <= 100:
                level = int(round((level / 100) * 255))
            else:
                level = -1
        if level >= 0 and level <= 255:
            sel = self.flowbox.get_selected_children()

            for flowboxchild in sel:
                children = flowboxchild.get_children()

                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1

                    if level != -1:
                        self.channels[channel].level = level
                        self.channels[channel].next_level = level
                        self.channels[channel].queue_draw()
                        self.user_channels[channel] = level

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_colon(self):
        """ Level - % """

        lvl = Gio.Application.get_default().settings.get_int('percent-level')

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                if level - lvl < 0:
                    level = 0
                else:
                    level = level - lvl

                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def keypress_exclam(self):
        """ Level + % """

        lvl = Gio.Application.get_default().settings.get_int('percent-level')

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                if level + lvl > 255:
                    level = 255
                else:
                    level = level + lvl

                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def keypress_U(self):
        """ Update Cue """

        # Find selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Step
            path, focus_column = self.treeview2.get_cursor()
            if path != None:
                selected = path.get_indices()[0]
                step = int(self.liststore2[selected][0])
                channels = self.seq.cues[step].channels

                memory = self.seq.cues[step].memory

                # Dialog to confirm Update
                dialog = Dialog(self.app.window, memory)
                response = dialog.run()

                if response == Gtk.ResponseType.OK:
                    # Update levels in the cue
                    for channel in range(512):
                        channels[channel] = self.channels[channel].level
                        if channels[channel] != 0:
                            self.seq.channels[channel] = 1

                    # Tag filename as modified
                    self.app.ascii.modified = True
                    self.app.window.header.set_title(self.app.ascii.basename + "*")

                    # Update Main playback display
                    if self.seq == self.app.sequence:
                        if step == self.app.sequence.position + 1:
                            for channel in range(512):
                                self.app.window.channels[channel].next_level = self.seq.cues[step].channels[channel]
                                self.app.window.channels[channel].queue_draw()

                elif response == Gtk.ResponseType.CANCEL:
                    pass

                dialog.destroy()

                # Reset user modifications
                self.user_channels = array.array('h', [-1] * 512)

    def keypress_N(self):
        """ New Chaser """

        # Use the next free index
        if len(self.app.chasers) >  0:
            index_seq = self.app.chasers[-1].index + 1
        else:
            # Or 2 (1 is for Main Playback)
            index_seq = 2

        # Create Chaser
        self.app.chasers.append(Sequence(index_seq, self.app.patch, type_seq = "Chaser"))

        # Update List of sequences
        self.liststore1.append([self.app.chasers[-1].index, self.app.chasers[-1].type_seq,
            self.app.chasers[-1].text])

        # Tag filename as modified
        self.app.ascii.modified = True
        self.app.window.header.set_title(self.app.ascii.basename + '*')

    def keypress_R(self):
        """ New Cue """

        # If user enter a memory number, use it
        mem = -1

        if self.keystring != "":
            mem = float(self.keystring)

            # Memory elready exist ?
            for i in range(len(self.seq.cues)):
                if self.seq.cues[i].memory == str(mem):
                    # Update memory

                    # Dialog to confirm Update
                    dialog = Dialog(self.app.window, str(mem))
                    response = dialog.run()

                    if response == Gtk.ResponseType.OK:
                        # Update memory's levels
                        for channel in range(512):
                            self.seq.cues[i].channels[channel] = self.channels[channel].level
                            if self.seq.cues[i].channels[channel] != 0:
                                self.seq.channels[channel] = 1

                        # Tag filename as modified
                        self.app.ascii.modified = True
                        self.app.window.header.set_title(self.app.ascii.basename + '*')

                        # Select memory modified
                        path = Gtk.TreePath.new_from_indices([i - 1])
                        self.treeview2.set_cursor(path, None, False)

                        # Update Main playback
                        if self.seq == self.app.sequence:
                            if i == self.app.sequence.position + 1:
                                for channel in range(512):
                                    self.app.window.channels[channel].next_level = self.seq.cues[i].channels[channel]
                                    self.app.window.channels[channel].queue_draw()

                    elif response == Gtk.ResponseType.CANCEL:
                        pass

                    dialog.destroy()

                    # Tag filename as modified
                    self.app.ascii.modified = True
                    self.app.window.header.set_title(self.app.ascii.basename + '*')

                    self.keystring = ""
                    self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

                    return

            self.keystring = ""
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        # Find the selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]

            # Insert new memory if a number is given
            if mem != -1:
                # Find step where insert new memory
                for i in range(len(self.seq.cues)):
                    if float(self.seq.cues[i].memory) > mem:
                        break

                # For chasers if the new cue is at the end
                if self.seq.index != 1:
                    if float(self.seq.cues[i].memory) < mem:
                        index = i + 1
                    else:
                        index = i
                else:
                    index = i

                memory = mem

            else:
                # Find the next free index and memory
                if self.seq.index == 1:
                    index = self.seq.cues[-2].index + 1
                    memory = float(self.seq.cues[-2].memory) + 1
                else:
                    index = self.seq.cues[-1].index + 1
                    memory = float(self.seq.cues[-1].memory) + 1

            channels = array.array('B', [0] * 512)
            for channel in range(512):
                channels[channel] = self.channels[channel].level

            cue = Cue(index, str(memory), channels)

            # Insert Cue
            self.seq.cues.insert(index, cue)
            self.seq.last += 1

            ### Update Display

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Main Playback
            if self.seq.index == 1:

                if self.seq.cues[i].wait.is_integer():
                    wait = str(int(self.seq.cues[index].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.cues[index].wait)
                if self.seq.cues[index].time_out.is_integer():
                    t_out = str(int(self.seq.cues[index].time_out))
                else:
                    t_out = str(self.seq.cues[index].time_out)
                if self.seq.cues[index].time_in.is_integer():
                    t_in = str(int(self.seq.cues[index].time_in))
                else:
                    t_in = str(self.seq.cues[index].time_in)
                channel_time = str(len(self.seq.cues[index].channel_time))
                if channel_time == "0":
                    channel_time = ""

                self.liststore2.insert(index - 1, [str(index), str(self.seq.cues[index].memory),
                    self.seq.cues[index].text, wait, t_out, t_in, channel_time])

                # Update indexes of cues in listsore
                for i in range(index, self.seq.last - 2):
                    self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)

                # Select new step
                path = Gtk.TreePath.new_from_indices([index - 1])
                self.treeview2.set_cursor(path, None, False)

                # Update Main Playback

                bg = "#232729"

                if self.seq.cues[index].wait.is_integer():
                    wait = str(int(self.seq.cues[index].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.cues[index].wait)
                if self.seq.cues[index].time_out.is_integer():
                    t_out = str(int(self.seq.cues[index].time_out))
                else:
                    t_out = str(self.seq.cues[index].time_out)
                if self.seq.cues[index].time_in.is_integer():
                    t_in = str(int(self.seq.cues[index].time_in))
                else:
                    t_in = str(self.seq.cues[index].time_in)
                channel_time = str(len(self.seq.cues[index].channel_time))
                if channel_time == "0":
                    channel_time = ""

                self.app.window.cues_liststore1.insert(index, [str(index), str(self.seq.cues[index].memory),
                    self.seq.cues[index].text, wait, t_out, t_in, channel_time, bg])
                self.app.window.cues_liststore2.insert(index, [str(index), str(self.seq.cues[index].memory),
                    self.seq.cues[index].text, wait, t_out, t_in, channel_time])

                # Update indexes of cues in listsore
                for i in range(index + 1, self.seq.last):
                    self.app.window.cues_liststore1[i][0] = str(int(self.app.window.cues_liststore1[i][0]) + 1)
                    self.app.window.cues_liststore2[i][0] = str(int(self.app.window.cues_liststore2[i][0]) + 1)

                # Update Crossfade
                if self.app.sequence.position + 1 == index:
                    self.app.window.sequential.time_in = self.seq.cues[index].time_in
                    self.app.window.sequential.time_out = self.seq.cues[index].time_out
                    self.app.window.sequential.wait = self.seq.cues[index].wait
                    self.app.window.sequential.total_time = self.seq.cues[index].total_time
                    self.app.window.sequential.queue_draw()

            else:
                # Update Chasers

                if self.seq.cues[index].wait.is_integer():
                    wait = str(int(self.seq.cues[index].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.cues[index].wait)
                if self.seq.cues[index].time_out.is_integer():
                    t_out = str(int(self.seq.cues[index].time_out))
                else:
                    t_out = str(self.seq.cues[index].time_out)
                if self.seq.cues[index].time_in.is_integer():
                    t_in = str(int(self.seq.cues[index].time_in))
                else:
                    t_in = str(self.seq.cues[index].time_in)
                channel_time = str(len(self.seq.cues[index].channel_time))
                if channel_time == "0":
                    channel_time = ""

                self.liststore2.insert(index - 1, [str(index), str(self.seq.cues[index].memory),
                    self.seq.cues[index].text, wait, t_out, t_in, channel_time])

                # Update indexes of cues in listsore
                for i in range(index, self.seq.last - 1):
                    self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)

                # Select new step
                path = Gtk.TreePath.new_from_indices([index - 1])
                self.treeview2.set_cursor(path, None, False)

            # Reset user modifications
            self.user_channels = array.array('h', [-1] * 512)

class Dialog(Gtk.Dialog):

    def __init__(self, parent, memory):
        Gtk.Dialog.__init__(self, "Confirmation", parent, 0,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                 Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_default_size(150,100)

        label = Gtk.Label("Update memory " + memory + " ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()

if __name__ == "__main__":

    sequence = Sequence(1)

    channels = array.array('B', [0] * 512)
    for i in range(512):
        channels[i] = int(i / 2)
    cue = Cue(1, 1.0, channels, text="Top blabla")
    sequence.add_cue(cue)

    print("Sequence :", sequence.index, "Type :", sequence.type_seq, "\n")
    print("Position in sequence :", sequence.position)
    print("Index of the last Cue :", sequence.last)
    for cue in sequence.cues:
        print("Index :", cue.index)
        print("memory :", cue.memory)
        print("time in :", cue.time_in)
        print("time out :", cue.time_out)
        print("text :", cue.text)
        print("Chanels :")
        for i in range(512):
            print(i+1, "@", cue.channels[i])
        print("")
