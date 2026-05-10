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
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator


class Protocol(Enum):
    """Output protocol."""

    ARNET = auto()
    SACN = auto()


_UNIVERSE_0_FORBIDDEN: frozenset[Protocol] = frozenset({Protocol.SACN})


@dataclass
class ArtNetSettings:
    net: int = 0  # 0-127
    sub: int = 0  # 0-15

    def __post_init__(self) -> None:
        if not (0 <= self.net <= 127):
            raise ValueError(f"ArtNet net must be 0-127, got {self.net}")
        if not (0 <= self.sub <= 15):
            raise ValueError(f"ArtNet sub must be 0-15, got {self.sub}")


@dataclass
class SacnSettings:
    priority: int = 100  # 1-200

    def __post_init__(self) -> None:
        if not (1 <= self.priority <= 200):
            raise ValueError(f"sACN priority must be 1-200, got {self.priority}")


class UniverseConfig:
    """Universe configuration"""

    _id: int
    _protocols: set[Protocol]
    artnet: ArtNetSettings
    sacn: SacnSettings

    def __init__(self, universe_id: int) -> None:
        if not isinstance(universe_id, int) or universe_id < 0:
            raise ValueError(
                f"universe_id must be a non-negative integer, got {universe_id!r}"
            )
        self._id = universe_id
        self._protocols = set()
        self.artnet = ArtNetSettings()
        self.sacn = SacnSettings()

    @property
    def universe_id(self) -> int:
        return self._id

    @property
    def protocols(self) -> frozenset[Protocol]:
        return frozenset(self._protocols)

    def enable(self, *protocols: Protocol) -> None:
        """Add one or more protocols to this universe"""
        for p in protocols:
            self._check_allowed(p)
            self._protocols.add(p)

    def disable(self, *protocols: Protocol) -> None:
        """Remove one or more protocols to this universe"""
        for p in protocols:
            self._protocols.discard(p)

    def set_protocols(self, protocols: set[Protocol]) -> None:
        """Replace the active protocol set entirely"""
        for protocol in protocols:
            self._check_allowed(protocol)
        self._protocols = protocols

    def disable_all(self) -> None:
        """Silence this universe (remove all protocols)"""
        self._protocols.clear()

    def _check_allowed(self, protocol: Protocol) -> None:
        if self._id == 0 and protocol in _UNIVERSE_0_FORBIDDEN:
            raise ValueError(f"Protocol.{protocol.name} is not allowed on universe 0")


class UniverseMap:
    """All universe configurations"""

    _universes: dict[int, UniverseConfig]

    def __init__(self, num_universes: int = 256) -> None:
        if num_universes < 1:
            raise ValueError("num_universe must be at least 1")
        self._universes = {uid: UniverseConfig(uid) for uid in range(num_universes)}

    def __getitem__(self, universe_id: int) -> UniverseConfig:
        self._check_exists(universe_id)
        return self._universes[universe_id]

    def __contains__(self, universe_id: int) -> bool:
        return universe_id in self._universes

    def __iter__(self) -> Iterator[UniverseConfig]:
        return iter(self._universes.values())

    def __len__(self) -> int:
        return len(self._universes)

    def set_protocols(self, universe_id: int, protocols: set[Protocol]) -> None:
        self._universes[universe_id].set_protocols(protocols)

    def enable_protocol(self, universe_id: int, protocol: Protocol) -> None:
        self._universes[universe_id].enable(protocol)

    def disable_protocol(self, universe_id: int, protocol: Protocol) -> None:
        self._universes[universe_id].disable(protocol)

    def disable_universe(self, universe_id: int) -> None:
        self._universes[universe_id].disable_all()

    def _check_exists(self, universe_id: int) -> None:
        if universe_id not in self._universes:
            raise KeyError(
                f"Universe {universe_id} does not exist "
                f"(valid range: 0-{len(self._universes) - 1})"
            )
