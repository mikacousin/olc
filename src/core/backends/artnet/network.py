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

import asyncio
import fcntl
import typing
from ipaddress import IPv4Address, ip_network
from socket import AF_INET, SO_BROADCAST, SO_REUSEADDR, SOCK_DGRAM, SOL_SOCKET, socket
from struct import pack

import ifaddr
from olc.core.backends.artnet.protocol import PORT

if typing.TYPE_CHECKING:
    from olc.core.backends.artnet.artnet import Artnet


def get_ip_and_mac(addr: tuple[str, int]) -> tuple[str | None, tuple[int, ...] | None]:
    """Retrieve local IP and MAC addresses used to reach a target."""
    reply_ip = None
    mac = None
    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for ip in adapter.ips:
            if ip.is_IPv4:
                a = ip_network(
                    f"{addr[0]}/{ip.network_prefix}", strict=False
                ).network_address
                b = ip_network(
                    f"{ip.ip}/{ip.network_prefix}", strict=False
                ).network_address
                if a == b:
                    reply_ip = str(ip.ip)
                    sock = socket(AF_INET, SOCK_DGRAM)
                    info = fcntl.ioctl(
                        sock.fileno(),
                        0x8927,
                        pack("256s", bytes(ip.nice_name, "utf-8")[:15]),
                    )
                    mac = tuple(info[18:24])
                    break
    return reply_ip, mac


class ArtNetProtocol(asyncio.DatagramProtocol):
    """Protocol handling incoming Art-Net UDP datagrams in the asyncio loop."""

    def __init__(self, artnet: Artnet) -> None:
        self.artnet = artnet

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Called when a UDP datagram is received."""
        self.artnet.read_packet(data, (addr[0], PORT))


class Network:  # pylint: disable=too-many-instance-attributes
    """Listen Art-Net packets"""

    def __init__(self, artnet: Artnet) -> None:
        self.interfaces: dict[str, IPv4Address] = {}
        self.sock: socket | None = None
        self.artnet = artnet
        self.listen = False
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: ArtNetProtocol | None = None
        self.if_task: asyncio.Task | None = None

    def start(self) -> None:
        """Start socket listener and interface polling asynchronously."""
        if not self.listen:
            self.listen = True
            loop = self.artnet.loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self._async_start(), loop).result()

    async def _async_start(self) -> None:
        """Asynchronously bind socket, interfaces task, and datagram endpoint."""
        if self.sock is not None:
            return

        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            sock.bind(("", PORT))
        except OSError as err:
            print(f"[Art-Net] Socket bind error: {err}")
            sock.close()
            return

        self.sock = sock

        loop = self.artnet.loop
        if loop is None:
            return
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: ArtNetProtocol(self.artnet), sock=sock
        )

        self.if_task = asyncio.create_task(self._interfaces_loop())

    def stop(self) -> None:
        """Stop network listener interfaces and close sockets."""
        self.listen = False
        loop = self.artnet.loop
        if loop and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._async_stop(), loop).result(
                    timeout=2.0
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        # Fallback local cleanup
        if self.if_task:
            self.if_task = None
        if self.transport:
            self.transport.close()
            self.transport = None
        self.protocol = None
        if self.sock:
            self.sock.close()
            self.sock = None

    async def _async_stop(self) -> None:
        """Asynchronously cancel interface task and close transport/socket."""
        if self.if_task:
            self.if_task.cancel()
            try:
                await self.if_task
            except asyncio.CancelledError:
                pass
            self.if_task = None

        if self.transport:
            self.transport.close()
            self.transport = None
        self.protocol = None

        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, packet: bytes, addr: tuple[str, int]) -> None:
        """Send packet to a specific address via socket."""
        if self.sock:
            self.sock.sendto(packet, addr)

    def send_broadcast(self, packet: bytes) -> None:
        """Broadcast packet on all authorized interfaces."""
        for brd in self.interfaces.values():
            if brd and self.sock:
                try:
                    self.sock.sendto(packet, (f"{brd}", PORT))
                except OSError:
                    pass

    async def _interfaces_loop(self) -> None:
        """Periodic loop scanning network interfaces every 1s."""
        while self.listen:
            try:
                self._get_if()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[Art-Net] Error getting interfaces: {e}")
            await asyncio.sleep(1.0)

    def _get_if(self) -> None:
        adapters = ifaddr.get_adapters()
        for adapter in adapters:
            for ip in adapter.ips:
                if ip.is_IPv4:
                    if IPv4Address(ip.ip).is_loopback:
                        self.interfaces[str(ip.ip)] = IPv4Address(ip.ip)
                    else:
                        net = ip_network(f"{ip.ip}/{ip.network_prefix}", strict=False)
                        broadcast = net.broadcast_address
                        if broadcast.version == 4:
                            self.interfaces[str(ip.ip)] = broadcast
