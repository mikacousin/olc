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
from typing import Optional

import numpy as np

from olc.define import DEFAULT_UNIVERSES, MAX_CHANNELS, is_int
from olc.devices.builtin import create_dimmer_definition
from olc.devices.device import Channel, ChannelType, FixtureType, LightingDevice
from olc.devices.fixture import FixtureDefinition

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.curve import Curve
    from olc.gtk3.application import Application


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
        self.map_dev_dst_universes = np.array([], dtype=np.intp)
        self.map_dev_dst_outputs = np.array([], dtype=np.intp)
        self.map_dev_is_htp = np.array([], dtype=bool)

        self.patch_1on1()

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

        if device_id in self.devices:
            self.unpatch_device(device_id)

        device = fixture_def.instantiate(
            fixture_id=device_id,
            label=label or f"{fixture_def.model} {device_id}",
            universe=universe,
            address=address,
            mode_name=mode.name,
        )
        device.set_curve_provider(self._get_curve_by_id)
        self.devices[device_id] = device

        for ch in device.channels:
            if ch.universe not in self._grid:
                self.add_universe(ch.universe)
            self._grid[ch.universe][ch.address - 1] = device_id

            # Maintain legacy structures for intensity/dimmer channels
            if (
                ch.channel_type == ChannelType.INTENSITY
                and not ch.fine
                and not ch.ultra_fine
            ):
                if device_id not in self.channels or self.channels[device_id] == [
                    [None, None]
                ]:
                    self.channels[device_id] = [[ch.address, ch.universe]]
                elif [ch.address, ch.universe] not in self.channels[device_id]:
                    self.channels[device_id].append([ch.address, ch.universe])
                if ch.universe not in self.outputs:
                    self.outputs[ch.universe] = {}
                self.outputs[ch.universe][ch.address] = [device_id, 0]

        self._numpy_cache_dirty = True
        return device

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

    def get_device(self, device_id: int) -> Optional[LightingDevice]:
        """Get a registered LightingDevice by ID."""
        return self.devices.get(device_id)

    def has_device(self, device_id: int) -> bool:
        """True if a device with device_id is patched."""
        return device_id in self.devices

    def restore_device(self, device: LightingDevice) -> None:
        """Restore an existing device instance into the patch registry."""
        device.set_curve_provider(self._get_curve_by_id)
        self.devices[device.fixture_id] = device
        for ch in device.channels:
            if ch.universe not in self._grid:
                self.add_universe(ch.universe)
            self._grid[ch.universe][ch.address - 1] = device.fixture_id
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
            self.devices[channel] = dev

        self._numpy_cache_dirty = True

    def unpatch(self, channel: int, output: int, univ: int) -> None:
        """Unpatch an output from a channel (legacy method)."""
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

    def _update_numpy_cache(self) -> None:  # pylint: disable=too-many-locals
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

        # 3. Direct routing for multi-parameter device channels
        dev_refs: list[tuple[LightingDevice, Channel]] = []
        dev_dst_univs = []
        dev_dst_outs = []
        dev_is_htp = []

        for dev in self.devices.values():
            for ch in dev.channels:
                if (
                    ch.channel_type != ChannelType.INTENSITY
                    or dev.fixture_type != FixtureType.DIMMER
                ):
                    if ch.universe in self.universes:
                        dev_refs.append((dev, ch))
                        dev_dst_univs.append(self.universes.index(ch.universe))
                        dev_dst_outs.append(ch.address - 1)
                        dev_is_htp.append(ch.is_htp)

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


