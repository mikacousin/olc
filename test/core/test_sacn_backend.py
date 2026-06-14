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
# pylint: disable=protected-access,wrong-spelling-in-comment,wrong-spelling-in-docstring
import asyncio
import contextlib
import socket
import struct
import threading
import typing
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from olc.core.backends.sacn import SacnManager
from olc.core.backends.sacn.merge import MergeMode, SacnMerger
from olc.core.backends.sacn.network import SacnNetwork, SacnProtocol
from olc.core.backends.sacn.protocol import (
    SacnDecodeError,
    SacnDiscoveryPacket,
    SacnPacket,
    SacnSyncPacket,
)
from olc.core.engine import CoreEngine
from olc.core.universe_config import Protocol, UniverseMap


@contextlib.contextmanager
def background_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Helper context manager to run an asyncio event loop in a background thread."""
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    ready.wait()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join()


class TestSacnProtocol:
    """Test suite for native sACN packet encoders, decoders, and errors."""

    def test_sacn_packet_encode_decode(self) -> None:
        """Verify sACN packet packing and unpacking logic."""
        cid = b"\x01" * 16
        dmx_data = [i % 256 for i in range(512)]

        packet = SacnPacket(
            cid=cid,
            source_name="OLC Source",
            universe=5,
            priority=150,
            sequence=42,
            data=dmx_data,
            stream_terminated=False,
            preview_data=True,
        )
        raw_bytes = packet.encode()

        # Check ACN Preamble
        assert raw_bytes[:16] == b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"

        # Check exact byte layout and fields based on Table 4-1 of ANSI E1.31-2025
        # Root Layer Flags & Length (octets 16-17)
        # Expected total packet length = 638 bytes. Root PDU length = 638 - 16 = 622.
        # Flags (0x7000) | 622 = 0x726e
        assert raw_bytes[16:18] == b"\x72\x6e"

        # Root Vector (octets 18-21)
        assert raw_bytes[18:22] == b"\x00\x00\x00\x04"

        # CID (octets 22-37)
        assert raw_bytes[22:38] == cid

        # Framing Layer Flags & Length (octets 38-39)
        # Expected Framing PDU length = 600. Flags (0x7000) | 600 = 0x7258
        assert raw_bytes[38:40] == b"\x72\x58"

        # Framing Vector (octets 40-43)
        assert raw_bytes[40:44] == b"\x00\x00\x00\x02"

        # Source Name (octets 44-107)
        assert raw_bytes[44:108] == b"OLC Source" + b"\x00" * 54

        # Priority (octet 108)
        assert raw_bytes[108] == 150

        # Synchronization Address (octets 109-110)
        assert raw_bytes[109:111] == b"\x00\x00"

        # Sequence Number (octet 111)
        assert raw_bytes[111] == 42

        # Options Flags (octet 112): preview data should set bit 7 (0x80)
        assert raw_bytes[112] == 0x80

        # Universe Number (octets 113-114)
        assert raw_bytes[113:115] == b"\x00\x05"

        # DMP Layer Flags & Length (octets 115-116)
        # Expected DMP PDU length = 513 + 10 = 523. Flags (0x7000) | 523 = 0x720b
        assert raw_bytes[115:117] == b"\x72\x0b"

        # DMP Vector (octet 117)
        assert raw_bytes[117] == 0x02

        # DMP Address Type & Data Type (octet 118) -> MUST BE 0xa1
        assert raw_bytes[118] == 0xA1

        # DMP First Property Address (octets 119-120)
        assert raw_bytes[119:121] == b"\x00\x00"

        # DMP Address Increment (octets 121-122)
        assert raw_bytes[121:123] == b"\x00\x01"

        # DMP Property Value Count (octets 123-124)
        assert raw_bytes[123:125] == b"\x02\x01"  # 513

        # DMX512-A START Code (octet 125)
        assert raw_bytes[125] == 0x00

        # DMX data slots (octets 126 to end)
        assert list(raw_bytes[126:]) == dmx_data

        # Decode packet
        decoded = SacnPacket()
        decoded.decode(raw_bytes)

        assert decoded.cid == cid
        assert decoded.source_name == "OLC Source"
        assert decoded.universe == 5
        assert decoded.priority == 150
        assert decoded.sequence == 42
        assert decoded.data == dmx_data
        assert decoded.stream_terminated is False
        assert decoded.preview_data is True

    def test_sacn_packet_decoding_exceptions(self) -> None:
        """Verify malformed packet layouts trigger SacnDecodeError."""
        packet = SacnPacket()

        # Packet too short
        with pytest.raises(SacnDecodeError):
            packet.decode(b"short")

        # Malformed preamble
        bad_preamble = b"BadACNPreamble!!" + b"\x00" * 120
        with pytest.raises(SacnDecodeError):
            packet.decode(bad_preamble)

        # Correct preamble but bad Root Vector
        bad_root_vec = (
            b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"
            + struct.pack(">H", 110)
            + struct.pack(">I", 0x99999999)  # Bad Vector
            + b"\x00" * 100
        )
        with pytest.raises(SacnDecodeError):
            packet.decode(bad_root_vec)

    def test_sacn_discovery_packet_encode_decode(self) -> None:
        """Verify sACN discovery packet packing and unpacking logic."""
        cid = b"\x03" * 16
        universes = [1, 2, 3, 10, 100, 512, 1000]

        packet = SacnDiscoveryPacket(
            cid=cid,
            source_name="OLC Discovery Source",
            universes=universes,
            page=2,
            last_page=5,
        )
        raw_bytes = packet.encode()

        # Check ACN Preamble
        assert raw_bytes[:16] == b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"

        # Decode packet
        decoded = SacnDiscoveryPacket()
        decoded.decode(raw_bytes)

        assert decoded.cid == cid
        assert decoded.source_name == "OLC Discovery Source"
        assert decoded.universes == universes
        assert decoded.page == 2
        assert decoded.last_page == 5

    def test_sacn_discovery_packet_decoding_exceptions(self) -> None:
        """Verify malformed sACN discovery packets raise SacnDecodeError."""
        packet = SacnDiscoveryPacket()

        # Packet too short
        with pytest.raises(SacnDecodeError):
            packet.decode(b"short")

        # Malformed preamble
        bad_preamble = b"BadACNPreamble!!" + b"\x00" * 120
        with pytest.raises(SacnDecodeError):
            packet.decode(bad_preamble)

        # Correct preamble but bad Root Vector (extended data)
        bad_root_vec = (
            b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"
            + struct.pack(">H", 110)
            + struct.pack(">I", 0x00000004)  # 0x04 instead of 0x08
            + b"\x00" * 100
        )
        with pytest.raises(SacnDecodeError):
            packet.decode(bad_root_vec)

        # Correct root vector but bad framing vector
        bad_framing_vec = (
            b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"
            + struct.pack(">H", 110)
            + struct.pack(">I", 0x00000008)  # Extended discovery vector
            + b"\x01" * 16  # CID
            + struct.pack(">H", 110)  # Framing length
            + struct.pack(">I", 0x00000001)  # Bad framing vector (0x01 instead of 0x02)
            + b"\x00" * 80
        )
        with pytest.raises(SacnDecodeError):
            packet.decode(bad_framing_vec)

    def test_sacn_sync_packet_encode_decode(self) -> None:
        """Verify sACN synchronization packet encode and decode logic."""
        cid = b"\x05" * 16
        packet = SacnSyncPacket(cid=cid, sequence=12, sync_address=2000)
        raw = packet.encode()

        # Check size and preambles
        assert len(raw) == 49
        assert raw[:16] == b"\x00\x10\x00\x00ASC-E1.17\x00\x00\x00"

        # Decode and verify
        decoded = SacnSyncPacket()
        decoded.decode(raw)
        assert decoded.cid == cid
        assert decoded.sequence == 12
        assert decoded.sync_address == 2000

    def test_sacn_packet_sync_address_field(self) -> None:
        """Verify standard data packets serialize and deserialize sync addresses."""
        packet = SacnPacket(sync_address=1500)
        raw = packet.encode()

        decoded = SacnPacket()
        decoded.decode(raw)
        assert decoded.sync_address == 1500


class TestSacnMerger:
    """Test suite for sACN priority merging, timeouts, and terminated flags."""

    def test_priority_merging(self) -> None:
        """Verify the highest priority source wins completely."""
        callback_mock = MagicMock()
        merger = SacnMerger(universe=2, callback=callback_mock)

        cid1 = b"\x01" * 16
        cid2 = b"\x02" * 16
        data1 = [10] * 512
        data2 = [20] * 512

        # Source 1 at priority 100
        merger.update(cid1, "Source 1", 100, data1)
        callback_mock.assert_called_with(2, data1)

        # Source 2 at priority 150 (wins completely)
        merger.update(cid2, "Source 2", 150, data2)
        callback_mock.assert_called_with(2, data2)

        # Update Source 1 at priority 100: no changes to output
        callback_mock.reset_mock()
        merger.update(cid1, "Source 1", 100, data1)
        callback_mock.assert_not_called()

    def test_equal_priority_htp_merge(self) -> None:
        """Verify equal highest priority sources HTP merge."""
        callback_mock = MagicMock()
        merger = SacnMerger(universe=2, mode=MergeMode.HTP, callback=callback_mock)

        cid1 = b"\x01" * 16
        cid2 = b"\x02" * 16
        data1 = [50] * 512
        data2 = [30] * 512
        data2[10] = 80

        merger.update(cid1, "S1", 100, data1)
        merger.update(cid2, "S2", 100, data2)

        expected = [50] * 512
        expected[10] = 80
        callback_mock.assert_called_with(2, expected)

    def test_equal_priority_ltp_merge(self) -> None:
        """Verify equal highest priority sources LTP merge."""
        callback_mock = MagicMock()
        merger = SacnMerger(universe=2, mode=MergeMode.LTP, callback=callback_mock)

        cid1 = b"\x01" * 16
        cid2 = b"\x02" * 16
        data1 = [10] * 512
        data2 = [20] * 512

        with patch("time.time", return_value=100.0):
            merger.update(cid1, "S1", 100, data1)
        with patch("time.time", return_value=101.0):
            merger.update(cid2, "S2", 100, data2)

        # S2 timestamp is newer: it wins completely
        callback_mock.assert_called_with(2, data2)

    def test_stream_terminated_option(self) -> None:
        """Verify stream terminated flag instantly purges a source."""
        callback_mock = MagicMock()
        merger = SacnMerger(universe=2, callback=callback_mock)

        cid1 = b"\x01" * 16
        cid2 = b"\x02" * 16
        data1 = [10] * 512
        data2 = [20] * 512

        merger.update(cid1, "S1", 150, data1)
        merger.update(cid2, "S2", 100, data2)

        assert cid1 in merger.sources

        # S1 terminated: instantly removed, S2 (priority 100) becomes active
        callback_mock.reset_mock()
        merger.update(cid1, "S1", 150, data1, stream_terminated=True)

        assert cid1 not in merger.sources
        callback_mock.assert_called_with(2, data2)

    def test_inactivity_timeout_purging(self) -> None:
        """Verify timed out sources are purged."""
        callback_mock = MagicMock()
        merger = SacnMerger(universe=2, timeout=2.0, callback=callback_mock)

        cid1 = b"\x01" * 16
        cid2 = b"\x02" * 16
        data1 = [10] * 512
        data2 = [20] * 512

        with patch("time.time", return_value=100.0):
            merger.update(cid1, "S1", 150, data1)
            merger.update(cid2, "S2", 100, data2)

        assert len(merger.sources) == 2

        # 3 seconds later: S2 updates, S1 is purged due to timeout
        with patch("time.time", return_value=103.0):
            merger.update(cid2, "S2", 100, data2)

        assert len(merger.sources) == 1
        assert cid1 not in merger.sources


class TestSacnNetwork:
    """Test suite for SacnNetwork socket setup, multicast, and reader loops."""

    def test_async_socket_options_and_multicast_membership(self) -> None:
        """Verify multicast memberships are requested when binding asynchronously."""
        manager_mock = MagicMock()
        loop = asyncio.new_event_loop()
        manager_mock.loop = loop
        net = SacnNetwork(manager_mock)
        net.joined_universes.add(3)

        async def run_test() -> None:
            with (
                patch(
                    "olc.core.backends.sacn.network.socket.socket"
                ) as mock_sock_class,
                patch(
                    "olc.core.backends.sacn.network.get_local_ips",
                    return_value=["0.0.0.0", "127.0.0.1"],
                ),
            ):
                mock_sock = MagicMock()
                mock_sock_class.return_value = mock_sock

                # Mock loop datagram endpoint creation
                mock_loop = typing.cast(typing.Any, loop)
                mock_loop.create_datagram_endpoint = MagicMock(
                    return_value=asyncio.Future()
                )
                mock_loop.create_datagram_endpoint.return_value.set_result(
                    (MagicMock(), MagicMock())
                )

                await net._async_start()

                # Verify socket options
                mock_sock.setsockopt.assert_any_call(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                )
                # Verify IGMP membership
                mock_sock.setsockopt.assert_any_call(
                    socket.IPPROTO_IP,
                    socket.IP_ADD_MEMBERSHIP,
                    socket.inet_aton("239.255.0.3") + socket.inet_aton("0.0.0.0"),
                )
                assert net.sock is mock_sock

        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()

    def test_get_join_ips_filtering(self) -> None:
        """Verify that _get_join_ips correctly filters redundant interfaces."""
        manager_mock = MagicMock()
        net = SacnNetwork(manager_mock)

        # Scenario 1: Only loopback and 0.0.0.0 (e.g. offline)
        #                                                  -> should fallback to 0.0.0.0
        with patch(
            "olc.core.backends.sacn.network.get_local_ips",
            return_value=["0.0.0.0", "127.0.0.1"],
        ):
            ips = net._get_join_ips()
            assert ips == ["0.0.0.0"]

        # Scenario 2: Physical interface present
        #                                       -> should return only physical interface
        with patch(
            "olc.core.backends.sacn.network.get_local_ips",
            return_value=["0.0.0.0", "127.0.0.1", "192.168.1.10"],
        ):
            ips = net._get_join_ips()
            assert ips == ["192.168.1.10"]

        # Scenario 3: Multiple physical interfaces present
        #                                       -> should return all physical interfaces
        with patch(
            "olc.core.backends.sacn.network.get_local_ips",
            return_value=["0.0.0.0", "127.0.0.1", "192.168.1.10", "10.0.0.5"],
        ):
            ips = net._get_join_ips()
            assert sorted(ips) == ["10.0.0.5", "192.168.1.10"]

    def test_socket_loop_packet_dispatch(self) -> None:
        """Verify DatagramProtocol correctly forwards packet buffers."""
        manager_mock = MagicMock()
        protocol = SacnProtocol(manager_mock)
        data = b"dummy_sacn_bytes"
        addr = ("192.168.1.10", 5568)

        protocol.datagram_received(data, addr)
        manager_mock.read_packet.assert_called_once_with(data, addr)


class TestSacnManager:
    """Test suite for sACN Manager coordinations and sending integration."""

    def test_manager_initialization(self) -> None:
        """Verify manager universe mapping and lifecycles."""
        umap = UniverseMap(8)
        umap.enable_protocol(2, Protocol.SACN)

        manager = SacnManager(umap)
        assert 2 in manager.universes

        # Senders instantiated
        assert 2 in manager.senders

        manager.stop()

    def test_manager_dmx_sending(self) -> None:
        """Verify DMX transmission calls the correct sACN senders."""
        umap = UniverseMap(4)
        umap.enable_protocol(1, Protocol.SACN)

        manager = SacnManager(umap)
        mock_sender = MagicMock()
        manager.senders[1] = mock_sender

        dmx_data = [255] * 512
        manager.send(1, dmx_data, priority=180)

        # Verify correct priority was set and sender triggered
        assert mock_sender._priority == 180
        mock_sender.send.assert_called_once()

        manager.stop()

    def test_manager_discovery_lifecycle(self) -> None:
        """Verify discovery loop and socket are properly managed during start/stop."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.SACN)

        with background_loop() as loop:
            with patch("olc.core.backends.sacn.SacnNetwork"):
                manager = SacnManager(umap, loop=loop)

                with patch("socket.socket") as mock_socket_class:
                    mock_sock = MagicMock()
                    mock_socket_class.return_value = mock_sock

                    manager.start()

                    # Check socket initialized
                    mock_socket_class.assert_called_once_with(
                        socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
                    )
                    mock_sock.setsockopt.assert_any_call(
                        socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20
                    )

                    # Verify initial discovery packet was sent
                    mock_sock.sendto.assert_called_once()
                    sent_data, sent_addr = mock_sock.sendto.call_args[0]
                    assert sent_addr == ("239.255.250.214", 5568)

                    decoded_packet = SacnDiscoveryPacket()
                    decoded_packet.decode(sent_data)
                    assert decoded_packet.universes == [1]

                    # Verify discovery task was created
                    assert manager.discovery_task is not None
                    assert not manager.discovery_task.done()

                    # Verify clean stop
                    manager.stop()
                    assert (
                        manager.discovery_task is None
                        or manager.discovery_task.cancelled()
                    )
                    mock_sock.close.assert_called_once()

    def test_manager_discovery_immediate_broadcast(self) -> None:
        """Verify immediate discovery broadcasts when senders are dynamically
        changed.
        """
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.SACN)

        with background_loop() as loop:
            with patch("olc.core.backends.sacn.SacnNetwork"):
                manager = SacnManager(umap, loop=loop)

                with patch("socket.socket") as mock_socket_class:
                    mock_sock = MagicMock()
                    mock_socket_class.return_value = mock_sock

                    manager.start()
                    mock_sock.sendto.reset_mock()

                    # Add a sender dynamically
                    mock_sender = MagicMock()
                    mock_sender._source = "OLC DMX Engine"
                    manager.add_sender(3, mock_sender)

                    # Verify immediate broadcast triggered
                    assert mock_sock.sendto.call_count == 1
                    sent_data, _ = mock_sock.sendto.call_args[0]
                    decoded = SacnDiscoveryPacket()
                    decoded.decode(sent_data)
                    assert decoded.universes == [1, 3]

                    mock_sock.sendto.reset_mock()

                    # Remove a sender dynamically
                    manager.del_sender(1)

                    # Verify immediate broadcast triggered
                    assert mock_sock.sendto.call_count == 1
                    sent_data, _ = mock_sock.sendto.call_args[0]
                    decoded = SacnDiscoveryPacket()
                    decoded.decode(sent_data)
                    assert decoded.universes == [3]

                    manager.stop()

    def test_manager_discovery_pagination(self) -> None:
        """Verify sACN universe list pagination when universe count exceeds 512."""
        umap = UniverseMap(601)
        # Configure universes 1 to 600
        for i in range(1, 601):
            umap.enable_protocol(i, Protocol.SACN)

        with background_loop() as loop:
            with patch("olc.core.backends.sacn.SacnNetwork"):
                manager = SacnManager(umap, loop=loop)

                with patch("socket.socket") as mock_socket_class:
                    mock_sock = MagicMock()
                    mock_socket_class.return_value = mock_sock

                    manager.start()

                    # Should have sent 2 discovery packets due to 600 (>512) universes
                    assert mock_sock.sendto.call_count == 2

                    # Verify first page
                    call1_data = mock_sock.sendto.call_args_list[0][0][0]
                    decoded1 = SacnDiscoveryPacket()
                    decoded1.decode(call1_data)
                    assert decoded1.page == 0
                    assert decoded1.last_page == 1
                    assert len(decoded1.universes) == 512
                    assert decoded1.universes == list(range(1, 513))

                    # Verify second page
                    call2_data = mock_sock.sendto.call_args_list[1][0][0]
                    decoded2 = SacnDiscoveryPacket()
                    decoded2.decode(call2_data)
                    assert decoded2.page == 1
                    assert decoded2.last_page == 1
                    assert len(decoded2.universes) == 88
                    assert decoded2.universes == list(range(513, 601))

                    manager.stop()

    def test_manager_sync_hold_and_release(self) -> None:
        """Verify DMX packets are held on sync and released by SacnSyncPacket."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.SACN)
        # Configure synchronization universe 2000 for universe 1
        umap[1].sacn.sync_address = 2000

        with patch("olc.core.backends.sacn.SacnNetwork"):
            manager = SacnManager(umap)

            # Mock on_dmx_received callback
            callback_mock = MagicMock()
            manager.on_dmx_received = callback_mock

            # Receive standard sACN packet WITH sync_address = 2000
            cid = b"\x09" * 16
            data = [200] * 512
            packet = SacnPacket(
                cid=cid,
                source_name="Sync Source",
                universe=1,
                data=data,
                sync_address=2000,
            )
            manager.read_packet(packet.encode(), ("192.168.1.5", 5568))

            # Verify that the packet was NOT merged immediately
            callback_mock.assert_not_called()
            assert cid in manager.pending_dmx
            assert manager.pending_dmx[cid][1] == data

            # Receive sACN Sync Packet for synchronization universe 2000
            sync_packet = SacnSyncPacket(cid=cid, sync_address=2000)
            manager.read_packet(sync_packet.encode(), ("192.168.1.5", 5568))

            # Verify that the packet was merged and released instantly!
            callback_mock.assert_called_once_with(1, data)
            assert cid not in manager.pending_dmx

    def test_manager_sync_timeout_fallback(self) -> None:
        """Verify DMX packets are committed automatically after 100ms timeout."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.SACN)
        umap[1].sacn.sync_address = 2000

        with patch("olc.core.backends.sacn.SacnNetwork"):
            manager = SacnManager(umap)

            callback_mock = MagicMock()
            manager.on_dmx_received = callback_mock

            cid = b"\x09" * 16
            data = [150] * 512
            packet = SacnPacket(
                cid=cid,
                universe=1,
                data=data,
                sync_address=2000,
            )

            # Fast forward time to test fallback
            with patch("time.time", return_value=100.0):
                manager.read_packet(packet.encode(), ("192.168.1.5", 5568))
                callback_mock.assert_not_called()

            # Process again after 150ms (>100ms timeout)
            with patch("time.time", return_value=100.15):
                # Trigger callback check on any incoming packet or direct call
                manager._check_pending_timeouts()

            # Verify that it committed automatically
            callback_mock.assert_called_once_with(1, data)

    def test_engine_sync_packet_transmission(self) -> None:
        """Verify that CoreEngine calls send_sync when universes have sync addresses."""
        umap = UniverseMap(3)
        umap.enable_protocol(1, Protocol.SACN)
        umap[1].sacn.sync_address = 2000

        with patch("olc.core.backends.sacn.SacnNetwork"):
            # CoreEngine initializes its own SacnManager if Protocol.SACN is in map
            engine = CoreEngine(umap)

            # Mock SacnManager.send_sync
            mock_send_sync = MagicMock()
            typing.cast(typing.Any, engine._sacn_manager).send_sync = mock_send_sync

            # Mock the sender's send method
            for sender in engine._slots[1].senders:
                typing.cast(typing.Any, sender).send = MagicMock()

            # Execute a single tick of the loop
            engine._send_all()

            # Verify SacnManager.send_sync was called with universe 2000
            mock_send_sync.assert_called_once_with(2000)

    def test_manager_discovery_receiving(self) -> None:
        """Verify that SacnManager receives and decodes discovery packets, and prunes
        expired ones.
        """
        umap = UniverseMap(3)
        umap.enable_protocol(1, Protocol.SACN)

        with patch("olc.core.backends.sacn.SacnNetwork"):
            manager = SacnManager(umap)

            # Create a mock discovery packet
            cid = b"\x08" * 16
            packet = SacnDiscoveryPacket(
                cid=cid,
                source_name="Test Source",
                universes=[1, 2, 5],
                page=0,
                last_page=0,
            )

            # Receive discovery packet
            with patch("time.time", return_value=100.0):
                manager.read_packet(packet.encode(), ("192.168.1.10", 5568))

            # Verify registered source
            assert cid in manager.discovered_sources
            src = manager.discovered_sources[cid]
            assert src["name"] == "Test Source"
            assert src["ip"] == "192.168.1.10"
            assert src["universes"] == {1, 2, 5}
            assert src["last_seen"] == 100.0

            # Verify pruning: time is 120.0 (not yet expired, < 25s)
            with patch("time.time", return_value=120.0):
                manager._check_pending_timeouts()
            assert cid in manager.discovered_sources

            # Verify pruning: time is 126.0 (>25s timeout, expired)
            with patch("time.time", return_value=126.0):
                manager._check_pending_timeouts()
            assert cid not in manager.discovered_sources
