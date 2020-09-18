"""Channels view in main window"""

from gi.repository import Gtk, Gdk
from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget


def on_page_added(notebook, _child, _page_num):
    """Get focus"""
    notebook.grab_focus()


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
        self.set_tab_reorderable(paned, True)
        self.set_tab_detachable(paned, True)

        self.connect("key_press_event", self.on_key_press_event)
        self.connect("page-added", on_page_added)
        self.connect("page-removed", on_page_added)
        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", self.on_scroll)

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

    def on_scroll(self, widget, event):
        """Executed on scroll wheel mouse event"""
        # Zoom In/Out Channels in Live View
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if (
            event.state & accel_mask
            == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        ):
            (scroll, direction) = event.get_scroll_direction()
            if scroll and direction == Gdk.ScrollDirection.UP:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale < 2:
                        self.channels[i].scale += 0.1
            if scroll and direction == Gdk.ScrollDirection.DOWN:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale >= 1.1:
                        self.channels[i].scale -= 0.1
            self.flowbox.queue_draw()

    def on_key_press_event(self, widget, event):
        """On key press event"""
        # Find open page in notebook to send keyboard events
        page = self.get_current_page()
        child = self.get_nth_page(page)
        if child == App().patch_outputs_tab:
            return App().patch_outputs_tab.on_key_press_event(widget, event)
        if child == App().patch_channels_tab:
            return App().patch_channels_tab.on_key_press_event(widget, event)
        if child == App().group_tab:
            return App().group_tab.on_key_press_event(widget, event)
        if child == App().sequences_tab:
            return App().sequences_tab.on_key_press_event(widget, event)
        if child == App().channeltime_tab:
            return App().channeltime_tab.on_key_press_event(widget, event)
        if child == App().track_channels_tab:
            return App().track_channels_tab.on_key_press_event(widget, event)
        if child == App().memories_tab:
            return App().memories_tab.on_key_press_event(widget, event)
        if child == App().masters_tab:
            return App().masters_tab.on_key_press_event(widget, event)
        if child == App().inde_tab:
            return App().inde_tab.on_key_press_event(widget, event)

        return App().window.on_key_press_event(widget, event)
