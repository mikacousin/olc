"""Channels view in main window"""

from gi.repository import Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget


class ChannelsView(Gtk.Notebook):
    """Channels View"""

    def __init__(self):
        Gtk.Notebook.__init__(self)
        self.set_group_name("olc")

        # 0 : patched channels
        # 1 : all channels
        self.view_type = 0

        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned.set_position(1100)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_func, None)

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox.add(self.channels[i])

        scrolled.add(self.flowbox)
        paned.pack1(scrolled, resize=True, shrink=False)

        # Gtk.Statusbar to display keyboard's keys
        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("keypress")

        grid = Gtk.Grid()
        label = Gtk.Label("Input : ")
        grid.add(label)
        grid.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)
        paned.pack2(grid, resize=True, shrink=False)

        self.append_page(paned, Gtk.Label("Channels"))

    def filter_func(self, child, _user_data):
        """Filter for channels window"""
        if self.view_type == 0:
            # Display only patched channels
            i = child.get_index()
            for channel in App().patch.channels[i][0]:
                if channel != 0:
                    return child
                return False
        else:
            # Display all channels
            return True
