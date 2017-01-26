from gi.repository import Gio, Gtk, Gdk

from olc.customwidgets import ChannelWidget

class ChanneltimeTab(Gtk.Paned):
    def __init__(self, step):

        self.app = Gio.Application.get_default()
        self.step = step

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

        self.cue = self.app.sequence.cues[int(step)]

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
        # TODO: If Delay and Time are 0, delete channel time
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

            if self.app.sequence.position + 1 == int(self.step):
                self.app.window.sequential.total_time = self.cue.total_time
                self.app.window.sequential.queue_draw()

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

            if self.app.sequence.position + 1 == int(self.step):
                self.app.window.sequential.total_time = self.cue.total_time
                self.app.window.sequential.queue_draw()

    def filter_channels(self, child, user_data):
        """ Filter Channels """

        # Find selected Channel Time
        path, focus_column = self.treeview.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]

            i = child.get_index()
            channels = self.cue.channels

            if channel - 1 == i:
                self.channels[i].level = channels[i]
                self.channels[i].next_level = channels[i]
                return child
            else:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False

    def on_channeltime_changed(self, treeview):
        """ Select a Channel Time """
        self.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab with the icon clicked """
        page = self.app.window.notebook.page_num(self.app.channeltime_tab)
        self.app.window.notebook.remove_page(page)
        self.app.channeltime_tab = None

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.channeltime_tab = None
