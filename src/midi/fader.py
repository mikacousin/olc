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
from enum import Enum, auto


class FaderState(Enum):
    """MIDI fader states"""

    VALID = auto()
    UP = auto()
    DOWN = auto()


class MIDIFader:
    """MIDI fader"""

    value: float
    valid: FaderState

    def __init__(self):
        self.value = 0
        self.valid = FaderState.VALID

    def get_value(self) -> float:
        """Get fader value

        Returns:
            Fader value
        """
        return self.value

    def set_state(self, value: int) -> None:
        """Set Fader state

        Args:
            value: Value of object attached to MIDI fader (Fader, GM, Independent)
        """
        if value > self.value:
            self.valid = FaderState.UP
        elif value < self.value:
            self.valid = FaderState.DOWN
        else:
            self.valid = FaderState.VALID

    def is_valid(self, new_value: int, level: int) -> bool:
        """Is fader valid

        Args:
            new_value: New value
            level: level to compare

        Returns:
            True if anchored, else False
        """
        self.value = new_value
        if (self.valid is FaderState.UP
                and self.value < level) or (self.valid is FaderState.DOWN
                                            and self.value > level):
            return False
        self.valid = FaderState.VALID
        return True
