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
# pylint: disable=protected-access,unexpected-keyword-arg,import-outside-toplevel,wrong-spelling-in-comment
import asyncio
import ipaddress
import socket
import struct
import typing
from unittest.mock import MagicMock, patch

import pytest
from olc.core.backends.artnet import ArtNetManager
from olc.core.backends.artnet.artnet import Discovery, Listeners, Sender
from olc.core.backends.artnet.merge import ArtDmxMerger, MergeMode
from olc.core.backends.artnet.network import Network
from olc.core.backends.artnet.protocol import (
    ArtDmx,
    ArtNetDecodeError,
    ArtPoll,
    ArtPollReply,
    PacketTracker,
    PriorityCodes,
    StyleCodes,
)
from olc.core.universe_config import Protocol, UniverseMap


class TestArtNetProtocol:
    """Test suite for the Art-Net packet encoders, decoders, and trackers."""

    def test_artdmx_encode_decode(self) -> None:
        """Verify ArtDmx pack and unpack logic."""
        dmx = ArtDmx()
        payload = bytes([i % 256 for i in range(512)])
        packet = dmx.encode(universe=3, data=payload)

        # Header prefix matches "Art-Net\x00" and OpDmx opcode
        assert packet[:8] == b"Art-Net\x00"
        assert packet[8:10] == struct.pack("<H", 0x5000)

        # Decode
        decoded = ArtDmx()
        decoded.decode(packet)
        assert decoded.universe == 3
        assert decoded.data == list(payload)

    def test_artdmx_invalid_decoding(self) -> None:
        """Verify malformed payload raises decode error."""
        dmx = ArtDmx()

        # Packet too short
        with pytest.raises(ArtNetDecodeError):
            dmx.decode(b"short")

        # Bad header magic
        bad_header = b"BadMagic\x00" + struct.pack("<H", 0x5000) + b"\x00" * 30
        with pytest.raises(ArtNetDecodeError):
            dmx.decode(bad_header)

    def test_packet_tracker(self) -> None:
        """Verify out-of-order, duplicate, and loss checks in PacketTracker."""
        tracker = PacketTracker(alert_threshold=10.0)

        # First packet is accepted
        assert tracker.process_packet(1) is True

        # Next sequential is accepted
        assert tracker.process_packet(2) is True

        # Duplicate packet is ignored/dropped
        assert tracker.process_packet(2) is False

        # Older packet is ignored/dropped
        assert tracker.process_packet(1) is False

        # Sequential sequence wrapping is handled gracefully
        tracker.previous_seq = 254
        assert tracker.process_packet(255) is True
        assert tracker.process_packet(1) is True

    def test_artpoll_encode_decode(self) -> None:
        """Verify ArtPoll pack and unpack logic."""
        poll = ArtPoll()
        packet = poll.encode()

        assert packet[:8] == b"Art-Net\x00"
        assert packet[8:10] == struct.pack("<H", 0x2000)

        decoded = ArtPoll()
        decoded.decode(packet)
        assert decoded.diag_priority == PriorityCodes.DP_LOW

    def test_artpollreply_encode_decode(self) -> None:
        """Verify ArtPollReply pack and unpack logic."""
        reply = ArtPollReply(universes=[0, 1, 2])
        mac = (0x00, 0x11, 0x22, 0x33, 0x44, 0x55)
        packet = reply.encode(ip="192.168.1.10", mac=mac)

        assert packet[:8] == b"Art-Net\x00"
        assert packet[8:10] == struct.pack("<H", 0x2100)

        decoded = ArtPollReply(universes=[0, 1, 2])
        decoded.decode(packet)

        # Verify parsed properties
        assert decoded.style == StyleCodes.ST_CONTROLLER
        assert decoded.mac == mac
        assert decoded.port_name.strip("\x00") == "olc"

    def test_listeners_discards_local_ips(self) -> None:
        """Verify Listeners discards ArtDmx packets from local IP addresses."""
        callback_mock = MagicMock()
        listeners = Listeners(universes=[1], callback=callback_mock)

        # Ensure local_ips contains "127.0.0.1" and "192.168.1.1"
        listeners.local_ips = {"127.0.0.1", "192.168.1.1"}

        dmx = ArtDmx()
        payload = bytes([i % 256 for i in range(512)])
        packet = dmx.encode(universe=1, data=payload)

        # 1. Packet from a local IP (e.g. 127.0.0.1) should be ignored
        listeners.on_artdmx(packet, ("127.0.0.1", 6454))
        callback_mock.assert_not_called()

        # 2. Packet from another local IP (e.g. 192.168.1.1) should be ignored
        listeners.on_artdmx(packet, ("192.168.1.1", 6454))
        callback_mock.assert_not_called()

        # 3. Packet from a non-local IP (e.g. 192.168.1.50) should be processed
        listeners.on_artdmx(packet, ("192.168.1.50", 6454))
        callback_mock.assert_called_once_with(1, list(payload))


