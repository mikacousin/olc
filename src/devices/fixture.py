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
"""Fixture templates: channel definitions, DMX modes, fixture definitions.

Also provides the FixtureLibrary registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .device import (
    Channel,
    ChannelRange,
    ChannelType,
    FixtureType,
    LightingDevice,
    MergeMode,
    get_default_merge_mode,
)

if TYPE_CHECKING:
    from .color import ColorMatcher, FixtureColorProfile


@dataclass
class ChannelDefinition:  # pylint: disable=too-many-instance-attributes
    """Relative channel template in a DMX mode.

    Uses a relative 0-based offset. The absolute address is determined
    at instantiation time based on the selected patch address.

    fine_offset: Offset of the 16-bit fine channel (None if 8-bit only).
    ranges: Semantic sub-ranges (for multi-function channels).
    """

    channel_type: ChannelType
    offset: int
    label: str = ""
    default_value: int = 0
    fine_offset: Optional[int] = None
    ultra_fine_offset: Optional[int] = None
    ranges: list[ChannelRange] = field(default_factory=list)
    physical_min: float = 0.0
    physical_max: float = 1.0
    physical_unit: str = ""
    merge_mode: Optional[MergeMode] = None

    def __post_init__(self) -> None:
        self.label = self.label or self.channel_type.value
        if self.merge_mode is None:
            self.merge_mode = get_default_merge_mode(self.channel_type)

    def to_channel(self, universe: int, base_address: int) -> list[Channel]:
        """Instantiate this template into absolute Channel instance(s).

        Returns 2 channels if fine_offset is specified (16-bit coarse + fine),
        or 3 channels if ultra_fine_offset is also specified (24-bit).
        Automatically handles universe overflows when address exceeds 512.
        """

        def resolve(univ: int, addr: int) -> tuple[int, int]:
            """1-based address -> (corrected universe, address 1-512)."""
            if addr > 512:
                univ += (addr - 1) // 512
                addr = ((addr - 1) % 512) + 1
            return univ, addr

        u, a = resolve(universe, base_address + self.offset)
        channels = [
            Channel(
                channel_type=self.channel_type,
                universe=u,
                address=a,
                default_value=self.default_value,
                label=self.label,
                ranges=list(self.ranges),
                physical_min=self.physical_min,
                physical_max=self.physical_max,
                physical_unit=self.physical_unit,
                merge_mode=self.merge_mode,
            )
        ]

        if self.fine_offset is not None:
            uf, af = resolve(universe, base_address + self.fine_offset)
            channels.append(
                Channel(
                    channel_type=self.channel_type,
                    universe=uf,
                    address=af,
                    default_value=0,
                    fine=True,
                    label=f"{self.label}_fine",
                    physical_min=self.physical_min,
                    physical_max=self.physical_max,
                    physical_unit=self.physical_unit,
                    merge_mode=self.merge_mode,
                )
            )

        if self.ultra_fine_offset is not None:
            uu, au = resolve(universe, base_address + self.ultra_fine_offset)
            channels.append(
                Channel(
                    channel_type=self.channel_type,
                    universe=uu,
                    address=au,
                    default_value=0,
                    fine=False,
                    ultra_fine=True,
                    label=f"{self.label}_ultra_fine",
                    physical_min=self.physical_min,
                    physical_max=self.physical_max,
                    physical_unit=self.physical_unit,
                    merge_mode=self.merge_mode,
                )
            )

        return channels


@dataclass
class DmxModeDefinition:
    """A specific DMX mode of a fixture (e.g. 'Basic 8ch', 'Extended 16ch')."""

    name: str
    channel_defs: list[ChannelDefinition] = field(default_factory=list)
    description: str = ""

    def channel_count(self) -> int:
        """Total number of channels including fine and ultra-fine channels."""
        count = len(self.channel_defs)
        count += sum(1 for cd in self.channel_defs if cd.fine_offset is not None)
        count += sum(1 for cd in self.channel_defs if cd.ultra_fine_offset is not None)
        return count

    def footprint(self) -> int:
        """Footprint: highest offset + 1 (including fine and ultra-fine channels)."""
        offsets = [cd.offset for cd in self.channel_defs]
        offsets += [
            cd.fine_offset for cd in self.channel_defs if cd.fine_offset is not None
        ]
        offsets += [
            cd.ultra_fine_offset
            for cd in self.channel_defs
            if cd.ultra_fine_offset is not None
        ]
        return max(offsets) + 1 if offsets else 0

    def __repr__(self) -> str:
        return f"<DmxMode '{self.name}' {self.channel_count()}ch>"


class FixtureDefinition:  # pylint: disable=too-many-instance-attributes
    """Complete specification of a lighting fixture model."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        manufacturer: str,
        model: str,
        fixture_type: FixtureType = FixtureType.GENERIC,
        dmx_modes: Optional[list[DmxModeDefinition]] = None,
        color_profile: Optional[FixtureColorProfile] = None,
        gdtf_id: str = "",
        thumbnail: Optional[bytes] = None,
        notes: str = "",
    ) -> None:
        self.manufacturer = manufacturer
        self.model = model
        self.fixture_type = fixture_type
        self.dmx_modes: list[DmxModeDefinition] = dmx_modes or []
        self.color_profile = color_profile
        self.gdtf_id = gdtf_id
        self.thumbnail = thumbnail
        self.notes = notes

    @property
    def full_name(self) -> str:
        """Return 'Manufacturer Model'."""
        return f"{self.manufacturer} {self.model}".strip()

    def get_mode(self, name: str) -> DmxModeDefinition:
        """Get DMX mode by name."""
        for m in self.dmx_modes:
            if m.name == name:
                return m
        available = [m.name for m in self.dmx_modes]
        raise KeyError(f"Mode '{name}' not found. Available modes: {available}")

    def default_mode(self) -> DmxModeDefinition:
        """Get the default (first) DMX mode."""
        if not self.dmx_modes:
            raise ValueError(f"No DMX modes defined for '{self.full_name}'")
        return self.dmx_modes[0]

    def mode_names(self) -> list[str]:
        """List all available DMX mode names."""
        return [m.name for m in self.dmx_modes]

    def instantiate(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        fixture_id: int,
        label: str,
        universe: int,
        address: int,
        mode_name: Optional[str] = None,
        group: str = "",
    ) -> LightingDevice:
        """Instantiate a patched LightingDevice from this definition."""
        mode = self.get_mode(mode_name) if mode_name else self.default_mode()

        channels: list[Channel] = []
        for ch_def in mode.channel_defs:
            channels.extend(ch_def.to_channel(universe, address))

        return LightingDevice(
            fixture_id=fixture_id,
            label=label,
            fixture_type=self.fixture_type,
            channels=channels,
            group=group,
            notes=f"{self.full_name} — {mode.name}",
            color_profile=self.color_profile,
        )

    @property
    def has_color_profile(self) -> bool:
        """True if colorimetric profile is available."""
        return self.color_profile is not None

    def get_color_matcher(self) -> Optional[ColorMatcher]:
        """Return a ColorMatcher pre-configured for this fixture."""
        if self.color_profile is None:
            return None
        from .color import ColorMatcher  # pylint: disable=import-outside-toplevel

        return ColorMatcher([self.color_profile])

    def __repr__(self) -> str:
        modes = ", ".join(f"'{m.name}'" for m in self.dmx_modes)
        color = " +color" if self.has_color_profile else ""
        return f"<FixtureDefinition '{self.full_name}' modes=[{modes}]{color}>"


