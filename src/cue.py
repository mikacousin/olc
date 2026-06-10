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
import typing

import numpy as np
from olc.define import MAX_CHANNELS


class CueChannels(dict[int, int]):
    """Custom dictionary to keep the array cache in sync with in-place changes."""

    # pylint: disable=protected-access

    def __init__(self, cue: "Cue", *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.cue = cue

    def __setitem__(self, key: int, value: int) -> None:
        super().__setitem__(key, value)
        if self.cue._channels_array is not None:
            if 1 <= key <= MAX_CHANNELS:
                self.cue._channels_array[key - 1] = value

    def __delitem__(self, key: int) -> None:
        super().__delitem__(key)
        self.cue._channels_array = None

    def clear(self) -> None:
        super().clear()
        self.cue._channels_array = None

    def update(  # ty: ignore[invalid-method-override]
        self,
        m: typing.Mapping[int, int] | typing.Iterable[tuple[int, int]] = (),
        /,
    ) -> None:
        super().update(m)
        self.cue._channels_array = None


class Cue:
    """Cue/Preset object
    A Cue or a Preset is used to store intensities for playback in a Sequence.
    A Cue is attached to a sequence and a Preset is a global memory
    """

    sequence: int  # Sequence number (0 for Preset)
    memory: float  # Cue number
    _channels: CueChannels  # Channels levels
    text: str  # Cue text
    _channels_array: np.ndarray | None

    def __init__(
        self,
        sequence: int,
        memory: float,
        channels: dict[int, int] | None = None,
        text: str = "",
    ) -> None:
        self.sequence = sequence
        self.memory = memory
        self._channels_array = None
        self._channels = CueChannels(self, channels or {})
        self.text = text

    @property
    def channels(self) -> dict[int, int]:
        """Get the channel levels dictionary."""
        return self._channels

    @channels.setter
    def channels(self, value: dict[int, int]) -> None:
        self._channels = CueChannels(self, value)
        self._channels_array = None

    @property
    def channels_array(self) -> np.ndarray:
        """Cached array representation of cue channels for block calculations."""
        if self._channels_array is None:
            arr = np.zeros(MAX_CHANNELS, dtype=np.uint8)
            for channel, level in self.channels.items():
                if 1 <= channel <= MAX_CHANNELS:
                    arr[channel - 1] = level
            self._channels_array = arr
        return self._channels_array

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
            if self._channels_array is not None:
                self._channels_array[channel - 1] = level

    def get_level(self, channel: int) -> int:
        """Get channel's level

        Args:
            channel: channel number (1-MAX_CHANNELS)

        Returns:
            channel's level (0-255)
        """
        return self.channels.get(channel, 0)
