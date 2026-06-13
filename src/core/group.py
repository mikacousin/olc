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


@dataclass
class Group:
    """A Group is composed of channels at some DMX levels."""

    index: float
    channels: dict[int, int]
    text: str = ""

    def set_text(self, text: str) -> None:
        """Set the group's text description."""
        self.text = text

    def set_channel(self, channel: int, level: int) -> None:
        """Set the DMX level of a channel in the group."""
        self.channels[channel] = level

    def remove_channel(self, channel: int) -> None:
        """Remove a channel from the group."""
        if channel in self.channels:
            del self.channels[channel]

    def get_channel_level(self, channel: int, default: int = 0) -> int:
        """Get the DMX level of a channel, returning default if not present."""
        return self.channels.get(channel, default)

    def get_channels(self) -> dict[int, int]:
        """Return the dictionary of channels and their levels."""
        return self.channels

    def set_channels(self, channels: dict[int, int]) -> None:
        """Set/overwrite the dictionary of channels."""
        self.channels = channels

    def clear(self) -> None:
        """Clear all channels from the group."""
        self.channels.clear()
