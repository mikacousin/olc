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
"""DMX primitives: address, channel, channel range, and patched lighting device."""

# pylint: disable=too-many-lines

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

from .color import CIExyY, ColorMatcher, FixtureColorProfile, sRGB

if TYPE_CHECKING:
    from olc.curve import Curve


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
    COLOR_WHEEL = "color_wheel"
    GOBO_WHEEL = "gobo_wheel"
    STROBE = "strobe"
    ZOOM = "zoom"
    FOCUS = "focus"
    IRIS = "iris"
    PRISM = "prism"
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
    }
)


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


class LightingDevice:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Patched lighting fixture in the show."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        fixture_id: int,
        label: str,
        fixture_type: FixtureType,
        channels: Optional[list[Channel]] = None,
        group: str = "",
        notes: str = "",
        color_profile: Optional[FixtureColorProfile] = None,
    ) -> None:
        self.fixture_id = fixture_id
        self.label = label
        self.fixture_type = fixture_type
        self.channels: list[Channel] = channels or []
        self.group = group
        self.notes = notes
        self.color_profile = color_profile
        self._enabled = True
        self._locked = False
        self._created_at = time.time()

        # Virtual controls and normalized states
        self.curve_id: int = 0
        self._curve: Optional[Curve] = None
        self._curve_provider: Optional[Callable[[int], Optional[Curve]]] = None
        self._intensity: float = 0.0 if self.has_physical_dimmer else 1.0
        self._target_color: sRGB = sRGB(1.0, 1.0, 1.0)
        self._target_cie: CIExyY = CIExyY(0.3127, 0.3290, 100.0)
        self._base_emitters: dict[ChannelType, float] = {}
        self._init_base_emitters()

    def set_curve_id(self, curve_id: int) -> None:
        """Set curve ID for the device intensity transfer function."""
        self.curve_id = max(0, int(curve_id))

    def set_curve(self, curve: Optional[Curve]) -> None:
        """Directly assign a Curve instance."""
        self._curve = curve
        if curve is not None and hasattr(curve, "number"):
            self.curve_id = getattr(curve, "number", 0)

    def set_curve_provider(
        self, provider: Optional[Callable[[int], Optional[Curve]]]
    ) -> None:
        """Set a callable (curve_id -> Curve) to resolve curves dynamically."""
        self._curve_provider = provider

    def get_effective_curve(self) -> Optional[Curve]:
        """Resolve effective Curve instance if assigned."""
        if self._curve is not None:
            return self._curve
        if self.curve_id != 0 and self._curve_provider is not None:
            return self._curve_provider(self.curve_id)
        return None

    def _init_base_emitters(self) -> None:
        """Initialize base emitter levels to open white."""
        for ch in self.channels:
            if ch.channel_type in COLOR_CHANNEL_TYPES:
                self._base_emitters[ch.channel_type] = 1.0

    def add_channel(self, channel: Channel) -> LightingDevice:
        """Add a Channel to this device."""
        self.channels.append(channel)
        if channel.channel_type in COLOR_CHANNEL_TYPES:
            if channel.channel_type not in self._base_emitters:
                self._base_emitters[channel.channel_type] = 1.0
        if channel.channel_type == ChannelType.INTENSITY:
            self._intensity = 0.0
        return self

    def get_channel(self, channel_type: ChannelType) -> Optional[Channel]:
        """Get first coarse channel matching the given ChannelType."""
        for ch in self.channels:
            if ch.channel_type == channel_type and not ch.fine and not ch.ultra_fine:
                return ch
        for ch in self.channels:
            if ch.channel_type == channel_type:
                return ch
        return None

    def get_channels(self, channel_type: ChannelType) -> list[Channel]:
        """Get all channels matching the given ChannelType."""
        return [ch for ch in self.channels if ch.channel_type == channel_type]

    def channel_count(self) -> int:
        """Total number of channels in this device."""
        return len(self.channels)

    def universes(self) -> list[int]:
        """List of universes spanned by this device."""
        return sorted({ch.universe for ch in self.channels})

    def channels_by_universe(self) -> dict[int, list[Channel]]:
        """Group channels by universe index."""
        result: dict[int, list[Channel]] = {}
        for ch in self.channels:
            result.setdefault(ch.universe, []).append(ch)
        return {
            u: sorted(chs, key=lambda c: c.address) for u, chs in sorted(result.items())
        }

    def footprint(self) -> dict[int, tuple[int, int]]:
        """Return {universe: (start_address, end_address)}."""
        return {
            u: (chs[0].address, chs[-1].address)
            for u, chs in self.channels_by_universe().items()
        }

    def patch_summary(self) -> str:
        """Human-readable summary of universe and address footprints."""
        fp = self.footprint()
        if not fp:
            return "unpatched"
        return " | ".join(f"U{u}:{s}-{e}" for u, (s, e) in fp.items())

    # Resolution channel helpers
    def _get_resolution_channels(
        self, channel_type: ChannelType
    ) -> tuple[Optional[Channel], Optional[Channel], Optional[Channel]]:
        """Get (coarse_channel, fine_channel, ultra_fine_channel) for ChannelType."""
        coarse_ch = None
        fine_ch = None
        ultra_fine_ch = None
        for ch in self.channels:
            if ch.channel_type == channel_type:
                if ch.ultra_fine:
                    ultra_fine_ch = ch
                elif ch.fine:
                    fine_ch = ch
                elif coarse_ch is None:
                    coarse_ch = ch
        return coarse_ch, fine_ch, ultra_fine_ch

    def _get_coarse_fine_channels(
        self, channel_type: ChannelType
    ) -> tuple[Optional[Channel], Optional[Channel]]:
        """Get (coarse_channel, fine_channel) for the specified ChannelType."""
        coarse_ch, fine_ch, _ = self._get_resolution_channels(channel_type)
        return coarse_ch, fine_ch

    # Dimmer and virtual dimmer properties
    @property
    def has_physical_dimmer(self) -> bool:
        """True if the device has at least one physical INTENSITY channel."""
        return any(
            ch.channel_type == ChannelType.INTENSITY
            and not ch.fine
            and not ch.ultra_fine
            for ch in self.channels
        )

    @property
    def has_16bit_dimmer(self) -> bool:
        """True if the physical dimmer is 16-bit (coarse + fine)."""
        return any(
            ch.channel_type == ChannelType.INTENSITY and ch.fine for ch in self.channels
        )

    @property
    def has_24bit_dimmer(self) -> bool:
        """True if the physical dimmer is 24-bit (coarse + fine + ultra-fine)."""
        return any(
            ch.channel_type == ChannelType.INTENSITY and ch.ultra_fine
            for ch in self.channels
        )

    @property
    def uses_virtual_dimmer(self) -> bool:
        """True if fixture has color emitters but no physical INTENSITY channel."""
        return not self.has_physical_dimmer and any(
            ch.channel_type in COLOR_CHANNEL_TYPES for ch in self.channels
        )

    # Intensity controls [0.0, 1.0]
    @property
    def intensity(self) -> float:
        """Normalized intensity level in range [0.0, 1.0]."""
        return self._intensity

    @property
    def intensity_8bit(self) -> int:
        """Intensity level as an 8-bit integer in range [0..255]."""
        return round(self._intensity * 255.0)

    @property
    def intensity_16bit(self) -> int:
        """Intensity level as a 16-bit integer in range [0..65535]."""
        return round(self._intensity * 65535.0)

    @property
    def intensity_24bit(self) -> int:
        """Intensity level as a 24-bit integer in range [0..16777215]."""
        return round(self._intensity * 16777215.0)

    @property
    def intensity_percent(self) -> float:
        """Intensity level as a percentage in range [0.0..100.0]."""
        return round(self._intensity * 100.0, 1)

    def set_intensity(self, value: float | int) -> None:
        """Set intensity level.

        Accepts normalized float [0.0, 1.0] or 8-bit int [0..255].
        Values > 1.0 are treated as 8-bit integers and normalized.
        """
        if isinstance(value, (int, float)) and value > 1.0:
            norm_val = max(0.0, min(1.0, float(value) / 255.0))
        else:
            norm_val = max(0.0, min(1.0, float(value)))
        self._intensity = norm_val
        self._apply_intensity()

    def set_intensity_8bit(self, value: int) -> None:
        """Set intensity from 8-bit integer [0..255]."""
        self.set_intensity(max(0, min(255, value)) / 255.0)

    def set_intensity_16bit(self, value: int) -> None:
        """Set intensity from 16-bit integer [0..65535]."""
        clamped = max(0, min(65535, value))
        self._intensity = clamped / 65535.0
        self._apply_intensity()

    def set_intensity_24bit(self, value: int) -> None:
        """Set intensity from 24-bit integer [0..16777215]."""
        clamped = max(0, min(16777215, value))
        self._intensity = clamped / 16777215.0
        self._apply_intensity()

    def set_intensity_percent(self, percent: float) -> None:
        """Set intensity from percentage [0.0..100.0]."""
        self.set_intensity(max(0.0, min(100.0, percent)) / 100.0)

    def _apply_intensity(self) -> None:
        """Propagate intensity to DMX channels, applying effective curve if any."""
        curve = self.get_effective_curve()
        if self.has_physical_dimmer:
            coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
                ChannelType.INTENSITY
            )
            if (
                ultra_fine_ch is not None
                and fine_ch is not None
                and coarse_ch is not None
            ):
                raw_24 = round(self._intensity * 16777215.0)
                val_24 = curve.get_level_24bit(raw_24) if curve else raw_24
                coarse_ch.set_value((val_24 >> 16) & 0xFF)
                fine_ch.set_value((val_24 >> 8) & 0xFF)
                ultra_fine_ch.set_value(val_24 & 0xFF)
            elif fine_ch is not None and coarse_ch is not None:
                raw_16 = round(self._intensity * 65535.0)
                val_16 = curve.get_level_16bit(raw_16) if curve else raw_16
                coarse_ch.set_value((val_16 >> 8) & 0xFF)
                fine_ch.set_value(val_16 & 0xFF)
            elif coarse_ch is not None:
                raw_8 = round(self._intensity * 255.0)
                val_8 = curve.get_level(raw_8) if curve else raw_8
                coarse_ch.set_value(val_8)
        elif self.uses_virtual_dimmer:
            self._apply_virtual_dimmer(curve=curve)

    def _apply_virtual_dimmer(self, curve: Optional[Curve] = None) -> None:
        """Scale base emitter levels by current intensity (curved if assigned)."""
        eff_intensity = (
            curve.evaluate_normalized(self._intensity) if curve else self._intensity
        )
        for ch in self.channels:
            if ch.channel_type in COLOR_CHANNEL_TYPES:
                base_val = self._base_emitters.get(ch.channel_type, 0.0)
                scaled_dmx = round(base_val * eff_intensity * 255.0)
                ch.set_value(max(0, min(255, scaled_dmx)))

    # Color controls
    @property
    def color_rgb(self) -> tuple[int, int, int]:
        """Return (r, g, b) tuple [0..255] of base target color."""
        return self._target_color.to_255()

    @property
    def color_srgb(self) -> sRGB:
        """Return target color as normalized sRGB instance."""
        return self._target_color

    @property
    def color_cie(self) -> CIExyY:
        """Return target color as CIE xyY chromaticity."""
        return self._target_cie

    def set_color_srgb(self, r: float, g: float, b: float) -> None:
        """Set color from normalized sRGB components [0.0, 1.0]."""
        r_norm = max(0.0, min(1.0, float(r)))
        g_norm = max(0.0, min(1.0, float(g)))
        b_norm = max(0.0, min(1.0, float(b)))
        self._target_color = sRGB(r_norm, g_norm, b_norm)
        self._target_cie = self._target_color.to_XYZ().to_xyY()

        if self.color_profile is not None:
            self._solve_emitters_from_cie(self._target_cie)
        else:
            self._base_emitters[ChannelType.RED] = r_norm
            self._base_emitters[ChannelType.GREEN] = g_norm
            self._base_emitters[ChannelType.BLUE] = b_norm
        self._apply_color()

    def set_color_rgb(self, r: int, g: int, b: int) -> None:
        """Set color from 8-bit integer RGB components [0..255]."""
        self.set_color_srgb(r / 255.0, g / 255.0, b / 255.0)

    def set_color_hex(self, hex_str: str) -> None:
        """Set color from HTML hex string (#RRGGBB)."""
        c = sRGB.from_hex(hex_str)
        self.set_color_srgb(c.r, c.g, c.b)

    def set_color_cie(
        self,
        x: float,
        y: float,
        Y: float = 100.0,  # pylint: disable=invalid-name
    ) -> None:
        """Set color from CIE xyY chromaticity coordinates."""
        self._target_cie = CIExyY(x, y, Y)
        srgb = self._target_cie.to_XYZ().to_srgb()
        self._target_color = srgb
        if self.color_profile is not None:
            self._solve_emitters_from_cie(self._target_cie)
        else:
            self._base_emitters[ChannelType.RED] = srgb.r
            self._base_emitters[ChannelType.GREEN] = srgb.g
            self._base_emitters[ChannelType.BLUE] = srgb.b
        self._apply_color()

    def set_color(self, r: int, g: int, b: int, w: int = 0, a: int = 0) -> None:
        """Set color emitter channel values directly [0..255]."""
        r_norm = max(0, min(255, r)) / 255.0
        g_norm = max(0, min(255, g)) / 255.0
        b_norm = max(0, min(255, b)) / 255.0
        w_norm = max(0, min(255, w)) / 255.0
        a_norm = max(0, min(255, a)) / 255.0

        self._base_emitters[ChannelType.RED] = r_norm
        self._base_emitters[ChannelType.GREEN] = g_norm
        self._base_emitters[ChannelType.BLUE] = b_norm
        self._base_emitters[ChannelType.WHITE] = w_norm
        self._base_emitters[ChannelType.AMBER] = a_norm

        self._target_color = sRGB(r_norm, g_norm, b_norm)
        self._target_cie = self._target_color.to_XYZ().to_xyY()
        self._apply_color()

    def _solve_emitters_from_cie(self, cie: CIExyY) -> None:
        """Calculate emitter fractions using NNLS ColorMatcher."""
        if self.color_profile is None:
            return
        matcher = ColorMatcher([self.color_profile])
        matches = matcher.match_cie(cie.x, cie.y, cie.Y)
        result = matches.get(self.color_profile.fixture_name)
        if result:
            name_map = {
                "red": ChannelType.RED,
                "green": ChannelType.GREEN,
                "blue": ChannelType.BLUE,
                "white": ChannelType.WHITE,
                "amber": ChannelType.AMBER,
            }
            for emitter_name, dmx_val in result.as_dict().items():
                ctype = name_map.get(emitter_name.lower())
                if ctype:
                    self._base_emitters[ctype] = dmx_val / 255.0

    def _apply_color(self) -> None:
        """Apply base emitters to DMX channels."""
        if self.uses_virtual_dimmer:
            self._apply_virtual_dimmer()
        else:
            for ch in self.channels:
                if ch.channel_type in COLOR_CHANNEL_TYPES:
                    base_val = self._base_emitters.get(ch.channel_type, 0.0)
                    ch.set_value(round(base_val * 255.0))

    # Physical and multi-resolution helpers
    def _set_physical_parameter(self, channel_type: ChannelType, value: float) -> None:
        """Set a parameter value using physical range (supports 8/16/24-bit)."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(channel_type)
        if coarse_ch is None:
            return

        p_min = coarse_ch.physical_min
        p_max = coarse_ch.physical_max
        if p_max == p_min:
            norm = 0.0
        else:
            clamped = max(min(p_min, p_max), min(max(p_min, p_max), float(value)))
            norm = (clamped - p_min) / (p_max - p_min)

        if ultra_fine_ch is not None and fine_ch is not None:
            val_24 = round(norm * 16777215.0)
            coarse_ch.set_value((val_24 >> 16) & 0xFF)
            fine_ch.set_value((val_24 >> 8) & 0xFF)
            ultra_fine_ch.set_value(val_24 & 0xFF)
        elif fine_ch is not None:
            val_16 = round(norm * 65535.0)
            coarse_ch.set_value((val_16 >> 8) & 0xFF)
            fine_ch.set_value(val_16 & 0xFF)
        else:
            val_8 = round(norm * 255.0)
            coarse_ch.set_value(val_8)

    def _get_physical_parameter(self, channel_type: ChannelType) -> Optional[float]:
        """Get parameter value in physical units, reconstructing 8/16/24-bit."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(channel_type)
        if coarse_ch is None:
            return None

        p_min = coarse_ch.physical_min
        p_max = coarse_ch.physical_max

        if ultra_fine_ch is not None and fine_ch is not None:
            raw_24 = (
                (coarse_ch.value << 16) | (fine_ch.value << 8) | ultra_fine_ch.value
            )
            norm = raw_24 / 16777215.0
        elif fine_ch is not None:
            raw_16 = (coarse_ch.value << 8) | fine_ch.value
            norm = raw_16 / 65535.0
        else:
            norm = coarse_ch.value / 255.0

        return p_min + norm * (p_max - p_min)

    # Position controls (8-bit, 16-bit, 24-bit and physical degrees)
    def set_position(self, pan: int, tilt: int) -> None:
        """Set pan and tilt coordinates (8-bit) [0..255]."""
        self.set_pan(pan)
        self.set_tilt(tilt)

    def set_position_16bit(self, pan: int, tilt: int) -> None:
        """Set pan and tilt coordinates (16-bit) [0..65535]."""
        self.set_pan_16bit(pan)
        self.set_tilt_16bit(tilt)

    def set_position_24bit(self, pan: int, tilt: int) -> None:
        """Set pan and tilt coordinates (24-bit) [0..16777215]."""
        self.set_pan_24bit(pan)
        self.set_tilt_24bit(tilt)

    def set_position_degrees(self, pan: float, tilt: float) -> None:
        """Set pan and tilt coordinates in physical degrees."""
        self.set_pan_degrees(pan)
        self.set_tilt_degrees(tilt)

    def set_pan(self, pan: int) -> None:
        """Set pan coordinate (8-bit) [0..255]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        if coarse_ch:
            coarse_ch.set_value(pan)
        if fine_ch:
            fine_ch.set_value(0)
        if ultra_fine_ch:
            ultra_fine_ch.set_value(0)

    def set_pan_16bit(self, pan: int) -> None:
        """Set pan coordinate (16-bit) [0..65535]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        clamped = max(0, min(65535, int(pan)))
        if fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 8) & 0xFF)
            fine_ch.set_value(clamped & 0xFF)
            if ultra_fine_ch:
                ultra_fine_ch.set_value(0)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 65535.0 * 255.0))

    def set_pan_24bit(self, pan: int) -> None:
        """Set pan coordinate (24-bit) [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        clamped = max(0, min(16777215, int(pan)))
        if ultra_fine_ch and fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 16) & 0xFF)
            fine_ch.set_value((clamped >> 8) & 0xFF)
            ultra_fine_ch.set_value(clamped & 0xFF)
        elif fine_ch and coarse_ch:
            val_16 = round(clamped / 16777215.0 * 65535.0)
            coarse_ch.set_value((val_16 >> 8) & 0xFF)
            fine_ch.set_value(val_16 & 0xFF)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 16777215.0 * 255.0))

    def set_tilt(self, tilt: int) -> None:
        """Set tilt coordinate (8-bit) [0..255]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        if coarse_ch:
            coarse_ch.set_value(tilt)
        if fine_ch:
            fine_ch.set_value(0)
        if ultra_fine_ch:
            ultra_fine_ch.set_value(0)

    def set_tilt_16bit(self, tilt: int) -> None:
        """Set tilt coordinate (16-bit) [0..65535]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        clamped = max(0, min(65535, int(tilt)))
        if fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 8) & 0xFF)
            fine_ch.set_value(clamped & 0xFF)
            if ultra_fine_ch:
                ultra_fine_ch.set_value(0)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 65535.0 * 255.0))

    def set_tilt_24bit(self, tilt: int) -> None:
        """Set tilt coordinate (24-bit) [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        clamped = max(0, min(16777215, int(tilt)))
        if ultra_fine_ch and fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 16) & 0xFF)
            fine_ch.set_value((clamped >> 8) & 0xFF)
            ultra_fine_ch.set_value(clamped & 0xFF)
        elif fine_ch and coarse_ch:
            val_16 = round(clamped / 16777215.0 * 65535.0)
            coarse_ch.set_value((val_16 >> 8) & 0xFF)
            fine_ch.set_value(val_16 & 0xFF)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 16777215.0 * 255.0))

    def set_pan_degrees(self, angle: float) -> None:
        """Set pan coordinate in physical degrees."""
        self._set_physical_parameter(ChannelType.PAN, angle)

    def set_tilt_degrees(self, angle: float) -> None:
        """Set tilt coordinate in physical degrees."""
        self._set_physical_parameter(ChannelType.TILT, angle)

    @property
    def pan_16bit(self) -> int:
        """Return pan coordinate as 16-bit integer [0..65535]."""
        coarse_ch, fine_ch = self._get_coarse_fine_channels(ChannelType.PAN)
        if not coarse_ch:
            return 0
        if fine_ch:
            return (coarse_ch.value << 8) | fine_ch.value
        return coarse_ch.value * 257

    @property
    def pan_24bit(self) -> int:
        """Return pan coordinate as 24-bit integer [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        if not coarse_ch:
            return 0
        if ultra_fine_ch and fine_ch:
            return (coarse_ch.value << 16) | (fine_ch.value << 8) | ultra_fine_ch.value
        if fine_ch:
            raw_16 = (coarse_ch.value << 8) | fine_ch.value
            return round(raw_16 / 65535.0 * 16777215.0)
        return round(coarse_ch.value / 255.0 * 16777215.0)

    @property
    def tilt_16bit(self) -> int:
        """Return tilt coordinate as 16-bit integer [0..65535]."""
        coarse_ch, fine_ch = self._get_coarse_fine_channels(ChannelType.TILT)
        if not coarse_ch:
            return 0
        if fine_ch:
            return (coarse_ch.value << 8) | fine_ch.value
        return coarse_ch.value * 257

    @property
    def tilt_24bit(self) -> int:
        """Return tilt coordinate as 24-bit integer [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        if not coarse_ch:
            return 0
        if ultra_fine_ch and fine_ch:
            return (coarse_ch.value << 16) | (fine_ch.value << 8) | ultra_fine_ch.value
        if fine_ch:
            raw_16 = (coarse_ch.value << 8) | fine_ch.value
            return round(raw_16 / 65535.0 * 16777215.0)
        return round(coarse_ch.value / 255.0 * 16777215.0)

    @property
    def position_24bit(self) -> tuple[int, int]:
        """Return (pan_24bit, tilt_24bit) tuple [0..16777215]."""
        return (self.pan_24bit, self.tilt_24bit)

    @property
    def pan_degrees(self) -> float:
        """Return pan coordinate in physical degrees."""
        val = self._get_physical_parameter(ChannelType.PAN)
        return val if val is not None else 0.0

    @property
    def tilt_degrees(self) -> float:
        """Return tilt coordinate in physical degrees."""
        val = self._get_physical_parameter(ChannelType.TILT)
        return val if val is not None else 0.0

    @property
    def position_degrees(self) -> tuple[float, float]:
        """Return (pan_degrees, tilt_degrees) tuple."""
        return (self.pan_degrees, self.tilt_degrees)

    @property
    def pan_tilt(self) -> tuple[int, int]:
        """Return (pan, tilt) tuple [0..255]."""
        pan_ch = self.get_channel(ChannelType.PAN)
        tilt_ch = self.get_channel(ChannelType.TILT)
        return (pan_ch.value if pan_ch else 0, tilt_ch.value if tilt_ch else 0)

    # Optical controls (Zoom, Focus)
    def set_zoom_degrees(self, angle: float) -> None:
        """Set beam zoom angle in degrees."""
        self._set_physical_parameter(ChannelType.ZOOM, angle)

    @property
    def zoom_degrees(self) -> Optional[float]:
        """Return beam zoom angle in degrees, or None if no ZOOM channel."""
        return self._get_physical_parameter(ChannelType.ZOOM)

    def set_focus_meters(self, distance: float) -> None:
        """Set focus distance in meters."""
        self._set_physical_parameter(ChannelType.FOCUS, distance)

    @property
    def focus_meters(self) -> Optional[float]:
        """Return focus distance in meters, or None if no FOCUS channel."""
        return self._get_physical_parameter(ChannelType.FOCUS)

    # Strobe frequency control
    def set_strobe_hz(self, freq: float) -> None:
        """Set strobe flash frequency in Hertz."""
        self._set_physical_parameter(ChannelType.STROBE, freq)

    @property
    def strobe_hz(self) -> Optional[float]:
        """Return strobe frequency in Hertz, or None if no STROBE channel."""
        return self._get_physical_parameter(ChannelType.STROBE)

    # Color temperature control (CCT)
    def set_color_temp_kelvin(self, kelvin: float) -> None:
        """Set correlated color temperature in Kelvin."""
        self._set_physical_parameter(ChannelType.COLOR_TEMP, kelvin)

    @property
    def color_temp_kelvin(self) -> Optional[float]:
        """Return color temperature in Kelvin, or None if no COLOR_TEMP channel."""
        return self._get_physical_parameter(ChannelType.COLOR_TEMP)

    def blackout(self) -> None:
        """Set intensity to zero (blackout)."""
        self.set_intensity(0.0)

    def reset(self) -> None:
        """Reset device to initial state."""
        self.reset_all()

    def reset_all(self) -> None:
        """Reset all channels to default values."""
        for ch in self.channels:
            ch.reset()
        self._intensity = 0.0 if self.has_physical_dimmer else 1.0
        self._target_color = sRGB(0.0, 0.0, 0.0)
        self._target_cie = CIExyY(0.3127, 0.3290, 0.0)
        for k in self._base_emitters:
            self._base_emitters[k] = 0.0

    def activate_range(self, channel_label: str, range_label: str) -> None:
        """Activate range on channel specified by label."""
        self._channel_by_label(channel_label).activate_range(range_label)

    def set_range_percent(
        self, channel_label: str, range_label: str, percent: float
    ) -> None:
        """Set relative range percentage on channel specified by label."""
        self._channel_by_label(channel_label).set_range_percent(range_label, percent)

    def _channel_by_label(self, label: str) -> Channel:
        for ch in self.channels:
            if ch.label == label:
                return ch
        raise KeyError(f"Channel '{label}' not found on device '{self.label}'")

    def dmx_values(self) -> dict[tuple[int, int], int]:
        """Return snapshot dictionary {(universe, address): value}."""
        return {(ch.universe, ch.address): ch.value for ch in self.channels}

    def dmx_values_for_universe(self, universe: int) -> dict[int, int]:
        """Return snapshot dictionary {address: value} for a given universe."""
        return {ch.address: ch.value for ch in self.channels if ch.universe == universe}

    def osc_address(self, sub_path: str = "") -> str:
        """Build OSC address path for this fixture."""
        base = f"/fixture/{self.fixture_id}"
        return f"{base}/{sub_path.lstrip('/')}" if sub_path else base

    def to_osc_bundle(self) -> list[tuple[str, int]]:
        """Generate OSC address/value pairs for all channels and intensity."""
        bundle: list[tuple[str, int]] = [
            (self.osc_address("intensity"), round(self.intensity_percent))
        ]
        bundle.extend((self.osc_address(ch.label), ch.value) for ch in self.channels)
        return bundle

    def describe_channels(self) -> str:
        """Return textual description of all channels and ranges."""
        lines = [f"Fixture '{self.label}' — {self.patch_summary()}"]
        for ch in self.channels:
            line = f"  {ch.label:20s} {str(ch.dmx_address):10s}  val={ch.value:3d}"
            if ch.is_multi_function:
                ar = ch.active_range
                mode = ar.label if ar else "out of range"
                line += f"  [{mode}]"
                for r in ch.ranges:
                    marker = " ◀" if r is ar else ""
                    line += (
                        f"\n    {'':20s} {r.value_min:3d}-{r.value_max:3d}  "
                        f"{r.label}{marker}"
                    )
            lines.append(line)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize device to a dictionary."""
        return {
            "fixture_id": self.fixture_id,
            "label": self.label,
            "fixture_type": self.fixture_type.value,
            "group": self.group,
            "notes": self.notes,
            "enabled": self._enabled,
            "curve_id": self.curve_id,
            "intensity": self._intensity,
            "target_color": self._target_color.to_hex(),
            "base_emitters": {
                ch_type.value: val for ch_type, val in self._base_emitters.items()
            },
            "channels": [
                {
                    "channel_type": ch.channel_type.value,
                    "universe": ch.universe,
                    "address": ch.address,
                    "value": ch.value,
                    "default_value": ch.default_value,
                    "fine": ch.fine,
                    "ultra_fine": ch.ultra_fine,
                    "label": ch.label,
                    "merge_mode": ch.merge_mode.value if ch.merge_mode else "htp",
                    "physical_min": ch.physical_min,
                    "physical_max": ch.physical_max,
                    "physical_unit": ch.physical_unit,
                    "ranges": [
                        {
                            "label": r.label,
                            "channel_type": r.channel_type.value,
                            "value_min": r.value_min,
                            "value_max": r.value_max,
                            "snap_value": r.snap_value,
                            "description": r.description,
                            "physical_min": r.physical_min,
                            "physical_max": r.physical_max,
                            "physical_unit": r.physical_unit,
                        }
                        for r in ch.ranges
                    ],
                }
                for ch in self.channels
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LightingDevice:
        """Instantiate device from a dictionary."""
        channels = []
        for cd in data.get("channels", []):
            ranges = [
                ChannelRange(
                    label=r["label"],
                    channel_type=ChannelType(r["channel_type"]),
                    value_min=r["value_min"],
                    value_max=r["value_max"],
                    snap_value=r.get("snap_value"),
                    description=r.get("description", ""),
                    physical_min=r.get("physical_min"),
                    physical_max=r.get("physical_max"),
                    physical_unit=r.get("physical_unit", ""),
                )
                for r in cd.get("ranges", [])
            ]
            ctype = ChannelType(cd["channel_type"])
            mm = (
                MergeMode(cd["merge_mode"])
                if "merge_mode" in cd
                else get_default_merge_mode(ctype)
            )
            channels.append(
                Channel(
                    channel_type=ctype,
                    universe=cd["universe"],
                    address=cd["address"],
                    value=cd.get("value", 0),
                    default_value=cd.get("default_value", 0),
                    fine=cd.get("fine", False),
                    ultra_fine=cd.get("ultra_fine", False),
                    label=cd.get("label", ""),
                    ranges=ranges,
                    physical_min=cd.get("physical_min", 0.0),
                    physical_max=cd.get("physical_max", 1.0),
                    physical_unit=cd.get("physical_unit", ""),
                    merge_mode=mm,
                )
            )
        device = cls(
            fixture_id=data["fixture_id"],
            label=data["label"],
            fixture_type=FixtureType(data["fixture_type"]),
            channels=channels,
            group=data.get("group", ""),
            notes=data.get("notes", ""),
        )
        device._enabled = data.get("enabled", True)
        device.curve_id = data.get("curve_id", 0)
        if "intensity" in data:
            device.set_intensity(data["intensity"])
        if "target_color" in data:
            device.set_color_hex(data["target_color"])
        if "base_emitters" in data:
            device._base_emitters = {
                ChannelType(k): float(v) for k, v in data["base_emitters"].items()
            }
            if device.uses_virtual_dimmer:
                device._apply_virtual_dimmer()
        return device

    @property
    def enabled(self) -> bool:
        """True if device output is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable device output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable device output."""
        self._enabled = False

    @property
    def locked(self) -> bool:
        """True if device parameters are locked against modifications."""
        return self._locked

    def lock(self) -> None:
        """Lock device parameters."""
        self._locked = True

    def unlock(self) -> None:
        """Unlock device parameters."""
        self._locked = False

    def __repr__(self) -> str:
        return (
            f"<LightingDevice id={self.fixture_id} '{self.label}' "
            f"type={self.fixture_type.value} "
            f"patch=[{self.patch_summary()}] ch={self.channel_count()}>"
        )
