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
import struct
import uuid

PORT = 5568
PREAMBLE = b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"

# Vector constants in compliance with ANSI E1.31-2025
VECTOR_ROOT_E131_DATA = 0x00000004
VECTOR_ROOT_E131_EXTENDED = 0x00000008

VECTOR_E131_DATA_PACKET = 0x00000002
VECTOR_E131_EXTENDED_SYNCHRONIZATION = 0x00000001
VECTOR_E131_EXTENDED_DISCOVERY = 0x00000002

VECTOR_UNIVERSE_DISCOVERY_UNIVERSE_LIST = 0x00000001
DISCOVERY_UNIVERSE = 64214


class SacnDecodeError(Exception):
    """Exception raised when an sACN packet is corrupted or malformed."""


# pylint: disable=too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-instance-attributes
class SacnPacket:
    """Represents a standard sACN (E1.31-2016) Data Packet."""

    def __init__(
        self,
        cid: bytes = b"",
        source_name: str = "OLC DMX Engine",
        universe: int = 1,
        priority: int = 100,
        sequence: int = 0,
        data: list[int] | None = None,
        stream_terminated: bool = False,
        preview_data: bool = False,
        sync_address: int = 0,
    ) -> None:
        self.cid = cid if cid else uuid.uuid4().bytes
        self.source_name = source_name
        self.universe = universe
        self.priority = priority
        self.sequence = sequence
        self.data = data if data is not None else [0] * 512
        self.stream_terminated = stream_terminated
        self.preview_data = preview_data
        self.sync_address = sync_address

    def encode(self) -> bytes:
        """Encode the sACN packet into raw bytes."""
        dmx_length = len(self.data) + 1  # Start code + DMX slots

        # 1. DMP Layer (10 bytes header + DMX slots + 1 start code)
        dmp = (
            struct.pack(
                ">HBBHHH",
                0x7000 | (dmx_length + 10),  # PDU length from octet 115 to end (§7.1)
                0x02,  # DMP Vector (VECTOR_DMP_SET_PROPERTY)
                0xA1,  # Address Type & Data Type
                0x0000,  # First Property Address
                0x0001,  # Address Increment
                dmx_length,  # Property Value Count
            )
            + b"\x00"
        )  # DMX Start Code (0x00)

        # 2. Framing Layer (77 bytes including flags/length)
        source_name_bytes = self.source_name.encode("utf-8").ljust(64, b"\x00")[:64]
        framing_len = len(dmp) + len(self.data) + 77
        options = 0
        if self.stream_terminated:
            options |= 0b01000000
        if self.preview_data:
            options |= 0b10000000

        # Pack sync address on 2 big-endian bytes
        sync_hi = (self.sync_address >> 8) & 0xFF
        sync_lo = self.sync_address & 0xFF

        framing = (
            struct.pack(
                ">H",
                0x7000 | framing_len,  # PDU length from octet 38 to end (§6.1)
            )
            + struct.pack(">I", 0x00000002)  # Framing Vector
            + source_name_bytes
            + bytes([self.priority, sync_hi, sync_lo, self.sequence & 0xFF, options])
            + struct.pack(">H", self.universe)
        )

        # 3. Root Layer (38 bytes)
        root_len = len(framing) + len(dmp) + len(self.data) + 38
        root = (
            PREAMBLE
            + struct.pack(
                ">H",
                0x7000 | (root_len - 16),  # PDU length from octet 16 to end (§5.4)
            )
            + struct.pack(">I", 0x00000004)  # Root Vector (VECTOR_ROOT_E131_DATA)
            + self.cid
        )

        return root + framing + dmp + bytes(self.data)

    def decode(self, packet: bytes) -> None:
        """Decode a raw sACN packet into properties."""
        if len(packet) < 126:
            raise SacnDecodeError(
                f"Packet too short to be sACN: {len(packet)} bytes (min 126)"
            )

        # Validate Root Preamble
        if packet[:16] != PREAMBLE:
            raise SacnDecodeError("Invalid ACN Root Preamble magic")

        # Validate Root Vector
        root_vec = struct.unpack(">I", packet[18:22])[0]
        if root_vec != 0x00000004:
            raise SacnDecodeError(f"Invalid sACN Root Vector: {root_vec}")

        self.cid = packet[22:38]

        # Validate Framing Vector
        framing_vec = struct.unpack(">I", packet[40:44])[0]
        if framing_vec != 0x00000002:
            raise SacnDecodeError(f"Invalid sACN Framing Vector: {framing_vec}")

        # Extract Source Name
        source_bytes = packet[44:108]
        decoded_name = source_bytes.decode("utf-8", errors="ignore")
        self.source_name = decoded_name.split("\x00", 1)[0]

        self.priority = packet[108]
        if not 0 <= self.priority <= 200:
            raise SacnDecodeError(f"Priority out of range: {self.priority}")

        self.sync_address = struct.unpack(">H", packet[109:111])[0]
        self.sequence = packet[111]

        # Extract Options Flags
        options = packet[112]
        self.stream_terminated = bool(options & 0b01000000)
        self.preview_data = bool(options & 0b10000000)

        self.universe = struct.unpack(">H", packet[113:115])[0]

        # Validate DMP Vector
        dmp_vec = packet[117]
        if dmp_vec != 0x02:
            raise SacnDecodeError(f"Invalid DMP Vector: {dmp_vec}")

        # DMP value count (First Property address increment etc. is at 118-122)
        prop_val_count = struct.unpack(">H", packet[123:125])[0]

        start_code = packet[125]
        if start_code != 0x00:
            raise SacnDecodeError(f"Unsupported DMX Start Code: {start_code}")

        # DMX data length is prop_val_count - 1 (since it includes start code)
        dmx_len = prop_val_count - 1
        expected_total = 126 + dmx_len
        if len(packet) < expected_total:
            raise SacnDecodeError(
                f"Packet truncated: got {len(packet)} bytes, expected {expected_total}"
            )

        self.data = list(packet[126 : 126 + dmx_len])


