from gi.repository import Gtk

from olc.dmx import PatchDmx

class PatchWindow(Gtk.Window):
    def __init__(self, patch):

        self.patch = patch

        Gtk.Window.__init__(self, title="Patch")
        self.set_border_width(10)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.add(self.grid)

        self.patch_liststore = Gtk.ListStore(int, str, str)
        for i in range(len(self.patch.chanels)):
            for j in range(len(self.patch.chanels[i])):
                self.patch_liststore.append([i+1, str(self.patch.chanels[i][j]), ""])

        self.treeview = Gtk.TreeView(self.patch_liststore)
        
        renderer_chan = Gtk.CellRendererText()
        column_chan = Gtk.TreeViewColumn("Chanel", renderer_chan, text=0)
        self.treeview.append_column(column_chan)

        renderer_output = Gtk.CellRendererText()
        renderer_output.set_property("editable", True)
        column_output = Gtk.TreeViewColumn("Output", renderer_output, text=1)
        self.treeview.append_column(column_output)
        renderer_output.connect("edited", self.output_edited)

        renderer_type = Gtk.CellRendererText()
        renderer_type.set_property("editable", True)
        column_type = Gtk.TreeViewColumn("Type", renderer_type, text=2)
        self.treeview.append_column(column_type)
        renderer_type.connect("edited", self.type_edited)

        self.buttons = list()
        for type in ["Patch 1:1", "Patch Vide"]:
            button = Gtk.Button(type)
            self.buttons.append(button)
            button.connect("clicked", self.on_button_clicked)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)
        self.grid.attach(self.scrollable_treelist, 0, 0, 6, 10)
        self.grid.attach_next_to(self.buttons[0], self.scrollable_treelist, Gtk.PositionType.BOTTOM, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.grid.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)
        self.scrollable_treelist.add(self.treeview)

    def output_edited(self, widget, path, value):
        # TODO: Pouvoir mettre plusieurs outputs sur un chanel
        # TODO: Mise à jour grille des chanels dans fenêtre principale
        output_old = self.patch.outputs[int(value) - 1]
        if output_old != 0:
            self.patch_liststore[output_old - 1][1] = ""
            self.patch.chanels[output_old - 1] = [0]
            self.patch.outputs[int(value) - 1] = 0
        self.patch_liststore[path][1] = value
        self.patch.chanels[int(path)] = [int(value)]
        self.patch.outputs[int(value) - 1] = int(path) + 1

    def type_edited(self, widget, path, text):
        self.patch_liststore[path][2] = text

    def on_button_clicked(self, widget):
        button_label = widget.get_label()
        if button_label == "Patch Vide":
            self.patch.patch_empty()
            for i in range(512):
                self.patch_liststore[i][1] = ""
        elif button_label == "Patch 1:1":
            self.patch.patch_1on1()
            for i in range(512):
                self.patch_liststore[i][1] = str(i + 1)
        else:
            print ("Ne devrait jamais arrivé !!!")
