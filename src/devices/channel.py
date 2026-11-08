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
"""DMX primitives: address, channel, channel range, and semantic definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FixtureType(Enum):
    """General classification of lighting devices."""

    DIMMER = "dimmer"
    MOVING_HEAD = "moving_head"
    LED_PAR = "led_par"
    STROBE = "strobe"
    LASER = "laser"
    GENERIC = "generic"


class ChannelType(Enum):
    """Semantic function of a DMX channel."""

    INTENSITY = "intensity"
    PAN = "pan"
    TILT = "tilt"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    WHITE = "white"
    AMBER = "amber"
    LIME = "lime"
    CYAN = "cyan"
    INDIGO = "indigo"
    MAGENTA = "magenta"
    YELLOW = "yellow"
    COLOR_WHEEL = "color_wheel"
    GOBO_WHEEL = "gobo_wheel"
    STROBE = "strobe"
    ZOOM = "zoom"
    FOCUS = "focus"
    IRIS = "iris"
    PRISM = "prism"
    FROST = "frost"
    MACRO = "macro"
    RESET = "reset"
    COLOR_TEMP = "color_temp"
    GENERIC = "generic"


COLOR_CHANNEL_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.RED,
        ChannelType.GREEN,
        ChannelType.BLUE,
        ChannelType.WHITE,
        ChannelType.AMBER,
        ChannelType.LIME,
        ChannelType.CYAN,
        ChannelType.INDIGO,
        ChannelType.MAGENTA,
        ChannelType.YELLOW,
    }
)

POSITION_CHANNEL_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.PAN,
        ChannelType.TILT,
    }
)

BEAM_CHANNEL_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.ZOOM,
        ChannelType.FOCUS,
        ChannelType.IRIS,
        ChannelType.STROBE,
        ChannelType.FROST,
        ChannelType.GOBO_WHEEL,
        ChannelType.PRISM,
        ChannelType.MACRO,
        ChannelType.RESET,
    }
)

CATEGORY_CHANNEL_TYPES: dict[str, frozenset[ChannelType]] = {
    "position": POSITION_CHANNEL_TYPES,
    "pos": POSITION_CHANNEL_TYPES,
    "color": COLOR_CHANNEL_TYPES,
    "colour": COLOR_CHANNEL_TYPES,
    "beam": BEAM_CHANNEL_TYPES,
    "intensity": frozenset({ChannelType.INTENSITY}),
    "int": frozenset({ChannelType.INTENSITY}),
}


class MergeMode(Enum):
    """Semantic merge mode for a DMX channel."""

    HTP = "htp"
    LTP = "ltp"


def get_default_merge_mode(channel_type: ChannelType) -> MergeMode:
    """Return default merge mode (HTP or LTP) for a given ChannelType."""
    if channel_type == ChannelType.INTENSITY:
        return MergeMode.HTP
    return MergeMode.LTP


@dataclass(frozen=True, order=True)
class DmxAddress:
    """Immutable absolute DMX address coordinate.

    universe: 1-based universe index.
    address: 1-based DMX channel address within the universe (1-512).
    """

    universe: int
    address: int

    def __post_init__(self) -> None:
        if self.universe < 1:
            raise ValueError(f"Invalid universe: {self.universe} (must be >= 1)")
        if not 1 <= self.address <= 512:
            raise ValueError(f"Invalid DMX address: {self.address} (must be 1-512)")

    @classmethod
    def parse(cls, s: str) -> DmxAddress:
        """Parse 'universe.address' or 'U<universe>:<address>' into DmxAddress."""
        if ":" in s:
            parts = s.lstrip("Uu").split(":")
        elif "." in s:
            parts = s.split(".")
        else:
            raise ValueError(f"Cannot parse DmxAddress from '{s}'")
        if len(parts) != 2:
            raise ValueError(f"Cannot parse DmxAddress from '{s}'")
        try:
            return cls(int(parts[0]), int(parts[1]))
        except ValueError as exc:
            raise ValueError(f"Invalid integer in DmxAddress '{s}'") from exc

    def next(self) -> DmxAddress:
        """Return the next sequential address, overflowing universe at 512."""
        if self.address < 512:
            return DmxAddress(self.universe, self.address + 1)
        return DmxAddress(self.universe + 1, 1)

    def offset(self, delta: int) -> DmxAddress:
        """Return address offset by delta channels (>= 0)."""
        if delta < 0:
            raise ValueError("Offset cannot be negative")
        total = self.address + delta
        univ = self.universe + (total - 1) // 512
        addr = ((total - 1) % 512) + 1
        return DmxAddress(univ, addr)

    def __str__(self) -> str:
        return f"{self.universe}.{self.address}"


@dataclass
class ChannelRange:  # pylint: disable=too-many-instance-attributes
    """Sub-range of values on a channel associated with a semantic feature.

    Common examples:
        ChannelRange("dimmer", ChannelType.INTENSITY, 0, 127)
        ChannelRange("strobe", ChannelType.STROBE, 128, 191, snap_value=160)
        ChannelRange("red", ChannelType.COLOR_WHEEL, 4, 7, snap_value=4)

    snap_value: Target value used when activating this range (None = midpoint).
    """

    label: str
    channel_type: ChannelType
    value_min: int
    value_max: int
    snap_value: Optional[int] = None
    description: str = ""
    physical_min: Optional[float] = None
    physical_max: Optional[float] = None
    physical_unit: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.value_min <= 255 and 0 <= self.value_max <= 255):
            raise ValueError(
                f"Invalid range bounds: [{self.value_min}, {self.value_max}]"
            )
        if self.value_min > self.value_max:
            raise ValueError(
                f"value_min ({self.value_min}) cannot exceed "
                f"value_max ({self.value_max})"
            )

    @property
    def width(self) -> int:
        """Total number of distinct DMX values covered by this range."""
        return self.value_max - self.value_min + 1

    @property
    def is_snap(self) -> bool:
        """True if the range contains a single discrete value."""
        return self.value_min == self.value_max

    @property
    def midpoint(self) -> int:
        """Central value of the range."""
        return (self.value_min + self.value_max) // 2

    @property
    def activation_value(self) -> int:
        """Value used when triggering this range."""
        if self.snap_value is not None:
            return max(self.value_min, min(self.value_max, self.snap_value))
        return self.midpoint

    def contains(self, value: int) -> bool:
        """Check if a DMX value falls within this range."""
        return self.value_min <= value <= self.value_max

    def value_at_percent(self, percent: float) -> int:
        """Calculate the absolute DMX value at a given percentage [0.0..100.0]."""
        pct = max(0.0, min(100.0, percent))
        return self.value_min + round(pct / 100.0 * (self.value_max - self.value_min))

    def percent_of(self, value: int) -> float:
        """Calculate relative percentage of a value within this range."""
        if self.width == 1:
            return 100.0
        return round(
            (value - self.value_min) / (self.value_max - self.value_min) * 100.0,
            1,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize ChannelRange to dictionary."""
        return {
            "label": self.label,
            "channel_type": self.channel_type.value,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "snap_value": self.snap_value,
            "description": self.description,
            "physical_min": self.physical_min,
            "physical_max": self.physical_max,
            "physical_unit": self.physical_unit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChannelRange:
        """Deserialize ChannelRange from dictionary."""
        return cls(
            label=str(data["label"]),
            channel_type=ChannelType(data["channel_type"]),
            value_min=int(data["value_min"]),
            value_max=int(data["value_max"]),
            snap_value=(
                int(data["snap_value"]) if data.get("snap_value") is not None else None
            ),
            description=str(data.get("description", "")),
            physical_min=(
                float(data["physical_min"])
                if data.get("physical_min") is not None
                else None
            ),
            physical_max=(
                float(data["physical_max"])
                if data.get("physical_max") is not None
                else None
            ),
            physical_unit=str(data.get("physical_unit", "")),
        )

    def __repr__(self) -> str:
        return (
            f"<ChannelRange '{self.label}' "
            f"[{self.value_min}-{self.value_max}] "
            f"type={self.channel_type.value}>"
        )


@dataclass
class Channel:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Individual DMX channel with absolute addressing and optional sub-ranges."""

    channel_type: ChannelType
    universe: int
    address: int
    value: int = 0
    default_value: int = 0
    highlight_value: Optional[int] = None
    fine: bool = False
    ultra_fine: bool = False
    label: str = ""
    ranges: list[ChannelRange] = field(default_factory=list)
    physical_min: float = 0.0
    physical_max: float = 1.0
    physical_unit: str = ""
    merge_mode: Optional[MergeMode] = None

    def __post_init__(self) -> None:
        DmxAddress(self.universe, self.address)  # Validate address bounds
        self.label = self.label or self.channel_type.value
        if self.merge_mode is None:
            self.merge_mode = get_default_merge_mode(self.channel_type)
        self._validate_ranges()
        self._clamp()

    @property
    def is_htp(self) -> bool:
        """True if this channel follows HTP (Highest Takes Precedence) merge rule."""
        return self.merge_mode == MergeMode.HTP

    @property
    def is_ltp(self) -> bool:
        """True if this channel follows LTP (Latest Takes Precedence) merge rule."""
        return self.merge_mode == MergeMode.LTP

    @property
    def is_coarse(self) -> bool:
        """True if this is the coarse (MSB / 8-bit) channel."""
        return not self.fine and not self.ultra_fine

    @property
    def is_fine(self) -> bool:
        """True if this is the 16-bit fine channel."""
        return self.fine

    @property
    def is_ultra_fine(self) -> bool:
        """True if this is the 24-bit ultra-fine channel."""
        return self.ultra_fine

    @property
    def resolution_byte_index(self) -> int:
        """Return byte significance index: 0=coarse, 1=fine, 2=ultra_fine."""
        if self.ultra_fine:
            return 2
        if self.fine:
            return 1
        return 0

    def _validate_ranges(self) -> None:
        if not self.ranges:
            return
        sorted_ranges = sorted(self.ranges, key=lambda r: r.value_min)
        for i, r in enumerate(sorted_ranges):
            if i > 0 and r.value_min <= sorted_ranges[i - 1].value_max:
                raise ValueError(
                    f"Overlapping ranges: '{sorted_ranges[i - 1].label}' "
                    f"and '{r.label}' on channel '{self.label}'"
                )

    def add_range(self, r: ChannelRange) -> Channel:
        """Add a ChannelRange to this channel."""
        self.ranges.append(r)
        self._validate_ranges()
        return self

    @property
    def dmx_address(self) -> DmxAddress:
        """Return the DmxAddress coordinate."""
        return DmxAddress(self.universe, self.address)

    @property
    def is_multi_function(self) -> bool:
        """True if multiple semantic sub-ranges are defined."""
        return len(self.ranges) > 0

    @property
    def percent(self) -> float:
        """Current level expressed as percentage [0.0..100.0]."""
        return round(self.value / 255.0 * 100.0, 1)

    @property
    def active_range(self) -> Optional[ChannelRange]:
        """Return currently active ChannelRange matching current value."""
        for r in self.ranges:
            if r.contains(self.value):
                return r
        return None

    @property
    def active_range_percent(self) -> Optional[float]:
        """Return relative percentage in currently active range."""
        ar = self.active_range
        return ar.percent_of(self.value) if ar else None

    def set_value(self, value: int) -> None:
        """Set absolute DMX value [0..255]."""
        self.value = value
        self._clamp()

    def set_percent(self, percent: float) -> None:
        """Set level from percentage [0.0..100.0]."""
        self.value = round(max(0.0, min(100.0, percent)) / 100.0 * 255.0)

    @property
    def normalized_value(self) -> float:
        """Return channel level normalized to [0.0..1.0]."""
        return self.value / 255.0

    def set_normalized(self, norm: float) -> None:
        """Set channel level from normalized float [0.0..1.0]."""
        self.value = round(max(0.0, min(1.0, float(norm))) * 255.0)

    def dmx_to_physical(self, dmx_value: Optional[int] = None) -> float:
        """Convert an 8-bit DMX value [0..255] to a physical value."""
        val = self.value if dmx_value is None else max(0, min(255, dmx_value))
        norm = val / 255.0
        return self.physical_min + norm * (self.physical_max - self.physical_min)

    def physical_to_dmx(self, physical_value: float) -> int:
        """Convert a physical value to an 8-bit DMX value [0..255]."""
        p_min = self.physical_min
        p_max = self.physical_max
        if p_max == p_min:
            return 0
        clamped = max(min(p_min, p_max), min(max(p_min, p_max), float(physical_value)))
        norm = (clamped - p_min) / (p_max - p_min)
        return round(norm * 255.0)

    @property
    def physical_value(self) -> float:
        """Current channel level expressed in physical units."""
        return self.dmx_to_physical()

    def set_physical_value(self, physical_value: float) -> None:
        """Set channel level from physical value."""
        self.set_value(self.physical_to_dmx(physical_value))

    def reset(self) -> None:
        """Reset value to default value."""
        self.value = self.default_value

    def locate(self) -> None:
        """Set channel to highlight/locate value or default."""
        if self.highlight_value is not None:
            self.value = self.highlight_value
        elif self.channel_type == ChannelType.INTENSITY:
            self.value = 255
        elif self.channel_type == ChannelType.STROBE:
            self.value = self.default_value if self.default_value != 0 else 255
        elif self.channel_type in COLOR_CHANNEL_TYPES:
            self.value = 255
        else:
            self.value = self.default_value

    def _clamp(self) -> None:
        self.value = max(0, min(255, self.value))

    def activate_range(self, label: str) -> None:
        """Activate range by label using its snap or midpoint value."""
        r = self.get_range(label)
        if r is None:
            raise KeyError(f"Range '{label}' not found on channel '{self.label}'")
        self.value = r.activation_value

    def set_range_percent(self, label: str, percent: float) -> None:
        """Set level as percentage relative to the specified range."""
        r = self.get_range(label)
        if r is None:
            raise KeyError(f"Range '{label}' not found on channel '{self.label}'")
        self.value = r.value_at_percent(percent)

    def set_range_value(self, label: str, value: int) -> None:
        """Set absolute value clamped within the specified range bounds."""
        r = self.get_range(label)
        if r is None:
            raise KeyError(f"Range '{label}' not found on channel '{self.label}'")
        self.value = max(r.value_min, min(r.value_max, value))

    def get_range(self, label: str) -> Optional[ChannelRange]:
        """Retrieve range by label."""
        for r in self.ranges:
            if r.label == label:
                return r
        return None

    def range_labels(self) -> list[str]:
        """List all defined range labels."""
        return [r.label for r in self.ranges]

    def __repr__(self) -> str:
        ar = self.active_range
        mode = f" [{ar.label}]" if ar else ""
        multi = f" ({len(self.ranges)} ranges)" if self.ranges else ""
        return (
            f"<Channel '{self.label}' @ {self.dmx_address} "
            f"val={self.value}{mode}{multi}>"
        )


__all__ = [
    "BEAM_CHANNEL_TYPES",
    "CATEGORY_CHANNEL_TYPES",
    "COLOR_CHANNEL_TYPES",
    "Channel",
    "ChannelRange",
    "ChannelType",
    "DmxAddress",
    "FixtureType",
    "MergeMode",
    "POSITION_CHANNEL_TYPES",
    "get_default_merge_mode",
]
