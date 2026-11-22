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
from typing import Optional

from gi.repository import Gdk, Gtk

from olc.core.tracking import (
    TRACKING_COLORS,
    TrackingDisplayState,
    TrackingEngine,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.define import MAX_CHANNELS, string_to_time, time_to_string
from olc.gtk3.dialog import ConfirmationDialog
from olc.gtk3.widgets.seq_channels_view import SeqChannelsView
from olc.show.sequence import Sequence

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow

__all__ = [
    "TRACKING_COLORS",
    "SeqChannelsView",
    "SequenceTab",
    "TrackingDisplayState",
    "classify_channel_tracking_state",
    "get_tracking_color",
]


# pylint: disable=too-many-instance-attributes, too-many-lines, too-many-public-methods
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
        self._setup_header_bar()
        self._setup_sequences_list()
        self._setup_cues_list()
        self.attach(self.header_box, 0, 0, 1, 1)
        self.attach_next_to(
            self.treeview1, self.header_box, Gtk.PositionType.BOTTOM, 1, 1
        )
        self.attach_next_to(self.paned, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1)

    def _setup_header_bar(self) -> None:
        """Create top control bar with Tracking vs Cue-Only and MIB switches."""
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.header_box.set_margin_start(6)
        self.header_box.set_margin_end(6)
        self.header_box.set_margin_top(4)
        self.header_box.set_margin_bottom(2)

        initial_tracking = getattr(self.lightshow.main_playback, "tracking_mode", False)
        self.tracking_mode_btn = Gtk.ToggleButton(
            label="Mode: Tracking" if initial_tracking else "Mode: Cue-Only"
        )
        self.tracking_mode_btn.set_active(initial_tracking)
        self.tracking_mode_btn.connect("toggled", self._on_tracking_mode_toggled)
        self.header_box.pack_start(self.tracking_mode_btn, False, False, 0)

        initial_mib = getattr(self.lightshow.main_playback, "mib_enabled", True)
        self.mib_btn = Gtk.ToggleButton(label="MIB: ON" if initial_mib else "MIB: OFF")
        self.mib_btn.set_active(initial_mib)
        self.mib_btn.connect("toggled", self._on_mib_toggled)
        self.header_box.pack_start(self.mib_btn, False, False, 0)

    def _on_tracking_mode_toggled(self, button: Gtk.ToggleButton) -> None:
        self.set_tracking_mode(button.get_active())

    def set_tracking_mode(self, enabled: bool) -> None:
        """Set Tracking mode (True) or Cue-Only mode (False) on active sequence."""
        seq = self.get_selected_sequence() or self.lightshow.main_playback
        self.window.app.core.action_registry.execute(
            "sequence.set_tracking_mode", seq.index, enabled
        )
        if self.tracking_mode_btn.get_active() != enabled:
            self.tracking_mode_btn.set_active(enabled)
        self.tracking_mode_btn.set_label(
            "Mode: Tracking" if enabled else "Mode: Cue-Only"
        )
        self.channels_view.flowbox.invalidate_filter()
        self.channels_view.flowbox.queue_draw()
        if hasattr(self, "liststore2"):
            self.on_sequence_changed(step_idx=self.get_selected_step())

    def toggle_tracking_mode(self) -> bool:
        """Toggle between Cue-Only and Tracking mode and return new state."""
        seq = self.get_selected_sequence() or self.lightshow.main_playback
        new_state = not getattr(seq, "tracking_mode", False)
        self.set_tracking_mode(new_state)
        return new_state

    def _on_mib_toggled(self, button: Gtk.ToggleButton) -> None:
        self.set_mib_enabled(button.get_active())

    def set_mib_enabled(self, enabled: bool) -> None:
        """Enable or disable Move In Black (MIB) on active sequence."""
        seq = self.get_selected_sequence() or self.lightshow.main_playback
        self.window.app.core.action_registry.execute(
            "sequence.set_mib_enabled", seq.index, enabled
        )
        if self.mib_btn.get_active() != enabled:
            self.mib_btn.set_active(enabled)
        self.mib_btn.set_label("MIB: ON" if enabled else "MIB: OFF")
        self.channels_view.flowbox.invalidate_filter()
        self.channels_view.flowbox.queue_draw()

    def toggle_mib_mode(self) -> bool:
        """Toggle Move In Black (MIB) mode and return new state."""
        seq = self.get_selected_sequence() or self.lightshow.main_playback
        new_state = not getattr(seq, "mib_enabled", True)
        self.set_mib_enabled(new_state)
        return new_state

    def _setup_sequences_list(self) -> None:
        """Setup the sequence selection list"""
        self.liststore1 = Gtk.ListStore(int, str)
        self.liststore1.append(
            [
                self.lightshow.main_playback.index,
                self.lightshow.main_playback.text,
            ]
        )
        for seq in self.lightshow.sequences:
            self.liststore1.append([seq.index, seq.text])

        self.treeview1 = Gtk.TreeView(model=self.liststore1)
        self.treeview1.set_enable_search(False)
        self.treeview1.get_selection().connect("changed", self.on_sequence_changed)

        for i, column_title in enumerate(["Seq", "Name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer)
            column.add_attribute(renderer, "text", i)
            self.treeview1.append_column(column)

    def _setup_cues_list(self) -> None:
        """Setup the cues layout"""
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.channels_view = SeqChannelsView(app=self.window.app)
        self.paned.add1(self.channels_view)

        self.liststore2 = Gtk.ListStore(
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            bool,
        )
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
            "Pos",
            "Color",
            "Beam",
            "Channel Time",
            "FX",
        ]
        edit_callbacks = {
            2: self.text_edited,
            3: self.wait_edited,
            4: self.delay_out_edited,
            5: self.out_edited,
            6: self.delay_in_edited,
            7: self.in_edited,
            8: self.pos_edited,
            9: self.color_edited,
            10: self.beam_edited,
        }
        for i, column_title in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))

            if i in edit_callbacks:
                renderer.set_property("editable", True)
                renderer.connect("edited", edit_callbacks[i])
                renderer.connect("editing-started", self._on_editing_started)

            column = Gtk.TreeViewColumn(column_title, renderer)
            column.add_attribute(renderer, "text", i)
            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)
            elif i == 12:
                column.add_attribute(renderer, "foreground", 13)
                column.add_attribute(renderer, "foreground-set", 14)

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
                self.lightshow.main_playback.text,
            ]
        )
        for seq in self.lightshow.sequences:
            self.liststore1.append([seq.index, seq.text])
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
                sequence = self.lightshow.get_sequence(sequence_number)
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
        if col_nb == 11:
            sequence = self.get_selected_sequence()
            step_str = self.liststore2[path][0]
            if sequence and step_str:
                step = int(step_str)
                self.window.app.channeltime(sequence, step)

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

    def pos_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Position family time edited (empty string resets to inherited None)."""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = -1.0 if text.strip() == "" else string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, time_position=time
        )

    def color_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Color family time edited (empty string resets to inherited None)."""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = -1.0 if text.strip() == "" else string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, time_color=time
        )

    def beam_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Beam family time edited (empty string resets to inherited None)."""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        time = -1.0 if text.strip() == "" else string_to_time(text)
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, time_beam=time
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

    def _on_editing_started(
        self,
        _renderer: Gtk.CellRenderer,
        editable: Gtk.CellEditable,
        _path: str,
    ) -> None:
        """Grab focus on editable when cell editing begins."""
        if isinstance(editable, Gtk.Widget):
            editable.grab_focus()

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

    def _keypress_backspace(self) -> None:
        """Empty keys buffer"""
        self.app.core.action_registry.execute("commandline.clear")

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
        self.app.core.action_registry.execute("commandline.clear")

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

    def rename_selected(self) -> None:
        """Start editing the text cell of the selected step."""
        path, _focus_column = self.treeview2.get_cursor()
        col = self.treeview2.get_column(2)
        if path is not None and col is not None:
            self.treeview2.grab_focus()
            self.treeview2.set_cursor(path, col, True)

    def _keypress_f2(self) -> None:
        """Rename selected Step."""
        self.rename_selected()

    def _keypress_n(self) -> None:
        """New secondary Sequence."""
        index_seq = (
            self.lightshow.sequences[-1].index + 1
            if len(self.lightshow.sequences) > 0
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
                cue_val = sequence.get_next_cue(step=step)
                assert cue_val is not None
                cue_num = cue_val
                step += 1
            else:
                cue_num = 1.0
                step = 1
        else:
            cue_num = float(keystring)
            found, step = sequence.get_step(cue=cue_num)
            self.app.core.action_registry.execute("commandline.clear")

        if not found:
            self._create_cue(sequence, cue_num, step)
        else:
            self._update_cue(sequence, cue_num)

    def _create_cue(self, sequence: Sequence, cue_num: float, step: int) -> None:
        """Create new cue inside the sequence"""
        channels = {}
        for channel in range(MAX_CHANNELS):
            widget_ch = self.channels_view.get_channel_widget(channel + 1)
            if widget_ch is not None:
                channel_widget = widget_ch
                if channel_widget.level:
                    channels[channel + 1] = channel_widget.level

        self.window.app.core.action_registry.execute(
            "sequence.insert_step", sequence.index, step, cue_num, channels
        )
        self.window.app.core.action_registry.execute(
            "cue.clear_editor", cue_num, int(sequence.index)
        )

    def _update_cue(self, sequence: Sequence, cue_num: float) -> None:
        """Update existing cue inside the sequence"""
        dialog = ConfirmationDialog(f"Update cue {cue_num} ?", self.window)
        response = dialog.run()
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return

        step_idx = sequence.get_step(cue=cue_num)[1]
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

    @staticmethod
    def _format_family_time(val: Optional[float]) -> str:
        """Format an optional family transition time for TreeView display."""
        if val is None:
            return ""
        if val == 0.0:
            return "0"
        return time_to_string(val)

    @staticmethod
    def _format_step_fx_status(sequence: Sequence, step: int) -> tuple[str, str | None]:
        """Return (label, foreground_hex) summarizing effects for a sequence step."""
        cue = sequence.steps[step].cue
        if cue is None:
            return "", None

        raw_refs = getattr(cue, "effect_refs", None)
        started_fx: set[float] = set()
        has_stop = False
        if isinstance(raw_refs, dict):
            for spec in raw_refs.values():
                if not isinstance(spec, dict):
                    continue
                if spec.get("stop"):
                    has_stop = True
                    continue
                fx_num = spec.get("effect")
                if fx_num is None:
                    fx_num = spec.get("effect_number")
                if fx_num is not None:
                    started_fx.add(float(fx_num))

        tracked_only_fx: set[float] = set()
        if getattr(sequence, "tracking_mode", False):
            resolved = TrackingEngine.resolve_step_effects(
                sequence, step, tracking_mode=True
            )
            resolved_fx: set[float] = set()
            for spec in resolved.values():
                if not isinstance(spec, dict) or spec.get("stop"):
                    continue
                fx_num = spec.get("effect")
                if fx_num is None:
                    fx_num = spec.get("effect_number")
                if fx_num is not None:
                    resolved_fx.add(float(fx_num))
            tracked_only_fx = resolved_fx - started_fx

        def _fmt_fx(nums: set[float]) -> str:
            return ",".join(
                str(int(n)) if n.is_integer() else f"{n:g}" for n in sorted(nums)
            )

        parts: list[str] = []
        if started_fx:
            parts.append(f"FX {_fmt_fx(started_fx)}")
        if tracked_only_fx:
            parts.append(f"FX {_fmt_fx(tracked_only_fx)} (T)")
        if has_stop:
            parts.append("Stop FX")

        if not parts:
            return "", None
        label = " / ".join(parts)
        if started_fx:
            return label, "#E59933"
        if tracked_only_fx and not has_stop:
            return label, "#33D9F2"
        return label, "#F25959"

    def add_step_to_liststore(self, step: int) -> None:
        """Add Step to the list

        Args:
            step: Step
        """
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step_obj = sequence.steps[step]
        wait = time_to_string(step_obj.wait)
        t_out = time_to_string(step_obj.time_out)
        d_out = time_to_string(step_obj.delay_out)
        t_in = time_to_string(step_obj.time_in)
        d_in = time_to_string(step_obj.delay_in)
        t_pos = self._format_family_time(step_obj.time_position)
        t_color = self._format_family_time(step_obj.time_color)
        t_beam = self._format_family_time(step_obj.time_beam)
        channel_time = str(len(step_obj.channel_time))
        if channel_time == "0":
            channel_time = ""
        cue = step_obj.cue
        cue_number = str(cue.number) if cue is not None else ""
        fx_text, fx_color = self._format_step_fx_status(sequence, step)
        self.liststore2.insert(
            step - 1,
            [
                str(step),
                cue_number,
                step_obj.text,
                wait,
                d_out,
                t_out,
                d_in,
                t_in,
                t_pos,
                t_color,
                t_beam,
                channel_time,
                fx_text,
                fx_color,
                fx_color is not None,
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
