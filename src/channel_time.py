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
from gi.repository import Gdk, Gtk

from olc.define import App
from olc.widgets_channels_view import ChannelsView


class ChannelTime:
    """Give a specific time to some channels in a step

    Attributes:
        delay (float): specific delay in seconds
        time (float): specific time in seconds
    """

    def __init__(self, delay=0.0, time=0.0):
        self.delay = delay
        self.time = time

    def get_delay(self):
        """Get specific delay

        Returns:
            Delay (float) in seconds
        """
        return self.delay

    def get_time(self):
        """Get specific time

        Returns:
            Time (float) in seconds
        """
        return self.time

    def set_delay(self, delay):
        """Set specific delay

        Args:
            delay (float): Delay in seconds
        """
        if isinstance(delay, float) and delay >= 0:
            self.delay = delay

    def set_time(self, time):
        """Set specific time

        Args:
            time (float): Time in seconds
        """
        if isinstance(time, float) and time >= 0:
            self.time = time


class ChanneltimeTab(Gtk.Paned):
    """Channels time edition"""

    def __init__(self, sequence, position):

        self.sequence = sequence
        self.position = position

        self.keystring = ""
        self.last_selected_channel = ""

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        self.channels_view = CTChannelsView()
        self.add1(self.channels_view)

        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled2.set_vexpand(True)
        self.scrolled2.set_hexpand(True)

        # List of Channels Times
        self.liststore = Gtk.ListStore(int, str, str)

        self.step = self.sequence.steps[int(position)]

        for channel in self.step.channel_time.keys():
            delay = (
                str(int(self.step.channel_time[channel].delay))
                if self.step.channel_time[channel].delay.is_integer()
                else str(self.step.channel_time[channel].delay)
            )
            if delay == "0":
                delay = ""
            time = (
                str(int(self.step.channel_time[channel].time))
                if self.step.channel_time[channel].time.is_integer()
                else str(self.step.channel_time[channel].time)
            )
            if time == "0":
                time = ""
            self.liststore.append([channel, delay, time])

        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_channeltime_changed)
        self.treeview.connect("focus-in-event", self.on_focus)

        for i, column_title in enumerate(["Channel", "Delay", "Time"]):
            renderer = Gtk.CellRendererText()
            if i == 1:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.delay_edited)
            elif i == 2:
                renderer.set_property("editable", True)
                renderer.connect("edited", self.time_edited)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        self.scrolled2.add(self.treeview)

        self.add2(self.scrolled2)

    def on_focus(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Give focus to notebook

        Returns:
            False
        """
        notebook = self.get_parent()
        if notebook:
            notebook.grab_focus()
        return False

    def delay_edited(self, _widget, path, text):
        """Delay changed

        Args:
            path: selected channel
            text (str): new delay value
        """
        if text == "":
            text = "0"
        if text.replace(".", "", 1).isdigit():
            self.liststore[path][1] = "" if text == "0" else text
        # Find selected Channel Time
        path, _focus_column = self.treeview.get_cursor()
        if path:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]
            # Delete Channel Time if Delay and Time are 0
            if self.step.channel_time[channel].time == 0 and text == "0":
                del self.step.channel_time[channel]
                # Redraw list of Channel Time
                self.liststore.clear()
                for channel in self.step.channel_time.keys():
                    delay = (
                        str(int(self.step.channel_time[channel].delay))
                        if self.step.channel_time[channel].delay.is_integer()
                        else str(self.step.channel_time[channel].delay)
                    )
                    if delay == "0":
                        delay = ""
                    time = (
                        str(int(self.step.channel_time[channel].time))
                        if self.step.channel_time[channel].time.is_integer()
                        else str(self.step.channel_time[channel].time)
                    )
                    if time == "0":
                        time = ""
                    self.liststore.append([channel, delay, time])
                    self.treeview.set_model(self.liststore)
            else:
                # Update Delay value
                self.step.channel_time[channel].delay = float(text)
            # Update Sequence Tab if Open on the good sequence
            if App().sequences_tab:
                # Start to find the selected sequence
                seq_path, _focus_column = App().sequences_tab.treeview1.get_cursor()
                selected = seq_path.get_indices()
                sequence = App().sequences_tab.liststore1[selected][0]
                # If the same sequence is selected
                if sequence == self.sequence.index:
                    path = Gtk.TreePath.new_from_indices([int(self.position) - 1])
                    ct_nb = len(self.step.channel_time)
                    App().sequences_tab.liststore2[path][8] = (
                        "" if ct_nb == 0 else str(ct_nb)
                    )
            # Update Total Time
            if self.step.time_in > self.step.time_out:
                self.step.total_time = self.step.time_in + self.step.wait
            else:
                self.step.total_time = self.step.time_out + self.step.wait
            for channel in self.step.channel_time.keys():
                t = (
                    self.step.channel_time[channel].delay
                    + self.step.channel_time[channel].time
                    + self.step.wait
                )
                if t > self.step.total_time:
                    self.step.total_time = t

            # Redraw Main Playback
            if self.sequence == App().sequence:
                path1 = Gtk.TreePath.new_from_indices([int(self.position) + 2])
                path2 = Gtk.TreePath.new_from_indices([int(self.position)])
                ct_nb = len(self.step.channel_time)
                if ct_nb == 0:
                    App().window.playback.cues_liststore1[path1][8] = ""
                    App().window.playback.cues_liststore2[path2][8] = ""
                else:
                    App().window.playback.cues_liststore1[path1][8] = str(ct_nb)
                    App().window.playback.cues_liststore2[path2][8] = str(ct_nb)
                if App().sequence.position + 1 == int(self.position):
                    App().window.playback.sequential.total_time = self.step.total_time
                    App().window.playback.sequential.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def time_edited(self, _widget, path, text):
        """Time changed

        Args:
            path: selected channel
            text (str): new time value
        """
        if text == "":
            text = "0"
        if text.replace(".", "", 1).isdigit():
            self.liststore[path][2] = "" if text == "0" else text
        # Find selected Channel Time
        path, _focus_column = self.treeview.get_cursor()
        if path:
            selected = path.get_indices()[0]
            channel = self.liststore[selected][0]
            # Delete Channel Time if Delay and Time are 0
            if self.step.channel_time[channel].delay == 0 and text == "0":
                del self.step.channel_time[channel]
                # Redraw List of Channel Time
                self.liststore.clear()
                for channel in self.step.channel_time.keys():
                    delay = (
                        str(int(self.step.channel_time[channel].delay))
                        if self.step.channel_time[channel].delay.is_integer()
                        else str(self.step.channel_time[channel].delay)
                    )
                    if delay == "0":
                        delay = ""
                    time = (
                        str(int(self.step.channel_time[channel].time))
                        if self.step.channel_time[channel].time.is_integer()
                        else str(self.step.channel_time[channel].time)
                    )
                    if time == "0":
                        time = ""
                    self.liststore.append([channel, delay, time])
                    self.treeview.set_model(self.liststore)
            else:
                # Update Time value
                self.step.channel_time[channel].time = float(text)
            # Update Sequence Tab if Open on the good sequence
            if App().sequences_tab:
                # Start to find the selected sequence
                seq_path, _focus_column = App().sequences_tab.treeview1.get_cursor()
                selected = seq_path.get_indices()
                sequence = App().sequences_tab.liststore1[selected][0]
                # If the same sequence is selected
                if sequence == self.sequence.index:
                    path = Gtk.TreePath.new_from_indices([int(self.position) - 1])
                    ct_nb = len(self.step.channel_time)
                    App().sequences_tab.liststore2[path][8] = (
                        "" if ct_nb == 0 else str(ct_nb)
                    )
            # Update Total Time
            if self.step.time_in > self.step.time_out:
                self.step.total_time = self.step.time_in + self.step.wait
            else:
                self.step.total_time = self.step.time_out + self.step.wait
            for channel in self.step.channel_time.keys():
                t = (
                    self.step.channel_time[channel].delay
                    + self.step.channel_time[channel].time
                    + self.step.wait
                )
                if t > self.step.total_time:
                    self.step.total_time = t

            # Redraw Main Playback
            if self.sequence == App().sequence:
                path1 = Gtk.TreePath.new_from_indices([int(self.position) + 2])
                path2 = Gtk.TreePath.new_from_indices([int(self.position)])
                ct_nb = len(self.step.channel_time)
                if ct_nb == 0:
                    App().window.playback.cues_liststore1[path1][8] = ""
                    App().window.playback.cues_liststore2[path2][8] = ""
                else:
                    App().window.playback.cues_liststore1[path1][8] = str(ct_nb)
                    App().window.playback.cues_liststore2[path2][8] = str(ct_nb)
                if App().sequence.position + 1 == int(self.position):
                    App().window.playback.sequential.total_time = self.step.total_time
                    App().window.playback.sequential.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def on_channeltime_changed(self, _treeview):
        """Select a Channel Time"""
        self.channels_view.update()

    def on_close_icon(self, _widget):
        """Close Tab with the icon clicked"""
        # If channel times has no delay and no time, delete it
        keys = list(self.step.channel_time.keys())
        for channel in keys:
            delay = self.step.channel_time[channel].delay
            time = self.step.channel_time[channel].time
            if delay == 0.0 and time == 0.0:
                del self.step.channel_time[channel]

        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().channeltime_tab = None

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
        self.last_selected_channel, self.keystring = self.channels_view.on_key_press(
            keyname, self.last_selected_channel, self.keystring
        )

        if func := getattr(self, "_keypress_" + keyname, None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        # If channel times has no delay and no time, delete it
        keys = list(self.step.channel_time.keys())
        for channel in keys:
            delay = self.step.channel_time[channel].delay
            time = self.step.channel_time[channel].time
            if delay == 0.0 and time == 0.0:
                del self.step.channel_time[channel]

        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().channeltime_tab = None

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_q(self):
        """Prev Channel Time"""

        self.channels_view.flowbox.unselect_all()

        path, _focus_column = self.treeview.get_cursor()
        if path:
            if path.prev():
                self.treeview.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview.set_cursor(path)
        self.get_parent().grab_focus()

    def _keypress_w(self):
        """Next Channel Time"""

        self.channels_view.flowbox.unselect_all()

        path, _focus_column = self.treeview.get_cursor()
        if path:
            path.next()
        else:
            path = Gtk.TreePath.new_first()

        self.treeview.set_cursor(path)
        self.get_parent().grab_focus()

    def _keypress_Insert(self):  # pylint: disable=C0103
        """Add Channel Time"""
        # Find selected channels
        sel = self.channels_view.flowbox.get_selected_children()
        for flowboxchild in sel:
            channelwidget = flowboxchild.get_child()
            channel = int(channelwidget.channel)
            # If not already exist
            if channel not in self.step.channel_time:
                # Add Channel Time
                delay = 0.0
                time = 0.0
                self.step.channel_time[channel] = ChannelTime(delay, time)
                # Update ui
                self.liststore.append([channel, "", ""])
                path = Gtk.TreePath.new_from_indices([len(self.liststore) - 1])
                self.treeview.set_cursor(path)
        self.get_parent().grab_focus()


class CTChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self):
        super().__init__()

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        if not App().channeltime_tab:
            return False
        channel_index = child.get_index()
        channel_widget = child.get_child()
        step = App().channeltime_tab.step
        channels = step.cue.channels
        path, _focus_column = App().channeltime_tab.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            channel = App().channeltime_tab.liststore[row][0]
            if channel - 1 == channel_index or child.is_selected():
                channel_widget.level = channels[channel_index]
                channel_widget.next_level = channels[channel_index]
                return True
            channel_widget.level = 0
            channel_widget.next_level = 0
            return False
        if child.is_selected():
            channel_widget.level = channels[channel_index]
            channel_widget.next_level = channels[channel_index]
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        return False
