# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
from gettext import gettext as _
from typing import Any, Dict, List
from scipy.interpolate import PchipInterpolator
from olc.define import App


class Curve:
    """Curve object"""

    name: str  # Curve name
    editable: bool  # Editable Curve or not
    values: Dict[int, int]  # To store values

    def __init__(self, name="", editable=False):
        self.name = name
        self.editable = editable
        self.values = {}
        self.populate_values()

    def get_level(self, level: int) -> int:
        """Get precalculate curve levels.

        Args:
            level: input level (0 - 255)

        Returns:
            new level
        """
        return self.values.get(level, 0)

    def populate_values(self) -> None:
        """Calculate each value of curve

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def is_all_zero(self) -> bool:
        """Test if all curve values are 0

        Returns:
            True if all zero, else False
        """
        if isinstance(self, LimitCurve) and self.limit == 0:
            # LimitCurve at 0%
            return True
        for value in self.values.values():
            if value != 0:
                return False
        return True


class LinearCurve(Curve):
    """Linear"""

    def __init__(self):
        super().__init__(name=_("Linear"))

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        for x in range(256):
            self.values[x] = x


class SquareRootCurve(Curve):
    """Square Root, TV2, Linear Light"""

    def __init__(self):
        super().__init__(name=_("Square root"))

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        for x in range(256):
            self.values[x] = round(pow(x, 0.5) * pow(255, 0.5))


class LimitCurve(Curve):
    """Proportional limitation"""

    limit: int  # Limit value (0 - 255)

    def __init__(self, limit=255):
        self.limit = limit
        super().__init__(name=_("Limit"), editable=True)

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        for x in range(256):
            self.values[x] = round(x * (self.limit / 255))


class PointsCurve(Curve):
    """Curve defined by points"""

    points: List[tuple]

    def __init__(self, *args, **kwargs):
        self.points = [(0, 0), (255, 255)]
        super().__init__(*args, **kwargs)

    def populate_values(self) -> None:
        """Calculate each value of curve

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def add_point(self, x: int, y: int) -> None:
        """Add point to segment curve

        Args:
            x: X coordinate (0 - 255)
            y: Y coordinate (0 - 255)
        """
        if not any(x in point for point in self.points):
            point = (x, y)
            self.points.append(point)
            self.points.sort()
            self.populate_values()

    def del_point(self, point_number: int) -> None:
        """Remove a point curve

        Args:
            point_number: Point index to remove
        """
        del self.points[point_number]
        self.populate_values()

    def set_point(self, point_number: int, x: int, y: int) -> None:
        """Change point values

        Args:
            point_number: Point index
            x: X coordinate (0 - 255)
            y: Y coordinate (0 - 255)
        """
        x = min(max(x, 0), 255)
        y = min(max(y, 0), 255)
        if 0 <= point_number <= len(self.points) - 1:
            self.points[point_number] = (x, y)
            self.populate_values()


class SegmentsCurve(PointsCurve):
    """Curve with segments"""

    def __init__(self):
        super().__init__(name=_("Segment"), editable=True)

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        intervals = len(self.points) - 1
        for i in range(intervals):
            x_start = self.points[i][0]
            y_start = self.points[i][1]
            x_end = self.points[i + 1][0]
            y_end = self.points[i + 1][1]
            for x in range(x_start, x_end + 1):
                self.values[x] = round(
                    y_start + (((x - x_start) / (x_end - x_start)) * (y_end - y_start))
                )


class InterpolateCurve(PointsCurve):
    """Interpolate Curve"""

    def __init__(self):
        super().__init__(name=_("Interpolate"), editable=True)
        self.add_point(70, 40)

    def populate_values(self) -> None:
        x = []
        y = []
        for point in self.points:
            x.append(point[0])
            y.append(point[1])
        spl = PchipInterpolator(x, y)
        for i in range(256):
            self.values[i] = min(max(round(float(spl(i))), 0), 255)


class Curves:
    """Curves supported by application

    Curve numbers from 0 to 9 are reserved
    """

    curves: Dict[int, Any]

    def __init__(self):
        self.curves = {
            0: LinearCurve(),
            1: SquareRootCurve(),
            2: SegmentsCurve(),
        }
        # Full at 1% curve
        self.curves[2].editable = False
        self.curves[2].name = _("Full at 1%")
        self.curves[2].add_point(2, 0)
        self.curves[2].add_point(3, 255)

    def get_curve(self, number: int) -> Curve:
        """Get Curve with number

        Args:
            number: Curve number (key in dictionnary)

        Returns:
            Curve or 0
        """
        return self.curves.get(number, 0)

    def find_limit_curve(self, limit: int) -> int:
        """Find CurveLimit number if a curve with limit exist

        Args:
            limit: Limit value (0 - 255)

        Returns:
            CurveLimit number or 0
        """
        for number, curve in self.curves.items():
            if isinstance(curve, LimitCurve) and curve.limit == limit:
                return number
        return 0

    def add_curve(self, curve: Curve) -> int:
        """Add curve to curves list

        Args:
            curve: Curve to add

        Returns:
            Curve number or 0
        """
        for index in range(10, 9999):
            if index not in self.curves:
                self.curves[index] = curve
                return index
        return 0

    def del_curve(self, curve_nb: int) -> None:
        """Delete curve

        Args:
            curve_nb: Curve number
        """
        # First, change each output using deleted curve to LinearCurve (0)
        for value in App().patch.outputs.values():
            for chan_dic in value.values():
                if chan_dic[1] == curve_nb:
                    chan_dic[1] = 0
        # Delete Curve from self.curves
        self.curves.pop(curve_nb, None)
