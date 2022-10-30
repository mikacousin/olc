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
from olc.cue import Cue
from olc.define import MAX_CHANNELS, App, is_float
from olc.widgets_channels_view import ChannelsView, VIEW_MODES


class CuesEditionTab(Gtk.Paned):
    """Cues edition"""

    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""

        # Channels modified by user
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(500)

        self.channels_view = CueChannelsView()
        self.add(self.channels_view)

        # List of Cues
        self.liststore = Gtk.ListStore(str, str, int)

        for mem in App().memories:
            channels = sum(1 for chan in range(MAX_CHANNELS) if mem.channels[chan])
            self.liststore.append([str(mem.memory), mem.text, channels])

        self.filter = self.liststore.filter_new()

        self.treeview = Gtk.TreeView(model=self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_cue_changed)
        self.treeview.connect("focus-in-event", self.on_focus)

        for i, column_title in enumerate(["Memory", "Text", "Channels"]):
            renderer = Gtk.CellRendererText()

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)

            self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

    def on_focus(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Give focus to notebook

        Returns:
            False
        """
        notebook = self.get_parent()
        if notebook:
            notebook.grab_focus()
        return False

    def on_cue_changed(self, _treeview):
        """Selected Cue"""
        self.channels_view.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        self.channels_view.update()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().memories_tab = None

    def on_key_press_event(self, _widget, event):
        """Key has been pressed

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

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().memories_tab = None

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
                channel_widget.level = level
                channel_widget.next_level = level
                channel_widget.queue_draw()
                self.user_channels[channel] = level

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
                channel_widget.level = level
                channel_widget.next_level = level
                channel_widget.queue_draw()
                self.user_channels[channel] = level

    def _keypress_U(self):  # pylint: disable=C0103
        """Update Memory"""
        self.channels_view.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Memory's channels
            channels = App().memories[row].channels
            # Update levels and count channels
            nb_chan = 0
            for chan in range(MAX_CHANNELS):
                channel_widget = self.channels_view.get_channel_widget(chan + 1)
                channels[chan] = channel_widget.level
                if channels[chan] != 0:
                    App().sequence.channels[chan] = 1
                    nb_chan += 1
            # Update Display
            treeiter = self.liststore.get_iter(row)
            self.liststore.set_value(treeiter, 2, nb_chan)
            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

    def _keypress_Delete(self):  # pylint: disable=C0103
        """Deletes selected Memory"""
        # TODO: Ask confirmation
        self.channels_view.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Find Steps using selected memory
            steps = [
                i
                for i, _ in enumerate(App().sequence.steps)
                if App().sequence.steps[i].cue.memory == App().memories[row].memory
            ]
            # Delete Steps
            for step in steps:
                App().sequence.steps.pop(step)
                App().sequence.last -= 1
            # Delete memory from the Memories List
            App().memories.pop(row)
            # Remove it from the ListStore
            treeiter = self.liststore.get_iter(path)
            self.liststore.remove(treeiter)
            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")
            # Update Main Playback
            App().window.playback.update_sequence_display()
            # Update Sequence Edition Tab if exist
            if App().sequences_tab:
                App().sequences_tab.liststore1.clear()
                App().sequences_tab.liststore1.append(
                    [
                        App().sequence.index,
                        App().sequence.type_seq,
                        App().sequence.text,
                    ]
                )
                for chaser in App().chasers:
                    App().sequences_tab.liststore1.append(
                        [chaser.index, chaser.type_seq, chaser.text]
                    )
                App().sequences_tab.treeview1.set_model(App().sequences_tab.liststore1)
                pth = Gtk.TreePath.new()
                App().window.playback.treeview1.set_cursor(pth, None, False)

    def _keypress_R(self):  # pylint: disable=C0103
        """Records a copy of the current Memory with a new number

        Returns:
            True or False
        """
        if not is_float(self.keystring):
            return False

        mem = float(self.keystring)
        if not mem:
            return False

        # Memory already exist ?
        for i, _ in enumerate(App().memories):
            if App().memories[i].memory == mem:
                # Find selected memory
                path, _focus_column = self.treeview.get_cursor()
                if path:
                    row = path.get_indices()[0]
                    # Copy channels
                    App().memories[i].channels = App().memories[row].channels
                    # Count channels
                    nb_chan = sum(
                        1
                        for chan in range(MAX_CHANNELS)
                        if App().memories[i].channels[chan]
                    )
                    # Update Display
                    treeiter = self.liststore.get_iter(i)
                    self.liststore.set_value(treeiter, 2, nb_chan)
                    if i == App().sequence.position:
                        for channel in range(MAX_CHANNELS):
                            flowbox = App().window.live_view.channels_view.flowbox
                            widget = flowbox.get_child_at_index(channel).get_child()
                            widget.next_level = App().memories[i].channels[channel]
                            widget.queue_draw()
                    # Tag filename as modified
                    App().ascii.modified = True
                    App().window.header.set_title(App().ascii.basename + "*")
                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)
                return True

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            sequence = App().memories[row].sequence
            channels = App().memories[row].channels
            cue = Cue(sequence, mem, channels)
            # Insert Memory
            found = False
            for i, _ in enumerate(App().memories):
                if App().memories[i].memory > mem:
                    found = True
                    break
            if not found:
                i += 1
            App().memories.insert(i, cue)
            nb_chan = sum(bool(channels[chan]) for chan in range(MAX_CHANNELS))
            self.liststore.insert(i, [str(mem), "", nb_chan])
            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        return True

    def _keypress_Insert(self):  # pylint: disable=C0103
        """Insert a new Memory

        Returns:
            True or False
        """
        if self.keystring == "":
            # Insert memory with the next free number
            mem = False
            # Find Next free number
            if len(App().memories) > 1:
                for i, _ in enumerate(App().memories[:-1]):
                    if (
                        int(App().memories[i + 1].memory)
                        - int(App().memories[i].memory)
                        > 1
                    ):
                        mem = App().memories[i].memory + 1
                        break
            elif len(App().memories) == 1:
                # Just one memory
                mem = App().memories[0].memory + 1
                i = 1
            else:
                # The list is empty
                i = 0
                mem = 1.0

            # Free number is at the end
            if not mem:
                mem = App().memories[-1].memory + 1
                i += 1

            # Find selected memory for channels levels
            path, _focus_column = self.treeview.get_cursor()
            if path:
                row = path.get_indices()[0]
                channels = App().memories[row].channels
            else:
                channels = array.array("B", [0] * MAX_CHANNELS)

            # Create new memory
            cue = Cue(0, mem, channels)
            App().memories.insert(i + 1, cue)
            nb_chan = sum(1 for chan in range(MAX_CHANNELS) if channels[chan])
            self.liststore.insert(i + 1, [str(mem), "", nb_chan])

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

            return True

        # Insert memory with the given number
        mem = float(self.keystring)

        # Memory already exist ?
        for item in App().memories:
            if item.memory == mem:
                return False

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            sequence = App().memories[row].sequence
            # memory = App().memories[row].memory
            channels = App().memories[row].channels
            # text = App().memories[row].text
        else:
            sequence = 0
            channels = array.array("B", [0] * MAX_CHANNELS)

        # Find Memory's position
        found = False
        i = 0
        for i, _ in enumerate(App().memories):
            if App().memories[i].memory > mem:
                found = True
                break
        if not found:
            # Memory is at the end
            i += 1

        # Create Memory
        cue = Cue(sequence, mem, channels)
        App().memories.insert(i, cue)

        # Update display
        nb_chan = sum(bool(channels[chan]) for chan in range(MAX_CHANNELS))
        self.liststore.insert(i, [str(mem), "", nb_chan])

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

        return True


class CueChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self):
        super().__init__()

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        if not App().memories or not App().memories_tab:
            return False
        # Find selected row
        path, _focus_column = App().memories_tab.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            if self.view_mode == VIEW_MODES["Active"]:
                return self.__filter_active(row, child)
            if self.view_mode == VIEW_MODES["Patched"]:
                return self.__filter_patched(row, child)
            return self.__filter_all(row, child)
        child.set_visible(False)
        return False

    def __filter_active(self, row, child: Gtk.FlowBoxChild) -> bool:
        user_channels = App().memories_tab.user_channels
        channel_index = child.get_index()
        channel_widget = child.get_child()
        # Channels in Cue
        channels = App().memories[row].channels
        if channels[channel_index] or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels[channel_index]
                channel_widget.next_level = channels[channel_index]
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            return True
        if user_channels[channel_index] == -1:
            channel_widget.level = 0
            channel_widget.next_level = 0
            return False
        channel_widget.level = user_channels[channel_index]
        channel_widget.next_level = user_channels[channel_index]
        return True

    def __filter_patched(self, row, child: Gtk.FlowBoxChild) -> bool:
        user_channels = App().memories_tab.user_channels
        channel_index = child.get_index()
        if channel_index + 1 in App().patch.channels:
            channel_widget = child.get_child()
            # Channels in Cue
            channels = App().memories[row].channels
            if channels[channel_index] or child.is_selected():
                if user_channels[channel_index] == -1:
                    channel_widget.level = channels[channel_index]
                    channel_widget.next_level = channels[channel_index]
                else:
                    channel_widget.level = user_channels[channel_index]
                    channel_widget.next_level = user_channels[channel_index]
                return True
            if user_channels[channel_index] == -1:
                channel_widget.level = 0
                channel_widget.next_level = 0
                return True
            channel_widget.level = user_channels[channel_index]
            channel_widget.next_level = user_channels[channel_index]
            return True
        return False

    def __filter_all(self, row, child: Gtk.FlowBoxChild) -> bool:
        user_channels = App().memories_tab.user_channels
        channel_index = child.get_index()
        channel_widget = child.get_child()
        # Channels in Cue
        channels = App().memories[row].channels
        if channels[channel_index] or child.is_selected():
            if user_channels[channel_index] == -1:
                channel_widget.level = channels[channel_index]
                channel_widget.next_level = channels[channel_index]
            else:
                channel_widget.level = user_channels[channel_index]
                channel_widget.next_level = user_channels[channel_index]
            return True
        if user_channels[channel_index] == -1:
            channel_widget.level = 0
            channel_widget.next_level = 0
            return True
        channel_widget.level = user_channels[channel_index]
        channel_widget.next_level = user_channels[channel_index]
        return True