class TestArtNetMerger:
    """Test suite for DMX merging modes and inactive source cleanup."""

    def test_htp_merge(self) -> None:
        """Verify Highest Takes Precedence logic with 2 sources."""
        merger = ArtDmxMerger(mode=MergeMode.HTP)
        callback_mock = MagicMock()
        merger.callback = callback_mock

        source1_data = [100] * 512
        source2_data = [50] * 512
        source2_data[10] = 200

        # Update source 1
        merger.update(universe=1, source_ip="192.168.1.1", data=source1_data)
        callback_mock.assert_called_with(1, source1_data)

        # Update source 2 (merging active)
        merger.update(universe=1, source_ip="192.168.1.2", data=source2_data)
        expected = [100] * 512
        expected[10] = 200
        callback_mock.assert_called_with(1, expected)

    def test_ltp_merge(self) -> None:
        """Verify Latest Takes Precedence logic with 2 sources."""
        merger = ArtDmxMerger(mode=MergeMode.LTP)
        callback_mock = MagicMock()
        merger.callback = callback_mock

        s1_data = [10] * 512
        s2_data = [20] * 512

        with patch("time.time", return_value=100.0):
            merger.update(universe=1, source_ip="192.168.1.1", data=s1_data)
        with patch("time.time", return_value=101.0):
            merger.update(universe=1, source_ip="192.168.1.2", data=s2_data)

        # Source 2 timestamp is newer: it wins completely
        callback_mock.assert_called_with(1, s2_data)

    def test_three_sources_limit(self) -> None:
        """Verify that exactly 2 sources are allowed and a 3rd source is dropped."""
        merger = ArtDmxMerger()
        callback_mock = MagicMock()
        merger.callback = callback_mock

        # Add two active sources
        merger.update(universe=1, source_ip="192.168.1.1", data=[10] * 512)
        merger.update(universe=1, source_ip="192.168.1.2", data=[20] * 512)

        callback_mock.reset_mock()

        # Attempt to add a third source
        merger.update(universe=1, source_ip="192.168.1.3", data=[30] * 512)

        # Third source was completely ignored: callback not triggered with its data
        callback_mock.assert_not_called()

    def test_cleanup_timeouts(self) -> None:
        """Verify inactive sources are removed after timeout threshold."""
        merger = ArtDmxMerger(timeout=4.0)

        with patch("time.time", return_value=100.0):
            merger.update(universe=1, source_ip="192.168.1.1", data=[10] * 512)
            merger.update(universe=1, source_ip="192.168.1.2", data=[20] * 512)
        assert len(merger.buffers[1]) == 2

        # 5 seconds later: source 1 updates, source 2 is timed out and removed
        with patch("time.time", return_value=105.0):
            merger.update(universe=1, source_ip="192.168.1.1", data=[15] * 512)

        assert len(merger.buffers[1]) == 1
        assert "192.168.1.2" not in merger.buffers[1]


