from gi.repository import Gtk, Gio, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_channel import ChannelWidget

class CuesEditionTab(Gtk.Paned):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ''
        self.last_chan_selected = ''

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        # Channels used in selected Cue
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)

        self.add(self.scrolled)

        # List of Cues
        self.liststore = Gtk.ListStore(str, str)

        for i in range(len(self.app.memories)):
            self.liststore.append([str(self.app.memories[i].memory), self.app.memories[i].text])

        self.filter = self.liststore.filter_new()
        self.filter.set_visible_func(self.filter_cue_func)

        self.treeview = Gtk.TreeView(model = self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect('cursor-changed', self.on_cue_changed)

        for i, column_title in enumerate(['Memory', 'Text']):
            renderer = Gtk.CellRendererText()

            column = Gtk.TreeViewColumn(column_title, renderer, text = i)

            self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

        self.flowbox.set_filter_func(self.filter_channel_func, None)

    def filter_channel_func(self, child, user_data):
        """ Filter channels """
        # Find selected row
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Index of Channel
            i = child.get_index()

            # Cue's channels
            channels = self.app.memories[row].channels

            if channels[i] or self.channels[i].clicked:
                self.channels[i].level = channels[i]
                self.channels[i].next_level = channels[i]
                return child
        else:
            return False

    def filter_cue_func(self, model, i, data):
        return True

    def on_cue_changed(self, treeview):
        """ Selected Cue """
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.memories_tab)
        self.app.window.notebook.remove_page(page)
        self.app.memories_tab = None

    def on_key_press_event(self, widget, event):
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

    def keypress_BackSpace(self):
        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Channel """

        self.flowbox.unselect_all()

        if self.keystring != '' and self.keystring != '0':
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < MAX_CHANNELS:

                # Only patched channel
                if self.app.patch.channels[channel][0] != 0:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring
        else:
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
            self.flowbox1.invalidate_filter()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
