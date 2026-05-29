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
import time

import numpy as np
from olc.core.universe_data import NUM_CHANNELS


class LTPMerger:
    """
    Merges N DMX sources according to the LTP (Latest Takes Precedence) rule:
    the source that wrote to a channel most recently wins.
    """

    def __init__(self, num_sources: int) -> None:
        self._num_sources = num_sources
        self._values = np.zeros((num_sources, NUM_CHANNELS), dtype=np.uint8)
        self._timestamps = np.zeros((num_sources, NUM_CHANNELS), dtype=np.float64)
        self._idx = np.arange(NUM_CHANNELS)

    def write(self, source_id: int, channels: dict[int, int]) -> None:
        """Writes specific channels for a source."""
        now = time.monotonic()
        idx = np.array(list(channels.keys()), dtype=np.intp)
        val = np.array(list(channels.values()), dtype=np.uint8)
        self._values[source_id, idx] = val
        self._timestamps[source_id, idx] = now

    def write_universe(self, source_id: int, arr: np.ndarray) -> None:
        """Writes an entire universe (512 array) for a source."""
        self._values[source_id] = arr
        self._timestamps[source_id] = time.monotonic()

    def get_output(self, out: np.ndarray | None = None) -> np.ndarray:
        """
        Calculates the merged universe.
        If `out` is provided, writes into it without allocation.
        """
        latest = np.argmax(self._timestamps, axis=0)
        result = self._values[latest, self._idx]
        if out is not None:
            np.copyto(out, result)
            return out
        return result


class HTPMerger:
    """
    Merges N DMX sources according to the HTP (Highest Takes Precedence) rule:
    the highest value wins on each channel.
    """

    def __init__(self, num_sources: int) -> None:
        self._num_sources = num_sources
        self._values = np.zeros((num_sources, NUM_CHANNELS), dtype=np.uint8)

    def write(self, source_id: int, channels: dict[int, int]) -> None:
        """Writes specific channels for a source."""
        idx = np.array(list(channels.keys()), dtype=np.intp)
        val = np.array(list(channels.values()), dtype=np.uint8)
        self._values[source_id, idx] = val

    def write_universe(self, source_id: int, arr: np.ndarray) -> None:
        """Writes an entire universe (512 array) for a source."""
        self._values[source_id] = arr

    def get_output(self, out: np.ndarray | None = None) -> np.ndarray:
        """
        Calculates the merged universe.
        If `out` is provided, writes into it without allocation.
        """
        result = np.max(self._values, axis=0)
        if out is not None:
            np.copyto(out, result)
            return out
        return result
