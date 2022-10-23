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
from olc.define import MAX_CHANNELS, App
from olc.sequence import Sequence
from olc.step import Step
from olc.widgets_channel import ChannelWidget
from olc.zoom import zoom


class SequenceTab(Gtk.Grid):
    """Tab to edit sequences"""

    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""

        # To stock user modification on channels
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)

        # List of Sequences
        self.liststore1 = Gtk.ListStore(int, str, str)

        self.liststore1.append(
            [App().sequence.index, App().sequence.type_seq, App().sequence.text]
        )

        for chaser in App().chasers:
            self.liststore1.append([chaser.index, chaser.type_seq, chaser.text])

        self.treeview1 = Gtk.TreeView(model=self.liststore1)
        self.treeview1.set_enable_search(False)
        self.treeview1.connect("focus-in-event", self.on_focus)
        selection = self.treeview1.get_selection()
        selection.connect("changed", self.on_sequence_changed)

        for i, column_title in enumerate(["Seq", "Type", "Name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview1.append_column(column)

        self.attach(self.treeview1, 0, 0, 1, 1)

        # We put channels and memories list in a paned
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Channels in the selected cue
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
        self.paned.add1(self.scrolled)

        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)

        # Selected Sequence
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            selected = path.get_indices()[0]

            # Find it
            for i, item in enumerate(self.liststore1):
                if i == selected:
                    if item[0] == App().sequence.index:
                        self.seq = App().sequence
                    else:
                        for chaser in App().chasers:
                            if item[0] == chaser.index:
                                self.seq = chaser
            # Liststore with infos from the sequence
            for i in range(self.seq.last)[1:-1]:
                self.add_step_to_liststore(i)

        self.treeview2 = Gtk.TreeView(model=self.liststore2)
        self.treeview2.set_enable_search(False)
        self.treeview2.connect("cursor-changed", self.on_memory_changed)
        self.treeview2.connect("row-activated", self.on_row_activated)
        self.treeview2.connect("focus-in-event", self.on_focus)

        # Display selected sequence
        for i, column_title in enumerate(
            [
                "Step",
                "Cue",
                "Text",
                "Wait",
                "Delay Out",
                "Out",
                "Delay In",
                "In",
                "Channel Time",
            ]
        ):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            if i == 2:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.text_edited)

            elif i == 3:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.wait_edited)
            elif i == 4:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.delay_out_edited)
            elif i == 5:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.out_edited)
            elif i == 6:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.delay_in_edited)
            elif i == 7:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.in_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)

            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)

            self.treeview2.append_column(column)

        # Put Cues List in a scrolled window
        self.scrollable2 = Gtk.ScrolledWindow()
        self.scrollable2.set_vexpand(True)
        self.scrollable2.set_hexpand(True)
        self.scrollable2.add(self.treeview2)

        self.paned.add2(self.scrollable2)

        self.attach_next_to(self.paned, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1)

        self.flowbox.set_filter_func(self.filter_func, None)
        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", zoom)

        # Select Main Playback
        path = Gtk.TreePath.new_first()
        self.treeview1.set_cursor(path, None, False)

    def on_focus(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Give focus to notebook

        Returns:
            False
        """
        notebook = self.get_parent()
        if notebook:
            notebook.grab_focus()
        return False

    def on_row_activated(self, _treeview, path, column):
        """Open Channel Time Edition if double clicked

        Args:
            path: Gtk.TreePath
            column: Column number
        """
        # Find double clicked cell
        columns = self.treeview2.get_columns()
        col_nb = 0
        for col_nb, col in enumerate(columns):
            if col == column:
                break
        # Double click on Channel Time
        if col_nb == 8:

            # Find selected sequence
            seq_path, _focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        seq = chaser

            # Edit Channel Time
            step = self.liststore2[path][0]
            App().channeltime(seq, step)

    def wait_edited(self, _widget, path, text):
        """Edit Wait

        Args:
            path: Gtk.TreePath
            text: string
        """
        if text == "":
            text = "0"

        if text.replace(".", "", 1).isdigit():

            if text[0] == ".":
                text = "0" + text

            self.liststore2[path][3] = "" if text == "0" else text
            # Find selected sequence
            seq_path, _focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Wait value
            self.seq.steps[step].wait = float(text)
            # Update Total Time
            if (self.seq.steps[step].time_in + self.seq.steps[step].delay_in) > (
                self.seq.steps[step].time_out + self.seq.steps[step].delay_out
            ):
                self.seq.steps[step].total_time = (
                    self.seq.steps[step].time_in
                    + self.seq.steps[step].wait
                    + self.seq.steps[step].delay_in
                )
            else:
                self.seq.steps[step].total_time = (
                    self.seq.steps[step].time_out
                    + self.seq.steps[step].wait
                    + self.seq.steps[step].delay_out
                )
            for channel in self.seq.steps[step].channel_time.keys():
                t = (
                    self.seq.steps[step].channel_time[channel].delay
                    + self.seq.steps[step].channel_time[channel].time
                    + self.seq.steps[step].wait
                )
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

            # Update Sequential Tab
            if self.seq == App().sequence:
                path = str(int(path) + 1)
                if text == "0":
                    App().window.playback.cues_liststore1[path][3] = ""
                    App().window.playback.cues_liststore2[path][3] = ""
                else:
                    App().window.playback.cues_liststore1[path][3] = text
                    App().window.playback.cues_liststore2[path][3] = text
                if App().sequence.position + 1 == step:
                    App().window.playback.sequential.wait = float(text)
                    App().window.playback.sequential.total_time = self.seq.steps[
                        step
                    ].total_time
                    App().window.playback.sequential.queue_draw()

    def out_edited(self, _widget, path, text):
        """Time Out edited

        Args:
            path: Gtk.TreePath
            text: string
        """
        if not text.replace(".", "", 1).isdigit():

            return
        if text[0] == ".":
            text = "0" + text

        self.liststore2[path][5] = text

        # Find selected sequence
        seq_path, _focus_column = self.treeview1.get_cursor()
        selected = seq_path.get_indices()[0]
        sequence = self.liststore1[selected][0]
        if sequence == App().sequence.index:
            self.seq = App().sequence
        else:
            for chaser in App().chasers:
                if sequence == chaser.index:
                    self.seq = chaser
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update Time Out value
        self.seq.steps[step].time_out = float(text)
        # Update Total Time
        if (
            self.seq.steps[step].time_in + self.seq.steps[step].delay_in
            > self.seq.steps[step].time_out + self.seq.steps[step].delay_out
        ):
            self.seq.steps[step].total_time = (
                self.seq.steps[step].time_in
                + self.seq.steps[step].wait
                + self.seq.steps[step].delay_in
            )
        else:
            self.seq.steps[step].total_time = (
                self.seq.steps[step].time_out
                + self.seq.steps[step].wait
                + self.seq.steps[step].delay_out
            )
        for channel in self.seq.steps[step].channel_time.keys():
            t = (
                self.seq.steps[step].channel_time[channel].delay
                + self.seq.steps[step].channel_time[channel].time
                + self.seq.steps[step].wait
            )
            if t > self.seq.steps[step].total_time:
                self.seq.steps[step].total_time = t

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        # Update Sequential Tab
        if self.seq == App().sequence:
            path = str(int(path) + 1)
            App().window.playback.cues_liststore1[path][5] = text
            App().window.playback.cues_liststore2[path][5] = text
            if App().sequence.position + 1 == step:
                App().window.playback.sequential.time_out = float(text)
                App().window.playback.sequential.total_time = self.seq.steps[
                    step
                ].total_time
                App().window.playback.sequential.queue_draw()

    def in_edited(self, _widget, path, text):
        """Time in edited

        Args:
            path: Gtk.TreePath
            text: string
        """
        if not text.replace(".", "", 1).isdigit():

            return
        if text[0] == ".":
            text = "0" + text

        self.liststore2[path][7] = text

        # Find selected sequence
        seq_path, _focus_column = self.treeview1.get_cursor()
        selected = seq_path.get_indices()[0]
        sequence = self.liststore1[selected][0]
        if sequence == App().sequence.index:
            self.seq = App().sequence
        else:
            for chaser in App().chasers:
                if sequence == chaser.index:
                    self.seq = chaser
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update Time In value
        self.seq.steps[step].time_in = float(text)
        # Update Total Time
        if (
            self.seq.steps[step].time_in + self.seq.steps[step].delay_in
            > self.seq.steps[step].time_out + self.seq.steps[step].delay_out
        ):
            self.seq.steps[step].total_time = (
                self.seq.steps[step].time_in
                + self.seq.steps[step].wait
                + self.seq.steps[step].delay_in
            )
        else:
            self.seq.steps[step].total_time = (
                self.seq.steps[step].time_out
                + self.seq.steps[step].wait
                + self.seq.steps[step].delay_out
            )
        for channel in self.seq.steps[step].channel_time.keys():
            t = (
                self.seq.steps[step].channel_time[channel].delay
                + self.seq.steps[step].channel_time[channel].time
                + self.seq.steps[step].wait
            )
            if t > self.seq.steps[step].total_time:
                self.seq.steps[step].total_time = t

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        # Update Sequential Tab
        if self.seq == App().sequence:
            path = str(int(path) + 1)
            App().window.playback.cues_liststore1[path][7] = text
            App().window.playback.cues_liststore2[path][7] = text
            if App().sequence.position + 1 == step:
                App().window.playback.sequential.time_in = float(text)
                App().window.playback.sequential.total_time = self.seq.steps[
                    step
                ].total_time
                App().window.playback.sequential.queue_draw()

    def delay_out_edited(self, _widget, path, text):
        """Delay Out edited

        Args:
            path: Gtk.TreePath
            text: string
        """
        if text == "":
            text = "0"

        if text.replace(".", "", 1).isdigit():

            if text[0] == ".":
                text = "0" + text

            self.liststore2[path][4] = "" if text == "0" else text
            # Find selected sequence
            seq_path, _focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            self.seq.steps[step].delay_out = float(text)
            # Update Total Time
            if (
                self.seq.steps[step].time_in + self.seq.steps[step].delay_in
                > self.seq.steps[step].time_out + self.seq.steps[step].delay_out
            ):
                self.seq.steps[step].total_time = (
                    self.seq.steps[step].time_in
                    + self.seq.steps[step].wait
                    + self.seq.steps[step].delay_in
                )
            else:
                self.seq.steps[step].total_time = (
                    self.seq.steps[step].time_out
                    + self.seq.steps[step].wait
                    + self.seq.steps[step].delay_out
                )
            for channel in self.seq.steps[step].channel_time.keys():
                t = (
                    self.seq.steps[step].channel_time[channel].delay
                    + self.seq.steps[step].channel_time[channel].time
                    + self.seq.steps[step].wait
                )
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

            # Update Sequential Tab
            if self.seq == App().sequence:
                path = str(int(path) + 1)
                if text == "0":
                    App().window.playback.cues_liststore1[path][4] = ""
                    App().window.playback.cues_liststore2[path][4] = ""
                else:
                    App().window.playback.cues_liststore1[path][4] = text
                    App().window.playback.cues_liststore2[path][4] = text
                if App().sequence.position + 1 == step:
                    App().window.playback.sequential.delay_out = float(text)
                    App().window.playback.sequential.total_time = self.seq.steps[
                        step
                    ].total_time
                    App().window.playback.sequential.queue_draw()

    def delay_in_edited(self, _widget, path, text):
        """Delay In edited

        Args:
            path: Gtk.TreePath
            text: string
        """
        if text == "":
            text = "0"

        if text.replace(".", "", 1).isdigit():

            if text[0] == ".":
                text = "0" + text

            self.liststore2[path][6] = "" if text == "0" else text
            # Find selected sequence
            seq_path, _focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            self.seq.steps[step].delay_in = float(text)
            # Update Total Time
            if (
                self.seq.steps[step].time_in + self.seq.steps[step].delay_in
                > self.seq.steps[step].time_out + self.seq.steps[step].delay_out
            ):
                self.seq.steps[step].total_time = (
                    self.seq.steps[step].time_in
                    + self.seq.steps[step].wait
                    + self.seq.steps[step].delay_in
                )
            else:
                self.seq.steps[step].total_time = (
                    self.seq.steps[step].time_out
                    + self.seq.steps[step].wait
                    + self.seq.steps[step].delay_out
                )
            for channel in self.seq.steps[step].channel_time.keys():
                t = (
                    self.seq.steps[step].channel_time[channel].delay
                    + self.seq.steps[step].channel_time[channel].time
                    + self.seq.steps[step].wait
                )
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

            # Update Sequential Tab
            if self.seq == App().sequence:
                path = str(int(path) + 1)
                if text == "0":
                    App().window.playback.cues_liststore1[path][6] = ""
                    App().window.playback.cues_liststore2[path][6] = ""
                else:
                    App().window.playback.cues_liststore1[path][6] = text
                    App().window.playback.cues_liststore2[path][6] = text
                if App().sequence.position + 1 == step:
                    App().window.playback.sequential.delay_in = float(text)
                    App().window.playback.sequential.total_time = self.seq.steps[
                        step
                    ].total_time
                    App().window.playback.sequential.queue_draw()

    def text_edited(self, _widget, path, text):
        """Step's Text edited

        Args:
            path: Gtk.TreePath
            text: string
        """
        self.liststore2[path][2] = text

        # Find selected sequence
        seq_path, _focus_column = self.treeview1.get_cursor()
        selected = seq_path.get_indices()[0]
        sequence = self.liststore1[selected][0]
        if sequence == App().sequence.index:
            self.seq = App().sequence
        else:
            for chaser in App().chasers:
                if sequence == chaser.index:
                    self.seq = chaser
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update text value
        self.seq.steps[step].text = text

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        # Update Main Playback
        if self.seq == App().sequence:
            path = str(int(path) + 1)
            App().window.playback.cues_liststore1[path][2] = text
            App().window.playback.cues_liststore2[path][2] = text

            # Update window's subtitle if needed
            if App().sequence.position == step:
                subtitle = (
                    "Mem. : "
                    + str(self.seq.steps[step].cue.memory)
                    + " "
                    + self.seq.steps[step].text
                    + " - Next Mem. : "
                    + str(self.seq.steps[step + 1].cue.memory)
                    + " "
                    + self.seq.steps[step + 1].text
                )
                App().window.header.set_subtitle(subtitle)

            if App().sequence.position + 1 == step:
                subtitle = (
                    "Mem. : "
                    + str(self.seq.steps[step - 1].cue.memory)
                    + " "
                    + self.seq.steps[step - 1].text
                    + " - Next Mem. : "
                    + str(self.seq.steps[step].cue.memory)
                    + " "
                    + self.seq.steps[step].text
                )
                App().window.header.set_subtitle(subtitle)

    def on_memory_changed(self, _treeview):
        """Select cue"""
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def filter_func(self, child, _user_data):
        """Filter channels

        Args:
            child: Child object


        Returns:
            child or False
        """
        # Find selected sequence
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
        # Find Step
        i = child.get_index()
        selection = self.treeview2.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            step = int(model[treeiter][0])
            # Display channels in step
            channels = self.seq.steps[step].cue.channels

            if channels[i] != 0 or self.channels[i].clicked:
                if self.user_channels[i] == -1:
                    self.channels[i].level = channels[i]
                    self.channels[i].next_level = channels[i]
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                return child
            if self.user_channels[i] == -1:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False
            self.channels[i].level = self.user_channels[i]
            self.channels[i].next_level = self.user_channels[i]
            return child

        if self.user_channels[i] != -1 or self.channels[i].clicked:
            if self.user_channels[i] == -1:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
            else:
                self.channels[i].level = self.user_channels[i]
                self.channels[i].next_level = self.user_channels[i]
            return child

        return False

    def on_sequence_changed(self, selection):
        """Select Sequence

        Args:
            selection: Object selected
        """
        # Empty ListStore
        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)

        # Find Sequence selected
        model, treeiter = selection.get_selected()
        if treeiter:
            selected = model[treeiter][0]
            # Find it
            for i, item in enumerate(self.liststore1):
                if i + 1 == selected:
                    if item[0] == App().sequence.index:
                        self.seq = App().sequence
                    else:
                        for chaser in App().chasers:
                            if item[0] == chaser.index:
                                self.seq = chaser
            # Display Sequence
            self.populate_liststore(1)

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().sequences_tab = None

    def on_key_press_event(self, _widget, event):
        """Receive keyboard event

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

        if func := getattr(self, "_keypress_" + keyname, None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().sequences_tab = None

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        """Empty keys buffer"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Q(self):  # pylint: disable=C0103
        """Cycle Sequences"""
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            path.next()
        else:
            path = Gtk.TreePath.new_first()
        self.treeview1.set_cursor(path)
        path = Gtk.TreePath.new_first()
        self.treeview2.set_cursor(path)
        # Reset user modifications
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        self.get_parent().grab_focus()

    def _keypress_q(self):
        """Prev Cue"""
        # Reset user modifications
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        path, _focus_column = self.treeview2.get_cursor()
        if path:
            if path.prev():
                self.treeview2.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)
        self.get_parent().grab_focus()

    def _keypress_w(self):
        """Next Cue"""
        # Reset user modifications
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        path, _focus_column = self.treeview2.get_cursor()
        if path:
            path.next()
        else:
            path = Gtk.TreePath.new_first()

        self.treeview2.set_cursor(path)
        self.get_parent().grab_focus()

    def _keypress_a(self):
        """All Channels"""
        self.flowbox.unselect_all()

        # Find selected sequence
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
            # Find Step
            path, _focus_column = self.treeview2.get_cursor()
        if path:
            selected = path.get_indices()[0]
            step = int(self.liststore2[selected][0])
            channels = self.seq.steps[step].cue.channels

            for channel in range(MAX_CHANNELS):
                if channels[channel] != 0:
                    self.channels[channel].clicked = True
                    child = self.flowbox.get_child_at_index(channel)
                    self.flowbox.select_child(child)
                else:
                    self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

        self.get_parent().grab_focus()

    def _keypress_c(self):
        """Channel"""
        self.flowbox.unselect_all()
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False

        if self.keystring not in ["", "0"]:
            channel = int(self.keystring)
            # Only patched channels
            if channel in App().patch.channels:
                self.channels[channel - 1].clicked = True
                child = self.flowbox.get_child_at_index(channel - 1)
                self.flowbox.select_child(child)
                self.last_chan_selected = self.keystring
        self.flowbox.invalidate_filter()

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):  # pylint: disable=C0103
        """Channel Thru"""
        self._keypress_greater()

    def _keypress_greater(self):
        """Channel Thru"""
        sel = self.flowbox.get_selected_children()
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
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):
                    # Only patched channels
                    if channel + 1 in App().patch.channels:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.flowbox.select_child(child)
            self.flowbox.invalidate_filter()

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_plus(self):
        """Channel +"""
        if self.keystring == "":
            return

        channel = int(self.keystring)
        if channel in App().patch.channels:
            self.channels[channel - 1].clicked = True
            self.flowbox.invalidate_filter()
            child = self.flowbox.get_child_at_index(channel - 1)
            self.flowbox.select_child(child)
            self.last_chan_selected = self.keystring

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_minus(self):
        """Channel -"""
        if self.keystring == "":
            return

        channel = int(self.keystring)
        if channel in App().patch.channels:
            self.channels[channel - 1].clicked = False
            self.flowbox.invalidate_filter()
            child = self.flowbox.get_child_at_index(channel - 1)
            self.flowbox.unselect_child(child)
            self.last_chan_selected = self.keystring

        self.get_parent().grab_focus()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self):
        """@ Level"""
        level = int(self.keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
        if 0 <= level <= 255:
            sel = self.flowbox.get_selected_children()

            for flowboxchild in sel:
                children = flowboxchild.get_children()

                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1

                    if level != -1:
                        self.channels[channel].level = level
                        self.channels[channel].next_level = level
                        self.channels[channel].queue_draw()
                        self.user_channels[channel] = level

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Level - %"""
        lvl = App().settings.get_int("percent-level")

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
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

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                level = min(level + lvl, 255)
                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def _keypress_U(self):  # pylint: disable=C0103
        """Update Cue"""
        # Find selected sequence
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
            # Find Step
            path, _focus_column = self.treeview2.get_cursor()
        if path:
            selected = path.get_indices()[0]
            step = int(self.liststore2[selected][0])
            channels = self.seq.steps[step].cue.channels

            memory = self.seq.steps[step].cue.memory

            # Dialog to confirm Update
            dialog = Dialog(App().window, memory)
            response = dialog.run()

            if response == Gtk.ResponseType.OK:
                # Update levels in the cue
                for channel in range(MAX_CHANNELS):
                    channels[channel] = self.channels[channel].level
                    if channels[channel] != 0:
                        self.seq.channels[channel] = 1

                # Tag filename as modified
                App().ascii.modified = True
                App().window.header.set_title(App().ascii.basename + "*")

                # Update Main playback display
                if self.seq == App().sequence and step == App().sequence.position + 1:
                    for channel in range(MAX_CHANNELS):
                        widget = (
                            App()
                            .window.channels_view.flowbox.get_child_at_index(channel)
                            .get_children()[0]
                        )
                        widget.next_level = self.seq.steps[step].cue.channels[channel]
                        widget.queue_draw()

            dialog.destroy()

            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

    def _keypress_Delete(self):  # pylint: disable=C0103
        """Delete selected Step"""
        # Find selected sequence
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == App().sequence.index:
                self.seq = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence == chaser.index:
                        self.seq = chaser
            # Find Step
            path, _focus_column = self.treeview2.get_cursor()
        if path:
            selected = path.get_indices()[0]
            step = int(self.liststore2[selected][0])
            # cue = self.seq.steps[step].cue.memory
            self.seq.steps.pop(step)
            self.seq.last -= 1
            self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)
            self.populate_liststore(step)
            # Update Main Playback
            App().window.playback.update_sequence_display()

    def _keypress_N(self):  # pylint: disable=C0103
        """New Chaser"""
        # Use the next free index
        # 1 is for Main Playback, Chasers start at 2
        index_seq = App().chasers[-1].index + 1 if len(App().chasers) > 0 else 2
        # Create Chaser
        App().chasers.append(Sequence(index_seq, type_seq="Chaser"))
        del App().chasers[-1].steps[1:]
        App().chasers[-1].last = len(App().chasers[-1].steps)

        # Update List of sequences
        self.liststore1.append(
            [
                App().chasers[-1].index,
                App().chasers[-1].type_seq,
                App().chasers[-1].text,
            ]
        )

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

    def _keypress_R(self):  # pylint: disable=C0103
        """New Step and new Cue"""
        found = False

        if self.keystring == "":
            # Find selected Step
            path, _focus_column = self.treeview2.get_cursor()
            if path:
                selected = path.get_indices()[0]
                step = int(self.liststore2[selected][0])
                # New Cue number
                mem = self.seq.get_next_cue(step=step)
                # New Step
                step += 1
            else:
                mem = 1.0
                step = 1
        else:
            # Cue number given by user
            mem = float(self.keystring)
            found, step = self.seq.get_step(cue=mem)
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

        if not found:  # New Cue
            # Create Cue
            channels = array.array("B", [0] * MAX_CHANNELS)
            for channel in range(MAX_CHANNELS):
                channels[channel] = self.channels[channel].level
            cue = Cue(self.seq.index, mem, channels)
            # Create Step
            step_object = Step(self.seq.index, cue=cue)
            self.seq.insert_step(step, step_object)
            # If we modify Main Sequence
            if self.seq is App().sequence:
                App().memories.insert(step, cue)
                # Update Preset Tab if exist
                if App().memories_tab:
                    nb_chan = sum(1 for chan in range(MAX_CHANNELS) if channels[chan])
                    App().memories_tab.liststore.insert(
                        step - 1, [str(mem), "", nb_chan]
                    )
            # Update Display
            self.update_sequence_display(step)
            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")
            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        else:  # Update Cue
            dialog = Dialog(App().window, str(mem))
            response = dialog.run()

            if response == Gtk.ResponseType.OK:
                # Find Preset's position
                found, step = self.seq.get_step(cue=mem)
                # Update Cue
                channels = array.array("B", [0] * MAX_CHANNELS)
                for channel in range(MAX_CHANNELS):
                    self.seq.steps[step].cue.channels[channel] = self.channels[
                        channel
                    ].level
                    if self.channels[channel].level:
                        self.seq.channels[channel] = 1

                # Tag filename as modified
                App().ascii.modified = True
                App().window.header.set_title(App().ascii.basename + "*")

                # Select memory modified
                path = Gtk.TreePath.new_from_indices([step - 1])
                self.treeview2.set_cursor(path, None, False)

                # Update Presets Tab if exist
                if self.seq is App().sequence and App().memories_tab:
                    nb_chan = sum(
                        1
                        for chan in range(MAX_CHANNELS)
                        if App().memories[step - 1].channels[chan]
                    )

                    treeiter = App().memories_tab.liststore.get_iter(step - 1)
                    App().memories_tab.liststore.set_value(treeiter, 2, nb_chan)
                    App().memories_tab.flowbox.invalidate_filter()

                # Update Channels tab
                if self.seq is App().sequence and step == App().sequence.position + 1:
                    for channel in range(MAX_CHANNELS):
                        widget = (
                            App()
                            .window.channels_view.flowbox.get_child_at_index(channel)
                            .get_children()[0]
                        )
                        widget.next_level = self.channels[channel].level
                        widget.queue_draw()

            dialog.destroy()

    def add_step_to_liststore(self, step):
        """Add Step to the list

        Args:
            step: Step
        """
        wait = (
            str(int(self.seq.steps[step].wait))
            if self.seq.steps[step].wait.is_integer()
            else str(self.seq.steps[step].wait)
        )
        if wait == "0":
            wait = ""
        t_out = (
            str(int(self.seq.steps[step].time_out))
            if self.seq.steps[step].time_out.is_integer()
            else str(self.seq.steps[step].time_out)
        )
        d_out = (
            str(int(self.seq.steps[step].delay_out))
            if self.seq.steps[step].delay_out.is_integer()
            else str(self.seq.steps[step].delay_out)
        )
        if d_out == "0":
            d_out = ""
        t_in = (
            str(int(self.seq.steps[step].time_in))
            if self.seq.steps[step].time_in.is_integer()
            else str(self.seq.steps[step].time_in)
        )
        d_in = (
            str(int(self.seq.steps[step].delay_in))
            if self.seq.steps[step].delay_in.is_integer()
            else str(self.seq.steps[step].delay_in)
        )
        if d_in == "0":
            d_in = ""
        channel_time = str(len(self.seq.steps[step].channel_time))
        if channel_time == "0":
            channel_time = ""
        self.liststore2.insert(
            step - 1,
            [
                str(step),
                str(self.seq.steps[step].cue.memory),
                self.seq.steps[step].text,
                wait,
                d_out,
                t_out,
                d_in,
                t_in,
                channel_time,
            ],
        )

    def populate_liststore(self, step):
        """Populate liststore with steps

        Args:
            step: Step
        """
        # Liststore with infos from the sequence
        if self.seq == App().sequence:
            for i in range(self.seq.last)[1:-1]:
                self.add_step_to_liststore(i)
        else:
            for i in range(self.seq.last)[1:]:
                self.add_step_to_liststore(i)

        self.treeview2.set_model(self.liststore2)
        # Select new step
        path = Gtk.TreePath.new_from_indices([step - 1])
        self.treeview2.set_cursor(path, None, False)

    def update_sequence_display(self, step):
        """Update Sequence display

        Args:
            step: Step
        """
        self.add_step_to_liststore(step)
        # Update Main Playback
        if self.seq is App().sequence:
            # Update indexes of cues in listsore
            for i in range(step, self.seq.last - 2):
                self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)
            # Update Main Tab
            App().window.playback.update_sequence_display()
            if App().sequence.position + 1 == step:
                # Update Crossfade
                App().window.playback.update_xfade_display(step - 1)
                # Update Channels Tab
                App().window.update_channels_display(step - 1)
        # Update Chasers
        else:
            # Update indexes of cues in listsore
            for i in range(step, self.seq.last - 1):
                self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)
        # Select new step
        path = Gtk.TreePath.new_from_indices([step - 1])
        self.treeview2.set_cursor(path, None, False)


class Dialog(Gtk.Dialog):
    """Confirmation dialog"""

    def __init__(self, parent, memory):
        Gtk.Dialog.__init__(
            self,
            "Confirmation",
            parent,
            0,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK,
                Gtk.ResponseType.OK,
            ),
        )

        self.set_default_size(150, 100)

        label = Gtk.Label("Update memory " + str(memory) + " ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()
