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

from gi.repository import Gdk, Gtk, Pango

from olc.define import time_to_string
from olc.gtk3.sequence import SequenceTab, format_step_tooltip
from olc.gtk3.widgets.sequential import SequentialWidget

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


# pylint: disable=too-many-return-statements
def step_filter_func1(
    model: Gtk.TreeModel, treeiter: Gtk.TreeIter, view: MainPlaybackView
) -> bool:
    """Filter for the first part of the cues list

    Args:
        model: Model
        treeiter: Treeiter
        view: MainPlaybackView instance

    Returns:
        True, False or step
    """
    if not view.app:
        return True
    main_seq = view._get_main_sequence()  # pylint: disable=protected-access
    if main_seq is None:
        return True
    if main_seq.position <= 0:
        if int(model[treeiter][11]) in {0, 1} or int(model[treeiter][0]) in {0, 1}:
            return True
    if main_seq.position == 1:
        if int(model[treeiter][11]) == 1:
            return True
        if int(model[treeiter][11]) == 0:
            return False
        return int(model[treeiter][0]) in {0, 1, 2}
    if int(model[treeiter][11]) in {0, 1}:
        return False

    return int(model[treeiter][0]) in [
        main_seq.position,
        main_seq.position + 1,
        main_seq.position - 1,
        main_seq.position - 2,
    ]


def step_filter_func2(
    model: Gtk.TreeModel, treeiter: Gtk.TreeIter, view: MainPlaybackView
) -> bool:
    """Filter for the second part of the cues list

    Args:
        model: Model
        treeiter: Treeiter
        view: MainPlaybackView instance

    Returns:
        True or False
    """
    if not view.app:
        return True
    main_seq = view._get_main_sequence()  # pylint: disable=protected-access
    if main_seq is None:
        return False
    if not model[treeiter][0]:
        return False
    return int(model[treeiter][0]) > main_seq.position + 1


def _empty_playback_row(
    step_str: str = "",
    background: str = "#232729",
    weight: int = 0,
    sentinel: int = 1,
) -> list[typing.Any]:
    """Build an empty/sentinel row matching cues_liststore1 schema."""
    return [
        step_str,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        background,
        weight,
        sentinel,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        None,
        False,
    ]


