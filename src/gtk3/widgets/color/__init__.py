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
"""Color picker GUI components."""

from olc.gtk3.widgets.color.cie_xy import CIExyWidget
from olc.gtk3.widgets.color.hs_disc import DISC_SIZE, HSDiscWidget
from olc.gtk3.widgets.color.point import FixtureColorPoint
from olc.gtk3.widgets.color.swatch import SWATCH_HEIGHT, SWATCH_WIDTH, SwatchButton

__all__ = [
    "CIExyWidget",
    "DISC_SIZE",
    "FixtureColorPoint",
    "HSDiscWidget",
    "SWATCH_HEIGHT",
    "SWATCH_WIDTH",
    "SwatchButton",
]
