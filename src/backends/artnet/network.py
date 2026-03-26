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

import fcntl
import threading
import typing
from ipaddress import IPv4Address, ip_network
from socket import AF_INET, SO_BROADCAST, SO_REUSEADDR, SOCK_DGRAM, SOL_SOCKET, socket
from struct import pack

import ifaddr
from olc.backends.artnet.protocol import PORT
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    from olc.backends.artnet import Artnet


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


class Network:
    """Listen Art-Net packets"""

    listen: bool
    listen_thread: threading.Thread
    sock: socket | None

    def __init__(self, artnet: Artnet) -> None:
        self.if_thread = RepeatedTimer(1, self._get_if)
        self.interfaces: dict[str, IPv4Address] = {}
        self.sock = None
        self.artnet = artnet
        self.listen_thread = threading.Thread(target=self._listener, daemon=True)
        self.listen_thread.start()
        self.listen = True

    def stop(self) -> None:
        """Stop network listener interfaces and close sockets."""
        self.listen = False
        self.listen_thread.join()
        self.if_thread.stop()
        if self.sock:
            self.sock.close()

    def send(self, packet: bytes, addr: tuple[str, int]) -> None:
        """Send packet to a specific address via socket."""
        if self.sock:
            self.sock.sendto(packet, addr)

    def send_broadcast(self, packet: bytes) -> None:
        """Broadcast packet on all authorized interfaces."""
        for brd in self.interfaces.values():
            if brd and self.sock:
                self.sock.sendto(packet, (f"{brd}", PORT))

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

    def _listener(self) -> None:
        with socket(AF_INET, SOCK_DGRAM) as self.sock:
            self.sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
            self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.sock.bind(("", PORT))
            self.sock.settimeout(5)

            while self.listen:
                try:
                    data, addr = self.sock.recvfrom(1024)
                except TimeoutError:
                    print("Timeout error on Art-Net listener.")
                    continue
                else:
                    self.artnet.read_packet(data, (addr[0], PORT))