class TestArtNetDiscovery:
    """Test suite for node and controller discovery registries and callbacks."""

    def test_node_addition_and_removal(self) -> None:
        """Verify nodes are registered upon ArtPollReply reception."""
        net_mock = MagicMock()
        senders: dict[int, Sender] = {1: Sender(1, None)}
        notify_mock = MagicMock()

        discovery = Discovery(
            net_mock, universes=[1], senders=senders, notify=notify_mock
        )

        # Create dummy reply
        reply = ArtPollReply(universes=[1])
        reply.ip = int(ipaddress.IPv4Address("192.168.1.50"))
        reply.mac = (0x00, 0x11, 0x22, 0x33, 0x44, 0x55)
        reply.port_types = (0x80, 0x00, 0x00, 0x00)  # Output DMX
        reply.sw_out = (1, 0, 0, 0)
        reply.style = StyleCodes.ST_NODE

        # Packet reply arrives
        discovery._handle_node_reply(reply)

        uid = (reply.mac, reply.bind_index, "192.168.1.50")
        assert uid in discovery.nodes
        assert discovery.nodes[uid].ip == "192.168.1.50"
        assert uid in senders[1].nodes

        # Del-node notification triggered
        notify_mock.assert_called_with("add-node", "192.168.1.50", 1)

    def test_node_reply_with_zero_ports(self) -> None:
        """Verify that nodes with num_ports=0 are handled cleanly without adding
        active ports.
        """
        net_mock = MagicMock()
        senders: dict[int, Sender] = {1: Sender(1, None)}
        notify_mock = MagicMock()

        discovery = Discovery(
            net_mock, universes=[1], senders=senders, notify=notify_mock
        )

        # Create dummy reply with num_ports=0
        reply = ArtPollReply(universes=[1])
        reply.ip = int(ipaddress.IPv4Address("192.168.1.50"))
        reply.mac = (0x00, 0x11, 0x22, 0x33, 0x44, 0x55)
        reply.port_types = (0x80, 0x80, 0x80, 0x80)  # Supposedly Output DMX
        reply.sw_out = (1, 2, 3, 4)
        reply.style = StyleCodes.ST_NODE
        reply.num_ports = 0  # 0 active ports!

        discovery._handle_node_reply(reply)

        uid = (reply.mac, reply.bind_index, "192.168.1.50")
        assert uid in discovery.nodes
        assert discovery.nodes[uid].num_ports == 0
        assert len(discovery.nodes[uid].output_universes) == 0
        assert uid not in senders[1].nodes
        notify_mock.assert_not_called()

    def test_node_inactivity_purging(self) -> None:
        """Verify inactive nodes are purged after 8 seconds of silence."""
        net_mock = MagicMock()
        senders: dict[int, Sender] = {1: Sender(1, None)}
        notify_mock = MagicMock()

        discovery = Discovery(
            net_mock, universes=[1], senders=senders, notify=notify_mock
        )

        reply = ArtPollReply(universes=[1])
        reply.ip = int(ipaddress.IPv4Address("192.168.1.50"))
        reply.mac = (0x00, 0x11, 0x22, 0x33, 0x44, 0x55)
        reply.port_types = (0x80, 0x00, 0x00, 0x00)
        reply.sw_out = (1, 0, 0, 0)
        reply.style = StyleCodes.ST_NODE

        # Register node at time=100
        with patch("time.time", return_value=100.0):
            discovery._handle_node_reply(reply)

        assert len(discovery.nodes) == 1

        # Check alive at time=105 (no purge)
        with patch("time.time", return_value=105.0):
            discovery.send_artpoll()
        assert len(discovery.nodes) == 1

        # Time passes (time=110), node is timed out
        with patch("time.time", return_value=110.0):
            discovery.send_artpoll()

        assert len(discovery.nodes) == 0
        notify_mock.assert_any_call("del-node", "192.168.1.50")


class TestArtNetNetwork:
    """Test suite for Network sockets, listener loops, and interface detection."""

    def test_network_socket_binding(self) -> None:
        """Verify socket creation sets BROADCAST and REUSEADDR options."""
        artnet_mock = MagicMock()
        loop = asyncio.new_event_loop()
        artnet_mock.loop = loop
        net = Network(artnet_mock)

        async def run_test() -> None:
            with patch("olc.core.backends.artnet.network.socket") as mock_sock_class:
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

                # Set listen to True to allow the interfaces loop to start
                net.listen = True
                await net._async_start()

                # Verify socket options
                mock_sock.setsockopt.assert_any_call(
                    socket.SOL_SOCKET, socket.SO_BROADCAST, 1
                )
                mock_sock.setsockopt.assert_any_call(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                )
                assert net.sock is mock_sock

                # Clean up
                await net._async_stop()

        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()

    def test_network_packet_dispatch(self) -> None:
        """Verify DatagramProtocol correctly forwards packet buffers."""
        artnet_mock = MagicMock()
        from olc.core.backends.artnet.network import ArtNetProtocol

        protocol = ArtNetProtocol(artnet_mock)
        data = b"dummy_packet"
        addr = ("192.168.1.1", 6454)

        protocol.datagram_received(data, addr)
        # Protocol should forward payload and source IP with standard Art-Net port
        from olc.core.backends.artnet.protocol import PORT

        artnet_mock.read_packet.assert_called_once_with(data, ("192.168.1.1", PORT))


