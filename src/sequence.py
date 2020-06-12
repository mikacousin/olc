import array
import threading
import time
from gi.repository import Gtk, Gio, GLib, Pango

from olc.define import NB_UNIVERSES, MAX_CHANNELS
from olc.cue import Cue
from olc.step import Step


class Sequence:
    def __init__(self, index, patch, type_seq="Normal", text=""):
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.steps = []
        self.position = 0
        self.last = 0
        # Flag pour savoir si on a un Go en cours
        self.on_go = False
        # Liste des channels présent dans le sequentiel
        self.channels = array.array("B", [0] * MAX_CHANNELS)
        # Flag for chasers
        self.run = False
        # Thread for chasers
        self.thread = None
        # Pour accéder à la fenêtre du séquentiel
        self.window = None
        # On a besoin de connaitre le patch
        self.patch = patch

        # Step and Cue 0
        cue = Cue(0, 0.0)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

        self.app = Gio.Application.get_default()

    def add_step(self, step):
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        for channel in range(MAX_CHANNELS):
            if step.cue.channels[channel] != 0:
                self.channels[channel] = 1

    def insert_step(self, index, step):
        self.steps.insert(index, step)
        self.last = len(self.steps)
        # Channels used in sequential
        for channel in range(MAX_CHANNELS):
            if step.cue.channels[channel] != 0:
                self.channels[channel] = 1

    def sequence_plus(self):

        if self.app.sequence.on_go:
            try:
                # Stop actual Thread
                self.app.sequence.thread.stop()
                self.app.sequence.on_go = False
                # Stop at the end
                if self.position > self.last - 3:
                    self.position = self.last - 3
            except Exception as e:
                print("Error :", e.message)

        position = self.position
        position += 1
        if position < self.last - 1:  # Stop on the last cue
            self.position += 1
            t_in = self.steps[position + 1].time_in
            t_out = self.steps[position + 1].time_out
            d_in = self.steps[position + 1].delay_in
            d_out = self.steps[position + 1].delay_out
            t_wait = self.steps[position + 1].wait
            self.window.sequential.total_time = self.steps[position + 1].total_time
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            self.window.sequential.delay_in = d_in
            self.window.sequential.delay_out = d_out
            self.window.sequential.wait = t_wait
            self.window.sequential.channel_time = self.steps[position + 1].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Update ui
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            # Next Cue in Bold
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
            self.window.step_filter1.refilter()
            self.window.step_filter2.refilter()
            path = Gtk.TreePath.new_first()
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)
            self.window.seq_grid.queue_draw()

            # Set main window's subtitle
            subtitle = (
                "Mem. : "
                + str(self.steps[position].cue.memory)
                + " "
                + self.steps[position].text
                + " - Next Mem. : "
                + str(self.steps[position + 1].cue.memory)
                + " "
                + self.steps[position + 1].text
            )
            self.app.window.header.set_subtitle(subtitle)

            # On vide le tableau des valeurs entrées par l'utilisateur
            self.app.dmx.user = array.array("h", [-1] * MAX_CHANNELS)

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = self.patch.outputs[univ][output][0]
                    if channel:
                        level = self.steps[position].cue.channels[channel - 1]
                        self.app.dmx.sequence[channel - 1] = level

    def sequence_minus(self):

        if self.on_go:
            try:
                # Stop actual Thread
                self.app.sequence.thread.stop()
                self.app.sequence.on_go = False
                # Stop at the begining
                if self.app.sequence.position < 1:
                    self.app.sequence.position = 1
            except Exception as e:
                print("Error :", e.message)

        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1
            # Always use times for next cue
            t_in = self.steps[position + 1].time_in
            t_out = self.steps[position + 1].time_out
            d_in = self.steps[position + 1].delay_in
            d_out = self.steps[position + 1].delay_out
            t_wait = self.steps[position + 1].wait
            self.window.sequential.total_time = self.steps[position + 1].total_time
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            self.window.sequential.delay_in = d_in
            self.window.sequential.delay_out = d_out
            self.window.sequential.wait = t_wait
            self.window.sequential.channel_time = self.steps[position + 1].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Set main window's subtitle
            subtitle = (
                "Mem. : "
                + str(self.steps[position].cue.memory)
                + " "
                + self.steps[position].text
                + " - Next Mem. : "
                + str(self.steps[position + 1].cue.memory)
                + " "
                + self.steps[position + 1].text
            )
            self.app.window.header.set_subtitle(subtitle)

            # Update ui
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            # Next Cue in Bold
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
            self.window.step_filter1.refilter()
            self.window.step_filter2.refilter()
            path = Gtk.TreePath.new_first()
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)
            self.window.seq_grid.queue_draw()

            # On vide le tableau des valeurs entrées par l'utilisateur
            self.app.dmx.user = array.array("h", [-1] * MAX_CHANNELS)

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = self.patch.outputs[univ][output][0]
                    if channel:
                        level = self.steps[position].cue.channels[channel - 1]
                        self.app.dmx.sequence[channel - 1] = level

    def sequence_goto(self, keystring):
        """ Jump to cue number """
        old_pos = self.app.sequence.position

        if not keystring:
            return

        # Scan all cues
        for i, step in enumerate(self.steps):
            # Until we find the good one
            if float(step.cue.memory) == float(keystring):
                # Position to the one just before
                self.app.sequence.position = i - 1
                position = self.app.sequence.position
                # Redraw Sequential window with new times
                t_in = self.app.sequence.steps[position + 1].time_in
                t_out = self.app.sequence.steps[position + 1].time_out
                d_in = self.steps[position + 1].delay_in
                d_out = self.steps[position + 1].delay_out
                t_wait = self.app.sequence.steps[position + 1].wait
                self.window.sequential.total_time = self.steps[position + 1].total_time
                self.app.window.sequential.time_in = t_in
                self.app.window.sequential.time_out = t_out
                self.window.sequential.delay_in = d_in
                self.window.sequential.delay_out = d_out
                self.app.window.sequential.wait = t_wait
                self.window.sequential.channel_time = self.steps[
                    position + 1
                ].channel_time
                self.app.window.sequential.pos_xA = 0
                self.app.window.sequential.pos_xB = 0

                # Update ui
                self.app.window.cues_liststore1[old_pos][9] = "#232729"
                self.app.window.cues_liststore1[position][9] = "#232729"
                self.app.window.cues_liststore1[position + 1][9] = "#232729"
                self.app.window.cues_liststore1[position + 2][9] = "#997004"
                self.app.window.cues_liststore1[position + 3][9] = "#555555"
                self.app.window.cues_liststore1[old_pos][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
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
        # Si un Go est en cours, on bascule sur la mémoire suivante
        if self.app.sequence.on_go:
            # Stop actual Thread
            try:
                self.app.sequence.thread.stop()
                self.app.sequence.thread.join()
            except Exception as e:
                print("Error :", e.message)
            self.app.sequence.on_go = False
            # Launch another Go
            position = self.app.sequence.position
            position += 1
            if position < self.app.sequence.last - 1:
                self.app.sequence.position += 1
                t_in = self.app.sequence.steps[position + 1].time_in
                t_out = self.app.sequence.steps[position + 1].time_out
                d_in = self.app.sequence.steps[position + 1].delay_in
                d_out = self.app.sequence.steps[position + 1].delay_out
                t_wait = self.app.sequence.steps[position + 1].wait
                self.app.window.sequential.total_time = self.app.sequence.steps[
                    position + 1
                ].total_time
                self.app.window.sequential.time_in = t_in
                self.app.window.sequential.time_out = t_out
                self.app.window.sequential.delay_in = d_in
                self.app.window.sequential.delay_out = d_out
                self.app.window.sequential.wait = t_wait
                self.app.window.sequential.channel_time = self.app.sequence.steps[
                    position + 1
                ].channel_time
                self.app.window.sequential.pos_xA = 0
                self.app.window.sequential.pos_xB = 0

                # Set main window's subtitle
                subtitle = (
                    "Mem. : "
                    + str(self.app.sequence.steps[position].cue.memory)
                    + " "
                    + self.app.sequence.steps[position].text
                    + " - Next Mem. : "
                    + str(self.app.sequence.steps[position + 1].cue.memory)
                    + " "
                    + self.app.sequence.steps[position + 1].text
                )
            else:
                self.app.sequence.position = 0
                position = 0
                t_in = self.app.sequence.steps[position + 1].time_in
                t_out = self.app.sequence.steps[position + 1].time_out
                d_in = self.app.sequence.steps[position + 1].delay_in
                d_out = self.app.sequence.steps[position + 1].delay_out
                t_wait = self.app.sequence.steps[position + 1].wait
                self.app.window.sequential.total_time = self.app.sequence.steps[
                    position + 1
                ].total_time
                self.app.window.sequential.time_in = t_in
                self.app.window.sequential.time_out = t_out
                self.app.window.sequential.delay_in = d_in
                self.app.window.sequential.delay_out = d_out
                self.app.window.sequential.wait = t_wait
                self.app.window.sequential.channel_time = self.app.sequence.steps[
                    position + 1
                ].channel_time
                self.app.window.sequential.pos_xA = 0
                self.app.window.sequential.pos_xB = 0

                # Set main window's subtitle
                subtitle = (
                    "Mem. : "
                    + str(self.app.sequence.steps[position].cue.memory)
                    + " "
                    + self.app.sequence.steps[position].text
                    + " - Next Mem. : "
                    + str(self.app.sequence.steps[position + 1].cue.memory)
                    + " "
                    + self.app.sequence.steps[position + 1].text
                )

            # Update Sequential Tab
            if position == 0:
                self.app.window.cues_liststore1[position][9] = "#232729"
                self.app.window.cues_liststore1[position + 1][9] = "#232729"
                self.app.window.cues_liststore1[position + 2][9] = "#997004"
                self.app.window.cues_liststore1[position + 3][9] = "#555555"
                self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
            else:
                self.app.window.cues_liststore1[position][9] = "#232729"
                self.app.window.cues_liststore1[position + 1][9] = "#232729"
                self.app.window.cues_liststore1[position + 2][9] = "#997004"
                self.app.window.cues_liststore1[position + 3][9] = "#555555"
                self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
            self.app.window.step_filter1.refilter()
            self.app.window.step_filter2.refilter()
            path = Gtk.TreePath.new_from_indices([0])
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)
            self.app.window.seq_grid.queue_draw()
            # Update Main Window's Subtitle
            self.app.window.header.set_subtitle(subtitle)

            self.sequence_go(None, None)

        else:
            # On indique qu'un Go est en cours
            self.app.sequence.on_go = True
            self.app.sequence.thread = ThreadGo(self.app)
            self.app.sequence.thread.start()

    def go_back(self, action, param):

        # Just return if we are at the beginning
        position = self.app.sequence.position
        if position == 0:
            return False

        if self.app.sequence.on_go:
            try:
                self.app.sequence.thread.stop()
                self.app.sequence.thread.join()
            except Exception as e:
                print("Error :", e.message)
            self.app.sequence.on_go = False

        go_back_time = self.app.settings.get_double("go-back-time")

        self.app.window.sequential.total_time = self.app.sequence.steps[
            position - 1
        ].total_time
        self.app.window.sequential.time_in = self.app.sequence.steps[
            position - 1
        ].time_in
        self.app.window.sequential.time_out = self.app.sequence.steps[
            position - 1
        ].time_out
        self.app.window.sequential.delay_in = self.app.sequence.steps[
            position - 1
        ].delay_in
        self.app.window.sequential.delay_out = self.app.sequence.steps[
            position - 1
        ].delay_out
        self.app.window.sequential.wait = self.app.sequence.steps[position - 1].wait
        self.app.window.sequential.channel_time = self.app.sequence.steps[
            position - 1
        ].channel_time
        self.app.window.sequential.pos_xA = 0
        self.app.window.sequential.pos_xB = 0

        self.app.window.seq_grid.queue_draw()

        subtitle = (
            "Mem. : "
            + str(self.app.sequence.steps[position].cue.memory)
            + " "
            + self.app.sequence.steps[position].text
            + " - Next Mem. : "
            + str(self.app.sequence.steps[position - 1].cue.memory)
            + " "
            + self.app.sequence.steps[position - 1].text
        )
        self.app.window.header.set_subtitle(subtitle)

        self.app.sequence.on_go = True
        self.app.sequence.thread = ThreadGoBack()
        self.app.sequence.thread.start()


