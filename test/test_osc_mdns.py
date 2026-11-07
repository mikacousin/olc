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
"""Tests for mDNS / DNS-SD advertiser for OSC."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from olc.core.backends.osc.mdns import (
    MDNSAdvertiser,
    _build_response_packet,
    _encode_dns_name,
    _encode_txt_record,
)


def test_encode_dns_name() -> None:
    """Test DNS wire format encoding of dotted names."""
    encoded = _encode_dns_name("_osc._udp.local.")
    expected = b"\x04_osc\x04_udp\x05local\x00"
    assert encoded == expected


def test_encode_txt_record() -> None:
    """Test TXT record encoding into key=value bytes."""
    props = {"txtvers": "1", "name": "OLC"}
    encoded = _encode_txt_record(props)
    assert b"\ttxtvers=1" in encoded
    assert b"\x08name=OLC" in encoded


def test_build_response_packet() -> None:
    """Test building full DNS-SD response packet."""
    packet = _build_response_packet(
        service_name="Open Lighting Console",
        port=9000,
        hostname="lighting-desk",
        ip_address="192.168.1.50",
        properties={"values": "normalized"},
        ttl=120,
    )
    assert len(packet) > 50
    # Check DNS response header (Flags: 0x8400)
    assert packet[2:4] == b"\x84\x00"
    # Contains service identifier
    assert b"_osc" in packet
    assert b"Open Lighting Console" in packet


def test_mdns_advertiser_lifecycle_native_fallback() -> None:
    """Test MDNSAdvertiser start and stop with native responder fallback."""
    advertiser = MDNSAdvertiser()
    assert not advertiser.is_active

    mock_responder = MagicMock()
    mock_responder.start.return_value = True

    with patch(
        "olc.core.backends.osc.mdns._NativeMDNSResponder", return_value=mock_responder
    ):
        started = advertiser.start("OLC Test", 9005)
        assert started is True
        assert advertiser.is_active is True
        assert advertiser.service_name == "OLC Test"
        assert advertiser.port == 9005
        mock_responder.start.assert_called_once()

        advertiser.stop()
        assert advertiser.is_active is False
        mock_responder.stop.assert_called_once()


def test_mdns_advertiser_with_mocked_zeroconf() -> None:
    """Test MDNSAdvertiser uses zeroconf when library is available."""
    advertiser = MDNSAdvertiser()

    mock_zc = MagicMock()
    mock_service_info_cls = MagicMock()
    mock_zc_mod = MagicMock()
    mock_zc_mod.Zeroconf = MagicMock(return_value=mock_zc)
    mock_zc_mod.ServiceInfo = mock_service_info_cls

    with patch.dict("sys.modules", {"zeroconf": mock_zc_mod}):
        started = advertiser.start("OLC Zeroconf", 9002)
        assert started is True
        assert advertiser.is_active is True
        mock_zc.register_service.assert_called_once()

        advertiser.stop()
        assert advertiser.is_active is False
        mock_zc.unregister_service.assert_called_once()
        mock_zc.close.assert_called_once()


def test_mdns_advertiser_oscquery_dual_announcement() -> None:
    """Test MDNSAdvertiser registers both _osc._udp and _oscjson._tcp with http_port."""
    advertiser = MDNSAdvertiser()

    mock_zc = MagicMock()
    mock_service_info_cls = MagicMock()
    mock_zc_mod = MagicMock()
    mock_zc_mod.Zeroconf = MagicMock(return_value=mock_zc)
    mock_zc_mod.ServiceInfo = mock_service_info_cls

    with patch.dict("sys.modules", {"zeroconf": mock_zc_mod}):
        started = advertiser.start("OLC Dual", port=9000, http_port=9001)
        assert started is True
        assert advertiser.http_port == 9001
        # Both UDP and TCP services must be registered
        assert mock_zc.register_service.call_count == 2

        advertiser.stop()
        assert mock_zc.unregister_service.call_count == 2
        mock_zc.close.assert_called_once()
