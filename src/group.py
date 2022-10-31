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
import array
from dataclasses import dataclass

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App, is_non_nul_float
from olc.widgets_channels_view import ChannelsView, VIEW_MODES
from olc.widgets_group import GroupWidget


@dataclass
class Group:
    """A Group is composed with channels at some levels

    Attributes:
        index: Group number
        channels: Array of channels with levels
        text: Group description
    """

    index: float
    channels: array.array = ("B", [0] * MAX_CHANNELS)  # type: ignore
    text: str = ""


class GroupTab(Gtk.Paned):
    """Groups edition"""

    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""
        self.last_group_selected = ""

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.channels_view = GroupChannelsView()
        self.add1(self.channels_view)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flowbox = Gtk.FlowBox()
        self.populate_tab()
        self.add2(self.scrolled)

    def populate_tab(self):
        """Add groups to tab"""
        # New FlowBox
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_activate_on_single_click(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # Add groups to FlowBox
        for i, _ in enumerate(App().groups):
            self.flowbox.add(GroupWidget(App().groups[i].index, App().groups[i].text))
        self.scrolled.add(self.flowbox)

    def on_close_icon(self, _widget):
        """Close Tab with the icon clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().group_tab = None

    def on_key_press_event(self, _widget, event):
        """Key has been presed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            App().window.statusbar.push(App().window.context_id, self.keystring)

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
            self.keystring += keyname[3:]
            App().window.statusbar.push(App().window.context_id, self.keystring)

        if keyname == "period":
            self.keystring += "."
            App().window.statusbar.push(App().window.context_id, self.keystring)

        # Channels View
        self.last_chan_selected, self.keystring = self.channels_view.on_key_press(
            keyname, self.last_chan_selected, self.keystring
        )

        if func := getattr(self, "_keypress_" + keyname, None):
            return func()
        return False

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().group_tab = None

    def _keypress_Right(self):  # pylint: disable=C0103
        """Next Group"""
        if self.last_group_selected == "":
            child = self.flowbox.get_child_at_index(0)
            if child:
                self.flowbox.select_child(child)
                App().window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected) + 1)
            if child:
                self.flowbox.select_child(child)
                App().window.set_focus(child)
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.last_group_selected = str(int(self.last_group_selected) + 1)
        self.get_parent().grab_focus()
        self.last_chan_selected = ""

    def _keypress_Left(self):  # pylint: disable=C0103
        """Previous Group"""
        if self.last_group_selected == "":
            child = self.flowbox.get_child_at_index(0)
            if child:
                self.flowbox.select_child(child)
                App().window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        elif int(self.last_group_selected) > 0:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected) - 1)
            self.flowbox.select_child(child)
            App().window.set_focus(child)
            self.channels_view.flowbox.unselect_all()
            self.channels_view.update()
            self.last_group_selected = str(int(self.last_group_selected) - 1)
        self.get_parent().grab_focus()
        self.last_chan_selected = ""

    def _keypress_Down(self):  # pylint: disable=C0103
        """Group on Next Line"""
        if self.last_group_selected == "":
            child = self.flowbox.get_child_at_index(0)
            if child:
                self.flowbox.select_child(child)
                App().window.set_focus(child)
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
                App().window.set_focus(child)
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.last_group_selected = str(index)
        self.get_parent().grab_focus()
        self.last_chan_selected = ""

    def _keypress_Up(self):  # pylint: disable=C0103
        """Group on Previous Line"""
        if self.last_group_selected == "":
            child = self.flowbox.get_child_at_index(0)
            if child:
                self.flowbox.select_child(child)
                App().window.set_focus(child)
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
                App().window.set_focus(child)
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.last_group_selected = str(index)
        self.get_parent().grab_focus()
        self.last_chan_selected = ""

    def _keypress_g(self):
        """Select Group"""
        self.flowbox.unselect_all()

        if self.keystring != "":
            group = float(self.keystring)
            flowbox_children = self.flowbox.get_children()
            for flowbox_child in flowbox_children:
                group_widget = flowbox_child.get_child()
                if group_widget.number == group:
                    index = flowbox_child.get_index()
                    self.flowbox.select_child(flowbox_child)
                    App().window.set_focus(flowbox_child)
                    self.last_group_selected = str(index)
                    break
        # Deselect all channels
        self.channels_view.flowbox.unselect_all()
        # Update display
        self.channels_view.update()
        self.flowbox.invalidate_filter()
        self.last_chan_selected = ""

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self):
        """@ Level"""
        channels, level = self.channels_view.at_level(self.keystring)
        if channels and level != -1:
            selected_group = self.flowbox.get_selected_children()[0]
            index = selected_group.get_index()
            for channel in channels:
                App().groups[index].channels[channel - 1] = level
        self.channels_view.update()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Level - %"""
        channels = self.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            selected_group = self.flowbox.get_selected_children()[0]
            index = selected_group.get_index()
            for channel in channels:
                level = App().groups[index].channels[channel - 1]
                level = max(level - step_level, 0)
                App().groups[index].channels[channel - 1] = level
        self.channels_view.update()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_exclam(self):
        """Level + %"""
        channels = self.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            selected_group = self.flowbox.get_selected_children()[0]
            index = selected_group.get_index()
            for channel in channels:
                level = App().groups[index].channels[channel - 1]
                level = min(level + step_level, 255)
                App().groups[index].channels[channel - 1] = level
        self.channels_view.update()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_N(self):  # pylint: disable=C0103
        """New Group"""
        # If no group number, use the next one
        if self.keystring == "":
            group_nb = 1.0 if len(App().groups) == 0 else App().groups[-1].index + 1.0
        elif is_non_nul_float(self.keystring):
            group_nb = float(self.keystring)
        else:
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return

        for group in App().groups:
            if group.index == group_nb:
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return

        channels = array.array("B", [0] * MAX_CHANNELS)
        txt = str(group_nb)
        App().groups.append(Group(group_nb, channels, txt))
        # Insert group widget
        flowbox_children = self.flowbox.get_children()
        i = len(flowbox_children)
        for child in flowbox_children:
            channel_widget = child.get_child()
            if group_nb < channel_widget.number:
                i = child.get_index()
                break
        self.flowbox.insert(
            GroupWidget(App().groups[-1].index, App().groups[-1].text), i
        )
        flowboxchild = self.flowbox.get_child_at_index(i)
        flowboxchild.show_all()
        self.flowbox.select_child(flowboxchild)
        App().window.set_focus(flowboxchild)
        self.last_group_selected = str(i)
        self.channels_view.flowbox.unselect_all()
        self.channels_view.update()
        self.get_parent().grab_focus()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)


class GroupChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self):
        super().__init__()

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        channels = self.get_selected_channels()
        selected_group = App().group_tab.flowbox.get_selected_children()[0]
        index = selected_group.get_index()
        for channel in channels:
            level = App().groups[index].channels[channel - 1]
            if direction == Gdk.ScrollDirection.UP:
                level = min(level + step, 255)
            elif direction == Gdk.ScrollDirection.DOWN:
                level = max(level - step, 0)
            App().groups[index].channels[channel - 1] = level
        self.update()

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Select channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        # Find selected group
        selected_group = None
        if App().group_tab:
            selected_group = App().group_tab.flowbox.get_selected_children()
        if selected_group:
            group_number = selected_group[0].get_child().number
            group = None
            for group in App().groups:
                if group.index == group_number:
                    break
            if not group:
                return False
            # Display active channels
            if self.view_mode == VIEW_MODES["Active"]:
                return self.__filter_active(group, child)
            # Display patched channels
            if self.view_mode == VIEW_MODES["Patched"]:
                return self.__filter_patched(group, child)
            # Display all channels by default
            return self.__filter_all(group, child)
        return False

    def __filter_all(self, group: GroupWidget, child: Gtk.FlowBoxChild) -> bool:
        """Display all channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        channel_index = child.get_index()  # Widget number (channel - 1)
        channel_widget = child.get_child()
        if group.channels[channel_index] or child.is_selected():
            channel_widget.level = group.channels[channel_index]
            channel_widget.next_level = channel_widget.level
        else:
            channel_widget.level = 0
            channel_widget.next_level = channel_widget.level
        return True

    def __filter_active(self, group: GroupWidget, child: Gtk.FlowBoxChild) -> bool:
        """Display only active channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        channel_index = child.get_index()  # Widget number (channel - 1)
        channel_widget = child.get_child()
        if group.channels[channel_index] or child.is_selected():
            channel_widget.level = group.channels[channel_index]
            channel_widget.next_level = channel_widget.level
            return True
        return False

    def __filter_patched(self, group: GroupWidget, child: Gtk.FlowBoxChild) -> bool:
        """Display only patched channels

        Args:
            group: Group widget
            child: Parent of Channel Widget

        Returns:
            True (visible) or False (not visible)
        """
        channel_index = child.get_index()  # Widget number (channel - 1)
        channel_widget = child.get_child()
        if channel_index + 1 in App().patch.channels:
            if group.channels[channel_index] or child.is_selected():
                channel_widget.level = group.channels[channel_index]
                channel_widget.next_level = channel_widget.level
            else:
                channel_widget.level = 0
                channel_widget.next_level = channel_widget.level
            return True
        return False
