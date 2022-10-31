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
from gi.repository import Gdk, Gtk, Pango
from olc.define import App
from olc.widgets_sequential import SequentialWidget


def on_page_added(notebook, _child, _page_num):
    """Get focus

    Args:
        notebook: Gtk Notebook
    """
    notebook.grab_focus()


def step_filter_func1(model, treeiter, _data):
    """Filter for the first part of the cues list

    Args:
        model: Model
        treeiter: Treeiter

    Returns:
        True, False or step
    """
    if App().sequence.position <= 0:
        if int(model[treeiter][11]) in [0, 1]:
            return True
        return int(model[treeiter][0]) in [0, 1]
    if App().sequence.position == 1:
        if int(model[treeiter][11]) == 1:
            return True
        if int(model[treeiter][11]) == 0:
            return False
        return int(model[treeiter][0]) in [0, 1, 2]
    if int(model[treeiter][11]) in [0, 1]:
        return False

    return int(model[treeiter][0]) in [
        App().sequence.position,
        App().sequence.position + 1,
        App().sequence.position - 1,
        App().sequence.position - 2,
    ]


def step_filter_func2(model, treeiter, _data):
    """Filter for the second part of the cues list

    Args:
        model: Model
        treeiter: Treeiter

    Returns:
        True or False
    """
    return int(model[treeiter][0]) > App().sequence.position + 1