class PatchByOutputs:
    """Manipulate Patch using Outputs order"""

    app: Application | CoreApplication
    outputs: list[int]
    last: int
    patch: DMXPatch

    def __init__(self, app: Application | CoreApplication, patch: DMXPatch) -> None:
        self.app = app
        self.outputs = []
        self.last = 0
        self.patch = patch

    @property
    def commandline(self) -> CoreCommandLine:
        """Get the logical command line instance."""
        return self.app.core.commandline

    def get_selected(self) -> str:
        """Return selected outputs

        Returns:
            String like "1, 2, 3, 4"
        """
        outs = []
        for out in self.outputs:
            output, universe = self.get_output_universe(out)
            outs.append(f"{output}.{universe}")
        string = ", ".join(str(out) for out in outs)
        return string

    def select_output(self) -> None:
        """Select one output"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            outputs = [output_index]
            last = output_index
        else:
            outputs = []
            last = 0
        self.app.core.action_registry.execute("output.select", outputs, last)

    def thru(self) -> None:
        """Thru output"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            new_outputs = list(self.outputs)
            if output_index > self.last:
                for out in range(self.last + 1, output_index + 1):
                    new_outputs.append(out)
            else:
                for out in range(self.last - 1, output_index - 1, -1):
                    new_outputs.append(out)
            self.app.core.action_registry.execute(
                "output.select", new_outputs, output_index
            )

    def add_output(self) -> None:
        """Add an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            new_outputs = list(self.outputs)
            new_outputs.append(output_index)
            self.app.core.action_registry.execute(
                "output.select", new_outputs, output_index
            )

    def del_output(self) -> None:
        """Remove an output to selection"""
        output, universe = self._string_to_output()
        output_index = self._get_output_index(output, universe)
        if output_index:
            new_outputs = list(self.outputs)
            if output_index in new_outputs:
                new_outputs.remove(output_index)
            self.app.core.action_registry.execute(
                "output.select", new_outputs, output_index
            )

    def patch_channel(self, several: bool) -> None:
        """Patch

        Args:
            several: True if increment channels for each output,
                     False if same channel for every output
        """
        channel = self._string_to_channel()
        if channel is None:
            return
        self.__for_each_output(channel, several)

        # Select next output
        output_index = self.last
        if output_index < len(self.patch.universes) * 512:
            output_index += 1
        output, universe = self.get_output_universe(output_index)
        self._set_commandline_string(f"{output}.{universe}")
        self.select_output()

    def __for_each_output(self, channel: int, several: bool) -> None:
        for i, output_index in enumerate(self.outputs):
            output, univ = self.get_output_universe(output_index)
            if output and univ:
                # Unpatch if no channel
                if not channel:
                    self.__unpatch(output, univ)
                else:
                    chan = channel + i if several else channel
                    self.app.core.action_registry.execute(
                        "patch.add_output", chan, output, univ
                    )

    def __unpatch(self, output: int, univ: int) -> None:
        if univ in self.patch.outputs and output in self.patch.outputs[univ]:
            self.app.core.action_registry.execute("patch.unpatch_output", output, univ)

    def _get_commandline_string(self) -> str:
        return self.commandline.get_string()

    def _set_commandline_string(self, value: str) -> None:
        self.app.core.action_registry.execute("commandline.set", value)

    def get_output_universe(self, out: int) -> tuple[Optional[int], Optional[int]]:
        """Returns output.universe corresponding to output index
        (1 to count of universes * 512).

        Args:
            out: output index

        Returns:
            output, universe
        """
        output = None
        universe = None
        max_out = len(self.patch.universes) * 512
        if 0 < out <= max_out:
            univ_index = int((out - 1) / 512)
            universe = self.patch.universes[univ_index]
            output = out - (univ_index * 512)
        return (output, universe)

    def _get_output_index(
        self, out: Optional[int], univ: Optional[int]
    ) -> Optional[int]:
        output = None
        if out is None or univ is None:
            return None
        if (0 < out <= 512) and univ in self.patch.universes:
            univ_index = self.patch.universes.index(univ)
            output = out + (univ_index * 512)
        return output

    def _string_to_output(self) -> tuple[Optional[int], Optional[int]]:
        output = None
        universe = None
        keystring = self._get_commandline_string()
        if not keystring:
            keystring = "0"
        if "." in keystring:
            if keystring.index("."):
                split = keystring.split(".")
                output = int(split[0])
                if 0 < output <= 512:
                    universe = int(split[1])
        else:
            output = int(keystring)
            universe = self.patch.universes[0] if self.patch.universes else 1
        return (output, universe)

    def _string_to_channel(self) -> Optional[int]:
        keystring = self._get_commandline_string()
        if not keystring:
            keystring = "0"
        if not is_int(keystring):
            return None
        return int(keystring)
