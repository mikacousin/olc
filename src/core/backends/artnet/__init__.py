from __future__ import annotations
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
import asyncio
import typing
from typing import Callable

from olc.core.backends.artnet.artnet import Discovery, Listeners, Sender
from olc.core.backends.artnet.network import Network
from olc.core.backends.artnet.protocol import PORT, OpCodes, get_opcode
from olc.core.universe_config import Protocol

if typing.TYPE_CHECKING:
    from olc.core.universe_config import UniverseMap


class ArtNetManager:  # pylint: disable=too-many-instance-attributes
    """UI-agnostic manager coordinating Art-Net discovery, listeners,

    and unicast target mapping for CoreEngine.
    """

    def __init__(
        self,
        universe_map: UniverseMap,
        on_dmx_received: Callable[[int, list[int]], None] | None = None,
        notify: Callable | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.loop = loop
        self.universes = [
            config.universe_id
            for config in universe_map
            if Protocol.ARTNET in config.protocols
        ]

        # Callbacks for received ArtDmx packets
        self.on_dmx_received = on_dmx_received
        self.notify = notify

        # Listeners for ArtDmx packets from other controllers
        self.listeners = Listeners(self.universes, self._handle_incoming_dmx)

        # Senders registry: map universe to active unicast nodes
        self.senders = {}
        for u in self.universes:
            self.senders[u] = Sender(u, self._notify_forwarder)

        self.network = Network(typing.cast(typing.Any, self))
        self.discovery = Discovery(
            self.network, self.universes, self.senders, self._notify_forwarder
        )

    def start(self) -> None:
        """Start network listener interfaces and discovery threads."""
        self.network.start()
        self.discovery.start()

    def stop(self) -> None:
        """Stop network listener interfaces and discovery threads."""
        self.network.stop()
        self.discovery.stop()

    def get_node_ips(self, universe: int) -> list[str]:
        """Return the list of discovered IP addresses outputting/listening for

        this universe.
        """
        if universe not in self.senders:
            return []
        nodes = self.senders[universe].nodes.copy()
        # Filter out local loopback virtual node to get real external nodes
        return [node.ip for node in nodes.values() if node.ip != "127.0.0.1"]

    def send(self, universe: int, packet: bytes) -> None:
        """Send Art-Net universe DMX data to registered nodes."""
        if self.senders.get(universe, None):
            data = self.senders[universe].artdmx.encode(universe, packet)
            nodes = self.senders[universe].nodes.copy()
            for node in nodes.values():
                addr = (node.ip, PORT)
                self.network.send(data, addr)

    def send_sync(self) -> None:
        """Broadcast an ArtSync packet to synchronize all Art-Net universes."""
        packet = b"Art-Net\x00" + b"\x00\x52" + b"\x00\x0e" + b"\x00\x00"
        self.network.send_broadcast(packet)

    def _handle_incoming_dmx(self, universe: int, data: list[int]) -> None:
        if self.on_dmx_received:
            self.on_dmx_received(universe, data)

    def _node_changed_callback(
        self, action: str, *args: object, **kwargs: object
    ) -> None:
        # Generic node discovery event logging
        pass

    def _notify_forwarder(self, action: str, *args: object, **kwargs: object) -> object:
        if self.notify is not None:
            return self.notify(action, *args, **kwargs)
        return None

    def read_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        """Dispatch received UDP packets to discovery or listener handlers."""
        opcode = get_opcode(data)
        if opcode == OpCodes.OP_POLL_REPLY:
            self.discovery.on_art_poll_reply(data)
        elif opcode == OpCodes.OP_POLL:
            self.discovery.on_art_poll(data, addr)
        elif opcode == OpCodes.OP_DMX:
            self.listeners.on_artdmx(data, addr)
