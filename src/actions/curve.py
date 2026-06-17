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

from olc.core.action import Action
from olc.curve import InterpolateCurve, LimitCurve, PointsCurve, SegmentsCurve

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.curve import Curve


class CurveNewAction(Action):
    """Action to create a new custom transfer curve."""

    name = "curve.new"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.curve_type: str = "segments"
        self.name_val: typing.Optional[str] = None
        self.created_curve: typing.Optional[Curve] = None
        self.curve_nb: typing.Optional[int] = None

    def configure(self, curve_type: str, name: str | None = None) -> None:
        """Configure the action with the curve type and optional name.

        Args:
            curve_type: The type of curve to create ('segments', 'interpolate',
                        'limit').
            name: Optional display name for the new curve.
        """
        self.curve_type = curve_type
        self.name_val = name

    def execute(self) -> int:
        """Execute the action, creating the configured curve."""
        curve_type = self.curve_type
        name = self.name_val

        curves = self.app.lightshow.curves

        if curve_type == "segments":
            curve_obj = SegmentsCurve()
            if name:
                curve_obj.name = name
            curve_obj.add_point(0, 0)
            curve_nb = curves.add_curve(curve_obj)
            curve_obj.add_point(255, 255)
        elif curve_type == "interpolate":
            curve_obj = InterpolateCurve()
            if name:
                curve_obj.name = name
            curve_obj.add_point(0, 0)
            curve_nb = curves.add_curve(curve_obj)
            curve_obj.add_point(70, 40)
            curve_obj.add_point(255, 255)
        elif curve_type == "limit":
            curve_obj = LimitCurve(255)
            if name:
                curve_obj.name = name
            curve_nb = curves.add_curve(curve_obj)
        else:
            raise ValueError(f"Unknown curve type: {curve_type}")

        self.created_curve = curve_obj
        self.curve_nb = curve_nb

        self.app.lightshow.set_modified()
        self.app.emit("curve.changed", curve_nb)
        return curve_nb

    def undo(self) -> None:
        if self.curve_nb is not None:
            self.app.lightshow.curves.del_curve(self.curve_nb)
            self.app.lightshow.set_modified()
            self.app.emit("curve.changed", 0)  # Reset to linear/first

    def redo(self) -> None:
        if self.curve_nb is not None and self.created_curve is not None:
            self.app.lightshow.curves.curves[self.curve_nb] = self.created_curve
            self.app.lightshow.set_modified()
            self.app.emit("curve.changed", self.curve_nb)


class CurveDeleteAction(Action):
    """Action to delete a custom transfer curve."""

    name = "curve.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.curve_nb: typing.Optional[int] = None
        self.deleted_curve: typing.Optional[Curve] = None
        # Saved outputs using this curve: list of (univ, output)
        self.saved_outputs: list[tuple[int, int]] = []

    def configure(self, curve_nb: int) -> None:
        """Configure the action with the curve number to delete.

        Args:
            curve_nb: The number of the curve to delete.
        """
        self.curve_nb = curve_nb

    def execute(self) -> None:
        """Execute the action, deleting the configured curve."""
        curve_nb = self.curve_nb
        if curve_nb is None:
            raise ValueError("curve_nb must be set via configure() before execute().")
        curves = self.app.lightshow.curves
        patch = self.app.lightshow.patch

        curve_obj = curves.get_curve(curve_nb)
        if curve_obj is None:
            raise ValueError(f"Curve number {curve_nb} does not exist.")
        if not curve_obj.editable:
            raise ValueError(f"Curve {curve_nb} is not editable and cannot be deleted.")

        self.deleted_curve = curve_obj

        # Save all outputs currently using this curve
        self.saved_outputs = []
        for univ, outputs in patch.outputs.items():
            for output, (_channel, curve) in outputs.items():
                if curve == curve_nb:
                    self.saved_outputs.append((univ, output))

        # Delete it (sets those outputs to curve 0)
        curves.del_curve(curve_nb)

        self.app.lightshow.set_modified()
        self.app.emit("curve.changed", 0)

    def undo(self) -> None:
        if self.curve_nb is not None and self.deleted_curve is not None:
            curves = self.app.lightshow.curves
            patch = self.app.lightshow.patch

            # Restore curve object
            curves.curves[self.curve_nb] = self.deleted_curve

            # Restore output links
            for univ, output in self.saved_outputs:
                if univ in patch.outputs and output in patch.outputs[univ]:
                    patch.outputs[univ][output][1] = self.curve_nb

            patch.invalidate_cache()
            self.app.lightshow.set_modified()
            self.app.emit("curve.changed", self.curve_nb)

    def redo(self) -> None:
        if self.curve_nb is not None:
            self.app.lightshow.curves.del_curve(self.curve_nb)
            self.app.lightshow.set_modified()
            self.app.emit("curve.changed", 0)


