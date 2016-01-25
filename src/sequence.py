import array
from gi.repository import Gtk

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
