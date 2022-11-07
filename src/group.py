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
from typing import Any, Dict
from dataclasses import dataclass

from gi.repository import Gdk, Gtk
from olc.define import App, is_non_nul_float
from olc.widgets.channels_view import ChannelsView, VIEW_MODES
from olc.widgets.group import GroupWidget


@dataclass
class Group:
    """A Group is composed with channels at some levels

    Attributes:
        index: Group number
        channels: Dictionary of channels with level
        text: Group description
    """

    index: float
    channels: Dict[int, int]
    text: str = ""


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
        channel = child.get_index() + 1  # Channel number
        channel_widget = child.get_child()
        if group.channels.get(channel) or child.is_selected():
            channel_widget.level = group.channels.get(channel, 0)
            channel_widget.next_level = group.channels.get(channel, 0)
        else:
            channel_widget.level = 0
            channel_widget.next_level = 0
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
        if channel not in App().patch.channels:
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
            return True
        return False


class GroupTab(Gtk.Paned):
    """Groups edition"""

    keystring: str
    last_group_selected: str
    channels_view: GroupChannelsView
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox

    def __init__(self):

        self.keystring = ""
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
        for i, _ in enumerate(App().groups):
            self.flowbox.add(GroupWidget(App().groups[i].index, App().groups[i].text))
        self.scrolled.add(self.flowbox)

    def on_close_icon(self, _widget) -> None:
        """Close Tab with the icon clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().group_tab = None

    def on_key_press_event(self, _widget, event: Gdk.Event) -> Any:
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
        self.keystring = self.channels_view.on_key_press(keyname, self.keystring)

        if func := getattr(self, f"_keypress_{keyname}", None):
            return func()
        return False

    def _keypress_BackSpace(self) -> None:  # pylint: disable=C0103
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Escape(self) -> None:  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().group_tab = None

    def _keypress_m(self) -> None:
        """Open Popover"""
        if selected := self.flowbox.get_selected_children():
            flowboxchild = selected[0]
            flowboxchild.get_child().popover.popup()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Right(self) -> None:    # pylint: disable=C0103
        """Next Group"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
                self.flowbox.select_child(child)
                App().window.set_focus(child)
                self.last_group_selected = "0"
                self.channels_view.flowbox.unselect_all()
                self.channels_view.update()
                self.flowbox.invalidate_filter()
        elif child := self.flowbox.get_child_at_index(
            int(self.last_group_selected) + 1
        ):
            self.flowbox.select_child(child)
            App().window.set_focus(child)
            self.channels_view.flowbox.unselect_all()
            self.channels_view.update()
            self.last_group_selected = str(int(self.last_group_selected) + 1)
        self.get_parent().grab_focus()
        self.channels_view.last_selected_channel = ""

    def _keypress_Left(self) -> None:    # pylint: disable=C0103
        """Previous Group"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
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
        self.channels_view.last_selected_channel = ""

    def _keypress_Down(self) -> None:    # pylint: disable=C0103
        """Group on Next Line"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
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
        self.channels_view.last_selected_channel = ""

    def _keypress_Up(self) -> None:    # pylint: disable=C0103
        """Group on Previous Line"""
        if self.last_group_selected == "":
            if child := self.flowbox.get_child_at_index(0):
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
        self.channels_view.last_selected_channel = ""

    def _keypress_g(self) -> None:
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
        self.channels_view.last_selected_channel = ""

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _update_master_level(self) -> None:
        """Update selected master channels levels"""
        if selected := self.flowbox.get_selected_children():
            flowboxchild = selected[0]
            index = flowboxchild.get_index()
            for master in App().masters:
                if (
                    master.content_type == 13
                    and master.content_value == App().groups[index].index
                ):
                    master.set_level(master.value)

    def _keypress_equal(self) -> None:
        """@ Level"""
        channels, level = self.channels_view.at_level(self.keystring)
        if channels and level != -1:
            selected_group = self.flowbox.get_selected_children()[0]
            index = selected_group.get_index()
            for channel in channels:
                App().groups[index].channels[channel] = level
        self.channels_view.update()
        self._update_master_level()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self) -> None:
        """Level - %"""
        channels = self.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            selected_group = self.flowbox.get_selected_children()[0]
            index = selected_group.get_index()
            for channel in channels:
                level = App().groups[index].channels.get(channel, 0)
                level = max(level - step_level, 0)
                App().groups[index].channels[channel] = level
        self.channels_view.update()
        self._update_master_level()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_exclam(self) -> None:
        """Level + %"""
        channels = self.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            selected_group = self.flowbox.get_selected_children()[0]
            index = selected_group.get_index()
            for channel in channels:
                level = App().groups[index].channels.get(channel, 0)
                level = min(level + step_level, 255)
                App().groups[index].channels[channel] = level
        self.channels_view.update()
        self._update_master_level()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_N(self) -> None:  # pylint: disable=C0103
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

        channels: Dict[int, int] = {}
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

    def _keypress_Delete(self) -> None:    # pylint: disable=C0103
        """Delete selected group"""
        if not (selected := self.flowbox.get_selected_children()):
            return
        # Update groups
        flowboxchild = selected[0]
        index = flowboxchild.get_index()
        flowboxchild.destroy()
        if index + 1 == len(App().groups):
            flowboxchild = self.flowbox.get_child_at_index(index - 1)
            self.last_group_selected = str(index - 1)
        else:
            flowboxchild = self.flowbox.get_child_at_index(index)
        if flowboxchild:
            self.flowbox.select_child(flowboxchild)
        self.channels_view.update()
        # Update masters
        for master in App().masters:
            if (
                master.content_type == 13
                and master.content_value == App().groups[index].index
            ):
                master.set_level(0)
                master.content_type = 0
                master.content_value = None
                master.text = ""
                if App().masters_tab:
                    App().masters_tab.channels_view.update()
                    liststore = App().masters_tab.liststores[master.page - 1]
                    treeiter = liststore.get_iter(master.number - 1)
                    liststore.set_value(treeiter, 1, "")
                    liststore.set_value(treeiter, 2, "")
                    liststore.set_value(treeiter, 3, "")
                if App().virtual_console and master.page == App().fader_page:
                    index = master.number - 1
                    fader = App().virtual_console.masters[index]
                    fader.set_value(0)
                    App().virtual_console.master_moved(fader)
                    App().virtual_console.flashes[index].label = ""
                    App().virtual_console.flashes[index].queue_draw()
                break
        # Remove group
        App().groups.pop(index)
        if not App().groups:
            self.last_group_selected = ""
