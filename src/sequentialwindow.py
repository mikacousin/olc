from gi.repository import Gtk

from olc.customwidgets import SequentialWidget

class SequentialWindow(Gtk.Window):
    def __init__(self, seq):

        self.seq = seq

        Gtk.Window.__init__(self, title="Sequential")
        self.set_border_width(10)

        t_in = self.seq.cues[0].time_in
        t_out = self.seq.cues[0].time_out

        self.sequential = SequentialWidget(t_in, t_out)
        self.add(self.sequential)
