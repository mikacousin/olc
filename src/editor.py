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
"""Base editor for temporary DMX channel levels."""

from __future__ import annotations

import typing

import numpy as np
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow

K = typing.TypeVar("K")


class TempChannelsEditor(typing.Generic[K]):
    """Base class for managing temporary channel level overrides."""

    def __init__(self, lightshow: LightShow | None = None) -> None:
        """Initialize the TempChannelsEditor.

        Args:
            lightshow: The LightShow model instance.
        """
        self.lightshow = lightshow
        # Temporary overrides: maps entity key to an ndarray of MAX_CHANNELS levels
        self._temp_overrides: dict[K, np.ndarray] = {}

    def _get_levels_internal(self, key: K) -> np.ndarray:
        """Retrieve the temporary channel overrides internal method.

        Args:
            key: Identification key of the edited entity.

        Returns:
            An ndarray containing DMX levels (-1 representing no modification).
        """
        if key not in self._temp_overrides:
            self._temp_overrides[key] = np.full(MAX_CHANNELS, -1, dtype=np.int16)
        return self._temp_overrides[key]

    def get_levels(self, key: K) -> np.ndarray:
        """Retrieve the temporary channel overrides for a specific key.

        Args:
            key: Identification key of the edited entity.

        Returns:
            An ndarray containing DMX levels (-1 representing no modification).
        """
        return self._get_levels_internal(key)

    def set_level(self, key: K, channel: int, level: int) -> None:
        """Set a temporary level override for a single channel.

        Args:
            key: Identification key of the edited entity.
            channel: Channel number (1-based).
            level: The temporary DMX level (0-255).
        """
        if 1 <= channel <= MAX_CHANNELS:
            levels = self._get_levels_internal(key)
            levels[channel - 1] = level
            self._notify_changed(key)

    def clear(self, key: K) -> None:
        """Clear all temporary channel overrides for a specific key.

        Args:
            key: Identification key of the edited entity.
        """
        if key in self._temp_overrides:
            self._temp_overrides[key].fill(-1)
            self._notify_changed(key)

    def has_overrides(self, key: K) -> bool:
        """Check if a specific key has any active channel level overrides.

        Args:
            key: Identification key of the edited entity.

        Returns:
            True if at least one channel has an active override, else False.
        """
        if key in self._temp_overrides:
            return bool(np.any(self._temp_overrides[key] != -1))
        return False

    def _notify_changed(self, key: K) -> None:
        """Notify changes. To be overridden by subclasses.

        Args:
            key: Identification key of the edited entity.
        """
