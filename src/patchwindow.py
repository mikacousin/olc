from gi.repository import Gtk

from olc.dmx import Dmx, PatchDmx

class PatchWindow(Gtk.Window):
    def __init__(self, patch, dmx, win):

        self.patch = patch
        self.dmx = dmx
        self.win = win

        Gtk.Window.__init__(self, title="Patch")
        self.set_border_width(10)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.add(self.grid)

        self.patch_liststore = Gtk.ListStore(str, int, str, str)
        for i in range(len(self.patch.channels)):
            for j in range(len(self.patch.channels[i])):
                #print("Chanel:", i+1, "Output:", self.patch.channels[i][j])
                if self.patch.channels[i][j] != 0:
                    self.patch_liststore.append(["     ", i+1, str(self.patch.channels[i][j]), ""])
                else:
                    self.patch_liststore.append(["     ", i+1, "", ""])

        self.treeview = Gtk.TreeView(model=self.patch_liststore)

        renderer_chan = Gtk.CellRendererText()
        column_chan = Gtk.TreeViewColumn("", renderer_chan, text=0)
        self.treeview.append_column(column_chan)

        renderer_chan = Gtk.CellRendererText()
        column_chan = Gtk.TreeViewColumn("Channel", renderer_chan, text=1)
        self.treeview.append_column(column_chan)

        renderer_output = Gtk.CellRendererText()
        renderer_output.set_property("editable", True)
        column_output = Gtk.TreeViewColumn("Output", renderer_output, text=2)
        self.treeview.append_column(column_output)
        renderer_output.connect("edited", self.output_edited)

        renderer_type = Gtk.CellRendererText()
        renderer_type.set_property("editable", True)
        column_type = Gtk.TreeViewColumn("Type", renderer_type, text=3)
        self.treeview.append_column(column_type)
        renderer_type.connect("edited", self.type_edited)

        self.buttons = list()
        for type in ["Patch 1:1", "Patch Vide"]:
            button = Gtk.Button(type)
            self.buttons.append(button)
            button.connect("clicked", self.on_button_clicked)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.add(self.treeview)
        self.scrollable_treelist.set_vexpand(True)
        self.grid.attach(self.scrollable_treelist, 0, 0, 6, 10)
        self.grid.attach_next_to(self.buttons[0], self.scrollable_treelist, Gtk.PositionType.BOTTOM, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.grid.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)

    def output_edited(self, widget, path, text):
        # TODO: Pouvoir mettre plusieurs outputs sur un channel
        # TODO: Bug quand on réutilise un output mis dans un groupe sur un channel
        s = ","
        value_list = text.split(',')
        for value in value_list:
            if value == "" or value == "0":
                self.patch_liststore[path][2] = ""
                self.patch.channels[int(path)] = [0]
                for i in range(len(self.patch.channels[int(path)])):
                    self.patch.outputs[self.patch.channels[int(path)][i]] = 0
                self.win.flowbox.invalidate_filter()
            else:
                output_old = self.patch.outputs[int(value) - 1]
                if output_old > 0:
                    self.patch_liststore[output_old - 1][2] = ""
                    self.patch.channels[output_old - 1] = [0]
                    self.patch.outputs[int(value) - 1] = 0
                self.patch_liststore[path][2] = text
                self.patch.add_output(int(path)+1, int(value))
                #level = self.dmx.get_level(int(value)-1)
                level = self.dmx.frame[int(value)-1]
                self.win.channels[int(path)].level = level
                self.win.channels[int(path)].queue_draw()
                self.win.flowbox.invalidate_filter()

    def type_edited(self, widget, path, text):
        self.patch_liststore[path][3] = text

    def on_button_clicked(self, widget):
        button_label = widget.get_label()
        if button_label == "Patch Vide":
            self.patch.patch_empty()
            for i in range(512):
                self.patch_liststore[i][2] = ""
            self.win.flowbox.invalidate_filter()
        elif button_label == "Patch 1:1":
            self.patch.patch_1on1()
            for i in range(512):
                self.patch_liststore[i][2] = str(i + 1)
                #level = self.dmx.get_level(i)
                level = self.dmx.frame[i]
                self.win.channels[i].level = level
                self.win.channels[i].queue_draw()
            self.win.flowbox.invalidate_filter()
