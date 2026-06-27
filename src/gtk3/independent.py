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
from olc.define import MAX_CHANNELS
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    import olc.gtk3.independent
    from gi.repository import Gio
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.widgets.channel import ChannelWidget
    from olc.gtk3.window import Window


# pylint: disable=too-many-instance-attributes
class IndependentsTab(Gtk.Paned):
    """Tab to edit independents"""

    app: Application
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    commandline: CoreCommandLine
    user_channels: np.ndarray
    liststore: Gtk.ListStore
    treeview: Gtk.TreeView
    channels_view: IndeChannelsView

    def __init__(self, app: Application) -> None:
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.commandline = app.core.commandline

        # Channels modified by user
        self.user_channels = np.full(MAX_CHANNELS, -1, dtype=np.int16)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.channels_view = IndeChannelsView(app=self.app)
        self.add(self.channels_view)

        # List of independents
        self.liststore = Gtk.ListStore(int, str, str)
        for inde in self.lightshow.independents.independents:
            self.liststore.append([inde.number, inde.inde_type, inde.text])
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_changed)
        # Model for independent type combo box
        liststore_types = Gtk.ListStore(str)
        liststore_types.append(["knob"])
        liststore_types.append(["button"])

        for i, column_title in enumerate(["Number", "Type", "Text"]):
            if i == 1:
                renderer = Gtk.CellRendererCombo()
                renderer.set_property("editable", True)
                renderer.set_property("model", liststore_types)
                renderer.set_property("text-column", 0)
                renderer.set_property("has-entry", False)
                renderer.connect("edited", self.type_edited)
            else:
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
        self.user_channels = np.full(MAX_CHANNELS, -1, dtype=np.int16)
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
        if self.app is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("independent.rename", number, text)
        else:
            self.lightshow.independents.independents[number - 1].text = text

    def type_edited(self, _widget: Gtk.Widget, path: str, text: str) -> None:
        """Independent type edited

        Args:
            _widget: Widget clicked
            path: Path to object
            text: New type (knob or button)
        """
        self.liststore[path][1] = text
        number = self.liststore[path][0]
        if self.app is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute(
                "independent.change_type", number, text
            )
        else:
            self.lightshow.independents.independents[number - 1].inde_type = text

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
        self.tabs.close("indes")

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
                if channel_widget is not None:
                    widget = channel_widget
                    channels[channel + 1] = widget.level
            if self.app is not None and hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute(
                    "independent.update_channels", number, channels
                )
            else:
                self.lightshow.independents.independents[number - 1].set_levels(
                    channels
                )
                self.lightshow.independents.update_channels()
                self.lightshow.independents.independents[number - 1].update_dmx()
            self.window.live_view.channels_view.flowbox.queue_draw()
            self.channels_view.update()

            # Reset user modifications
            self.user_channels = np.full(MAX_CHANNELS, -1, dtype=np.int16)


class IndeChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self, app: Application) -> None:
        super().__init__(app=app)

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        if self.tabs is not None:
            tab = typing.cast(
                "olc.gtk3.independent.IndependentsTab", self.tabs.tabs["indes"]
            )
            tab.user_channels[channel - 1] = level

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget is not None:
                widget = channel_widget
                level = widget.level
                if direction == Gdk.ScrollDirection.UP:
                    level = min(level + step, 255)
                elif direction == Gdk.ScrollDirection.DOWN:
                    level = max(level - step, 0)
                widget.level = level
                widget.next_level = level
                widget.queue_draw()
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
            or not self.lightshow.independents.independents
            or self.tabs is None
            or not self.tabs.tabs["indes"]
        ):
            child.set_visible(False)
            return False
        # Find selected independent
        tab = typing.cast(
            "olc.gtk3.independent.IndependentsTab", self.tabs.tabs["indes"]
        )
        path, _focus_column = tab.treeview.get_cursor()
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
        if self.tabs is None or self.lightshow is None:
            return False
        channel_index = child.get_index()
        channel_widget = child.get_child()
        if channel_widget is None:
            return False
        widget = typing.cast("ChannelWidget", channel_widget)

        tab = typing.cast(
            "olc.gtk3.independent.IndependentsTab", self.tabs.tabs["indes"]
        )
        user_channels = tab.user_channels
        channels = self.lightshow.independents.independents[row].levels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                widget.level = channels.get(channel_index + 1, 0)
                widget.next_level = channels.get(channel_index + 1, 0)
            else:
                widget.level = user_channels[channel_index]
                widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        if user_channels[channel_index] != -1:
            widget.level = user_channels[channel_index]
            widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        widget.level = 0
        widget.next_level = 0
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
        if self.lightshow is None:
            return False
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
        if self.tabs is None or self.lightshow is None:
            return False
        channel_index = child.get_index()
        channel_widget = child.get_child()
        if channel_widget is None:
            return False
        widget = typing.cast("ChannelWidget", channel_widget)

        tab = typing.cast(
            "olc.gtk3.independent.IndependentsTab", self.tabs.tabs["indes"]
        )
        user_channels = tab.user_channels
        channels = self.lightshow.independents.independents[row].levels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                widget.level = channels.get(channel_index + 1, 0)
                widget.next_level = channels.get(channel_index + 1, 0)
            else:
                widget.level = user_channels[channel_index]
                widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        if user_channels[channel_index] != -1:
            widget.level = user_channels[channel_index]
            widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        widget.level = 0
        widget.next_level = 0
        child.set_visible(True)
        return True
