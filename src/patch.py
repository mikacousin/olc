from gi.repository import Gio, Gtk, Gdk

from olc.dmx import Dmx, PatchDmx

class PatchTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.liststore = Gtk.ListStore(str, int, str, str)

        for channel in range(len(self.app.patch.channels)):
            for output in range(len(self.app.patch.channels[channel])):
                if self.app.patch.channels[channel][output] != 0:
                    self.liststore.append(["      ", channel+1, str(self.app.patch.channels[channel][output]), ""])
                else:
                    self.liststore.append(["      ", channel+1, "", ""])
        
        self.treeview = Gtk.TreeView(model=self.liststore)

        renderer_chan = Gtk.CellRendererText()
        column_chan = Gtk.TreeViewColumn("", renderer_chan, text=0)
        self.treeview.append_column(column_chan)

        renderer_chan = Gtk.CellRendererText()
        column_chan = Gtk.TreeViewColumn("Channel", renderer_chan, text=1)
        self.treeview.append_column(column_chan)

        renderer_output = Gtk.CellRendererText()
        renderer_output.set_property('editable', True)
        column_output = Gtk.TreeViewColumn("Output", renderer_output, text=2)
        self.treeview.append_column(column_output)
        renderer_output.connect('edited', self.output_edited)

        renderer_type = Gtk.CellRendererText()
        renderer_type.set_property('editable', True)
        column_type = Gtk.TreeViewColumn("Type", renderer_type, text=3)
        self.treeview.append_column(column_type)
        renderer_type.connect('edited', self.type_edited)

        self.buttons = list()
        for type in ["Patch 1:1", "Patch Vide"]:
            button = Gtk.Button(type)
            self.buttons.append(button)
            button.connect('clicked', self.on_button_clicked)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.add(self.treeview)
        self.scrollable_treelist.set_vexpand(True)

        self.attach(self.scrollable_treelist, 0, 0, 6, 10)
        self.attach_next_to(self.buttons[0], self.scrollable_treelist, Gtk.PositionType.BOTTOM, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)

    def output_edited(self, widget, path, text):
        # TODO: Pouvoir mettre plusieurs outputs sur un channel
        # TODO: Bug quand on réutilise un output mis dans un groupe sur un channel
        value_list = text.split(',')
        for value in value_list:
            if value == "" or value == "0":
                self.liststore[path][2] = ""
                self.app.patch.channels[int(path)] = [0]
                for i in range(len(self.app.patch.channels[int(path)])):
                    self.app.patch.outputs[self.app.patch.channels[int(path)][i]] = 0
                self.app.window.flowbox.invalidate_filter()
            else:
                output_old = self.app.patch.outputs[int(value) - 1]
                if output_old > 0:
                    self.liststore[output_old - 1][2] = ""
                    self.app.patch.channels[output_old -1] = [0]
                    self.app.patch.outputs[int(value) - 1] = 0
                self.liststore[path][2] = text
                self.app.patch.add_output(int(path)+1, int(value))
                level = self.app.dmx.frame[int(value)-1]
                self.app.window.channels[int(path)].level = level
                self.app.window.channels[int(path)].queue_draw()
                self.app.window.flowbox.invalidate_filter()

    def type_edited(self, widget, path, text):
        self.liststore[path][3] = text

    def on_button_clicked(self, widget):
        button_label = widget.get_label()
        if button_label == "Patch Vide":
            self.app.patch.patch_empty()
            for channel in range(512):
                self.liststore[channel][2] = ""
            self.app.window.flowbox.invalidate_filter()
        elif button_label == "Patch 1:1":
            self.app.patch.patch_1on1()
            for channel in range(512):
                self.liststore[channel][2] = str(channel + 1)
                level = self.app.dmx.frame[channel]
                self.app.window.channels[channel].level = level
                self.app.window.channels[channel].queue_draw()
            self.app.window.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.patch_tab)
        self.app.window.notebook.remove_page(page)
        self.app.patch_tab = None

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print(keyname)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.patch_tab = None
