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


# pylint: disable=too-few-public-methods,too-many-nested-blocks
# pylint: disable=too-many-arguments,too-many-positional-arguments
class MergeMode(Enum):
    """sACN Merging Mode for equal-priority sources."""

    HTP = auto()
    LTP = auto()


class Source:
    """Represents a single active sACN source transmitting DMX."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self, cid: bytes, name: str, priority: int, data: list[int], ip: str = ""
    ) -> None:
        self.cid = cid
        self.name = name
        self.priority = priority
        self.data = list(data)
        self.ip = ip
        self.last_seen = time.time()


class SacnMerger:
    """E1.31 sACN Merging logic supporting priorities and HTP/LTP fallbacks."""

    def __init__(
        self,
        universe: int,
        mode: MergeMode = MergeMode.HTP,
        timeout: float = 2.5,
        callback: Callable[[int, list[int]], None] | None = None,
    ) -> None:
        self.universe = universe
        self.mode = mode
        self.timeout = timeout
        self.callback = callback
        self.sources: dict[bytes, Source] = {}
        self._last_merged: list[int] = [0] * 512

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def update(
        self,
        cid: bytes,
        name: str,
        priority: int,
        data: list[int],
        stream_terminated: bool = False,
        ip: str = "",
    ) -> None:
        """Update a source's DMX values and trigger a merge."""
        if stream_terminated:
            # Terminate this source immediately
            self.sources.pop(cid, None)
        else:
            if cid in self.sources:
                src = self.sources[cid]
                src.name = name
                src.priority = priority
                src.data = list(data)
                src.ip = ip
                src.last_seen = time.time()
            else:
                self.sources[cid] = Source(cid, name, priority, data, ip)

        self.merge()

    def merge(self) -> None:
        """Merge all active sources according to sACN priority rules."""
        now = time.time()
        # Filter active sources (not timed out)
        active_sources = [
            src for src in self.sources.values() if now - src.last_seen < self.timeout
        ]

        # Cleanup timed out sources
        self.sources = {src.cid: src for src in active_sources}

        if not active_sources:
            merged = [0] * 512
        else:
            # Find the highest priority among all active sources
            max_priority = max(src.priority for src in active_sources)
            highest_sources = [
                src for src in active_sources if src.priority == max_priority
            ]

            if len(highest_sources) == 1:
                # Sole highest priority source wins completely
                merged = list(highest_sources[0].data)
            else:
                # Merge multiple sources sharing the highest priority
                merged = [0] * 512
                if self.mode == MergeMode.HTP:
                    # Highest Takes Precedence
                    for src in highest_sources:
                        for i in range(512):
                            if src.data[i] > merged[i]:
                                merged[i] = src.data[i]
                else:
                    # Latest Takes Precedence
                    # Find the source with the most recent timestamp
                    newest_src = max(highest_sources, key=lambda s: s.last_seen)
                    merged = list(newest_src.data)

        # Trigger callback if merged DMX data has changed
        if merged != self._last_merged:
            self._last_merged = list(merged)
            if self.callback:
                self.callback(self.universe, merged)
