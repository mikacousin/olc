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

# pylint: disable=too-many-lines
import typing
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from olc.define import DEFAULT_UNIVERSES, MAX_CHANNELS
from olc.devices.builtin import create_dimmer_definition
from olc.devices.device import Channel, ChannelType, FixtureType, LightingDevice
from olc.devices.fixture import FixtureDefinition

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow
    from olc.cue import Cue
    from olc.curve import Curve


class PatchCollisionError(ValueError):
    """Raised when attempting to patch a device over already occupied DMX addresses."""

    def __init__(
        self, universe: int, address: int, colliding_device_id: int, new_device_id: int
    ) -> None:
        self.universe = universe
        self.address = address
        self.colliding_device_id = colliding_device_id
        self.new_device_id = new_device_id
        super().__init__(
            f"Address collision on universe {universe}, address {address}: "
            f"already occupied by device {colliding_device_id} "
            f"(attempted by device {new_device_id})."
        )


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class AddressParameterInfo:
    """Precomputed display metadata for a DMX address occupant."""

    device_id: int
    is_simple_dimmer: bool
    channel_type: ChannelType
    short_name: str
    param_color: tuple[float, float, float]


_CHANNEL_TYPE_SHORT_NAMES: dict[ChannelType, str] = {
    ChannelType.INTENSITY: "DIM",
    ChannelType.PAN: "PAN",
    ChannelType.TILT: "TILT",
    ChannelType.RED: "RED",
    ChannelType.GREEN: "GRN",
    ChannelType.BLUE: "BLU",
    ChannelType.WHITE: "WHT",
    ChannelType.AMBER: "AMB",
    ChannelType.LIME: "LIM",
    ChannelType.CYAN: "CYN",
    ChannelType.INDIGO: "IND",
    ChannelType.MAGENTA: "MAG",
    ChannelType.YELLOW: "YEL",
    ChannelType.COLOR_WHEEL: "CWHL",
    ChannelType.COLOR_TEMP: "CTC",
    ChannelType.GOBO_WHEEL: "GOB",
    ChannelType.PRISM: "PRIS",
    ChannelType.ZOOM: "ZOOM",
    ChannelType.FOCUS: "FOC",
    ChannelType.IRIS: "IRIS",
    ChannelType.STROBE: "SHUT",
    ChannelType.RESET: "RST",
    ChannelType.MACRO: "MAC",
}

_CHANNEL_TYPE_COLORS: dict[ChannelType, tuple[float, float, float]] = {
    ChannelType.PAN: (0.0, 0.82, 1.0),
    ChannelType.TILT: (0.0, 0.82, 1.0),
    ChannelType.RED: (1.0, 0.4, 0.4),
    ChannelType.GREEN: (0.35, 1.0, 0.35),
    ChannelType.BLUE: (0.4, 0.7, 1.0),
    ChannelType.WHITE: (0.95, 0.95, 0.95),
    ChannelType.AMBER: (1.0, 0.75, 0.0),
    ChannelType.LIME: (0.8, 1.0, 0.2),
    ChannelType.CYAN: (0.0, 1.0, 1.0),
    ChannelType.MAGENTA: (1.0, 0.4, 1.0),
    ChannelType.YELLOW: (1.0, 1.0, 0.3),
    ChannelType.COLOR_WHEEL: (0.9, 0.6, 0.9),
    ChannelType.COLOR_TEMP: (0.9, 0.6, 0.9),
    ChannelType.INDIGO: (0.9, 0.6, 0.9),
    ChannelType.GOBO_WHEEL: (1.0, 0.8, 0.1),
    ChannelType.PRISM: (1.0, 0.8, 0.1),
    ChannelType.ZOOM: (1.0, 0.8, 0.1),
    ChannelType.FOCUS: (1.0, 0.8, 0.1),
    ChannelType.IRIS: (1.0, 0.8, 0.1),
    ChannelType.INTENSITY: (1.0, 0.6, 0.2),
    ChannelType.STROBE: (1.0, 0.4, 0.8),
}


def get_channel_short_name(channel: Channel) -> str:
    """Return a concise 2-5 character mnemonic for a fixture channel."""
    suffix = ""
    if channel.ultra_fine:
        suffix = "_UF"
    elif channel.fine:
        suffix = "_F"

    base_name = _CHANNEL_TYPE_SHORT_NAMES.get(channel.channel_type, "")
    if not base_name:
        lbl = (channel.label or "").strip().upper()
        base_name = lbl[:4] if lbl and lbl != "GENERIC" else "GEN"

    if suffix:
        if base_name in ("PAN", "TILT"):
            return f"{base_name[0]}{suffix}"
        return f"{base_name}{suffix}"

    return base_name


