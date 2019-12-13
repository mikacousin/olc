from gi.repository import Gtk, Gio

from olc.define import MAX_CHANNELS

class MastersTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)

        self.content_type = Gtk.ListStore(str)
        types = ['Channels', 'Sequence', 'Group']
        for item in types:
            self.content_type.append([item])

        self.liststore = Gtk.ListStore(int, str, str)

        # Create 40 empty Masters
        for i in range(40):
            self.liststore.append([i + 1, '', ''])

        for page in range(2):
            for i in range(len(self.app.masters)):
                if self.app.masters[i].page == page + 1:
                    row = self.app.masters[i].number - 1 + (page * 20)
                    treeiter = self.liststore.get_iter(row)
                    # Content type
                    if self.app.masters[i].content_type == 2:
                        self.liststore.set_value(treeiter, 1, 'Channels')
                        nb_chan = 0
                        for chan in range(MAX_CHANNELS):
                            if self.app.masters[i].channels[chan]:
                                nb_chan += 1
                        self.liststore.set_value(treeiter, 2, str(nb_chan))
                    elif self.app.masters[i].content_type == 3:
                        self.liststore.set_value(treeiter, 1, 'Sequence')
                        if self.app.masters[i].content_value.is_integer():
                            self.liststore.set_value(treeiter, 2, str(int(self.app.masters[i].content_value)))
                        else:
                            self.liststore.set_value(treeiter, 2, str(self.app.masters[i].content_value))
                    elif self.app.masters[i].content_type == 13:
                        self.liststore.set_value(treeiter, 1, 'Group')
                        if self.app.masters[i].content_value.is_integer():
                            self.liststore.set_value(treeiter, 2, str(int(self.app.masters[i].content_value)))
                        else:
                            self.liststore.set_value(treeiter, 2, str(self.app.masters[i].content_value))
                    else:
                        self.liststore.set_value(treeiter, 1, 'Inconnu')

        self.filter = self.liststore.filter_new()
        self.filter.set_visible_func(self.filter_master)

        self.treeview = Gtk.TreeView(model = self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect('cursor-changed', self.on_master_changed)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Master', renderer, text = 0)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererCombo()
        renderer.set_property('editable', True)
        renderer.set_property('model', self.content_type)
        renderer.set_property('text-column', 0)
        renderer.set_property('has-entry', False)
        renderer.connect('edited', self.on_content_type_changed)
        column = Gtk.TreeViewColumn('Content type', renderer, text = 1)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Content', renderer, text = 2)
        self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

        # Select First Master
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

    def filter_master(self, model, i, data):
        return True

    def on_master_changed(self, treeview):
        pass

    def on_content_type_changed(self, widget, path, text):
        self.liststore[path][1] = text

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.masters_tab)
        self.app.window.notebook.remove_page(page)
        self.app.masters_tab = None
