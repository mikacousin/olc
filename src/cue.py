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
from __future__ import annotations

import typing

import numpy as np
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow


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
    A Cue is attached to a sequence and a Preset is global
    """

    sequence: int  # Sequence number (0 for Preset)
    number: float  # Cue number
    _channels: CueChannels  # Channels levels
    text: str  # Cue text
    _channels_array: np.ndarray | None

    def __init__(
        self,
        sequence: int,
        number: float,
        channels: dict[int, int] | None = None,
        text: str = "",
    ) -> None:
        self.sequence = sequence
        self.number = number
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


class Cues:
    """Cues container class.

    Wraps a list of Cue objects and acts as a proxy list while providing
    high-level methods for lookup, sorted insertion, and validation.
    """

    def __init__(self, _lightshow: object = None) -> None:
        """Initialize the Cues container."""
        self._cues: list[Cue] = []
        self._lightshow = _lightshow
        self.cue_editor = CueEditor(typing.cast("LightShow | None", _lightshow))

    def __len__(self) -> int:
        """Return the number of cues."""
        return len(self._cues)

    @typing.overload
    def __getitem__(self, index: int) -> Cue: ...

    @typing.overload
    def __getitem__(self, index: slice) -> list[Cue]: ...

    def __getitem__(self, index: int | slice) -> Cue | list[Cue]:
        """Get Cue at list position index or slice."""
        return self._cues[index]

    def __delitem__(self, index: int | slice) -> None:
        """Delete Cue(s) at list position or slice."""
        del self._cues[index]

    def __iter__(self) -> typing.Iterator[Cue]:
        """Iterate over all cues."""
        return iter(self._cues)

    def get(self, number: float, sequence: int) -> Cue | None:
        """Retrieve a Cue by its number and sequence index.

        Args:
            number: Cue number.
            sequence: Sequence index (0 for presets).

        Returns:
            The matching Cue or None.
        """
        for cue in self._cues:
            if cue.number == number and cue.sequence == sequence:
                return cue
        return None

    def add(self, cue: Cue) -> None:
        """Add a Cue in sorted number order.

        Args:
            cue: Cue object to add.

        Raises:
            ValueError: If a cue with the same (number, sequence) already exists.
        """
        if self.get(cue.number, cue.sequence) is not None:
            raise ValueError(f"Cue {cue.number} (seq {cue.sequence}) already exists.")

        # Find insertion index to maintain sorted order
        insert_idx = len(self._cues)
        for i, c in enumerate(self._cues):
            if cue.number < c.number:
                insert_idx = i
                break
        self._cues.insert(insert_idx, cue)

    def append(self, cue: Cue) -> None:
        """Append a Cue (adds in sorted order).

        Args:
            cue: Cue object to append.
        """
        self.add(cue)

    def remove(self, cue: Cue) -> None:
        """Remove a Cue.

        Args:
            cue: Cue object to remove.
        """
        if cue in self._cues:
            self._cues.remove(cue)

    def insert(self, _idx: int, cue: Cue) -> None:
        """Insert a Cue (adds in sorted order).

        Args:
            _idx: Intended list index.
            cue: Cue object.
        """
        self.add(cue)

    def pop(self, idx: int) -> Cue:
        """Pop a Cue at list position idx.

        Args:
            idx: List index.

        Returns:
            The popped Cue.
        """
        return self._cues.pop(idx)

    def clear(self) -> None:
        """Clear all cues."""
        self._cues.clear()


class CueEditor:
    """Manages the temporary channel levels during cue editing, agnostic to the UI."""

    def __init__(self, lightshow: LightShow | None = None) -> None:
        """Initialize the CueEditor.

        Args:
            lightshow: The LightShow model instance.
        """
        self.lightshow = lightshow
        # Temporary overrides: maps (number, sequence) to an ndarray
        # of MAX_CHANNELS levels
        self._temp_overrides: dict[tuple[float, int], np.ndarray] = {}

    def get_levels(self, number: float, sequence: int) -> np.ndarray:
        """Retrieve the temporary channel overrides for a specific cue.

        Args:
            number: Cue number.
            sequence: Sequence index.

        Returns:
            An ndarray containing DMX levels (-1 representing no modification).
        """
        key = (number, sequence)
        if key not in self._temp_overrides:
            self._temp_overrides[key] = np.full(MAX_CHANNELS, -1, dtype=np.int16)
        return self._temp_overrides[key]

    def set_level(self, number: float, sequence: int, channel: int, level: int) -> None:
        """Set a temporary level override for a single channel.

        Args:
            number: Cue number.
            sequence: Sequence index.
            channel: Channel number (1-based).
            level: The temporary DMX level (0-255).
        """
        if 1 <= channel <= MAX_CHANNELS:
            levels = self.get_levels(number, sequence)
            levels[channel - 1] = level
            if self.lightshow and self.lightshow.app:
                app = self.lightshow.app
                if hasattr(app, "core"):
                    app = app.core
                app.emit("cue_editor.changed", sequence, number)

    def clear(self, number: float, sequence: int) -> None:
        """Clear all temporary channel overrides for a specific cue.

        Args:
            number: Cue number.
            sequence: Sequence index.
        """
        key = (number, sequence)
        if key in self._temp_overrides:
            self._temp_overrides[key].fill(-1)
            if self.lightshow and self.lightshow.app:
                app = self.lightshow.app
                if hasattr(app, "core"):
                    app = app.core
                app.emit("cue_editor.changed", sequence, number)

    def has_overrides(self, number: float, sequence: int) -> bool:
        """Check if a specific cue has any active channel level overrides.

        Args:
            number: Cue number.
            sequence: Sequence index.

        Returns:
            True if at least one channel has an active override, else False.
        """
        key = (number, sequence)
        if key in self._temp_overrides:
            return bool(np.any(self._temp_overrides[key] != -1))
        return False