def get_channel_category_color(
    channel_type: ChannelType,
) -> tuple[float, float, float]:
    """Return Cairo RGB color tuple (values 0.0..1.0) for a given channel type."""
    return _CHANNEL_TYPE_COLORS.get(channel_type, (0.75, 0.75, 0.75))


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class FixtureExchangeWarning:
    """Warning emitted when a cue value exceeds physical limits of a new profile."""

    device_id: int
    cue_number: float
    sequence: int
    parameter: str
    original_value: float
    clamped_value: float
    unit: str
    physical_min: float
    physical_max: float

    def format_message(self) -> str:
        """Format a user-friendly warning message."""
        seq_label = (
            f"Cue {self.cue_number:g} (Seq {self.sequence})"
            if self.sequence > 0
            else f"Preset {self.cue_number:g}"
        )
        unit_str = f" {self.unit}" if self.unit else ""
        param_cap = self.parameter.capitalize()
        return (
            f"{seq_label}: {param_cap} = {self.original_value:g}{unit_str} "
            f"écrêté à {self.clamped_value:g}{unit_str} "
            f"[{self.physical_min:g}..{self.physical_max:g}{unit_str}]"
        )


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class PatchManager:
    """Unified DMX patch manager handling both devices and conventional dimmers.

    Replaces the legacy 1:1 patch structure with a device-centric registry while
    maintaining full backward compatibility with the existing UI and file formats.

    Attributes:
        universes: List of active DMX universes (e.g. [1, 2, 3, 4]).
        devices: Dictionary of LightingDevice instances keyed by device_id.
        channels: Legacy mapping {channel_id: [[output, universe], ...]}.
        outputs: Legacy mapping {universe: {output: [channel_id, curve]}}.
    """

    universes: list[int]
    devices: dict[int, LightingDevice]
    channels: dict[int, list[list[Optional[int]]]]
    outputs: dict[int, dict[int, list[int]]]
    _address_param_cache: dict[tuple[int, int], AddressParameterInfo]

    def __init__(
        self,
        universes: list[int] | None = None,
        lightshow: Optional[LightShow] = None,
    ) -> None:
        self.lightshow = lightshow
        self.universes = (
            list(universes) if universes is not None else list(DEFAULT_UNIVERSES)
        )
        self.devices = {}
        self._address_param_cache = {}
        self._grid: dict[int, np.ndarray] = {
            u: np.zeros(512, dtype=np.int32) for u in self.universes
        }
        self.channels = {}
        self.outputs = {}
        self.on_patch_empty_cb: typing.Callable[[], None] | None = None
        self.on_unpatch_cb: typing.Callable[[int, int], None] | None = None
        self._numpy_cache_dirty = True
        self.is_patched_mask = np.zeros(MAX_CHANNELS, dtype=bool)
        self.map_src_channels = np.array([], dtype=np.intp)
        self.map_dst_universes = np.array([], dtype=np.intp)
        self.map_dst_outputs = np.array([], dtype=np.intp)
        self.map_dst_curves = np.array([], dtype=np.intp)
        self.device_channel_refs: list[tuple[LightingDevice, Channel]] = []
        self.dynamic_intensity_devices: list[LightingDevice] = []
        self.map_dev_dst_universes = np.array([], dtype=np.intp)
        self.map_dev_dst_outputs = np.array([], dtype=np.intp)
        self.map_dev_is_htp = np.array([], dtype=bool)
        self.last_exchange_warnings: list[FixtureExchangeWarning] = []

        self.patch_empty()

    def invalidate_cache(self) -> None:
        """Invalidate the numpy cache."""
        self._numpy_cache_dirty = True

    def _get_curve_by_id(self, curve_id: int) -> Optional[Curve]:
        """Resolve a curve by ID from the parent lightshow if available."""
        lightshow = getattr(self, "lightshow", None)
        if lightshow is not None:
            curves = getattr(lightshow, "curves", None)
            if curves is not None and hasattr(curves, "get_curve"):
                curve: Optional[Curve] = curves.get_curve(curve_id)
                return curve
        return None

    # -------------------------------------------------------------------------
    # Collision and Address Grid Inspection
    # -------------------------------------------------------------------------

    def get_address_occupant(self, universe: int, address: int) -> Optional[int]:
        """Return the device_id occupying (universe, address), or None if free."""
        if universe in self._grid and 1 <= address <= 512:
            occ = int(self._grid[universe][address - 1])
            if occ != 0:
                return occ
        if universe in self.outputs and address in self.outputs[universe]:
            return self.outputs[universe][address][0]
        return None

    def get_address_parameter_info(
        self, universe: int, address: int
    ) -> Optional[AddressParameterInfo]:
        """Return precomputed display metadata for a DMX address occupant."""
        if (universe, address) in self._address_param_cache:
            return self._address_param_cache[(universe, address)]
        occ = self.get_address_occupant(universe, address)
        if occ is not None and occ > 0:
            return AddressParameterInfo(
                device_id=occ,
                is_simple_dimmer=True,
                channel_type=ChannelType.INTENSITY,
                short_name="",
                param_color=(1.0, 0.6, 0.2),
            )
        return None

    def is_address_free(self, universe: int, address: int) -> bool:
        """Return True if the specified address is unallocated."""
        return self.get_address_occupant(universe, address) is None

    def check_collision(
        self,
        universe: int,
        address: int,
        count: int = 1,
        ignore_device_id: Optional[int] = None,
    ) -> list[tuple[int, int, int]]:
        """Check for address collisions across a consecutive block of channels.

        Handles universe overflows when address exceeds 512.

        Returns:
            List of (universe, address, colliding_device_id) tuples.
        """
        collisions: list[tuple[int, int, int]] = []
        curr_univ = universe
        curr_addr = address
        for _ in range(count):
            if curr_addr > 512:
                curr_univ += (curr_addr - 1) // 512
                curr_addr = ((curr_addr - 1) % 512) + 1
            occ = self.get_address_occupant(curr_univ, curr_addr)
            if occ is not None and occ != ignore_device_id:
                collisions.append((curr_univ, curr_addr, occ))
            curr_addr += 1
        return collisions

    # -------------------------------------------------------------------------
    # Device Management
    # -------------------------------------------------------------------------

    def patch_device(  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
        self,
        device_id: int,
        fixture_def: FixtureDefinition,
        universe: int,
        address: int,
        mode_name: Optional[str] = None,
        label: str = "",
        force: bool = False,
    ) -> LightingDevice:
        """Patch a lighting device into the console.

        Args:
            device_id: Positive fixture identifier (e.g. 1, 101).
            fixture_def: The FixtureDefinition template.
            universe: Starting universe (1-based).
            address: Starting DMX address (1-512).
            mode_name: DMX mode name (defaults to default mode if None).
            label: User label for the device.
            force: If True, overwrite colliding addresses rather than erroring.

        Returns:
            The instantiated and registered LightingDevice.

        Raises:
            ValueError: If device_id is <= 0.
            PatchCollisionError: If colliding with another device and force is False.
        """
        if device_id <= 0:
            raise ValueError(f"device_id must be a positive integer, got {device_id}")

        mode = (
            fixture_def.get_mode(mode_name) if mode_name else fixture_def.default_mode()
        )
        footprint = mode.footprint()
        if footprint > 0:
            collisions = self.check_collision(
                universe, address, footprint, ignore_device_id=device_id
            )
            if collisions:
                if not force:
                    c = collisions[0]
                    raise PatchCollisionError(
                        universe=c[0],
                        address=c[1],
                        colliding_device_id=c[2],
                        new_device_id=device_id,
                    )
                for c_univ, c_addr, _ in collisions:
                    self.unpatch_address(c_univ, c_addr)

        if self.lightshow is not None and hasattr(self.lightshow, "fixture_library"):
            self.lightshow.fixture_library.register(fixture_def)

        if device_id in self.devices:
            self.unpatch_device(device_id)

        device = fixture_def.instantiate(
            fixture_id=device_id,
            label=label or f"{fixture_def.model} {device_id}",
            universe=universe,
            address=address,
            mode_name=mode.name,
        )
        self._register_device_in_grid(device)
        return device

    def _register_device_in_grid(self, device: LightingDevice) -> None:
        """Register a device and its channels into grid and legacy mappings."""
        dev_id = device.fixture_id
        device.set_curve_provider(self._get_curve_by_id)
        self.devices[dev_id] = device

        is_simple_dimmer = (
            device.fixture_type == FixtureType.DIMMER
            and len(device.channels) == 1
            and not device.channels[0].fine
            and not device.channels[0].ultra_fine
        )

        for ch in device.channels:
            if ch.universe not in self._grid:
                self.add_universe(ch.universe)
            self._grid[ch.universe][ch.address - 1] = dev_id

            if is_simple_dimmer:
                self._address_param_cache[(ch.universe, ch.address)] = (
                    AddressParameterInfo(
                        device_id=dev_id,
                        is_simple_dimmer=True,
                        channel_type=ChannelType.INTENSITY,
                        short_name="",
                        param_color=(1.0, 0.6, 0.2),
                    )
                )
            else:
                short_name = get_channel_short_name(ch)
                param_color = get_channel_category_color(ch.channel_type)
                self._address_param_cache[(ch.universe, ch.address)] = (
                    AddressParameterInfo(
                        device_id=dev_id,
                        is_simple_dimmer=False,
                        channel_type=ch.channel_type,
                        short_name=short_name,
                        param_color=param_color,
                    )
                )

            # Maintain legacy structures for intensity/dimmer channels
            if (
                ch.channel_type == ChannelType.INTENSITY
                and not ch.fine
                and not ch.ultra_fine
            ):
                if dev_id not in self.channels or self.channels[dev_id] == [
                    [None, None]
                ]:
                    self.channels[dev_id] = [[ch.address, ch.universe]]
                elif [ch.address, ch.universe] not in self.channels[dev_id]:
                    self.channels[dev_id].append([ch.address, ch.universe])
                if ch.universe not in self.outputs:
                    self.outputs[ch.universe] = {}
                self.outputs[ch.universe][ch.address] = [dev_id, device.curve_id]

        self._numpy_cache_dirty = True

    def patch_dimmer(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        channel: int,
        universe: int,
        address: int,
        curve: int = 0,
        fine: bool = False,
        label: str = "",
        force: bool = False,
    ) -> LightingDevice:
        """Patch a dimmer (8-bit or 16-bit).

        Args:
            channel: Channel number (1-MAX_CHANNELS).
            universe: Universe identifier.
            address: DMX address (1-512).
            curve: Transfer curve index (0 = Linear).
            fine: If True, patch 16-bit dimmer (2 channels: coarse + fine).
            label: Device label.
            force: If True, overwrite existing occupant.

        Returns:
            The created LightingDevice.
        """
        dim_def = create_dimmer_definition(fine=fine)
        dev = self.patch_device(
            device_id=channel,
            fixture_def=dim_def,
            universe=universe,
            address=address,
            label=label or f"Dimmer {channel}",
            force=force,
        )
        dev.set_curve_id(curve)
        if universe in self.outputs and address in self.outputs[universe]:
            self.outputs[universe][address][1] = curve
        self._numpy_cache_dirty = True
        return dev

    def unpatch_device(self, device_id: int) -> Optional[LightingDevice]:
        """Unpatch a device and free its allocated DMX addresses."""
        if device_id not in self.devices:
            return None
        device = self.devices.pop(device_id)
        for ch in device.channels:
            self._address_param_cache.pop((ch.universe, ch.address), None)
            if (
                ch.universe in self._grid
                and self._grid[ch.universe][ch.address - 1] == device_id
            ):
                self._grid[ch.universe][ch.address - 1] = 0
            if ch.universe in self.outputs:
                self.outputs[ch.universe].pop(ch.address, None)
            if ch.universe in self.universes:
                index = self.universes.index(ch.universe)
                if self.on_unpatch_cb:
                    self.on_unpatch_cb(index, ch.address - 1)
        if device_id in self.channels:
            self.channels[device_id] = [[None, None]]
        self._numpy_cache_dirty = True
        return device

    def unpatch_address(self, universe: int, address: int) -> Optional[int]:
        """Unpatch whatever occupies (universe, address). Returns device_id or None."""
        self._address_param_cache.pop((universe, address), None)
        occupant = self.get_address_occupant(universe, address)
        if occupant is not None:
            if occupant in self.devices:
                self.unpatch_device(occupant)
                return occupant
        if universe in self.outputs and address in self.outputs[universe]:
            ch, _ = self.outputs[universe].pop(address)
            if ch in self.channels:
                if [address, universe] in self.channels[ch]:
                    self.channels[ch].remove([address, universe])
                if not self.channels[ch]:
                    self.channels[ch] = [[None, None]]
            if universe in self._grid:
                self._grid[universe][address - 1] = 0
            if universe in self.universes:
                index = self.universes.index(universe)
                if self.on_unpatch_cb:
                    self.on_unpatch_cb(index, address - 1)
            self._numpy_cache_dirty = True
            return ch
        return None

    def auto_patch(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_ids: list[int],
        fixture_def: FixtureDefinition,
        start_universe: int,
        start_address: int,
        mode_name: Optional[str] = None,
    ) -> list[LightingDevice]:
        """Sequentially patch multiple devices without collisions."""
        mode = (
            fixture_def.get_mode(mode_name) if mode_name else fixture_def.default_mode()
        )
        footprint = mode.footprint()
        cur_univ = start_universe
        cur_addr = start_address
        patched: list[LightingDevice] = []

        for dev_id in device_ids:
            if cur_addr + footprint - 1 > 512:
                cur_univ += 1
                cur_addr = 1

            while True:
                collisions = self.check_collision(cur_univ, cur_addr, footprint)
                if not collisions:
                    break
                cur_addr += 1
                if cur_addr + footprint - 1 > 512:
                    cur_univ += 1
                    cur_addr = 1

            dev = self.patch_device(
                device_id=dev_id,
                fixture_def=fixture_def,
                universe=cur_univ,
                address=cur_addr,
                mode_name=mode.name,
            )
            patched.append(dev)
            cur_addr += footprint

        return patched

    def exchange_fixture(  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals, too-many-branches
        self,
        device_id: int,
        new_fixture_def: FixtureDefinition,
        new_mode_name: Optional[str] = None,
        universe: Optional[int] = None,
        address: Optional[int] = None,
        label: Optional[str] = None,
        force: bool = False,
    ) -> LightingDevice:
        """Exchange fixture definition for an existing device.

        Physical attributes stored in Cues (degrees, colors, zoom, etc.) remain intact
        and will be translated by the new fixture definition to its native DMX channels.

        Args:
            device_id: ID of the device to replace.
            new_fixture_def: The new FixtureDefinition to use.
            new_mode_name: Mode name (defaults to fixture's default_mode).
            universe: Universe (if None, reuses existing device universe).
            address: DMX address (if None, reuses existing device address).
            label: Device label (if None, reuses existing label or default).
            force: If True, overwrite collisions at the target address.

        Returns:
            The newly instantiated LightingDevice.
        """
        old_dev = self.get_device(device_id)
        target_univ = universe
        target_addr = address
        target_label = label
        curve_id = 0

        if old_dev is not None:
            if target_univ is None and old_dev.channels:
                target_univ = old_dev.channels[0].universe
            if target_addr is None and old_dev.channels:
                target_addr = old_dev.channels[0].address
            if target_label is None:
                target_label = old_dev.label
            curve_id = old_dev.curve_id

        if target_univ is None:
            target_univ = self.universes[0] if self.universes else 1
        if target_addr is None:
            target_addr = 1

        mode = (
            new_fixture_def.get_mode(new_mode_name)
            if new_mode_name
            else new_fixture_def.default_mode()
        )
        footprint = mode.footprint()
        if footprint > 0:
            collisions = self.check_collision(
                target_univ, target_addr, footprint, ignore_device_id=device_id
            )
            if collisions:
                if not force:
                    c = collisions[0]
                    raise PatchCollisionError(
                        universe=c[0],
                        address=c[1],
                        colliding_device_id=c[2],
                        new_device_id=device_id,
                    )
                for c_univ, c_addr, _ in collisions:
                    self.unpatch_address(c_univ, c_addr)

        if old_dev is not None:
            self.unpatch_device(device_id)

        new_dev = self.patch_device(
            device_id=device_id,
            fixture_def=new_fixture_def,
            universe=target_univ,
            address=target_addr,
            mode_name=mode.name,
            label=target_label or f"{new_fixture_def.model} {device_id}",
            force=force,
        )
        new_dev.curve_id = curve_id

        self.last_exchange_warnings = self.check_clamped_cue_parameters(
            device_id, new_fixture_def, mode.name
        )
        if self.lightshow is not None:
            app = getattr(self.lightshow, "app", None)
            core = getattr(app, "core", app) if app is not None else None
            if core is not None and hasattr(core, "emit"):
                core.emit(
                    "patch.fixture_exchanged",
                    new_dev,
                    self.last_exchange_warnings,
                )

        return new_dev

    @staticmethod
    def _get_mode_physical_limits(
        mode: Any,  # noqa: ANN401
    ) -> dict[str, tuple[float, float, str]]:
        """Build mapping of parameter names to (physical_min, physical_max, unit)."""
        param_limits: dict[str, tuple[float, float, str]] = {}
        for cd in mode.channel_defs:
            p_min = cd.physical_min
            p_max = cd.physical_max
            unit = cd.physical_unit
            bounds = (min(p_min, p_max), max(p_min, p_max), unit)

            if cd.channel_type == ChannelType.PAN:
                param_limits["pan"] = bounds
            elif cd.channel_type == ChannelType.TILT:
                param_limits["tilt"] = bounds
            elif cd.channel_type == ChannelType.ZOOM:
                param_limits["zoom"] = bounds
            elif cd.channel_type == ChannelType.FOCUS:
                param_limits["focus"] = bounds
            elif cd.channel_type == ChannelType.STROBE:
                param_limits["strobe"] = bounds
            elif cd.channel_type == ChannelType.COLOR_TEMP:
                param_limits["color_temp"] = bounds
                param_limits["colortemp"] = bounds
                param_limits["cct"] = bounds
            elif cd.channel_type == ChannelType.IRIS:
                param_limits["iris"] = bounds
        return param_limits

    def _collect_show_cues(self) -> list[Cue]:
        """Collect unique cues across global cues, main playback, and chasers."""
        all_cues: list[Cue] = []
        seen_cues: set[tuple[int, float]] = set()

        def add_cue(c: Optional[Cue]) -> None:
            if c is not None:
                k = (c.sequence, c.number)
                if k not in seen_cues:
                    seen_cues.add(k)
                    all_cues.append(c)

        if hasattr(self.lightshow, "cues") and self.lightshow.cues:
            for cue in self.lightshow.cues:
                add_cue(cue)

        if hasattr(self.lightshow, "main_playback") and self.lightshow.main_playback:
            for step in self.lightshow.main_playback.steps:
                add_cue(step.cue)

        if hasattr(self.lightshow, "chasers") and self.lightshow.chasers:
            for seq in self.lightshow.chasers:
                for step in seq.steps:
                    add_cue(step.cue)

        return all_cues

    @staticmethod
    def _check_single_cue_clamping(
        cue: Cue,
        device_id: int,
        param_limits: dict[str, tuple[float, float, str]],
    ) -> list[FixtureExchangeWarning]:
        """Inspect a cue's device values against new physical limits."""
        warnings: list[FixtureExchangeWarning] = []
        if not cue.device_values or device_id not in cue.device_values:
            return warnings
        for param_name, raw_val in cue.device_values[device_id].items():
            p_lower = param_name.lower()
            if p_lower not in param_limits or not isinstance(raw_val, (int, float)):
                continue
            val = float(raw_val)
            p_min, p_max, unit = param_limits[p_lower]
            if val < p_min or val > p_max:
                warnings.append(
                    FixtureExchangeWarning(
                        device_id=device_id,
                        cue_number=cue.number,
                        sequence=cue.sequence,
                        parameter=param_name,
                        original_value=val,
                        clamped_value=max(p_min, min(p_max, val)),
                        unit=unit,
                        physical_min=p_min,
                        physical_max=p_max,
                    )
                )
        return warnings

    def check_clamped_cue_parameters(
        self,
        device_id: int,
        new_fixture_def: FixtureDefinition,
        new_mode_name: Optional[str] = None,
    ) -> list[FixtureExchangeWarning]:
        """Check all show cues for parameter values clamped by the new fixture."""
        warnings: list[FixtureExchangeWarning] = []
        if self.lightshow is None:
            return warnings

        mode = (
            new_fixture_def.get_mode(new_mode_name)
            if new_mode_name
            else new_fixture_def.default_mode()
        )
        param_limits = self._get_mode_physical_limits(mode)
        if not param_limits:
            return warnings

        for cue in self._collect_show_cues():
            warnings.extend(
                self._check_single_cue_clamping(cue, device_id, param_limits)
            )

        return warnings

    def get_device(self, device_id: int) -> Optional[LightingDevice]:
        """Get a registered LightingDevice by ID."""
        return self.devices.get(device_id)

    def has_device(self, device_id: int) -> bool:
        """True if a device with device_id is patched."""
        return device_id in self.devices

    def restore_device(self, device: LightingDevice) -> None:
        """Restore an existing device instance into the patch registry."""
        dev_id = device.fixture_id
        if dev_id in self.devices:
            self.unpatch_device(dev_id)

        for ch in device.channels:
            occ = self.get_address_occupant(ch.universe, ch.address)
            if occ is not None and occ != dev_id:
                self.unpatch_address(ch.universe, ch.address)

        self._register_device_in_grid(device)
        self.invalidate_cache()

    # -------------------------------------------------------------------------
    # Legacy DMXPatch Compatibility Methods
    # -------------------------------------------------------------------------

    def is_patched(self, channel: int) -> bool:
        """Test if channel is patched."""
        if channel in self.channels:
            if None not in self.channels[channel][0]:
                return True
        return channel in self.devices

    def patch_empty(self) -> None:
        """Set Dimmers patch to Zero."""
        if self.on_patch_empty_cb:
            self.on_patch_empty_cb()
        self.outputs = {}
        self.devices.clear()
        self._address_param_cache.clear()
        for univ in self.universes:
            if univ in self._grid:
                self._grid[univ].fill(0)
        for channel in range(1, MAX_CHANNELS + 1):
            self.channels[channel] = [[None, None]]
        self._numpy_cache_dirty = True

    def patch_1on1(self) -> None:
        """Set patch 1:1."""
        self.patch_empty()
        for channel in range(1, MAX_CHANNELS + 1):
            index = int((channel - 1) / 512)
            if index < len(self.universes):
                univ = self.universes[index]
                output = channel - (index * 512)
                self.add_output(channel, output, univ)

    def add_output(self, channel: int, output: int, univ: int, curve: int = 0) -> None:
        """Add an output to a channel (legacy method)."""
        occ = self.get_address_occupant(univ, output)
        if occ is not None and occ != channel:
            self.unpatch_address(univ, output)
        elif univ in self.outputs and output in self.outputs[univ]:
            prev_ch, _ = self.outputs[univ][output]
            if prev_ch != channel:
                self.unpatch(prev_ch, output, univ)

        if channel not in self.channels or self.channels[channel] == [[None, None]]:
            self.channels[channel] = [[output, univ]]
        elif [output, univ] not in self.channels[channel]:
            self.channels[channel].append([output, univ])

        if univ not in self.outputs:
            self.outputs[univ] = {}
        self.outputs[univ][output] = [channel, curve]

        if univ not in self.universes:
            self.add_universe(univ)

        if univ not in self._grid:
            self._grid[univ] = np.zeros(512, dtype=np.int32)
        self._grid[univ][output - 1] = channel

        if channel in self.devices:
            dev = self.devices[channel]
            found = any(
                ch.universe == univ and ch.address == output for ch in dev.channels
            )
            if not found:
                dev.channels.append(
                    Channel(
                        channel_type=ChannelType.INTENSITY,
                        universe=univ,
                        address=output,
                        default_value=0,
                        label=f"Dimmer {channel}",
                    )
                )
        else:
            dim_def = create_dimmer_definition(fine=False)
            dev = dim_def.instantiate(
                fixture_id=channel,
                label=f"Dimmer {channel}",
                universe=univ,
                address=output,
            )
            dev.set_curve_provider(self._get_curve_by_id)
            self.devices[channel] = dev

        if curve:
            self.devices[channel].set_curve_id(curve)

        self._address_param_cache[(univ, output)] = AddressParameterInfo(
            device_id=channel,
            is_simple_dimmer=True,
            channel_type=ChannelType.INTENSITY,
            short_name="",
            param_color=(1.0, 0.6, 0.2),
        )

        self._numpy_cache_dirty = True

    def unpatch(self, channel: int, output: int, univ: int) -> None:
        """Unpatch an output from a channel (legacy method)."""
        self._address_param_cache.pop((univ, output), None)
        if univ in self.outputs:
            self.outputs[univ].pop(output, None)
        if channel in self.channels and [output, univ] in self.channels[channel]:
            self.channels[channel].remove([output, univ])
        if channel in self.channels and not self.channels[channel]:
            self.channels[channel] = [[None, None]]
        if univ in self._grid and self._grid[univ][output - 1] == channel:
            self._grid[univ][output - 1] = 0
        if channel in self.devices:
            dev = self.devices[channel]
            dev.channels = [
                c
                for c in dev.channels
                if not (c.universe == univ and c.address == output)
            ]
            if not dev.channels:
                self.devices.pop(channel, None)
        if univ in self.universes:
            index = self.universes.index(univ)
            if self.on_unpatch_cb:
                self.on_unpatch_cb(index, output - 1)
        self._numpy_cache_dirty = True

    def add_universe(self, univ: int) -> None:
        """Add a universe to the patch if not already present."""
        if univ not in self.universes:
            self.universes.append(univ)
            self.universes.sort()
            if univ not in self._grid:
                self._grid[univ] = np.zeros(512, dtype=np.int32)
            self._numpy_cache_dirty = True

    def remove_universe(self, univ: int) -> dict[int, tuple[int, int]]:
        """Remove a universe from the patch and unpatch all its outputs."""
        unpatched: dict[int, tuple[int, int]] = {}
        if univ in self.outputs:
            for out, val in list(self.outputs[univ].items()):
                unpatched[out] = (val[0], val[1])

        for channel, outputs in list(self.channels.items()):
            for out in list(outputs):
                if len(out) > 1 and out[1] == univ and out[0] is not None:
                    self.unpatch(channel, out[0], univ)

        to_unpatch_devs = [
            dev_id
            for dev_id, dev in self.devices.items()
            if any(ch.universe == univ for ch in dev.channels)
        ]
        for dev_id in to_unpatch_devs:
            self.unpatch_device(dev_id)

        if univ in self.outputs:
            del self.outputs[univ]

        if univ in self._grid:
            del self._grid[univ]

        if univ in self.universes:
            self.universes.remove(univ)

        self._numpy_cache_dirty = True
        return unpatched

    # -------------------------------------------------------------------------
    # NumPy High-Speed Cache & Routing
    # -------------------------------------------------------------------------

    def update_numpy_cache_if_dirty(self) -> None:
        """Update cached mappings if dirty."""
        if getattr(self, "_numpy_cache_dirty", True) or not hasattr(
            self, "map_src_channels"
        ):
            self._update_numpy_cache()
            self._numpy_cache_dirty = False

    def _update_numpy_cache(  # pylint: disable=too-many-locals, too-many-branches
        self,
    ) -> None:
        """Update cached arrays for fast block operations."""
        # 1. Boolean mask of patched channels (True if patched, False if not)
        mask = np.zeros(MAX_CHANNELS, dtype=bool)
        for channel in range(1, MAX_CHANNELS + 1):
            if channel in self.channels:
                if (
                    self.channels[channel] != [[None, None]]
                    and None not in self.channels[channel][0]
                ):
                    mask[channel - 1] = True
        for dev_id in self.devices:
            if 1 <= dev_id <= MAX_CHANNELS:
                mask[dev_id - 1] = True
        self.is_patched_mask = mask

        # 2. Flat indexing arrays for conventional intensity level distribution
        src_channels = []
        dst_universes = []
        dst_outputs = []
        dst_curves = []

        for channel, outputs in self.channels.items():
            if outputs == [[None, None]] or None in outputs[0]:
                continue
            for out in outputs:
                output = out[0]
                universe = out[1]
                if universe in self.universes and output:
                    src_channels.append(channel - 1)
                    dst_universes.append(self.universes.index(universe))
                    dst_outputs.append(output - 1)

                    curve_numb = 0
                    if universe in self.outputs and output in self.outputs[universe]:
                        curve_numb = self.outputs[universe][output][1]
                    dst_curves.append(curve_numb)

        self.map_src_channels = np.array(src_channels, dtype=np.intp)
        self.map_dst_universes = np.array(dst_universes, dtype=np.intp)
        self.map_dst_outputs = np.array(dst_outputs, dtype=np.intp)
        self.map_dst_curves = np.array(dst_curves, dtype=np.intp)

        # 3. Direct routing for multi-parameter and multi-resolution device channels
        dynamic_devs: list[LightingDevice] = []
        devices_snapshot = tuple(self.devices.values())
        for dev in devices_snapshot:
            if (
                dev.uses_virtual_dimmer
                or dev.has_16bit_dimmer
                or dev.has_24bit_dimmer
                or (dev.has_physical_dimmer and dev.fixture_type != FixtureType.DIMMER)
            ):
                dynamic_devs.append(dev)

        dev_refs: list[tuple[LightingDevice, Channel]] = []
        dev_dst_univs = []
        dev_dst_outs = []
        dev_is_htp = []

        for dev in devices_snapshot:
            for ch in dev.channels:
                is_conventional_8bit_dimmer = (
                    dev.fixture_type == FixtureType.DIMMER
                    and not dev.has_16bit_dimmer
                    and not dev.has_24bit_dimmer
                    and ch.channel_type == ChannelType.INTENSITY
                    and not ch.fine
                    and not ch.ultra_fine
                )
                if not is_conventional_8bit_dimmer:
                    if ch.universe in self.universes:
                        dev_refs.append((dev, ch))
                        dev_dst_univs.append(self.universes.index(ch.universe))
                        dev_dst_outs.append(ch.address - 1)
                        # Channels driven dynamically by set_intensity are
                        # already scaled with float precision by main_fader.
                        dev_is_htp.append(ch.is_htp and dev not in dynamic_devs)

        self.dynamic_intensity_devices = dynamic_devs
        self.device_channel_refs = dev_refs
        self.map_dev_dst_universes = np.array(dev_dst_univs, dtype=np.intp)
        self.map_dev_dst_outputs = np.array(dev_dst_outs, dtype=np.intp)
        self.map_dev_is_htp = np.array(dev_is_htp, dtype=bool)

    def get_first_patched_channel(self) -> int:
        """Return first patched channel."""
        self.update_numpy_cache_if_dirty()
        indices = np.nonzero(self.is_patched_mask)[0]
        return int(indices[0]) + 1 if len(indices) > 0 else 1

    def get_last_patched_channel(self) -> int:
        """Return last patched channel."""
        self.update_numpy_cache_if_dirty()
        indices = np.nonzero(self.is_patched_mask)[0]
        return int(indices[-1]) + 1 if len(indices) > 0 else 1


# Backward compatibility alias
DMXPatch = PatchManager


__all__ = [
    "PatchCollisionError",
    "FixtureExchangeWarning",
    "PatchManager",
    "DMXPatch",
]
