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
        if keyname == "ISO_Left_Tab":
            return App().window.move_tab()
        # Find open page in notebook to send keyboard events
        page = self.get_current_page()
        child = self.get_nth_page(page)
        if child in App().tabs.tabs.values():
            return child.on_key_press_event(widget, event)
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
        channel_widget = child.get_child()
        channel = child.get_index() + 1
        channel_widget.next_level = self.get_next_level(channel, channel_widget)
        if self.view_mode == VIEW_MODES["Active"]:
            return bool(
                channel_widget.level or channel_widget.next_level or child.is_selected()
            )

        if self.view_mode == VIEW_MODES["Patched"]:
            return channel in App().patch.channels
        if channel not in App().patch.channels:
            channel_widget.level = 0
        return True

    def get_next_level(self, channel: int, channel_widget) -> int:
        """Get Channel next level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            channel_widget: Channel widget

        Returns:
            Channel next level (0 - 255)
        """
        position = App().sequence.position
        if App().sequence.last > 1 and position < App().sequence.last - 1:
            next_level = App().sequence.steps[position + 1].cue.channels.get(channel, 0)
        elif App.sequence.last:
            next_level = App().sequence.steps[0].cue.channels.get(channel, 0)
        else:
            next_level = channel_widget.level
        return next_level

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level

        Args:
            channel: channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        App().dmx.user[channel - 1] = level

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
