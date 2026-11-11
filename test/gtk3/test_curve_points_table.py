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
"""GUI tests for CurvePointsTable, CurveSampledMonitor and unit modes."""

from __future__ import annotations

import cairo
import pytest
from gi.repository import Gtk

from olc.curve import SegmentsCurve
from olc.gtk3.application import Application
from olc.gtk3.curve import CurvesTab
from olc.gtk3.widgets.curve_units import CurveUnitMode
from test.gtk3.conftest import process_events

pytestmark = pytest.mark.gui


def test_curve_points_table_and_units(app_gui: Application) -> None:
    """Test curve points table population, unit switching, adding/editing points."""
    # 1. Open curves tab
    app_gui.activate_action("curves", None)
    process_events()

    assert app_gui.tabs is not None
    curves_tab = app_gui.tabs.tabs.get("curves")
    assert isinstance(curves_tab, CurvesTab)
    edition = curves_tab.curve_edition
    assert edition is not None

    # 2. Create new Segments curve
    curves_tab.on_new_curve(curves_tab.buttons["segments"])
    process_events()

    curve_nb = list(app_gui.core.lightshow.curves.curves.keys())[-1]
    curve = app_gui.core.lightshow.curves.get_curve(curve_nb)
    assert isinstance(curve, SegmentsCurve)

    # Verify table has initial 2 points (0,0) and (255,255)
    assert len(edition.points_table.store) == 2
    row0 = edition.points_table.store[0]
    row1 = edition.points_table.store[1]
    assert row0[2] == "0 %"
    assert row0[3] == "0 %"
    assert row1[2] == "100 %"
    assert row1[3] == "100 %"

    # 3. Test unit mode switching
    edition.unit_combo.set_active_id(CurveUnitMode.NORMALIZED.value)
    process_events()
    assert edition.points_table.unit_mode == CurveUnitMode.NORMALIZED
    assert edition.points_table.store[0][2] == "0.000"
    assert edition.points_table.store[1][2] == "1.000"

    edition.unit_combo.set_active_id(CurveUnitMode.DMX_8BIT.value)
    process_events()
    assert edition.points_table.store[0][2] == "0"
    assert edition.points_table.store[1][2] == "255"

    edition.unit_combo.set_active_id(CurveUnitMode.PERCENT.value)
    process_events()

    # 4. Add point via table
    edition.points_table.add_point()
    process_events()
    assert len(curve.points) == 3
    assert len(edition.points_table.store) == 3
    # Middle point inserted at (127, 127)
    assert curve.points[1] == (127, 127)

    # 5. Edit Output (Out) of middle point
    edition.points_table._on_edited_out(Gtk.CellRendererText(), "1", "25 %")
    process_events()
    assert round(curve.points[1][1] / 255.0 * 100.0) == 25

    # 6. Edit Input (In) of middle point with monotonicity check
    # Valid edit
    edition.points_table._on_edited_in(Gtk.CellRendererText(), "1", "40 %")
    process_events()
    assert round(curve.points[1][0] / 255.0 * 100.0) == 40

    # Invalid edit (violates monotonicity: > next point at 100%)
    old_x = curve.points[1][0]
    edition.points_table._on_edited_in(Gtk.CellRendererText(), "1", "110 %")
    process_events()
    assert curve.points[1][0] == old_x

    # 7. Select point and delete it
    edition.points_table.select_point(1)
    process_events()
    assert edition.points_table.get_selected_index() == 1

    edition.points_table.delete_point()
    process_events()
    assert len(curve.points) == 2
    assert len(edition.points_table.store) == 2

    # 8. Undo deletion
    app_gui.activate_action("undo", None)
    process_events()
    assert len(curve.points) == 3
    assert len(edition.points_table.store) == 3

    # 9. Test non-editable curves (buttons hidden, cells non-editable)
    # 9a. Analytical non-points curve (0: Linear): both table and buttons hidden
    curves_tab.select_curve(0)
    process_events()
    assert not edition.points_actions_box.get_visible()
    assert not edition.table_container.get_visible()
    height_without_table = edition.sampled_monitor.get_allocated_height()
    assert height_without_table == 54

    # 9b. Predefined points curve (3: IES Square):
    # table visible in read-only, buttons hidden
    curves_tab.select_curve(3)
    process_events()
    assert not edition.points_actions_box.get_visible()
    assert edition.table_container.get_visible()
    assert not edition.points_table.renderer_in.get_property("editable")
    assert not edition.points_table.renderer_out.get_property("editable")
    height_with_table = edition.sampled_monitor.get_allocated_height()
    assert height_with_table == 54
    assert height_with_table == height_without_table

    # 9c. Switch back to editable custom curve: buttons and cell editing restored
    curves_tab.select_curve(curve_nb)
    process_events()
    assert edition.points_actions_box.get_visible()
    assert edition.table_container.get_visible()
    assert edition.points_table.renderer_in.get_property("editable")
    assert edition.points_table.renderer_out.get_property("editable")

    # 10. Test CurveSampledMonitor drawing
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 500, 60)
    cr = cairo.Context(surface)
    edition.sampled_monitor.on_draw(edition.sampled_monitor, cr)
