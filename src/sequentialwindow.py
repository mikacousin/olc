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
        t_in = self.seq.cues[position].time_in
        t_out = self.seq.cues[position].time_out

        # TODO: Faire une boucle sur les outputs
        # Set levels for chanels in actual cue
        for output in range(512):
            channel = self.app.patch.outputs[output]

            if channel:
                level = self.app.sequence.cues[position].channels[channel-1]
                self.app.dmx.sequence[channel-1] = level

        self.app.dmx.send()

        # Création du crossfade
        self.sequential = SequentialWidget(t_in, t_out)

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
        for i, column_title in enumerate(["Pas", "Mémoire", "Texte", "Wait", "Out", "In", "Tps Circ"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)
            self.treeview.append_column(column)

        # Création d'une scrollwindow pour mettre la lsite des mémoires
        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)
        self.grid.add(self.sequential)
        self.grid.attach_next_to(self.scrollable, self.sequential, Gtk.PositionType.BOTTOM, 1, 1)

        """
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

        self.grid.attach_next_to(self.sequential, self.step[4], Gtk.PositionType.BOTTOM, 7, 1)

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
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[1], self.step[1], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[2], self.step[2], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(self.seq.cues[position].memory))
        self.grid.attach_next_to(self.mem[3], self.step[3], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[4], self.step[4], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[5], self.step[5], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[6], self.step[6], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[7], self.step[7], Gtk.PositionType.RIGHT, 1, 1)
        self.mem.append(Gtk.Label(""))
        self.grid.attach_next_to(self.mem[8], self.step[8], Gtk.PositionType.RIGHT, 1, 1)

        self.text = []
        self.text.append(Gtk.Label("Texte"))
        self.grid.attach_next_to(self.text[0], self.mem[0], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[1], self.mem[1], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[2], self.mem[2], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(self.seq.cues[position].text))
        self.grid.attach_next_to(self.text[3], self.mem[3], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[4], self.mem[4], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[5], self.mem[5], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[6], self.mem[6], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[7], self.mem[7], Gtk.PositionType.RIGHT, 1, 1)
        self.text.append(Gtk.Label(""))
        self.grid.attach_next_to(self.text[8], self.mem[8], Gtk.PositionType.RIGHT, 1, 1)

        self.wait = []
        self.wait.append(Gtk.Label("Wait"))
        self.grid.attach_next_to(self.wait[0], self.text[0], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[1], self.text[3], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[2], self.text[2], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(self.seq.cues[position].wait))
        self.grid.attach_next_to(self.wait[3], self.text[3], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[4], self.text[4], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[5], self.text[5], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[6], self.text[6], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[7], self.text[7], Gtk.PositionType.RIGHT, 1, 1)
        self.wait.append(Gtk.Label(""))
        self.grid.attach_next_to(self.wait[8], self.text[8], Gtk.PositionType.RIGHT, 1, 1)

        self.t_out = []
        self.t_out.append(Gtk.Label("Out"))
        self.grid.attach_next_to(self.t_out[0], self.wait[0], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[1], self.wait[1], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[2], self.wait[2], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(self.seq.cues[position].time_out))
        self.grid.attach_next_to(self.t_out[3], self.wait[3], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[4], self.wait[4], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[5], self.wait[5], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[6], self.wait[6], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[7], self.wait[7], Gtk.PositionType.RIGHT, 1, 1)
        self.t_out.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_out[8], self.wait[8], Gtk.PositionType.RIGHT, 1, 1)

        self.t_in = []
        self.t_in.append(Gtk.Label("In"))
        self.grid.attach_next_to(self.t_in[0], self.t_out[0], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[1], self.t_out[1], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[2], self.t_out[2], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(self.seq.cues[position].time_in))
        self.grid.attach_next_to(self.t_in[3], self.t_out[3], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[4], self.t_out[4], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[5], self.t_out[5], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[6], self.t_out[6], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[7], self.t_out[7], Gtk.PositionType.RIGHT, 1, 1)
        self.t_in.append(Gtk.Label(""))
        self.grid.attach_next_to(self.t_in[8], self.t_out[8], Gtk.PositionType.RIGHT, 1, 1)

        # TODO
        self.t_circ = []
        self.t_circ.append(Gtk.Label("Tps Circ"))
        self.grid.attach_next_to(self.t_circ[0], self.t_in[0], Gtk.PositionType.RIGHT, 1, 1)
    """

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
