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
"""Table widget for viewing and editing curve control points."""

from __future__ import annotations

import typing
from gettext import gettext as _

from gi.repository import Gtk

from olc.curve import PointsCurve
from olc.gtk3.widgets.curve_units import (
    CurveUnitMode,
    format_curve_value,
    parse_curve_value,
)

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow


class CurvePointsTable(Gtk.Box):
    """Dynamic table for editing curve control points with direct cell editing."""

    def __init__(
        self,
        lightshow: LightShow,
        curve_edition: typing.Any,  # noqa: ANN401
        unit_mode: CurveUnitMode = CurveUnitMode.PERCENT,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lightshow = lightshow
        self.curve_edition = curve_edition
        self.unit_mode = unit_mode
        self.curve_nb: int | None = None
        self._is_updating = False

        # Scrolled window
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_min_content_height(140)

        # Store: [index, label, in_formatted, out_formatted, in_norm, out_norm]
        self.store = Gtk.ListStore(int, str, str, str, float, float)
        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.set_headers_visible(True)

        # Column 0: Index (#)
        renderer_idx = Gtk.CellRendererText()
        renderer_idx.set_alignment(0.5, 0.5)
        col_idx = Gtk.TreeViewColumn(_("#"), renderer_idx)
        col_idx.add_attribute(renderer_idx, "text", 1)
        col_idx.set_min_width(45)
        self.treeview.append_column(col_idx)

        # Column 1: Input (In) - Editable
        self.renderer_in = Gtk.CellRendererText()
        self.renderer_in.set_property("editable", True)
        self.renderer_in.connect("edited", self._on_edited_in)
        col_in = Gtk.TreeViewColumn(_("Input (In)"), self.renderer_in)
        col_in.add_attribute(self.renderer_in, "text", 2)
        col_in.set_expand(True)
        self.treeview.append_column(col_in)

        # Column 2: Output (Out) - Editable
        self.renderer_out = Gtk.CellRendererText()
        self.renderer_out.set_property("editable", True)
        self.renderer_out.connect("edited", self._on_edited_out)
        col_out = Gtk.TreeViewColumn(_("Output (Out)"), self.renderer_out)
        col_out.add_attribute(self.renderer_out, "text", 3)
        col_out.set_expand(True)
        self.treeview.append_column(col_out)

        # Selection handler
        self.selection = self.treeview.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.selection.connect("changed", self._on_selection_changed)

        self.scrolled.add(self.treeview)
        self.pack_start(self.scrolled, True, True, 0)

    def set_unit_mode(self, unit_mode: CurveUnitMode) -> None:
        """Switch active unit mode and re-format table cells."""
        self.unit_mode = unit_mode
        self._refresh_formatted_values()

    def set_curve(self, curve_nb: int | None) -> None:
        """Load points for the specified curve."""
        self.curve_nb = curve_nb
        self.refresh()

    def refresh(self) -> None:
        """Reload store data from the active curve."""
        self._is_updating = True
        try:
            self.store.clear()
            if self.curve_nb is None:
                return
            curve = self.lightshow.curves.get_curve(self.curve_nb)
            if not isinstance(curve, PointsCurve):
                return

            for idx, pt in enumerate(curve.points):
                in_norm = pt[0] / 255.0
                out_norm = pt[1] / 255.0
                in_str = format_curve_value(in_norm, self.unit_mode)
                out_str = format_curve_value(out_norm, self.unit_mode)
                self.store.append(
                    [idx, f"#{idx + 1}", in_str, out_str, in_norm, out_norm]
                )
        finally:
            self._is_updating = False

    def _refresh_formatted_values(self) -> None:
        """Re-format display strings without reloading points from curve."""
        self._is_updating = True
        try:
            for row in self.store:
                in_norm = row[4]
                out_norm = row[5]
                row[2] = format_curve_value(in_norm, self.unit_mode)
                row[3] = format_curve_value(out_norm, self.unit_mode)
        finally:
            self._is_updating = False

    def select_point(self, index: int | None) -> None:
        """Select a row in the table from an external event."""
        if self._is_updating:
            return
        if index is None or index < 0 or index >= len(self.store):
            self.selection.unselect_all()
            return
        path = Gtk.TreePath.new_from_string(str(index))
        self.selection.select_path(path)
        self.treeview.scroll_to_cell(path, None, False, 0.0, 0.0)

    def get_selected_index(self) -> int | None:
        """Return the index of currently selected row, or None."""
        _model, tree_iter = self.selection.get_selected()
        if tree_iter is None:
            return None
        return typing.cast(int, self.store.get_value(tree_iter, 0))

    def _on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        """Synchronize table selection with graph points."""
        if self._is_updating:
            return
        _model, tree_iter = selection.get_selected()
        selected_idx = (
            typing.cast(int, self.store.get_value(tree_iter, 0))
            if tree_iter is not None
            else None
        )

        # Update curve edition point toggles
        if hasattr(self.curve_edition, "points") and self.curve_edition.points:
            for idx, pt_widget in enumerate(self.curve_edition.points):
                pt_widget.set_active(idx == selected_idx)
                pt_widget.queue_draw()
        if hasattr(self.curve_edition, "queue_draw"):
            self.curve_edition.queue_draw()

    def _on_edited_in(
        self, _renderer: Gtk.CellRendererText, path: str, new_text: str
    ) -> None:
        """Handle user edit on Input (In) column."""
        if self.curve_nb is None or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return

        idx = int(path)
        # Boundaries X are locked at 0 and 255
        if idx == 0 or idx == len(curve.points) - 1:
            self._refresh_formatted_values()
            return

        parsed = parse_curve_value(new_text, self.unit_mode)
        if parsed is None:
            self._refresh_formatted_values()
            return

        new_x = round(parsed * 255.0)
        prev_x = curve.points[idx - 1][0]
        next_x = curve.points[idx + 1][0]

        # Enforce strict monotonicity between adjacent points
        if not (prev_x < new_x < next_x):
            self._refresh_formatted_values()
            return

        new_points = list(curve.points)
        new_points[idx] = (new_x, new_points[idx][1])
        self.lightshow.app.core.action_registry.execute(
            "curve.update_points", self.curve_nb, new_points
        )

    def _on_edited_out(
        self, _renderer: Gtk.CellRendererText, path: str, new_text: str
    ) -> None:
        """Handle user edit on Output (Out) column."""
        if self.curve_nb is None or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return

        idx = int(path)
        parsed = parse_curve_value(new_text, self.unit_mode)
        if parsed is None:
            self._refresh_formatted_values()
            return

        new_y = round(parsed * 255.0)
        new_points = list(curve.points)
        new_points[idx] = (new_points[idx][0], new_y)
        self.lightshow.app.core.action_registry.execute(
            "curve.update_points", self.curve_nb, new_points
        )

    def add_point(self) -> None:
        """Add a new point between selected point and next, or in widest gap."""
        if self.curve_nb is None or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return

        idx = self.get_selected_index()
        new_x: int | None = None
        new_y: int | None = None

        if idx is not None and idx < len(curve.points) - 1:
            p1 = curve.points[idx]
            p2 = curve.points[idx + 1]
            if p2[0] - p1[0] > 1:
                new_x = (p1[0] + p2[0]) // 2
                new_y = (p1[1] + p2[1]) // 2

        if new_x is None:
            # Find largest gap in X
            max_gap = 0
            best_idx = 0
            for i in range(len(curve.points) - 1):
                gap = curve.points[i + 1][0] - curve.points[i][0]
                if gap > max_gap:
                    max_gap = gap
                    best_idx = i
            if max_gap > 1:
                p1 = curve.points[best_idx]
                p2 = curve.points[best_idx + 1]
                new_x = (p1[0] + p2[0]) // 2
                new_y = (p1[1] + p2[1]) // 2

        if new_x is not None and new_y is not None:
            new_points = list(curve.points)
            new_points.append((new_x, new_y))
            new_points.sort()
            inserted_idx = new_points.index((new_x, new_y))
            self.curve_edition.pending_active_point_idx = inserted_idx
            self.lightshow.app.core.action_registry.execute(
                "curve.update_points", self.curve_nb, new_points
            )

    def delete_point(self) -> None:
        """Delete currently selected point (if not an endpoint)."""
        if self.curve_nb is None or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return

        idx = self.get_selected_index()
        if idx is None or idx == 0 or idx >= len(curve.points) - 1:
            return

        new_points = list(curve.points)
        del new_points[idx]
        self.lightshow.app.core.action_registry.execute(
            "curve.update_points", self.curve_nb, new_points
        )
