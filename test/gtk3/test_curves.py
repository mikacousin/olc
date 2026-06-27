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
"""GUI behavior tests for the Curves tab."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.curve import CurveButton, CurvesTab  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_curves_tab_behavior(app_gui: Application) -> None:
    """Test CurvesTab creation, modification, deletion, and undo."""
    # 1. Open curves tab
    app_gui.activate_action("curves", None)
    process_events()

    assert app_gui.tabs is not None
    curves_tab = app_gui.tabs.tabs.get("curves")
    assert isinstance(curves_tab, CurvesTab)
    assert curves_tab.flowbox is not None

    # 2. Create new Limit curve
    initial_curve_count = len(app_gui.core.lightshow.curves.curves)
    curves_tab.on_new_curve(curves_tab.buttons["limit"])
    process_events()

    assert len(app_gui.core.lightshow.curves.curves) == initial_curve_count + 1, (
        "A new curve should be created."
    )

    # Get the created curve number (usually the last index)
    new_curve_number = list(app_gui.core.lightshow.curves.curves.keys())[-1]

    # 3. Verify it is visible in the flowbox
    children = curves_tab.flowbox.get_children()
    flowbox_children = [c for c in children if isinstance(c, Gtk.FlowBoxChild)]

    def get_curve_button(c: Gtk.FlowBoxChild) -> CurveButton:
        btn = c.get_child()
        assert isinstance(btn, CurveButton)
        return btn

    assert any(
        get_curve_button(c).curve_nb == new_curve_number for c in flowbox_children
    ), "Curve widget should be rendered."

    # 4. Select the new curve
    target_child = None
    for child in flowbox_children:
        if get_curve_button(child).curve_nb == new_curve_number:
            target_child = child
            break
    assert target_child is not None
    curves_tab.flowbox.select_child(target_child)
    process_events()

    # 5. Delete curve
    assert curves_tab.curve_edition is not None
    curves_tab.curve_edition.on_del_curve(Gtk.Button())
    process_events()
    assert new_curve_number not in app_gui.core.lightshow.curves.curves, (
        "Curve should be deleted."
    )

    # 6. Undo deletion
    app_gui.activate_action("undo", None)
    process_events()
    assert new_curve_number in app_gui.core.lightshow.curves.curves, (
        "Undo should restore the deleted curve."
    )
