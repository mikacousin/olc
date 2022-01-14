"""Independents edition"""

import array

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget
from olc.zoom import zoom


class IndependentsTab(Gtk.Paned):
    """Tab to edit independents"""

    def __init__(self):
        self.keystring = ""
        self.last_selected_channel = ""
        # Channels modified by user
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        # To display channels used in selected independent
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.channels = []
        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox.add(self.channels[i])
        scrolled.add(self.flowbox)
        self.add(scrolled)

        # List of independents
        self.liststore = Gtk.ListStore(int, str, str)
        for inde in App().independents.independents:
            self.liststore.append([inde.number, inde.inde_type, inde.text])
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_changed)
        for i, column_title in enumerate(["Number", "Type", "Text"]):
            renderer = Gtk.CellRendererText()
            if i == 2:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.text_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.set_hexpand(True)
        scrollable.add(self.treeview)
        self.add(scrollable)

        self.flowbox.set_filter_func(self.filter_channel_func, None)
        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", zoom)

        # Select first independent
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

    def filter_channel_func(self, child, _user_data):
        """Filter channels"""
        # If independent, just return
        if not App().independents.independents:
            return False
        # Find selected row
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Index of Channel
            i = child.get_index()
            # Independent's channels
            channels = App().independents.independents[row].levels

            if channels[i] or self.channels[i].clicked:
                if self.user_channels[i] == -1:
                    self.channels[i].level = channels[i]
                    self.channels[i].next_level = channels[i]
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                return child
            if self.user_channels[i] == -1:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False
            self.channels[i].level = self.user_channels[i]
            self.channels[i].next_level = self.user_channels[i]
            return child
        return False

    def on_changed(self, _treeview):
        """Select independent"""
        self.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().inde_tab = None

    def text_edited(self, _widget, path, text):
        """Independent text edited"""
        self.liststore[path][2] = text
        number = self.liststore[path][0]
        App().independents.independents[number - 1].text = text

    def on_key_press_event(self, _widget, event):
        """Keyboard events"""
        # Hack to know if user is editing something
        widget = App().window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            App().window.statusbar.push(App().window.context_id, self.keystring)
        if keyname in (
            "KP_1",
            "KP_2",
            "KP_3",
            "KP_4",
            "KP_5",
            "KP_6",
            "KP_7",
            "KP_8",
            "KP_9",
            "KP_0",
        ):
            self.keystring += keyname[3:]
            App().window.statusbar.push(App().window.context_id, self.keystring)
        if keyname == "period":
            self.keystring += "."
            App().window.statusbar.push(App().window.context_id, self.keystring)
        func = getattr(self, "_keypress_" + keyname, None)
        if func:
            return func()
        return False

    def _keypress_Escape(self):
        """Close Tab"""
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().inde_tab = None

    def _keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_c(self):
        """Channel"""
        self.flowbox.unselect_all()
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                # Only patched channel
                if App().patch.channels[channel][0] != [0, 0]:
                    self.channels[channel].clicked = True

                    child = self.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_selected_channel = self.keystring
        self.flowbox.invalidate_filter()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):
        """Channel Thru"""
        self._keypress_greater()

    def _keypress_greater(self):
        """Channel Thru"""
        selected_children = self.flowbox.get_selected_children()
        if len(selected_children) == 1:
            flowboxchild = selected_children[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_selected_channel = channelwidget.channel
        if self.last_selected_channel:
            to_chan = int(self.keystring)
            if 0 < to_chan < MAX_CHANNELS:
                if to_chan > int(self.last_selected_channel):
                    for channel in range(int(self.last_selected_channel) - 1, to_chan):
                        # Only patched channels
                        if App().patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            App().window.set_focus(child)
                            self.flowbox.select_child(child)
                else:
                    for channel in range(to_chan - 1, int(self.last_selected_channel)):
                        # Only patched channels
                        if App().patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            App().window.set_focus(child)
                            self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_plus(self):
        """Channel +"""
        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            self.channels[channel].clicked = True
            self.flowbox.invalidate_filter()
            child = self.flowbox.get_child_at_index(channel)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_selected_channel = self.keystring
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_minus(self):
        """Channel -"""
        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()
            child = self.flowbox.get_child_at_index(channel)
            App().window.set_focus(child)
            self.flowbox.unselect_child(child)
            self.last_selected_channel = self.keystring
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_a(self):
        """All channels"""
        self.flowbox.unselect_all()
        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Independent's channels
            channels = App().independents.independents[row].levels
            # Select channels with a level
            for chan in range(MAX_CHANNELS):
                if (
                    channels[chan] and self.user_channels[chan] != 0
                ) or self.user_channels[chan] > 0:
                    self.channels[chan].clicked = True
                    child = self.flowbox.get_child_at_index(chan)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                else:
                    self.channels[chan].clicked = False
            self.flowbox.invalidate_filter()

    def _keypress_equal(self):
        """@ level"""
        level = int(self.keystring)

        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
        if 0 <= level < 256:

            selected_children = self.flowbox.get_selected_children()

            for flowboxchild in selected_children:
                child = flowboxchild.get_children()

                for channelwidget in child:
                    channel = int(channelwidget.channel) - 1

                    self.channels[channel].level = level
                    self.channels[channel].next_level = level
                    self.channels[channel].queue_draw()
                    self.user_channels[channel] = level

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Level - %"""
        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")

        if percent:
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                level = max(level - lvl, 0)
                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def _keypress_exclam(self):
        """Level + %"""
        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")

        if percent:
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                level = min(level + lvl, 255)
                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def _keypress_U(self):
        """Update independent channels"""
        # Find independent
        path, _focus_column = self.treeview.get_cursor()
        if path:
            selected = path.get_indices()[0]
            number = self.liststore[selected][0]
            # Update channels level
            channels = array.array("B", [0] * MAX_CHANNELS)
            for channel in range(MAX_CHANNELS):
                channels[channel] = self.channels[channel].level
            App().independents.independents[number - 1].set_levels(channels)
            App().independents.update_channels()
            App().independents.independents[number - 1].update_dmx()
            App().window.channels_view.flowbox.queue_draw()
            self.queue_draw()

            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
