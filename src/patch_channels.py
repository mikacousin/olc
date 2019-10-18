from gi.repository import Gtk, Gio, Gdk

class PatchChannelsTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.liststore = Gtk.ListStore(int, str, str)
        # Populate patch
        for channel in range(512):
            outputs = ''
            for i in range(len(self.app.patch.channels[channel])):
                output = self.app.patch.channels[channel][i]
                if output:
                    if i > 0:
                        outputs += ', '
                    outputs += str(output)
            self.liststore.append([channel+1, outputs, ''])

        self.treeview = Gtk.TreeView(model=self.liststore)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Channel", renderer, text=0)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        column = Gtk.TreeViewColumn("Outputs", renderer, text=1)
        self.treeview.append_column(column)
        renderer.connect('edited', self.output_edited)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Text", renderer, text=2)
        self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.attach(self.scrollable, 0, 0, 1, 1)

    def output_edited(self, widget, path, value):
        channel = int(path)

        if value == '' or value == '0':
            # Unpatch if no entry
            output = self.app.patch.channels[channel]
            for i in range(len(output)):
                out = self.app.patch.channels[channel][i] - 1
                self.app.patch.outputs[out] = 0
            self.app.patch.channels[channel] = [0]
            self.liststore[channel][1] = ''
        else:
            # TODO: Add severals outputs to a channel
            output = int(value) - 1
            old_channel = self.app.patch.outputs[output]
            # Delete old values
            self.app.patch.channels[channel] = [0]
            self.app.patch.outputs[channel] = 0
            if old_channel:
                self.app.patch.outputs[output] = 0
                self.app.patch.channels[old_channel - 1].remove(output + 1)
            # Patch
            self.app.patch.add_output(channel + 1, output + 1)
            self.liststore[path][1] = ''
            for i in range(len(self.app.patch.channels[channel])):
                if i > 0:
                    self.liststore[path][1] += ', '
                self.liststore[path][1] += str(self.app.patch.channels[channel][i])
            self.liststore[old_channel - 1][1] = ''

        # Update Live view
        self.app.window.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.patch_channels_tab)
        self.app.window.notebook.remove_page(page)
        self.app.patch_channels_tab = None

    def on_key_press_event(self, widget, event):

        # TODO: Hack to know if user is editing something
        widget = self.app.window.get_focus()
        #print(widget.get_path().is_type(Gtk.Entry))
        if not widget:
            return
        if widget.get_path().is_type(Gtk.Entry):
            return

        keyname = Gdk.keyval_name(event.keyval)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'period':
            self.keystring += '.'
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.patch_channels_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
