from gi.repository import Gio, Gtk, Gdk

from olc.customwidgets import ChannelWidget

class ChanneltimeTab(Gtk.Paned):
    def __init__(self, sequence, step):

        self.app = Gio.Application.get_default()
        self.sequence = sequence
        self.step = step

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
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)

        self.channels = []

        for i in range(512):
            self.channels.append(ChannelWidget(i+1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled1.add(self.flowbox)

        self.add1(self.scrolled1)

        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled2.set_vexpand(True)
        self.scrolled2.set_hexpand(True)

        # List of Channels Times
        self.liststore = Gtk.ListStore(int, str, str)

        self.cue = self.sequence.cues[int(step)]

        for channel in self.cue.channel_time.keys():

            if self.cue.channel_time[channel].delay.is_integer():
                delay = str(int(self.cue.channel_time[channel].delay))
                if delay == "0":
                    delay = ""
            else:
                delay = str(self.cue.channel_time[channel].delay)

            if self.cue.channel_time[channel].time.is_integer():
                time = str(int(self.cue.channel_time[channel].time))
                if time == "0":
                    time = ""
            else:
                time = str(self.cue.channel_time[channel].time)

            self.liststore.append([channel, delay, time])

        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect('cursor-changed', self.on_channeltime_changed)

        for i, column_title in enumerate(["Channel", "Delay", "Time"]):
            renderer = Gtk.CellRendererText()
            if i == 1:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.delay_edited)
            if i == 2:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.time_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        self.scrolled2.add(self.treeview)

        self.add2(self.scrolled2)

        self.flowbox.set_filter_func(self.filter_channels, None)

    def delay_edited(self, widget, path, text):
        if text == "":
            text = "0"
        if text.replace('.', '', 1).isdigit():
            if text == "0":
                self.liststore[path][1] = ""
            else:
                self.liststore[path][1] = text

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]
            # Delete Channel Time if Delay and Time are 0
            if self.cue.channel_time[channel].time == 0 and text == "0":
                del self.cue.channel_time[channel]
                # Redraw list of Channel Time
                self.liststore.clear()
                for channel in self.cue.channel_time.keys():
                    if self.cue.channel_time[channel].delay.is_integer():
                        delay = str(int(self.cue.channel_time[channel].delay))
                        if delay == "0":
                            delay = ""
                    else:
                        delay = str(self.cue.channel_time[channel].delay)
                    if self.cue.channel_time[channel].time.is_integer():
                        time = str(int(self.cue.channel_time[channel].time))
                        if time == "0":
                            time = ""
                    else:
                        time = str(self.cue.channel_time[channel].time)
                    self.liststore.append([channel, delay, time])
                    self.treeview.set_model(self.liststore)
                # Update Sequence Tab if Open on the good sequence
                if self.app.sequences_tab != None:
                    # Start to find the selected sequence
                    seq_path, focus_column = self.app.sequences_tab.treeview1.get_cursor()
                    selected = seq_path.get_indices()
                    sequence = self.app.sequences_tab.liststore1[selected][0]
                    # If the same sequence is selected
                    if sequence == self.sequence.index:
                        path = Gtk.TreePath.new_from_indices([int(self.step) - 1])
                        ct_nb = len(self.cue.channel_time)
                        if ct_nb == 0:
                            self.app.sequences_tab.liststore2[path][6] = ""
                        else:
                            self.app.sequences_tab.liststore2[path][6] = str(ct_nb)
            else:
                # Update Delay value
                self.cue.channel_time[channel].delay = float(text)
            # Update Total Time
            if self.cue.time_in > self.cue.time_out:
                self.cue.total_time = self.cue.time_in + self.cue.wait
            else:
                self.cue.total_time = self.cue.time_out + self.cue.wait
            for channel in self.cue.channel_time.keys():
                t = self.cue.channel_time[channel].delay + self.cue.channel_time[channel].time + self.cue.wait
                if t > self.cue.total_time:
                    self.cue.total_time = t

            # Redraw Main Playback
            if self.sequence == self.app.sequence:
                path = Gtk.TreePath.new_from_indices([int(self.step)])
                ct_nb = len(self.cue.channel_time)
                if ct_nb == 0:
                    self.app.window.cues_liststore1[path][6] = ""
                    self.app.window.cues_liststore2[path][6] = ""
                else:
                    self.app.window.cues_liststore1[path][6] = str(ct_nb)
                    self.app.window.cues_liststore2[path][6] = str(ct_nb)
                if self.app.sequence.position + 1 == int(self.step):
                    self.app.window.sequential.total_time = self.cue.total_time
                    self.app.window.sequential.queue_draw()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def time_edited(self, widget, path, text):
        if text == "":
            text = "0"
        if text.replace('.', '', 1).isdigit():
            if text == "0":
                self.liststore[path][2] = ""
            else:
                self.liststore[path][2] = text

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]
            # Delete Channel Time if Delay and Time are 0
            if self.cue.channel_time[channel].delay == 0 and text == "0":
                del self.cue.channel_time[channel]
                # Redraw List of Channel Time
                self.liststore.clear()
                for channel in self.cue.channel_time.keys():
                    if self.cue.channel_time[channel].delay.is_integer():
                        delay = str(int(self.cue.channel_time[channel].delay))
                        if delay == "0":
                            delay = ""
                    else:
                        delay = str(self.cue.channel_time[channel].delay)
                    if self.cue.channel_time[channel].time.is_integer():
                        time = str(int(self.cue.channel_time[channel].time))
                        if time == "0":
                            time = ""
                    else:
                        time = str(self.cue.channel_time[channel].time)
                    self.liststore.append([channel, delay, time])
                    self.treeview.set_model(self.liststore)
                # Update Sequence Tab if Open on the good sequence
                if self.app.sequences_tab != None:
                    # Start to find the selected sequence
                    seq_path, focus_column = self.app.sequences_tab.treeview1.get_cursor()
                    selected = seq_path.get_indices()
                    sequence = self.app.sequences_tab.liststore1[selected][0]
                    # If the same sequence is selected
                    if sequence == self.sequence.index:
                        path = Gtk.TreePath.new_from_indices([int(self.step) - 1])
                        ct_nb = len(self.cue.channel_time)
                        if ct_nb == 0:
                            self.app.sequences_tab.liststore2[path][6] = ""
                        else:
                            self.app.sequences_tab.liststore2[path][6] = str(ct_nb)
            else:
                # Update Time value
                self.cue.channel_time[channel].time = float(text)
            # Update Total Time
            if self.cue.time_in > self.cue.time_out:
                self.cue.total_time = self.cue.time_in + self.cue.wait
            else:
                self.cue.total_time = self.cue.time_out + self.cue.wait
            for channel in self.cue.channel_time.keys():
                t = self.cue.channel_time[channel].delay + self.cue.channel_time[channel].time + self.cue.wait
                if t > self.cue.total_time:
                    self.cue.total_time = t

            # Redraw Main Playback
            if self.sequence == self.app.sequence:
                path = Gtk.TreePath.new_from_indices([int(self.step)])
                ct_nb = len(self.cue.channel_time)
                if ct_nb == 0:
                    self.app.window.cues_liststore1[path][6] = ""
                    self.app.window.cues_liststore2[path][6] = ""
                else:
                    self.app.window.cues_liststore1[path][6] = str(ct_nb)
                    self.app.window.cues_liststore2[path][6] = str(ct_nb)
                if self.app.sequence.position + 1 == int(self.step):
                    self.app.window.sequential.total_time = self.cue.total_time
                    self.app.window.sequential.queue_draw()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def filter_channels(self, child, user_data):
        """ Filter Channels """

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]

            i = child.get_index()
            channels = self.cue.channels

            if channel - 1 == i or self.channels[i].clicked:
                self.channels[i].level = channels[i]
                self.channels[i].next_level = channels[i]
                return child
            else:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False

    def on_channeltime_changed(self, treeview):
        """ Select a Channel Time """
        for channel in range(512):
            self.channels[channel].clicked = False
            #self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab with the icon clicked """
        page = self.app.window.notebook.page_num(self.app.channeltime_tab)
        self.app.window.notebook.remove_page(page)
        self.app.channeltime_tab = None

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
        self.app.channeltime_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Channel """
        if self.keystring == "" or self.keystring == "0":
            for channel in range(512):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox.invalidate_filter()
        else:
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < 512:
                for chan in range(512):
                    self.channels[chan].clicked = False
                self.channels[channel].clicked = True
                self.flowbox.invalidate_filter()
                self.last_chan_selected = self.keystring
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Up(self):
        """ Prev Channel Time """
        path, focus_column = self.treeview.get_cursor()
        if path != None:
            if path.prev():
                self.treeview.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview.set_cursor(path)

    def keypress_Down(self):
        """ Next Channel Time """
        path, focus_column = self.treeview.get_cursor()
        if path != None:
            path.next()
            self.treeview.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview.set_cursor(path)
