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
"""Actions for parking and unparking channels and physical DMX output addresses."""

from __future__ import annotations

import typing

from olc.core.action import Action
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _convert_level_to_dmx(level: float | int) -> int:
    """Convert float [0.0..1.0] or int [0..255] or percent float to 0..255."""
    if isinstance(level, float) and 0.0 <= level <= 1.0:
        return int(round(level * 255.0))
    return max(0, min(255, int(round(level))))


def _refresh_dmx(app: CoreApplication) -> None:
    """Trigger DMX frame recalculation and send if backend is present."""
    backend = getattr(app, "backend", None)
    if backend is not None and getattr(backend, "dmx", None) is not None:
        backend.dmx.set_levels()
        backend.dmx.send()


def _clear_unpatched_addresses(
    app: CoreApplication, addresses: typing.Iterable[tuple[int, int]]
) -> None:
    """Reset unpatched physical addresses to 0 in DMX frame."""
    backend = getattr(app, "backend", None)
    dmx = getattr(backend, "dmx", None) if backend is not None else None
    if dmx is None or not hasattr(app, "lightshow"):
        return
    patch = getattr(app.lightshow, "patch", None)
    if patch is None:
        return
    for u, o in addresses:
        if patch.get_address_occupant(u, o) is None:
            if u in patch.universes:
                u_idx = patch.universes.index(u)
                if u_idx < len(dmx.frame) and 1 <= o <= 512:
                    dmx.frame[u_idx][o - 1] = 0


class ChannelParkAction(Action):
    """Action to park one or more channels at a level (or current level)."""

    name = "channel.park"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []
        self.level: float | int | None = None
        self.old_parked: dict[int, int | None] = {}
        self.applied_levels: dict[int, int] = {}

    def configure(
        self,
        channels: list[int] | int,
        level: float | int | None = None,
    ) -> None:
        """Configure channel park action.

        Args:
            channels: Channel number or list of channel numbers.
            level: Target DMX level (0-255 or 0.0-1.0), or None for current level.
        """
        self.channels = [channels] if isinstance(channels, int) else list(channels)
        self.level = level

    def execute(self) -> None:
        """Execute channel park."""
        park_mgr = self.app.lightshow.park
        backend = getattr(self.app, "backend", None)
        dmx = getattr(backend, "dmx", None) if backend is not None else None

        self.old_parked.clear()
        self.applied_levels.clear()

        for ch in self.channels:
            if not 1 <= ch <= MAX_CHANNELS:
                continue
            self.old_parked[ch] = park_mgr.get_channel_park_level(ch)

            if self.level is not None:
                dmx_val = _convert_level_to_dmx(self.level)
            elif dmx is not None:
                curr_level, _ = dmx.get_composite_level(ch - 1)
                dmx_val = curr_level
            else:
                dmx_val = 0

            park_mgr.park_channel(ch, dmx_val)
            self.applied_levels[ch] = dmx_val
            self.app.emit("park.channel_parked", ch, dmx_val)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())

    def undo(self) -> None:
        """Undo channel park."""
        park_mgr = self.app.lightshow.park
        for ch, old_lvl in self.old_parked.items():
            if old_lvl is None:
                park_mgr.unpark_channel(ch)
                self.app.emit("park.channel_unparked", ch)
            else:
                park_mgr.park_channel(ch, old_lvl)
                self.app.emit("park.channel_parked", ch, old_lvl)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())


class ChannelUnparkAction(Action):
    """Action to unpark one or more channels."""

    name = "channel.unpark"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []
        self.old_parked: dict[int, int | None] = {}

    def configure(self, channels: list[int] | int) -> None:
        """Configure channel unpark action."""
        self.channels = [channels] if isinstance(channels, int) else list(channels)

    def execute(self) -> None:
        """Execute channel unpark."""
        park_mgr = self.app.lightshow.park
        self.old_parked.clear()

        for ch in self.channels:
            if not 1 <= ch <= MAX_CHANNELS:
                continue
            self.old_parked[ch] = park_mgr.unpark_channel(ch)
            self.app.emit("park.channel_unparked", ch)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())

    def undo(self) -> None:
        """Undo channel unpark."""
        park_mgr = self.app.lightshow.park
        for ch, old_lvl in self.old_parked.items():
            if old_lvl is not None:
                park_mgr.park_channel(ch, old_lvl)
                self.app.emit("park.channel_parked", ch, old_lvl)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())


