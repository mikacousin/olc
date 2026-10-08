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
"""Transfer curves module supporting normalized, 8-bit, and 16-bit resolutions."""

from __future__ import annotations

import typing

import numpy as np
from scipy.interpolate import PchipInterpolator

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow


class Curve:
    """Base transfer curve object supporting multi-resolution evaluation."""

    name: str  # Curve name
    editable: bool  # Editable Curve or not
    values_array: np.ndarray  # 8-bit lookup table (256 entries)
    values_array_16bit: np.ndarray  # 16-bit lookup table (65536 entries)

    def __init__(self, name: str = "", editable: bool = False) -> None:
        self.name = name
        self.editable = editable
        self.values_array = np.zeros(256, dtype=np.uint8)
        self.values_array_16bit = np.zeros(65536, dtype=np.uint16)
        self.populate_values()

    def get_level(self, level: int) -> int:
        """Get precalculated curve level for 8-bit input.

        Args:
            level: input level (0 - 255)

        Returns:
            new 8-bit level
        """
        clamped = max(0, min(255, level))
        return int(self.values_array[clamped])

    def get_level_16bit(self, level: int) -> int:
        """Get precalculated curve level for 16-bit input.

        Args:
            level: input level (0 - 65535)

        Returns:
            new 16-bit level
        """
        clamped = max(0, min(65535, level))
        return int(self.values_array_16bit[clamped])

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        """Evaluate the curve in the continuous normalized [0.0, 1.0] domain.

        Args:
            values: Input value or array in [0.0, 1.0]

        Returns:
            Output value or array in [0.0, 1.0]
        """
        raise NotImplementedError

    def evaluate_8bit(self, levels: int | np.ndarray) -> int | np.ndarray:
        """Evaluate the curve for 8-bit integer level(s) [0..255].

        Args:
            levels: Integer or NumPy array of integers in [0..255]

        Returns:
            Transformed integer level(s) in [0..255]
        """
        if isinstance(levels, (int, np.integer)):
            clamped = int(max(0, min(255, int(levels))))
            return int(self.values_array[clamped])
        arr = np.clip(np.asarray(levels, dtype=np.int64), 0, 255)
        return self.values_array[arr]

    def evaluate_16bit(self, levels: int | np.ndarray) -> int | np.ndarray:
        """Evaluate the curve for 16-bit integer level(s) [0..65535].

        Args:
            levels: Integer or NumPy array of integers in [0..65535]

        Returns:
            Transformed integer level(s) in [0..65535]
        """
        if isinstance(levels, (int, np.integer)):
            clamped = int(max(0, min(65535, int(levels))))
            return int(self.values_array_16bit[clamped])
        arr = np.clip(np.asarray(levels, dtype=np.int64), 0, 65535)
        return self.values_array_16bit[arr]

    def evaluate_range(
        self,
        level: float | np.ndarray,
        in_min: float = 0.0,
        in_max: float = 255.0,
        out_min: float = 0.0,
        out_max: float = 255.0,
    ) -> float | np.ndarray:
        """Evaluate the curve mapped from [in_min, in_max] to [out_min, out_max].

        Args:
            level: Input level or array
            in_min: Minimum of input range
            in_max: Maximum of input range
            out_min: Minimum of output range
            out_max: Maximum of output range

        Returns:
            Output level or array mapped to [out_min, out_max]
        """
        in_span = in_max - in_min
        out_span = out_max - out_min
        if in_span == 0:
            return out_min

        norm_in = np.clip((np.asarray(level) - in_min) / in_span, 0.0, 1.0)
        norm_out = self.evaluate_normalized(norm_in)
        result = out_min + norm_out * out_span
        if isinstance(level, (int, float, np.number)):
            return float(result)
        return result

    def populate_values(self) -> None:
        """Calculate each value of 8-bit and 16-bit lookup tables."""
        raise NotImplementedError

    def is_all_zero(self) -> bool:
        """Test if all curve values are 0.

        Returns:
            True if all zero, else False
        """
        if isinstance(self, LimitCurve) and self.limit == 0:
            return True
        return bool(np.all(self.values_array == 0))


class LinearCurve(Curve):
    """Linear transfer curve."""

    def __init__(self) -> None:
        super().__init__(name="Linear")

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        if isinstance(values, (int, float)):
            return max(0.0, min(1.0, float(values)))
        return np.clip(values, 0.0, 1.0)

    def populate_values(self) -> None:
        """Populate 8-bit and 16-bit lookup tables."""
        self.values_array = np.arange(256, dtype=np.uint8)
        self.values_array_16bit = np.arange(65536, dtype=np.uint16)


class SquareRootCurve(Curve):
    """Square Root (TV2, Linear Light) transfer curve."""

    def __init__(self) -> None:
        super().__init__(name="Square root")

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        if isinstance(values, (int, float)):
            clamped = max(0.0, min(1.0, float(values)))
            return float(np.sqrt(clamped))
        return np.sqrt(np.clip(values, 0.0, 1.0))

    def populate_values(self) -> None:
        """Populate 8-bit and 16-bit lookup tables."""
        self.values_array = np.round(np.sqrt(np.arange(256)) * np.sqrt(255)).astype(
            np.uint8
        )
        self.values_array_16bit = np.round(
            np.sqrt(np.arange(65536)) * np.sqrt(65535)
        ).astype(np.uint16)


