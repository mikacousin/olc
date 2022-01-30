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
from olc.zoom import zoom


class MastersTab(Gtk.Paned):
    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""

        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        # Channels used in selected Master
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)

        self.add(self.scrolled)

        # Content Type
        self.content_type = Gtk.ListStore(str)
        types = ["", "Preset", "Channels", "Sequence", "Group"]
        for item in types:
            self.content_type.append([item])

        # Mode
        self.mode = Gtk.ListStore(str)
        modes = ["Inclusif", "Exclusif"]
        for item in modes:
            self.mode.append([item])

        self.liststore = Gtk.ListStore(int, str, str, str)

        # Populate with masters
        self.populate_tab()

        self.filter = self.liststore.filter_new()
        self.filter.set_visible_func(self.filter_master)

        self.treeview = Gtk.TreeView(model=self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_master_changed)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Master", renderer, text=0)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererCombo()
        renderer.set_property("editable", True)
        renderer.set_property("model", self.content_type)
        renderer.set_property("text-column", 0)
        renderer.set_property("has-entry", False)
        renderer.connect("edited", self.on_content_type_changed)
        column = Gtk.TreeViewColumn("Content type", renderer, text=1)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.set_property("editable", True)
        renderer.connect("edited", self.on_content_value_edited)
        column = Gtk.TreeViewColumn("Content", renderer, text=2)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererCombo()
        renderer.set_property("editable", True)
        renderer.set_property("model", self.mode)
        renderer.set_property("text-column", 0)
        renderer.set_property("has-entry", False)
        renderer.connect("edited", self.on_mode_changed)
        column = Gtk.TreeViewColumn("Mode", renderer, text=3)
        self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

        self.flowbox.set_filter_func(self.filter_channel_func, None)
        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", zoom)

        # Select First Master
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

    def populate_tab(self):
        """Add Masters to tab"""
        # Masters (2 pages of 20 Masters)
        for page in range(2):
            for i in range(20):
                index = i + (page * 20)
                # Type: None
                if App().masters[index].content_type == 0:
                    self.liststore.append([index + 1, "", "", ""])
                # Type: Preset
                elif App().masters[index].content_type == 1:
                    content_value = str(App().masters[index].content_value)
                    self.liststore.append([index + 1, "Preset", content_value, ""])
                # Type: Group
                elif App().masters[index].content_type == 13:
                    content_value = (
                        str(int(App().masters[index].content_value))
                        if App().masters[index].content_value.is_integer()
                        else str(App().masters[index].content_value)
                    )
                    self.liststore.append(
                        [index + 1, "Group", content_value, "Exclusif"]
                    )
                # Type: Channels
                elif App().masters[index].content_type == 2:
                    nb_chan = sum(
                        1
                        for chan in range(MAX_CHANNELS)
                        if App().masters[index].content_value[chan]
                    )

                    self.liststore.append([index + 1, "Channels", str(nb_chan), ""])
                # Type: Sequence
                elif App().masters[index].content_type == 3:
                    content_value = (
                        str(int(App().masters[index].content_value))
                        if App().masters[index].content_value.is_integer()
                        else str(App().masters[index].content_value)
                    )
                    self.liststore.append([index + 1, "Sequence", content_value, ""])
                else:
                    self.liststore.append([index + 1, "Unknown", "", ""])

    def filter_master(self, _model, _i, _data):
        return True

    def filter_channel_func(self, child, _user_data):
        """Filter channels

        Args:
            child: Child object

        Returns:
            child or False
        """
        # Find selected row
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Index of Channel
            index = child.get_index()

            # Type : None
            if App().masters[row].content_type == 0:
                return False

            # Type : Preset
            if App().masters[row].content_type == 1:
                found = False
                mem = None
                preset = App().masters[row].content_value
                for mem in App().memories:
                    if mem.memory == preset:
                        found = True
                        break
                if found:
                    channels = mem.channels
                    if channels[index] or self.channels[index].clicked:
                        if self.user_channels[index] == -1:
                            self.channels[index].level = channels[index]
                            self.channels[index].next_level = channels[index]
                        else:
                            self.channels[index].level = self.user_channels[index]
                            self.channels[index].next_level = self.user_channels[index]
                        return child
                    if self.user_channels[index] == -1:
                        return False
                    self.channels[index].level = self.user_channels[index]
                    self.channels[index].next_level = self.user_channels[index]
                    return child
                return False

            # Type : Channels
            if App().masters[row].content_type == 2:
                channels = App().masters[row].content_value

                if channels[index] or self.channels[index].clicked:
                    if self.user_channels[index] == -1:
                        self.channels[index].level = channels[index]
                        self.channels[index].next_level = channels[index]
                    else:
                        self.channels[index].level = self.user_channels[index]
                        self.channels[index].next_level = self.user_channels[index]
                    return child
                if self.user_channels[index] == -1:
                    return False
                self.channels[index].level = self.user_channels[index]
                self.channels[index].next_level = self.user_channels[index]
                return child

            # Type : Sequence
            if App().masters[row].content_type == 3:
                return False

            # Type : Group
            if App().masters[row].content_type == 13:
                found = False
                grp = None
                group = App().masters[row].content_value
                for grp in App().groups:
                    if grp.index == group:
                        found = True
                        break
                if found:
                    channels = grp.channels
                    if channels[index] or self.channels[index].clicked:
                        if self.user_channels[index] == -1:
                            self.channels[index].level = channels[index]
                            self.channels[index].next_level = channels[index]
                        else:
                            self.channels[index].level = self.user_channels[index]
                            self.channels[index].next_level = self.user_channels[index]
                        return child
                    if self.user_channels[index] == -1:
                        return False
                    self.channels[index].level = self.user_channels[index]
                    self.channels[index].next_level = self.user_channels[index]
                    return child
                return False

        return False

    def on_master_changed(self, _treeview):
        """New master is selected"""
        self.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        for channel in range(MAX_CHANNELS):
            self.channels[channel].level = 0
            self.channels[channel].next_level = 0
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_content_type_changed(self, _widget, path, text):
        # Update display
        self.liststore[path][1] = text

        # Find content type
        content_type = 0

        if text == "":
            content_type = 0
        elif text == "Channels":
            content_type = 2
        elif text == "Group":
            content_type = 13

        elif text == "Preset":
            content_type = 1
        elif text == "Sequence":
            content_type = 3
        # Update content type
        index = int(path)

        if App().masters[index].content_type != content_type:

            App().masters[index].content_type = content_type

            # Update content value
            if content_type == 2:
                App().masters[index].content_type = array.array("B", [0] * MAX_CHANNELS)
            else:
                App().masters[index].content_value = -1
            App().masters[index].text = ""

            # Update ui
            self.flowbox.invalidate_filter()
            self.liststore[path][2] = ""
            self.liststore[path][3] = ""

            # Update Virtual Console
            if App().virtual_console and App().virtual_console.props.visible:
                App().virtual_console.flashes[index].label = ""
                App().virtual_console.flashes[index].queue_draw()

    def on_mode_changed(self, _widget, path, text):
        self.liststore[path][3] = text

    def on_content_value_edited(self, _widget, path, text):
        if text == "":
            text = "0"

        if text.replace(".", "", 1).isdigit():

            if text[0] == ".":
                text = "0" + text

            self.liststore[path][2] = "" if text == "0" else text
            # Update content value
            index = int(path)
            content_value = float(text)

            App().masters[index].content_value = content_value

            if App().masters[index].content_type in [0, 2]:
                App().masters[index].text = ""

            elif App().masters[index].content_type == 1:
                if self.liststore[path][2] != "":
                    self.liststore[path][2] = str(float(self.liststore[path][2]))
                App().masters[index].text = ""
                for mem in App().memories:
                    if mem.memory == content_value:
                        App().masters[index].text = mem.text

            elif App().masters[index].content_type == 13:
                App().masters[index].text = ""
                for grp in App().groups:
                    if grp.index == content_value:
                        App().masters[index].text = grp.text

            elif App().masters[index].content_type == 3:
                App().masters[index].text = ""
                for chaser in App().chasers:
                    if chaser.index == content_value:
                        App().masters[index].text = chaser.text

            self.flowbox.invalidate_filter()

            # Update Virtual Console
            if App().virtual_console:
                App().virtual_console.flashes[index].label = App().masters[index].text
                App().virtual_console.flashes[index].queue_draw()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().masters_tab = None

    def on_key_press_event(self, widget, event):

        # Hack to know if user is editing something
        # TODO: Bug with CellRendererCombo (entry blocked)
        widget = App().window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

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

    def _keypress_Escape(self):
        """Close Tab"""
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().masters_tab = None

    def _keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_c(self):
        """Channel

        Returns:
            True or False
        """

        # Find Selected Master
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if App().masters[row].content_type in [0, 3]:
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return False

            self.flowbox.unselect_all()
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
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring

            self.flowbox.invalidate_filter()

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return True
        return False

    def _keypress_KP_Divide(self):
        self._keypress_greater()

    def _keypress_greater(self):
        """Channel Thru

        Returns:
            True or False
        """

        # Find Selected Master
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if App().masters[row].content_type in [0, 3]:
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return False

            selected_children = self.flowbox.get_selected_children()
            if len(selected_children) == 1:
                flowboxchild = selected_children[0]
                channelwidget = flowboxchild.get_children()[0]
                self.last_chan_selected = channelwidget.channel

            if self.last_chan_selected:
                to_chan = int(self.keystring)
                if 0 < to_chan < MAX_CHANNELS:
                    if to_chan > int(self.last_chan_selected):
                        for channel in range(int(self.last_chan_selected) - 1, to_chan):
                            # Only patched channels
                            if App().patch.channels[channel][0] != [0, 0]:
                                self.channels[channel].clicked = True
                                child = self.flowbox.get_child_at_index(channel)
                                App().window.set_focus(child)
                                self.flowbox.select_child(child)
                    else:
                        for channel in range(to_chan - 1, int(self.last_chan_selected)):
                            # Only patched channels
                            if App().patch.channels[channel][0] != [0, 0]:
                                self.channels[channel].clicked = True
                                child = self.flowbox.get_child_at_index(channel)
                                App().window.set_focus(child)
                                self.flowbox.select_child(child)
                    self.flowbox.invalidate_filter()

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return True
        return False

    def _keypress_plus(self):
        """Channel +

        Returns:
            True or False
        """

        # Find Selected Master
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if App().masters[row].content_type in [0, 3]:
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return False

            if self.keystring != "":

                channel = int(self.keystring) - 1

                if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
                    0,
                    0,
                ]:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring

                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return True
            return False
        return False

    def _keypress_minus(self):
        """Channel -

        Returns:
            True or False
        """

        # Find Selected Master
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if App().masters[row].content_type in [0, 3]:
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return False

            if self.keystring != "":

                channel = int(self.keystring) - 1

                if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
                    0,
                    0,
                ]:
                    self.channels[channel].clicked = False
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    self.flowbox.unselect_child(child)
                    self.last_chan_selected = self.keystring

                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return True
            return False
        return False

    def _keypress_a(self):
        """All Channels

        Returns:
            True or False
        """

        # Find Selected Master
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if App().masters[row].content_type in [0, 3]:
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return False

            self.flowbox.unselect_all()

            # Master's channels
            if App().masters[row].content_type == 1:
                preset = App().masters[row].content_value
                if cue := next(mem for mem in App().memories if mem.memory == preset):
                    channels = cue.channels
                else:
                    return False
            elif App().masters[row].content_type == 13:
                group = App().masters[row].content_value
                if grp := next(grp for grp in App().groups if grp.index == group):
                    channels = grp.channels
                else:
                    return False
            elif App().masters[row].content_type == 2:
                channels = App().masters[row].content_value

            # Select channels with a level
            for chan in range(MAX_CHANNELS):
                if (
                    channels[chan] and self.user_channels[chan] != 0
                ) or self.user_channels[chan] > 0:
                    self.channels[chan].clicked = True
                    child = self.flowbox.get_child_at_index(chan)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                else:
                    self.channels[chan].clicked = False
            self.flowbox.invalidate_filter()
            return True
        return False

    def _keypress_equal(self):
        """@ level"""

        level = int(self.keystring)

        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
        if 0 <= level < 256:

            selected_children = self.flowbox.get_selected_children()

            for flowboxchild in selected_children:
                child = flowboxchild.get_children()

                for channelwidget in child:
                    channel = int(channelwidget.channel) - 1

                    self.channels[channel].level = level
                    self.channels[channel].next_level = level
                    self.channels[channel].queue_draw()
                    self.user_channels[channel] = level

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Level - %"""

        lvl = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                level = max(level - lvl, 0)
                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def _keypress_exclam(self):
        """Level + %"""

        lvl = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                level = min(level + lvl, 255)
                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def _keypress_U(self):
        self._keypress_R()

    def _keypress_R(self):
        """Record Master

        Returns:
            True or False
        """

        self.flowbox.unselect_all()

        # Find selected Master
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Type : None
            if App().masters[row].content_type == 0:
                return False

            # Type : Preset
            if App().masters[row].content_type == 1:
                found = False
                mem = None
                for mem in App().memories:
                    if mem.memory == App().masters[row].content_value:
                        found = True
                        break
                if found:
                    channels = mem.channels
                    for chan in range(MAX_CHANNELS):
                        channels[chan] = self.channels[chan].level
                    # Update Preset Tab if open
                    if App().memories_tab:
                        App().memories_tab.flowbox.invalidate_filter()

            # Type : Channels
            if App().masters[row].content_type == 2:
                channels = App().masters[row].content_value

                nb_chan = 0
                text = "Ch"
                for chan in range(MAX_CHANNELS):
                    channels[chan] = self.channels[chan].level
                    if channels[chan]:
                        nb_chan += 1
                        text += " " + str(chan + 1)

                App().masters[row].text = text

                # Update Display
                self.liststore[path][2] = str(nb_chan)
                self.flowbox.invalidate_filter()

                # Update Virtual Console
                if App().virtual_console:
                    App().virtual_console.flashes[row].label = App().masters[row].text
                    App().virtual_console.flashes[row].queue_draw()

            # Type = Group
            elif App().masters[row].content_type == 13:
                found = False
                grp = None
                for grp in App().groups:
                    if grp.index == App().masters[row].content_value:
                        found = True
                        break
                if found:
                    for chan in range(MAX_CHANNELS):
                        grp.channels[chan] = self.channels[chan].level
                    # Update Group Tab if open
                    if App().group_tab:
                        App().group_tab.flowbox1.invalidate_filter()

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return True

        return False
