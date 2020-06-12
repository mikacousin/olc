from gi.repository import Gio, Gtk, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_channel import ChannelWidget


class ChannelTime:
    def __init__(self, delay=0.0, time=0.0):
        self.delay = delay
        self.time = time

    def get_delay(self):
        return self.delay

    def get_time(self):
        return self.time

    def set_delay(self, delay):
        if isinstance(delay, float) and delay >= 0:
            self.delay = delay

    def set_time(self, time):
        if isinstance(time, float) and time >= 0:
            self.time = time


class ChanneltimeTab(Gtk.Paned):
    def __init__(self, sequence, position):

        self.app = Gio.Application.get_default()
        self.sequence = sequence
        self.position = position

        self.keystring = ""
        self.last_chan_selected = ""

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        self.scrolled1 = Gtk.ScrolledWindow()
        self.scrolled1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled1.add(self.flowbox)

        self.add1(self.scrolled1)

        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled2.set_vexpand(True)
        self.scrolled2.set_hexpand(True)

        # List of Channels Times
        self.liststore = Gtk.ListStore(int, str, str)

        self.step = self.sequence.steps[int(position)]

        for channel in self.step.channel_time.keys():

            if self.step.channel_time[channel].delay.is_integer():
                delay = str(int(self.step.channel_time[channel].delay))
                if delay == "0":
                    delay = ""
            else:
                delay = str(self.step.channel_time[channel].delay)

            if self.step.channel_time[channel].time.is_integer():
                time = str(int(self.step.channel_time[channel].time))
                if time == "0":
                    time = ""
            else:
                time = str(self.step.channel_time[channel].time)

            self.liststore.append([channel, delay, time])

        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_channeltime_changed)

        for i, column_title in enumerate(["Channel", "Delay", "Time"]):
            renderer = Gtk.CellRendererText()
            if i == 1:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.delay_edited)
            if i == 2:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.time_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        self.scrolled2.add(self.treeview)

        self.add2(self.scrolled2)

        self.flowbox.set_filter_func(self.filter_channels, None)

        # Select first Channel Time
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path)
        self.app.window.set_focus(self.treeview)

    def delay_edited(self, widget, path, text):
        if text == "":
            text = "0"
        if text.replace(".", "", 1).isdigit():
            if text == "0":
                self.liststore[path][1] = ""
            else:
                self.liststore[path][1] = text

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]
            # Delete Channel Time if Delay and Time are 0
            if self.step.channel_time[channel].time == 0 and text == "0":
                del self.step.channel_time[channel]
                # Redraw list of Channel Time
                self.liststore.clear()
                for channel in self.step.channel_time.keys():
                    if self.step.channel_time[channel].delay.is_integer():
                        delay = str(int(self.step.channel_time[channel].delay))
                        if delay == "0":
                            delay = ""
                    else:
                        delay = str(self.step.channel_time[channel].delay)
                    if self.step.channel_time[channel].time.is_integer():
                        time = str(int(self.step.channel_time[channel].time))
                        if time == "0":
                            time = ""
                    else:
                        time = str(self.step.channel_time[channel].time)
                    self.liststore.append([channel, delay, time])
                    self.treeview.set_model(self.liststore)
            else:
                # Update Delay value
                self.step.channel_time[channel].delay = float(text)
            # Update Sequence Tab if Open on the good sequence
            if self.app.sequences_tab:
                # Start to find the selected sequence
                seq_path, focus_column = self.app.sequences_tab.treeview1.get_cursor()
                selected = seq_path.get_indices()
                sequence = self.app.sequences_tab.liststore1[selected][0]
                # If the same sequence is selected
                if sequence == self.sequence.index:
                    path = Gtk.TreePath.new_from_indices([int(self.position) - 1])
                    ct_nb = len(self.step.channel_time)
                    if ct_nb == 0:
                        self.app.sequences_tab.liststore2[path][8] = ""
                    else:
                        self.app.sequences_tab.liststore2[path][8] = str(ct_nb)
            # Update Total Time
            if self.step.time_in > self.step.time_out:
                self.step.total_time = self.step.time_in + self.step.wait
            else:
                self.step.total_time = self.step.time_out + self.step.wait
            for channel in self.step.channel_time.keys():
                t = (
                    self.step.channel_time[channel].delay
                    + self.step.channel_time[channel].time
                    + self.step.wait
                )
                if t > self.step.total_time:
                    self.step.total_time = t

            # Redraw Main Playback
            if self.sequence == self.app.sequence:
                path1 = Gtk.TreePath.new_from_indices([int(self.position) + 2])
                path2 = Gtk.TreePath.new_from_indices([int(self.position)])
                ct_nb = len(self.step.channel_time)
                if ct_nb == 0:
                    self.app.window.cues_liststore1[path1][8] = ""
                    self.app.window.cues_liststore2[path2][8] = ""
                else:
                    self.app.window.cues_liststore1[path1][8] = str(ct_nb)
                    self.app.window.cues_liststore2[path2][8] = str(ct_nb)
                if self.app.sequence.position + 1 == int(self.position):
                    self.app.window.sequential.total_time = self.step.total_time
                    self.app.window.sequential.queue_draw()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def time_edited(self, widget, path, text):
        if text == "":
            text = "0"
        if text.replace(".", "", 1).isdigit():
            if text == "0":
                self.liststore[path][2] = ""
            else:
                self.liststore[path][2] = text

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]
            # Delete Channel Time if Delay and Time are 0
            if self.step.channel_time[channel].delay == 0 and text == "0":
                del self.step.channel_time[channel]
                # Redraw List of Channel Time
                self.liststore.clear()
                for channel in self.step.channel_time.keys():
                    if self.step.channel_time[channel].delay.is_integer():
                        delay = str(int(self.step.channel_time[channel].delay))
                        if delay == "0":
                            delay = ""
                    else:
                        delay = str(self.step.channel_time[channel].delay)
                    if self.step.channel_time[channel].time.is_integer():
                        time = str(int(self.step.channel_time[channel].time))
                        if time == "0":
                            time = ""
                    else:
                        time = str(self.step.channel_time[channel].time)
                    self.liststore.append([channel, delay, time])
                    self.treeview.set_model(self.liststore)
            else:
                # Update Time value
                self.step.channel_time[channel].time = float(text)
            # Update Sequence Tab if Open on the good sequence
            if self.app.sequences_tab:
                # Start to find the selected sequence
                seq_path, focus_column = self.app.sequences_tab.treeview1.get_cursor()
                selected = seq_path.get_indices()
                sequence = self.app.sequences_tab.liststore1[selected][0]
                # If the same sequence is selected
                if sequence == self.sequence.index:
                    path = Gtk.TreePath.new_from_indices([int(self.position) - 1])
                    ct_nb = len(self.step.channel_time)
                    if ct_nb == 0:
                        self.app.sequences_tab.liststore2[path][8] = ""
                    else:
                        self.app.sequences_tab.liststore2[path][8] = str(ct_nb)
            # Update Total Time
            if self.step.time_in > self.step.time_out:
                self.step.total_time = self.step.time_in + self.step.wait
            else:
                self.step.total_time = self.step.time_out + self.step.wait
            for channel in self.step.channel_time.keys():
                t = (
                    self.step.channel_time[channel].delay
                    + self.step.channel_time[channel].time
                    + self.step.wait
                )
                if t > self.step.total_time:
                    self.step.total_time = t

            # Redraw Main Playback
            if self.sequence == self.app.sequence:
                path1 = Gtk.TreePath.new_from_indices([int(self.position) + 2])
                path2 = Gtk.TreePath.new_from_indices([int(self.position)])
                ct_nb = len(self.step.channel_time)
                if ct_nb == 0:
                    self.app.window.cues_liststore1[path1][8] = ""
                    self.app.window.cues_liststore2[path2][8] = ""
                else:
                    self.app.window.cues_liststore1[path1][8] = str(ct_nb)
                    self.app.window.cues_liststore2[path2][8] = str(ct_nb)
                if self.app.sequence.position + 1 == int(self.position):
                    self.app.window.sequential.total_time = self.step.total_time
                    self.app.window.sequential.queue_draw()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def filter_channels(self, child, user_data):
        """ Filter Channels """

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]

            i = child.get_index()
            channels = self.step.cue.channels

            if channel - 1 == i or self.channels[i].clicked:
                self.channels[i].level = channels[i]
                self.channels[i].next_level = channels[i]
                return child
            else:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False
        # If no selected Channel Time, display selected channels
        else:
            i = child.get_index()
            channels = self.step.cue.channels

            if self.channels[i].clicked:
                self.channels[i].level = channels[i]
                self.channels[i].next_level = channels[i]
                return child
            else:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False

    def on_channeltime_changed(self, treeview):
        """ Select a Channel Time """
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            # self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab with the icon clicked """
        # If channel times has no delay and no time, delete it
        keys = list(self.step.channel_time.keys())
        for channel in keys:
            delay = self.step.channel_time[channel].delay
            time = self.step.channel_time[channel].time
            if delay == 0.0 and time == 0.0:
                del self.step.channel_time[channel]

        page = self.app.window.notebook.page_num(self.app.channeltime_tab)
        self.app.window.notebook.remove_page(page)
        self.app.channeltime_tab = None

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

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
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == "period":
            self.keystring += "."
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, "keypress_" + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        # If channel times has no delay and no time, delete it
        keys = list(self.step.channel_time.keys())
        for channel in keys:
            delay = self.step.channel_time[channel].delay
            time = self.step.channel_time[channel].time
            if delay == 0.0 and time == 0.0:
                del self.step.channel_time[channel]

        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.channeltime_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Channel """
        # TODO: Bug on Empty Channel time

        self.flowbox.unselect_all()

        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                self.channels[channel].clicked = True
                # self.flowbox.invalidate_filter()

                child = self.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = self.keystring

        self.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_q(self):
        """ Prev Channel Time """

        self.flowbox.unselect_all()

        path, focus_column = self.treeview.get_cursor()
        if path:
            if path.prev():
                self.treeview.set_cursor(path)
                self.app.window.set_focus(self.treeview)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview.set_cursor(path)
            self.app.window.set_focus(self.treeview)

    def keypress_w(self):
        """ Next Channel Time """

        self.flowbox.unselect_all()

        path, focus_column = self.treeview.get_cursor()
        if path:
            path.next()
            self.treeview.set_cursor(path)
            self.app.window.set_focus(self.treeview)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview.set_cursor(path)
            self.app.window.set_focus(self.treeview)

    def keypress_Insert(self):
        """ Add Channel Time """

        # Find selected channels
        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel)

                # If not already exist
                if channel not in self.step.channel_time:
                    # Add Channel Time
                    delay = 0.0
                    time = 0.0
                    self.step.channel_time[channel] = ChannelTime(delay, time)

                    # Update ui
                    self.liststore.append([channel, "", ""])
                    path = Gtk.TreePath.new_from_indices([len(self.liststore) - 1])
                    self.treeview.set_cursor(path)
                    self.app.window.set_focus(self.treeview)