class LimitCurve(Curve):
    """Proportional limitation transfer curve."""

    limit: int  # Limit value (0 - 255)

    def __init__(self, limit: int = 255) -> None:
        self.limit = limit
        super().__init__(name="Limit", editable=True)

    @property
    def normalized_limit(self) -> float:
        """Return the limit as a normalized fraction [0.0, 1.0]."""
        return max(0.0, min(1.0, self.limit / 255.0))

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        factor = self.normalized_limit
        if isinstance(values, (int, float)):
            clamped = max(0.0, min(1.0, float(values)))
            return float(clamped * factor)
        return np.clip(values, 0.0, 1.0) * factor

    def populate_values(self) -> None:
        """Populate 8-bit and 16-bit lookup tables."""
        factor = self.limit / 255.0
        self.values_array = np.round(np.arange(256) * factor).astype(np.uint8)
        self.values_array_16bit = np.round(np.arange(65536) * factor).astype(np.uint16)


class PointsCurve(Curve):
    """Base class for curves defined by control points."""

    points: list[tuple[int, int]]

    def __init__(self, name: str = "", editable: bool = False) -> None:
        self.points = [(0, 0), (255, 255)]
        super().__init__(name=name, editable=editable)

    @property
    def normalized_points(self) -> list[tuple[float, float]]:
        """Return control points in normalized [0.0, 1.0] domain."""
        return [(p[0] / 255.0, p[1] / 255.0) for p in self.points]

    def add_point(self, x: int, y: int) -> None:
        """Add point to curve.

        Args:
            x: X coordinate (0 - 255)
            y: Y coordinate (0 - 255)
        """
        x_clamped = min(max(int(round(x)), 0), 255)
        y_clamped = min(max(int(round(y)), 0), 255)
        if not any(x_clamped == point[0] for point in self.points):
            self.points.append((x_clamped, y_clamped))
            self.points.sort()
            self.populate_values()

    def add_normalized_point(self, x: float, y: float) -> None:
        """Add point using normalized coordinates [0.0, 1.0]."""
        self.add_point(int(round(x * 255.0)), int(round(y * 255.0)))

    def del_point(self, point_number: int) -> None:
        """Remove a point from curve.

        Args:
            point_number: Point index to remove
        """
        del self.points[point_number]
        self.populate_values()

    def set_point(self, point_number: int, x: int, y: int) -> None:
        """Change point values.

        Args:
            point_number: Point index
            x: X coordinate (0 - 255)
            y: Y coordinate (0 - 255)
        """
        x_clamped = min(max(int(round(x)), 0), 255)
        y_clamped = min(max(int(round(y)), 0), 255)
        if 0 <= point_number < len(self.points):
            self.points[point_number] = (x_clamped, y_clamped)
            self.populate_values()

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        raise NotImplementedError

    def populate_values(self) -> None:
        raise NotImplementedError


class SegmentsCurve(PointsCurve):
    """Linear segments curve."""

    def __init__(self) -> None:
        super().__init__(name="Segment", editable=True)

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        xp = [p[0] / 255.0 for p in self.points]
        fp = [p[1] / 255.0 for p in self.points]
        if isinstance(values, (int, float)):
            clamped = max(0.0, min(1.0, float(values)))
            return float(np.interp(clamped, xp, fp))
        return np.interp(np.clip(values, 0.0, 1.0), xp, fp)

    def populate_values(self) -> None:
        """Calculate 8-bit and 16-bit lookup tables."""
        if not hasattr(self, "values_array") or self.values_array is None:
            self.values_array = np.zeros(256, dtype=np.uint8)
        if not hasattr(self, "values_array_16bit") or self.values_array_16bit is None:
            self.values_array_16bit = np.zeros(65536, dtype=np.uint16)

        # 8-bit table
        xp_8 = [p[0] for p in self.points]
        fp_8 = [p[1] for p in self.points]
        self.values_array = np.round(np.interp(np.arange(256), xp_8, fp_8)).astype(
            np.uint8
        )

        # 16-bit table
        xp_16 = [p[0] / 255.0 * 65535.0 for p in self.points]
        fp_16 = [p[1] / 255.0 * 65535.0 for p in self.points]
        self.values_array_16bit = np.round(
            np.interp(np.arange(65536), xp_16, fp_16)
        ).astype(np.uint16)


