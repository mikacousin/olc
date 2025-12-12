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
from typing import Callable

from gi.repository import Gdk, Gtk, Pango
from olc.define import App, time_to_string
from olc.widgets.sequential import SequentialWidget


def step_filter_func1(
    model: Gtk.TreeModel, treeiter: Gtk.TreeIter, _data: None
) -> bool:
    """Filter for the first part of the cues list

    Args:
        model: Model
        treeiter: Treeiter

    Returns:
        True, False or step
    """
    if App().lightshow.main_playback.position <= 0:
        if int(model[treeiter][11]) in {0, 1} or int(model[treeiter][0]) in {0, 1}:
            return True
    if App().lightshow.main_playback.position == 1:
        if int(model[treeiter][11]) == 1:
            return True
        if int(model[treeiter][11]) == 0:
            return False
        return int(model[treeiter][0]) in {0, 1, 2}
    if int(model[treeiter][11]) in {0, 1}:
        return False

    return int(model[treeiter][0]) in [
        App().lightshow.main_playback.position,
        App().lightshow.main_playback.position + 1,
        App().lightshow.main_playback.position - 1,
        App().lightshow.main_playback.position - 2,
    ]


def step_filter_func2(
    model: Gtk.TreeModel, treeiter: Gtk.TreeIter, _data: None
) -> bool:
    """Filter for the second part of the cues list

    Args:
        model: Model
        treeiter: Treeiter

    Returns:
        True or False
    """
    if not model[treeiter][0]:
        return False
    return int(model[treeiter][0]) > App().lightshow.main_playback.position + 1


