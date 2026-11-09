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
"""Park manager for locking channel and physical DMX address levels."""

from __future__ import annotations

import typing


class ParkManager:
    """Manages parked channels and physical DMX output addresses."""

    def __init__(self) -> None:
        self.parked_channels: dict[int, int] = {}
        self.parked_addresses: dict[tuple[int, int], int] = {}

    def park_channel(self, channel: int, level: int) -> None:
        """Park a channel at a given DMX level (0-255).

        Args:
            channel: 1-based channel number.
            level: DMX value clamped between 0 and 255.
        """
        clamped = max(0, min(255, int(level)))
        self.parked_channels[channel] = clamped

    def unpark_channel(self, channel: int) -> int | None:
        """Unpark a channel.

        Args:
            channel: 1-based channel number.

        Returns:
            Previous parked DMX level, or None if channel was not parked.
        """
        return self.parked_channels.pop(channel, None)

    def park_address(self, universe: int, output: int, level: int) -> None:
        """Park a physical DMX address at a given DMX level (0-255).

        Args:
            universe: DMX universe number.
            output: 1-based DMX slot (1-512).
            level: DMX value clamped between 0 and 255.
        """
        clamped = max(0, min(255, int(level)))
        self.parked_addresses[(universe, output)] = clamped

    def unpark_address(self, universe: int, output: int) -> int | None:
        """Unpark a physical DMX address.

        Args:
            universe: DMX universe number.
            output: 1-based DMX slot (1-512).

        Returns:
            Previous parked DMX level, or None if address was not parked.
        """
        return self.parked_addresses.pop((universe, output), None)

    def unpark_all(
        self,
    ) -> tuple[dict[int, int], dict[tuple[int, int], int]]:
        """Unpark all parked channels and addresses.

        Returns:
            Tuple of previous (parked_channels, parked_addresses).
        """
        old_channels = dict(self.parked_channels)
        old_addresses = dict(self.parked_addresses)
        self.parked_channels.clear()
        self.parked_addresses.clear()
        return old_channels, old_addresses

    def is_channel_parked(self, channel: int) -> bool:
        """Return True if channel is parked."""
        return channel in self.parked_channels

    def get_channel_park_level(self, channel: int) -> int | None:
        """Return parked level for channel, or None if not parked."""
        return self.parked_channels.get(channel)

    def is_address_parked(self, universe: int, output: int) -> bool:
        """Return True if physical address is parked."""
        return (universe, output) in self.parked_addresses

    def get_address_park_level(self, universe: int, output: int) -> int | None:
        """Return parked level for physical address, or None if not parked."""
        return self.parked_addresses.get((universe, output))

    def total_parked_count(self) -> int:
        """Return total number of parked channels and addresses."""
        return len(self.parked_channels) + len(self.parked_addresses)

    def clear(self) -> None:
        """Clear all parked entries without returning previous state."""
        self.parked_channels.clear()
        self.parked_addresses.clear()

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize park state to dictionary for show persistence."""
        return {
            "channels": {str(ch): lvl for ch, lvl in self.parked_channels.items()},
            "addresses": {
                f"{u}/{o}": lvl for (u, o), lvl in self.parked_addresses.items()
            },
        }

    def from_dict(self, data: dict[str, typing.Any]) -> None:
        """Restore park state from dictionary."""
        self.clear()
        channels = data.get("channels", {})
        if isinstance(channels, dict):
            for k, v in channels.items():
                try:
                    self.park_channel(int(k), int(v))
                except (ValueError, TypeError):
                    pass
        addresses = data.get("addresses", {})
        if isinstance(addresses, dict):
            for k, v in addresses.items():
                try:
                    parts = str(k).split("/")
                    if len(parts) == 2:
                        u, o = int(parts[0]), int(parts[1])
                        self.park_address(u, o, int(v))
                except (ValueError, TypeError):
                    pass