# Objet Thread pour gérer les Go
class ThreadGo(threading.Thread):
    def __init__(self, app, name=""):
        threading.Thread.__init__(self)
        self.app = app
        self.name = name
        self._stopevent = threading.Event()
        # To save dmx levels when user send Go
        self.dmxlevels = []
        for univ in range(NB_UNIVERSES):
            self.dmxlevels.append(array.array("B", [0] * 512))

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
        t_in = self.app.sequence.steps[position + 1].time_in
        t_out = self.app.sequence.steps[position + 1].time_out
        d_in = self.app.sequence.steps[position + 1].delay_in
        d_out = self.app.sequence.steps[position + 1].delay_out
        t_wait = self.app.sequence.steps[position + 1].wait
        t_total = self.app.sequence.steps[position + 1].total_time

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
            self.update_levels(
                delay,
                delay_in,
                delay_out,
                delay_d_in,
                delay_d_out,
                delay_wait,
                i,
                position,
            )
            # Sleep for 50ms
            time.sleep(0.05)
            i = (time.time() * 1000) - start_time

        # Stop thread if we send stop message
        if self._stopevent.isSet():
            return

        # Finish to load memory
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = self.app.patch.outputs[univ][output][0]
                if channel:
                    if position < self.app.sequence.last - 1:
                        level = self.app.sequence.steps[position + 1].cue.channels[
                            channel - 1
                        ]
                    else:
                        level = self.app.sequence.steps[0].cue.channels[channel - 1]
                    self.app.dmx.sequence[channel - 1] = level

        # Le Go est terminé
        self.app.sequence.on_go = False
        # On vide le tableau des valeurs entrées par l'utilisateur
        self.app.dmx.user = array.array("h", [-1] * MAX_CHANNELS)

        # On se positionne à la mémoire suivante
        position = self.app.sequence.position
        position += 1

        # Si elle existe
        if position < self.app.sequence.last - 1:
            self.app.sequence.position += 1
            t_in = self.app.sequence.steps[position + 1].time_in
            t_out = self.app.sequence.steps[position + 1].time_out
            d_in = self.app.sequence.steps[position + 1].delay_in
            d_out = self.app.sequence.steps[position + 1].delay_out
            t_wait = self.app.sequence.steps[position + 1].wait
            self.app.window.sequential.total_time = self.app.sequence.steps[
                position + 1
            ].total_time
            self.app.window.sequential.time_in = t_in
            self.app.window.sequential.time_out = t_out
            self.app.window.sequential.delay_in = d_in
            self.app.window.sequential.delay_out = d_out
            self.app.window.sequential.wait = t_wait
            self.app.window.sequential.channel_time = self.app.sequence.steps[
                position + 1
            ].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Set main window's subtitle
            subtitle = (
                "Mem. : "
                + str(self.app.sequence.steps[position].cue.memory)
                + " "
                + self.app.sequence.steps[position].text
                + " - Next Mem. : "
                + str(self.app.sequence.steps[position + 1].cue.memory)
                + " "
                + self.app.sequence.steps[position + 1].text
            )

            # Update Gtk in the main thread
            GLib.idle_add(self.update_ui, position, subtitle)

            # Si la mémoire a un Wait
            if self.app.sequence.steps[position + 1].wait:
                self.app.sequence.sequence_go(None, None)

        # Sinon, on revient au début
        else:
            self.app.sequence.position = 0
            position = 0
            t_in = self.app.sequence.steps[position + 1].time_in
            t_out = self.app.sequence.steps[position + 1].time_out
            d_in = self.app.sequence.steps[position + 1].delay_in
            d_out = self.app.sequence.steps[position + 1].delay_out
            t_wait = self.app.sequence.steps[position + 1].wait
            self.app.window.sequential.total_time = self.app.sequence.steps[
                position + 1
            ].total_time
            self.app.window.sequential.time_in = t_in
            self.app.window.sequential.time_out = t_out
            self.app.window.sequential.delay_in = d_in
            self.app.window.sequential.delay_out = d_out
            self.app.window.sequential.wait = t_wait
            self.app.window.sequential.channel_time = self.app.sequence.steps[
                position + 1
            ].channel_time
            self.app.window.sequential.pos_xA = 0
            self.app.window.sequential.pos_xB = 0

            # Set main window's subtitle
            subtitle = (
                "Mem. : "
                + str(self.app.sequence.steps[position].cue.memory)
                + " "
                + self.app.sequence.steps[position].text
                + " - Next Mem. : "
                + str(self.app.sequence.steps[position + 1].cue.memory)
                + " "
                + self.app.sequence.steps[position + 1].text
            )

            # Update Gtk in the main thread
            GLib.idle_add(self.update_ui, position, subtitle)

    def stop(self):
        self._stopevent.set()

    def update_levels(
        self,
        delay,
        delay_in,
        delay_out,
        delay_d_in,
        delay_d_out,
        delay_wait,
        i,
        position,
    ):
        # Update sliders position
        # Get width of the sequential widget to place cursors correctly
        allocation = self.app.window.sequential.get_allocation()
        self.app.window.sequential.pos_xA = ((allocation.width - 32) / delay) * i
        self.app.window.sequential.pos_xB = ((allocation.width - 32) / delay) * i
        GLib.idle_add(self.app.window.sequential.queue_draw)

        # Move Virtual Console's XFade
        if self.app.virtual_console:
            if self.app.virtual_console.props.visible:
                val = round((255 / delay) * i)
                GLib.idle_add(self.app.virtual_console.scaleA.set_value, val)
                GLib.idle_add(self.app.virtual_console.scaleB.set_value, val)

        # On attend que le temps d'un éventuel wait soit passé pour changer
        # les levels
        if i > delay_wait:

            for univ in range(NB_UNIVERSES):

                for output in range(512):

                    # DMX values with Grand Master correction
                    old_level = round(
                        self.dmxlevels[univ][output] * (255 / self.app.dmx.grand_master)
                    )

                    channel = self.app.patch.outputs[univ][output][0]

                    if channel:

                        if position < self.app.sequence.last - 1:
                            next_level = self.app.sequence.steps[
                                position + 1
                            ].cue.channels[channel - 1]
                        else:
                            next_level = self.app.sequence.steps[0].cue.channels[
                                channel - 1
                            ]

                        channel_time = self.app.sequence.steps[
                            position + 1
                        ].channel_time

                        # If channel is in a channel time
                        if channel in channel_time:
                            ct_delay = channel_time[channel].delay * 1000
                            ct_time = channel_time[channel].time * 1000

                            if next_level > old_level:

                                if i < ct_delay + delay_wait:
                                    level = old_level

                                elif (
                                    ct_delay + delay_wait
                                    <= i
                                    < ct_delay + ct_time + delay_wait
                                ):
                                    level = (
                                        int(
                                            ((next_level - old_level + 1) / ct_time)
                                            * (i - ct_delay - delay_wait)
                                        )
                                        + old_level
                                    )

                                elif i >= ct_delay + ct_time + delay_wait:
                                    level = next_level

                            else:
                                if i < ct_delay + delay_wait:
                                    level = old_level

                                elif (
                                    ct_delay + delay_wait
                                    <= i
                                    < ct_delay + ct_time + delay_wait
                                ):
                                    level = old_level - abs(
                                        int(
                                            ((next_level - old_level - 1) / ct_time)
                                            * (i - ct_delay - delay_wait)
                                        )
                                    )

                                elif i >= ct_delay + ct_time + delay_wait:
                                    level = next_level

                            self.app.dmx.sequence[channel - 1] = level

                        # Else channel is normal
                        else:
                            # On boucle sur les mémoires et on revient à 0
                            if position < self.app.sequence.last - 1:
                                next_level = self.app.sequence.steps[
                                    position + 1
                                ].cue.channels[channel - 1]
                            else:
                                next_level = self.app.sequence.steps[0].cue.channels[
                                    channel - 1
                                ]
                                self.app.sequence.position = 0

                            # Si le level augmente,
                            # on prends le temps de montée
                            if (
                                next_level > old_level
                                and delay_wait + delay_d_in
                                < i
                                < delay_in + delay_wait + delay_d_in
                            ):
                                level = (
                                    int(
                                        ((next_level - old_level + 1) / delay_in)
                                        * (i - delay_wait - delay_d_in)
                                    )
                                    + old_level
                                )

                            elif (
                                next_level > old_level
                                and i > delay_in + delay_wait + delay_d_in
                            ):
                                level = next_level

                            # Si le level descend,
                            # on prend le temps de descente
                            elif (
                                next_level < old_level
                                and delay_wait + delay_d_out
                                < i
                                < delay_out + delay_wait + delay_d_out
                            ):
                                level = old_level - abs(
                                    int(
                                        ((next_level - old_level - 1) / delay_out)
                                        * (i - delay_wait - delay_d_out)
                                    )
                                )

                            elif (
                                next_level < old_level
                                and i > delay_out + delay_wait + delay_d_out
                            ):
                                level = next_level

                            # Sinon, la valeur est déjà bonne
                            else:
                                level = old_level

                            self.app.dmx.sequence[channel - 1] = level

            if self.app.patch_outputs_tab:
                GLib.idle_add(self.app.patch_outputs_tab.flowbox.queue_draw)

    def update_ui(self, position, subtitle):
        # Update Sequential Tab
        if position == 0:
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
        else:
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
        self.app.window.step_filter1.refilter()
        self.app.window.step_filter2.refilter()
        path = Gtk.TreePath.new_from_indices([0])
        self.app.window.treeview1.set_cursor(path, None, False)
        self.app.window.treeview2.set_cursor(path, None, False)
        self.app.window.seq_grid.queue_draw()
        # Update Main Window's Subtitle
        self.app.window.header.set_subtitle(subtitle)
        # Virtual Console's Xfade
        if self.app.virtual_console:
            if self.app.virtual_console.props.visible:
                if self.app.virtual_console.scaleA.get_inverted():
                    self.app.virtual_console.scaleA.set_inverted(False)
                    self.app.virtual_console.scaleB.set_inverted(False)
                else:
                    self.app.virtual_console.scaleA.set_inverted(True)
                    self.app.virtual_console.scaleB.set_inverted(True)
                self.app.virtual_console.scaleA.set_value(0)
                self.app.virtual_console.scaleB.set_value(0)