class MainPlaybackView(Gtk.Notebook):
    """Main Playback View"""

    def __init__(self) -> None:
        Gtk.Notebook.__init__(self)
        self.set_group_name("olc")

        # Sequential part of the window
        if App().lightshow.main_playback.last > 1:
            position = App().lightshow.main_playback.position
            t_total = App().lightshow.main_playback.steps[position].total_time
            t_in = App().lightshow.main_playback.steps[position].time_in
            t_out = App().lightshow.main_playback.steps[position].time_out
            d_in = App().lightshow.main_playback.steps[position].delay_in
            d_out = App().lightshow.main_playback.steps[position].delay_out
            t_wait = App().lightshow.main_playback.steps[position].wait
            channel_time = App().lightshow.main_playback.steps[position].channel_time
        else:
            position = 0
            t_total = 5.0
            t_in = 5.0
            t_out = 5.0
            d_in = 0.0
            d_out = 0.0
            t_wait = 0.0
            channel_time = {}
        # Crossfade widget
        self.sequential = SequentialWidget(
            t_total, t_in, t_out, d_in, d_out, t_wait, channel_time
        )
        # Main Playback
        self.cues_liststore1 = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str, str, int, int
        )
        # Filters
        self.step_filter1 = self.cues_liststore1.filter_new()
        self.step_filter1.set_visible_func(step_filter_func1)
        self.step_filter2 = self.cues_liststore1.filter_new()
        self.step_filter2.set_visible_func(step_filter_func2)
        # Lists
        self.treeview1 = Gtk.TreeView(model=self.step_filter1)
        self.treeview1.set_enable_search(False)
        sel = self.treeview1.get_selection()
        sel.set_mode(Gtk.SelectionMode.NONE)
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
            column = Gtk.TreeViewColumn(
                column_title, renderer, text=i, background=9, weight=10
            )
            if i == 2:
                column.set_min_width(400)
                column.set_resizable(True)
            self.treeview1.append_column(column)
        self.treeview2 = Gtk.TreeView(model=self.step_filter2)
        self.treeview2.set_enable_search(False)
        sel = self.treeview2.get_selection()
        sel.set_mode(Gtk.SelectionMode.NONE)
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
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == 2:
                column.set_min_width(400)
                column.set_resizable(True)
            self.treeview2.append_column(column)
        # Put Cues List in a scrolled window
        scrollable2 = Gtk.ScrolledWindow()
        scrollable2.set_vexpand(True)
        scrollable2.set_hexpand(True)
        scrollable2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
        scrollable2.add(self.treeview2)
        # Put Cues lists and sequential in a grid
        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(False)
        self.grid.attach(self.treeview1, 0, 0, 1, 1)
        self.grid.attach_next_to(
            self.sequential, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1
        )
        self.grid.attach_next_to(
            scrollable2, self.sequential, Gtk.PositionType.BOTTOM, 1, 1
        )

        self.populate_sequence()

        if App().lightshow.main_playback.last == 1:
            self.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )

        self.append_page(self.grid, Gtk.Label("Main Playback"))
        self.set_tab_reorderable(self.grid, True)
        self.set_tab_detachable(self.grid, True)

        self.connect("key_press_event", self.on_key_press_event)

    def update_sequence_display(self) -> None:
        """Update Sequence display"""
        self.cues_liststore1.clear()
        self.populate_sequence()

    def populate_sequence(self) -> None:
        """Display main playback"""
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
        )
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
        )
        for i in range(App().lightshow.main_playback.last):
            wait = time_to_string(App().lightshow.main_playback.steps[i].wait)
            t_out = time_to_string(App().lightshow.main_playback.steps[i].time_out)
            d_out = time_to_string(App().lightshow.main_playback.steps[i].delay_out)
            t_in = time_to_string(App().lightshow.main_playback.steps[i].time_in)
            d_in = time_to_string(App().lightshow.main_playback.steps[i].delay_in)
            channel_time = str(len(App().lightshow.main_playback.steps[i].channel_time))
            if channel_time == "0":
                channel_time = ""
            if i == 0:
                background = "#997004"
            elif i == 1:
                background = "#555555"
            else:
                background = "#232729"
            # Actual and Next Cue in Bold
            weight = Pango.Weight.HEAVY if i in (0, 1) else Pango.Weight.NORMAL
            if i in (0, App().lightshow.main_playback.last - 1):
                self.cues_liststore1.append(
                    [
                        str(i),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        background,
                        Pango.Weight.NORMAL,
                        99,
                    ]
                )
            else:
                self.cues_liststore1.append(
                    [
                        str(i),
                        str(App().lightshow.main_playback.steps[i].cue.memory),
                        str(App().lightshow.main_playback.steps[i].text),
                        wait,
                        d_out,
                        str(t_out),
                        d_in,
                        str(t_in),
                        channel_time,
                        background,
                        weight,
                        99,
                    ]
                )
        self.update_active_cues_display()
        self.grid.queue_draw()

    def update_active_cues_display(self) -> None:
        """Update First part of sequential"""
        self.cues_liststore1[App().lightshow.main_playback.position][9] = "#232729"
        self.cues_liststore1[App().lightshow.main_playback.position][10] = (
            Pango.Weight.NORMAL
        )
        if (
            App().lightshow.main_playback.position + 1
            <= App().lightshow.main_playback.last
        ):
            self.cues_liststore1[App().lightshow.main_playback.position + 1][9] = (
                "#232729"
            )
            self.cues_liststore1[App().lightshow.main_playback.position + 1][10] = (
                Pango.Weight.NORMAL
            )
        if (
            App().lightshow.main_playback.position + 2
            <= App().lightshow.main_playback.last
        ):
            self.cues_liststore1[App().lightshow.main_playback.position + 2][9] = (
                "#997004"
            )
            self.cues_liststore1[App().lightshow.main_playback.position + 2][10] = (
                Pango.Weight.HEAVY
            )
        if (
            App().lightshow.main_playback.position + 3
            <= App().lightshow.main_playback.last
        ):
            self.cues_liststore1[App().lightshow.main_playback.position + 3][9] = (
                "#555555"
            )
            self.cues_liststore1[App().lightshow.main_playback.position + 3][10] = (
                Pango.Weight.HEAVY
            )
        self.step_filter1.refilter()
        self.step_filter2.refilter()
        path1 = Gtk.TreePath.new_from_indices(
            [App().lightshow.main_playback.position + 2]
        )
        path2 = Gtk.TreePath.new_from_indices([0])
        self.treeview1.set_cursor(path1, None, False)
        self.treeview2.set_cursor(path2, None, False)

    def display_times(self) -> None:
        """Display Cues times after countdown"""
        step = App().lightshow.main_playback.position
        t_wait = App().lightshow.main_playback.steps[step].wait
        self.cues_liststore1[step + 2][3] = time_to_string(t_wait)
        d_out = App().lightshow.main_playback.steps[step].delay_out
        self.cues_liststore1[step + 2][4] = time_to_string(d_out)
        t_out = App().lightshow.main_playback.steps[step].time_out
        self.cues_liststore1[step + 2][5] = time_to_string(t_out)
        d_in = App().lightshow.main_playback.steps[step].delay_in
        self.cues_liststore1[step + 2][6] = time_to_string(d_in)
        t_in = App().lightshow.main_playback.steps[step].time_in
        self.cues_liststore1[step + 2][7] = time_to_string(t_in)
        t_wait = App().lightshow.main_playback.steps[step + 1].wait
        self.cues_liststore1[step + 3][3] = time_to_string(t_wait)
        d_out = App().lightshow.main_playback.steps[step + 1].delay_out
        self.cues_liststore1[step + 3][4] = time_to_string(d_out)
        t_out = App().lightshow.main_playback.steps[step + 1].time_out
        self.cues_liststore1[step + 3][5] = time_to_string(t_out)
        d_in = App().lightshow.main_playback.steps[step + 1].delay_in
        self.cues_liststore1[step + 3][6] = time_to_string(d_in)
        t_in = App().lightshow.main_playback.steps[step + 1].time_in
        self.cues_liststore1[step + 3][7] = time_to_string(t_in)

    def show_timeleft(self, i: float) -> None:
        """Display countdowns during Go and color crossfade of active cues

        Args:
            i: Spent time of the Go in milliseconds
        """
        self.show_timeleft_out(i)
        self.show_timeleft_in(i)
        # Color crossfade
        step = App().lightshow.main_playback.position + 1
        total_time = App().lightshow.main_playback.steps[step].total_time * 1000
        progress = min(max(i / total_time, 0.0), 1.0)
        self.update_cue_crossfade_color(step, progress)

    def show_timeleft_out(self, i: float) -> None:
        """Display Out Countdowns during Xfade

        Args:
            i: Position in Xfade in milliseconds
        """
        step = App().lightshow.main_playback.position + 1
        wait = App().lightshow.main_playback.steps[step].wait * 1000
        if i > wait:
            d_out = App().lightshow.main_playback.steps[step].delay_out * 1000
            if i > wait + d_out:
                t_out = App().lightshow.main_playback.steps[step].time_out * 1000
                time = (t_out + wait + d_out - i) / 1000
                if time >= 0:
                    self.cues_liststore1[step + 2][5] = time_to_string(time)
            else:
                time = (d_out + wait - i) / 1000
                if time >= 0:
                    self.cues_liststore1[step + 2][4] = time_to_string(time)
        else:
            time = (wait - i) / 1000
            self.cues_liststore1[step + 2][3] = time_to_string(time)

    def show_timeleft_in(self, i: float) -> None:
        """Display In Countdowns during Xfade

        Args:
            i: Position in Xfade in milliseconds
        """
        step = App().lightshow.main_playback.position + 1
        wait = App().lightshow.main_playback.steps[step].wait * 1000
        if i > wait:
            d_in = App().lightshow.main_playback.steps[step].delay_in * 1000
            if i > wait + d_in:
                t_in = App().lightshow.main_playback.steps[step].time_in * 1000
                time = (t_in + wait + d_in - i) / 1000
                if time >= 0:
                    self.cues_liststore1[step + 2][7] = time_to_string(time)
            else:
                time = (d_in + wait - i) / 1000
                if time >= 0:
                    self.cues_liststore1[step + 2][6] = time_to_string(time)
        else:
            time = (wait - i) / 1000
            self.cues_liststore1[step + 2][3] = time_to_string(time)

    def update_cue_crossfade_color(self, step: int, progress: float) -> None:
        """Crossfade active cues color background

        Args:
            step: active step
            progress: position in xfade in milliseconds
        """
        start_color = "#555555"
        end_color = "#997004"
        blended = self._blend_color(start_color, end_color, progress)
        hex_color = self._rgb_to_hex(blended)
        self.cues_liststore1[step + 2][9] = hex_color
        start_color = "#997004"
        end_color = "#232729"
        blended = self._blend_color(start_color, end_color, progress)
        hex_color = self._rgb_to_hex(blended)
        self.cues_liststore1[step + 1][9] = hex_color
        self.treeview1.queue_draw()

    def _blend_color(self, color1: str, color2: str, t: float) -> tuple[int, ...]:
        start = self._hex_to_rgb(color1)
        end = self._hex_to_rgb(color2)
        return tuple(int(c1 + (c2 - c1) * t) for c1, c2 in zip(start, end, strict=True))

    def _hex_to_rgb(self, color: str) -> tuple[int, ...]:
        color = color.lstrip("#")
        return tuple(int(color[i: i + 2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb: tuple[int, ...]) -> str:
        return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"

    def goback_countdown(self, i: float, goback_time: float, step: int) -> None:
        """Display countdowns during GoBack

        Args:
            i: Position in milliseconds
            goback_time: GoBack Time set in preference
            step: Active Step
        """
        count = (goback_time - i) / 1000
        if count >= 0:
            self.cues_liststore1[step + 1][5] = time_to_string(count)
            self.cues_liststore1[step + 1][7] = time_to_string(count)
        progress = min(max(i / goback_time, 0.0), 1.0)
        blended = self._blend_color("#232729", "#997004", progress)
        hex_color = self._rgb_to_hex(blended)
        self.cues_liststore1[step + 1][9] = hex_color
        blended = self._blend_color("#997004", "#555555", progress)
        hex_color = self._rgb_to_hex(blended)
        self.cues_liststore1[step + 2][9] = hex_color
        if step < App().lightshow.main_playback.last - 2:
            blended = self._blend_color("#555555", "#232729", progress)
            hex_color = self._rgb_to_hex(blended)
            self.cues_liststore1[step + 3][9] = hex_color
        self.treeview1.queue_draw()

    def update_xfade_display(self, step: int) -> None:
        """Update Crossfade display

        Args:
            step: Step
        """
        self.sequential.total_time = (
            App().lightshow.main_playback.steps[step + 1].total_time
        )
        self.sequential.time_in = App().lightshow.main_playback.steps[step + 1].time_in
        self.sequential.time_out = (
            App().lightshow.main_playback.steps[step + 1].time_out
        )
        self.sequential.delay_in = (
            App().lightshow.main_playback.steps[step + 1].delay_in
        )
        self.sequential.delay_out = (
            App().lightshow.main_playback.steps[step + 1].delay_out
        )
        self.sequential.wait = App().lightshow.main_playback.steps[step + 1].wait
        self.sequential.channel_time = (
            App().lightshow.main_playback.steps[step + 1].channel_time
        )
        self.sequential.queue_draw()

    def on_key_press_event(self, widget: Gtk.Widget, event: Gdk.EventKey) -> Callable:
        """On key press event

        Args:
            widget: Gtk Widget
            event: Gdk.EventKey

        Returns:
            function() to handle keys pressed
        """
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Tab":
            return App().window.toggle_focus()
        if keyname == "ISO_Left_Tab":
            return App().window.move_tab()
        # Find open page in notebook to send keyboard events
        page = self.get_current_page()
        child = self.get_nth_page(page)
        if child in App().tabs.tabs.values():
            return child.on_key_press_event(widget, event)
        return App().window.on_key_press_event(widget, event)
