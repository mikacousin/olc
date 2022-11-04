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
from olc.widgets_channels_view import ChannelsView, VIEW_MODES


class IndependentsTab(Gtk.Paned):
    """Tab to edit independents"""

    def __init__(self):
        self.keystring = ""
        # Channels modified by user
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.channels_view = IndeChannelsView()
        self.add(self.channels_view)

        # List of independents
        self.liststore = Gtk.ListStore(int, str, str)
        for inde in App().independents.independents:
            self.liststore.append([inde.number, inde.inde_type, inde.text])
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_changed)
        self.treeview.connect("focus-in-event", self.on_focus)
        for i, column_title in enumerate(["Number", "Type", "Text"]):
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

    def on_focus(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Give focus to notebook

        Returns:
            False
        """
        notebook = self.get_parent()
        if notebook:
            notebook.grab_focus()
        return False

    def on_changed(self, _treeview):
        """Select independent"""
        self.channels_view.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        self.channels_view.update()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().inde_tab = None

    def text_edited(self, _widget, path, text):
        """Independent text edited

        Args:
            path: Path to object
            text: New text
        """
        self.liststore[path][2] = text
        number = self.liststore[path][0]
        App().independents.independents[number - 1].text = text

    def on_key_press_event(self, _widget, event):
        """Keyboard events

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        # Hack to know if user is editing something
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
        # Channels View
        self.keystring = self.channels_view.on_key_press(keyname, self.keystring)

        if func := getattr(self, "_keypress_" + keyname, None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().inde_tab = None

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self):
        """@ level"""
        channels, level = self.channels_view.at_level(self.keystring)
        if channels and level != -1:
            for channel in channels:
                self.user_channels[channel - 1] = level
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
            for channel in channels:
                channel_widget = self.channels_view.get_channel_widget(channel)
                level = channel_widget.level
                level = max(level - step_level, 0)
                self.user_channels[channel - 1] = level
        self.channels_view.update()

    def _keypress_exclam(self):
        """Level + %"""
        channels = self.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            for channel in channels:
                channel_widget = self.channels_view.get_channel_widget(channel)
                level = channel_widget.level
                level = min(level + step_level, 255)
                self.user_channels[channel - 1] = level
        self.channels_view.update()

    def _keypress_U(self):  # pylint: disable=C0103
        """Update independent channels"""
        # Find independent
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            number = self.liststore[row][0]
            # Update channels level
            channels = array.array("B", [0] * MAX_CHANNELS)
            for channel in range(MAX_CHANNELS):
                channel_widget = self.channels_view.get_channel_widget(channel + 1)
                channels[channel] = channel_widget.level
            App().independents.independents[number - 1].set_levels(channels)
            App().independents.update_channels()
            App().independents.independents[number - 1].update_dmx()
            App().window.live_view.channels_view.flowbox.queue_draw()
            self.queue_draw()

            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)


class IndeChannelsView(ChannelsView):
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
            App().inde_tab.user_channels[channel - 1] = level

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        if not App().independents.independents or not App().inde_tab:
            return False
        # Find selected independent
        path, _focus_column = App().inde_tab.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            if self.view_mode == VIEW_MODES["Active"]:
                return self._filter_active(row, child)
            if self.view_mode == VIEW_MODES["Patched"]:
                return self._filter_patched(row, child)
            return self._filter_all(row, child)
        return False

    def _filter_active(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in Active mode

        Args:
            row: Row number
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channels = App().inde_tab.user_channels
        channels = App().independents.independents[row].levels
        if channels[channel_index] or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels[channel_index]
                channel_widget.next_level = channels[channel_index]
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            return True
        if user_channels[channel_index] != -1:
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        return False

    def _filter_patched(self, row: int, child: Gtk.FlowBoxChild) -> bool:
        """Filter in Patched mode

        Args:
            row: Row number
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        # Return all patched channels
        channel_index = child.get_index()
        if channel_index + 1 not in App().patch.channels:
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
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channels = App().inde_tab.user_channels
        channels = App().independents.independents[row].levels
        if channels[channel_index] or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels[channel_index]
                channel_widget.next_level = channels[channel_index]
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            return True
        if user_channels[channel_index] != -1:
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        return True
