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
from __future__ import annotations

import typing
from typing import Callable

import numpy as np
from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, is_float
from olc.dialog import ConfirmationDialog
from olc.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.lightshow import LightShow
    from olc.tabs_manager import Tabs
    from olc.widgets.channel import ChannelWidget
    from olc.window import Window


# pylint: disable=too-many-instance-attributes
class CuesEditionTab(Gtk.Paned):
    """Cues edition"""

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings

        # Channels modified by user
        self.user_channels = np.full(MAX_CHANNELS, -1, dtype=np.int16)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(500)

        self.channels_view = CueChannelsView(
            self.lightshow, self.tabs, self.window, self.settings
        )
        self.add(self.channels_view)

        # List of Cues
        self.liststore = Gtk.ListStore(str, str, int)

        for mem in self.lightshow.cues:
            channels = len(mem.channels)
            self.liststore.append([str(mem.memory), mem.text, channels])

        self.filter = self.liststore.filter_new()

        self.treeview = Gtk.TreeView(model=self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_cue_changed)

        for i, column_title in enumerate(["Memory", "Text", "Channels"]):
            renderer = Gtk.CellRendererText()
            if i == 1:
                renderer.set_property("editable", True)
                renderer.connect("edited", self._text_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)

            self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

    def on_cue_changed(self, _treeview: Gtk.TreeView) -> None:
        """Selected Cue"""
        self.channels_view.flowbox.unselect_all()
        self.user_channels = np.full(MAX_CHANNELS, -1, dtype=np.int16)
        self.channels_view.update()

    def refresh(self) -> None:
        """Refresh display"""
        self.liststore.clear()
        for mem in self.lightshow.cues:
            channels = len(mem.channels)
            self.liststore.append([str(mem.memory), mem.text, channels])
        self.channels_view.update()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        self.tabs.close("memories")

    def _text_edited(self, _widget: Gtk.CellRendererText, path: str, text: str) -> None:
        cue = self.lightshow.cues[int(path)]
        self.window.app.core.action_registry.execute(
            "cue.rename", cue.memory, cue.sequence, text
        )

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Key has been pressed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
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
        self.tabs.close("memories")

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
        """Update Memory"""
        self.channels_view.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Memory's channels
            cue = self.lightshow.cues[row]
            # Update levels and count channels
            channels_dict = {}
            for chan in range(MAX_CHANNELS):
                channel_widget = self.channels_view.get_channel_widget(chan + 1)
                if channel_widget is not None:
                    if (chan + 1 in cue.channels) or (self.user_channels[chan] != -1):
                        channels_dict[chan + 1] = channel_widget.level
            self.window.app.core.action_registry.execute(
                "cue.update", cue.memory, cue.sequence, channels_dict
            )

    def _keypress_delete(self) -> None:
        """Deletes selected Memory"""
        self.channels_view.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Confirm Delete
            dialog = ConfirmationDialog(
                f"Delete memory {self.lightshow.cues[row].memory} ?", self.window
            )
            response = dialog.run()
            if response == Gtk.ResponseType.CANCEL:
                dialog.destroy()
                return
            dialog.destroy()
            cue = self.lightshow.cues[row]
            self.window.app.core.action_registry.execute(
                "cue.delete", cue.memory, cue.sequence
            )

    def _update_live_view_channels(self, i: int) -> None:
        channels_dict = self.lightshow.cues[i].channels
        for channel_num in range(1, MAX_CHANNELS + 1):
            widget = self.window.live_view.channels_view.get_channel_widget(channel_num)
            if widget:
                widget.next_level = channels_dict.get(channel_num, 0)
                widget.queue_draw()

    def _keypress_r(self) -> bool:
        """Records a copy of the current Memory with a new number

        Returns:
            True or False
        """
        if not is_float(self.window.commandline.get_string()):
            return False

        mem = float(self.window.commandline.get_string())
        if not mem:
            return False

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            src_cue = self.lightshow.cues[row]
            self.window.app.core.action_registry.execute(
                "cue.copy", src_cue.memory, mem, src_cue.sequence
            )

        self.window.commandline.set_string("")
        return True

    def _keypress_insert(self) -> bool:
        """Insert a new Memory

        Returns:
            True or False
        """
        keystring = self.window.commandline.get_string()
        if keystring == "":
            self._insert_cue_on_next_free_number()
            return True

        # Insert memory with the given number
        mem = float(keystring)

        # Memory already exist ?
        for item in self.lightshow.cues:
            if item.memory == mem:
                return False

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            sequence = self.lightshow.cues[row].sequence
            channels = self.lightshow.cues[row].channels
        else:
            sequence = 0
            channels = None

        self.window.app.core.action_registry.execute(
            "cue.insert", mem, sequence, channels
        )
        self.window.commandline.set_string("")
        return True

    def _insert_cue_on_next_free_number(self) -> None:
        cue_nb = None
        # Find Next free number
        if len(self.lightshow.cues) > 1:
            for i, _ in enumerate(self.lightshow.cues[:-1]):
                if (
                    int(self.lightshow.cues[i + 1].memory)
                    - int(self.lightshow.cues[i].memory)
                    > 1
                ):
                    cue_nb = self.lightshow.cues[i].memory + 1
                    break
        elif len(self.lightshow.cues) == 1:
            # Just one memory
            cue_nb = self.lightshow.cues[0].memory + 1
        else:
            # The list is empty
            cue_nb = 1.0
        # Free number is at the end
        if not cue_nb:
            cue_nb = self.lightshow.cues[-1].memory + 1

        # Find selected memory for channels levels
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            sequence = self.lightshow.cues[row].sequence
            channels = self.lightshow.cues[row].channels
        else:
            sequence = 0
            channels = None

        self.window.app.core.action_registry.execute(
            "cue.insert", cue_nb, sequence, channels
        )


