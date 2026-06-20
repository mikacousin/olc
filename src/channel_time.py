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


class ChannelTime:
    """Give a specific time to some channels in a step

    Attributes:
        delay (float): specific delay in seconds
        time (float): specific time in seconds
    """

    def __init__(self, delay: float = 0.0, time: float = 0.0) -> None:
        self.delay = delay
        self.time = time

    def get_delay(self) -> float:
        """Get specific delay

        Returns:
            Delay in seconds
        """
        return self.delay

    def get_time(self) -> float:
        """Get specific time

        Returns:
            Time in seconds
        """
        return self.time

    def set_delay(self, delay: float) -> None:
        """Set specific delay

        Args:
            delay: Delay in seconds
        """
        if isinstance(delay, float) and delay >= 0:
            self.delay = delay

    def set_time(self, time: float) -> None:
        """Set specific time

        Args:
            time: Time in seconds
        """
        if isinstance(time, float) and time >= 0:
            self.time = time
