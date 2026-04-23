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
import typing
from dataclasses import dataclass
from typing import Callable

from gi.repository import Gdk, Gtk
from olc.define import is_non_nul_float
from olc.fader import FaderType
from olc.fader_edition import FaderTab
from olc.widgets.channels_view import VIEW_MODES, ChannelsView
from olc.widgets.group import GroupWidget

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.lightshow import LightShow
    from olc.tabs_manager import Tabs
    from olc.window import Window


@dataclass
class Group:
    """A Group is composed with channels at some levels

    Attributes:
        index: Group number
        channels: Dictionary of channels with level
        text: Group description
    """

    index: float
    channels: dict[int, int]
    text: str = ""


class GroupChannelsView(ChannelsView):
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
        if not self.tabs or not self.lightshow:
            return
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        self.lightshow.groups[index].channels[channel] = level
        self.lightshow.set_modified()

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        if not self.tabs or not self.lightshow:
            return
        channels = self.get_selected_channels()
        selected_group = typing.cast(
            GroupTab, self.tabs.tabs["groups"]
        ).flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        for channel in channels:
            level = self.lightshow.groups[index].channels.get(channel, 0)
            if direction == Gdk.ScrollDirection.UP:
                level = min(level + step, 255)
            elif direction == Gdk.ScrollDirection.DOWN:
                level = max(level - step, 0)
            self.lightshow.groups[index].channels[channel] = level
        self.update()
        self.lightshow.set_modified()

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
        if selected_group:
            group_number = selected_group[0].get_child().number
            group = None
            for group in self.lightshow.groups:
                if group.index == group_number:
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

    def __filter_all(self, group: GroupWidget, child: Gtk.FlowBoxChild) -> bool:
        """Display all channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        channel = child.get_index() + 1  # Channel number
        channel_widget = child.get_child()
        if group.channels.get(channel) or child.is_selected():
            channel_widget.level = group.channels.get(channel, 0)
            channel_widget.next_level = group.channels.get(channel, 0)
        else:
            channel_widget.level = 0
            channel_widget.next_level = 0
        child.set_visible(True)
        return True

    def __filter_patched(self, group: GroupWidget, child: Gtk.FlowBoxChild) -> bool:
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

    def __filter_active(self, group: GroupWidget, child: Gtk.FlowBoxChild) -> bool:
        """Display only active channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        channel = child.get_index() + 1
        channel_widget = child.get_child()
        if group.channels.get(channel) or child.is_selected():
            channel_widget.level = group.channels.get(channel, 0)
            channel_widget.next_level = channel_widget.level
            child.set_visible(True)
            return True
        child.set_visible(False)
        return False