class InterpolateCurve(PointsCurve):
    """Monotonic cubic spline curve using PCHIP interpolation."""

    def __init__(self) -> None:
        super().__init__(name="Interpolate", editable=True)

    def _get_interpolator(self) -> PchipInterpolator:
        xp = [p[0] / 255.0 for p in self.points]
        fp = [p[1] / 255.0 for p in self.points]
        return PchipInterpolator(xp, fp)

    def evaluate_normalized(self, values: float | np.ndarray) -> float | np.ndarray:
        spl = self._get_interpolator()
        if isinstance(values, (int, float)):
            clamped = max(0.0, min(1.0, float(values)))
            return float(np.clip(spl(clamped), 0.0, 1.0))
        return np.clip(spl(np.clip(values, 0.0, 1.0)), 0.0, 1.0)

    def populate_values(self) -> None:
        """Calculate 8-bit and 16-bit lookup tables using PCHIP."""
        if not hasattr(self, "values_array") or self.values_array is None:
            self.values_array = np.zeros(256, dtype=np.uint8)
        if not hasattr(self, "values_array_16bit") or self.values_array_16bit is None:
            self.values_array_16bit = np.zeros(65536, dtype=np.uint16)

        spl = self._get_interpolator()

        # 8-bit table
        grid_8 = np.linspace(0.0, 1.0, 256)
        vals_8 = np.clip(np.round(spl(grid_8) * 255.0), 0.0, 255.0)
        self.values_array = vals_8.astype(np.uint8)

        # 16-bit table
        grid_16 = np.linspace(0.0, 1.0, 65536)
        vals_16 = np.clip(np.round(spl(grid_16) * 65535.0), 0.0, 65535.0)
        self.values_array_16bit = vals_16.astype(np.uint16)


class Curves:
    """Curves supported by application.

    Curve numbers from 0 to 9 are reserved.
    """

    curves: dict[int, Curve]

    def __init__(self, lightshow: LightShow) -> None:
        self.lightshow = lightshow
        self.curves = {
            0: LinearCurve(),
            1: SquareRootCurve(),
        }
        self._default_curves()

    def _default_curves(self) -> None:
        curves = {
            2: ("Full at 1%", SegmentsCurve, ((2, 0), (3, 255))),
            3: (
                "IES Square",
                InterpolateCurve,
                (
                    (13, 18),
                    (26, 38),
                    (38, 56),
                    (51, 71),
                    (64, 84),
                    (77, 97),
                    (89, 107),
                    (102, 115),
                    (115, 122),
                    (128, 130),
                    (140, 140),
                    (153, 150),
                    (166, 161),
                    (179, 171),
                    (191, 184),
                    (204, 196),
                    (217, 209),
                    (230, 224),
                    (242, 240),
                ),
            ),
            4: (
                "Slow Bottom",
                InterpolateCurve,
                (
                    (13, 8),
                    (26, 13),
                    (38, 20),
                    (51, 28),
                    (64, 36),
                    (77, 48),
                    (89, 64),
                    (102, 82),
                    (115, 99),
                    (128, 120),
                    (140, 140),
                    (153, 161),
                    (166, 176),
                    (179, 194),
                    (191, 207),
                    (204, 219),
                    (217, 230),
                    (230, 240),
                    (242, 247),
                ),
            ),
            5: (
                "Fast Bottom",
                InterpolateCurve,
                (
                    (13, 26),
                    (26, 51),
                    (38, 74),
                    (51, 94),
                    (64, 110),
                    (77, 122),
                    (89, 133),
                    (102, 140),
                    (115, 150),
                    (128, 158),
                    (140, 166),
                    (153, 173),
                    (166, 181),
                    (179, 189),
                    (191, 199),
                    (204, 209),
                    (217, 219),
                    (230, 230),
                    (242, 242),
                ),
            ),
            6: (
                "Fast Top",
                InterpolateCurve,
                (
                    (13, 13),
                    (26, 26),
                    (38, 33),
                    (51, 41),
                    (64, 46),
                    (77, 51),
                    (89, 56),
                    (102, 64),
                    (115, 74),
                    (128, 89),
                    (140, 107),
                    (153, 128),
                    (166, 148),
                    (179, 168),
                    (191, 189),
                    (204, 207),
                    (217, 227),
                    (230, 242),
                    (242, 250),
                ),
            ),
        }
        for number, curve in curves.items():
            curve_obj = curve[1]()
            curve_obj.editable = False
            curve_obj.name = curve[0]
            if isinstance(curve_obj, PointsCurve):
                for point in curve[2]:
                    curve_obj.add_point(point[0], point[1])
            self.curves[number] = curve_obj

    def get_curve(self, number: int) -> Curve | None:
        """Get Curve with number.

        Args:
            number: Curve number (key in dictionary)

        Returns:
            Curve or None
        """
        return self.curves.get(number)

    def find_limit_curve(self, limit: int) -> int:
        """Find CurveLimit number if a curve with limit exists.

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
        """Add curve to curves list.

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
        """Delete curve.

        Args:
            curve_nb: Curve number
        """
        # First, change each output using deleted curve to LinearCurve (0)
        for value in self.lightshow.patch.outputs.values():
            for chan_dic in value.values():
                if chan_dic[1] == curve_nb:
                    chan_dic[1] = 0
        # Delete Curve from self.curves
        self.curves.pop(curve_nb, None)

    def reset(self) -> None:
        """Delete additional curves."""
        keys = []
        for curve_nb in self.curves:
            if curve_nb >= 10:
                keys.append(curve_nb)
        for key in keys:
            self.del_curve(key)
