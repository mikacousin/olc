from gi.repository import Gtk

from olc.customwidgets import SequentialWidget

class SequentialWindow(Gtk.Window):
    def __init__(self, app, seq):

        self.app = app
        self.seq = seq

        Gtk.Window.__init__(self, title="Sequential")
        self.set_border_width(10)

        position = self.seq.position
        t_in = self.seq.cues[position].time_in
        t_out = self.seq.cues[position].time_out

        # Set levels for chanels in actual cue
        for i in range(512):
            level = self.app.sequence.cues[position].channels[i]
            outputs = self.app.patch.chanels[i]
            for output in outputs:
                #print(output)
                self.app.dmxframe.set_level(output-1, level)
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

        self.sequential = SequentialWidget(t_in, t_out)

        self.grid = Gtk.Grid()
        self.add(self.grid)

        self.step = []
        self.step.append(Gtk.Label("Pas"))
        self.grid.add(self.step[0])
        self.step.append(Gtk.Label(""))
        self.grid.attach_next_to(self.step[1], self.step[0], Gtk.PositionType.BOTTOM, 1, 1)
        self.step.append(Gtk.Label(""))
        self.grid.attach_next_to(self.step[2], self.step[1], Gtk.PositionType.BOTTOM, 1, 1)
        # Ligne de la mémoire en scène
        self.step.append(Gtk.Label(self.seq.position))
        self.grid.attach_next_to(self.step[3], self.step[2], Gtk.PositionType.BOTTOM, 1, 1)
        self.step.append(Gtk.Label(self.seq.position+1))
        self.grid.attach_next_to(self.step[4], self.step[3], Gtk.PositionType.BOTTOM, 1, 1)

        self.grid.attach_next_to(self.sequential, self.step[4], Gtk.PositionType.BOTTOM, 6, 1)

        self.step.append(Gtk.Label(self.seq.position+2))
        self.grid.attach_next_to(self.step[5], self.sequential, Gtk.PositionType.BOTTOM, 1, 1)
        self.step.append(Gtk.Label(self.seq.position+3))
        self.grid.attach_next_to(self.step[6], self.step[5], Gtk.PositionType.BOTTOM, 1, 1)
        self.step.append(Gtk.Label(self.seq.position+4))
        self.grid.attach_next_to(self.step[7], self.step[6], Gtk.PositionType.BOTTOM, 1, 1)
        self.step.append(Gtk.Label(self.seq.position+5))
        self.grid.attach_next_to(self.step[8], self.step[7], Gtk.PositionType.BOTTOM, 1, 1)

        self.mem = []
        self.mem.append(Gtk.Label("Mémoire"))
        self.grid.attach_next_to(self.mem[0], self.step[0], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(self.seq.cues[position].memory))
        self.grid.attach_next_to(self.mem[1], self.step[3], Gtk.PositionType.RIGHT, 1, 1)

        self.text = []
        self.text.append(Gtk.Label("Texte"))
        self.grid.attach_next_to(self.text[0], self.mem[0], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(self.seq.cues[position].text))
        self.grid.attach_next_to(self.text[1], self.mem[1], Gtk.PositionType.RIGHT, 1, 1)

        self.wait = []
        self.wait.append(Gtk.Label("Wait"))
        self.grid.attach_next_to(self.wait[0], self.text[0], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(self.seq.cues[position].wait))
        self.grid.attach_next_to(self.wait[1], self.text[1], Gtk.PositionType.RIGHT, 1, 1)

        self.t_out = []
        self.t_out.append(Gtk.Label("Out"))
        self.grid.attach_next_to(self.t_out[0], self.wait[0], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(self.seq.cues[position].time_out))
        self.grid.attach_next_to(self.t_out[1], self.wait[1], Gtk.PositionType.RIGHT, 1, 1)

        self.t_in = []
        self.t_in.append(Gtk.Label("In"))
        self.grid.attach_next_to(self.t_in[0], self.t_out[0], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(self.seq.cues[position].time_in))
        self.grid.attach_next_to(self.t_in[1], self.t_out[1], Gtk.PositionType.RIGHT, 1, 1)

        self.t_circ = []
        self.t_circ.append(Gtk.Label("Tps Circ"))
        self.grid.attach_next_to(self.t_circ[0], self.t_in[0], Gtk.PositionType.RIGHT, 1, 1)
