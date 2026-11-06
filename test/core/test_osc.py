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

# pylint: disable=missing-class-docstring,missing-function-docstring,too-few-public-methods
import json
from unittest.mock import MagicMock

from olc.core.osc import (
    CoreOSCServer,
    EngineOSCServer,
    OSCSubscriptionManager,
    build_message,
    make_method,
    parse_message,
)


class TestOSCCodec:
    """Test suite for the OSC binary codec."""

    def test_encode_decode_int(self) -> None:
        """Encoding and decoding an integer must yield the exact value."""
        msg = build_message("/test/path", 42)
        address, args = parse_message(msg)
        assert address == "/test/path"
        assert args == [42]

    def test_encode_decode_float(self) -> None:
        """Encoding and decoding a float must yield the exact value."""
        msg = build_message("/test/path", 3.14)
        address, args = parse_message(msg)
        assert address == "/test/path"
        assert abs(args[0] - 3.14) < 1e-5

    def test_encode_decode_string(self) -> None:
        """Encoding and decoding a string must yield the exact value."""
        msg = build_message("/test/path", "hello")
        address, args = parse_message(msg)
        assert address == "/test/path"
        assert args == ["hello"]

    def test_encode_decode_bool(self) -> None:
        """Encoding and decoding booleans must yield the exact values."""
        msg = build_message("/test/path", True, False)
        address, args = parse_message(msg)
        assert address == "/test/path"
        assert args == [True, False]

    def test_encode_decode_mixed(self) -> None:
        """Encoding and decoding mixed types must yield the exact values."""
        msg = build_message("/test/path", 10, 0.5, "world", True)
        address, args = parse_message(msg)
        assert address == "/test/path"
        assert args == [10, 0.5, "world", True]


class TestOSCServerDispatch:
    """Test suite for the OSC server routing and dispatch."""

    def test_dispatch_exact_match(self) -> None:
        """An exact OSC address match must be prioritized and triggered."""

        class MockServer(CoreOSCServer):
            def __init__(self) -> None:
                super().__init__(port=9999)
                self.triggered = False

            @make_method("/olc/fader/1")
            def on_fader_1(self, address: str, args: list) -> None:
                self.triggered = True
                assert address == "/olc/fader/1"
                assert args == [100]

        server = MockServer()
        server.dispatch("/olc/fader/1", [100])
        assert server.triggered

    def test_dispatch_glob_match(self) -> None:
        """Glob pattern matching (using asterisks) must route correctly."""

        class MockServer(CoreOSCServer):
            def __init__(self) -> None:
                super().__init__(port=9999)
                self.matched_group = None

            @make_method("/olc/group/*/fader")
            def on_group_fader(self, address: str, _args: list) -> None:
                parts = address.split("/")
                self.matched_group = parts[3]

        server = MockServer()
        server.dispatch("/olc/group/A/fader", [0.5])
        assert server.matched_group == "A"
        server.dispatch("/olc/group/B/fader", [0.8])
        assert server.matched_group == "B"

    def test_dispatch_fallback(self) -> None:
        """Unmatched addresses must trigger the fallback handler if registered."""

        class MockServer(CoreOSCServer):
            def __init__(self) -> None:
                super().__init__(port=9999)
                self.fallback_triggered = False

            @make_method(None)
            def on_fallback(self, _address: str, _args: list) -> None:
                self.fallback_triggered = True

        server = MockServer()
        server.dispatch("/some/unknown/path", [])
        assert server.fallback_triggered

    def test_delegate_harvesting(self) -> None:
        """OSC Server must dynamically harvest decorated methods from registered
        delegates.
        """

        class MockDelegate:
            def __init__(self) -> None:
                self.triggered = False

            @make_method("/delegate/test")
            def on_test(self, _address: str, _args: list) -> None:
                self.triggered = True

        server = CoreOSCServer(port=9999)
        delegate = MockDelegate()
        server.register_delegate(delegate)
        server.dispatch("/delegate/test", [])
        assert delegate.triggered


class TestEngineOSCServer:
    """Test suite for direct CoreEngine control endpoints."""

    def test_set_channels_direct(self) -> None:
        """Direct channel values in list format must write to engine."""
        mock_engine = MagicMock()
        server = EngineOSCServer(port=9999, engine=mock_engine)

        server.dispatch("/olc/universe/2/set_channels", [1, 255, 2, 128])
        mock_engine.set_channels.assert_called_once_with(2, {1: 255, 2: 128})

    def test_set_channels_json(self) -> None:
        """JSON-encoded channel string must write to engine."""
        mock_engine = MagicMock()
        server = EngineOSCServer(port=9999, engine=mock_engine)

        channels_json = json.dumps({"5": 200, "6": 100})
        server.dispatch("/olc/universe/1/set_channels", [channels_json])
        mock_engine.set_channels.assert_called_once_with(1, {5: 200, 6: 100})

    def test_blackout(self) -> None:
        """Blackout endpoint must trigger engine blackout."""
        mock_engine = MagicMock()
        server = EngineOSCServer(port=9999, engine=mock_engine)

        server.dispatch("/olc/universe/3/blackout", [])
        mock_engine.blackout.assert_called_once_with(3)