class MainPlaybackView(Gtk.Notebook):
    """Main Playback View"""

    def __init__(self):
        Gtk.Notebook.__init__(self)
        self.set_group_name("olc")

        # Sequential part of the window
        if App().sequence.last > 1:
            position = App().sequence.position
            t_total = App().sequence.steps[position].total_time
            t_in = App().sequence.steps[position].time_in
            t_out = App().sequence.steps[position].time_out
            d_in = App().sequence.steps[position].delay_in
            d_out = App().sequence.steps[position].delay_out
            t_wait = App().sequence.steps[position].wait
            channel_time = App().sequence.steps[position].channel_time
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
        self.cues_liststore2 = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str
        )
        # Filters
        self.step_filter1 = self.cues_liststore1.filter_new()
        self.step_filter1.set_visible_func(step_filter_func1)
        self.step_filter2 = self.cues_liststore2.filter_new()
        self.step_filter2.set_visible_func(step_filter_func2)
        # Lists
        self.treeview1 = Gtk.TreeView(model=self.step_filter1)
        self.treeview1.connect("focus-in-event", self.on_focus)
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
        self.treeview2.connect("focus-in-event", self.on_focus)
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

        if App().sequence.last == 1:
            self.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )

        self.append_page(self.grid, Gtk.Label("Main Playback"))
        self.set_tab_reorderable(self.grid, True)
        self.set_tab_detachable(self.grid, True)

        self.connect("key_press_event", self.on_key_press_event)
        self.connect("page-added", on_page_added)
        self.connect("page-removed", on_page_added)

    def on_focus(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Give focus to notebook

        Returns:
            False
        """
        self.grab_focus()
        return False

    def update_sequence_display(self):
        """Update Sequence display"""
        self.cues_liststore1.clear()
        self.cues_liststore2.clear()
        self.populate_sequence()

    def populate_sequence(self):
        """Display main playback"""
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
        )
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
        )
        for i in range(App().sequence.last):
            wait = (
                str(int(App().sequence.steps[i].wait))
                if App().sequence.steps[i].wait.is_integer()
                else str(App().sequence.steps[i].wait)
            )
            if wait == "0":
                wait = ""
            t_out = (
                int(App().sequence.steps[i].time_out)
                if App().sequence.steps[i].time_out.is_integer()
                else App().sequence.steps[i].time_out
            )
            d_out = (
                str(int(App().sequence.steps[i].delay_out))
                if App().sequence.steps[i].delay_out.is_integer()
                else str(App().sequence.steps[i].delay_out)
            )
            if d_out == "0":
                d_out = ""
            t_in = (
                int(App().sequence.steps[i].time_in)
                if App().sequence.steps[i].time_in.is_integer()
                else App().sequence.steps[i].time_in
            )
            d_in = (
                str(int(App().sequence.steps[i].delay_in))
                if App().sequence.steps[i].delay_in.is_integer()
                else str(App().sequence.steps[i].delay_in)
            )
            if d_in == "0":
                d_in = ""
            channel_time = str(len(App().sequence.steps[i].channel_time))
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
            if i in (0, App().sequence.last - 1):
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
                self.cues_liststore2.append([str(i), "", "", "", "", "", "", "", ""])
            else:
                self.cues_liststore1.append(
                    [
                        str(i),
                        str(App().sequence.steps[i].cue.memory),
                        str(App().sequence.steps[i].text),
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
                self.cues_liststore2.append(
                    [
                        str(i),
                        str(App().sequence.steps[i].cue.memory),
                        str(App().sequence.steps[i].text),
                        wait,
                        d_out,
                        str(t_out),
                        d_in,
                        str(t_in),
                        channel_time,
                    ]
                )
        self.update_active_cues_display()
        self.grid.queue_draw()

    def update_active_cues_display(self):
        """Update First part of sequential"""
        self.cues_liststore1[App().sequence.position][9] = "#232729"
        self.cues_liststore1[App().sequence.position + 1][9] = "#232729"
        self.cues_liststore1[App().sequence.position + 2][9] = "#997004"
        self.cues_liststore1[App().sequence.position + 3][9] = "#555555"
        self.cues_liststore1[App().sequence.position][10] = Pango.Weight.NORMAL
        self.cues_liststore1[App().sequence.position + 1][10] = Pango.Weight.NORMAL
        self.cues_liststore1[App().sequence.position + 2][10] = Pango.Weight.HEAVY
        self.cues_liststore1[App().sequence.position + 3][10] = Pango.Weight.HEAVY
        self.step_filter1.refilter()
        self.step_filter2.refilter()
        path1 = Gtk.TreePath.new_from_indices([App().sequence.position + 2])
        path2 = Gtk.TreePath.new_from_indices([0])
        self.treeview1.set_cursor(path1, None, False)
        self.treeview2.set_cursor(path2, None, False)

    def update_xfade_display(self, step):
        """Update Crossfade display

        Args:
            step: Step
        """
        self.sequential.total_time = App().sequence.steps[step + 1].total_time
        self.sequential.time_in = App().sequence.steps[step + 1].time_in
        self.sequential.time_out = App().sequence.steps[step + 1].time_out
        self.sequential.delay_in = App().sequence.steps[step + 1].delay_in
        self.sequential.delay_out = App().sequence.steps[step + 1].delay_out
        self.sequential.wait = App().sequence.steps[step + 1].wait
        self.sequential.channel_time = App().sequence.steps[step + 1].channel_time
        self.sequential.queue_draw()

    def on_key_press_event(self, widget, event):
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
        # Find open page in notebook to send keyboard events
        page = self.get_current_page()
        child = self.get_nth_page(page)
        if child == App().patch_outputs_tab:
            return App().patch_outputs_tab.on_key_press_event(widget, event)
        if child == App().patch_channels_tab:
            return App().patch_channels_tab.on_key_press_event(widget, event)
        if child == App().group_tab:
            return App().group_tab.on_key_press_event(widget, event)
        if child == App().sequences_tab:
            return App().sequences_tab.on_key_press_event(widget, event)
        if child == App().channeltime_tab:
            return App().channeltime_tab.on_key_press_event(widget, event)
        if child == App().track_channels_tab:
            return App().track_channels_tab.on_key_press_event(widget, event)
        if child == App().memories_tab:
            return App().memories_tab.on_key_press_event(widget, event)
        if child == App().masters_tab:
            return App().masters_tab.on_key_press_event(widget, event)
        if child == App().inde_tab:
            return App().inde_tab.on_key_press_event(widget, event)

        return App().window.on_key_press_event(widget, event)