class CurveUpdatePointsAction(Action):
    """Action to update the list of points defining a custom curve."""

    name = "curve.update_points"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.curve_nb: typing.Optional[int] = None
        self.points: list[tuple[int, int]] = []
        self.old_points: list[tuple[int, int]] = []

    def configure(self, curve_nb: int, points: list[tuple[int, int]]) -> None:
        """Configure the action with the curve number and new point list.

        Args:
            curve_nb: The number of the curve to update.
            points: The new list of (x, y) control points.
        """
        self.curve_nb = curve_nb
        self.points = list(points)

    def execute(self) -> None:
        """Execute the action, applying the configured points to the curve."""
        curve_nb = self.curve_nb
        if curve_nb is None:
            raise ValueError("curve_nb must be set via configure() before execute().")

        curve = self.app.lightshow.curves.get_curve(curve_nb)
        if curve is None:
            raise ValueError(f"Curve {curve_nb} does not exist.")
        if not isinstance(curve, PointsCurve):
            raise ValueError(f"Curve {curve_nb} is not a points-defined curve.")

        self.old_points = list(curve.points)

        # Apply new points
        curve.points = list(self.points)
        curve.populate_values()

        self.app.lightshow.set_modified()
        self.app.emit("curve.changed", curve_nb)

    def undo(self) -> None:
        if self.curve_nb is not None:
            curve = self.app.lightshow.curves.get_curve(self.curve_nb)
            if isinstance(curve, PointsCurve):
                curve.points = list(self.old_points)
                curve.populate_values()
                self.app.lightshow.set_modified()
                self.app.emit("curve.changed", self.curve_nb)

    def redo(self) -> None:
        if self.curve_nb is not None:
            curve = self.app.lightshow.curves.get_curve(self.curve_nb)
            if isinstance(curve, PointsCurve):
                curve.points = list(self.points)
                curve.populate_values()
                self.app.lightshow.set_modified()
                self.app.emit("curve.changed", self.curve_nb)


class CurveSetLimitAction(Action):
    """Action to set the limit of a LimitCurve."""

    name = "curve.set_limit"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.curve_nb: typing.Optional[int] = None
        self.limit: int = 255
        self.old_limit: int = 255

    def configure(self, curve_nb: int, limit: int) -> None:
        """Configure the action with the curve number and new limit value.

        Args:
            curve_nb: The number of the LimitCurve to update.
            limit: The new limit value (0-255).
        """
        self.curve_nb = curve_nb
        self.limit = limit

    def execute(self) -> None:
        """Execute the action, applying the configured limit to the curve."""
        curve_nb = self.curve_nb
        if curve_nb is None:
            raise ValueError("curve_nb must be set via configure() before execute().")

        curve = self.app.lightshow.curves.get_curve(curve_nb)
        if curve is None:
            raise ValueError(f"Curve {curve_nb} does not exist.")
        if not isinstance(curve, LimitCurve):
            raise ValueError(f"Curve {curve_nb} is not a limit curve.")

        self.old_limit = curve.limit

        # Apply limit
        curve.limit = self.limit
        curve.populate_values()

        self.app.lightshow.set_modified()
        self.app.emit("curve.changed", curve_nb)

    def undo(self) -> None:
        if self.curve_nb is not None:
            curve = self.app.lightshow.curves.get_curve(self.curve_nb)
            if isinstance(curve, LimitCurve):
                curve.limit = self.old_limit
                curve.populate_values()
                self.app.lightshow.set_modified()
                self.app.emit("curve.changed", self.curve_nb)

    def redo(self) -> None:
        if self.curve_nb is not None:
            curve = self.app.lightshow.curves.get_curve(self.curve_nb)
            if isinstance(curve, LimitCurve):
                curve.limit = self.limit
                curve.populate_values()
                self.app.lightshow.set_modified()
                self.app.emit("curve.changed", self.curve_nb)