class TestOSCSubscriptionManager:
    """Test suite for OSCSubscriptionManager topic pub/sub and lease management."""

    def test_subscribe_and_snapshot(self) -> None:
        """Subscriptions must be tracked and reportable via get_subscribers_snapshot."""
        manager = OSCSubscriptionManager()
        is_new = manager.subscribe("192.168.1.10", 8000, "patch")
        assert is_new is True

        # Re-subscribing with same or another topic
        is_new2 = manager.subscribe("192.168.1.10", 8000, "faders")
        assert is_new2 is False

        snapshot = manager.get_subscribers_snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["host"] == "192.168.1.10"
        assert snapshot[0]["port"] == 8000
        assert snapshot[0]["topics"] == ["faders", "patch"]
        assert snapshot[0]["is_static"] is False

    def test_unsubscribe(self) -> None:
        """Unsubscribing topics or all must correctly update manager."""
        manager = OSCSubscriptionManager()
        manager.subscribe("10.0.0.5", 9000, "patch")
        manager.subscribe("10.0.0.5", 9000, "faders")

        # Discard one topic
        removed = manager.unsubscribe("10.0.0.5", 9000, "patch")
        assert removed is False
        snapshot = manager.get_subscribers_snapshot()
        assert snapshot[0]["topics"] == ["faders"]

        # Discard all
        removed_all = manager.unsubscribe("10.0.0.5", 9000, "all")
        assert removed_all is True
        assert len(manager.get_subscribers_snapshot()) == 0

    def test_static_subscriber_persistence(self) -> None:
        """Static subscriber must not be removed by timeout expiration."""
        manager = OSCSubscriptionManager()
        manager.subscribe("127.0.0.1", 8000, "all", is_static=True)
        manager.subscribe("192.168.1.99", 5000, "patch", is_static=False)

        # Expire dynamic subscriber by specifying 0 timeout
        expired = manager.cleanup_expired(timeout_seconds=0.0)
        assert ("192.168.1.99", 5000) in expired
        assert ("127.0.0.1", 8000) not in expired

        snapshot = manager.get_subscribers_snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["host"] == "127.0.0.1"
        assert snapshot[0]["is_static"] is True

    def test_refresh_keepalive(self) -> None:
        """Keepalive refresh must update last_seen timestamp."""
        manager = OSCSubscriptionManager()
        manager.subscribe("192.168.1.12", 7000, "playback")
        snapshot1 = manager.get_subscribers_snapshot()
        ts1 = snapshot1[0]["last_seen"]

        # Refresh with matching endpoint
        assert manager.refresh_keepalive("192.168.1.12", 7000) is True
        snapshot2 = manager.get_subscribers_snapshot()
        assert snapshot2[0]["last_seen"] >= ts1

        # Refresh with matching host even if port differs (ephemeral sender port)
        assert manager.refresh_keepalive("192.168.1.12", 54321) is True

    def test_publish_filtering(self) -> None:
        """Publish must only deliver to subscribers of matching topic or 'all'."""
        mock_sock = MagicMock()
        manager = OSCSubscriptionManager(sock=mock_sock)

        manager.subscribe("192.168.1.1", 8001, "patch")
        manager.subscribe("192.168.1.2", 8002, "faders")
        manager.subscribe("192.168.1.3", 8003, "all")

        # 1. Publish patch event
        mock_sock.sendto.reset_mock()
        manager.publish("patch", "/olc/patch/changed", 10)
        recipients = [call[0][1] for call in mock_sock.sendto.call_args_list]
        assert ("192.168.1.1", 8001) in recipients
        assert ("192.168.1.3", 8003) in recipients
        assert ("192.168.1.2", 8002) not in recipients

        # 2. Publish fader event
        mock_sock.sendto.reset_mock()
        manager.publish("faders", "/olc/fader/1/1/level", 255)
        recipients = [call[0][1] for call in mock_sock.sendto.call_args_list]
        assert ("192.168.1.2", 8002) in recipients
        assert ("192.168.1.3", 8003) in recipients
        assert ("192.168.1.1", 8001) not in recipients

    def test_send_direct(self) -> None:
        """send_direct must deliver to the specified host and port immediately."""
        mock_sock = MagicMock()
        manager = OSCSubscriptionManager(sock=mock_sock)

        manager.send_direct("192.168.1.50", 9999, "/direct/msg", "hello")
        mock_sock.sendto.assert_called_once()
        msg_bytes, target = mock_sock.sendto.call_args[0]
        assert target == ("192.168.1.50", 9999)
        addr, args = parse_message(msg_bytes)
        assert addr == "/direct/msg"
        assert args == ["hello"]
