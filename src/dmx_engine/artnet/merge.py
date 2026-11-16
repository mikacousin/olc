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
from enum import Enum, auto
from typing import Callable


class MergeMode(Enum):
    """Art-Net DMX Merge Modes"""

    HTP = auto()  # Highest Takes Precedence
    LTP = auto()  # Latest Takes Precedence


# pylint: disable=too-few-public-methods
class ArtDmxMerger:
    """Manages merging of multiple ArtDmx sources per universe."""

    mode: MergeMode
    timeout: float
    callback: Callable | None
    buffers: dict[int, dict[str, tuple[list[int], float]]]

    def __init__(
        self,
        mode: MergeMode = MergeMode.HTP,
        timeout: float = 4.0,
        callback: Callable | None = None,
    ) -> None:
        self.mode = mode
        self.timeout = timeout
        self.callback = callback
        # Dictionary organized by: {universe: {source_ip: (dmx_data_list, timestamp)}}
        self.buffers = {}

    def update(self, universe: int, source_ip: str, data: list[int]) -> None:
        """Update source data and trigger merging/callback."""
        now = time.time()

        if universe not in self.buffers:
            self.buffers[universe] = {}

        sources = self.buffers[universe]

        # Art-Net merge rules: Limit to exactly 2 sources.
        if source_ip not in sources and len(sources) >= 2:
            self._cleanup_timeouts(universe, now)
            if len(self.buffers[universe]) >= 2:
                # Still 2 active sources, drop this 3rd source packet totally
                return

        # Update the buffer for this IP
        sources[source_ip] = (data, now)

        # Remove dead sources
        self._cleanup_timeouts(universe, now)

        # Merge available active sources
        merged_data = self._merge(universe)

        if self.callback:
            self.callback(universe, merged_data)

    def _cleanup_timeouts(self, universe: int, now: float) -> None:
        """Remove sources that have not sent data for self.timeout seconds."""
        if universe not in self.buffers:
            return
        sources = self.buffers[universe]
        dead_sources = [
            ip for ip, (_, ts) in sources.items() if (now - ts) > self.timeout
        ]
        for ip in dead_sources:
            del sources[ip]

    def _merge(self, universe: int) -> list[int]:
        """Perform HTP or LTP merge."""
        sources = self.buffers[universe]

        # No sources (should not happen since we just updated one, but safe guard)
        if not sources:
            return [0] * 512

        # 1 single active source
        if len(sources) == 1:
            return list(sources.values())[0][0]

        # 2 active sources
        s1, s2 = list(sources.values())
        data1, ts1 = s1
        data2, ts2 = s2

        # Ensure both are length 512 using padding
        d1 = data1 + [0] * (512 - len(data1))
        d2 = data2 + [0] * (512 - len(data2))

        if self.mode == MergeMode.HTP:
            # HTP: Compare each channel and take the maximum
            return [max(v1, v2) for v1, v2 in zip(d1, d2, strict=True)]

        # LTP: The source which received data most recently wins completely
        return d1 if ts1 > ts2 else d2
