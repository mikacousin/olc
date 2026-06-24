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

from gi.repository import Gdk, GLib, Gtk
from olc.define import MAX_CHANNELS, is_int, is_non_nul_float
from olc.group import Group
from olc.gtk3.widgets.channel import ChannelWidget
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView
from olc.gtk3.widgets.group import GroupWidget

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window


class GroupChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self, app: Application) -> None:
        super().__init__(app=app)

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level via temporary action.

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        if not self.tabs or not self.lightshow or not self.window:
            return
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        group = self.lightshow.groups[index]
        self.window.app.core.action_registry.execute(
            "group.set_temp_channels", group.index, {channel: level}
        )

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel using a temporary action.

        Args:
            step: Step level
            direction: Up or Down
        """
        if not self.tabs or not self.lightshow or not self.window:
            return
        channels = self.get_selected_channels()
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        group = self.lightshow.groups[index]
        channels_dict = {}
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if direction == Gdk.ScrollDirection.UP:
                    level = min(level + step, 255)
                elif direction == Gdk.ScrollDirection.DOWN:
                    level = max(level - step, 0)
                channels_dict[channel] = level
        if channels_dict:
            self.window.app.core.action_registry.execute(
                "group.set_temp_channels", group.index, channels_dict
            )

    def at_level(self) -> None:
        """Channels at level using a temporary action."""
        if not self.window or not self.settings or not self.tabs or not self.lightshow:
            return
        keystring = self.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if self.settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        group = self.lightshow.groups[index]
        channels_dict = {channel: level for channel in channels}
        if channels_dict:
            self.window.app.core.action_registry.execute(
                "group.set_temp_channels", group.index, channels_dict
            )

    def level_plus(self) -> None:
        """Channels +% using a temporary action."""
        if not self.settings or not self.tabs or not self.lightshow or not self.window:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        group = self.lightshow.groups[index]
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
                "group.set_temp_channels", group.index, channels_dict
            )

    def level_minus(self) -> None:
        """Channels -% using a temporary action."""
        if not self.settings or not self.tabs or not self.lightshow or not self.window:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        group = self.lightshow.groups[index]
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
                "group.set_temp_channels", group.index, channels_dict
            )

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Select channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        # Find selected group
        selected_group = None
        if self.tabs and self.tabs.tabs["groups"]:
            selected_group = typing.cast(
                GroupTab, self.tabs.tabs["groups"]
            ).flowbox.get_selected_children()
        if selected_group and self.lightshow:
            group_widget = typing.cast(GroupWidget, selected_group[0].get_child())
            group_number = group_widget.number
            group = None
            for g in self.lightshow.groups:
                if g.index == group_number:
                    group = g
                    break
            if not group:
                child.set_visible(False)
                return False
            # Display active channels
            if self.view_mode == VIEW_MODES["Active"]:
                return self.__filter_active(group, child)
            # Display patched channels
            if self.view_mode == VIEW_MODES["Patched"]:
                return self.__filter_patched(group, child)
            # Display all channels by default
            return self.__filter_all(group, child)
        child.set_visible(False)
        return False

    def __filter_all(self, group: Group, child: Gtk.FlowBoxChild) -> bool:
        """Display all channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        if self.lightshow is None:
            return False
        channel = child.get_index() + 1  # Channel number
        channel_widget = typing.cast(ChannelWidget, child.get_child())
        group_editor = self.lightshow.groups.group_editor
        temp_levels = group_editor.get_levels(group.index)
        temp_level = temp_levels[channel - 1]

        level = temp_level if temp_level != -1 else group.get_channel_level(channel, 0)

        if level or child.is_selected() or temp_level != -1:
            channel_widget.level = level
            channel_widget.next_level = level
        else:
            channel_widget.level = 0
            channel_widget.next_level = 0
        child.set_visible(True)
        return True

    def __filter_patched(self, group: Group, child: Gtk.FlowBoxChild) -> bool:
        """Display only patched channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        channel = child.get_index() + 1
        if self.lightshow and not self.lightshow.patch.is_patched(channel):
            child.set_visible(False)
            return False
        return self.__filter_all(group, child)

    def __filter_active(self, group: Group, child: Gtk.FlowBoxChild) -> bool:
        """Display only active channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        if self.lightshow is None:
            return False
        channel = child.get_index() + 1
        channel_widget = typing.cast(ChannelWidget, child.get_child())
        group_editor = self.lightshow.groups.group_editor
        temp_levels = group_editor.get_levels(group.index)
        temp_level = temp_levels[channel - 1]

        level = temp_level if temp_level != -1 else group.get_channel_level(channel, 0)

        if level or child.is_selected() or temp_level != -1:
            channel_widget.level = level
            channel_widget.next_level = level
            child.set_visible(True)
            return True
        child.set_visible(False)
        return False


