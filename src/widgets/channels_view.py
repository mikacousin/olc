# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Any, Dict, List, Optional

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App, is_non_nul_int

from .channel import ChannelWidget

VIEW_MODES: Dict[str, int] = {"All": 0, "Patched": 1, "Active": 2}


class ChannelsView(Gtk.Box):
    """Channels view

    This class must be subclassed and filter_channels, wheel_level, set_channel_level
    implemented
    """

    view_mode: int
    last_selected_channel: str
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox

    def __init__(self, *args, **kwargs):
        super().__init__(*args, orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.view_mode = VIEW_MODES.get("All")
        self.last_selected_channel = ""

        header = Gtk.HeaderBar()
        self.combo = Gtk.ComboBoxText()
        self.combo.set_entry_text_column(0)
        self.combo.connect("changed", self._on_view_mode_changed)
        for mode in VIEW_MODES:
            self.combo.append_text(mode)
        header.pack_end(self.combo)
        self.pack_start(header, False, False, 0)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_channels, None)
        for i in range(MAX_CHANNELS):
            self.flowbox.add(ChannelWidget(i + 1, 0, 0))
        self.scrolled.add(self.flowbox)

        self.pack_start(self.scrolled, True, True, 0)
        self.combo.set_active(0)

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> Any:
        """Display channels

        Args:
            child: Parent of Channel Widget

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def set_channel_level(self, channel: int, level: int) -> None:
        """Channel at level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def update(self) -> None:
        """Update channels display"""
        self.flowbox.invalidate_filter()

    def get_channel_widget(self, channel: int) -> Optional[ChannelWidget]:
        """Get ChannelWidget of channel number

        Args:
            channel: Channel (1-MAX_CHANNELS)

        Returns:
            Channel widget
        """
        if 0 < channel <= MAX_CHANNELS:
            flowboxchild = self.flowbox.get_child_at_index(channel - 1)
            return flowboxchild.get_child()
        return None

    def _on_view_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        """Change View Mode

        Args:
            combo: Widget to change mode
        """
        text = combo.get_active_text()
        if text is not None:
            index = VIEW_MODES.get(text, 0)
            self.view_mode = index
            self.flowbox.invalidate_filter()
        self.grab_focus()

    def _toggle_view_mode(self) -> None:
        """Select next View Mode"""
        index = self.view_mode + 1
        if index not in VIEW_MODES.values():
            index = 0
        self.combo.set_active(index)

    def select_channel(self, channel: int) -> None:
        """Select one channel

        Args:
            channel: Channel to select
        """
        self.flowbox.unselect_all()
        if channel:
            flowboxchild = self.flowbox.get_child_at_index(channel - 1)
            self.flowbox.select_child(flowboxchild)
            App().window.set_focus(flowboxchild)
            self.flowbox.invalidate_filter()
            self.last_selected_channel = str(channel)
            self.grab_focus()

    def select_plus(self, channel: int) -> None:
        """Add channel to selection

        Args:
            channel: Channel to select
        """
        if not channel:
            return
        flowboxchild = self.flowbox.get_child_at_index(channel - 1)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = str(channel)
        self.grab_focus()

    def select_minus(self, channel: int) -> None:
        """Remove channel from selection

        Args:
            channel: Channel to deselect
        """
        if not channel:
            return
        flowboxchild = self.flowbox.get_child_at_index(channel - 1)
        self.flowbox.unselect_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = str(channel)
        self.grab_focus()

    def select_thru(self, from_channel: int, to_channel: int) -> None:
        """Select a series of channels

        Args:
            from_channel: Start channel
            to_channel: End channel
        """
        if not from_channel or not to_channel:
            return
        if from_channel < to_channel:
            for channel in range(from_channel - 1, to_channel):
                if 0 <= channel < MAX_CHANNELS:
                    flowboxchild = self.flowbox.get_child_at_index(channel)
                    self.flowbox.select_child(flowboxchild)
        else:
            for channel in range(to_channel - 1, from_channel):
                if 0 <= channel < MAX_CHANNELS:
                    flowboxchild = self.flowbox.get_child_at_index(channel)
                    self.flowbox.select_child(flowboxchild)
        if flowboxchild:
            App().window.set_focus(flowboxchild)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = str(to_channel)
        self.grab_focus()

    def deselect_thru(self, from_channel: int, to_channel: int) -> None:
        """Remove a series of channels

        Args:
            from_channel: Start channel
            to_channel: End channel
        """
        if not from_channel or not to_channel:
            return
        if from_channel < to_channel:
            for channel in range(from_channel - 1, to_channel):
                if 0 <= channel < MAX_CHANNELS:
                    flowboxchild = self.flowbox.get_child_at_index(channel)
                    self.flowbox.unselect_child(flowboxchild)
        else:
            for channel in range(to_channel - 1, from_channel):
                if 0 <= channel < MAX_CHANNELS:
                    flowboxchild = self.flowbox.get_child_at_index(channel)
                    self.flowbox.unselect_child(flowboxchild)
        if flowboxchild:
            App().window.set_focus(flowboxchild)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = str(to_channel)
        self.grab_focus()

    def select_next(self) -> int | None:
        """Select next channel

        Returns:
            Channel number or None
        """
        self.flowbox.unselect_all()
        if self.last_selected_channel and not is_non_nul_int(
                self.last_selected_channel):
            return None
        if self.view_mode == VIEW_MODES["Patched"]:
            return self._next_patched()
        if self.view_mode == VIEW_MODES["Active"]:
            return self._next_active()
        # Default mode: All channels
        selected_channel = ""
        channel_index = (int(self.last_selected_channel)
                         if self.last_selected_channel else 0)

        if channel_index > MAX_CHANNELS - 1:
            channel_index = 0
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel
        return channel_index + 1

    def _next_active(self) -> int:
        """Select next channel in Active mode view

        Returns:
            Channel number
        """
        selected_channel = ""
        children = self.flowbox.get_children()
        start = (int(self.last_selected_channel)
                 if self.last_selected_channel else self.__get_first_active_channel())

        for child in children:
            channel_index = child.get_index()
            if child.get_visible() and channel_index >= start:
                break
        if channel_index + 1 >= MAX_CHANNELS:
            channel_index = self.__get_first_active_channel()
        selected_channel = str(channel_index + 1)
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel
        return channel_index + 1

    def _next_patched(self) -> int:
        """Select next channel in Patched mode view

        Returns:
            Channel number
        """
        start = (int(self.last_selected_channel) if self.last_selected_channel else
                 App().lightshow.patch.get_first_patched_channel() - 1)

        for channel_index in range(start, MAX_CHANNELS):
            if App().lightshow.patch.is_patched(channel_index + 1):
                break
        if channel_index + 1 >= MAX_CHANNELS:
            channel_index = App().lightshow.patch.get_first_patched_channel() - 1
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel
        return channel_index + 1

    def select_previous(self) -> int | None:
        """Select previous channel

        Returns:
            Channel number or None
        """
        self.flowbox.unselect_all()
        if self.last_selected_channel and not is_non_nul_int(
                self.last_selected_channel):
            return None
        if self.view_mode == VIEW_MODES["Patched"]:
            return self._previous_patched()
        if self.view_mode == VIEW_MODES["Active"]:
            return self._previous_active()
        # Default mode: All channels
        selected_channel = ""
        channel_index = (int(self.last_selected_channel) -
                         2 if self.last_selected_channel else 0)

        if channel_index < 0:
            channel_index = MAX_CHANNELS - 1
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel
        return channel_index + 1

    def _previous_active(self) -> int:
        """Select previous channel in Active mode view

        Returns:
            Channel number
        """
        selected_channel = ""
        start = (int(self.last_selected_channel) -
                 2 if self.last_selected_channel else self.__get_last_active_channel() +
                 1)

        children = self.flowbox.get_children()
        children.reverse()
        for child in children:
            channel_index = child.get_index()
            if child.get_visible() and channel_index <= start:
                break
        if channel_index < self.__get_first_active_channel() or start < 0:
            channel_index = self.__get_last_active_channel()
        selected_channel = str(channel_index + 1)
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel
        return channel_index + 1

    def _previous_patched(self) -> int:
        """Select previous channel in Patched mode view

        Returns:
            Channel number
        """
        start = (int(self.last_selected_channel) - 2 if self.last_selected_channel else
                 App().lightshow.patch.get_last_patched_channel())

        for channel_index in range(start, 0, -1):
            if App().lightshow.patch.is_patched(channel_index + 1):
                break
        if channel_index < App().lightshow.patch.get_first_patched_channel() - 1:
            channel_index = App().lightshow.patch.get_last_patched_channel() - 1
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel
        return channel_index + 1

    def select_all(self) -> None:
        """Select all channel with a level > 0"""
        self.flowbox.unselect_all()
        channels = []
        for channel_index in range(MAX_CHANNELS):
            flowboxchild = self.flowbox.get_child_at_index(channel_index)
            channel_widget = flowboxchild.get_child()
            level = channel_widget.level
            if level:
                channels.append(channel_index + 1)
        string = App().window.commandline.get_selection_string(channels)
        App().window.commandline.set_string(string)
        App().window.commandline.add_string("\n", context=self)

    def at_level(self, level: int) -> None:
        """Selected channels at level

        Args:
            level: Level
        """
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        for channel in channels:
            self.set_channel_level(channel, level)

    def thru_level(self, from_level: int, to_level: int) -> None:
        """Distribute levels over selected channels

        Args:
            from_level: Start level
            to_level: Final level
        """
        if App().settings.get_boolean("percent"):
            from_level = int(round((from_level / 100) * 255))
            to_level = int(round((to_level / 100) * 255))
        from_level = min(from_level, 255)
        to_level = min(to_level, 255)
        channels = self.get_selected_channels()
        step = (to_level - from_level) / (len(channels) - 1)
        for index, channel in enumerate(channels):
            self.set_channel_level(channel, from_level + round(index * step))

    def level_plus(self) -> None:
        """Channels +%"""
        step_level = App().settings.get_int("percent-level")
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if App().settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                self.set_channel_level(channel, new_level)

    def level_minus(self) -> None:
        """Channels -%"""
        step_level = App().settings.get_int("percent-level")
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if App().settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                self.set_channel_level(channel, new_level)

    def get_selected_channels(self) -> List[int]:
        """Return selected channels

        Returns:
            Selected channels
        """
        channels = []
        selected = self.flowbox.get_selected_children()
        for flowboxchild in selected:
            channel = int(flowboxchild.get_child().channel)
            channels.append(channel)
        return channels

    def __get_first_active_channel(self) -> int:
        """Return first active channel index

        Returns:
            Channel index (from 0 to MAX_CHANNELS - 1)
        """
        child = None
        children = self.flowbox.get_children()
        for child in children:
            if child.get_visible():
                break
        return child.get_index()

    def __get_last_active_channel(self) -> int:
        """Return last active channel index

        Returns:
            Channel index (from 0 to MAX_CHANNELS - 1)
        """
        child = None
        children = self.flowbox.get_children()
        children.reverse()
        for child in children:
            if child.get_visible():
                break
        return child.get_index()

    def grab_focus(self) -> None:
        """Grab focus to active Tab"""
        parent = self.get_parent()
        if App().window and parent in (App().window.live_view, App().window.playback):
            parent.grab_focus()
        elif parent:
            parent.get_parent().grab_focus()

    def on_key_press(self, keyname: str) -> Any:
        """Processes common keyboard methods of Channels View

        Args:
            keyname: Gdk Name of the pressed key

        Returns:
            method or None
        """
        if keyname in {
                "f",
                "Page_Up",
                "Page_Down",
                "a",
                "c",
                "KP_Divide",
                "greater",
                "KP_Add",
                "plus",
                "KP_Subtract",
                "minus",
        }:
            if func := getattr(self, f"_keypress_{keyname.lower()}", None):
                return func()
        return None

    def _keypress_f(self) -> None:
        """Toggle display mode"""
        self._toggle_view_mode()
        self.grab_focus()

    def _keypress_a(self) -> None:
        """All Channels"""
        self.select_all()
        self.grab_focus()

    def _keypress_page_up(self) -> None:
        """Next Channel"""
        channel = self.select_next()
        self.grab_focus()
        if channel:
            App().window.commandline.set_string(f"chan {channel}")
        else:
            App().window.commandline.set_string("")

    def _keypress_page_down(self) -> None:
        """Previous Channel"""
        channel = self.select_previous()
        self.grab_focus()
        if channel:
            App().window.commandline.set_string(f"chan {channel}")
        else:
            App().window.commandline.set_string("")

    def _keypress_c(self) -> None:
        """Channel"""
        App().window.commandline.add_string(" chan ", context=self)
        self.grab_focus()

    def _keypress_kp_divide(self):
        self._keypress_greater()

    def _keypress_greater(self) -> None:
        """Channel Thru"""
        App().window.commandline.add_string(" thru ", context=self)
        self.grab_focus()

    def _keypress_kp_add(self):
        self._keypress_plus()

    def _keypress_plus(self) -> None:
        """Channel +"""
        App().window.commandline.add_string(" + ", context=self)
        self.grab_focus()

    def _keypress_kp_subtract(self):
        self._keypress_minus()

    def _keypress_minus(self) -> None:
        """Channel -"""
        App().window.commandline.add_string(" - ", context=self)
        self.grab_focus()
