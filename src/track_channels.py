# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
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
import typing
from typing import Callable

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS
from olc.widgets.track_channels import TrackChannelsHeader, TrackChannelsWidget

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.lightshow import LightShow
    from olc.tabs_manager import Tabs
    from olc.window import Window


# pylint: disable=too-many-instance-attributes
class TrackChannelsTab(Gtk.Grid):
    """Tab to track channels"""

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings

        self.percent_level = self.settings.get_boolean("percent")

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
        sel = self.window.live_view.channels_view.flowbox.get_selected_children()
        for flowboxchild in sel:
            channelwidget = flowboxchild.get_child()
            channel = int(channelwidget.channel)
            if self.lightshow.patch.is_patched(channel):
                self.channels.append(channel - 1)

        self.populate_steps()

        self.flowbox.set_filter_func(self.filter_func, None)

        scrollable = Gtk.ScrolledWindow()
        scrollable.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(self.flowbox)

        self.attach(scrollable, 0, 0, 1, 1)

    def populate_steps(self) -> None:
        """Main Playback Steps"""
        # Clear flowbox
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)
        self.steps = []
        self.steps.append(TrackChannelsHeader(self.channels))
        levels: list[list[int]] = [[]]
        self.flowbox.add(self.steps[0])
        for step in range(1, self.lightshow.main_playback.last):
            memory = self.lightshow.main_playback.steps[step].cue.memory
            text = self.lightshow.main_playback.steps[step].text
            levels.append([])
            for channel in self.channels:
                level = self.lightshow.main_playback.steps[step].cue.channels.get(
                    channel + 1, 0
                )
                levels[step].append(level)
            self.steps.append(
                TrackChannelsWidget(
                    step, memory, text, levels[step], self, self.settings
                )
            )
            self.flowbox.add(self.steps[step])

    def filter_func(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Step filter

        Args:
            child: Child object

        Returns:
            True or False
        """
        if child == self.steps[0].get_parent():
            return True
        if len(self.steps) <= self.lightshow.main_playback.last - 1:
            return False
        if child == self.steps[self.lightshow.main_playback.last - 1].get_parent():
            return False
        return True

    def update_display(self) -> None:
        """Update display of tracked channels"""
        # Find selected channels
        self.channels = []
        sel = self.window.live_view.channels_view.flowbox.get_selected_children()
        for flowboxchild in sel:
            channelwidget = flowboxchild.get_child()
            channel = int(channelwidget.channel)
            if self.lightshow.patch.is_patched(channel):
                self.channels.append(channel - 1)
        self.channel_selected = 0
        # Update Track Channels Tab
        self.steps[0].channels = self.channels
        levels: list[list[int]] = [[]]
        for step in range(self.lightshow.main_playback.last):
            levels.append([])
            for channel in self.channels:
                level = self.lightshow.main_playback.steps[step].cue.channels.get(
                    channel + 1, 0
                )
                levels[step].append(level)
            self.steps[step].levels = levels[step]
        self.flowbox.queue_draw()

    def refresh(self) -> None:
        """Refresh display"""
        self.populate_steps()
        self.flowbox.invalidate_filter()
        self.show_all()
        self.update_display()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        self.tabs.close("track_channels")

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Keyboard events

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.window.commandline.add_string(keyname)

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
            self.window.commandline.add_string(keyname[3:])

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        self.tabs.close("track_channels")

    def _keypress_backspace(self) -> None:
        """Empty keys buffer"""
        self.window.commandline.set_string("")

    def _keypress_right(self) -> None:
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

    def _keypress_left(self) -> None:
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

    def _keypress_down(self) -> None:
        """Next Step"""

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        elif int(self.last_step_selected) < self.lightshow.main_playback.last - 2:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) + 1)
            self.flowbox.select_child(child)
            index = child.get_index()
            self.last_step_selected = str(index)

    def _keypress_up(self) -> None:
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

    def _keypress_equal(self) -> None:
        """Modify Level"""

        # Find selected Channel
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            widget = flowboxchild.get_child()
            step = widget.step
            channel = self.channels[self.channel_selected] + 1
            level = int(self.window.commandline.get_string())

            if self.settings.get_boolean("percent"):
                level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
            if 0 <= level <= 255:
                self.lightshow.main_playback.steps[step].cue.channels[channel] = level
                widget.levels[self.channel_selected] = level
                widget.queue_draw()
                self.tabs.refresh_all()
                self.window.live_view.channels_view.update()
                self.lightshow.set_modified()

        self.window.commandline.set_string("")

    def _keypress_c(self) -> None:
        """Select Channel"""

        self.window.live_view.channels_view.flowbox.unselect_all()

        if self.window.commandline.get_string() not in ["", "0"]:
            channel = int(self.window.commandline.get_string()) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = self.window.live_view.channels_view.flowbox.get_child_at_index(
                    channel
                )
                self.window.live_view.channels_view.flowbox.select_child(child)
                self.window.last_chan_selected = str(channel)

        self.update_display()

        self.window.commandline.set_string("")

    def _keypress_kp_divide(self) -> None:
        """Channel Thru"""
        self._keypress_greater()

    def _keypress_greater(self) -> None:
        """Channel Thru"""

        sel = self.window.live_view.channels_view.flowbox.get_selected_children()
        keystring = self.window.commandline.get_string()

        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_child()
            self.window.last_chan_selected = channelwidget.channel

        if not self.window.last_chan_selected:
            sel = self.window.live_view.channels_view.flowbox.get_selected_children()
            if len(sel) > 0:
                for flowboxchild in sel:
                    channelwidget = flowboxchild.get_child()
                    channel = int(channelwidget.channel)
                self.window.last_chan_selected = str(channel)

        if self.window.last_chan_selected:
            to_chan = int(keystring)
            if to_chan > int(self.window.last_chan_selected):
                for channel in range(int(self.window.last_chan_selected) - 1, to_chan):
                    child = (
                        self.window.live_view.channels_view.flowbox.get_child_at_index(
                            channel
                        )
                    )
                    self.window.live_view.channels_view.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(self.window.last_chan_selected)):
                    child = (
                        self.window.live_view.channels_view.flowbox.get_child_at_index(
                            channel
                        )
                    )
                    self.window.live_view.channels_view.flowbox.select_child(child)

            self.window.last_chan_selected = keystring

            self.update_display()

        self.window.commandline.set_string("")

    def _keypress_kp_add(self) -> None:
        """Channel +"""
        self._keypress_plus()

    def _keypress_plus(self) -> None:
        """Channel +"""
        keystring = self.window.commandline.get_string()
        if keystring == "":
            return

        channel = int(keystring) - 1
        if 0 <= channel < MAX_CHANNELS:
            child = self.window.live_view.channels_view.flowbox.get_child_at_index(
                channel
            )
            self.window.live_view.channels_view.flowbox.select_child(child)
            self.window.last_chan_selected = keystring

            self.update_display()

        self.window.commandline.set_string("")

    def _keypress_kp_subtract(self) -> None:
        """Channel -"""
        self._keypress_minus()

    def _keypress_minus(self) -> None:
        """Channel -"""
        keystring = self.window.commandline.get_string()
        if keystring == "":
            return

        channel = int(keystring) - 1
        if 0 <= channel < MAX_CHANNELS:
            child = self.window.live_view.channels_view.flowbox.get_child_at_index(
                channel
            )
            self.window.live_view.channels_view.flowbox.unselect_child(child)
            self.window.last_chan_selected = keystring

            self.update_display()

        self.window.commandline.set_string("")