# pylint: disable=too-many-instance-attributes
class GroupTab(Gtk.Paned):
    """Groups edition"""

    last_group_selected: str
    channels_view: GroupChannelsView
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        self.last_group_selected = ""
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.channels_view = GroupChannelsView(
            lightshow=self.lightshow,
            window=self.window,
            settings=self.settings,
            tabs=self.tabs,
        )
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
        # Add groups to FlowBox
        for i, _ in enumerate(self.lightshow.groups):
            self.flowbox.add(
                GroupWidget(
                    self.lightshow.groups[i].index, self.lightshow.groups[i].text
                )
            )
        self.scrolled.add(self.flowbox)

    def refresh(self) -> None:
        """Refresh display"""
        # Remove Old Groups
        self.scrolled.remove(self.flowbox)
        self.flowbox.destroy()
        # Update Group tab
        self.populate_tab()
        self.channels_view.update()
        self.flowbox.invalidate_filter()
        self.window.show_all()

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

    def _keypress_backspace(self) -> None:
        self.window.commandline.set_string("")

    def _keypress_escape(self) -> None:
        """Close Tab"""
        self.tabs.close("groups")

    def _keypress_l(self) -> None:
        """Open Popover to change label group"""
        if selected := self.flowbox.get_selected_children():
            flowboxchild = selected[0]
            flowboxchild.get_child().popover.popup()
        self.window.commandline.set_string("")

    def _keypress_right(self) -> None:
        """Next Group"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                self.flowbox.select_child(child)
                self.window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        elif child := self.flowbox.get_child_at_index(
            int(self.last_group_selected) + 1
        ):
            self.flowbox.select_child(child)
            self.window.set_focus(child)
            self.channels_view.flowbox.unselect_all()
            self.channels_view.update()
            self.last_group_selected = str(int(self.last_group_selected) + 1)
        self.channels_view.last_selected_channel = ""

    def _keypress_left(self) -> None:
        """Previous Group"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                self.flowbox.select_child(child)
                self.window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        elif int(self.last_group_selected) > 0:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected) - 1)
            self.flowbox.select_child(child)
            self.window.set_focus(child)
            self.channels_view.flowbox.unselect_all()
            self.channels_view.update()
            self.last_group_selected = str(int(self.last_group_selected) - 1)
        self.channels_view.last_selected_channel = ""

    def _keypress_down(self) -> None:
        """Group on Next Line"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                self.flowbox.select_child(child)
                self.window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected))
            allocation = child.get_allocation()
            if child := self.flowbox.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            ):
                self.flowbox.unselect_all()
                index = child.get_index()
                self.flowbox.select_child(child)
                self.window.set_focus(child)
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.last_group_selected = str(index)
        self.channels_view.last_selected_channel = ""

    def _keypress_up(self) -> None:
        """Group on Previous Line"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                self.flowbox.select_child(child)
                self.window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected))
            allocation = child.get_allocation()
            if child := self.flowbox.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            ):
                self.flowbox.unselect_all()
                index = child.get_index()
                self.flowbox.select_child(child)
                self.window.set_focus(child)
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.last_group_selected = str(index)
        self.channels_view.last_selected_channel = ""

    def _keypress_g(self) -> None:
        """Select Group"""
        self.flowbox.unselect_all()

        keystring = self.window.commandline.get_string()
        if keystring != "":
            group = float(keystring)
            flowbox_children = self.flowbox.get_children()
            for flowbox_child in flowbox_children:
                group_widget = flowbox_child.get_child()
                if group_widget.number == group:
                    index = flowbox_child.get_index()
                    self.flowbox.select_child(flowbox_child)
                    self.window.set_focus(flowbox_child)
                    self.last_group_selected = str(index)
                    break
        # Deselect all channels
        self.channels_view.flowbox.unselect_all()
        # Update display
        self.channels_view.update()
        self.flowbox.invalidate_filter()
        self.channels_view.last_selected_channel = ""

        self.window.commandline.set_string("")

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
        self.window.commandline.set_string("")

    def _keypress_colon(self) -> None:
        """Level - %"""
        self.channels_view.level_minus()
        self.channels_view.update()
        self._update_fader_level()
        self.window.commandline.set_string("")

    def _keypress_exclam(self) -> None:
        """Level + %"""
        self.channels_view.level_plus()
        self.channels_view.update()
        self._update_fader_level()
        self.window.commandline.set_string("")

    def _keypress_n(self) -> None:
        """New Group"""
        keystring = self.window.commandline.get_string()
        # If no group number, use the next one
        if keystring == "":
            group_nb = (
                1.0
                if len(self.lightshow.groups) == 0
                else self.lightshow.groups[-1].index + 1.0
            )
        elif is_non_nul_float(keystring):
            group_nb = float(keystring)
        else:
            self.window.commandline.set_string("")
            return

        for group in self.lightshow.groups:
            if group.index == group_nb:
                self.window.commandline.set_string("")
                return

        channels: dict[int, int] = {}
        txt = str(group_nb)
        self.lightshow.groups.append(Group(group_nb, channels, txt))
        # Insert group widget
        flowbox_children = self.flowbox.get_children()
        i = len(flowbox_children)
        for child in flowbox_children:
            channel_widget = child.get_child()
            if group_nb < channel_widget.number:
                i = child.get_index()
                break
        self.flowbox.insert(
            GroupWidget(
                self.lightshow.groups[-1].index, self.lightshow.groups[-1].text
            ),
            i,
        )
        flowboxchild = self.flowbox.get_child_at_index(i)
        flowboxchild.show_all()
        self.flowbox.select_child(flowboxchild)
        self.window.set_focus(flowboxchild)
        self.last_group_selected = str(i)
        self.channels_view.flowbox.unselect_all()
        self.channels_view.update()

        self.window.commandline.set_string("")
        self.lightshow.set_modified()

    def _keypress_delete(self) -> None:
        """Delete selected group"""
        if not (selected := self.flowbox.get_selected_children()):
            return
        # Update groups
        flowboxchild = selected[0]
        index = flowboxchild.get_index()
        flowboxchild.destroy()
        if index + 1 == len(self.lightshow.groups):
            flowboxchild = self.flowbox.get_child_at_index(index - 1)
            self.last_group_selected = str(index - 1)
        else:
            flowboxchild = self.flowbox.get_child_at_index(index)
        if flowboxchild:
            self.flowbox.select_child(flowboxchild)
        self.channels_view.update()
        # Update faders
        group = self.lightshow.groups[index]
        fader_bank = self.lightshow.fader_bank
        for page, faders in fader_bank.faders.items():
            for fader in faders.values():
                if fader.contents is group:
                    fader_bank.set_fader(page, fader.index, FaderType.NONE, None)
                    fader_tab = typing.cast(FaderTab, self.tabs.tabs["faders"])
                    if fader_tab:
                        fader_tab.refresh()
        # Remove group
        self.lightshow.groups.pop(index)
        if not self.lightshow.groups:
            self.last_group_selected = ""
        self.lightshow.set_modified()