# pylint: disable=too-many-instance-attributes
class SacnDiscoveryPacket:
    """Represents a standard sACN (E1.31-2016/2025) Universe Discovery Packet."""

    def __init__(
        self,
        cid: bytes = b"",
        source_name: str = "OLC DMX Engine",
        universes: list[int] | None = None,
        page: int = 0,
        last_page: int = 0,
    ) -> None:
        self.cid = cid if cid else uuid.uuid4().bytes
        self.source_name = source_name
        self.universes = sorted(universes) if universes is not None else []
        self.page = page
        self.last_page = last_page

    def encode(self) -> bytes:
        """Encode the sACN Universe Discovery packet into raw bytes."""
        num_univs = len(self.universes)
        discovery_length = 8 + 2 * num_univs

        # List of universes packed in big-endian 16-bit
        univs_bytes = b"".join(struct.pack(">H", u) for u in self.universes)

        discovery = (
            struct.pack(
                ">H",
                0x7000 | discovery_length,  # PDU length from octet 112 to end (§8.1)
            )
            + struct.pack(">I", VECTOR_UNIVERSE_DISCOVERY_UNIVERSE_LIST)
            + bytes([self.page, self.last_page])
            + univs_bytes
        )

        # Framing Layer (74 bytes including flags/length)
        source_name_bytes = self.source_name.encode("utf-8").ljust(64, b"\x00")[:64]
        framing_len = len(discovery) + 74

        framing = (
            struct.pack(
                ">H",
                0x7000 | framing_len,  # PDU length from octet 38 to end (§6.1)
            )
            + struct.pack(">I", VECTOR_E131_EXTENDED_DISCOVERY)
            + source_name_bytes
            + struct.pack(">I", 0)  # Reserved (4 bytes)
        )

        # Root Layer (38 bytes)
        root_len = len(framing) + len(discovery) + 38
        root = (
            PREAMBLE
            + struct.pack(
                ">H",
                0x7000 | (root_len - 16),  # PDU length from octet 16 to end (§5.4)
            )
            + struct.pack(">I", VECTOR_ROOT_E131_EXTENDED)
            + self.cid
        )

        return root + framing + discovery

    def decode(self, packet: bytes) -> None:
        """Decode a raw sACN Universe Discovery packet into properties."""
        if len(packet) < 120:
            raise SacnDecodeError(
                f"Packet too short to be sACN Discovery: {len(packet)} bytes (min 120)"
            )

        # Validate Root Preamble
        if packet[:16] != PREAMBLE:
            raise SacnDecodeError("Invalid ACN Root Preamble magic")

        # Validate Root Vector
        root_vec = struct.unpack(">I", packet[18:22])[0]
        if root_vec != VECTOR_ROOT_E131_EXTENDED:
            raise SacnDecodeError(f"Invalid sACN Root Vector for Discovery: {root_vec}")

        self.cid = packet[22:38]

        # Validate Framing Vector
        framing_vec = struct.unpack(">I", packet[40:44])[0]
        if framing_vec != VECTOR_E131_EXTENDED_DISCOVERY:
            raise SacnDecodeError(
                f"Invalid sACN Framing Vector for Discovery: {framing_vec}"
            )

        # Extract Source Name
        source_bytes = packet[44:108]
        decoded_name = source_bytes.decode("utf-8", errors="ignore")
        self.source_name = decoded_name.split("\x00", 1)[0]

        # Validate Discovery Layer Vector
        disc_vec = struct.unpack(">I", packet[114:118])[0]
        if disc_vec != VECTOR_UNIVERSE_DISCOVERY_UNIVERSE_LIST:
            raise SacnDecodeError(f"Invalid Discovery Layer Vector: {disc_vec}")

        self.page = packet[118]
        self.last_page = packet[119]

        # List of universes starts at 120
        rem = len(packet) - 120
        if rem % 2 != 0:
            raise SacnDecodeError(
                f"Discovery universe list truncated: odd remainder {rem}"
            )

        num_univs = rem // 2
        self.universes = []
        for i in range(num_univs):
            offset = 120 + i * 2
            u = struct.unpack(">H", packet[offset : offset + 2])[0]
            self.universes.append(u)


