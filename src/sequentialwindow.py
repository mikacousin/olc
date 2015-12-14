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

        for i in range(512):
            level = self.app.sequence.cues[position].chanels.dmx_frame[i]
            self.app.dmxframe.set_level(i, level)
        self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)

        self.sequential = SequentialWidget(t_in, t_out)
        self.add(self.sequential)
