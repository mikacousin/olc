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

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget
from olc.widgets_group import GroupWidget
from olc.zoom import zoom


class Group:
    """A Group is composed with channels at some levels

    Attributes:
        index: Group number
        channels: Array of channels with levels
        text: Group description
    """

    def __init__(self, index, channels=array.array("B", [0] * MAX_CHANNELS), text=""):
        self.index = index
        self.channels = channels
        self.text = str(text)


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

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox1.add(self.channels[i])

        self.scrolled1.add(self.flowbox1)

        self.add1(self.scrolled1)

        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.grps = []

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
            self.grps.append(
                GroupWidget(i, App().groups[i].index, App().groups[i].text, self.grps)
            )
            self.flowbox2.add(self.grps[i])
        self.scrolled2.add(self.flowbox2)

    def filter_channels(self, child, _user_data):
        """Pour n'afficher que les channels du groupe

        Args:
            child: Child object

        Returns:
            child or False
        """
        i = child.get_index()  # Numéro du widget qu'on filtre (channel - 1)
        # On cherche le groupe actuellement séléctionné
        for j, _ in enumerate(self.grps):
            if self.grps[j].get_parent().is_selected():
                # Si le channel est dans le groupe, on l'affiche
                if App().groups[j].channels[i] or self.channels[i].clicked:
                    # On récupère le level (next_level à la même valeur)
                    self.channels[i].level = App().groups[j].channels[i]
                    self.channels[i].next_level = App().groups[j].channels[i]
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
        # print(keyname)

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
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.flowbox2.invalidate_filter()
        elif int(self.last_group_selected) + 1 < len(self.grps):
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected) + 1)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.last_group_selected = str(int(self.last_group_selected) + 1)

    def _keypress_Left(self):  # pylint: disable=C0103
        """Previous Group"""

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.flowbox2.invalidate_filter()
        elif int(self.last_group_selected) > 0:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected) - 1)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.last_group_selected = str(int(self.last_group_selected) - 1)

    def _keypress_Down(self):  # pylint: disable=C0103
        """Group on Next Line"""

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
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
                App().window.set_focus(child)
                self.flowbox2.select_child(child)
                # Deselect all channels
                for channel in range(MAX_CHANNELS):
                    self.channels[channel].clicked = False
                    self.channels[channel].queue_draw()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(index)

    def _keypress_Up(self):  # pylint: disable=C0103
        """Group on Previous Line"""

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
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
                App().window.set_focus(child)
                self.flowbox2.select_child(child)
                # Deselect all channels
                for channel in range(MAX_CHANNELS):
                    self.channels[channel].clicked = False
                    self.channels[channel].queue_draw()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(index)

    def _keypress_g(self):
        """Select Group"""

        self.flowbox2.unselect_all()

        if self.keystring != "":
            group = float(self.keystring)
            for grp in self.grps:
                if group == float(grp.number):
                    index = grp.index
                    child = self.flowbox2.get_child_at_index(index)
                    App().window.set_focus(child)
                    self.flowbox2.select_child(child)
                    break
            self.last_group_selected = str(index)
        # Deselect all channels
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        # Update display
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()

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
                index = groupwidget.index

                for channel in range(MAX_CHANNELS):
                    level = App().groups[index].channels[channel]
                    if level > 0:
                        self.channels[channel].clicked = True
                        child = self.flowbox1.get_child_at_index(channel)
                        App().window.set_focus(child)
                        self.flowbox1.select_child(child)

    def _keypress_c(self):
        """Channel"""

        self.flowbox1.unselect_all()
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False

        if self.keystring not in ["", "0"]:
            channel = int(self.keystring) - 1
            # Only patched channels
            if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
                0,
                0,
            ]:
                self.channels[channel].clicked = True

                child = self.flowbox1.get_child_at_index(channel)
                App().window.set_focus(child)
                self.flowbox1.select_child(child)
                self.last_chan_selected = self.keystring

        self.flowbox1.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):  # pylint: disable=C0103
        self._keypress_greater()

    def _keypress_greater(self):
        """Channel Thru"""

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
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels[channel].clicked = True

                        child = self.flowbox1.get_child_at_index(channel)
                        App().window.set_focus(child)
                        self.flowbox1.select_child(child)

            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):

                    # Only patched channels
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels[channel].clicked = True

                        child = self.flowbox1.get_child_at_index(channel)
                        App().window.set_focus(child)
                        self.flowbox1.select_child(child)

            self.flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_plus(self):
        """Channel +"""

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            self.channels[channel].clicked = True
            self.flowbox1.invalidate_filter()

            child = self.flowbox1.get_child_at_index(channel)
            App().window.set_focus(child)
            self.flowbox1.select_child(child)
            self.last_chan_selected = self.keystring

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_minus(self):
        """Channel -"""

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            self.channels[channel].clicked = False
            self.flowbox1.invalidate_filter()

            child = self.flowbox1.get_child_at_index(channel)
            App().window.set_focus(child)
            self.flowbox1.unselect_child(child)

            self.last_chan_selected = self.keystring

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self):
        """@ Level"""

        if self.keystring == "":
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
                index = groupwidget.index

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
                index = groupwidget.index

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
                index = groupwidget.index

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
            group_nb = 1 if len(App().groups) == 0 else App().groups[-1].index + 1
        else:
            group_nb = int(self.keystring)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

        channels = array.array("B", [0] * MAX_CHANNELS)
        txt = str(float(group_nb))
        App().groups.append(Group(float(group_nb), channels, txt))
        i = self.grps[-1].index + 1 if len(self.grps) > 0 else 0
        self.grps.append(
            GroupWidget(i, App().groups[-1].index, App().groups[-1].text, self.grps)
        )
        self.flowbox2.add(self.grps[-1])
        # Deselect all channels
        self.flowbox1.unselect_all()
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()
        App().window.show_all()