class CueChannelsView(ChannelsView):
    """Channels View"""

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        super().__init__(
            lightshow=lightshow, window=window, settings=settings, tabs=tabs
        )

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set level channel

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        if self.tabs is None:
            return
        memories_tab = self.tabs.tabs.get("memories")
        if memories_tab is None:
            return
        tab = typing.cast(CuesEditionTab, memories_tab)
        tab.user_channels[channel - 1] = level

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        channels = self.get_selected_channels()
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
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
            self.lightshow is None
            or not self.lightshow.cues
            or self.tabs is None
            or self.tabs.tabs.get("memories") is None
        ):
            child.set_visible(False)
            return False
        # Find selected row
        tab = typing.cast(CuesEditionTab, self.tabs.tabs["memories"])
        path, _focus_column = tab.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            if row < 0 or row >= len(self.lightshow.cues):
                child.set_visible(False)
                return False
            if self.view_mode == VIEW_MODES["Active"]:
                visible = self.__filter_active(row, child)
                child.set_visible(visible)
                return visible
            if self.view_mode == VIEW_MODES["Patched"]:
                visible = self.__filter_patched(row, child)
                child.set_visible(visible)
                return visible
            self.__filter_all(row, child)
            child.set_visible(True)
            return True
        child.set_visible(False)
        return False

    def __filter_active(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        if (
            self.tabs is None
            or self.tabs.tabs.get("memories") is None
            or self.lightshow is None
        ):
            return False
        user_channels = typing.cast(
            CuesEditionTab, self.tabs.tabs["memories"]
        ).user_channels
        channel_index = child.get_index()
        channel_widget = child.get_child()
        if channel_widget is None:
            return False
        widget = typing.cast("ChannelWidget", channel_widget)
        # Channels in Cue
        channels = self.lightshow.cues[row].channels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                widget.level = int(channels.get(channel_index + 1, 0))
                widget.next_level = int(channels.get(channel_index + 1, 0))
            else:
                widget.level = int(user_channels[channel_index])
                widget.next_level = int(user_channels[channel_index])
            return True
        if user_channels[channel_index] == -1:
            widget.level = 0
            widget.next_level = 0
            return False
        widget.level = int(user_channels[channel_index])
        widget.next_level = int(user_channels[channel_index])
        return True

    def __filter_patched(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        """Return all patched channels

        Args:
            row: Cue index
            child: FlowBoxChild corresponding to a channel

        Returns:
            True if patched, else False
        """
        channel = child.get_index() + 1
        if self.lightshow is None or not self.lightshow.patch.is_patched(channel):
            return False
        return self.__filter_all(row, child)

    def __filter_all(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        if (
            self.tabs is None
            or self.tabs.tabs.get("memories") is None
            or self.lightshow is None
        ):
            return False
        user_channels = typing.cast(
            CuesEditionTab, self.tabs.tabs["memories"]
        ).user_channels
        channel_index = child.get_index()
        channel_widget = child.get_child()
        if channel_widget is None:
            return False
        widget = typing.cast("ChannelWidget", channel_widget)
        # Channels in Cue
        channels = self.lightshow.cues[row].channels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                widget.level = int(channels.get(channel_index + 1, 0))
                widget.next_level = int(channels.get(channel_index + 1, 0))
            else:
                widget.level = int(user_channels[channel_index])
                widget.next_level = int(user_channels[channel_index])
            return True
        if user_channels[channel_index] == -1:
            widget.level = 0
            widget.next_level = 0
            return True
        widget.level = int(user_channels[channel_index])
        widget.next_level = int(user_channels[channel_index])
        return True
