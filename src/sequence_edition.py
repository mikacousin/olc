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
from typing import Optional

from gi.repository import Gdk, Gtk
from olc.cue import Cue
from olc.define import MAX_CHANNELS, App
from olc.sequence import Sequence
from olc.step import Step
from olc.widgets.channels_view import ChannelsView, VIEW_MODES


class SequenceTab(Gtk.Grid):
    """Tab to edit sequences"""

    def __init__(self):

        self.keystring = ""

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
        self.channels_view = SeqChannelsView()
        self.paned.add1(self.channels_view)

        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)
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

    def refresh(self) -> None:
        """Refresh display"""
        self.liststore1.clear()
        self.liststore1.append(
            [App().sequence.index, App().sequence.type_seq, App().sequence.text]
        )
        for chaser in App().chasers:
            self.liststore1.append([chaser.index, chaser.type_seq, chaser.text])
        self.treeview1.set_model(self.liststore1)
        path = Gtk.TreePath.new_first()
        self.treeview1.set_cursor(path, None, False)
        self.on_sequence_changed()

    def get_selected_sequence(self) -> Optional[Sequence]:
        """Get selected sequence

        Returns:
            Selected sequence or None
        """
        sequence = None
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            row = path.get_indices()[0]
            sequence_number = self.liststore1[row][0]
            if sequence_number == App().sequence.index:
                sequence = App().sequence
            else:
                for chaser in App().chasers:
                    if sequence_number == chaser.index:
                        sequence = chaser
        return sequence

    def get_selected_step(self) -> Optional[int]:
        """Get selected step

        Returns:
            Selected step or None
        """
        tree_selection = self.treeview2.get_selection()
        model, treeiter = tree_selection.get_selected()
        return int(model[treeiter][0]) if treeiter else None

    def on_focus(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Give focus to notebook

        Returns:
            False
        """
        if notebook := self.get_parent():
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
            sequence = self.get_selected_sequence()
            step = self.liststore2[path][0]
            if sequence and step:
                App().channeltime(sequence, step)

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
                text = f"0{text}"

            self.liststore2[path][3] = "" if text == "0" else text
            sequence = self.get_selected_sequence()
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Wait value
            sequence.steps[step].wait = float(text)
            # Update Total Time
            if (sequence.steps[step].time_in + sequence.steps[step].delay_in) > (
                sequence.steps[step].time_out + sequence.steps[step].delay_out
            ):
                sequence.steps[step].total_time = (
                    sequence.steps[step].time_in
                    + sequence.steps[step].wait
                    + sequence.steps[step].delay_in
                )
            else:
                sequence.steps[step].total_time = (
                    sequence.steps[step].time_out
                    + sequence.steps[step].wait
                    + sequence.steps[step].delay_out
                )
            for channel in sequence.steps[step].channel_time.keys():
                t = (
                    sequence.steps[step].channel_time[channel].delay
                    + sequence.steps[step].channel_time[channel].time
                    + sequence.steps[step].wait
                )
                if t > sequence.steps[step].total_time:
                    sequence.steps[step].total_time = t

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(f"{App().ascii.basename}*")

            # Update Sequential Tab
            if sequence == App().sequence:
                path = str(int(path) + 1)
                if text == "0":
                    App().window.playback.cues_liststore1[path][3] = ""
                    App().window.playback.cues_liststore2[path][3] = ""
                else:
                    App().window.playback.cues_liststore1[path][3] = text
                    App().window.playback.cues_liststore2[path][3] = text
                if App().sequence.position + 1 == step:
                    App().window.playback.sequential.wait = float(text)
                    App().window.playback.sequential.total_time = sequence.steps[
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
            text = f"0{text}"

        self.liststore2[path][5] = text

        # Find selected sequence
        sequence = self.get_selected_sequence()
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update Time Out value
        sequence.steps[step].time_out = float(text)
        # Update Total Time
        if (
            sequence.steps[step].time_in + sequence.steps[step].delay_in
            > sequence.steps[step].time_out + sequence.steps[step].delay_out
        ):
            sequence.steps[step].total_time = (
                sequence.steps[step].time_in
                + sequence.steps[step].wait
                + sequence.steps[step].delay_in
            )
        else:
            sequence.steps[step].total_time = (
                sequence.steps[step].time_out
                + sequence.steps[step].wait
                + sequence.steps[step].delay_out
            )
        for channel in sequence.steps[step].channel_time.keys():
            t = (
                sequence.steps[step].channel_time[channel].delay
                + sequence.steps[step].channel_time[channel].time
                + sequence.steps[step].wait
            )
            if t > sequence.steps[step].total_time:
                sequence.steps[step].total_time = t

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(f"{App().ascii.basename}*")

        # Update Sequential Tab
        if sequence == App().sequence:
            path = str(int(path) + 1)
            App().window.playback.cues_liststore1[path][5] = text
            App().window.playback.cues_liststore2[path][5] = text
            if App().sequence.position + 1 == step:
                App().window.playback.sequential.time_out = float(text)
                App().window.playback.sequential.total_time = sequence.steps[
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
            text = f"0{text}"

        self.liststore2[path][7] = text

        # Find selected sequence
        sequence = self.get_selected_sequence()
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update Time In value
        sequence.steps[step].time_in = float(text)
        # Update Total Time
        if (
            sequence.steps[step].time_in + sequence.steps[step].delay_in
            > sequence.steps[step].time_out + sequence.steps[step].delay_out
        ):
            sequence.steps[step].total_time = (
                sequence.steps[step].time_in
                + sequence.steps[step].wait
                + sequence.steps[step].delay_in
            )
        else:
            sequence.steps[step].total_time = (
                sequence.steps[step].time_out
                + sequence.steps[step].wait
                + sequence.steps[step].delay_out
            )
        for channel in sequence.steps[step].channel_time.keys():
            t = (
                sequence.steps[step].channel_time[channel].delay
                + sequence.steps[step].channel_time[channel].time
                + sequence.steps[step].wait
            )
            if t > sequence.steps[step].total_time:
                sequence.steps[step].total_time = t

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(f"{App().ascii.basename}*")

        # Update Sequential Tab
        if sequence == App().sequence:
            path = str(int(path) + 1)
            App().window.playback.cues_liststore1[path][7] = text
            App().window.playback.cues_liststore2[path][7] = text
            if App().sequence.position + 1 == step:
                App().window.playback.sequential.time_in = float(text)
                App().window.playback.sequential.total_time = sequence.steps[
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
                text = f"0{text}"

            self.liststore2[path][4] = "" if text == "0" else text
            # Find selected sequence
            sequence = self.get_selected_sequence()
            # Find Step
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            sequence.steps[step].delay_out = float(text)
            # Update Total Time
            if (
                sequence.steps[step].time_in + sequence.steps[step].delay_in
                > sequence.steps[step].time_out + sequence.steps[step].delay_out
            ):
                sequence.steps[step].total_time = (
                    sequence.steps[step].time_in
                    + sequence.steps[step].wait
                    + sequence.steps[step].delay_in
                )
            else:
                sequence.steps[step].total_time = (
                    sequence.steps[step].time_out
                    + sequence.steps[step].wait
                    + sequence.steps[step].delay_out
                )
            for channel in sequence.steps[step].channel_time.keys():
                t = (
                    sequence.steps[step].channel_time[channel].delay
                    + sequence.steps[step].channel_time[channel].time
                    + sequence.steps[step].wait
                )
                if t > sequence.steps[step].total_time:
                    sequence.steps[step].total_time = t

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(f"{App().ascii.basename}*")

            # Update Sequential Tab
            if sequence == App().sequence:
                path = str(int(path) + 1)
                if text == "0":
                    App().window.playback.cues_liststore1[path][4] = ""
                    App().window.playback.cues_liststore2[path][4] = ""
                else:
                    App().window.playback.cues_liststore1[path][4] = text
                    App().window.playback.cues_liststore2[path][4] = text
                if App().sequence.position + 1 == step:
                    App().window.playback.sequential.delay_out = float(text)
                    App().window.playback.sequential.total_time = sequence.steps[
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
                text = f"0{text}"

            self.liststore2[path][6] = "" if text == "0" else text
            # Find selected sequence
            sequence = self.get_selected_sequence()
            # Find Step
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            sequence.steps[step].delay_in = float(text)
            # Update Total Time
            if (
                sequence.steps[step].time_in + sequence.steps[step].delay_in
                > sequence.steps[step].time_out + sequence.steps[step].delay_out
            ):
                sequence.steps[step].total_time = (
                    sequence.steps[step].time_in
                    + sequence.steps[step].wait
                    + sequence.steps[step].delay_in
                )
            else:
                sequence.steps[step].total_time = (
                    sequence.steps[step].time_out
                    + sequence.steps[step].wait
                    + sequence.steps[step].delay_out
                )
            for channel in sequence.steps[step].channel_time.keys():
                t = (
                    sequence.steps[step].channel_time[channel].delay
                    + sequence.steps[step].channel_time[channel].time
                    + sequence.steps[step].wait
                )
                if t > sequence.steps[step].total_time:
                    sequence.steps[step].total_time = t

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(f"{App().ascii.basename}*")

            # Update Sequential Tab
            if sequence == App().sequence:
                path = str(int(path) + 1)
                if text == "0":
                    App().window.playback.cues_liststore1[path][6] = ""
                    App().window.playback.cues_liststore2[path][6] = ""
                else:
                    App().window.playback.cues_liststore1[path][6] = text
                    App().window.playback.cues_liststore2[path][6] = text
                if App().sequence.position + 1 == step:
                    App().window.playback.sequential.delay_in = float(text)
                    App().window.playback.sequential.total_time = sequence.steps[
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
        sequence = self.get_selected_sequence()
        # Find Step
        step = int(self.liststore2[path][0])

        # Update text value
        sequence.steps[step].text = text

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(f"{App().ascii.basename}*")

        # Update Main Playback
        if sequence == App().sequence:
            path = str(int(path) + 1)
            App().window.playback.cues_liststore2[path][2] = text
            path = str(int(path) + 2)
            App().window.playback.cues_liststore1[path][2] = text

            # Update window's subtitle if needed
            if App().sequence.position == step:
                subtitle = (
                    "Mem. : "
                    + str(sequence.steps[step].cue.memory)
                    + " "
                    + sequence.steps[step].text
                    + " - Next Mem. : "
                    + str(sequence.steps[step + 1].cue.memory)
                    + " "
                    + sequence.steps[step + 1].text
                )
                App().window.header.set_subtitle(subtitle)

            if App().sequence.position + 1 == step:
                subtitle = (
                    "Mem. : "
                    + str(sequence.steps[step - 1].cue.memory)
                    + " "
                    + sequence.steps[step - 1].text
                    + " - Next Mem. : "
                    + str(sequence.steps[step].cue.memory)
                    + " "
                    + sequence.steps[step].text
                )
                App().window.header.set_subtitle(subtitle)

    def on_memory_changed(self, _treeview):
        """Select cue"""
        self.channels_view.update()

    def on_sequence_changed(self, _selection=None):
        """Select Sequence"""
        # Empty ListStore
        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)
        # Display Sequence
        self.populate_liststore(1)

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        App().tabs.close("sequences")

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

        # Channels View
        self.keystring = self.channels_view.on_key_press(keyname, self.keystring)

        if func := getattr(self, f"_keypress_{keyname}", None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        App().tabs.close("sequences")

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

    def _keypress_equal(self):
        """@ Level"""
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
        """Update Cue"""
        # Find selected sequence
        sequence = self.get_selected_sequence()
        # Find Step
        step = self.get_selected_step()
        if sequence and step:
            channels = sequence.steps[step].cue.channels
            memory = sequence.steps[step].cue.memory
            # Dialog to confirm Update
            dialog = Dialog(App().window, memory)
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                # Update levels in the cue
                for channel in range(MAX_CHANNELS):
                    channel_widget = self.channels_view.get_channel_widget(channel + 1)
                    if channel_widget.level:
                        channels[channel + 1] = channel_widget.level
                        sequence.channels[channel] = 1
                # Tag filename as modified
                App().ascii.modified = True
                App().window.header.set_title(f"{App().ascii.basename}*")
                # Update Main playback display
                if sequence == App().sequence and step == App().sequence.position + 1:
                    for channel in range(1, MAX_CHANNELS + 1):
                        widget = (
                            App().window.live_view.channels_view.get_channel_widget(
                                channel
                            )
                        )
                        widget.next_level = sequence.steps[step].cue.channels.get(
                            channel, 0
                        )
                        widget.queue_draw()
            dialog.destroy()
            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

    def _keypress_Delete(self):  # pylint: disable=C0103
        """Delete selected Step"""
        # Find selected sequence
        sequence = self.get_selected_sequence()
        step = self.get_selected_step()
        if sequence and step:
            sequence.steps.pop(step)
            sequence.last -= 1
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
        App().window.header.set_title(f"{App().ascii.basename}*")

    def _keypress_R(self):  # pylint: disable=C0103
        """New Step and new Cue"""
        found = False
        # Find selected Step
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = self.get_selected_step()
        if self.keystring == "":
            if step:
                # New Cue number
                mem = sequence.get_next_cue(step=step)
                # New Step
                step += 1
            else:
                mem = 1.0
                step = 1
        else:
            # Cue number given by user
            mem = float(self.keystring)
            found, step = sequence.get_step(cue=mem)
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
        if not found:  # New Cue
            # Create Cue
            channels = {}
            for channel in range(MAX_CHANNELS):
                channel_widget = self.channels_view.get_channel_widget(channel + 1)
                if channel_widget.level:
                    channels[channel] = channel_widget.level
            cue = Cue(sequence.index, mem, channels)
            # Create Step
            step_object = Step(sequence.index, cue=cue)
            sequence.insert_step(step, step_object)
            # If we modify Main Sequence
            if sequence is App().sequence:
                App().memories.insert(step, cue)
                # Update Preset Tab if exist
                if App().tabs.tabs["memories"]:
                    nb_chan = len(channels)
                    App().tabs.tabs["memories"].liststore.insert(
                        step - 1, [str(mem), "", nb_chan]
                    )
            # Update Display
            self.update_sequence_display(step)
            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(f"{App().ascii.basename}*")
            # Reset user modifications
            self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        else:  # Update Cue
            dialog = Dialog(App().window, str(mem))
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                # Find Preset's position
                found, step = sequence.get_step(cue=mem)
                # Update Cue
                channels = {}
                for channel in range(MAX_CHANNELS):
                    channel_widget = self.channels_view.get_channel_widget(channel + 1)
                    if channel_widget.level:
                        sequence.steps[step].cue.channels[
                            channel
                        ] = channel_widget.level
                        sequence.channels[channel] = 1
                # Tag filename as modified
                App().ascii.modified = True
                App().window.header.set_title(f"{App().ascii.basename}*")
                # Select memory modified
                path = Gtk.TreePath.new_from_indices([step - 1])
                self.treeview2.set_cursor(path, None, False)
                # Update Presets Tab if exist
                if sequence is App().sequence and App().tabs.tabs["memories"]:
                    nb_chan = len(App().memories[step - 1].channels)
                    treeiter = App().tabs.tabs["memories"].liststore.get_iter(step - 1)
                    App().tabs.tabs["memories"].liststore.set_value(
                        treeiter, 2, nb_chan
                    )
                    App().tabs.tabs["memories"].channels_view.update()
                # Update Channels tab
                if sequence is App().sequence and step == App().sequence.position + 1:
                    for channel in range(MAX_CHANNELS):
                        widget = (
                            App().window.live_view.channels_view.get_channel_widget(
                                channel + 1
                            )
                        )
                        channel_widget = self.channels_view.get_channel_widget(
                            channel + 1
                        )
                        widget.next_level = channel_widget.level
                        widget.queue_draw()
            dialog.destroy()

    def add_step_to_liststore(self, step):
        """Add Step to the list

        Args:
            step: Step
        """
        sequence = self.get_selected_sequence()
        wait = (
            str(int(sequence.steps[step].wait))
            if sequence.steps[step].wait.is_integer()
            else str(sequence.steps[step].wait)
        )
        if wait == "0":
            wait = ""
        t_out = (
            str(int(sequence.steps[step].time_out))
            if sequence.steps[step].time_out.is_integer()
            else str(sequence.steps[step].time_out)
        )
        d_out = (
            str(int(sequence.steps[step].delay_out))
            if sequence.steps[step].delay_out.is_integer()
            else str(sequence.steps[step].delay_out)
        )
        if d_out == "0":
            d_out = ""
        t_in = (
            str(int(sequence.steps[step].time_in))
            if sequence.steps[step].time_in.is_integer()
            else str(sequence.steps[step].time_in)
        )
        d_in = (
            str(int(sequence.steps[step].delay_in))
            if sequence.steps[step].delay_in.is_integer()
            else str(sequence.steps[step].delay_in)
        )
        if d_in == "0":
            d_in = ""
        channel_time = str(len(sequence.steps[step].channel_time))
        if channel_time == "0":
            channel_time = ""
        self.liststore2.insert(
            step - 1,
            [
                str(step),
                str(sequence.steps[step].cue.memory),
                sequence.steps[step].text,
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
        if sequence := self.get_selected_sequence():
            if sequence == App().sequence:
                for i in range(sequence.last)[1:-1]:
                    self.add_step_to_liststore(i)
            else:
                for i in range(sequence.last)[1:]:
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
        sequence = self.get_selected_sequence()
        # Update Main Playback
        if sequence is App().sequence:
            # Update indexes of cues in listsore
            for i in range(step, sequence.last - 2):
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
            for i in range(step, sequence.last - 1):
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

        label = Gtk.Label(f"Update memory {str(memory)} ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()


class SeqChannelsView(ChannelsView):
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
            App().tabs.tabs["sequences"].user_channels[channel - 1] = level

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        if not App().tabs.tabs["sequences"]:
            return False
        sequence = App().tabs.tabs["sequences"].get_selected_sequence()
        step = App().tabs.tabs["sequences"].get_selected_step()
        if not sequence or not step:
            return False
        channel = child.get_index() + 1
        channel_level = sequence.steps[step].cue.channels.get(channel, 0)
        if self.view_mode == VIEW_MODES["Active"]:
            return self._filter_active(child, channel_level)
        if self.view_mode == VIEW_MODES["Patched"]:
            return self._filter_patched(child, channel_level)
        return self._filter_all(child, channel_level)

    def _filter_active(self, child: Gtk.FlowBoxChild, channel_level: int) -> bool:
        """Filter in Active mode

        Args:
            child: Parent of Channel Widget
            channel_level: Channel level of selected step of selected sequence

        Returns:
            True or False
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channel = App().tabs.tabs["sequences"].user_channels[channel_index]
        if channel_level or child.is_selected():
            if user_channel == -1:
                channel_widget.level = channel_level
                channel_widget.next_level = channel_level
            else:
                channel_widget.level = user_channel
                channel_widget.next_level = user_channel
            return True
        if user_channel != -1:
            channel_widget.level = user_channel
            channel_widget.next_level = user_channel
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        return False

    def _filter_patched(self, child: Gtk.FlowBoxChild, channel_level: int) -> bool:
        """Filter in Patched mode

        Args:
            child: Parent of Channel Widget
            channel_level: Channel level of selected step of selected sequence

        Returns:
            True or False
        """
        channel_index = child.get_index()
        if channel_index + 1 not in App().patch.channels:
            return False
        return self._filter_all(child, channel_level)

    def _filter_all(self, child: Gtk.FlowBoxChild, channel_level: int) -> bool:
        """Filter in All channels mode

        Args:
            child: Parent of Channel Widget
            channel_level: Channel level of selected step of selected sequence

        Returns:
            True or False
        """
        channel_index = child.get_index()
        channel_widget = child.get_child()
        user_channel = App().tabs.tabs["sequences"].user_channels[channel_index]
        if channel_level or child.is_selected():
            if user_channel == -1:
                channel_widget.level = channel_level
                channel_widget.next_level = channel_level
            else:
                channel_widget.level = user_channel
                channel_widget.next_level = user_channel
            return True
        if user_channel != -1:
            channel_widget.level = user_channel
            channel_widget.next_level = user_channel
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        return True
