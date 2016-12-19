from gi.repository import Gtk

from olc.customwidgets import SequentialWidget

class SequentialWindow(Gtk.Window):
    def __init__(self, app, seq):

        self.app = app
        self.seq = seq

        Gtk.Window.__init__(self, title="Sequential")
        #self.set_default_size(820, 1000)
        self.set_default_size(820, 700)
        self.set_border_width(10)

        position = self.seq.position
        t_total = self.seq.cues[position].total_time
        t_in = self.seq.cues[position].time_in
        t_out = self.seq.cues[position].time_out
        t_wait = self.seq.cues[position].wait
        channel_time = self.seq.cues[position].channel_time

        # Set levels for channels in actual cue
        for output in range(512):
            channel = self.app.patch.outputs[output]

            if channel:
                level = self.app.sequence.cues[position].channels[channel-1]
                self.app.dmx.sequence[channel-1] = level

        self.app.dmx.send()

        # Création du crossfade
        self.sequential = SequentialWidget(t_total, t_in, t_out, t_wait, channel_time)

        # Création de la liste des mémoires
        self.grid = Gtk.Grid()
        #self.grid.set_column_homogeneous(True)
        self.add(self.grid)

        # Création du modèle
        # Pas, Mémoire, Texte, Wait, Out, In, Tps Circ
        self.cues_liststore = Gtk.ListStore(str, str, str, str, str, str, str)
        for i in range(self.app.sequence.last):
            print(i)
            self.cues_liststore.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                    str(self.seq.cues[i].wait), str(self.seq.cues[i].time_out), str(self.seq.cues[i].time_in),
                    ""])

        # Création du filtre
        self.step_filter = self.cues_liststore.filter_new()
        self.step_filter.set_visible_func(self.step_filter_func)

        # Création de la liste
        #self.treeview = Gtk.TreeView(model=self.cues_liststore)
        self.treeview = Gtk.TreeView(model=self.step_filter)
        #self.treeview.set_hexpand(True)
        #self.treeview.set_vexpand(True)
        for i, column_title in enumerate(["Pas", "Mémoire", "Texte", "Wait", "Out", "In", "Channel Time"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)
            self.treeview.append_column(column)

        # Création d'une scrollwindow pour mettre la liste des mémoires
        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)
        self.grid.add(self.sequential)
        self.grid.attach_next_to(self.scrollable, self.sequential, Gtk.PositionType.BOTTOM, 1, 1)

    def step_filter_func(self, model, iter, data):
        return True
        position = self.seq.position
        #print(position, model[iter][0])
        if model[iter][0] == str(position):
            return True
        if model[iter][0] == str(position+1):
            return True
        if model[iter][0] == str(position+2):
            return True
        if model[iter][0] == str(position+3):
            return True
        if model[iter][0] == str(position+4):
            return True