# pylint: disable=too-many-instance-attributes
class MainPlaybackView(Gtk.Notebook):
    """Main Playback View"""

    def __init__(self, app: Application | None = None) -> None:
        Gtk.Notebook.__init__(self)
        self.app = app
        self.set_group_name("olc")

        self._setup_sequential()
        self._setup_treeviews()
        self._setup_layout()

        self._tab_label = Gtk.Label(label="Main Playback")
        self.append_page(self.grid, self._tab_label)
        self.set_tab_reorderable(self.grid, True)
        self.set_tab_detachable(self.grid, True)

        self.populate_sequence()
        self.update_tab_title()

    def _get_main_sequence(self) -> typing.Any:  # noqa: ANN401
        """Return the active Main Sequence from PlaybackEngine (fallback Seq 1)."""
        if not self.app:
            return None
        engine = getattr(self.app.core, "playback_engine", None)
        if engine is not None:
            seq = engine.main_sequence
            if seq is not None:
                return seq
        return getattr(self.app.core.lightshow, "main_playback", None)

    def update_tab_title(self) -> None:
        """Update notebook tab label to reflect the active Main Sequence."""
        seq = self._get_main_sequence()
        if seq is None:
            self._tab_label.set_text("Main Playback")
            return
        idx = int(seq.index) if float(seq.index).is_integer() else seq.index
        title = f"Main · Seq {idx} — {seq.text}" if seq.text else f"Main · Seq {idx}"
        self._tab_label.set_text(title)

    def _setup_sequential(self) -> None:
        """Setup the Sequential Widget parameters"""
        # Crossfade widget
        self.sequential = SequentialWidget(
            self.app.core.lightshow if self.app else None,
            main_sequence_getter=self._get_main_sequence,
        )

    def _setup_treeviews(self) -> None:
        """Init ListStores and TreeViews"""
        self.cues_liststore1 = Gtk.ListStore(
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
            int,
            int,
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
        self.step_filter1 = self.cues_liststore1.filter_new()
        self.step_filter1.set_visible_func(step_filter_func1, self)
        self.step_filter2 = self.cues_liststore1.filter_new()
        self.step_filter2.set_visible_func(step_filter_func2, self)

        self.treeview1 = self._create_treeview(self.step_filter1, is_main=True)
        self.treeview2 = self._create_treeview(self.step_filter2, is_main=False)
        self._syncing_column_widths = False
        self._connect_column_width_sync()

    def _connect_column_width_sync(self) -> None:
        """Keep column widths identical between treeview1 and treeview2."""
        cols1 = self.treeview1.get_columns()
        cols2 = self.treeview2.get_columns()
        for col1, col2 in zip(cols1, cols2, strict=True):
            col1.connect("notify::width", self._on_column_width_changed, col2)
            col2.connect("notify::width", self._on_column_width_changed, col1)

    def _on_column_width_changed(
        self,
        source_col: Gtk.TreeViewColumn,
        _pspec: object,
        target_col: Gtk.TreeViewColumn,
    ) -> None:
        if self._syncing_column_widths:
            return
        width = source_col.get_width()
        if width <= 0 or target_col.get_fixed_width() == width:
            return
        self._syncing_column_widths = True
        try:
            target_col.set_fixed_width(width)
        finally:
            self._syncing_column_widths = False

    def _create_treeview(self, model: Gtk.TreeModel, is_main: bool) -> Gtk.TreeView:
        """Factory method for TreeViews to avoid repetition"""
        treeview = Gtk.TreeView(model=model)
        treeview.set_enable_search(False)
        treeview.get_selection().set_mode(Gtk.SelectionMode.NONE)
        treeview.set_fixed_height_mode(True)
        treeview.set_has_tooltip(True)
        treeview.connect("query-tooltip", self._on_treeview_query_tooltip)

        columns = [
            (0, "Step", 55),
            (1, "Cue", 65),
            (2, "Text", 220),
            (3, "Wait", 65),
            (4, "Delay Out", 80),
            (5, "Out", 65),
            (6, "Delay In", 80),
            (7, "In", 65),
            (8, "Channel Time", 105),
            (12, "Pos", 75),
            (13, "Color", 75),
            (14, "Beam", 75),
            (15, "FX", 95),
            (16, "Flags", 65),
            (17, "Total", 65),
            (18, "Link", 65),
            (19, "Notes", 160),
        ]
        for display_idx, (store_idx, column_title, default_width) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if display_idx % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            if store_idx in (2, 15, 19):
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)

            column = Gtk.TreeViewColumn(title=column_title, cell_renderer=renderer)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(default_width)
            column.set_min_width(min(default_width, 55))
            column.set_resizable(True)
            column.add_attribute(renderer, "text", store_idx)
            if is_main:
                column.add_attribute(renderer, "background", 9)
                column.add_attribute(renderer, "weight", 10)
            if store_idx == 15:
                column.add_attribute(renderer, "foreground", 20)
                column.add_attribute(renderer, "foreground-set", 21)

            if store_idx == 2:
                column.set_expand(True)
            treeview.append_column(column)

        return treeview

    def _setup_layout(self) -> None:
        """Arrange components within the Grid layout"""
        scrollable2 = Gtk.ScrolledWindow()
        scrollable2.set_vexpand(True)
        scrollable2.set_hexpand(True)
        scrollable2.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.EXTERNAL)
        scrollable2.add(self.treeview2)

        scrollable1 = Gtk.ScrolledWindow()
        scrollable1.set_hexpand(True)
        scrollable1.set_propagate_natural_height(True)
        scrollable1.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        scrollable1.set_hadjustment(scrollable2.get_hadjustment())
        scrollable1.add(self.treeview1)

        self.grid = Gtk.Grid(row_homogeneous=False)
        self.grid.attach(scrollable1, 0, 0, 1, 1)
        self.grid.attach_next_to(
            self.sequential, scrollable1, Gtk.PositionType.BOTTOM, 1, 1
        )
        self.grid.attach_next_to(
            scrollable2, self.sequential, Gtk.PositionType.BOTTOM, 1, 1
        )

    def update_sequence_display(self) -> None:
        """Clear and repopulate the playback cue list."""
        self.cues_liststore1.clear()
        self.populate_sequence()
        self.update_tab_title()

    def _on_treeview_query_tooltip(
        self,
        treeview: Gtk.TreeView,
        x: int,
        y: int,
        keyboard_mode: bool,
        tooltip: Gtk.Tooltip,
    ) -> bool:
        """Provide tooltips for Channel Time, IFCB timings, Flags, and Notes."""
        if keyboard_mode or not self.app:
            return False
        bx, by = treeview.convert_widget_to_bin_window_coords(x, y)
        hit = treeview.get_path_at_pos(bx, by)
        if hit is None:
            return False
        path, col, _cx, _cy = hit
        model = treeview.get_model()
        if path is None or col is None or model is None:
            return False
        step_text = model[path][0]
        if not step_text:
            return False
        step_idx = int(step_text)
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return False
        steps = main_seq.steps
        if step_idx < 0 or step_idx >= len(steps):
            return False
        text = format_step_tooltip(steps[step_idx], col.get_title() or "")
        if not text:
            return False
        tooltip.set_text(text)
        return True

    def populate_sequence(self) -> None:
        """Display main playback"""
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
        self.cues_liststore1.append(_empty_playback_row(sentinel=0))
        self.cues_liststore1.append(_empty_playback_row(sentinel=1))
        for i in range(main_seq.last):
            step_obj = main_seq.steps[i]
            wait = time_to_string(step_obj.wait)
            t_out = time_to_string(step_obj.time_out)
            d_out = time_to_string(step_obj.delay_out)
            t_in = time_to_string(step_obj.time_in)
            d_in = time_to_string(step_obj.delay_in)
            channel_time = str(len(step_obj.channel_time))
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
            if i == 0 or step_obj.cue is None or step_obj.cue.number == 0:
                self.cues_liststore1.append(
                    _empty_playback_row(
                        step_str=str(i),
                        background=background,
                        weight=Pango.Weight.NORMAL,
                        sentinel=99,
                    )
                )
            else:
                cue = step_obj.cue
                cue_number = str(cue.number) if cue is not None else ""
                pos = SequenceTab._format_family_timing(  # pylint: disable=protected-access
                    step_obj.delay_position, step_obj.time_position
                )
                color = SequenceTab._format_family_timing(  # pylint: disable=protected-access
                    step_obj.delay_color, step_obj.time_color
                )
                beam = SequenceTab._format_family_timing(  # pylint: disable=protected-access
                    step_obj.delay_beam, step_obj.time_beam
                )
                fx_text, fx_color = SequenceTab._format_step_fx_status(  # pylint: disable=protected-access
                    main_seq, i
                )
                flags_text = SequenceTab._format_cue_flags(cue)  # pylint: disable=protected-access
                total_text = SequenceTab._format_family_time(step_obj.total_time)  # pylint: disable=protected-access
                link_text = (
                    f"P{cue.execute_preset:g}"
                    if cue is not None and cue.execute_preset is not None
                    else ""
                )
                notes_text = cue.notes if cue is not None else ""
                self.cues_liststore1.append(
                    [
                        str(i),
                        cue_number,
                        str(step_obj.text),
                        wait,
                        d_out,
                        str(t_out),
                        d_in,
                        str(t_in),
                        channel_time,
                        background,
                        weight,
                        99,
                        pos,
                        color,
                        beam,
                        fx_text,
                        flags_text,
                        total_text,
                        link_text,
                        notes_text,
                        fx_color,
                        fx_color is not None,
                    ]
                )
        if main_seq.last == 1:
            self.cues_liststore1.append(_empty_playback_row(sentinel=1))
        self.update_active_cues_display()
        self.grid.queue_draw()

    def update_active_cues_display(self) -> None:
        """Update First part of sequential"""
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
        n_rows = len(self.cues_liststore1)
        pos = main_seq.position
        if 0 <= pos < n_rows:
            self.cues_liststore1[pos][9] = "#232729"
            self.cues_liststore1[pos][10] = Pango.Weight.NORMAL
        if pos + 1 <= main_seq.last and pos + 1 < n_rows:
            self.cues_liststore1[pos + 1][9] = "#232729"
            self.cues_liststore1[pos + 1][10] = Pango.Weight.NORMAL
        if pos + 2 <= main_seq.last and pos + 2 < n_rows:
            self.cues_liststore1[pos + 2][9] = "#997004"
            self.cues_liststore1[pos + 2][10] = Pango.Weight.HEAVY
        if pos + 3 <= main_seq.last and pos + 3 < n_rows:
            self.cues_liststore1[pos + 3][9] = "#555555"
            self.cues_liststore1[pos + 3][10] = Pango.Weight.HEAVY
        self.step_filter1.refilter()
        self.step_filter2.refilter()
        if 0 <= pos + 2 < n_rows:
            path1 = Gtk.TreePath.new_from_indices([pos + 2])
            self.treeview1.set_cursor(path1, None, False)
        path2 = Gtk.TreePath.new_from_indices([0])
        self.treeview2.set_cursor(path2, None, False)

    def display_times(self) -> None:
        """Display Cues times after countdown"""
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
        step = main_seq.position
        for offset in (0, 1):
            if not (
                0 <= step + offset < len(main_seq.steps)
                and 0 <= step + 2 + offset < len(self.cues_liststore1)
            ):
                continue
            step_obj = main_seq.steps[step + offset]
            row = self.cues_liststore1[step + 2 + offset]
            row[3] = time_to_string(step_obj.wait)
            row[4] = time_to_string(step_obj.delay_out)
            row[5] = time_to_string(step_obj.time_out)
            row[6] = time_to_string(step_obj.delay_in)
            row[7] = time_to_string(step_obj.time_in)
            row[12] = SequenceTab._format_family_timing(  # pylint: disable=protected-access
                step_obj.delay_position, step_obj.time_position
            )
            row[13] = SequenceTab._format_family_timing(  # pylint: disable=protected-access
                step_obj.delay_color, step_obj.time_color
            )
            row[14] = SequenceTab._format_family_timing(  # pylint: disable=protected-access
                step_obj.delay_beam, step_obj.time_beam
            )
            row[17] = SequenceTab._format_family_time(step_obj.total_time)  # pylint: disable=protected-access

    def show_timeleft(self, i: float) -> None:
        """Display countdowns during Go and color crossfade of active cues

        Args:
            i: Spent time of the Go in milliseconds
        """
        self.show_timeleft_out(i)
        self.show_timeleft_in(i)
        # Color crossfade
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
        step = main_seq.position + 1
        if step >= len(main_seq.steps):
            return
        total_time = main_seq.steps[step].total_time * 1000
        if total_time <= 0:
            return
        progress = min(max(i / total_time, 0.0), 1.0)
        self.update_cue_crossfade_color(step, progress)

    def show_timeleft_out(self, i: float) -> None:
        """Display Out Countdowns during Xfade

        Args:
            i: Position in Xfade in milliseconds
        """
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
        step = main_seq.position + 1
        if step >= len(main_seq.steps):
            return
        wait = main_seq.steps[step].wait * 1000
        if i > wait:
            d_out = main_seq.steps[step].delay_out * 1000
            if i > wait + d_out:
                t_out = main_seq.steps[step].time_out * 1000
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
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
        step = main_seq.position + 1
        if step >= len(main_seq.steps):
            return
        wait = main_seq.steps[step].wait * 1000
        if i > wait:
            d_in = main_seq.steps[step].delay_in * 1000
            if i > wait + d_in:
                t_in = main_seq.steps[step].time_in * 1000
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
        self._update_family_timeleft(step, i)

    def _update_family_timeleft(self, step: int, elapsed_ms: float) -> None:
        """Update Total, Pos, Color, and Beam countdowns during an active crossfade."""
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None or step >= len(main_seq.steps):
            return
        step_obj = main_seq.steps[step]
        row = self.cues_liststore1[step + 2]
        rem_total = max(0.0, step_obj.total_time - elapsed_ms / 1000.0)
        row[17] = SequenceTab._format_family_time(rem_total)  # pylint: disable=protected-access

        wait_ms = step_obj.wait * 1000.0
        if elapsed_ms <= wait_ms:
            return
        for fam, col_idx in (("position", 12), ("color", 13), ("beam", 14)):
            if not step_obj.has_explicit_family_timing(fam):
                continue
            explicit_delay = getattr(step_obj, f"delay_{fam}")
            explicit_time = getattr(step_obj, f"time_{fam}")
            eff_delay_ms = getattr(step_obj, f"effective_delay_{fam}") * 1000.0
            eff_time_ms = getattr(step_obj, f"effective_time_{fam}") * 1000.0

            if elapsed_ms <= wait_ms + eff_delay_ms:
                if explicit_delay is not None:
                    rem_delay = max(0.0, (wait_ms + eff_delay_ms - elapsed_ms) / 1000.0)
                    fade_str = SequenceTab._format_family_time(explicit_time) or "-"  # pylint: disable=protected-access
                    row[col_idx] = (
                        f"{SequenceTab._format_family_time(rem_delay)}/{fade_str}"  # pylint: disable=protected-access
                    )
            else:
                rem_time = max(
                    0.0, (wait_ms + eff_delay_ms + eff_time_ms - elapsed_ms) / 1000.0
                )
                rem_str = SequenceTab._format_family_time(rem_time)  # pylint: disable=protected-access
                row[col_idx] = f"0/{rem_str}" if explicit_delay is not None else rem_str

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
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb: tuple[int, ...]) -> str:
        return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"

    def goback_countdown(self, i: float, goback_time: float, step: int) -> None:
        """Display countdowns during GoBack

        Args:
            i: Position in milliseconds
            goback_time: GoBack Time set in preference
            step: Active Step
        """
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            return
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
        if step < main_seq.last - 2:
            blended = self._blend_color("#555555", "#232729", progress)
            hex_color = self._rgb_to_hex(blended)
            self.cues_liststore1[step + 3][9] = hex_color
        self.treeview1.queue_draw()

    def update_xfade_display(self, step: int) -> None:
        """Update Crossfade display

        Args:
            step: Step
        """
        if not self.app:
            return
        main_seq = self._get_main_sequence()
        if main_seq is None:
            self.sequential.sync_from_sequence(None)
            return
        if not (0 <= step + 1 < len(main_seq.steps)):
            self.sequential.sync_from_sequence(main_seq)
            return
        next_step = main_seq.steps[step + 1]
        self.sequential.total_time = next_step.total_time
        self.sequential.time_in = next_step.time_in
        self.sequential.time_out = next_step.time_out
        self.sequential.delay_in = next_step.delay_in
        self.sequential.delay_out = next_step.delay_out
        self.sequential.wait = next_step.wait
        self.sequential.channel_time = next_step.channel_time
        self.sequential.queue_draw()