class FixtureLibrary:
    """Registry of FixtureDefinition templates indexed by manufacturer and model."""

    def __init__(self) -> None:
        self._definitions: dict[str, FixtureDefinition] = {}

    @staticmethod
    def _key(manufacturer: str, model: str) -> str:
        return f"{manufacturer.lower()}::{model.lower()}"

    def register(self, defn: FixtureDefinition) -> FixtureDefinition:
        """Register a fixture definition."""
        self._definitions[self._key(defn.manufacturer, defn.model)] = defn
        return defn

    def get(self, manufacturer: str, model: str) -> FixtureDefinition:
        """Get fixture definition by exact manufacturer and model name."""
        key = self._key(manufacturer, model)
        if key not in self._definitions:
            raise KeyError(f"'{manufacturer} {model}' not found in fixture library.")
        return self._definitions[key]

    def search(self, query: str) -> list[FixtureDefinition]:
        """Search definitions by substring in manufacturer or model."""
        q = query.lower()
        return [
            d
            for d in self._definitions.values()
            if q in d.manufacturer.lower() or q in d.model.lower()
        ]

    def instantiate(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        manufacturer: str,
        model: str,
        fixture_id: int,
        label: str,
        universe: int,
        address: int,
        mode_name: Optional[str] = None,
        group: str = "",
    ) -> LightingDevice:
        """Lookup definition and instantiate directly."""
        return self.get(manufacturer, model).instantiate(
            fixture_id, label, universe, address, mode_name, group
        )

    def color_matcher(self) -> ColorMatcher:
        """Return ColorMatcher for all registered fixtures with color profiles."""
        from .color import ColorMatcher  # pylint: disable=import-outside-toplevel

        profiles = [
            d.color_profile
            for d in self._definitions.values()
            if d.color_profile is not None
        ]
        return ColorMatcher(profiles)

    def all(self) -> list[FixtureDefinition]:
        """Return all registered fixture definitions."""
        return list(self._definitions.values())

    def list_fixtures(self) -> list[FixtureDefinition]:
        """Alias for all()."""
        return self.all()

    def __len__(self) -> int:
        return len(self._definitions)

    def __repr__(self) -> str:
        return f"<FixtureLibrary {len(self)} fixtures>"
