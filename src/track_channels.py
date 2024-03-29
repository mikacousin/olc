# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from olc.define import MAX_CHANNELS, App
from olc.widgets.track_channels import TrackChannelsHeader, TrackChannelsWidget


class TrackChannelsTab(Gtk.Grid):
    """Tab to track channels"""

    def __init__(self):
        self.percent_level = App().settings.get_boolean("percent")

        self.last_step_selected = ""

        self.channel_selected = 0

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        # Find selected channels
        self.channels = []
        sel = App().window.live_view.channels_view.flowbox.get_selected_children()
        for flowboxchild in sel:
            channelwidget = flowboxchild.get_child()
            channel = int(channelwidget.channel)
            if App().lightshow.patch.is_patched(channel):
                self.channels.append(channel - 1)

        self.populate_steps()

        self.flowbox.set_filter_func(self.filter_func, None)

        scrollable = Gtk.ScrolledWindow()
        scrollable.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(self.flowbox)

        self.attach(scrollable, 0, 0, 1, 1)

    def populate_steps(self):
        """Main Playback's Steps"""
        # Clear flowbox
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)
        self.steps = []
        self.steps.append(TrackChannelsHeader(self.channels))
        levels = [[]]
        self.flowbox.add(self.steps[0])
        for step in range(1, App().lightshow.main_playback.last):
            memory = App().lightshow.main_playback.steps[step].cue.memory
            text = App().lightshow.main_playback.steps[step].text
            levels.append([])
            for channel in self.channels:
                level = App().lightshow.main_playback.steps[step].cue.channels.get(
                    channel + 1, 0)
                levels[step].append(level)
            self.steps.append(TrackChannelsWidget(step, memory, text, levels[step]))
            self.flowbox.add(self.steps[step])

    def filter_func(self, child, _user_data):
        """Step filter

        Args:
            child: Child object

        Returns:
            child or False
        """
        if child == self.steps[0].get_parent():
            return child
        if len(self.steps) <= App().lightshow.main_playback.last - 1:
            return False
        if child == self.steps[App().lightshow.main_playback.last - 1].get_parent():
            return False
        return child

    def update_display(self):
        """Update display of tracked channels"""
        # Find selected channels
        self.channels = []
        sel = App().window.live_view.channels_view.flowbox.get_selected_children()
        for flowboxchild in sel:
            channelwidget = flowboxchild.get_child()
            channel = int(channelwidget.channel)
            if App().lightshow.patch.is_patched(channel):
                self.channels.append(channel - 1)
        self.channel_selected = 0
        # Update Track Channels Tab
        self.steps[0].channels = self.channels
        levels = []
        for step in range(App().lightshow.main_playback.last):
            levels.append([])
            for channel in self.channels:
                level = App().lightshow.main_playback.steps[step].cue.channels.get(
                    channel + 1, 0)
                levels[step].append(level)
            self.steps[step].levels = levels[step]
        self.flowbox.queue_draw()

    def refresh(self) -> None:
        """Refresh display"""
        self.populate_steps()
        self.flowbox.invalidate_filter()
        self.show_all()
        self.update_display()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        App().tabs.close("track_channels")

    def on_key_press_event(self, _widget, event):
        """Keyboard events

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
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

        if func := getattr(self, f"_keypress_{keyname}", None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        App().tabs.close("track_channels")

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        """Empty keys buffer"""
        App().window.commandline.set_string("")

    def _keypress_Right(self):  # pylint: disable=C0103
        """Next Channel"""

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        else:
            sel = self.flowbox.get_selected_children()
            for flowboxchild in sel:
                widget = flowboxchild.get_child()
                if self.channel_selected + 1 < len(widget.levels):
                    self.channel_selected += 1
                    widget.queue_draw()

    def _keypress_Left(self):  # pylint: disable=C0103
        """Previous Channel"""

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        else:
            sel = self.flowbox.get_selected_children()
            for flowboxchild in sel:
                widget = flowboxchild.get_child()
                if self.channel_selected > 0:
                    self.channel_selected -= 1
                    widget.queue_draw()

    def _keypress_Down(self):  # pylint: disable=C0103
        """Next Step"""

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        elif int(self.last_step_selected) < App().lightshow.main_playback.last - 2:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) + 1)
            self.flowbox.select_child(child)
            index = child.get_index()
            self.last_step_selected = str(index)

    def _keypress_Up(self):  # pylint: disable=C0103
        """Previous Step"""

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        elif int(self.last_step_selected) > 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) - 1)
            self.flowbox.select_child(child)
            index = child.get_index()
            self.last_step_selected = str(index)

    def _keypress_equal(self):
        """Modify Level"""

        # Find selected Channel
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            widget = flowboxchild.get_child()
            step = widget.step
            channel = self.channels[self.channel_selected] + 1
            level = int(App().window.commandline.get_string())

            if App().settings.get_boolean("percent"):
                level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
            if 0 <= level <= 255:
                App().lightshow.main_playback.steps[step].cue.channels[channel] = level
                widget.levels[self.channel_selected] = level
                widget.queue_draw()
                App().tabs.refresh_all()
                App().window.live_view.channels_view.update()
                App().lightshow.set_modified()

        App().window.commandline.set_string("")

    def _keypress_c(self):
        """Select Channel"""

        App().window.live_view.channels_view.flowbox.unselect_all()

        if App().window.commandline.get_string() not in ["", "0"]:
            channel = int(App().window.commandline.get_string()) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = App().window.live_view.channels_view.flowbox.get_child_at_index(
                    channel)
                App().window.live_view.channels_view.flowbox.select_child(child)
                App().window.last_chan_selected = str(channel)

        self.update_display()

        App().window.commandline.set_string("")

    def _keypress_KP_Divide(self):  # pylint: disable=C0103
        """Channel Thru"""
        self._keypress_greater()

    def _keypress_greater(self):
        """Channel Thru"""

        sel = App().window.live_view.channels_view.flowbox.get_selected_children()
        keystring = App().window.commandline.get_string()

        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_child()
            App().window.last_chan_selected = channelwidget.channel

        if not App().window.last_chan_selected:
            sel = App().window.live_view.channels_view.flowbox.get_selected_children()
            if len(sel) > 0:
                for flowboxchild in sel:
                    channelwidget = flowboxchild.get_child()
                    channel = int(channelwidget.channel)
                App().window.last_chan_selected = str(channel)

        if App().window.last_chan_selected:
            to_chan = int(keystring)
            if to_chan > int(App().window.last_chan_selected):
                for channel in range(int(App().window.last_chan_selected) - 1, to_chan):
                    child = (App().window.live_view.channels_view.flowbox.
                             get_child_at_index(channel))
                    App().window.live_view.channels_view.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(App().window.last_chan_selected)):
                    child = (App().window.live_view.channels_view.flowbox.
                             get_child_at_index(channel))
                    App().window.live_view.channels_view.flowbox.select_child(child)

            App().window.last_chan_selected = keystring

            self.update_display()

        App().window.commandline.set_string("")

    def _keypress_KP_Add(self):  # pylint: disable=C0103
        """Channel +"""
        self._keypress_plus()

    def _keypress_plus(self):
        """Channel +"""
        keystring = App().window.commandline.get_string()
        if keystring == "":
            return

        channel = int(keystring) - 1
        if 0 <= channel < MAX_CHANNELS:
            child = App().window.live_view.channels_view.flowbox.get_child_at_index(
                channel)
            App().window.live_view.channels_view.flowbox.select_child(child)
            App().window.last_chan_selected = keystring

            self.update_display()

        App().window.commandline.set_string("")

    def _keypress_KP_Subtract(self):  # pylint: disable=C0103
        """Channel -"""
        self._keypress_minus()

    def _keypress_minus(self):
        """Channel -"""
        keystring = App().window.commandline.get_string()
        if keystring == "":
            return

        channel = int(keystring) - 1
        if 0 <= channel < MAX_CHANNELS:
            child = App().window.live_view.channels_view.flowbox.get_child_at_index(
                channel)
            App().window.live_view.channels_view.flowbox.unselect_child(child)
            App().window.last_chan_selected = keystring

            self.update_display()

        App().window.commandline.set_string("")
