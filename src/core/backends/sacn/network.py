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
"""sACN network protocol and socket coordinator."""

import asyncio
import errno
import socket
import typing

from olc.core.backends.network_utils import get_local_ips
from olc.core.backends.sacn.protocol import PORT

if typing.TYPE_CHECKING:
    from olc.core.backends.sacn import SacnManager


def get_multicast_ip(universe: int) -> str:
    """Return the standard sACN multicast IP address for a given universe."""
    hi = (universe >> 8) & 0xFF
    lo = universe & 0xFF
    return f"239.255.{hi}.{lo}"


class SacnProtocol(asyncio.DatagramProtocol):
    """Protocol handling incoming sACN UDP datagrams in the asyncio loop."""

    def __init__(self, manager: "SacnManager") -> None:
        self.manager = manager

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Called when a UDP datagram is received."""
        self.manager.read_packet(data, addr)


class SacnNetwork:
    """Handles low-level sACN socket creation, multicast joining, and receiving."""

    def __init__(self, manager: "SacnManager") -> None:
        self.manager = manager
        self.sock: socket.socket | None = None
        self.listen = False
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: SacnProtocol | None = None
        self.joined_universes: set[int] = set()

    def _get_join_ips(self) -> list[str]:
        """Get the list of IP addresses of interfaces to join multicast on.
        Filters loopback and 0.0.0.0 if other active interfaces exist to avoid
        redundant IGMP memberships.
        """
        local_ips = get_local_ips()
        physical_ips = [ip for ip in local_ips if ip not in ("0.0.0.0", "127.0.0.1")]
        if physical_ips:
            return physical_ips
        return ["0.0.0.0"]

    def start(self) -> None:
        """Create socket, join multicast groups, and bind DatagramProtocol."""
        if not self.listen:
            self.listen = True
            if self.manager.loop and self.manager.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._async_start(), self.manager.loop
                ).result()

    async def _async_start(self) -> None:
        """Asynchronously bind the UDP datagram socket and endpoint."""
        if self.sock is not None:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        try:
            sock.bind(("", PORT))
        except OSError as err:
            print(f"[sACN] Socket bind error: {err}")
            sock.close()
            return

        self.sock = sock

        # Join all multicast groups on all discovered local network interfaces
        local_ips = self._get_join_ips()
        for universe in list(self.joined_universes):
            mcast_ip = get_multicast_ip(universe)
            for iface in local_ips:
                try:
                    mreq = socket.inet_aton(mcast_ip) + socket.inet_aton(iface)
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                except OSError as err:
                    if err.errno != errno.EADDRINUSE:
                        print(
                            f"[sACN] Error joining multicast on {iface} "
                            f"for universe {universe}: {err}"
                        )

        loop = self.manager.loop
        if loop is None:
            return
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: SacnProtocol(self.manager), sock=sock
        )

    def stop(self) -> None:
        """Stop receiver transport and close socket."""
        self.listen = False
        if self.manager.loop and self.manager.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._async_stop(), self.manager.loop
                ).result(timeout=2.0)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        # Fallback local cleanup
        if self.transport:
            self.transport.close()
            self.transport = None
        self.protocol = None
        if self.sock:
            self.sock.close()
            self.sock = None

    async def _async_stop(self) -> None:
        """Close transport and leave multicast groups asynchronously."""
        if self.transport:
            self.transport.close()
            self.transport = None
        self.protocol = None

        if self.sock:
            local_ips = self._get_join_ips()
            for universe in list(self.joined_universes):
                mcast_ip = get_multicast_ip(universe)
                for iface in local_ips:
                    try:
                        mreq = socket.inet_aton(mcast_ip) + socket.inet_aton(iface)
                        self.sock.setsockopt(
                            socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq
                        )
                    except OSError:
                        pass
            self.sock.close()
            self.sock = None

    def join_multicast(self, universe: int) -> None:
        """Join the sACN multicast group for a given universe."""
        if universe in self.joined_universes:
            return

        self.joined_universes.add(universe)
        if self.sock:
            mcast_ip = get_multicast_ip(universe)
            local_ips = self._get_join_ips()
            for iface in local_ips:
                try:
                    mreq = socket.inet_aton(mcast_ip) + socket.inet_aton(iface)
                    self.sock.setsockopt(
                        socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
                    )
                except OSError as err:
                    if err.errno != errno.EADDRINUSE:
                        print(
                            f"[sACN] Error joining multicast on {iface} "
                            f"for universe {universe}: {err}"
                        )

    def leave_multicast(self, universe: int) -> None:
        """Leave the sACN multicast group for a given universe."""
        if universe not in self.joined_universes:
            return

        self.joined_universes.discard(universe)
        if self.sock:
            mcast_ip = get_multicast_ip(universe)
            local_ips = self._get_join_ips()
            for iface in local_ips:
                try:
                    mreq = socket.inet_aton(mcast_ip) + socket.inet_aton(iface)
                    self.sock.setsockopt(
                        socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq
                    )
                except OSError:
                    pass
