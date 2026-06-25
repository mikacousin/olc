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
from __future__ import annotations

import typing
from typing import Callable, Optional

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, is_int, string_to_time, time_to_string
from olc.gtk3.dialog import ConfirmationDialog
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView
from olc.sequence import Sequence

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.widgets.channel import ChannelWidget
    from olc.gtk3.window import Window


# pylint: disable=too-many-instance-attributes, too-many-lines
class SequenceTab(Gtk.Grid):
    """Tab to edit sequences"""

    app: Application
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    commandline: CoreCommandLine

    def __init__(self, app: Application) -> None:
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.commandline = app.core.commandline

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self._setup_sequences_list()
        self._setup_cues_list()
        self.attach(self.treeview1, 0, 0, 1, 1)
        self.attach_next_to(self.paned, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1)

    def _setup_sequences_list(self) -> None:
        """Setup the sequence selection list"""
        self.liststore1 = Gtk.ListStore(int, str, str)
        self.liststore1.append(
            [
                self.lightshow.main_playback.index,
                self.lightshow.main_playback.type_seq,
                self.lightshow.main_playback.text,
            ]
        )
        for chaser in self.lightshow.chasers:
            self.liststore1.append([chaser.index, chaser.type_seq, chaser.text])

        self.treeview1 = Gtk.TreeView(model=self.liststore1)
        self.treeview1.set_enable_search(False)
        self.treeview1.get_selection().connect("changed", self.on_sequence_changed)

        for i, column_title in enumerate(["Seq", "Type", "Name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview1.append_column(column)

    def _setup_cues_list(self) -> None:
        """Setup the cues layout"""
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.channels_view = SeqChannelsView(app=self.window.app)
        self.paned.add1(self.channels_view)

        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)
        self.treeview2 = Gtk.TreeView(model=self.liststore2)
        self.treeview2.set_enable_search(False)
        self.treeview2.connect("cursor-changed", self.on_cue_changed)
        self.treeview2.connect("row-activated", self.on_row_activated)

        columns = [
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
        for i, column_title in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))

            if i in (2, 3, 4, 5, 6, 7):
                renderer.set_property("editable", True)
                if i == 2:
                    renderer.connect("edited", self.text_edited)
                elif i == 3:
                    renderer.connect("edited", self.wait_edited)
                elif i == 4:
                    renderer.connect("edited", self.delay_out_edited)
                elif i == 5:
                    renderer.connect("edited", self.out_edited)
                elif i == 6:
                    renderer.connect("edited", self.delay_in_edited)
                elif i == 7:
                    renderer.connect("edited", self.in_edited)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)

            self.treeview2.append_column(column)

        self.scrollable2 = Gtk.ScrolledWindow()
        self.scrollable2.set_vexpand(True)
        self.scrollable2.set_hexpand(True)
        self.scrollable2.add(self.treeview2)
        self.paned.add2(self.scrollable2)

    def refresh(self) -> None:
        """Refresh display"""
        selected_seq_index = None
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            row = path.get_indices()[0]
            if row < len(self.liststore1):
                selected_seq_index = self.liststore1[row][0]

        self.liststore1.clear()
        self.liststore1.append(
            [
                self.lightshow.main_playback.index,
                self.lightshow.main_playback.type_seq,
                self.lightshow.main_playback.text,
            ]
        )
        for chaser in self.lightshow.chasers:
            self.liststore1.append([chaser.index, chaser.type_seq, chaser.text])
        self.treeview1.set_model(self.liststore1)

        selected_iter = None
        if selected_seq_index is not None:
            for row in self.liststore1:
                if row[0] == selected_seq_index:
                    selected_iter = row.iter
                    break

        if selected_iter is not None:
            path = self.liststore1.get_path(selected_iter)
            self.treeview1.set_cursor(path, None, False)
        else:
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
            if sequence_number == 1:
                sequence = self.lightshow.main_playback
            else:
                for chaser in self.lightshow.chasers:
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
        if not treeiter:
            return None
        try:
            step = int(model[treeiter][0])
            sequence = self.get_selected_sequence()
            if sequence and 0 <= step < len(sequence.steps):
                return step
        except (IndexError, ValueError, TypeError):
            pass
        return None

    def on_row_activated(
        self, _treeview: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn
    ) -> None:
        """Open Channel Time Edition if double clicked

        Args:
            path: Gtk.TreePath
            column: Column number
        """
        # Find double clicked cell
        columns = self.treeview2.get_columns()
        col_nb = 0
        for col in columns:
            if col == column:
                break
            col_nb += 1
        # Double click on Channel Time
        if col_nb == 8:
            sequence = self.get_selected_sequence()
            step_str = self.liststore2[path][0]
            if sequence and step_str:
                step = int(step_str)
                self.window.app.channeltime(sequence, step)

    def update_total_time(self, sequence: Sequence, step_number: int) -> None:
        """Update Step total time

        Args:
            sequence: Modified sequence
            step_number: Step number
        """
        step = sequence.steps[step_number]
        if step.time_in + step.delay_in > step.time_out + step.delay_out:
            step.total_time = step.time_in + step.wait + step.delay_in
        else:
            step.total_time = step.time_out + step.wait + step.delay_out
        for channel in step.channel_time.keys():
            t = (
                step.channel_time[channel].delay
                + step.channel_time[channel].time
                + step.wait
            )
            step.total_time = max(step.total_time, t)

    def wait_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Wait edited"""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, wait=time
        )

    def out_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Time Out edited"""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, time_out=time
        )

    def in_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Time in edited"""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, time_in=time
        )

    def delay_out_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Delay Out edited"""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, delay_out=time
        )

    def delay_in_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Delay In edited"""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, delay_in=time
        )

    def text_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Step Text edited"""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        self.window.app.core.action_registry.execute(
            "step.update_text", sequence.index, step, text
        )

    def on_cue_changed(self, _treeview: Gtk.TreeView) -> None:
        """Select cue"""
        self.channels_view.update()

    def on_sequence_changed(
        self, _selection: Gtk.TreeSelection | None = None, step_idx: int | None = None
    ) -> None:
        """Select Sequence"""
        # Detach model to avoid multiple layout updates during population
        self.treeview2.set_model(None)
        # Empty ListStore
        self.liststore2.clear()
        if step_idx is None:
            step_idx = self.get_selected_step()
        if step_idx is None:
            step_idx = 1
        # Display Sequence
        self.populate_liststore(step_idx)

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        self.tabs.close("sequences")

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Receive keyboard event

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        # Hack to know if user is editing something
        widget = self.window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.commandline.add_string(keyname)

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
            self.commandline.add_string(keyname[3:])

        if keyname == "period":
            self.commandline.add_string(".")

        # Channels View
        self.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        self.tabs.close("sequences")

    def _keypress_backspace(self) -> None:
        """Empty keys buffer"""
        self.commandline.set_string("")

    def _keypress_s(self) -> None:
        """Cycle Sequences"""
        path, _focus_column = self.treeview1.get_cursor()
        if path:
            path.next()
        else:
            path = Gtk.TreePath.new_first()
        self.treeview1.set_cursor(path)
        path = Gtk.TreePath.new_first()
        self.treeview2.set_cursor(path)

    def _keypress_q(self) -> None:
        """Previous Cue"""
        path, _focus_column = self.treeview2.get_cursor()
        if path:
            if path.prev():
                self.treeview2.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

    def _keypress_w(self) -> None:
        """Next Cue"""
        path, _focus_column = self.treeview2.get_cursor()
        if path:
            path.next()
        else:
            path = Gtk.TreePath.new_first()

        self.treeview2.set_cursor(path)

    def _keypress_equal(self) -> None:
        """@ Level"""
        self.channels_view.at_level()
        self.channels_view.update()
        self.commandline.set_string("")

    def _keypress_colon(self) -> None:
        """Level - %"""
        self.channels_view.level_minus()
        self.channels_view.update()

    def _keypress_exclam(self) -> None:
        """Level + %"""
        self.channels_view.level_plus()
        self.channels_view.update()

    def _keypress_u(self) -> None:
        """Update Cue"""
        sequence = self.get_selected_sequence()
        step = self.get_selected_step()
        if not sequence or step is None:
            return
        cue = sequence.steps[step].cue
        if cue is None:
            return
        dialog = ConfirmationDialog(f"Update cue {cue.number} ?", self.window)
        response = dialog.run()
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return

        cue_editor = self.lightshow.cues.cue_editor
        user_channels = cue_editor.get_levels(cue.number, cue.sequence)

        new_channels = dict(cue.channels)
        for channel in range(MAX_CHANNELS):
            widget_ch = self.channels_view.get_channel_widget(channel + 1)
            if widget_ch is not None:
                channel_widget = widget_ch
                if (channel + 1 in cue.channels) or (user_channels[channel] != -1):
                    new_channels[channel + 1] = channel_widget.level

        self.window.app.core.action_registry.execute(
            "cue.update", cue.number, cue.sequence, new_channels
        )
        dialog.destroy()

    def _keypress_delete(self) -> None:
        """Delete selected Step"""
        sequence = self.get_selected_sequence()
        step = self.get_selected_step()
        if sequence and step is not None:
            self.window.app.core.action_registry.execute(
                "sequence.delete_step", sequence.index, step
            )

    def _keypress_n(self) -> None:
        """New Chaser"""
        index_seq = (
            self.lightshow.chasers[-1].index + 1
            if len(self.lightshow.chasers) > 0
            else 2
        )
        self.window.app.core.action_registry.execute("sequence.new", index_seq)

    def _keypress_r(self) -> None:
        """New Step and new Cue"""
        found = False
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = self.get_selected_step()
        keystring = self.commandline.get_string()
        if keystring == "":
            if step:
                mem_val = sequence.get_next_cue(step=step)
                assert mem_val is not None
                mem = mem_val
                step += 1
            else:
                mem = 1.0
                step = 1
        else:
            mem = float(keystring)
            found, step = sequence.get_step(cue=mem)
            self.commandline.set_string("")

        if not found:
            self._create_cue(sequence, mem, step)
        else:
            self._update_cue(sequence, mem)

    def _create_cue(self, sequence: Sequence, mem: float, step: int) -> None:
        """Create new cue inside the sequence"""
        channels = {}
        for channel in range(MAX_CHANNELS):
            widget_ch = self.channels_view.get_channel_widget(channel + 1)
            if widget_ch is not None:
                channel_widget = widget_ch
                if channel_widget.level:
                    channels[channel + 1] = channel_widget.level

        self.window.app.core.action_registry.execute(
            "sequence.insert_step", sequence.index, step, mem, channels
        )
        self.lightshow.cues.cue_editor.clear(mem, int(sequence.index))

    def _update_cue(self, sequence: Sequence, mem: float) -> None:
        """Update existing cue inside the sequence"""
        dialog = ConfirmationDialog(f"Update cue {mem} ?", self.window)
        response = dialog.run()
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return

        step_idx = sequence.get_step(cue=mem)[1]
        cue = sequence.steps[step_idx].cue
        if cue is None:
            dialog.destroy()
            return

        cue_editor = self.lightshow.cues.cue_editor
        user_channels = cue_editor.get_levels(cue.number, cue.sequence)

        new_channels = dict(cue.channels)
        for channel in range(MAX_CHANNELS):
            widget_ch = self.channels_view.get_channel_widget(channel + 1)
            if widget_ch is not None:
                channel_widget = widget_ch
                if (channel + 1 in cue.channels) or (user_channels[channel] != -1):
                    new_channels[channel + 1] = channel_widget.level

        self.window.app.core.action_registry.execute(
            "cue.update", cue.number, cue.sequence, new_channels
        )
        dialog.destroy()

    def add_step_to_liststore(self, step: int) -> None:
        """Add Step to the list

        Args:
            step: Step
        """
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        wait = time_to_string(sequence.steps[step].wait)
        t_out = time_to_string(sequence.steps[step].time_out)
        d_out = time_to_string(sequence.steps[step].delay_out)
        t_in = time_to_string(sequence.steps[step].time_in)
        d_in = time_to_string(sequence.steps[step].delay_in)
        channel_time = str(len(sequence.steps[step].channel_time))
        if channel_time == "0":
            channel_time = ""
        cue = sequence.steps[step].cue
        cue_number = str(cue.number) if cue is not None else ""
        self.liststore2.insert(
            step - 1,
            [
                str(step),
                cue_number,
                sequence.steps[step].text,
                wait,
                d_out,
                t_out,
                d_in,
                t_in,
                channel_time,
            ],
        )

    def populate_liststore(self, step: int) -> None:
        """Populate liststore with steps

        Args:
            step: Step
        """
        if sequence := self.get_selected_sequence():
            if sequence == self.lightshow.main_playback:
                for i in range(sequence.last)[1:-1]:
                    self.add_step_to_liststore(i)
            else:
                for i in range(sequence.last)[1:]:
                    self.add_step_to_liststore(i)

        self.treeview2.set_model(self.liststore2)
        # Select new step
        path = Gtk.TreePath.new_from_indices([step - 1])
        self.treeview2.set_cursor(path, None, False)
        # Tag filename as modified
        self.lightshow.set_modified()

    def update_sequence_display(self, step: int) -> None:
        """Update Sequence display

        Args:
            step: Step
        """
        self.add_step_to_liststore(step)
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        # Update Main Playback
        if sequence is self.lightshow.main_playback:
            # Update indexes of cues in liststore
            for i in range(step, sequence.last - 2):
                self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)
            # Update Main Tab
            self.window.playback.update_sequence_display()
            if self.lightshow.main_playback.position + 1 == step:
                # Update Crossfade
                self.window.playback.update_xfade_display(step - 1)
                # Update Channels Tab
                self.window.update_channels_display(step - 1)
        # Update Chasers
        else:
            # Update indexes of cues in liststore
            for i in range(step, sequence.last - 1):
                self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)
        # Select new step
        path = Gtk.TreePath.new_from_indices([step - 1])
        self.treeview2.set_cursor(path, None, False)


class SeqChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self, app: Application) -> None:
        self._cache_time: float = 0.0
        self._cached_sequence: Sequence | None = None
        self._cached_step: int | None = None
        super().__init__(app=app)

    def _get_cached_selection(self) -> tuple[Optional[Sequence], Optional[int]]:
        """Get cached selected sequence and step to avoid heavy GTK calls."""
        import time  # pylint: disable=import-outside-toplevel

        now = time.time()
        if now - self._cache_time > 0.05:
            if self.tabs is not None and self.tabs.tabs.get("sequences") is not None:
                tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
                self._cached_sequence = tab.get_selected_sequence()
                self._cached_step = tab.get_selected_step()
            else:
                self._cached_sequence = None
                self._cached_step = None
            self._cache_time = now
        return self._cached_sequence, self._cached_step

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level"""
        if self.tabs is not None:
            tab = typing.cast(SequenceTab, self.tabs.tabs["sequences"])
            seq = tab.get_selected_sequence()
            step_idx = tab.get_selected_step()
            if seq and step_idx is not None:
                step = seq.steps[step_idx]
                if step.cue and self.window is not None:
                    self.window.app.core.action_registry.execute(
                        "cue.set_temp_channels",
                        step.cue.number,
                        step.cue.sequence,
                        {channel: level},
                    )

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel using a group action."""
        if self.tabs is None or self.lightshow is None or self.window is None:
            return
        tab = typing.cast(SequenceTab, self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step_obj = seq.steps[step_idx]
        if step_obj.cue is None:
            return

        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if direction == Gdk.ScrollDirection.UP:
                    level = min(level + step, 255)
                elif direction == Gdk.ScrollDirection.DOWN:
                    level = max(level - step, 0)
                channels_dict[channel] = level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step_obj.cue.number,
                step_obj.cue.sequence,
                channels_dict,
            )

    def at_level(self) -> None:
        """Channels at level using a group action."""
        if (
            not self.window
            or not self.settings
            or self.tabs is None
            or self.lightshow is None
        ):
            return
        tab = typing.cast(SequenceTab, self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step = seq.steps[step_idx]
        if step.cue is None:
            return

        keystring = self.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if self.settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        channels_dict = {channel: level for channel in channels}

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step.cue.number,
                step.cue.sequence,
                channels_dict,
            )

    def level_plus(self) -> None:
        """Channels +% using a group action."""
        if (
            not self.settings
            or self.tabs is None
            or self.lightshow is None
            or self.window is None
        ):
            return
        tab = typing.cast(SequenceTab, self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step = seq.steps[step_idx]
        if step.cue is None:
            return

        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                channels_dict[channel] = new_level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step.cue.number,
                step.cue.sequence,
                channels_dict,
            )

    def level_minus(self) -> None:
        """Channels -% using a group action."""
        if (
            not self.settings
            or self.tabs is None
            or self.lightshow is None
            or self.window is None
        ):
            return
        tab = typing.cast(SequenceTab, self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step = seq.steps[step_idx]
        if step.cue is None:
            return

        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                channels_dict[channel] = new_level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step.cue.number,
                step.cue.sequence,
                channels_dict,
            )

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Filter channels to display"""
        if not self.tabs or not self.tabs.tabs["sequences"]:
            child.set_visible(False)
            return False
        sequence, step = self._get_cached_selection()
        if not sequence or step is None or step >= len(sequence.steps) or step < 0:
            child.set_visible(False)
            return False
        channel = child.get_index() + 1
        cue = sequence.steps[step].cue
        channel_level = cue.channels.get(channel, 0) if cue is not None else 0
        if self.view_mode == VIEW_MODES["Active"]:
            return self._filter_active(child, channel_level)
        if self.view_mode == VIEW_MODES["Patched"]:
            return self._filter_patched(child, channel_level)
        return self._filter_all(child, channel_level)

    def _filter_active(self, child: Gtk.FlowBoxChild, channel_level: int) -> bool:
        """Filter in Active mode"""
        channel_index = child.get_index()
        widget = child.get_child()
        if widget is None:
            return False
        channel_widget = typing.cast("ChannelWidget", widget)
        assert self.tabs is not None
        assert self.lightshow is not None

        seq, step_idx = self._get_cached_selection()
        if seq and step_idx is not None:
            cue = seq.steps[step_idx].cue
            if cue:
                user_channel = self.lightshow.cues.cue_editor.get_levels(
                    cue.number, cue.sequence
                )[channel_index]
            else:
                user_channel = -1
        else:
            user_channel = -1

        if channel_level or child.is_selected():
            if user_channel == -1:
                channel_widget.level = channel_level
                channel_widget.next_level = channel_level
            else:
                channel_widget.level = user_channel
                channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        if user_channel != -1:
            channel_widget.level = user_channel
            channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(False)
        return False

    def _filter_patched(self, child: Gtk.FlowBoxChild, channel_level: int) -> bool:
        """Filter in Patched mode"""
        channel = child.get_index() + 1
        assert self.lightshow is not None
        if not self.lightshow.patch.is_patched(channel):
            child.set_visible(False)
            return False
        return self._filter_all(child, channel_level)

    def _filter_all(self, child: Gtk.FlowBoxChild, channel_level: int) -> bool:
        """Filter in All channels mode"""
        channel_index = child.get_index()
        widget = child.get_child()
        if widget is None:
            return False
        channel_widget = typing.cast("ChannelWidget", widget)
        assert self.tabs is not None
        assert self.lightshow is not None

        seq, step_idx = self._get_cached_selection()
        if seq and step_idx is not None:
            cue = seq.steps[step_idx].cue
            if cue:
                user_channel = self.lightshow.cues.cue_editor.get_levels(
                    cue.number, cue.sequence
                )[channel_index]
            else:
                user_channel = -1
        else:
            user_channel = -1

        if channel_level or child.is_selected():
            if user_channel == -1:
                channel_widget.level = channel_level
                channel_widget.next_level = channel_level
            else:
                channel_widget.level = user_channel
                channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        if user_channel != -1:
            channel_widget.level = user_channel
            channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True
