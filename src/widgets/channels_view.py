# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
from olc.define import App, MAX_CHANNELS, is_non_nul_int, is_int
from olc.zoom import zoom
from .channel import ChannelWidget

VIEW_MODES: Dict[str, int] = {"All": 0, "Patched": 1, "Active": 2}


class ChannelsView(Gtk.Box):
    """Channels view

    This class must be subclassed and filter_channels implemented
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
        self.combo.connect("changed", self.on_view_mode_changed)
        for mode in VIEW_MODES:
            self.combo.append_text(mode)
        header.pack_end(self.combo)
        self.pack_start(header, False, False, 0)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_channels, None)
        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", zoom)
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

    def on_view_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        """Change View Mode

        Args:
            combo: Widget to change mode
        """
        text = combo.get_active_text()
        if text is not None:
            index = VIEW_MODES.get(text, 0)
            self.view_mode = index
            self.flowbox.invalidate_filter()

    def toggle_view_mode(self) -> None:
        """Select next View Mode"""
        index = self.view_mode + 1
        if index not in VIEW_MODES.values():
            index = 0
        self.combo.set_active(index)

    def select_channel(self, keystring: str) -> None:
        """Select one channel

        Args:
            keystring: Channel number (1-MAX_CHANNELS)
        """
        string = ""
        self.flowbox.unselect_all()
        if is_non_nul_int(keystring):
            channel = int(keystring)
            if 0 < channel <= MAX_CHANNELS:
                flowboxchild = self.flowbox.get_child_at_index(channel - 1)
                self.flowbox.select_child(flowboxchild)
                App().window.set_focus(flowboxchild)
                string = keystring
        self.flowbox.invalidate_filter()
        self.last_selected_channel = string

    def select_plus(self, keystring: str) -> None:
        """Add channel to selection

        Args:
            keystring: Channel number (1-MAX_CHANNELS)
        """
        string = ""
        if is_non_nul_int(keystring):
            channel = int(keystring)
            if 0 < channel <= MAX_CHANNELS:
                flowboxchild = self.flowbox.get_child_at_index(channel - 1)
                self.flowbox.select_child(flowboxchild)
                App().window.set_focus(flowboxchild)
                string = keystring
        self.flowbox.invalidate_filter()
        self.last_selected_channel = string

    def select_minus(self, keystring: str) -> None:
        """Remove channel from selection

        Args:
            keystring: Channel number (1-MAX_CHANNELS)
        """
        string = ""
        if is_non_nul_int(keystring):
            channel = int(keystring)
            if 0 < channel <= MAX_CHANNELS:
                flowboxchild = self.flowbox.get_child_at_index(channel - 1)
                self.flowbox.unselect_child(flowboxchild)
                App().window.set_focus(flowboxchild)
                string = keystring
        self.flowbox.invalidate_filter()
        self.last_selected_channel = string

    def select_next(self) -> None:
        """Select next channel"""
        self.flowbox.unselect_all()
        if self.last_selected_channel and not is_non_nul_int(
            self.last_selected_channel
        ):
            return
        if self.view_mode == VIEW_MODES["Patched"]:
            self._next_patched()
        if self.view_mode == VIEW_MODES["Active"]:
            self._next_active()
        # Default mode: All channels
        selected_channel = ""
        channel_index = (
            int(self.last_selected_channel) if self.last_selected_channel else 0
        )

        if channel_index > MAX_CHANNELS - 1:
            channel_index = 0
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel

    def _next_active(self) -> None:
        """Select next channel in Active mode view"""
        selected_channel = ""
        children = self.flowbox.get_children()
        start = (
            int(self.last_selected_channel)
            if self.last_selected_channel
            else self.__get_first_active_channel()
        )

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

    def _next_patched(self) -> None:
        """Select next channel in Patched mode view"""
        start = (
            int(self.last_selected_channel)
            if self.last_selected_channel
            else App().patch.get_first_patched_channel() - 1
        )

        for channel_index in range(start, MAX_CHANNELS):
            if channel_index + 1 in App().patch.channels:
                break
        if channel_index + 1 >= MAX_CHANNELS:
            channel_index = App().patch.get_first_patched_channel() - 1
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel

    def select_previous(self) -> None:
        """Select previous channel"""
        self.flowbox.unselect_all()
        if self.last_selected_channel and not is_non_nul_int(
            self.last_selected_channel
        ):
            return
        if self.view_mode == VIEW_MODES["Patched"]:
            self._previous_patched()
        if self.view_mode == VIEW_MODES["Active"]:
            self._previous_active()
        # Default mode: All channels
        selected_channel = ""
        channel_index = (
            int(self.last_selected_channel) - 2 if self.last_selected_channel else 0
        )

        if channel_index < 0:
            channel_index = MAX_CHANNELS - 1
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel

    def _previous_active(self) -> None:
        """Select previous channel in Active mode view"""
        selected_channel = ""
        start = (
            int(self.last_selected_channel) - 2
            if self.last_selected_channel
            else self.__get_last_active_channel() + 1
        )

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

    def _previous_patched(self) -> None:
        """Select previous channel in Patched mode view"""
        start = (
            int(self.last_selected_channel) - 2
            if self.last_selected_channel
            else App().patch.get_last_patched_channel()
        )

        for channel_index in range(start, 0, -1):
            if channel_index + 1 in App().patch.channels:
                break
        if channel_index < App().patch.get_first_patched_channel() - 1:
            channel_index = App().patch.get_last_patched_channel() - 1
        flowboxchild = self.flowbox.get_child_at_index(channel_index)
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        selected_channel = str(channel_index + 1)
        self.flowbox.invalidate_filter()
        self.last_selected_channel = selected_channel

    def select_all(self) -> None:
        """Select all channel with a level > 0"""
        self.flowbox.unselect_all()
        for channel_index in range(MAX_CHANNELS):
            flowboxchild = self.flowbox.get_child_at_index(channel_index)
            channel_widget = flowboxchild.get_child()
            level = channel_widget.level
            if level:
                self.flowbox.select_child(flowboxchild)

    def select_thru(self, keystring: str) -> None:
        """Select Channel Thru

        Args:
            keystring: Channel number
        """
        last_chan = self.last_selected_channel
        string = last_chan
        if is_non_nul_int(keystring) and last_chan:
            from_chan = int(last_chan)
            to_chan = int(keystring)
            if to_chan > from_chan:
                for channel in range(from_chan - 1, to_chan):
                    if 0 <= channel < MAX_CHANNELS:
                        flowboxchild = self.flowbox.get_child_at_index(channel)
                        self.flowbox.select_child(flowboxchild)
            else:
                for channel in range(to_chan - 1, from_chan):
                    if 0 <= channel < MAX_CHANNELS:
                        flowboxchild = self.flowbox.get_child_at_index(channel)
                        self.flowbox.select_child(flowboxchild)
            if flowboxchild:
                App().window.set_focus(flowboxchild)
            self.flowbox.invalidate_filter()
            string = keystring
        self.last_selected_channel = string

    def at_level(self, keystring: str) -> None:
        """Channels at level

        Args:
            keystring: Level (positive integer)
        """
        if not is_int(keystring):
            return
        level = int(keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        for channel in channels:
            self.set_channel_level(channel, level)

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

    def on_key_press(self, keyname: str, keystring: str) -> Any:
        """Processes common keyboard methods of Channels View

        Args:
            keyname: Gdk Name of the pressed key
            keystring: Keys buffer

        Returns:
            method or Keys buffer
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
                return func(keystring)
        return keystring

    def _keypress_f(self, keystring: str) -> str:
        """Toggle display mode

        Args:
            keystring: Keys buffer

        Returns:
            Keys buffer
        """
        self.toggle_view_mode()
        return keystring

    def _keypress_a(self, keystring: str) -> str:
        """All Channels

        Args:
            keystring: Keys buffer

        Returns:
            Keys buffer
        """
        self.select_all()
        return keystring

    def _keypress_page_up(self, keystring: str) -> str:
        """Next Channel

        Args:
            keystring: Keys buffer

        Returns:
            Empty string
        """
        self.select_next()
        keystring = ""
        App().window.statusbar.push(App().window.context_id, keystring)
        return keystring

    def _keypress_page_down(self, keystring: str) -> str:
        """Previous Channel

        Args:
            keystring: Keys buffer

        Returns:
            Empty string
        """
        self.select_previous()
        keystring = ""
        App().window.statusbar.push(App().window.context_id, keystring)
        return keystring

    def _keypress_c(self, keystring: str) -> str:
        """Channel

        Args:
            keystring: Keys buffer

        Returns:
            Empty string
        """
        self.select_channel(keystring)
        keystring = ""
        App().window.statusbar.push(App().window.context_id, keystring)
        return keystring

    def _keypress_kp_divide(self, keystring):
        self._keypress_greater(keystring)

    def _keypress_greater(self, keystring: str) -> str:
        """Channel Thru

        Args:
            keystring: Keys buffer

        Returns:
            Empty string
        """
        self.select_thru(keystring)
        keystring = ""
        App().window.statusbar.push(App().window.context_id, keystring)
        return keystring

    def _keypress_kp_add(self, keystring):
        self._keypress_plus(keystring)

    def _keypress_plus(self, keystring: str) -> str:
        """Channel +

        Args:
            keystring: Keys buffer

        Returns:
            Empty string
        """
        self.select_plus(keystring)
        keystring = ""
        App().window.statusbar.push(App().window.context_id, keystring)
        return keystring

    def _keypress_kp_subtract(self, keystring):
        self._keypress_minus(keystring)

    def _keypress_minus(self, keystring: str) -> str:
        """Channel -

        Args:
            keystring: Keys buffer

        Returns:
            Empty string
        """
        self.select_minus(keystring)
        keystring = ""
        App().window.statusbar.push(App().window.context_id, keystring)
        return keystring
