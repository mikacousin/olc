# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Dict

from olc.define import MAX_CHANNELS


class Cue:
    """Cue/Preset object
    A Cue or a Preset is used to store intensities for playback in a Sequence.
    A Cue is attached to a sequence and a Preset is a global memory
    """

    sequence: int  # Sequence number (0 for Preset)
    memory: float  # Cue number
    channels: Dict[int, int]  # Channels levels
    text: str  # Cue text

    def __init__(
        self,
        sequence,
        memory,
        channels=None,
        text="",
    ):

        self.sequence = sequence
        self.memory = memory
        self.channels = channels or {}
        self.text = text

    def set_level(self, channel: int, level: int) -> None:
        """Set level of a channel.

        Args :
            channel: channel number (1-MAX_CHANNELS)
            level: level (0 - 255)
        """
        if (
            isinstance(level, int)
            and 0 <= level < 256
            and isinstance(channel, int)
            and 0 < channel <= MAX_CHANNELS
        ):
            self.channels[channel] = level

    def get_level(self, channel: int) -> int:
        """Get channel's level

        Args:
            channel: channel number (1-MAX_CHANNELS)

        Returns:
            channel's level (0-255)
        """
        return self.channels.get(channel, 0)
