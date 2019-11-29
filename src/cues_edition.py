from gi.repository import Gtk, Gio

class CuesEditionTab(Gtk.Paned):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ''
        self.last_chan_selected = ''

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        # Channels used in selected Memory
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

        # List of Memories
        self.liststore = Gtk.ListStore(str, str)
