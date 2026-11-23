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
from collections.abc import Mapping

import numpy as np

from olc.define import MAX_CHANNELS
from olc.show.editor import TempChannelsEditor
from olc.show.palette import PaletteRef, serialize_palette_refs

if typing.TYPE_CHECKING:
    from olc.show.lightshow import LightShow


class CueChannels(dict[int, int | float]):
    """Custom dictionary to keep the array cache in sync with in-place changes."""

    # pylint: disable=protected-access

    def __init__(self, cue: "Cue", *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.cue = cue

    def __setitem__(self, key: int, value: int | float) -> None:
        super().__setitem__(key, value)
        if self.cue._channels_array is not None:
            ch_int = int(key)
            if 1 <= ch_int <= MAX_CHANNELS:
                self.cue._channels_array[ch_int - 1] = float(value)

    def __delitem__(self, key: int) -> None:
        super().__delitem__(key)
        self.cue._channels_array = None

    def clear(self) -> None:
        super().clear()
        self.cue._channels_array = None

    def update(  # ty: ignore[incompatible-method-override]
        self,
        m: typing.Mapping[int, int | float]
        | typing.Iterable[tuple[int, int | float]] = (),
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
    device_values: dict[int, dict[str, typing.Any]]
    palette_refs: dict[int, dict[str, PaletteRef]]
    effect_refs: dict[int, dict[str, typing.Any]]
    is_block: bool
    is_assert: bool
    is_int_block: bool
    notes: str
    execute_preset: float | None

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        sequence: int,
        number: float,
        channels: Mapping[int, int | float] | None = None,
        text: str = "",
        device_values: dict[int, dict[str, typing.Any]] | None = None,
        is_block: bool = False,
        palette_refs: dict[int, dict[str, PaletteRef]] | None = None,
        effect_refs: dict[int, dict[str, typing.Any]] | None = None,
        is_assert: bool = False,
        is_int_block: bool = False,
        notes: str = "",
        execute_preset: float | None = None,
    ) -> None:
        self.sequence = sequence
        self.number = number
        self._channels_array = None
        self._channels = CueChannels(self, channels or {})
        self.text = text
        self.device_values = device_values if device_values is not None else {}
        self.palette_refs = palette_refs if palette_refs is not None else {}
        self.effect_refs = effect_refs if effect_refs is not None else {}
        self.is_block = is_block
        self.is_assert = bool(is_assert)
        self.is_int_block = bool(is_int_block)
        self.notes = str(notes)
        self.execute_preset = (
            float(execute_preset) if execute_preset is not None else None
        )

    @property
    def channels(self) -> dict[int, int | float]:
        """Get the channel levels dictionary."""
        return self._channels

    @channels.setter
    def channels(self, value: Mapping[int, int | float]) -> None:
        self._channels = CueChannels(self, value)
        self._channels_array = None

    @property
    def channels_array(self) -> np.ndarray:
        """Cached array representation of cue channels for block calculations."""
        if self._channels_array is None:
            arr = np.zeros(MAX_CHANNELS, dtype=np.float64)
            for channel, level in self.channels.items():
                ch_int = int(channel)
                if 1 <= ch_int <= MAX_CHANNELS:
                    arr[ch_int - 1] = float(level)
            self._channels_array = arr
        return self._channels_array

    def set_level(self, channel: int, level: int | float) -> None:
        """Set normalized level of a channel.

        Args :
            channel: channel number (1-MAX_CHANNELS)
            level: normalized level (0.0 - 1.0)
        """
        if (
            isinstance(level, (int, float))
            and 0.0 <= level <= 1.0
            and isinstance(channel, int)
            and 0 < channel <= MAX_CHANNELS
        ):
            val = float(level)
            self.channels[channel] = val
            if self._channels_array is not None:
                self._channels_array[channel - 1] = val

    def get_level(self, channel: int) -> float:
        """Get channel's normalized level (including fallback to device_values).

        Args:
            channel: channel number (1-MAX_CHANNELS)

        Returns:
            channel's normalized level (0.0 - 1.0)
        """
        lvl = float(self.channels.get(channel, 0.0))
        if lvl == 0.0 and channel in self.device_values:
            dev_int = self.device_values[channel].get("intensity")
            if isinstance(dev_int, (int, float)):
                lvl = max(0.0, min(1.0, float(dev_int)))
        return lvl

    def get_active_channels_count(self) -> int:
        """Return total number of channels and devices defined in this cue."""
        return len(set(self.channels.keys()) | set(self.device_values.keys()))

    def has_channel_or_device(self, channel: int) -> bool:
        """Return True if channel has an explicit level or device parameters."""
        return bool(self.channels.get(channel) or self.has_device(channel))

    def set_device_parameter(
        self,
        device_id: int,
        param_name: str,
        value: typing.Any,  # noqa: ANN401
    ) -> None:
        """Set a physical parameter value for a specific device in this cue."""
        if device_id not in self.device_values:
            self.device_values[device_id] = {}
        self.device_values[device_id][param_name] = value

    def get_device_parameter(
        self,
        device_id: int,
        param_name: str,
        default: typing.Any = None,  # noqa: ANN401
    ) -> typing.Any:  # noqa: ANN401
        """Get a physical parameter value for a specific device in this cue."""
        return self.device_values.get(device_id, {}).get(param_name, default)

    def get_device_parameters(self, device_id: int) -> dict[str, typing.Any]:
        """Get all parameter values defined for a specific device in this cue."""
        return self.device_values.get(device_id, {})

    def has_device(self, device_id: int) -> bool:
        """True if any parameters are explicitly defined for device_id."""
        return device_id in self.device_values and bool(self.device_values[device_id])

    def clear_device(self, device_id: int) -> None:
        """Remove all explicit parameter values for device_id."""
        self.device_values.pop(device_id, None)

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize Cue to a dictionary."""
        d: dict[str, typing.Any] = {
            "sequence": self.sequence,
            "number": self.number,
            "label": self.text,
            "channels": dict(self.channels),
        }
        if self.device_values:
            d["device_values"] = {
                int(k): dict(v) for k, v in self.device_values.items()
            }
        if self.palette_refs:
            d["palette_refs"] = serialize_palette_refs(self.palette_refs)
        if self.is_block:
            d["is_block"] = self.is_block
        if self.is_assert:
            d["is_assert"] = self.is_assert
        if self.is_int_block:
            d["is_int_block"] = self.is_int_block
        if self.notes:
            d["notes"] = self.notes
        if self.execute_preset is not None:
            d["execute_preset"] = self.execute_preset
        return d


class _CueTempChannelsEditor(TempChannelsEditor[tuple[float, int]]):
    """Internal TempChannelsEditor subclass for Cues."""

    def _notify_changed(self, key: tuple[float, int]) -> None:
        """Notify that the cue editor state has changed.

        Args:
            key: Identification key of the edited cue (number, sequence).
        """
        number, sequence = key
        if self.lightshow and self.lightshow.app:
            self.lightshow.app.emit("cue_editor.changed", sequence, number)


class CueEditor:
    """Manages the temporary channel levels during cue editing, agnostic to the UI."""

    def __init__(self, lightshow: LightShow | None = None) -> None:
        """Initialize the CueEditor.

        Args:
            lightshow: The LightShow model instance.
        """
        self._editor = _CueTempChannelsEditor(lightshow)

    @property
    def lightshow(self) -> LightShow | None:
        """The LightShow model instance."""
        return self._editor.lightshow

    def get_levels(self, number: float, sequence: int) -> np.ndarray:
        """Retrieve the temporary channel overrides for a specific cue.

        Args:
            number: Cue number.
            sequence: Sequence index.

        Returns:
            An ndarray containing DMX levels (-1 representing no modification).
        """
        return self._editor.get_levels((number, sequence))

    def set_level(
        self, number: float, sequence: int, channel: int, level: float
    ) -> None:
        """Set a temporary level override for a single channel.

        Args:
            number: Cue number.
            sequence: Sequence index.
            channel: Channel number (1-based).
            level: The temporary normalized level (0.0-1.0).
        """
        self._editor.set_level((number, sequence), channel, level)

    def clear(self, number: float, sequence: int) -> None:
        """Clear all temporary channel overrides for a specific cue.

        Args:
            number: Cue number.
            sequence: Sequence index.
        """
        self._editor.clear((number, sequence))

    def has_overrides(self, number: float, sequence: int) -> bool:
        """Check if a specific cue has any active channel level overrides.

        Args:
            number: Cue number.
            sequence: Sequence index.

        Returns:
            True if at least one channel has an active override, else False.
        """
        return self._editor.has_overrides((number, sequence))
