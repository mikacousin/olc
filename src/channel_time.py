from gi.repository import Gio, Gtk

from olc.customwidgets import ChannelWidget

class ChanneltimeTab(Gtk.Paned):
    def __init__(self, step):

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

        self.cue = Gio.Application.get_default().sequence.cues[int(step)]

        for channel in self.cue.channel_time.keys():

            if self.cue.channel_time[channel].delay.is_integer():
                delay = int(self.cue.channel_time[channel].delay)
            else:
                delay = self.cue.channel_time[channel].delay

            if self.cue.channel_time[channel].time.is_integer():
                time = int(self.cue.channel_time[channel].time)
            else:
                time = self.cue.channel_time[channel].time

            self.liststore.append([channel, str(delay), str(time)])

        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect('cursor-changed', self.on_channeltime_changed)

        for i, column_title in enumerate(["Channel", "Delay", "Time"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        self.scrolled2.add(self.treeview)

        self.add2(self.scrolled2)

        self.flowbox.set_filter_func(self.filter_channels, None)

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
