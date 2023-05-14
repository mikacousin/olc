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
from typing import Any, Dict
import numpy as np
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


class LinearCurve(Curve):
    """Linear"""

    def __init__(self):
        super().__init__(name="Linear")

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        for x in range(256):
            self.values[x] = x


class SquareRootCurve(Curve):
    """Square Root, TV2, Linear Light"""

    def __init__(self):
        super().__init__(name="Square root")

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        for x in range(256):
            self.values[x] = round(pow(x, 0.5) * pow(255, 0.5))


class LimitCurve(Curve):
    """Proportional limitation"""

    limit: int  # Limit value (0 - 255)

    def __init__(self, limit=255):
        self.limit = limit
        super().__init__(name="Limit", editable=True)

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        for x in range(256):
            self.values[x] = round(x * (self.limit / 255))


class BezierCurve(Curve):
    """Bezier Curve"""

    def __init__(self):
        coord = [(0, 0), (70, 40), (255, 255)]
        self.points = np.array(coord)
        super().__init__(name="Bezier", editable=True)
        import random

        for _ in range(8):
            x = random.randint(0, 256)
            y = random.randint(0, 256)
            self.add_point(x, y)

    def populate_values(self) -> None:
        """Calculate each value of curve"""
        nb_interval_points = round((256 / (len(self.points) - 1)) * 4)
        self.path = self.evaluate_bezier(self.points, nb_interval_points)
        self.values = {
            min(max(round(k), 0), 255): min(max(round(v), 0), 255) for k, v in self.path
        }

    def add_point(self, x: int, y: int) -> None:
        """Add point to bezier curve

        Args:
            x: X coordinate (0 - 255)
            y: Y coordinate (0 - 255)
        """
        point = [(x, y)]
        if x not in self.points[:, 0]:
            self.points = np.append(self.points, point, axis=0)
            # Sort x values
            self.points = self.points[self.points[:, 0].argsort()]
            self.populate_values()

    def get_bezier_coef(self, points: np.ndarray) -> tuple[np.ndarray, list]:
        """Find the a & b points

        Args:
            points: Array of points

        Returns:
            A and B points
        """
        # since the formulas work given that we have n+1 points
        # then n must be this:
        n = len(points) - 1

        # build coefficents matrix
        C = 4 * np.identity(n)
        np.fill_diagonal(C[1:], 1)
        np.fill_diagonal(C[:, 1:], 1)
        C[0, 0] = 2
        C[n - 1, n - 1] = 7
        C[n - 1, n - 2] = 2

        # build points vector
        P = [2 * (2 * points[i] + points[i + 1]) for i in range(n)]
        P[0] = points[0] + 2 * points[1]
        P[n - 1] = 8 * points[n - 1] + points[n]

        # solve system, find a & b
        A = np.linalg.solve(C, P)
        B = [0] * n
        for i in range(n - 1):
            B[i] = 2 * points[i + 1] - A[i + 1]
        B[n - 1] = (A[n - 1] + points[n]) / 2

        return A, B

    def get_cubic(self, a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray):
        """Returns the general Bezier cubic formula given 4 control points

        Args:
            a: Point coord
            b: Point coord
            c: Point coord
            d: Point coord

        Returns:
            Lambda function
        """
        return (
            lambda t: np.power(1 - t, 3) * a
            + 3 * np.power(1 - t, 2) * t * b
            + 3 * (1 - t) * np.power(t, 2) * c
            + np.power(t, 3) * d
        )

    def get_bezier_cubic(self, points: np.ndarray) -> list:
        """Return one cubic curve for each consecutive points

        Args:
            points: Points

        Returns:
            List of self.get_cubic() functions
        """
        A, B = self.get_bezier_coef(points)
        return [
            self.get_cubic(points[i], A[i], B[i], points[i + 1])
            for i in range(len(points) - 1)
        ]

    def evaluate_bezier(self, points: np.ndarray, nb_points: int) -> np.ndarray:
        """Evalute each cubic curve on the range [0, 1] sliced in n points

        Args:
            points: Points
            nb_points: Number of interval points

        Returns:
            Bezier curves points
        """
        curves = self.get_bezier_cubic(points)
        return np.array(
            [fun(t) for fun in curves for t in np.linspace(0, 1, nb_points)]
        )


class Curves:
    """Curves supported by application

    Curve numbers from 0 to 9 are reserved
    """

    curves: Dict[int, Any]

    def __init__(self):
        # self.curves = {0: LinearCurve(), 1: SquareRootCurve(), 2: BezierCurve()}
        self.curves = {0: LinearCurve(), 1: SquareRootCurve()}

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