class AddressParkAction(Action):
    """Action to park one or more physical DMX addresses."""

    name = "address.park"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.addresses: list[tuple[int, int]] = []
        self.level: float | int = 0
        self.old_parked: dict[tuple[int, int], int | None] = {}

    def configure(
        self,
        addresses: list[tuple[int, int]] | tuple[int, int],
        level: float | int,
    ) -> None:
        """Configure address park action."""
        if isinstance(addresses, tuple):
            self.addresses = [addresses]
        else:
            self.addresses = list(addresses)
        self.level = level

    def execute(self) -> None:
        """Execute address park."""
        park_mgr = self.app.lightshow.park
        self.old_parked.clear()
        dmx_val = _convert_level_to_dmx(self.level)

        for u, o in self.addresses:
            self.old_parked[(u, o)] = park_mgr.get_address_park_level(u, o)
            park_mgr.park_address(u, o, dmx_val)
            self.app.emit("park.address_parked", u, o, dmx_val)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())

    def undo(self) -> None:
        """Undo address park."""
        park_mgr = self.app.lightshow.park
        unparked_addrs = []
        for (u, o), old_lvl in self.old_parked.items():
            if old_lvl is None:
                park_mgr.unpark_address(u, o)
                self.app.emit("park.address_unparked", u, o)
                unparked_addrs.append((u, o))
            else:
                park_mgr.park_address(u, o, old_lvl)
                self.app.emit("park.address_parked", u, o, old_lvl)

        if unparked_addrs:
            _clear_unpatched_addresses(self.app, unparked_addrs)
        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())


class AddressUnparkAction(Action):
    """Action to unpark one or more physical DMX addresses."""

    name = "address.unpark"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.addresses: list[tuple[int, int]] = []
        self.old_parked: dict[tuple[int, int], int | None] = {}

    def configure(
        self,
        addresses: list[tuple[int, int]] | tuple[int, int],
    ) -> None:
        """Configure address unpark action."""
        if isinstance(addresses, tuple):
            self.addresses = [addresses]
        else:
            self.addresses = list(addresses)

    def execute(self) -> None:
        """Execute address unpark."""
        park_mgr = self.app.lightshow.park
        self.old_parked.clear()

        for u, o in self.addresses:
            self.old_parked[(u, o)] = park_mgr.unpark_address(u, o)
            self.app.emit("park.address_unparked", u, o)

        _clear_unpatched_addresses(self.app, self.addresses)
        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())

    def undo(self) -> None:
        """Undo address unpark."""
        park_mgr = self.app.lightshow.park
        for (u, o), old_lvl in self.old_parked.items():
            if old_lvl is not None:
                park_mgr.park_address(u, o, old_lvl)
                self.app.emit("park.address_parked", u, o, old_lvl)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())


class ParkUnparkAllAction(Action):
    """Action to unpark all parked channels and physical DMX addresses."""

    name = "park.unpark_all"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_channels: dict[int, int] = {}
        self.old_addresses: dict[tuple[int, int], int] = {}

    def configure(self) -> None:
        """Configure unpark all action."""

    def execute(self) -> None:
        """Execute unpark all."""
        park_mgr = self.app.lightshow.park
        self.old_channels, self.old_addresses = park_mgr.unpark_all()

        for ch in self.old_channels:
            self.app.emit("park.channel_unparked", ch)

        for u, o in self.old_addresses:
            self.app.emit("park.address_unparked", u, o)

        _clear_unpatched_addresses(self.app, self.old_addresses.keys())
        _refresh_dmx(self.app)
        self.app.emit("park.changed", 0)

    def undo(self) -> None:
        """Undo unpark all."""
        park_mgr = self.app.lightshow.park
        for ch, lvl in self.old_channels.items():
            park_mgr.park_channel(ch, lvl)
            self.app.emit("park.channel_parked", ch, lvl)

        for (u, o), lvl in self.old_addresses.items():
            park_mgr.park_address(u, o, lvl)
            self.app.emit("park.address_parked", u, o, lvl)

        _refresh_dmx(self.app)
        self.app.emit("park.changed", park_mgr.total_parked_count())
