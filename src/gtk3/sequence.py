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

from gi.repository import Gdk, Gtk, Pango

from olc.core.playback_arbitrator import PlaybackPriority
from olc.core.tracking import (
    TRACKING_COLORS,
    TrackingDisplayState,
    TrackingEngine,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.define import MAX_CHANNELS, string_to_time, time_to_string
from olc.gtk3.dialog import ConfirmationDialog
from olc.gtk3.widgets.curve import get_curve_display_name
from olc.gtk3.widgets.curve_popover import CurveSelectionPopover
from olc.gtk3.widgets.seq_channels_view import SeqChannelsView
from olc.show.sequence import Sequence

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow
    from olc.show.step import Step

__all__ = [
    "TRACKING_COLORS",
    "SeqChannelsView",
    "SequenceTab",
    "TrackingDisplayState",
    "classify_channel_tracking_state",
    "get_tracking_color",
]


def format_step_tooltip(step_obj: Step, title: str) -> str | None:
    """Return detailed tooltip text for a step column, or None if not applicable."""
    if title == "Channel Time" and step_obj.channel_time:
        lines = []
        for ch in sorted(step_obj.channel_time):
            ct = step_obj.channel_time[ch]
            d_str = time_to_string(ct.delay)
            t_str = time_to_string(ct.time)
            lines.append(
                f"Ch {ch}: {d_str}/{t_str}s" if ct.delay else f"Ch {ch}: {t_str}s"
            )
        return "\n".join(lines[:20])

    family_map = {"Pos": "position", "Color": "color", "Beam": "beam"}
    if title in family_map:
        fam = family_map[title]
        d_val = getattr(step_obj, f"delay_{fam}")
        t_val = getattr(step_obj, f"time_{fam}")
        if d_val is not None or t_val is not None:
            d_txt = SequenceTab._format_family_time(d_val) or "inherited"
            t_txt = SequenceTab._format_family_time(t_val) or "inherited"
            return f"{title} — Delay: {d_txt}  Time: {t_txt}"

    cue = step_obj.cue
    if title == "Flags" and cue is not None:
        names = []
        if cue.is_block:
            names.append("Block (B)")
        if cue.is_int_block:
            names.append("Intensity Block (IB)")
        if cue.is_assert:
            names.append("Assert (A)")
        if names:
            return ", ".join(names)

    if title == "Notes" and cue is not None and cue.notes:
        return cue.notes

    return None


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
        self._updating_flag_btns: bool = False
        self._setup_header_bar()
        self._setup_sequences_list()
        self._setup_cues_list()
        header_scroll = Gtk.ScrolledWindow()
        header_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        header_scroll.set_shadow_type(Gtk.ShadowType.NONE)
        header_scroll.add(self.header_box)

        seq_scroll = Gtk.ScrolledWindow()
        seq_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        seq_scroll.set_min_content_height(90)
        seq_scroll.add(self.treeview1)

        self.attach(header_scroll, 0, 0, 1, 1)
        self.attach_next_to(seq_scroll, header_scroll, Gtk.PositionType.BOTTOM, 1, 1)
        self.attach_next_to(self.paned, seq_scroll, Gtk.PositionType.BOTTOM, 1, 1)

    def _setup_header_bar(self) -> None:
        """Create two-row top bar for sequence management, modes, flags & playback."""
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.header_box.set_margin_start(6)
        self.header_box.set_margin_end(6)
        self.header_box.set_margin_top(4)
        self.header_box.set_margin_bottom(2)

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.new_seq_btn = Gtk.Button(label="+ New")
        self.new_seq_btn.set_tooltip_text("Create a new secondary sequence")
        self.new_seq_btn.connect("clicked", lambda *_: self.create_new_sequence())
        row1.pack_start(self.new_seq_btn, False, False, 0)

        self.delete_seq_btn = Gtk.Button(label="Delete")
        self.delete_seq_btn.set_tooltip_text("Delete the selected secondary sequence")
        self.delete_seq_btn.connect(
            "clicked", lambda *_: self.delete_selected_sequence()
        )
        row1.pack_start(self.delete_seq_btn, False, False, 0)

        row1.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2
        )

        initial_tracking = getattr(self.lightshow.main_playback, "tracking_mode", False)
        self.tracking_mode_btn = Gtk.ToggleButton(
            label="Tracking" if initial_tracking else "Cue-Only"
        )
        self.tracking_mode_btn.set_tooltip_text("Toggle Tracking vs Cue-Only mode")
        self.tracking_mode_btn.set_active(initial_tracking)
        self.tracking_mode_btn.connect("toggled", self._on_tracking_mode_toggled)
        row1.pack_start(self.tracking_mode_btn, False, False, 0)

        initial_mib = getattr(self.lightshow.main_playback, "mib_enabled", True)
        self.mib_btn = Gtk.ToggleButton(label="MIB: ON" if initial_mib else "MIB: OFF")
        self.mib_btn.set_tooltip_text("Toggle Move In Black (MIB)")
        self.mib_btn.set_active(initial_mib)
        self.mib_btn.connect("toggled", self._on_mib_toggled)
        row1.pack_start(self.mib_btn, False, False, 0)

        self.seq_priority_combo = Gtk.ComboBoxText()
        self.seq_priority_combo.set_tooltip_text("Selected sequence playback priority")
        for prio_val, prio_lbl in (
            (PlaybackPriority.LOW, "Low"),
            (PlaybackPriority.NORMAL, "Normal"),
            (PlaybackPriority.HIGH, "High"),
            (PlaybackPriority.SUPER, "Super"),
        ):
            self.seq_priority_combo.append(str(int(prio_val)), prio_lbl)
        self.seq_priority_combo.set_active_id(str(int(PlaybackPriority.NORMAL)))
        self.seq_priority_combo.connect("changed", self._on_seq_priority_changed)
        row1.pack_start(self.seq_priority_combo, False, False, 0)

        row1.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2
        )

        self.block_btn = Gtk.ToggleButton(label="Block")
        self.block_btn.set_tooltip_text("Toggle Block flag (B) on selected cue")
        self.block_btn.connect("toggled", self._on_flag_toggled, "cue.set_block")
        row1.pack_start(self.block_btn, False, False, 0)

        self.int_block_btn = Gtk.ToggleButton(label="Int Block")
        self.int_block_btn.set_tooltip_text(
            "Toggle Intensity Block flag (IB) on selected cue"
        )
        self.int_block_btn.connect(
            "toggled", self._on_flag_toggled, "cue.set_int_block"
        )
        row1.pack_start(self.int_block_btn, False, False, 0)

        self.assert_btn = Gtk.ToggleButton(label="Assert")
        self.assert_btn.set_tooltip_text("Toggle Assert flag (A) on selected cue")
        self.assert_btn.connect("toggled", self._on_flag_toggled, "cue.set_assert")
        row1.pack_start(self.assert_btn, False, False, 0)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.seq_go_btn = Gtk.Button(label="Go")
        self.seq_go_btn.connect(
            "clicked",
            lambda *_: self.app.core.action_registry.execute(
                "sequence.go", self.get_selected_sequence_index()
            ),
        )
        row2.pack_start(self.seq_go_btn, False, False, 0)

        self.seq_pause_btn = Gtk.Button(label="Pause")
        self.seq_pause_btn.connect(
            "clicked",
            lambda *_: self.app.core.action_registry.execute(
                "sequence.pause", self.get_selected_sequence_index()
            ),
        )
        row2.pack_start(self.seq_pause_btn, False, False, 0)

        self.seq_assert_btn = Gtk.Button(label="Assert Seq")
        self.seq_assert_btn.connect(
            "clicked",
            lambda *_: self.app.core.action_registry.execute(
                "sequence.assert", self.get_selected_sequence_index()
            ),
        )
        row2.pack_start(self.seq_assert_btn, False, False, 0)

        self.seq_release_btn = Gtk.Button(label="Release")
        self.seq_release_btn.connect(
            "clicked",
            lambda *_: self.app.core.action_registry.execute(
                "sequence.release", self.get_selected_sequence_index()
            ),
        )
        row2.pack_start(self.seq_release_btn, False, False, 0)

        self.seq_release_all_btn = Gtk.Button(label="Release All")
        self.seq_release_all_btn.connect(
            "clicked",
            lambda *_: self.app.core.action_registry.execute("sequence.release_all"),
        )
        row2.pack_start(self.seq_release_all_btn, False, False, 0)

        self.header_box.pack_start(row1, False, False, 0)
        self.header_box.pack_start(row2, False, False, 0)

    def get_selected_sequence_index(self) -> float:
        """Return currently selected sequence index in treeview1 (default 1.0)."""
        if not hasattr(self, "treeview1"):
            return 1.0
        model, tree_iter = self.treeview1.get_selection().get_selected()
        if tree_iter is not None:
            return float(model.get_value(tree_iter, 0))
        return 1.0

    def _sync_seq_priority_combo(self) -> None:
        seq_idx = self.get_selected_sequence_index()
        seq = (
            self.lightshow.main_playback
            if seq_idx == 1.0
            else self.lightshow.get_sequence(seq_idx)
        )
        if seq is None:
            return
        self._updating_flag_btns = True
        try:
            self.seq_priority_combo.set_active_id(str(int(seq.priority)))
        finally:
            self._updating_flag_btns = False

    def _on_seq_priority_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._updating_flag_btns:
            return
        active_id = combo.get_active_id()
        if active_id is None:
            return
        self.app.core.action_registry.execute(
            "sequence.set_playback_options",
            self.get_selected_sequence_index(),
            priority=int(active_id),
        )

    def _on_flag_toggled(self, button: Gtk.ToggleButton, action_name: str) -> None:
        if self._updating_flag_btns:
            return
        sequence = self.get_selected_sequence()
        step = self.get_selected_step()
        if sequence is None or step is None or step >= len(sequence.steps):
            return
        cue = sequence.steps[step].cue
        if cue is None:
            return
        self.window.app.core.action_registry.execute(
            action_name, cue.number, button.get_active(), int(sequence.index)
        )

    def _sync_flag_buttons(self) -> None:
        """Synchronize Block / Int Block / Assert toggle buttons with selected cue."""
        if not hasattr(self, "block_btn"):
            return
        sequence = self.get_selected_sequence()
        step = self.get_selected_step()
        cue = (
            sequence.steps[step].cue
            if sequence is not None and step is not None and step < len(sequence.steps)
            else None
        )
        self._updating_flag_btns = True
        try:
            has_cue = cue is not None
            for btn, attr in (
                (self.block_btn, "is_block"),
                (self.int_block_btn, "is_int_block"),
                (self.assert_btn, "is_assert"),
            ):
                btn.set_sensitive(has_cue)
                btn.set_active(bool(getattr(cue, attr, False)) if cue else False)
        finally:
            self._updating_flag_btns = False

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
        self.tracking_mode_btn.set_label("Tracking" if enabled else "Cue-Only")
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

    def _populate_sequences_list(self) -> None:
        """Populate liststore1 sorted by ascending sequence number."""
        sequences = [self.lightshow.main_playback, *self.lightshow.sequences]
        sequences.sort(key=lambda seq: seq.index)
        for seq in sequences:
            self.liststore1.append([seq.index, seq.text])

    def _setup_sequences_list(self) -> None:
        """Setup the sequence selection list"""
        self.liststore1 = Gtk.ListStore(int, str)
        self._populate_sequences_list()

        self.treeview1 = Gtk.TreeView(model=self.liststore1)
        self.treeview1.set_enable_search(False)
        self.treeview1.get_selection().connect("changed", self.on_sequence_changed)

        for i, column_title in enumerate(["Seq", "Name"]):
            renderer = Gtk.CellRendererText()
            if i == 1:
                renderer.set_property("editable", True)
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                renderer.connect("edited", self._on_sequence_name_edited)
            column = Gtk.TreeViewColumn(column_title, renderer)
            column.add_attribute(renderer, "text", i)
            self.treeview1.append_column(column)

    def _on_sequence_name_edited(
        self, _widget: Gtk.CellRendererText, path: str, new_text: str
    ) -> None:
        """Rename the edited sequence via sequence.rename action."""
        seq_idx = float(self.liststore1[path][0])
        self.window.app.core.action_registry.execute(
            "sequence.rename", seq_idx, new_text
        )

    def _setup_cues_list(self) -> None:
        """Setup the cues layout"""
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)

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
            str,
            str,
            str,
            str,
            str,
        )
        self.link_column: Gtk.TreeViewColumn | None = None
        self.curve_column: Gtk.TreeViewColumn | None = None
        self._active_curve_step: tuple[float, int] | None = None
        self.step_curve_popover = CurveSelectionPopover(
            self.lightshow, self._on_step_curve_selected
        )
        self.treeview2 = Gtk.TreeView(model=self.liststore2)
        self.treeview2.set_enable_search(False)
        self.treeview2.set_has_tooltip(True)
        self.treeview2.connect("cursor-changed", self.on_cue_changed)
        self.treeview2.connect("row-activated", self.on_row_activated)
        self.treeview2.connect("query-tooltip", self._on_treeview2_query_tooltip)
        self.treeview2.connect("button-press-event", self._on_treeview2_button_press)

        column_specs: list[tuple[str, int, typing.Callable[..., None] | None]] = [
            ("Step", 0, None),
            ("Cue", 1, None),
            ("Text", 2, self.text_edited),
            ("Wait", 3, self.wait_edited),
            ("Delay Out", 4, self.delay_out_edited),
            ("Out", 5, self.out_edited),
            ("Delay In", 6, self.delay_in_edited),
            ("In", 7, self.in_edited),
            ("Pos", 8, self.pos_edited),
            ("Color", 9, self.color_edited),
            ("Beam", 10, self.beam_edited),
            ("Channel Time", 11, None),
            ("FX", 12, None),
            ("Flags", 15, None),
            ("Total", 16, None),
            ("Link", 17, None),
            ("Curve", 19, None),
            ("Notes", 18, self.notes_edited),
        ]
        for view_idx, (column_title, model_idx, edit_cb) in enumerate(column_specs):
            renderer = Gtk.CellRendererText()
            if view_idx % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))

            if edit_cb is not None:
                renderer.set_property("editable", True)
                renderer.connect("edited", edit_cb)
                renderer.connect("editing-started", self._on_editing_started)

            column = Gtk.TreeViewColumn(column_title, renderer)
            column.add_attribute(renderer, "text", model_idx)
            if model_idx == 2:
                column.set_min_width(200)
                column.set_resizable(True)
            elif model_idx == 12:
                column.add_attribute(renderer, "foreground", 13)
                column.add_attribute(renderer, "foreground-set", 14)
            elif model_idx == 17:
                self.link_column = column
            elif model_idx == 19:
                self.curve_column = column
            elif model_idx == 18:
                column.set_min_width(150)
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
        self._populate_sequences_list()
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

    def _edit_family_timing(self, path: Gtk.TreePath, text: str, family: str) -> None:
        """Update family delay/fade timing ('delay/time', 'time', or '' to reset)."""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        raw = text.strip()
        kwargs: dict[str, float]
        if raw == "":
            kwargs = {f"time_{family}": -1.0, f"delay_{family}": -1.0}
        elif "/" in raw:
            d_part, t_part = (p.strip() for p in raw.split("/", 1))
            d_val = -1.0 if d_part in ("", "-") else string_to_time(d_part)
            t_val = -1.0 if t_part in ("", "-") else string_to_time(t_part)
            kwargs = {f"delay_{family}": d_val, f"time_{family}": t_val}
        else:
            kwargs = {f"time_{family}": string_to_time(raw)}
        self.window.app.core.action_registry.execute(
            "step.update_times", sequence.index, step, **kwargs
        )

    def pos_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Position family time edited (empty string resets to inherited None)."""
        self._edit_family_timing(path, text, "position")

    def color_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Color family time edited (empty string resets to inherited None)."""
        self._edit_family_timing(path, text, "color")

    def beam_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Beam family time edited (empty string resets to inherited None)."""
        self._edit_family_timing(path, text, "beam")

    def notes_edited(
        self, _widget: Gtk.CellRendererText, path: Gtk.TreePath, text: str
    ) -> None:
        """Cue notes edited inline."""
        sequence = self.get_selected_sequence()
        if not sequence:
            return
        step = int(self.liststore2[path][0])
        cue = sequence.steps[step].cue
        if cue is None:
            return
        self.window.app.core.action_registry.execute(
            "cue.set_notes", cue.number, text, int(sequence.index)
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
        self._sync_flag_buttons()
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
        self._sync_seq_priority_combo()

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

        cue_editor = self.lightshow.cue_editor
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

    def create_new_sequence(self) -> None:
        """Create a new secondary sequence using the next available index."""
        next_idx = max((int(s.index) for s in self.lightshow.sequences), default=1) + 1
        self.window.app.core.action_registry.execute("sequence.new", float(next_idx))

    def delete_selected_sequence(self) -> None:
        """Delete the currently selected secondary sequence."""
        seq_idx = self.get_selected_sequence_index()
        if seq_idx <= 1.0:
            return
        self.window.app.core.action_registry.execute("sequence.delete", seq_idx)

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

        cue_editor = self.lightshow.cue_editor
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

    @classmethod
    def _format_family_timing(
        cls, delay: Optional[float], fade: Optional[float]
    ) -> str:
        """Format optional family delay and fade time ('time' or 'delay/time')."""
        fade_str = cls._format_family_time(fade)
        if delay is None:
            return fade_str
        delay_str = cls._format_family_time(delay)
        return f"{delay_str}/{fade_str or '-'}"

    @staticmethod
    def _format_cue_flags(cue: object | None) -> str:
        """Return compact flag string ('B', 'IB', 'A') for a Cue."""
        if cue is None:
            return ""
        flags: list[str] = []
        if getattr(cue, "is_block", False):
            flags.append("B")
        if getattr(cue, "is_int_block", False):
            flags.append("IB")
        if getattr(cue, "is_assert", False):
            flags.append("A")
        return " ".join(flags)

    def _on_treeview2_query_tooltip(
        self,
        treeview: Gtk.TreeView,
        x: int,
        y: int,
        keyboard_mode: bool,
        tooltip: Gtk.Tooltip,
    ) -> bool:
        """Provide tooltips for Channel Time, IFCB timings, Flags, and Notes."""
        if keyboard_mode:
            return False
        bx, by = treeview.convert_widget_to_bin_window_coords(x, y)
        hit = treeview.get_path_at_pos(bx, by)
        if hit is None:
            return False
        path, col, _cx, _cy = hit
        if path is None or col is None:
            return False
        sequence = self.get_selected_sequence()
        if sequence is None:
            return False
        step_idx = int(self.liststore2[path][0])
        if step_idx < 0 or step_idx >= len(sequence.steps):
            return False
        text = format_step_tooltip(sequence.steps[step_idx], col.get_title() or "")
        if not text:
            return False
        tooltip.set_text(text)
        return True

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
        t_pos = self._format_family_timing(
            step_obj.delay_position, step_obj.time_position
        )
        t_color = self._format_family_timing(step_obj.delay_color, step_obj.time_color)
        t_beam = self._format_family_timing(step_obj.delay_beam, step_obj.time_beam)
        channel_time = str(len(step_obj.channel_time))
        if channel_time == "0":
            channel_time = ""
        cue = step_obj.cue
        cue_number = str(cue.number) if cue is not None else ""
        fx_text, fx_color = self._format_step_fx_status(sequence, step)
        flags_text = self._format_cue_flags(cue)
        total_str = time_to_string(step_obj.total_time)
        link_parts: list[str] = []
        if cue is not None and cue.execute_preset is not None:
            link_parts.append(f"P{cue.execute_preset:g}")
        link_cue = getattr(step_obj, "link_cue", None)
        if link_cue is not None:
            loop_cnt = int(getattr(step_obj, "loop_count", 0))
            suffix = f" ×{loop_cnt}" if loop_cnt > 0 else ""
            link_parts.append(f"→ Q{link_cue:g}{suffix}")
        link_str = " / ".join(link_parts)

        step_cid = int(getattr(step_obj, "curve_id", 0))
        if step_cid > 0:
            c_obj = self.lightshow.curves.get_curve(step_cid)
            curve_str = (
                get_curve_display_name(c_obj)
                if c_obj is not None
                else f"Curve #{step_cid}"
            )
        else:
            curve_str = ""

        notes_str = cue.notes if cue is not None else ""
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
                flags_text,
                total_str,
                link_str,
                notes_str,
                curve_str,
            ],
        )

    def _get_cell_pointing_rect(
        self, treeview: Gtk.TreeView, path: Gtk.TreePath, col: Gtk.TreeViewColumn
    ) -> Gdk.Rectangle:
        rect = treeview.get_cell_area(path, col)
        rx, ry = treeview.convert_bin_window_to_widget_coords(rect.x, rect.y)
        out = Gdk.Rectangle()
        out.x = rx
        out.y = ry
        out.width = rect.width
        out.height = rect.height
        return out

    def _on_treeview2_button_press(
        self, treeview: Gtk.TreeView, event: Gdk.EventButton
    ) -> bool:
        if event.button != 1:
            return False
        path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
        if not path_info:
            return False
        path, col, _cx, _cy = path_info
        if path is None or col is None:
            return False
        seq = self.get_selected_sequence()
        if seq is None:
            return False
        step_idx = path.get_indices()[0] + 1
        if not (0 <= step_idx < len(seq.steps)):
            return False
        step_obj = seq.steps[step_idx]
        if col == self.curve_column:
            self._active_curve_step = (seq.index, step_idx)
            rect = self._get_cell_pointing_rect(treeview, path, col)
            self.step_curve_popover.open_for_curve(
                int(getattr(step_obj, "curve_id", 0)),
                relative_to=treeview,
                pointing_to=rect,
            )
            return True
        if col == self.link_column:
            self._open_link_popover(treeview, path, col, seq, step_idx, step_obj)
            return True
        return False

    def _on_step_curve_selected(self, curve_id: int) -> None:
        if self._active_curve_step is None:
            return
        seq_idx, step_idx = self._active_curve_step
        self.app.core.action_registry.execute(
            "step.set_curve", seq_idx, step_idx, curve_id
        )
        self.refresh()
        seq = self.get_selected_sequence()
        engine = getattr(self.app.core, "playback_engine", None)
        is_main = (
            engine.is_main_sequence(seq.index)
            if (seq is not None and engine is not None)
            else (seq is self.lightshow.main_playback)
        )
        if is_main and seq is not None and seq.position + 1 == step_idx:
            self.window.playback.update_xfade_display(step_idx - 1)

    def _open_link_popover(
        self,
        treeview: Gtk.TreeView,
        path: Gtk.TreePath,
        col: Gtk.TreeViewColumn,
        seq: Sequence,
        step_idx: int,
        step_obj: Step,
    ) -> None:
        popover = Gtk.Popover()
        popover.set_relative_to(treeview)
        popover.set_pointing_to(self._get_cell_pointing_rect(treeview, path, col))
        popover.set_position(Gtk.PositionType.BOTTOM)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_border_width(8)

        combo = Gtk.ComboBoxText()
        combo.append("", "None")
        cur_link = getattr(step_obj, "link_cue", None)
        active_id = ""
        for idx in range(1, len(seq.steps)):
            cue = seq.steps[idx].cue
            if cue is None or cue.number == 0.0:
                continue
            cid = f"{cue.number:g}"
            combo.append(cid, f"Q{cid}")
            if cur_link is not None and abs(float(cue.number) - float(cur_link)) < 1e-4:
                active_id = cid
        combo.set_active_id(active_id)
        vbox.add(combo)

        loop_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        loop_row.pack_start(Gtk.Label(label="Loops (0 = ∞)"), False, False, 0)
        spin_loops = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                value=int(getattr(step_obj, "loop_count", 0)),
                lower=0,
                upper=99,
                step_increment=1,
                page_increment=5,
                page_size=0,
            )
        )
        spin_loops.set_digits(0)
        loop_row.pack_end(spin_loops, False, False, 0)
        vbox.add(loop_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_apply = Gtk.Button(label="Apply")
        btn_clear = Gtk.Button(label="Clear")

        def _apply(_btn: Gtk.Button) -> None:
            sel = combo.get_active_id()
            target_cue = float(sel) if sel else None
            self.app.core.action_registry.execute(
                "step.set_link",
                seq.index,
                step_idx,
                target_cue,
                int(spin_loops.get_value()),
            )
            popover.popdown()
            self.refresh()

        def _clear(_btn: Gtk.Button) -> None:
            self.app.core.action_registry.execute(
                "step.set_link", seq.index, step_idx, None, 0
            )
            popover.popdown()
            self.refresh()

        btn_apply.connect("clicked", _apply)
        btn_clear.connect("clicked", _clear)
        btn_row.pack_start(btn_apply, True, True, 0)
        btn_row.pack_start(btn_clear, True, True, 0)
        vbox.add(btn_row)

        vbox.show_all()
        popover.add(vbox)
        popover.popup()

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
        self._sync_flag_buttons()

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
        engine = getattr(self.app.core, "playback_engine", None)
        is_main = (
            engine.is_main_sequence(sequence.index)
            if engine is not None
            else (sequence is self.lightshow.main_playback)
        )
        has_trailing_sentinel = (
            len(sequence.steps) >= 2
            and sequence.steps[-1].cue is not None
            and sequence.steps[-1].cue.number == 0.0
        )
        end_idx = sequence.last - 2 if has_trailing_sentinel else sequence.last - 1
        for i in range(step, end_idx):
            self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)
        if is_main:
            # Update Main Tab
            self.window.playback.update_sequence_display()
            if sequence.position + 1 == step:
                # Update Crossfade
                self.window.playback.update_xfade_display(step - 1)
                # Update Channels Tab
                self.window.update_channels_display(step - 1)
        # Select new step
        path = Gtk.TreePath.new_from_indices([step - 1])
        self.treeview2.set_cursor(path, None, False)
