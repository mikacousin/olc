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
from typing import Any, Callable, Optional

from gi.repository import Gdk, Gtk
from olc.core.selection import (
    SelectActiveAction,
    SelectAddAction,
    SelectAllAction,
    SelectionManager,
    SelectNoneAction,
    SelectRemoveAction,
    SelectThruAction,
)
from olc.define import MAX_CHANNELS, is_int, is_non_nul_int
from olc.gtk3.widgets.channel import ChannelWidget

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window

VIEW_MODES: dict[str, int] = {"All": 0, "Patched": 1, "Active": 2}


# pylint: disable=too-many-instance-attributes
class ChannelsView(Gtk.Box):
    """Channels view

    This class must be subclassed and filter_channels, wheel_level, set_channel_level
    implemented
    """

    view_mode: int
    last_selected_channel: str
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox
    app: Application
    window: Window | None
    commandline: CoreCommandLine
    lightshow: LightShow | None
    settings: Gio.Settings | None
    tabs: Tabs | None
    updating_selection: bool
    selection_manager: SelectionManager

    def __init__(
        self,
        app: Application,
        *args: Any,  # noqa: ANN401
        window: Window | None = None,
        tabs: Tabs | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        kwargs.setdefault("orientation", Gtk.Orientation.VERTICAL)
        super().__init__(*args, **kwargs)
        self.app = app
        self.window = window if window is not None else app.window
        self.commandline = app.core.commandline
        self.lightshow = app.core.lightshow
        self.settings = app.settings
        self.tabs = tabs if tabs is not None else app.tabs

        self.view_mode = VIEW_MODES.get("All", 0)
        self.last_selected_channel = ""
        self.updating_selection = False

        if self.__class__.__name__ == "LiveChannelsView":
            self.selection_manager = app.core.live_selection
        else:
            self.selection_manager = SelectionManager(
                commandline=app.core.commandline,
                on_changed_callback=self.sync_selection_to_gui,
                history_manager=app.core.history,
                get_level_callback=self._get_channel_level_for_select,
            )

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
        if self.lightshow and self.settings and self.window and self.tabs:
            for i in range(MAX_CHANNELS):
                self.flowbox.add(
                    ChannelWidget(
                        i + 1,
                        0,
                        0,
                        self.app,
                        window=self.window,
                        tabs=self.tabs,
                    )
                )
        self.scrolled.add(self.flowbox)

        self.pack_start(self.scrolled, True, True, 0)
        self.combo.set_active(0)

    def _get_channel_level_for_select(self, channel: int) -> int:
        """Helper callback to read the level from a ChannelWidget."""
        widget = self.get_channel_widget(channel)
        return widget.level if widget else 0

    def sync_selection_to_gui(self, selected_channels: list[int]) -> None:
        """Synchronize the logical selection state from selection_manager to FlowBox."""
        self.updating_selection = True
        try:
            self.flowbox.unselect_all()
            for ch in selected_channels:
                if 1 <= ch <= MAX_CHANNELS:
                    flowboxchild = self.flowbox.get_child_at_index(ch - 1)
                    if flowboxchild:
                        self.flowbox.select_child(flowboxchild)
            if self.selection_manager.last_selected_channel is not None:
                self.last_selected_channel = str(
                    self.selection_manager.last_selected_channel
                )
            else:
                self.last_selected_channel = ""
            self.flowbox.invalidate_filter()
        finally:
            self.updating_selection = False

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
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
            if flowboxchild:
                channelwidget = typing.cast("ChannelWidget", flowboxchild.get_child())
                return channelwidget
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

    def toggle_view_mode(self) -> None:
        """Select next View Mode"""
        index = self.view_mode + 1
        if index not in VIEW_MODES.values():
            index = 0
        self.combo.set_active(index)

    def select_channel(self) -> None:
        """Select one channel, or clear selection if commandline is empty or zero."""
        if not self.window or not self.commandline:
            return
        cmd = self.commandline.get_string()
        if not cmd or cmd == "0":
            self.selection_manager.execute_action(SelectNoneAction)
            return
        self.selection_manager.execute_action(SelectActiveAction)
        if self.selection_manager.last_selected_channel:
            ch = self.selection_manager.last_selected_channel
            if flowboxchild := self.flowbox.get_child_at_index(ch - 1):
                self.window.set_focus(flowboxchild)

    def select_plus(self) -> None:
        """Add channel to selection"""
        if not self.window or not self.commandline:
            return

        self.selection_manager.execute_action(SelectAddAction)
        if self.selection_manager.last_selected_channel:
            ch = self.selection_manager.last_selected_channel
            if flowboxchild := self.flowbox.get_child_at_index(ch - 1):
                self.window.set_focus(flowboxchild)

    def select_minus(self) -> None:
        """Remove channel from selection"""
        if not self.window or not self.commandline:
            return

        self.selection_manager.execute_action(SelectRemoveAction)
        if self.selection_manager.last_selected_channel:
            ch = self.selection_manager.last_selected_channel
            if flowboxchild := self.flowbox.get_child_at_index(ch - 1):
                self.window.set_focus(flowboxchild)

    def select_next(self) -> None:
        """Select next channel"""
        if not self.window:
            return
        if self.last_selected_channel and not is_non_nul_int(
            self.last_selected_channel
        ):
            return
        if self.view_mode == VIEW_MODES["Patched"]:
            channel_index = self._get_next_patched_index()
        elif self.view_mode == VIEW_MODES["Active"]:
            channel_index = self._get_next_active_index()
        else:
            channel_index = (
                int(self.last_selected_channel) if self.last_selected_channel else 0
            )
            if channel_index > MAX_CHANNELS - 1:
                channel_index = 0

        target_channel = channel_index + 1

        self.selection_manager.execute_action(SelectActiveAction, target_channel)
        if flowboxchild := self.flowbox.get_child_at_index(channel_index):
            self.window.set_focus(flowboxchild)

    def _get_next_active_index(self) -> int:
        """Get next active channel index"""
        children = self.flowbox.get_children()
        start = (
            int(self.last_selected_channel)
            if self.last_selected_channel
            else self.__get_first_active_channel()
        )

        channel_index = start
        for child in children:
            flowboxchild = typing.cast(Gtk.FlowBoxChild, child)
            idx = flowboxchild.get_index()
            if flowboxchild.get_visible() and idx >= start:
                channel_index = idx
                break
        if channel_index + 1 >= MAX_CHANNELS:
            channel_index = self.__get_first_active_channel()
        return channel_index

    def _get_next_patched_index(self) -> int:
        """Get next patched channel index"""
        if not self.lightshow:
            return 0
        start = (
            int(self.last_selected_channel)
            if self.last_selected_channel
            else self.lightshow.patch.get_first_patched_channel() - 1
        )

        channel_index = start
        for idx in range(start, MAX_CHANNELS):
            if self.lightshow.patch.is_patched(idx + 1):
                channel_index = idx
                break
        if channel_index + 1 >= MAX_CHANNELS:
            channel_index = self.lightshow.patch.get_first_patched_channel() - 1
        return channel_index

    def select_previous(self) -> None:
        """Select previous channel"""
        if not self.window:
            return
        if self.last_selected_channel and not is_non_nul_int(
            self.last_selected_channel
        ):
            return
        if self.view_mode == VIEW_MODES["Patched"]:
            channel_index = self._get_previous_patched_index()
        elif self.view_mode == VIEW_MODES["Active"]:
            channel_index = self._get_previous_active_index()
        else:
            channel_index = (
                int(self.last_selected_channel) - 2 if self.last_selected_channel else 0
            )
            if channel_index < 0:
                channel_index = MAX_CHANNELS - 1

        target_channel = channel_index + 1

        self.selection_manager.execute_action(SelectActiveAction, target_channel)
        if flowboxchild := self.flowbox.get_child_at_index(channel_index):
            self.window.set_focus(flowboxchild)

    def _get_previous_active_index(self) -> int:
        """Get previous active channel index"""
        start = (
            int(self.last_selected_channel) - 2
            if self.last_selected_channel
            else self.__get_last_active_channel() + 1
        )

        children = self.flowbox.get_children()
        children.reverse()
        channel_index = start
        for child in children:
            flowboxchild = typing.cast(Gtk.FlowBoxChild, child)
            idx = flowboxchild.get_index()
            if flowboxchild.get_visible() and idx <= start:
                channel_index = idx
                break
        if channel_index < self.__get_first_active_channel() or start < 0:
            channel_index = self.__get_last_active_channel()
        return channel_index

    def _get_previous_patched_index(self) -> int:
        """Get previous patched channel index"""
        if not self.lightshow:
            return 0
        start = (
            int(self.last_selected_channel) - 2
            if self.last_selected_channel
            else self.lightshow.patch.get_last_patched_channel()
        )

        channel_index = start
        for idx in range(start, 0, -1):
            if self.lightshow.patch.is_patched(idx + 1):
                channel_index = idx
                break
        if channel_index < self.lightshow.patch.get_first_patched_channel() - 1:
            channel_index = self.lightshow.patch.get_last_patched_channel() - 1
        return channel_index

    def select_all(self) -> None:
        """Select all channel with a level > 0"""

        self.selection_manager.execute_action(SelectAllAction)

    def select_thru(self) -> None:
        """Select Channel Thru"""
        if not self.window or not self.commandline:
            return

        self.selection_manager.execute_action(SelectThruAction)
        if self.selection_manager.last_selected_channel:
            ch = self.selection_manager.last_selected_channel
            if flowboxchild := self.flowbox.get_child_at_index(ch - 1):
                self.window.set_focus(flowboxchild)

    def at_level(self) -> None:
        """Channels at level"""
        if not self.window or not self.settings or not self.commandline:
            return
        keystring = self.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if self.settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        for channel in channels:
            self.set_channel_level(channel, level)

    def level_plus(self) -> None:
        """Channels +%"""
        if not self.settings:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                self.set_channel_level(channel, new_level)

    def level_minus(self) -> None:
        """Channels -%"""
        if not self.settings:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                self.set_channel_level(channel, new_level)

    def get_selected_channels(self) -> list[int]:
        """Return selected channels

        Returns:
            Selected channels
        """
        return list(self.selection_manager.selected_channels)

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
        if child is not None:
            return typing.cast(Gtk.FlowBoxChild, child).get_index()
        return 0

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
        if child is not None:
            return typing.cast(Gtk.FlowBoxChild, child).get_index()
        return 0

    def grab_focus(self) -> None:
        """Grab focus to active Tab"""
        parent = self.get_parent()
        if not self.window or not parent:
            return
        if self.window and parent in (self.window.live_view, self.window.playback):
            parent.grab_focus()
        elif parent:
            if grandparent := parent.get_parent():
                grandparent.grab_focus()

    def on_key_press(self, keyname: str | None) -> Callable | None:
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
        self.toggle_view_mode()
        self.grab_focus()

    def _keypress_a(self) -> None:
        """All Channels"""
        self.select_all()
        self.grab_focus()

    def _keypress_page_up(self) -> None:
        """Next Channel"""
        self.select_next()
        self.grab_focus()
        if self.commandline:
            self.commandline.set_string("")

    def _keypress_page_down(self) -> None:
        """Previous Channel"""
        self.select_previous()
        self.grab_focus()
        if self.commandline:
            self.commandline.set_string("")

    def _keypress_c(self) -> None:
        """Channel"""
        self.select_channel()
        self.grab_focus()
        if self.commandline:
            self.commandline.set_string("")

    def _keypress_kp_divide(self) -> None:
        self._keypress_greater()

    def _keypress_greater(self) -> None:
        """Channel Thru"""
        self.select_thru()
        self.grab_focus()
        if self.commandline:
            self.commandline.set_string("")

    def _keypress_kp_add(self) -> None:
        self._keypress_plus()

    def _keypress_plus(self) -> None:
        """Channel +"""
        self.select_plus()
        self.grab_focus()
        if self.commandline:
            self.commandline.set_string("")

    def _keypress_kp_subtract(self) -> None:
        self._keypress_minus()

    def _keypress_minus(self) -> None:
        """Channel -"""
        self.select_minus()
        self.grab_focus()
        if self.commandline:
            self.commandline.set_string("")
