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
from olc.define import MAX_CHANNELS, App, is_non_nul_int, is_int, is_non_nul_float
from olc.widgets_channel import ChannelWidget
from olc.widgets_group import GroupWidget
from olc.zoom import zoom


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
        self.set_position(300)

        self.scrolled1 = Gtk.ScrolledWindow()
        self.scrolled1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox1 = Gtk.FlowBox()
        self.flowbox1.set_valign(Gtk.Align.START)
        self.flowbox1.set_max_children_per_line(20)
        self.flowbox1.set_homogeneous(True)
        self.flowbox1.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        for i in range(MAX_CHANNELS):
            self.flowbox1.add(ChannelWidget(i + 1, 0, 0))

        self.scrolled1.add(self.flowbox1)

        self.add1(self.scrolled1)

        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.populate_tab()

        self.add2(self.scrolled2)

        self.flowbox1.set_filter_func(self.filter_channels, None)
        self.flowbox1.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox1.connect("scroll-event", zoom)

    def populate_tab(self):
        """Add groups to tab"""
        # New FlowBox
        self.flowbox2 = Gtk.FlowBox()
        self.flowbox2.set_valign(Gtk.Align.START)
        self.flowbox2.set_max_children_per_line(20)
        self.flowbox2.set_homogeneous(True)
        self.flowbox2.set_activate_on_single_click(True)
        self.flowbox2.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # Add groups to FlowBox
        for i, _ in enumerate(App().groups):
            self.flowbox2.add(GroupWidget(App().groups[i].index, App().groups[i].text))
        self.scrolled2.add(self.flowbox2)

    def filter_channels(self, child, _user_data):
        """Display only channels group

        Args:
            child (Gtk.FlowBoxChild): Parent of Channel Widget

        Returns:
            child or False
        """
        channel_index = child.get_index()  # Widget number (channel - 1)
        channel_widget = child.get_children()[0]
        # Find selected group
        group_selected = self.flowbox2.get_selected_children()
        if group_selected:
            group_number = group_selected[0].get_children()[0].number
            for group in App().groups:
                if group.index == group_number:
                    if group.channels[channel_index] or child.is_selected():
                        channel_widget.level = group.channels[channel_index]
                        channel_widget.next_level = channel_widget.level
                        return child
                    return False
        return False

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
            child = self.flowbox2.get_child_at_index(0)
            if child:
                self.flowbox2.select_child(child)
                self.last_group_selected = "0"
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.flowbox2.invalidate_filter()
        else:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected) + 1)
            if child:
                self.flowbox2.select_child(child)
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(int(self.last_group_selected) + 1)
        self.get_parent().grab_focus()

    def _keypress_Left(self):  # pylint: disable=C0103
        """Previous Group"""
        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            if child:
                self.flowbox2.select_child(child)
                self.last_group_selected = "0"
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.flowbox2.invalidate_filter()
        elif int(self.last_group_selected) > 0:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected) - 1)
            self.flowbox2.select_child(child)
            self.flowbox1.unselect_all()
            self.flowbox1.invalidate_filter()
            self.last_group_selected = str(int(self.last_group_selected) - 1)
        self.get_parent().grab_focus()

    def _keypress_Down(self):  # pylint: disable=C0103
        """Group on Next Line"""
        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            if child:
                self.flowbox2.select_child(child)
                self.last_group_selected = "0"
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.flowbox2.invalidate_filter()
        else:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected))
            allocation = child.get_allocation()
            if child := self.flowbox2.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            ):
                self.flowbox2.unselect_all()
                index = child.get_index()
                self.flowbox2.select_child(child)
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(index)
        self.get_parent().grab_focus()

    def _keypress_Up(self):  # pylint: disable=C0103
        """Group on Previous Line"""
        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            if child:
                self.flowbox2.select_child(child)
                self.last_group_selected = "0"
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.flowbox2.invalidate_filter()
        else:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected))
            allocation = child.get_allocation()
            if child := self.flowbox2.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            ):
                self.flowbox2.unselect_all()
                index = child.get_index()
                self.flowbox2.select_child(child)
                self.flowbox1.unselect_all()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(index)
        self.get_parent().grab_focus()

    def _keypress_g(self):
        """Select Group"""
        self.flowbox2.unselect_all()

        if self.keystring != "":
            group = float(self.keystring)
            flowbox_children = self.flowbox2.get_children()
            for flowbox_child in flowbox_children:
                channel_widget = flowbox_child.get_child()
                if channel_widget.number == group:
                    index = flowbox_child.get_index()
                    child = self.flowbox2.get_child_at_index(index)
                    self.flowbox2.select_child(child)
                    self.last_group_selected = str(index)
                    break
        # Deselect all channels
        self.flowbox1.unselect_all()
        # Update display
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_a(self):
        """All Channels"""
        self.flowbox1.unselect_all()

        sel2 = self.flowbox2.get_selected_children()
        children2 = []
        for flowboxchild2 in sel2:
            children2 = flowboxchild2.get_children()

            for groupwidget in children2:
                index = groupwidget.get_parent().get_index()

                for channel in range(MAX_CHANNELS):
                    level = App().groups[index].channels[channel]
                    if level > 0:
                        child = self.flowbox1.get_child_at_index(channel)
                        self.flowbox1.select_child(child)
        self.get_parent().grab_focus()

    def _keypress_c(self):
        """Channel"""
        self.flowbox1.unselect_all()

        if is_non_nul_int(self.keystring):
            channel = int(self.keystring)
            # Only patched channels
            if channel in App().patch.channels:
                child = self.flowbox1.get_child_at_index(channel - 1)
                self.flowbox1.select_child(child)
                self.last_chan_selected = self.keystring
        self.flowbox1.invalidate_filter()

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):  # pylint: disable=C0103
        self._keypress_greater()

    def _keypress_greater(self):
        """Channel Thru"""
        if not is_non_nul_int(self.keystring):
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return
        sel = self.flowbox1.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(self.last_chan_selected):
                for channel in range(int(self.last_chan_selected) - 1, to_chan):
                    # Only patched channels
                    if channel + 1 in App().patch.channels:
                        child = self.flowbox1.get_child_at_index(channel)
                        self.flowbox1.select_child(child)
            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):
                    # Only patched channels
                    if channel + 1 in App().patch.channels:
                        child = self.flowbox1.get_child_at_index(channel)
                        self.flowbox1.select_child(child)
            self.flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_plus(self):
        """Channel +"""
        if not is_non_nul_int(self.keystring):
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return

        channel = int(self.keystring)
        if channel in App().patch.channels:
            child = self.flowbox1.get_child_at_index(channel - 1)
            self.flowbox1.select_child(child)
            self.last_chan_selected = self.keystring
            self.flowbox1.invalidate_filter()

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_minus(self):
        """Channel -"""
        if not is_non_nul_int(self.keystring):
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return

        channel = int(self.keystring)
        if channel in App().patch.channels:
            child = self.flowbox1.get_child_at_index(channel - 1)
            self.flowbox1.unselect_child(child)
            self.last_chan_selected = self.keystring
            self.flowbox1.invalidate_filter()

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self):
        """@ Level"""
        if not is_int(self.keystring):
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return

        level = int(self.keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
        else:
            level = min(level, 255)
        sel = self.flowbox2.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for groupwidget in children:
                index = groupwidget.get_parent().get_index()

                sel1 = self.flowbox1.get_selected_children()

                for flowboxchild1 in sel1:
                    children1 = flowboxchild1.get_children()

                    for channelwidget in children1:
                        channel = int(channelwidget.channel) - 1

                        if level != -1:
                            App().groups[index].channels[channel] = level
        self.flowbox1.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Level - %"""
        lvl = App().settings.get_int("percent-level")

        sel2 = self.flowbox2.get_selected_children()
        children2 = []
        for flowboxchild2 in sel2:
            children2 = flowboxchild2.get_children()
            for groupwidget in children2:
                index = groupwidget.get_parent().get_index()
                sel = self.flowbox1.get_selected_children()
                for flowboxchild in sel:
                    children = flowboxchild.get_children()
                    for channelwidget in children:
                        channel = int(channelwidget.channel) - 1
                        level = App().groups[index].channels[channel]
                        level = max(level - lvl, 0)
                        App().groups[index].channels[channel] = level
        self.flowbox1.invalidate_filter()

    def _keypress_exclam(self):
        """Level + %"""
        lvl = App().settings.get_int("percent-level")

        sel2 = self.flowbox2.get_selected_children()
        children2 = []
        for flowboxchild2 in sel2:
            children2 = flowboxchild2.get_children()
            for groupwidget in children2:
                index = groupwidget.get_parent().get_index()
                sel = self.flowbox1.get_selected_children()
                for flowboxchild in sel:
                    children = flowboxchild.get_children()
                    for channelwidget in children:
                        channel = int(channelwidget.channel) - 1
                        level = App().groups[index].channels[channel]
                        level = min(level + lvl, 255)
                        App().groups[index].channels[channel] = level
        self.flowbox1.invalidate_filter()

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
        flowbox_children = self.flowbox2.get_children()
        i = len(flowbox_children)
        for child in flowbox_children:
            channel_widget = child.get_child()
            if group_nb < channel_widget.number:
                i = child.get_index()
                break
        self.flowbox2.insert(
            GroupWidget(App().groups[-1].index, App().groups[-1].text), i
        )
        self.flowbox1.unselect_all()
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()
        App().window.show_all()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
