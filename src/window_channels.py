# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget
from olc.zoom import zoom


def on_page_added(notebook, _child, _page_num):
    """Get focus

    Args:
        notebook: Gtk Notebook
    """
    notebook.grab_focus()


class LiveView(Gtk.Notebook):
    """Live Channels View"""

    def __init__(self):
        Gtk.Notebook.__init__(self)
        self.set_group_name("olc")

        # 0 : patched channels
        # 1 : all channels
        self.view_type = 0

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_func, None)

        for i in range(MAX_CHANNELS):
            self.flowbox.add(ChannelWidget(i + 1, 0, 0))

        scrolled.add(self.flowbox)

        self.append_page(scrolled, Gtk.Label("Channels"))
        self.set_tab_reorderable(scrolled, True)
        self.set_tab_detachable(scrolled, True)

        self.connect("key_press_event", self.on_key_press_event)
        self.connect("page-added", on_page_added)
        self.connect("page-removed", on_page_added)
        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", zoom)

    def update_channel_widget(self, channel: int, level: int, next_level: int) -> None:
        """Update display of channel widget

        Args:
            channel: Index of channel (from 0 to MAX_CHANNELS - 1)
            level: Channel level (from 0 to 255)
            next_level: Channel next level (from 0 to 255)
        """
        # Get ChannelWidget (child of FlowBoxChild in a FlowBox)
        widget = self.flowbox.get_child_at_index(channel).get_children()[0]
        widget.level = level
        widget.next_level = next_level
        widget.queue_draw()

    def filter_func(self, child, _user_data):
        """Filter for channels window

        Args:
            child: Child object

        Returns:
            child or False
        """
        if self.view_type:
            # Display all channels
            return child
        # Display only patched channels
        i = child.get_index() + 1
        return child if i in App().patch.channels else False

    def on_key_press_event(self, widget, event):
        """On key press event

        Args:
            widget: Gtk Widget
            event: Gdk.EventKey

        Returns:
            function() to handle keys pressed
        """
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
