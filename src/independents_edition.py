# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
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
import array
import typing
from typing import Callable

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS
from olc.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.lightshow import LightShow
    from olc.tabs_manager import Tabs
    from olc.window import Window


# pylint: disable=too-many-instance-attributes
class IndependentsTab(Gtk.Paned):
    """Tab to edit independents"""

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        # Channels modified by user
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings

        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.channels_view = IndeChannelsView(
            lightshow=self.lightshow,
            window=self.window,
            settings=self.settings,
            tabs=self.tabs,
        )
        self.add(self.channels_view)

        # List of independents
        self.liststore = Gtk.ListStore(int, str, str)
        for inde in self.lightshow.independents.independents:
            self.liststore.append([inde.number, inde.inde_type, inde.text])
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_changed)
        for i, column_title in enumerate(["Number", "Type", "Text"]):
            renderer = Gtk.CellRendererText()
            if i == 2:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.text_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.set_hexpand(True)
        scrollable.add(self.treeview)
        self.add(scrollable)

    def on_changed(self, _treeview: Gtk.TreeView) -> None:
        """Select independent"""
        self.channels_view.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        self.channels_view.update()

    def refresh(self) -> None:
        """Refresh display"""
        self.liststore.clear()
        for inde in self.lightshow.independents.independents:
            self.liststore.append([inde.number, inde.inde_type, inde.text])
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        self.tabs.close("indes")

    def text_edited(self, _widget: Gtk.Widget, path: int, text: str) -> None:
        """Independent text edited

        Args:
            path: Path to object
            text: New text
        """
        self.liststore[path][2] = text
        number = self.liststore[path][0]
        self.lightshow.independents.independents[number - 1].text = text

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Keyboard events

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        # Hack to know if user is editing something
        widget = self.window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.window.commandline.add_string(keyname)
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
            self.window.commandline.add_string(keyname[3:])
        if keyname == "period":
            self.window.commandline.add_string(".")
        # Channels View
        self.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        self.tabs.close("indes")

    def _keypress_backspace(self) -> None:
        self.window.commandline.set_string("")

    def _keypress_equal(self) -> None:
        """@ level"""
        self.channels_view.at_level()
        self.channels_view.update()
        self.window.commandline.set_string("")

    def _keypress_colon(self) -> None:
        """Level - %"""
        self.channels_view.level_minus()
        self.channels_view.update()

    def _keypress_exclam(self) -> None:
        """Level + %"""
        self.channels_view.level_plus()
        self.channels_view.update()

    def _keypress_u(self) -> None:
        """Update independent channels"""
        # Find independent
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            number = self.liststore[row][0]
            # Update channels level
            channels = {}
            for channel in range(MAX_CHANNELS):
                channel_widget = self.channels_view.get_channel_widget(channel + 1)
                channels[channel + 1] = channel_widget.level
            self.lightshow.independents.independents[number - 1].set_levels(channels)
            self.lightshow.independents.update_channels()
            self.lightshow.independents.independents[number - 1].update_dmx()
            self.window.live_view.channels_view.flowbox.queue_draw()
            self.channels_view.update()

            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)


class IndeChannelsView(ChannelsView):
    """Channels View"""

    def __init__(
        self,
        lightshow: LightShow,
        window: Window,
        settings: Gio.Settings,
        tabs: Tabs,
    ) -> None:
        super().__init__(
            lightshow=lightshow, window=window, settings=settings, tabs=tabs
        )
        self.tabs = tabs

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        typing.cast(IndependentsTab, self.tabs.tabs["indes"]).user_channels[
            channel - 1
        ] = level

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            level = channel_widget.level
            if direction == Gdk.ScrollDirection.UP:
                level = min(level + step, 255)
            elif direction == Gdk.ScrollDirection.DOWN:
                level = max(level - step, 0)
            channel_widget.level = level
            channel_widget.next_level = level
            channel_widget.queue_draw()
            self.set_channel_level(channel, level)

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        if (
            not self.lightshow.independents.independents
            or not self.tabs
            or not self.tabs.tabs["indes"]
        ):
            child.set_visible(False)
            return False
        # Find selected independent
        path, _focus_column = typing.cast(
            IndependentsTab, self.tabs.tabs["indes"]
        ).treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            if self.view_mode == VIEW_MODES["Active"]:
                return self._filter_active(row, child)
            if self.view_mode == VIEW_MODES["Patched"]:
                return self._filter_patched(row, child)
            return self._filter_all(row, child)
        child.set_visible(False)
        return False

    def _filter_active(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in Active mode

        Args:
            row: Row number
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channels = typing.cast(
            IndependentsTab, self.tabs.tabs["indes"]
        ).user_channels
        channels = self.lightshow.independents.independents[row].levels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels.get(channel_index + 1, 0)
                channel_widget.next_level = channels.get(channel_index + 1, 0)
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        if user_channels[channel_index] != -1:
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(False)
        return False

    def _filter_patched(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in Patched mode

        Args:
            row: Row number
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        # Return all patched channels
        channel = child.get_index() + 1
        if not self.lightshow.patch.is_patched(channel):
            child.set_visible(False)
            return False
        return self._filter_all(row, child)

    def _filter_all(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in All channels mode

        Args:
            row: Row number
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channels = typing.cast(
            IndependentsTab, self.tabs.tabs["indes"]
        ).user_channels
        channels = self.lightshow.independents.independents[row].levels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels.get(channel_index + 1, 0)
                channel_widget.next_level = channels.get(channel_index + 1, 0)
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        if user_channels[channel_index] != -1:
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True
