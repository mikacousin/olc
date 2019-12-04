import array
from gi.repository import Gtk, Gio, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_channel import ChannelWidget

class CuesEditionTab(Gtk.Paned):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ''
        self.last_chan_selected = ''

        # Channels modified by user
        self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

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
        self.liststore = Gtk.ListStore(str, str, int)

        for i in range(len(self.app.memories)):
            channels = 0
            for chan in range(MAX_CHANNELS):
                if self.app.memories[i].channels[chan]:
                    channels += 1
            self.liststore.append([str(self.app.memories[i].memory), self.app.memories[i].text, channels])

        self.filter = self.liststore.filter_new()
        self.filter.set_visible_func(self.filter_cue_func)

        self.treeview = Gtk.TreeView(model = self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect('cursor-changed', self.on_cue_changed)

        for i, column_title in enumerate(['Memory', 'Text', 'Channels']):
            renderer = Gtk.CellRendererText()

            column = Gtk.TreeViewColumn(column_title, renderer, text = i)

            self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

        self.flowbox.set_filter_func(self.filter_channel_func, None)

        # Select first Memory
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

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
                if self.user_channels[i] == -1:
                    self.channels[i].level = channels[i]
                    self.channels[i].next_level = channels[i]
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                return child
            else:
                if self.user_channels[i] == -1:
                    self.channels[i].level = 0
                    self.channels[i].next_level = 0
                    return False
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                    return child
        else:
            return False

    def filter_cue_func(self, model, i, data):
        return True

    def on_cue_changed(self, treeview):
        """ Selected Cue """
        self.user_channels = array.array('h', [-1] * MAX_CHANNELS)
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.memories_tab)
        self.app.window.notebook.remove_page(page)
        self.app.memories_tab = None

    def on_scroll(self, widget, event):
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK:
            (scroll, direction) = event.get_scroll_direction()
            if scroll and direction == Gdk.ScrollDirection.UP:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale <= 2:
                        self.channels[i].scale += 0.1
                self.flowbox.queue_draw()
            if scroll and direction == Gdk.ScrollDirection.DOWN:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale >= 1.1:
                        self.channels[i].scale -= 0.1
                self.flowbox.queue_draw()
            # TODO: Fix widgets dimensions
            if self.channels[0].scale > 1:
                self.flowbox.set_homogeneous(False)
            else:
                self.flowbox.set_homogeneous(True)

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

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.memories_tab = None

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
                if self.app.patch.channels[channel][0] != [0, 0]:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring
        else:
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        selected_children = self.flowbox.get_selected_children()
        if len(selected_children) == 1:
            flowboxchild = selected_children[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > 0 and to_chan < MAX_CHANNELS:
                if to_chan > int(self.last_chan_selected):
                    for channel in range(int(self.last_chan_selected) - 1, to_chan):
                        # Only patched channels
                        if self.app.patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            self.app.window.set_focus(child)
                            self.flowbox.select_child(child)
                else:
                    for channel in range(to_chan - 1, int(self.last_chan_selected)):
                        # Only patched channels
                        if self.app.patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            self.app.window.set_focus(child)
                            self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_plus(self):
        """ Channel + """

        if self.keystring != '':

            channel = int(self.keystring) - 1

            if (channel >= 0 and channel < MAX_CHANNELS
                    and self.app.patch.channels[channel][0] != [0, 0]):
                self.channels[channel].clicked = True
                self.flowbox.invalidate_filter()

                child = self.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = self.keystring

            self.keystring = ''
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_minus(self):
        """ Channel - """

        if self.keystring != '':

            channel = int(self.keystring) - 1

            if (channel >= 0 and channel < MAX_CHANNELS
                    and self.app.patch.channels[channel][0] != [0, 0]):
                self.channels[channel].clicked = False
                self.flowbox.invalidate_filter()

                child = self.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.flowbox.unselect_child(child)
                self.last_chan_selected = self.keystring

            self.keystring = ''
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_a(self):
        """ All Channels """

        self.flowbox.unselect_all()

        # Find selected memory
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Memory's channels
            channels = self.app.memories[row].channels

            # Select channels with a level
            for chan in range(MAX_CHANNELS):
                if ((channels[chan] and self.user_channels[chan] != 0)
                        or self.user_channels[chan] > 0):
                    self.channels[chan].clicked = True
                    child = self.flowbox.get_child_at_index(chan)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                else:
                    self.channels[chan].clicked = False
            self.flowbox.invalidate_filter()

    def keypress_equal(self):
        """ @ level """

        level = int(self.keystring)

        if self.app.settings.get_boolean('percent'):
            if level >= 0 and level <= 100:
                level = int(round((level / 100) * 255))
            else:
                level = -1

        if level >= 0 and level < 256:

            selected_children = self.flowbox.get_selected_children()

            for flowboxchild in selected_children:
                child = flowboxchild.get_children()

                for channelwidget in child:
                    channel = int(channelwidget.channel) - 1

                    self.channels[channel].level = level
                    self.channels[channel].next_level = level
                    self.channels[channel].queue_draw()
                    self.user_channels[channel] = level

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_colon(self):
        """ Level - % """

        lvl = self.app.settings.get_int('percent-level')
        percent = self.app.settings.get_boolean('percent')

        if percent:
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                if level - lvl < 0:
                    level = 0
                else:
                    level = level - lvl

                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def keypress_exclam(self):
        """ Level + % """

        lvl = self.app.settings.get_int('percent-level')
        percent = self.app.settings.get_boolean('percent')

        if percent:
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                if level + lvl > 255:
                    level = 255
                else:
                    level = level + lvl

                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def keypress_U(self):
        """ Update Memory """

        self.flowbox.unselect_all()

        # Find selected memory
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Memory's channels
            channels = self.app.memories[row].channels

            # Update levels
            for chan in range(MAX_CHANNELS):
                channels[chan] = self.channels[chan].level
                if channels[chan] != 0:
                    self.app.sequence.channels[chan] = 1

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + "*")

    def keypress_R(self):
        """ Record Memory """
        pass
