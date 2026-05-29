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
import socket
import struct
import sys
import typing
import uuid

from olc.core.universe_data import NUM_CHANNELS, DMXUniverse

if typing.TYPE_CHECKING:
    from olc.core.backends.artnet import ArtNetManager

ARTNET_PORT = 6454
SACN_PORT = 5568

# Art-Net ArtDmx fixed header parts
_ARTNET_ID = b"Art-Net\x00"
_ARTNET_OPCODE = struct.pack("<H", 0x5000)  # OpDmx
_ARTNET_PROTO = struct.pack(">H", 14)  # protocol version 14

_HAS_SENDMSG = hasattr(socket.socket, "sendmsg")


def _build_artnet_header(sequence: int, universe: int) -> bytes:
    """Build the 18-byte ArtDmx header."""
    return (
        _ARTNET_ID
        + _ARTNET_OPCODE
        + _ARTNET_PROTO
        + struct.pack("B", sequence & 0xFF)
        + b"\x00"  # physical
        + struct.pack("<H", universe & 0x7FFF)  # universe LE
        + struct.pack(">H", NUM_CHANNELS)  # length BE
    )


class ArtNetSender:
    """
    Sends a DMX universe over Art-Net 4 via UDP.
    Uses send-msg() + memory-view on Linux/macOS (zero-copy).
    Falls back to send-to() on Windows.
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        ip: str,
        universe: int = 0,
        port: int = ARTNET_PORT,
        manager: ArtNetManager | None = None,
        sync_active: bool = False,
    ) -> None:
        self._ip = ip
        self._port = port
        self._universe = universe
        self._manager = manager
        self._sequence = 0
        self._sync_active = sync_active
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setblocking(False)

    def send(self, dmx_universe: DMXUniverse) -> None:
        """Send one DMX frame."""
        self._sequence = (self._sequence + 1) & 0xFF
        header = _build_artnet_header(self._sequence, self._universe)

        ips = self._manager.get_node_ips(self._universe) if self._manager else []

        if ips:
            # Unicast to all discovered active nodes
            for ip in ips:
                if _HAS_SENDMSG and sys.platform != "win32":
                    try:
                        self._sock.sendmsg(
                            [header, dmx_universe.view], [], 0, (ip, self._port)
                        )
                    except OSError:
                        pass
                else:
                    try:
                        self._sock.sendto(
                            header + bytes(dmx_universe.view), (ip, self._port)
                        )
                    except OSError:
                        pass
        else:
            # Fallback to broadcast
            if _HAS_SENDMSG and sys.platform != "win32":
                try:
                    self._sock.sendmsg(
                        [header, dmx_universe.view], [], 0, (self._ip, self._port)
                    )
                except OSError:
                    pass
            else:
                try:
                    self._sock.sendto(
                        header + bytes(dmx_universe.view), (self._ip, self._port)
                    )
                except OSError:
                    pass

    def close(self) -> None:
        """Close the underlying UDP socket."""
        self._sock.close()


def _sacn_multicast_ip(universe: int) -> str:
    """Return the sACN multi-cast address for a given universe."""
    hi = (universe >> 8) & 0xFF
    lo = universe & 0xFF
    return f"239.255.{hi}.{lo}"


def _build_sacn_buffers(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    cid: bytes,
    source: str,
    universe: int,
    sequence: int,
    priority: int,
    payload: memoryview,
    sync_address: int = 0,
) -> list[bytes | memoryview]:
    """
    Build the sACN (E1.31) scatter/gather buffers for send-msg().
    Returns [root, framing, dmp_layer, payload] without copying the DMX payload.
    """
    dmx_length = NUM_CHANNELS + 1  # start code + 512

    # DMX Protocol Layer
    dmp = (
        struct.pack(
            ">HBBHHH",
            0x7000 | (dmx_length + 10),
            0x02,
            0xA1,
            0x0000,
            0x0001,
            NUM_CHANNELS + 1,
        )
        + b"\x00"
    )  # DMX start code

    # Framing Layer
    source_name = source.encode().ljust(64, b"\x00")[:64]
    # payload is NUM_CHANNELS (512) bytes — start code is already in dmp
    framing_len = len(dmp) + NUM_CHANNELS + 77
    sync_hi = (sync_address >> 8) & 0xFF
    sync_lo = sync_address & 0xFF
    framing = (
        struct.pack(">H", 0x7000 | framing_len)
        + struct.pack(">I", 0x00000002)
        + source_name
        + bytes([priority, sync_hi, sync_lo, sequence & 0xFF, 0x00])
        + struct.pack(">H", universe)
    )

    # Root Layer
    root_len = len(framing) + len(dmp) + NUM_CHANNELS + 38  # total packet size
    preamble = b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"
    root_vec = struct.pack(">I", 0x00000004)
    root = preamble + struct.pack(">H", 0x7000 | (root_len - 16)) + root_vec + cid

    return [root, framing, dmp, payload]


class SACNSender:
    """
    Sends a DMX universe over sACN (E1.31) via UDP multi-cast.
    Uses send-msg() + memory-view on Linux/macOS (zero-copy).
    Falls back to send-to() on Windows.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        universe: int = 1,
        source: str = "OLC DMX Engine",
        priority: int = 100,
        multicast: bool = True,
        ip: str = "127.0.0.1",
        sync_address: int = 0,
    ) -> None:
        self._universe = universe
        self._source = source
        self._priority = priority
        self._sequence = 0
        self._cid = uuid.uuid4().bytes
        self._sync_address = sync_address

        self._sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        try:
            self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        except OSError:
            pass
        self._sock.setblocking(False)

        if multicast:
            self._dest = (_sacn_multicast_ip(universe), SACN_PORT)
        else:
            self._dest = (ip, SACN_PORT)

    def send(self, dmx_universe: DMXUniverse) -> None:
        """Send one DMX frame."""
        self._sequence = (self._sequence + 1) & 0xFF
        buffers = _build_sacn_buffers(
            cid=self._cid,
            source=self._source,
            universe=self._universe,
            sequence=self._sequence,
            priority=self._priority,
            payload=dmx_universe.view,
            sync_address=self._sync_address,
        )
        if _HAS_SENDMSG and sys.platform != "win32":
            self._sock.sendmsg(buffers, [], 0, self._dest)
        else:
            self._sock.sendto(
                b"".join(b if isinstance(b, bytes) else bytes(b) for b in buffers),
                self._dest,
            )

    def close(self) -> None:
        """Close the underlying UDP socket."""
        self._sock.close()
