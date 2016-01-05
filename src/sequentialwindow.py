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
        self.add(self.sequential)
