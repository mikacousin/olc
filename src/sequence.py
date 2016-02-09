import array
import threading
import time
from gi.repository import Gtk, GLib


from olc.cue import Cue
from olc.sequentialwindow import SequentialWindow
from olc.dmx import PatchDmx

class Sequence(object):
    def __init__(self, index, patch, type_seq = "Normal", text=""):
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
        # Flag pour les chasers
        self.run = False
        # Pour accéder à la fenêtre du séquentiel
        self.window = None
        # On a besoin de connaitre le patch
        self.patch = patch

        # create an empty cue 0
        cue = Cue(0, 0, text="Cue 0")
        self.add_cue(cue)

    def add_cue(self, cue):
        self.cues.append(cue)
        self.last = cue.index
        # On enregistre la liste des circuits présents dans la mméoire
        for i in range(512):
            if cue.channels[i] != 0:
                self.channels[i] = 1 # Si présent on le note

    def sequence_plus(self, app):
        self.app = app
        position = self.position
        position += 1
        if position < self.last-1:     # Stop on the last cue
            self.position += 1
            self.window.sequential.pos_x = 0
            t_in = self.cues[position+1].time_in
            t_out = self.cues[position+1].time_out
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            path = Gtk.TreePath.new_from_indices([position])
            self.window.treeview.set_cursor(path, None, False)
            self.window.grid.queue_draw()

            for chanel in range(512):
                level = self.cues[position].channels[chanel]
                outputs = self.patch.chanels[chanel]
                for output in outputs:
                    self.app.dmxframe.set_level(output-1, level)
            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def sequence_minus(self, app):
        self.app = app
        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1
            self.window.sequential.pos_x = 0
            t_in = self.cues[position+1].time_in   # Always use times for next cue
            t_out = self.cues[position+1].time_out
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            path = Gtk.TreePath.new_from_indices([position])
            self.window.treeview.set_cursor(path, None, False)
            self.window.grid.queue_draw()

            for chanel in range(512):
                level = self.cues[position].channels[chanel]
                outputs = self.patch.chanels[chanel]
                for output in outputs:
                    self.app.dmxframe.set_level(output-1, level)
            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

    def sequence_go(self, app):
        self.app = app
        # TODO: Si un Go est en cours
        if self.on_go:
            self.thread.stop()
            self.on_go = False
            #self.sequence_go(self.app)
        else:
            # On indique qu'un Go est en cours
            self.on_go = True
            self.thread = ThreadGo(self.app)
            self.thread.start()
            #time.sleep(6)
            #thread.stop()

# TODO: objet Thread pour gérer les Go
class ThreadGo(threading.Thread):
    def __init__(self, app, name=''):
        threading.Thread.__init__(self)
        self.app = app
        self.name = name
        self._stopevent = threading.Event()
        # To save dmx levels when user send Go
        self.dmxlevels = array.array('B', [0] * 512)

    def run(self):
        # Position dans le séquentiel
        position = self.app.sequence.position

        # Levels when Go is sent
        for output in range(512):
            self.dmxlevels[output] = self.app.dmxframe.dmx_frame[output]

        # On récupère les temps de montée et de descente de la mémoire suivante
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

        # Boucle sur le temps de montée ou de descente (le plus grand)
        while i < delay and not self._stopevent.isSet():
            GLib.idle_add(self.update_levels, delay, delay_in, delay_out, i, position) # Mise à jour des niveaux
            time.sleep(0.02)
            i = (time.time() * 1000) - start_time

        # Le Go est terminé
        self.app.sequence.on_go = False

        # On se positionne à la mémoire suivante
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
            path = Gtk.TreePath.new_from_indices([position])
            self.app.win_seq.treeview.set_cursor(path, None, False)
            self.app.win_seq.grid.queue_draw()

            # TODO: Si la mémoire a un Wait
            if self.app.sequence.cues[position+1].wait:
                print("Auto Go after", self.app.sequence.cues[position+1].wait, "seconds")
                time.sleep(self.app.sequence.cues[position+1].wait)
                print("GO!")
                self.app.window.keypress_space()

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

    def stop(self):
        self._stopevent.set()

    def update_levels(self, delay, delay_in, delay_out, i, position):
        #Mise à jour position des sliders
        self.app.win_seq.sequential.pos_x = ((800 - 32) / delay) * i # TODO (800-32) en dur dans customwidgets
        self.app.win_seq.sequential.queue_draw()

        for output in range(512):

            # On utilise les valeurs dmx comme valeurs de départ
            old_level = self.dmxlevels[output]

            channel = self.app.patch.outputs[output]

            if channel:
                # On boucle sur les mémoires et on revient à 0
                if position < self.app.sequence.last - 1:
                    next_level = self.app.sequence.cues[position+1].channels[channel-1]
                else:
                    next_level = self.app.sequence.cues[0].channels[channel-1]
                    self.app.sequence.position = 0

                # Si le level augmente, on prends le temps de montée
                if next_level > old_level and i < delay_in:
                    level = int(((next_level - old_level+1) / delay_in) * i) + old_level
                # Si le level descend, on prend le temps de descente
                elif next_level < old_level and i < delay_out:
                    level = old_level - abs(int(((next_level - old_level-1) / delay_out) *i))
                # Sinon, la valeur est déjà bonne
                else:
                    level = next_level

                #print("Channel :", channel, "old_level", old_level, "next_level", next_level, "level", level)

                self.app.dmxframe.set_level(output, level)

        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

        """
        for channel in range(512):

            #TODO: le niveau précédent doit prendre en compte les channels envoyés
            #      et pas ceux de la conduite
            old_level = self.app.sequence.cues[position].channels[channel]

            # On boucle sur les mémoires et on revient à 0
            if position < self.app.sequence.last - 1:
                next_level = self.app.sequence.cues[position+1].channels[channel]
            else:
                next_level = self.app.sequence.cues[0].channels[channel]
                self.app.sequence.position = 0

            # Si le level augmente, on prends le temps de montée
            if next_level > old_level and i < delay_in:
                level = int(((next_level - old_level+1) / delay_in) * i) + old_level
            # Si le level descend, on prend le temps de descente
            elif next_level < old_level and i < delay_out:
                level = old_level - abs(int(((next_level - old_level-1) / delay_out) *i))
            # Sinon, la valeur est déjà bonne
            else:
                level = next_level

            outputs = self.app.patch.chanels[channel]
            for output in outputs:
                self.app.dmxframe.set_level(output-1, level)

        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        """

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
