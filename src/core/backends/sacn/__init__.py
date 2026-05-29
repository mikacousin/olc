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
# pylint: disable=too-many-instance-attributes,too-many-branches
# pylint: disable=too-many-nested-blocks,no-name-in-module,unexpected-keyword-arg
from __future__ import annotations

import asyncio
import socket
import time
import typing
import uuid
from typing import Callable

from olc.core.backends.sacn.merge import SacnMerger
from olc.core.backends.sacn.network import SacnNetwork
from olc.core.backends.sacn.protocol import (
    SacnDecodeError,
    SacnDiscoveryPacket,
    SacnPacket,
    SacnSyncPacket,
)
from olc.core.senders import SACNSender, _sacn_multicast_ip
from olc.core.universe_config import Protocol
from olc.core.universe_data import DMXUniverse

if typing.TYPE_CHECKING:
    from olc.core.universe_config import UniverseMap


class SacnManager:
    """UI-agnostic manager coordinating sACN multicast listeners,

    source priority merging, and DMX transmit operations for CoreEngine.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        universe_map: UniverseMap,
        on_dmx_received: Callable[[int, list[int]], None] | None = None,
        notify: Callable | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        no_transmit: bool = False,
        no_listen: bool = False,
    ) -> None:
        self.loop = loop
        self.universe_map = universe_map
        self._no_transmit = no_transmit
        self._no_listen = no_listen
        self.universes = [
            config.universe_id
            for config in universe_map
            if Protocol.SACN in config.protocols
        ]
        self.on_dmx_received = on_dmx_received
        self.notify = notify

        # Set up a priority-based source merger per universe
        self.mergers: dict[int, SacnMerger] = {}
        for u in self.universes:
            self.mergers[u] = SacnMerger(
                universe=u,
                callback=self._handle_incoming_dmx,
            )

        # Set up a sender registry
        self.senders: dict[int, SACNSender] = {}
        if not no_transmit:
            for u in self.universes:
                self.senders[u] = SACNSender(universe=u, multicast=True)

        self.network = SacnNetwork(typing.cast(typing.Any, self))

        # ACN Component CID and discovery thread configurations
        self._cid = uuid.uuid4().bytes
        self.is_running = False
        self.discovery_task: asyncio.Task | None = None
        self._discovery_sock: socket.socket | None = None
        self._last_discovery_universes: list[int] = []

        # Queue for pending synchronized DMX packets
        self.pending_dmx: dict[bytes, dict[int, list[int]]] = {}
        self.pending_timestamps: dict[bytes, float] = {}
        self.pending_ips: dict[bytes, str] = {}
        self._sync_sequences: dict[int, int] = {}

    def _get_active_universes(self) -> list[int]:
        """Return the sorted list of active transmitting universes (1 to 63999)."""
        return sorted([u for u in self.senders if 1 <= u <= 63999])

    def _broadcast_discovery(self) -> None:
        """Broadcast sACN Universe Discovery packets for all active universes."""
        if not self._discovery_sock:
            return

        univs = self._get_active_universes()
        chunk_size = 512
        chunks = [univs[i : i + chunk_size] for i in range(0, len(univs), chunk_size)]
        if not chunks:
            chunks = [[]]

        last_page = len(chunks) - 1
        # Use first sender's source name if customized, otherwise default
        source_name = "OLC DMX Engine"
        if self.senders:
            first_sender = next(iter(self.senders.values()))
            source_name = getattr(first_sender, "_source", "OLC DMX Engine")

        for page, chunk in enumerate(chunks):
            packet = SacnDiscoveryPacket(
                cid=self._cid,
                source_name=source_name,
                universes=chunk,
                page=page,
                last_page=last_page,
            )
            try:
                self._discovery_sock.sendto(packet.encode(), ("239.255.250.198", 5568))
            except OSError:
                pass

    def _periodic_discovery(self) -> None:
        """Triggered periodically by the RepeatedTimer."""
        self._broadcast_discovery()

    def trigger_discovery(self) -> None:
        """Check if active universes list changed, and broadcast immediately if so."""
        if not self._discovery_sock:
            return
        current = self._get_active_universes()
        if current != self._last_discovery_universes:
            self._last_discovery_universes = list(current)
            self._broadcast_discovery()

    def add_sender(self, universe: int, sender: SACNSender) -> None:
        """Register a dynamic sender and trigger discovery update.

        Args:
            universe: Universe ID
            sender: SACNSender instance
        """
        self.senders[universe] = sender
        self.trigger_discovery()

    def del_sender(self, universe: int) -> None:
        """Unregister a sender and trigger discovery update.

        Args:
            universe: Universe ID
        """
        sender = self.senders.pop(universe, None)
        if sender:
            sender.close()
        self.trigger_discovery()

    def send_sync(self, sync_address: int) -> None:
        """Send an E1.31 Synchronization Packet for the specified universe."""
        if not self._discovery_sock:
            return

        seq = self._sync_sequences.get(sync_address, 0)
        self._sync_sequences[sync_address] = (seq + 1) & 0xFF

        packet = SacnSyncPacket(
            cid=self._cid,
            sequence=seq,
            sync_address=sync_address,
        )
        data = packet.encode()
        try:
            dest_ip = _sacn_multicast_ip(sync_address)
            self._discovery_sock.sendto(data, (dest_ip, 5568))
        except OSError:
            pass

    def start(self) -> None:
        """Start low-level UDP listeners and join multicast groups."""
        self.is_running = True
        if not self._no_listen:
            self.network.start()
            # Join multicast groups for all configured universes
            for u in self.universes:
                # Universe 0 is reserved and forbidden for sACN multicast by standard
                if u != 0:
                    self.network.join_multicast(u)
                    # Also join multicast group for synchronization universes if
                    # configured
                    sync_addr = self.universe_map[u].sacn.sync_address
                    if sync_addr > 0:
                        self.network.join_multicast(sync_addr)

        if self._no_transmit:
            return

        # Initialize multicast socket for universe discovery broadcasts
        self._discovery_sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        self._discovery_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        self._discovery_sock.setblocking(False)

        # Broadcast the initial universe list
        self._last_discovery_universes = list(self._get_active_universes())
        self._broadcast_discovery()

        # Start periodic universe discovery loop every 10 seconds
        if self.loop and self.loop.is_running() and self.discovery_task is None:
            asyncio.run_coroutine_threadsafe(
                self._start_discovery_loop(), self.loop
            ).result()

    async def _start_discovery_loop(self) -> None:
        """Launch the discovery loop task inside the event loop thread."""
        self.discovery_task = asyncio.create_task(self._discovery_loop())

    async def _discovery_loop(self) -> None:
        """Periodic loop broadcasting sACN universe discovery every 10s."""
        while self.is_running:
            await asyncio.sleep(10.0)
            try:
                self._periodic_discovery()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[sACN] Error in discovery loop: {e}")

    def stop(self) -> None:
        """Stop low-level UDP listeners and leave multicast groups."""
        self.is_running = False
        self.network.stop()
        for sender in self.senders.values():
            sender.close()

        if self._no_transmit:
            return

        # Cleanly stop discovery thread and close discovery socket
        if self.loop and self.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._async_stop_discovery(), self.loop
                ).result(timeout=2.0)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if self.discovery_task:
            self.discovery_task = None

        if self._discovery_sock is not None:
            self._discovery_sock.close()
            self._discovery_sock = None

    async def _async_stop_discovery(self) -> None:
        """Cancel discovery loop task asynchronously."""
        if self.discovery_task:
            self.discovery_task.cancel()
            try:
                await self.discovery_task
            except asyncio.CancelledError:
                pass
            self.discovery_task = None

    def send(self, universe: int, data: bytes | list[int], priority: int = 100) -> None:
        """Send DMX data to sACN multicast groups."""
        sender = self.senders.get(universe)
        if sender:
            # Update priority dynamically
            sender._priority = priority  # pylint: disable=protected-access
            # Wrap payload into a DMXUniverse container
            dummy_univ = DMXUniverse(universe)
            dummy_univ.array[:] = list(data)[:512]
            sender.send(dummy_univ)

    def _check_pending_timeouts(self) -> None:
        """Process and commit pending DMX packets that have timed out (>100ms)."""
        now = time.time()
        timeout_cids = []
        for cid, timestamp in list(self.pending_timestamps.items()):
            if now - timestamp > 0.1:  # 100ms timeout
                timeout_cids.append(cid)

        for cid in timeout_cids:
            if cid in self.pending_dmx:
                for u, dmx_data in list(self.pending_dmx[cid].items()):
                    merger = self.mergers.get(u)
                    if merger:
                        source_name = "sACN Source"
                        for s in merger.sources.values():
                            if s.cid == cid:
                                source_name = s.name
                                break
                        merger.update(
                            cid=cid,
                            name=source_name,
                            priority=100,  # Fallback priority
                            data=dmx_data,
                            ip=self.pending_ips.get(cid, ""),
                        )
                self.pending_dmx.pop(cid, None)
            self.pending_timestamps.pop(cid, None)
            self.pending_ips.pop(cid, None)

    def read_packet(self, data: bytes, _addr: tuple[str, int]) -> None:
        """Callback from low-level network UDP socket on packet reception."""
        self._check_pending_timeouts()

        # Try decoding as standard sACN Data Packet
        try:
            packet = SacnPacket()
            packet.decode(data)
            universe = packet.universe
            merger = self.mergers.get(universe)
            if merger:
                # If packet has a non-zero synchronization address, queue it
                if packet.sync_address > 0:
                    if packet.cid not in self.pending_dmx:
                        self.pending_dmx[packet.cid] = {}
                    self.pending_dmx[packet.cid][universe] = packet.data
                    if packet.cid not in self.pending_timestamps:
                        self.pending_timestamps[packet.cid] = time.time()
                    self.pending_ips[packet.cid] = _addr[0]
                else:
                    # Otherwise, apply immediately
                    merger.update(
                        cid=packet.cid,
                        name=packet.source_name,
                        priority=packet.priority,
                        data=packet.data,
                        stream_terminated=packet.stream_terminated,
                        ip=_addr[0],
                    )
                    if self.notify and packet.cid not in merger.sources:
                        self.notify("add-source", packet.source_name, universe)
            return
        except SacnDecodeError:
            pass

        # Try decoding as sACN Synchronization Packet
        try:
            sync_packet = SacnSyncPacket()
            sync_packet.decode(data)
            cid = sync_packet.cid
            if cid in self.pending_dmx:
                for u, u_data in list(self.pending_dmx[cid].items()):
                    # Match the universe's configured synchronization address
                    if u in self.universe_map:
                        config = self.universe_map[u]
                        if config.sacn.sync_address == sync_packet.sync_address:
                            merger = self.mergers.get(u)
                            if merger:
                                source_name = "sACN Source"
                                for s in merger.sources.values():
                                    if s.cid == cid:
                                        source_name = s.name
                                        break
                                merger.update(
                                    cid=cid,
                                    name=source_name,
                                    priority=100,  # Fallback priority
                                    data=u_data,
                                    ip=self.pending_ips.get(cid, ""),
                                )
                self.pending_dmx.pop(cid, None)
                self.pending_timestamps.pop(cid, None)
                self.pending_ips.pop(cid, None)
        except SacnDecodeError:
            pass

    def _handle_incoming_dmx(self, universe: int, data: list[int]) -> None:
        if self.on_dmx_received:
            self.on_dmx_received(universe, data)