# pylint: disable=too-many-instance-attributes
class GroupTab(Gtk.Paned):
    """Groups edition"""

    app: Application
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    commandline: CoreCommandLine
    last_group_selected: str
    selected_group_number: float | None
    channels_view: GroupChannelsView
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox
    _updating_selection: bool

    def __init__(self, app: Application) -> None:
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.commandline = app.core.commandline
        self.last_group_selected = ""
        self.selected_group_number = None
        self._updating_selection = False
        self._selection_idle_id: int | None = None

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.channels_view = GroupChannelsView(app=self.app)
        self.add1(self.channels_view)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flowbox = Gtk.FlowBox()
        self.populate_tab()
        self.add2(self.scrolled)

    def populate_tab(self) -> None:
        """Add groups to tab"""
        # New FlowBox
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_activate_on_single_click(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.connect("selected-children-changed", self.on_selection_changed)
        # Add groups to FlowBox
        for i, _ in enumerate(self.lightshow.groups):
            self.flowbox.add(
                GroupWidget(  # pylint: disable=unexpected-keyword-arg
                    self.lightshow.groups[i].index,
                    self.lightshow.groups[i].text,
                    lightshow=self.lightshow,
                    tabs=self.tabs,
                    window=self.window,
                )
            )
        self.scrolled.add(self.flowbox)

    def on_selection_changed(self, flowbox: Gtk.FlowBox) -> None:
        """Called when user selection changes on flowbox"""
        if self._updating_selection:
            return

        if self._selection_idle_id is not None:
            GLib.source_remove(self._selection_idle_id)
            self._selection_idle_id = None

        self._selection_idle_id = GLib.idle_add(self._apply_selection_changed, flowbox)

    def _apply_selection_changed(self, flowbox: Gtk.FlowBox) -> bool:
        self._selection_idle_id = None
        selected = flowbox.get_selected_children()
        if selected:
            child = selected[0]
            group_widget = typing.cast(GroupWidget, child.get_child())
            group_nb = group_widget.number
        else:
            group_nb = None
        self.app.core.action_registry.execute("group.select", group_nb)
        return False

    def select_group_graphically(self, group_nb: float | None) -> None:
        """Update the graphical group selection from the logical state."""
        self._updating_selection = True
        try:
            self.flowbox.unselect_all()
            if group_nb is not None:
                for child in self.flowbox.get_children():
                    fb_child = typing.cast(Gtk.FlowBoxChild, child)
                    group_widget = typing.cast(GroupWidget, fb_child.get_child())
                    if group_widget and group_widget.number == group_nb:
                        self.flowbox.select_child(fb_child)
                        self.selected_group_number = group_nb
                        self.last_group_selected = str(fb_child.get_index())
                        break
            else:
                self.selected_group_number = None
                self.last_group_selected = ""
            self.channels_view.update()
        finally:
            self._updating_selection = False

    def refresh(self) -> None:
        """Refresh display"""
        # Remove Old Groups
        self.scrolled.remove(self.flowbox)
        self.flowbox.destroy()
        # Update Group tab
        self.populate_tab()
        self.flowbox.invalidate_filter()
        self.window.show_all()

        # Restore selection
        restored = False
        self._updating_selection = True
        try:
            if getattr(self, "selected_group_number", None) is not None:
                for child in self.flowbox.get_children():
                    fb_child = typing.cast(Gtk.FlowBoxChild, child)
                    group_widget = typing.cast(GroupWidget, fb_child.get_child())
                    if (
                        group_widget
                        and group_widget.number == self.selected_group_number
                    ):
                        self.flowbox.select_child(fb_child)
                        fb_child.grab_focus()
                        restored = True
                        break
            if not restored:
                self.selected_group_number = None
                self.last_group_selected = ""
                self.channels_view.update()
        finally:
            self._updating_selection = False

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab with the icon clicked"""
        self.tabs.close("groups")

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

    def _keypress_backspace(self) -> None:
        self.commandline.set_string("")

    def _keypress_escape(self) -> None:
        """Close Tab"""
        self.tabs.close("groups")

    def _keypress_l(self) -> None:
        """Open Popover to change label group"""
        if selected := self.flowbox.get_selected_children():
            flowboxchild = selected[0]
            group_widget = typing.cast(GroupWidget, flowboxchild.get_child())
            group_widget.popover.popup()
        self.commandline.set_string("")

    def _keypress_u(self) -> None:
        """Update Group"""
        self.channels_view.flowbox.unselect_all()

        # Find selected group
        if selected := self.flowbox.get_selected_children():
            flowboxchild = selected[0]
            group_widget = typing.cast(GroupWidget, flowboxchild.get_child())
            group_nb = group_widget.number
            group = self.lightshow.groups.get(group_nb)
            if group:
                group_editor = self.lightshow.groups.group_editor
                temp_levels = group_editor.get_levels(group_nb)
                channels_dict = {}
                for chan in range(MAX_CHANNELS):
                    channel_widget = self.channels_view.get_channel_widget(chan + 1)
                    if channel_widget is not None:
                        if (chan + 1 in group.channels) or (temp_levels[chan] != -1):
                            channels_dict[chan + 1] = channel_widget.level
                self.window.app.core.action_registry.execute(
                    "group.update_channels", group_nb, channels_dict
                )

    def _keypress_right(self) -> None:
        """Next Group"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                self.flowbox.select_child(fb_child)
                self.window.set_focus(fb_child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        elif child := self.flowbox.get_child_at_index(
            int(self.last_group_selected) + 1
        ):
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            self.flowbox.select_child(fb_child)
            self.window.set_focus(fb_child)
            self.channels_view.flowbox.unselect_all()
            self.channels_view.update()
            self.last_group_selected = str(int(self.last_group_selected) + 1)
        self.channels_view.last_selected_channel = ""

    def _keypress_left(self) -> None:
        """Previous Group"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                self.flowbox.select_child(fb_child)
                self.window.set_focus(fb_child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        elif int(self.last_group_selected) > 0:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected) - 1)
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            self.flowbox.select_child(fb_child)
            self.window.set_focus(fb_child)
            self.channels_view.flowbox.unselect_all()
            self.channels_view.update()
            self.last_group_selected = str(int(self.last_group_selected) - 1)
        self.channels_view.last_selected_channel = ""

    def _keypress_down(self) -> None:
        """Group on Next Line"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                self.flowbox.select_child(fb_child)
                self.window.set_focus(fb_child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected))
            if child is not None:
                allocation = child.get_allocation()
                if next_child := self.flowbox.get_child_at_pos(
                    allocation.x, allocation.y + allocation.height
                ):
                    self.flowbox.unselect_all()
                    fb_child = typing.cast(Gtk.FlowBoxChild, next_child)
                    index = fb_child.get_index()
                    self.flowbox.select_child(fb_child)
                    self.window.set_focus(fb_child)
                    self.channels_view.flowbox.unselect_all()
                    self.channels_view.update()
                    self.last_group_selected = str(index)
        self.channels_view.last_selected_channel = ""

    def _keypress_up(self) -> None:
        """Group on Previous Line"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                self.flowbox.select_child(fb_child)
                self.window.set_focus(fb_child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected))
            if child is not None:
                allocation = child.get_allocation()
                y_pos = int(allocation.y - allocation.height / 2)
                if prev_child := self.flowbox.get_child_at_pos(allocation.x, y_pos):
                    self.flowbox.unselect_all()
                    fb_child = typing.cast(Gtk.FlowBoxChild, prev_child)
                    index = fb_child.get_index()
                    self.flowbox.select_child(fb_child)
                    self.window.set_focus(fb_child)
                    self.channels_view.flowbox.unselect_all()
                    self.channels_view.update()
                    self.last_group_selected = str(index)
        self.channels_view.last_selected_channel = ""

    def _keypress_g(self) -> None:
        """Select Group"""
        self.flowbox.unselect_all()

        keystring = self.commandline.get_string()
        if keystring != "":
            group = float(keystring)
            flowbox_children = self.flowbox.get_children()
            for flowbox_child in flowbox_children:
                fb_child = typing.cast(Gtk.FlowBoxChild, flowbox_child)
                group_widget = typing.cast(GroupWidget, fb_child.get_child())
                if group_widget.number == group:
                    index = fb_child.get_index()
                    self.flowbox.select_child(fb_child)
                    self.window.set_focus(fb_child)
                    self.last_group_selected = str(index)
                    break
        # Deselect all channels
        self.channels_view.flowbox.unselect_all()
        # Update display
        self.channels_view.update()
        self.flowbox.invalidate_filter()
        self.channels_view.last_selected_channel = ""

        self.commandline.set_string("")

    def _update_fader_level(self) -> None:
        """Update selected fader channels levels"""
        if selected := self.flowbox.get_selected_children():
            flowboxchild = selected[0]
            index = flowboxchild.get_index()
            group = self.lightshow.groups[index]
            for page in self.lightshow.fader_bank.faders.values():
                for fader in page.values():
                    if fader.contents is group:
                        fader.set_level(fader.level)
                        break

    def _keypress_equal(self) -> None:
        """@ Level"""
        self.channels_view.at_level()
        self.channels_view.update()
        self._update_fader_level()
        self.commandline.set_string("")

    def _keypress_colon(self) -> None:
        """Level - %"""
        self.channels_view.level_minus()
        self.channels_view.update()
        self._update_fader_level()
        self.commandline.set_string("")

    def _keypress_exclam(self) -> None:
        """Level + %"""
        self.channels_view.level_plus()
        self.channels_view.update()
        self._update_fader_level()
        self.commandline.set_string("")

    def _keypress_n(self) -> None:
        """New Group"""
        keystring = self.commandline.get_string()
        # If no group number, use the next one
        if keystring == "":
            group_nb = self.lightshow.groups.get_next_index()
        elif is_non_nul_float(keystring):
            group_nb = float(keystring)
        else:
            self.commandline.set_string("")
            return

        # Execute new group action
        app = self.window.app
        try:
            self.selected_group_number = group_nb
            app.core.action_registry.execute("group.new", group_nb)
            self.channels_view.flowbox.unselect_all()
        except ValueError:
            self.selected_group_number = None

        self.commandline.set_string("")

    def _keypress_delete(self) -> None:
        """Delete selected group"""
        if not (selected := self.flowbox.get_selected_children()):
            return

        # Find selected group index and group object
        flowboxchild = selected[0]
        index = flowboxchild.get_index()
        group = self.lightshow.groups[index]

        # Determine next group number to select
        if len(self.lightshow.groups) <= 1:
            next_group_number = None
        elif index + 1 == len(self.lightshow.groups):
            next_group_number = self.lightshow.groups[index - 1].index
        else:
            next_group_number = self.lightshow.groups[index + 1].index

        # Execute delete group action
        self.selected_group_number = next_group_number
        app = self.window.app
        app.core.action_registry.execute("group.delete", group.index)
