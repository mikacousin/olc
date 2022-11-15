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
from olc.define import App
from olc.widgets.channels_view import ChannelsView, VIEW_MODES


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

        self.channels_view = LiveChannelsView()

        self.append_page(self.channels_view, Gtk.Label("Channels"))
        self.set_tab_reorderable(self.channels_view, True)
        self.set_tab_detachable(self.channels_view, True)

        self.connect("key_press_event", self.on_key_press_event)
        self.connect("page-added", on_page_added)
        self.connect("page-removed", on_page_added)

    def update_channel_widget(self, channel: int, level: int, next_level: int) -> None:
        """Update display of channel widget

        Args:
            channel: Index of channel (from 1 to MAX_CHANNELS)
            level: Channel level (from 0 to 255)
            next_level: Channel next level (from 0 to 255)
        """
        widget = self.channels_view.get_channel_widget(channel)
        widget.level = level
        widget.next_level = next_level
        widget.queue_draw()

    def on_key_press_event(self, widget, event):
        """On key press event

        Args:
            widget: Gtk Widget
            event: Gdk.EventKey

        Returns:
            function() to handle keys pressed
        """
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Tab":
            return App().window.toggle_focus()
        # Find open page in notebook to send keyboard events
        page = self.get_current_page()
        child = self.get_nth_page(page)
        if child is App().tabs.tabs["patch_outputs"]:
            return App().tabs.tabs["patch_outputs"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["patch_channels"]:
            return App().tabs.tabs["patch_channels"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["groups"]:
            return App().tabs.tabs["groups"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["sequences"]:
            return App().tabs.tabs["sequences"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["channel_time"]:
            return App().tabs.tabs["channel_time"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["track_channels"]:
            return App().tabs.tabs["track_channels"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["memories"]:
            return App().tabs.tabs["memories"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["masters"]:
            return App().tabs.tabs["masters"].on_key_press_event(widget, event)
        if child is App().tabs.tabs["indes"]:
            return App().tabs.tabs["indes"].on_key_press_event(widget, event)

        return App().window.on_key_press_event(widget, event)


class LiveChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self):
        super().__init__()

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        if self.view_mode == VIEW_MODES["Active"]:
            channel_widget = child.get_child()
            return bool(
                channel_widget.level or channel_widget.next_level or child.is_selected()
            )

        channel = child.get_index() + 1
        if self.view_mode == VIEW_MODES["Patched"]:
            return channel in App().patch.channels
        if channel not in App().patch.channels:
            channel_widget = child.get_child()
            channel_widget.level = 0
        return True

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change patched channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        channels = self.get_selected_channels()
        for channel in channels:
            if App().patch.channels.get(channel):
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][out - 1]
                    if direction == Gdk.ScrollDirection.UP:
                        App().dmx.user[channel - 1] = min(level + step, 255)
                    elif direction == Gdk.ScrollDirection.DOWN:
                        App().dmx.user[channel - 1] = max(level - step, 0)
