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
"""Unit tests for Transfer Curve actions and Undo/Redo."""

from __future__ import annotations

import typing
from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.curve import LimitCurve, SegmentsCurve


def test_curve_actions_and_undo_redo() -> None:
    """Test curve.new, curve.delete, curve.update_points, and curve.set_limit
    actions.
    """
    settings = MagicMock()
    app = CoreApplication(settings)
    curves = app.lightshow.curves

    # 1. Create a segments curve
    curve_events = 0

    def on_curve_changed(_curve_nb: int) -> None:
        nonlocal curve_events
        curve_events += 1

    app.subscribe("curve.changed", on_curve_changed)

    curve_nb = typing.cast(int, app.action_registry.execute("curve.new", "segments"))
    assert curve_events == 1
    assert curve_nb in curves.curves
    curve = typing.cast(SegmentsCurve, curves.get_curve(curve_nb))
    assert curve is not None
    assert curve.points == [(0, 0), (255, 255)]

    # Undo creation
    app.history.undo()
    assert curve_events == 2
    assert curve_nb not in curves.curves

    # Redo creation
    app.history.redo()
    assert curve_events == 3
    assert curve_nb in curves.curves

    # 2. Update points
    new_points = [(0, 0), (100, 50), (255, 255)]
    app.action_registry.execute("curve.update_points", curve_nb, new_points)
    curve = typing.cast(SegmentsCurve, curves.get_curve(curve_nb))
    assert curve is not None
    assert curve.points == new_points

    # Undo update points
    app.history.undo()
    assert curve.points == [(0, 0), (255, 255)]

    # Redo update points
    app.history.redo()
    assert curve.points == new_points

    # 3. Create limit curve and change limit
    limit_nb = typing.cast(int, app.action_registry.execute("curve.new", "limit"))
    limit_curve = curves.get_curve(limit_nb)
    assert isinstance(limit_curve, LimitCurve)
    assert limit_curve.limit == 255

    app.action_registry.execute("curve.set_limit", limit_nb, 128)
    assert limit_curve.limit == 128

    # Undo set limit
    app.history.undo()
    assert limit_curve.limit == 255

    # Redo set limit
    app.history.redo()
    assert limit_curve.limit == 128

    # 4. Delete curve
    # Patch an output to use this curve
    app.lightshow.patch.add_output(1, 1, 1, curve_nb)
    assert app.lightshow.patch.outputs[1][1][1] == curve_nb

    app.action_registry.execute("curve.delete", curve_nb)
    # Curve should be deleted and output curve reset to 0 (Linear)
    assert curve_nb not in curves.curves
    assert app.lightshow.patch.outputs[1][1][1] == 0

    # Undo delete curve -> restores curve and links it back to outputs
    app.history.undo()
    assert curve_nb in curves.curves
    assert app.lightshow.patch.outputs[1][1][1] == curve_nb

    # Redo delete curve
    app.history.redo()
    assert curve_nb not in curves.curves
    assert app.lightshow.patch.outputs[1][1][1] == 0