class TestArtNetManager:
    """Test suite for ArtNetManager configurations, targets, and callbacks."""

    def test_manager_initialization(self) -> None:
        """Verify UniverseMap maps correctly inside ArtNetManager."""
        umap = UniverseMap(8)
        umap.enable_protocol(0, Protocol.ARTNET)
        umap.enable_protocol(3, Protocol.ARTNET)

        manager = ArtNetManager(umap)
        assert 0 in manager.universes
        assert 3 in manager.universes

        # Default discovered target address list is empty
        assert manager.get_node_ips(0) == []

        manager.stop()

    def test_manager_dmx_received_callback(self) -> None:
        """Verify received packets route to registered callbacks."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.ARTNET)

        callback_mock = MagicMock()
        manager = ArtNetManager(umap, on_dmx_received=callback_mock)

        dmx_data = [255] * 512

        # Trigger listener update callback
        manager._handle_incoming_dmx(1, dmx_data)
        callback_mock.assert_called_once_with(1, dmx_data)

        manager.stop()

    def test_manager_sync_active_configuration(self) -> None:
        """Verify sync_active configuration maps to ArtNetSender."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.ARTNET)
        umap[1].artnet.sync_active = True

        from olc.core.engine import CoreEngine

        engine = CoreEngine(umap)

        sender = engine._slots[1].senders[0]
        assert typing.cast(typing.Any, sender)._sync_active is True

    def test_manager_artsync_packet_transmission(self) -> None:
        """Verify ArtNetManager send_sync broadcasts the correct 14-byte packet."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.ARTNET)

        manager = ArtNetManager(umap)
        mock_network = MagicMock()
        manager.network = mock_network

        manager.send_sync()

        # Check broadcast sent the correct 14-byte ArtSync packet
        mock_network.send_broadcast.assert_called_once()
        sent_packet = mock_network.send_broadcast.call_args[0][0]
        assert len(sent_packet) == 14
        assert sent_packet == b"Art-Net\x00\x00\x52\x00\x0e\x00\x00"

        manager.stop()

    def test_engine_artsync_packet_transmission(self) -> None:
        """Verify that CoreEngine calls send_sync when universes have sync active."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.ARTNET)
        umap[1].artnet.sync_active = True

        from olc.core.engine import CoreEngine

        engine = CoreEngine(umap)

        # Mock ArtNetManager.send_sync
        mock_send_sync = MagicMock()
        typing.cast(typing.Any, engine._artnet_manager).send_sync = mock_send_sync

        # Mock the sender's send method
        for sender in engine._slots[1].senders:
            typing.cast(typing.Any, sender).send = MagicMock()

        # Execute a single tick of the loop
        engine._send_all()

        # Verify that ArtNetManager.send_sync was called!
        mock_send_sync.assert_called_once()

    def test_manager_dynamic_notify(self) -> None:
        """Verify that dynamic notify callbacks are correctly forwarded."""
        umap = UniverseMap(2)
        umap.enable_protocol(1, Protocol.ARTNET)

        manager = ArtNetManager(umap)

        # Initially, notify is None, so forwarder should do nothing and return None
        assert manager._notify_forwarder("add-node", "127.0.0.1", 1) is None

        # Bind a magic mock notify callback (simulating front-end registration)
        mock_notify = MagicMock()
        manager.notify = mock_notify

        # Trigger forwarder
        manager._notify_forwarder("add-node", "192.168.1.100", 2)

        # Assert mock was called
        mock_notify.assert_called_once_with("add-node", "192.168.1.100", 2)

        manager.stop()