# pylint: disable=too-many-instance-attributes
class SacnSyncPacket:
    """Represents a standard sACN (E1.31-2016) Synchronization Packet."""

    def __init__(
        self,
        cid: bytes = b"",
        sequence: int = 0,
        sync_address: int = 0,
    ) -> None:
        self.cid = cid if cid else uuid.uuid4().bytes
        self.sequence = sequence
        self.sync_address = sync_address

    def encode(self) -> bytes:
        """Encode the sACN Synchronization packet into raw bytes."""
        # Framing Layer (11 bytes including flags/length)
        framing = (
            struct.pack(">H", 0x7000 | 11)
            + struct.pack(">I", VECTOR_E131_EXTENDED_SYNCHRONIZATION)
            + bytes([self.sequence & 0xFF])
            + struct.pack(">H", self.sync_address)
            + b"\x00\x00"  # Reserved (2 bytes)
        )

        # Root Layer (38 bytes)
        root_len = len(framing) + 38
        root = (
            PREAMBLE
            + struct.pack(
                ">H",
                0x7000 | (root_len - 16),  # PDU length from octet 16 to end (§5.4)
            )
            + struct.pack(">I", VECTOR_ROOT_E131_EXTENDED)
            + self.cid
        )

        return root + framing

    def decode(self, packet: bytes) -> None:
        """Decode a raw sACN Synchronization packet into properties."""
        if len(packet) < 49:
            raise SacnDecodeError(
                f"Packet too short to be sACN Sync: {len(packet)} bytes (min 49)"
            )

        # Validate Root Preamble
        if packet[:16] != PREAMBLE:
            raise SacnDecodeError("Invalid ACN Root Preamble magic")

        # Validate Root Vector
        root_vec = struct.unpack(">I", packet[18:22])[0]
        if root_vec != VECTOR_ROOT_E131_EXTENDED:
            raise SacnDecodeError(f"Invalid sACN Root Vector for Sync: {root_vec}")

        self.cid = packet[22:38]

        # Validate Framing Vector
        framing_vec = struct.unpack(">I", packet[40:44])[0]
        if framing_vec != VECTOR_E131_EXTENDED_SYNCHRONIZATION:
            raise SacnDecodeError(
                f"Invalid sACN Framing Vector for Sync: {framing_vec}"
            )

        self.sequence = packet[44]
        self.sync_address = struct.unpack(">H", packet[45:47])[0]