# Thread Object for Go Back
class ThreadGoBack(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()

        self.app = Gio.Application.get_default()

        self.dmxlevels = []
        for univ in range(NB_UNIVERSES):
            self.dmxlevels.append(array.array("B", [0] * 512))

    def run(self):
        # If sequential is empty, just return
        if self.app.sequence.last == 2:
            return

        position = self.app.sequence.position

        # Levels when Go Back starts
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.dmxlevels[univ][output] = self.app.dmx.frame[univ][output]

        # Go Back's default time
        go_back_time = self.app.settings.get_double("go-back-time") * 1000

        # Actual time in ms
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time

        while i < go_back_time and not self._stopevent.isSet():
            # Update DMX levels
            self.update_levels(go_back_time, i, position)
            # Sleep 50ms
            time.sleep(0.05)
            i = (time.time() * 1000) - start_time

        # Finish to load preset
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = self.app.patch.outputs[univ][output][0]
                if channel:
                    # TODO: Handle first position
                    level = self.app.sequence.steps[position - 1].cue.channels[
                        channel - 1
                    ]
                    self.app.dmx.sequence[channel - 1] = level

        self.app.sequence.go = False

        self.app.dmx.user = array.array("h", [-1] * MAX_CHANNELS)

        # TODO: Gérer la position
        position -= 1

        self.app.sequence.position = position
        self.app.window.sequential.time_in = self.app.sequence.steps[
            position + 1
        ].time_in
        self.app.window.sequential.time_out = self.app.sequence.steps[
            position + 1
        ].time_out
        self.app.window.sequential.delay_in = self.app.sequence.steps[
            position + 1
        ].delay_in
        self.app.window.sequential.delay_out = self.app.sequence.steps[
            position + 1
        ].delay_out
        self.app.window.sequential.wait = self.app.sequence.steps[position + 1].wait
        self.app.window.sequential.total_time = self.app.sequence.steps[
            position + 1
        ].total_time
        self.app.window.sequential.channel_time = self.app.sequence.steps[
            position + 1
        ].channel_time
        self.app.window.sequential.pos_xA = 0
        self.app.window.sequential.pos_xB = 0

        # Set main window's subtitle
        subtitle = (
            "Mem. : "
            + str(self.app.sequence.steps[position].cue.memory)
            + " "
            + self.app.sequence.steps[position].text
            + " - Next Mem. : "
            + str(self.app.sequence.steps[position + 1].cue.memory)
            + " "
            + self.app.sequence.steps[position + 1].text
        )

        # Update Gtk in the main thread
        GLib.idle_add(self.update_ui, position, subtitle)

        if self.app.sequence.steps[position + 1].wait:
            self.app.sequence.sequence_go(None, None)

    def stop(self):
        self._stopevent.set()

    def update_levels(self, go_back_time, i, position):
        # Update sliders position
        allocation = self.app.window.sequential.get_allocation()
        self.app.window.sequential.pos_xA = ((allocation.width - 32) / go_back_time) * i
        self.app.window.sequential.pos_xB = ((allocation.width - 32) / go_back_time) * i
        GLib.idle_add(self.app.window.sequential.queue_draw)

        # Move Virtual Console's XFade
        if self.app.virtual_console:
            if self.app.virtual_console.props.visible:
                val = round((255 / go_back_time) * i)
                GLib.idle_add(self.app.virtual_console.scaleA.set_value, val)
                GLib.idle_add(self.app.virtual_console.scaleB.set_value, val)

        for univ in range(NB_UNIVERSES):

            for output in range(512):

                old_level = round(
                    self.dmxlevels[univ][output] * (255 / self.app.dmx.grand_master)
                )

                channel = self.app.patch.outputs[univ][output][0]

                if channel:

                    next_level = self.app.sequence.steps[position - 1].cue.channels[
                        channel - 1
                    ]

                    if next_level > old_level:
                        level = (
                            round(((next_level - old_level) / go_back_time) * i)
                            + old_level
                        )
                    elif next_level < old_level:
                        level = old_level - abs(
                            round(((next_level - old_level) / go_back_time) * i)
                        )
                    else:
                        level = next_level

                    self.app.dmx.sequence[channel - 1] = level

        # if self.app.patch_outputs_tab != None:
        #     GLib.idle_add(self.app.patch_outputs_tab.flowbox.queue_draw)

    def update_ui(self, position, subtitle):
        # Update Sequential Tab
        if position == 0:
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
        else:
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
        self.app.window.step_filter1.refilter()
        self.app.window.step_filter2.refilter()
        path = Gtk.TreePath.new_from_indices([0])
        self.app.window.treeview1.set_cursor(path, None, False)
        self.app.window.treeview2.set_cursor(path, None, False)
        self.app.window.seq_grid.queue_draw()
        # Update Main Window's Subtitle
        self.app.window.header.set_subtitle(subtitle)
        # Virtual Console's Xfade
        if self.app.virtual_console:
            if self.app.virtual_console.props.visible:
                if self.app.virtual_console.scaleA.get_inverted():
                    self.app.virtual_console.scaleA.set_inverted(False)
                    self.app.virtual_console.scaleB.set_inverted(False)
                else:
                    self.app.virtual_console.scaleA.set_inverted(True)
                    self.app.virtual_console.scaleB.set_inverted(True)
                self.app.virtual_console.scaleA.set_value(0)
                self.app.virtual_console.scaleB.set_value(0)
