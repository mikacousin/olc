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

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, is_float, is_int
from olc.gtk3.dialog import ConfirmationDialog
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.widgets.channel import ChannelWidget
    from olc.gtk3.window import Window


# pylint: disable=too-many-instance-attributes
class CuesEditionTab(Gtk.Paned):
    """Cues edition"""

    app: Application
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    commandline: CoreCommandLine
    liststore: Gtk.ListStore
    filter: Gtk.TreeModelFilter
    treeview: Gtk.TreeView
    scrollable: Gtk.ScrolledWindow
    channels_view: CueChannelsView

    def __init__(self, app: Application) -> None:
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.commandline = app.core.commandline

        # Cues tab initialization

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(500)

        self.channels_view = CueChannelsView(app=self.app)
        self.add(self.channels_view)

        # List of Cues
        self.liststore = Gtk.ListStore(str, str, int)

        for mem in self.lightshow.cues:
            channels = len(mem.channels)
            self.liststore.append([str(mem.number), mem.text, channels])

        self.filter = self.liststore.filter_new()

        self.treeview = Gtk.TreeView(model=self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_cue_changed)

        for i, column_title in enumerate(["Cue", "Text", "Channels"]):
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
        self.channels_view.update()

    def refresh(self) -> None:
        """Refresh display by syncing the liststore without clearing it entirely"""
        actual_cues = {str(mem.number): mem for mem in self.lightshow.cues}
        store = self.liststore
        it = store.get_iter_first()
        existing_memories = set()

        while isinstance(it, Gtk.TreeIter):
            mem_str = store.get_value(it, 0)
            if mem_str in actual_cues:
                cue = actual_cues[mem_str]
                nb_chan = len(cue.channels)

                curr_text = store.get_value(it, 1)
                curr_chan = store.get_value(it, 2)

                if curr_text != cue.text:
                    store.set_value(it, 1, cue.text)
                if curr_chan != nb_chan:
                    store.set_value(it, 2, nb_chan)

                existing_memories.add(mem_str)
                it = store.iter_next(it)
            else:
                it = store.remove(it)

        for mem in self.lightshow.cues:
            mem_str = str(mem.number)
            if mem_str not in existing_memories:
                nb_chan = len(mem.channels)
                insert_idx = 0
                it_insert = store.get_iter_first()
                while isinstance(it_insert, Gtk.TreeIter):
                    curr_mem_val = float(store.get_value(it_insert, 0))
                    if mem.number < curr_mem_val:
                        break
                    insert_idx += 1
                    it_insert = store.iter_next(it_insert)

                store.insert(insert_idx, [mem_str, mem.text, nb_chan])

        self.channels_view.update()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        self.tabs.close("memories")

    def _text_edited(self, _widget: Gtk.CellRendererText, path: str, text: str) -> None:
        cue = self.lightshow.cues[int(path)]
        self.window.app.core.action_registry.execute(
            "cue.rename", cue.number, cue.sequence, text
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
            self.commandline.add_string(keyname)

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
            self.commandline.add_string(keyname[3:])

        if keyname == "period":
            self.commandline.add_string(".")

        # Channels View
        self.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        self.tabs.close("memories")

    def _keypress_backspace(self) -> None:
        self.commandline.set_string("")

    def _keypress_equal(self) -> None:
        """@ level"""
        self.channels_view.at_level()
        self.channels_view.update()
        self.commandline.set_string("")

    def _keypress_colon(self) -> None:
        """Level - %"""
        self.channels_view.level_minus()
        self.channels_view.update()

    def _keypress_exclam(self) -> None:
        """Level + %"""
        self.channels_view.level_plus()
        self.channels_view.update()

    def _keypress_u(self) -> None:
        """Update Cue"""
        self.channels_view.flowbox.unselect_all()

        # Find selected cue
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Cue's channels
            cue = self.lightshow.cues[row]
            # Update levels and count channels
            channels_dict = {}
            cue_editor = self.lightshow.cues.cue_editor
            temp_levels = cue_editor.get_levels(cue.number, cue.sequence)
            for chan in range(MAX_CHANNELS):
                channel_widget = self.channels_view.get_channel_widget(chan + 1)
                if channel_widget is not None:
                    if (chan + 1 in cue.channels) or (temp_levels[chan] != -1):
                        channels_dict[chan + 1] = channel_widget.level
            self.window.app.core.action_registry.execute(
                "cue.update", cue.number, cue.sequence, channels_dict
            )

    def _keypress_delete(self) -> None:
        """Deletes selected Cue"""
        self.channels_view.flowbox.unselect_all()

        # Find selected cue
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Confirm Delete
            dialog = ConfirmationDialog(
                f"Delete cue {self.lightshow.cues[row].number} ?", self.window
            )
            response = dialog.run()
            if response == Gtk.ResponseType.CANCEL:
                dialog.destroy()
                return
            dialog.destroy()
            cue = self.lightshow.cues[row]
            self.window.app.core.action_registry.execute(
                "cue.delete", cue.number, cue.sequence
            )

    def _update_live_view_channels(self, i: int) -> None:
        channels_dict = self.lightshow.cues[i].channels
        for channel_num in range(1, MAX_CHANNELS + 1):
            widget = self.window.live_view.channels_view.get_channel_widget(channel_num)
            if widget:
                widget.next_level = channels_dict.get(channel_num, 0)
                widget.queue_draw()

    def _keypress_r(self) -> bool:
        """Records a copy of the current Cue with a new number

        Returns:
            True or False
        """
        if not is_float(self.commandline.get_string()):
            return False

        mem = float(self.commandline.get_string())
        if not mem:
            return False

        # Find selected cue
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            src_cue = self.lightshow.cues[row]
            self.window.app.core.action_registry.execute(
                "cue.copy", src_cue.number, mem, src_cue.sequence
            )

        self.commandline.set_string("")
        return True

    def _keypress_insert(self) -> bool:
        """Insert a new Cue

        Returns:
            True or False
        """
        keystring = self.commandline.get_string()
        if keystring == "":
            self._insert_cue_on_next_free_number()
            return True

        # Insert cue with the given number
        mem = float(keystring)

        # Cue already exist ?
        for item in self.lightshow.cues:
            if item.number == mem:
                return False

        # Find selected cue
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
        self.commandline.set_string("")
        return True

    def _insert_cue_on_next_free_number(self) -> None:
        cue_nb = None
        # Find Next free number
        if len(self.lightshow.cues) > 1:
            for i, _ in enumerate(self.lightshow.cues[:-1]):
                if (
                    int(self.lightshow.cues[i + 1].number)
                    - int(self.lightshow.cues[i].number)
                    > 1
                ):
                    cue_nb = self.lightshow.cues[i].number + 1
                    break
        elif len(self.lightshow.cues) == 1:
            # Just one cue
            cue_nb = self.lightshow.cues[0].number + 1
        else:
            # The list is empty
            cue_nb = 1.0
        # Free number is at the end
        if not cue_nb:
            cue_nb = self.lightshow.cues[-1].number + 1

        # Find selected cue for channels levels
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

    def __init__(self, app: Application) -> None:
        super().__init__(app=app)

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set level channel via temporary action.

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        if self.tabs is None or self.lightshow is None or self.window is None:
            return
        memories_tab = self.tabs.tabs.get("memories")
        if memories_tab is None:
            return
        tab = typing.cast(CuesEditionTab, memories_tab)
        path, _focus_column = tab.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            cue = self.lightshow.cues[row]
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels", cue.number, cue.sequence, {channel: level}
            )

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel using a group action.

        Args:
            step: Step level
            direction: Up or Down
        """
        if self.tabs is None or self.lightshow is None or self.window is None:
            return
        memories_tab = self.tabs.tabs.get("memories")
        if memories_tab is None:
            return
        tab = typing.cast(CuesEditionTab, memories_tab)
        path, _focus_column = tab.treeview.get_cursor()
        if not path:
            return
        row = path.get_indices()[0]
        cue = self.lightshow.cues[row]

        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if direction == Gdk.ScrollDirection.UP:
                    level = min(level + step, 255)
                elif direction == Gdk.ScrollDirection.DOWN:
                    level = max(level - step, 0)
                channels_dict[channel] = level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels", cue.number, cue.sequence, channels_dict
            )

    def at_level(self) -> None:
        """Channels at level using a group action."""
        if (
            not self.window
            or not self.settings
            or self.tabs is None
            or self.lightshow is None
        ):
            return
        memories_tab = self.tabs.tabs.get("memories")
        if memories_tab is None:
            return
        tab = typing.cast(CuesEditionTab, memories_tab)
        path, _focus_column = tab.treeview.get_cursor()
        if not path:
            return
        row = path.get_indices()[0]
        cue = self.lightshow.cues[row]

        keystring = self.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if self.settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        channels_dict = {channel: level for channel in channels}

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels", cue.number, cue.sequence, channels_dict
            )

    def level_plus(self) -> None:
        """Channels +% using a group action."""
        if (
            not self.settings
            or self.tabs is None
            or self.lightshow is None
            or self.window is None
        ):
            return
        memories_tab = self.tabs.tabs.get("memories")
        if memories_tab is None:
            return
        tab = typing.cast(CuesEditionTab, memories_tab)
        path, _focus_column = tab.treeview.get_cursor()
        if not path:
            return
        row = path.get_indices()[0]
        cue = self.lightshow.cues[row]

        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                channels_dict[channel] = new_level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels", cue.number, cue.sequence, channels_dict
            )

    def level_minus(self) -> None:
        """Channels -% using a group action."""
        if (
            not self.settings
            or self.tabs is None
            or self.lightshow is None
            or self.window is None
        ):
            return
        memories_tab = self.tabs.tabs.get("memories")
        if memories_tab is None:
            return
        tab = typing.cast(CuesEditionTab, memories_tab)
        path, _focus_column = tab.treeview.get_cursor()
        if not path:
            return
        row = path.get_indices()[0]
        cue = self.lightshow.cues[row]

        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                channels_dict[channel] = new_level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels", cue.number, cue.sequence, channels_dict
            )

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
        cue_editor = self.lightshow.cues.cue_editor
        cue = self.lightshow.cues[row]
        user_channels = cue_editor.get_levels(cue.number, cue.sequence)
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
        cue_editor = self.lightshow.cues.cue_editor
        cue = self.lightshow.cues[row]
        user_channels = cue_editor.get_levels(cue.number, cue.sequence)
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
