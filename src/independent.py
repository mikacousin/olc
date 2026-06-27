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

import numpy as np
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.core.lightshow import LightShow


# pylint: disable=too-many-instance-attributes
class Independent:
    """Independent object
    Control channels excluded from recording

    Attributes:
        number (int): independent number
        level (int): independent level (0-255)
        channels (set): channels present in independent
        levels (Dict[int, int]): channels levels
        text (str): independent text
        inde_type (str): knob or button
        dmx (array): DMX levels
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        number: int,
        independents: Independents,
        text: str = "",
        levels: dict[int, int] | None = None,
        inde_type: str = "knob",
    ) -> None:
        self.number = number
        self.independents = independents
        self.level = 0
        self.channels = set()
        self.levels = levels or {}
        self.text = text
        self.inde_type = inde_type
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)

        self.update_channels()

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.independents.app

    def update_channels(self) -> None:
        """Update set of channels"""
        for channel, level in self.levels.items():
            if level:
                self.channels.add(channel)

    def set_levels(self, levels: dict[int, int]) -> None:
        """Define channels and levels

        Args:
            levels (Dict[int, int]): channels levels
        """
        self.levels = levels
        self.channels = {channel for channel, level in levels.items() if level}

    def set_level(self, value: int) -> None:
        """Set independent level

        Args:
            value: New level
        """
        # Send MIDI message to knob LEDs (only for knobs 1 to 6)
        if self.number <= 6:
            if self.app and hasattr(self.app, "midi") and self.app.midi:
                self.app.midi.messages.control_change.send(
                    f"inde_led_{self.number}", 32 + int((value / 255) * 12)
                )
        self.level = value
        self.update_dmx()

    def update_dmx(self) -> None:
        """Update DMX levels"""
        for channel, level in self.levels.items():
            dmx_lvl = round(level * (self.level / 255))
            self.dmx[channel - 1] = dmx_lvl
        self.independents.update_dmx()
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            self.app.backend.dmx.set_levels()


class Independents:
    """All independents

    Attributes:
        independents (list): list of independents
        channels (set): list of channels present in independents
    """

    def __init__(self, lightshow: typing.Optional[LightShow] = None) -> None:
        self.lightshow = lightshow
        self.independents: list[Independent] = []
        self.channels = set()
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)

        # Create 9 Independents
        for i in range(6):
            self.add(Independent(i + 1, self))
        for i in range(6, 9):
            self.add(Independent(i + 1, self, inde_type="button"))

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.lightshow.app if self.lightshow else None

    def update_dmx(self) -> None:
        """Update DMX levels"""
        self.dmx.fill(0)
        for inde in self.independents:
            self.dmx = np.maximum(self.dmx, inde.dmx)

    def add(self, independent: Independent) -> bool:
        """Add an independent

        Args:
            independent: Independent object

        Returns:
            True or False
        """
        number = independent.number
        for inde in self.independents:
            if inde.number == number:
                print("Independent already exist")
                return False
        self.independents.append(independent)
        self.update_channels()
        return True

    def update(self, independent: Independent) -> None:
        """Update independent

        Args:
            independent: Independent object
        """
        number = independent.number
        text = independent.text
        levels = independent.levels
        self.independents[number - 1].text = text
        self.independents[number - 1].set_levels(levels)
        self.update_channels()

    def get_channels(self) -> set[int]:
        """
        Returns:
            (set) channels presents in all independent
        """
        return self.channels

    def update_channels(self) -> None:
        """Update set of channels present in all independents"""
        self.channels = set()
        for inde in self.independents:
            self.channels = self.channels | inde.channels
