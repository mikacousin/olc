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
import numpy as np

NUM_CHANNELS = 512


class DMXUniverse:
    """
    Represents the raw data of a DMX512 universe.
    """

    def __init__(self, universe_id: int = 0) -> None:
        self.universe_id = universe_id
        self._data = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        self._mv = memoryview(self._data)

    def __getitem__(self, ch: int) -> int:
        return int(self._data[ch])

    def __setitem__(self, ch: int, val: int) -> None:
        self._data[ch] = np.clip(val, 0, 255)

    def set_channel(self, ch: int, val: int) -> None:
        """Applies a raw value without clipping (for performance)."""
        self._data[ch] = val

    def set_channels(self, channels: dict[int, int]) -> None:
        """Applies a dictionary of channels."""
        idx = np.array(list(channels.keys()), dtype=np.intp)
        val = np.array(list(channels.values()), dtype=np.uint8)
        self._data[idx] = val

    def set_all(self, val: int) -> None:
        """Applies the same value to all channels."""
        self._data[:] = val

    def apply_array(self, arr: np.ndarray) -> None:
        """Copies an entire array without allocation."""
        np.copyto(self._data, arr)

    def blackout(self) -> None:
        """Resets the universe to zero."""
        self._data[:] = 0

    @property
    def array(self) -> np.ndarray:
        """Direct access to the underlying array."""
        return self._data

    @property
    def view(self) -> memoryview:
        """Direct access to the memory view for network sending (0-copy)."""
        return self._mv

    def slice_view(self, start: int, stop: int) -> memoryview:
        """Returns a sub-memory view."""
        return self._mv[start:stop]

    def snapshot(self) -> np.ndarray:
        """Returns a copy of the current frame."""
        return self._data.copy()

    def diff(self, other: np.ndarray) -> np.ndarray:
        """Returns the indices that have changed."""
        return np.where(self._data != other)[0]
