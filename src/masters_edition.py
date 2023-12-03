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
import array
from typing import Dict

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets.channels_view import ChannelsView, VIEW_MODES


class MastersTab(Gtk.Paned):
    """Masters edition"""

    def __init__(self):
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(500)

        self.channels_view = MasterChannelsView()
        self.add(self.channels_view)

        # Content Type
        content_type = Gtk.ListStore(str)
        types = ["", "Preset", "Channels", "Sequence", "Group"]
        for item in types:
            content_type.append([item])
        # Mode
        self.mode = Gtk.ListStore(str)
        modes = ["Inclusif", "Exclusif"]
        for item in modes:
            self.mode.append([item])

        self.liststores = []
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        for page in range(10):
            # Liststore
            self.liststores.append(Gtk.ListStore(int, str, str, str))
            self.populate_tab(page)
            # Treeview
            self.new_treeview(page, content_type)
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        vbox.pack_start(stack_switcher, False, True, 0)
        vbox.pack_start(self.stack, True, True, 0)

        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.set_hexpand(True)
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(vbox)
        self.add(scrollable)

    def new_treeview(self, page: int, content_type: Gtk.ListStore) -> None:
        """Create treeview

        Args:
            page: Page number (0-9)
            content_type: Available master types
        """
        child = Gtk.TreeView(model=self.liststores[page])
        child.set_enable_search(False)
        child.connect("cursor-changed", self.on_master_changed)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Master", renderer, text=0)
        child.append_column(column)
        renderer = Gtk.CellRendererCombo()
        renderer.set_property("editable", True)
        renderer.set_property("model", content_type)
        renderer.set_property("text-column", 0)
        renderer.set_property("has-entry", False)
        renderer.connect("edited", self.on_content_type_changed)
        column = Gtk.TreeViewColumn("Content type", renderer, text=1)
        child.append_column(column)
        renderer = Gtk.CellRendererText()
        renderer.set_property("editable", True)
        renderer.connect("edited", self.on_content_value_edited)
        column = Gtk.TreeViewColumn("Content", renderer, text=2)
        child.append_column(column)
        renderer = Gtk.CellRendererCombo()
        renderer.set_property("editable", True)
        renderer.set_property("model", self.mode)
        renderer.set_property("text-column", 0)
        renderer.set_property("has-entry", False)
        renderer.connect("edited", self.on_mode_changed)
        column = Gtk.TreeViewColumn("Mode", renderer, text=3)
        child.append_column(column)
        self.stack.add_titled(child, str(page), f"Page {page + 1}")

    def refresh(self) -> None:
        """Refresh display"""
        for page in range(10):
            self.liststores[page].clear()
            self.populate_tab(page)
        self.channels_view.update()

    def populate_tab(self, page: int) -> None:
        """Add Masters to tab

        Args:
            page: Page to populate (0-9)
        """
        # Masters (10 Masters per page)
        for i in range(10):
            index = i + (page * 10)
            # Type: None
            if App().masters[index].content_type == 0:
                self.liststores[page].append([index + 1, "", "", ""])
            # Type: Preset
            elif App().masters[index].content_type == 1:
                content_value = str(App().masters[index].content_value)
                self.liststores[page].append([index + 1, "Preset", content_value, ""])
            # Type: Group
            elif App().masters[index].content_type == 13:
                content_value = (
                    str(int(App().masters[index].content_value))
                    if App().masters[index].content_value.is_integer()
                    else str(App().masters[index].content_value)
                )
                self.liststores[page].append(
                    [index + 1, "Group", content_value, "Exclusif"]
                )
            # Type: Channels
            elif App().masters[index].content_type == 2:
                nb_chan = len(App().masters[index].content_value)
                self.liststores[page].append([index + 1, "Channels", str(nb_chan), ""])
            # Type: Sequence
            elif App().masters[index].content_type == 3:
                content_value = (
                    str(int(App().masters[index].content_value))
                    if App().masters[index].content_value.is_integer()
                    else str(App().masters[index].content_value)
                )
                self.liststores[page].append([index + 1, "Sequence", content_value, ""])
            else:
                self.liststores[page].append([index + 1, "Unknown", "", ""])

    def on_master_changed(self, _treeview):
        """New master is selected"""
        self.channels_view.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        self.channels_view.update()

    def on_content_type_changed(self, _widget, path, text):
        """Master type has been changed

        Args:
            path (int): Row (starting at 0)
            text (str): Master type
        """
        page = int(self.stack.get_visible_child_name())
        # Update display
        self.liststores[page][path][1] = text
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
        index = int(path) + (page * 10)
        if App().masters[index].content_type != content_type:
            App().masters[index].content_type = content_type
            # Update content value
            App().masters[index].content_value = {} if content_type == 2 else -1
            App().masters[index].text = ""
            # Update ui
            self.channels_view.update()
            self.liststores[page][path][2] = ""
            self.liststores[page][path][3] = ""
            # Update Virtual Console
            if App().virtual_console and App().virtual_console.props.visible:
                App().virtual_console.flashes[int(path)].label = ""
                App().virtual_console.flashes[int(path)].queue_draw()
            # Update MIDI
            App().midi.lcd.show_masters()

    def on_mode_changed(self, _widget, path, text):
        """Master mode has been changed
        Master modes are not used for now, just change displayed text

        Args:
            path (int): Row number (starting at 0)
            text (str): Mode
        """
        page = int(self.stack.get_visible_child_name())
        self.liststores[page][path][3] = text

    def on_content_value_edited(self, _widget, path, text):
        """Master Content value has been changed

        Args:
            path (int): Row number (starting at 0)
            text (str): Value
        """
        if text == "":
            text = "0"

        if text.replace(".", "", 1).isdigit():
            if text[0] == ".":
                text = f"0{text}"

            page = int(self.stack.get_visible_child_name())
            self.liststores[page][path][2] = "" if text == "0" else text
            # Update content value
            index = int(path) + (page * 10)
            content_value = float(text)

            App().masters[index].content_value = content_value

            if App().masters[index].content_type in [0, 2]:
                App().masters[index].text = ""
            elif App().masters[index].content_type == 1:
                if self.liststores[page][path][2] != "":
                    self.liststores[page][path][2] = str(
                        float(self.liststores[page][path][2])
                    )
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
            self.channels_view.update()
            # Update Virtual Console
            if App().virtual_console:
                App().virtual_console.flashes[index].label = App().masters[index].text
                App().virtual_console.flashes[index].queue_draw()
            # Update MIDI
            App().midi.lcd.show_masters()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        App().tabs.close("masters")

    def on_key_press_event(self, _widget, event):
        """Key has been pressed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
        # Hack to know if user is editing something
        widget = App().window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            App().window.commandline.add_string(keyname)

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
            App().window.commandline.add_string(keyname[3:])

        if keyname == "period":
            App().window.commandline.add_string(".")

        # Channels View
        treeview = self.stack.get_visible_child()
        path, _focus_column = treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            if App().masters[row].content_type not in (0, 3) or keyname in "f":
                self.channels_view.on_key_press(keyname)
        elif keyname in "f":
            self.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname}", None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        App().tabs.close("masters")

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        App().window.commandline.set_string("")

    def _keypress_equal(self):
        """@ level"""
        self.channels_view.at_level()
        self.channels_view.update()
        App().window.commandline.set_string("")

    def _keypress_colon(self):
        """Level - %"""
        self.channels_view.level_minus()
        self.channels_view.update()

    def _keypress_exclam(self):
        """Level + %"""
        self.channels_view.level_plus()
        self.channels_view.update()

    def _keypress_U(self):  # pylint: disable=C0103
        self._keypress_R()

    def _keypress_R(self):  # pylint: disable=C0103
        """Record Master

        Returns:
            True or False
        """
        self.channels_view.flowbox.unselect_all()
        # Find selected Master
        treeview = self.stack.get_visible_child()
        path, _focus_column = treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            page = int(self.stack.get_visible_child_name())
            index = (page * 10) + row
            # Type : None
            if App().masters[index].content_type == 0:
                return False
            # Type : Preset
            if App().masters[index].content_type == 1:
                found = False
                mem = None
                for mem in App().memories:
                    if mem.memory == App().masters[index].content_value:
                        found = True
                        break
                if found:
                    master_level = App().masters[index].value
                    App().masters[index].set_level(0)
                    channels = mem.channels
                    for chan in range(1, MAX_CHANNELS + 1):
                        channel_widget = self.channels_view.get_channel_widget(chan)
                        channels[chan] = channel_widget.level
                    # Update Preset Tab if open
                    if App().tabs.tabs["memories"]:
                        App().tabs.tabs["memories"].channels_view.update()
                    App().masters[index].set_level(master_level)
            # Type : Channels
            if App().masters[index].content_type == 2:
                master_level = App().masters[index].value
                App().masters[index].set_level(0)
                channels = App().masters[index].content_value
                channels.clear()
                nb_chan = 0
                text = "Ch"
                for chan in range(MAX_CHANNELS):
                    channel_widget = self.channels_view.get_channel_widget(chan + 1)
                    if channel_widget.level:
                        channels[chan + 1] = channel_widget.level
                        nb_chan += 1
                        text += f" {chan + 1}"
                App().masters[index].text = text
                App().masters[index].set_level(master_level)
                # Update Display
                self.liststores[page][path][2] = str(nb_chan)
                self.channels_view.update()
                # Update Virtual Console
                if App().virtual_console:
                    App().virtual_console.flashes[row].label = App().masters[index].text
                    App().virtual_console.flashes[row].queue_draw()
            elif App().masters[index].content_type == 13:
                found = False
                grp = None
                for grp in App().groups:
                    if grp.index == App().masters[index].content_value:
                        found = True
                        break
                if found:
                    for chan in range(MAX_CHANNELS):
                        channel_widget = self.channels_view.get_channel_widget(chan + 1)
                        grp.channels[chan + 1] = channel_widget.level
                    # Update Group Tab if open
                    if App().tabs.tabs["groups"]:
                        App().tabs.tabs["groups"].channels_view.update()
            App().window.commandline.set_string("")
            return True
        return False


class MasterChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self):
        super().__init__()

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)
        """
        App().tabs.tabs["masters"].user_channels[channel - 1] = level

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            level = channel_widget.level
            if direction == Gdk.ScrollDirection.UP:
                level = min(level + step, 255)
            elif direction == Gdk.ScrollDirection.DOWN:
                level = max(level - step, 0)
            channel_widget.level = level
            channel_widget.next_level = level
            channel_widget.queue_draw()
            self.set_channel_level(channel, level)

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel widget

        Returns:
            True or False
        """
        if not App().tabs.tabs["masters"]:
            child.set_visible(False)
            return False
        treeview = App().tabs.tabs["masters"].stack.get_visible_child()
        path, _focus_column = treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            page = int(App().tabs.tabs["masters"].stack.get_visible_child_name())
            index = row + (page * 10)
            # Master type is None or Sequence: No channels to display
            if App().masters[index].content_type in (0, 3):
                child.set_visible(False)
                return False
            if self.view_mode == VIEW_MODES["Active"]:
                return self._filter_active(index, child)
            if self.view_mode == VIEW_MODES["Patched"]:
                return self._filter_patched(index, child)
            return self._filter_all(index, child)
        return False

    def _filter_active(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in Active mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True or False
        """
        # Master type is Preset
        if App().masters[index].content_type == 1:
            return self.__filter_active_preset(index, child)
        # Master type is Channels
        if App().masters[index].content_type == 2:
            return self.__filter_active_channels(index, child)
        # Master type is Group
        if App().masters[index].content_type == 13:
            return self.__filter_active_group(index, child)
        child.set_visible(False)
        return False

    def __filter_active_preset(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter Preset channels in Active mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True or False
        """
        found = False
        mem = None
        preset = App().masters[index].content_value
        for mem in App().memories:
            if mem.memory == preset:
                found = True
                break
        if found:
            channels = mem.channels
            return self.__active_channels(channels, child)
        child.set_visible(False)
        return False

    def __filter_active_channels(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter recorded channels in Active mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True or False
        """
        channels = App().masters[index].content_value
        return self.__active_channels(channels, child)

    def __filter_active_group(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter Group channels in Active mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True or False
        """
        found = False
        grp = None
        group = App().masters[index].content_value
        for grp in App().groups:
            if grp.index == group:
                found = True
                break
        if found:
            channels = grp.channels
            return self.__active_channels(channels, child)
        child.set_visible(False)
        return False

    def __active_channels(
        self, channels: Dict[int, int], child: Gtk.FlowBoxChild
    ) -> bool:
        """Set Channel Widget level in Active mode

        Args:
            channels: Channels levels
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channels = App().tabs.tabs["masters"].user_channels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels.get(channel_index + 1, 0)
                channel_widget.next_level = channels.get(channel_index + 1, 0)
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        if user_channels[channel_index] != -1:
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(False)
        return False

    def _filter_patched(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in Patched mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True or False
        """
        # Return False if not patched
        channel = child.get_index() + 1
        if not App().patch.is_patched(channel):
            child.set_visible(False)
            return False
        # Return all other channels
        if App().masters[index].content_type == 1:
            return self.__filter_all_preset(index, child)
        if App().masters[index].content_type == 2:
            return self.__filter_all_channels(index, child)
        if App().masters[index].content_type == 13:
            return self.__filter_all_group(index, child)
        channel_widget = child.get_child()
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True

    def _filter_all(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in All channels mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True
        """
        # Master type is Preset
        if App().masters[index].content_type == 1:
            return self.__filter_all_preset(index, child)
        # Master type is Channels
        if App().masters[index].content_type == 2:
            return self.__filter_all_channels(index, child)
        # Master type is Group
        if App().masters[index].content_type == 13:
            return self.__filter_all_group(index, child)
        channel_widget = child.get_child()
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True

    def __filter_all_preset(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter Preset channels in All channels mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True
        """
        found = False
        mem = None
        preset = App().masters[index].content_value
        for mem in App().memories:
            if mem.memory == preset:
                found = True
                break
        if found:
            channels = mem.channels
            return self.__all_channels(channels, child)
        channel_widget = child.get_child()
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True

    def __filter_all_channels(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter Preset channels in All channels mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True
        """
        channels = App().masters[index].content_value
        return self.__all_channels(channels, child)

    def __filter_all_group(self, index: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter Preset channels in All channels mode

        Args:
            index: Master number
            child: Parent of Channel widget

        Returns:
            True
        """
        found = False
        grp = None
        group = App().masters[index].content_value
        for grp in App().groups:
            if grp.index == group:
                found = True
                break
        if found:
            channels = grp.channels
            return self.__all_channels(channels, child)
        channel_widget = child.get_child()
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True

    def __all_channels(self, channels: Dict[int, int], child: Gtk.FlowBoxChild) -> bool:
        """Set Channel Widget level

        Args:
            channels: Channels levels
            child: Parent of Channel Widget

        Returns:
            True
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channels = App().tabs.tabs["masters"].user_channels
        if channels.get(channel_index + 1) or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels.get(channel_index + 1, 0)
                channel_widget.next_level = channels.get(channel_index + 1, 0)
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        if user_channels[channel_index] != -1:
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True
