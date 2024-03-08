# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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


class MainFader:
    """Main Fader"""

    value: float

    def __init__(self):
        self.value = 1.0

    def set_level(self, value: float) -> None:
        """Set Main Fader level

        Args:
            value: New level (0 - 1)
        """
        self.value = value

    def get_level(self) -> float:
        """Get Main Fader level

        Returns:
            level (0 - 1)
        """
        return self.value
