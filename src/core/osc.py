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
import fnmatch
import inspect
import json
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast


def _pad(data: bytes) -> bytes:
    r = len(data) % 4
    return data + b"\x00" * (4 - r if r else 0)


def _encode_string(s: str) -> bytes:
    return _pad(s.encode("utf-8") + b"\x00")


def _decode_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.index(b"\x00", offset)
    s = data[offset:end].decode("utf-8")
    return s, (end + 1 + 3) & ~3


def parse_message(data: bytes) -> tuple[str, list]:
    """Parse a raw OSC message into (address, args)."""
    address, offset = _decode_string(data, 0)
    tags, offset = _decode_string(data, offset)
    args = []
    for tag in tags[1:]:  # Skip leading comma
        if tag == "i":
            args.append(struct.unpack_from(">i", data, offset)[0])
            offset += 4
        elif tag == "f":
            args.append(struct.unpack_from(">f", data, offset)[0])
            offset += 4
        elif tag == "s":
            s, offset = _decode_string(data, offset)
            args.append(s)
        elif tag == "T":
            args.append(True)
        elif tag == "F":
            args.append(False)
    return address, args


def build_message(address: str, *args: object) -> bytes:
    """Build a raw binary OSC message from an address and arguments."""
    tags, encoded = ",", b""
    for arg in args:
        if isinstance(arg, bool):
            tags += "T" if arg else "F"
        elif isinstance(arg, int):
            tags += "i"
            encoded += struct.pack(">i", arg)
        elif isinstance(arg, float):
            tags += "f"
            encoded += struct.pack(">f", arg)
        elif isinstance(arg, str):
            tags += "s"
            encoded += _encode_string(arg)
    return _encode_string(address) + _encode_string(tags) + encoded


def make_method(address: str | None, typetags: str | None = None) -> Callable:
    """
    Decorator to register a method as an OSC handler.
    Supports exact match, glob match, and fallback.
    """

    def decorator(func: Callable) -> Callable:
        func_any = cast(Any, func)
        if not hasattr(func_any, "osc_methods"):
            func_any.osc_methods = []
        func_any.osc_methods.append((address, typetags))
        return func

    return decorator


class CoreOSCClient:
    """OSC Client for sending UDP messages."""

    def __init__(self, host: str, port: int) -> None:
        self._addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def target_changed(self, host: str = "", port: int | None = None) -> None:
        """Change the target IP or port."""
        current_host, current_port = self._addr
        new_host = host if host else current_host
        new_port = port if port is not None else current_port
        self._addr = (new_host, new_port)

    def send(self, address: str, *args: object) -> None:
        """Send an OSC message."""
        try:
            self._sock.sendto(build_message(address, *args), self._addr)
        except OSError as err:
            print(
                f"[OSC Client] Warning: Failed to send message to {self._addr}: {err}"
            )

    def close(self) -> None:
        """Close the UDP socket."""
        self._sock.close()


@dataclass
class OSCSubscriber:
    """Represents an active OSC client subscriber."""

    host: str
    port: int
    topics: set[str]
    last_seen: float
    is_static: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return dictionary representation for GUI monitoring."""
        return {
            "host": self.host,
            "port": self.port,
            "topics": sorted(self.topics),
            "last_seen": self.last_seen,
            "is_static": self.is_static,
        }


class OSCSubscriptionManager:
    """Manages active OSC subscribers and topic publishing."""

    def __init__(self, sock: socket.socket | None = None) -> None:
        self._lock = threading.Lock()
        self._sock = sock
        self._subscribers: dict[tuple[str, int], OSCSubscriber] = {}

    def set_socket(self, sock: socket.socket) -> None:
        """Assign or update the outgoing UDP socket."""
        with self._lock:
            self._sock = sock

    def subscribe(
        self,
        host: str,
        port: int,
        topic: str = "all",
        is_static: bool = False,
    ) -> bool:
        """Register or update a subscription for a given client address.

        Returns True if a new subscriber was added, False if updated.
        """
        key = (host, port)
        clean_topic = topic.strip().lower() or "all"
        is_new = False
        with self._lock:
            if key not in self._subscribers:
                self._subscribers[key] = OSCSubscriber(
                    host=host,
                    port=port,
                    topics={clean_topic},
                    last_seen=time.time(),
                    is_static=is_static,
                )
                is_new = True
            else:
                sub = self._subscribers[key]
                sub.topics.add(clean_topic)
                sub.last_seen = time.time()
                if is_static:
                    sub.is_static = True
        return is_new

    def unsubscribe(self, host: str, port: int, topic: str = "all") -> bool:
        """Unsubscribe a client from a specific topic or all topics."""
        key = (host, port)
        clean_topic = topic.strip().lower() or "all"
        removed = False
        with self._lock:
            if key in self._subscribers:
                sub = self._subscribers[key]
                if clean_topic in ("all", "*"):
                    del self._subscribers[key]
                    removed = True
                else:
                    sub.topics.discard(clean_topic)
                    if not sub.topics and not sub.is_static:
                        del self._subscribers[key]
                        removed = True
        return removed

    def refresh_keepalive(self, host: str, port: int) -> bool:
        """Refresh the last_seen timestamp of a subscriber."""
        key = (host, port)
        with self._lock:
            if key in self._subscribers:
                self._subscribers[key].last_seen = time.time()
                return True
            for (h, _p), sub in self._subscribers.items():
                if h == host:
                    sub.last_seen = time.time()
                    return True
        return False

    def cleanup_expired(self, timeout_seconds: float = 60.0) -> list[tuple[str, int]]:
        """Remove subscribers inactive for longer than timeout_seconds."""
        now = time.time()
        expired: list[tuple[str, int]] = []
        with self._lock:
            for key, sub in list(self._subscribers.items()):
                if not sub.is_static and (now - sub.last_seen > timeout_seconds):
                    expired.append(key)
                    del self._subscribers[key]
        return expired

    def get_subscribers_snapshot(self) -> list[dict[str, Any]]:
        """Return a snapshot list of current subscribers for telemetry/GUI."""
        with self._lock:
            return [sub.to_dict() for sub in self._subscribers.values()]

    def send_direct(self, host: str, port: int, address: str, *args: object) -> None:
        """Send an OSC message directly to a specific target."""
        with self._lock:
            if self._sock is None:
                return
            try:
                msg = build_message(address, *args)
                self._sock.sendto(msg, (host, port))
            except OSError as err:
                print(
                    f"[OSC SubManager] Warning: send_direct to ({host}:{port}) "
                    f"failed: {err}"
                )

    def publish(self, topic: str, address: str, *args: object) -> None:
        """Publish an OSC message to all subscribers of the topic."""
        clean_topic = topic.strip().lower()
        targets: list[tuple[str, int]] = []
        with self._lock:
            if self._sock is None:
                return
            for key, sub in self._subscribers.items():
                if "all" in sub.topics or clean_topic in sub.topics:
                    targets.append(key)

        if not targets:
            return

        msg = build_message(address, *args)
        for host, port in targets:
            try:
                self._sock.sendto(msg, (host, port))
            except OSError as err:
                print(
                    f"[OSC SubManager] Warning: publish to ({host}:{port}) "
                    f"failed: {err}"
                )


class CoreOSCServer:
    """
    Subclassable asynchronous OSC Server.
    Dispatches exact matches, glob patterns, and fallbacks.
    """

    _handler_map: list[tuple[str | None, Callable]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._handler_map = []
        # Harvest decorated methods from the class dictionary
        for attr in cls.__dict__.values():
            if hasattr(attr, "osc_methods"):
                for address, _ in attr.osc_methods:
                    cls._handler_map.append((address, attr))

    def __init__(
        self, port: int, host: str = "0.0.0.0", engine: Optional[object] = None
    ) -> None:
        self._port = port
        self._host = host
        self._engine = engine
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._delegate: Optional[object] = None
        # Copy the harvested class handlers to this instance's handler table
        self._handlers = list(self._handler_map)

    def register_delegate(self, delegate: object) -> None:
        """Dynamically harvest and register OSC handlers from a delegate instance."""
        self._delegate = delegate
        for attr_name in dir(delegate):
            try:
                attr = getattr(delegate, attr_name)
                if hasattr(attr, "osc_methods"):
                    for address, _ in attr.osc_methods:
                        self._handlers.append((address, attr))
            except AttributeError:
                continue

    def dispatch(
        self,
        address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Route the received message to matching handlers."""
        fallback = None
        for pattern, handler in self._handlers:
            if pattern is None:
                fallback = handler
            elif pattern == address:
                self._invoke_handler(handler, address, args, sender_addr)
                return
            elif fnmatch.fnmatch(address, pattern):
                self._invoke_handler(handler, address, args, sender_addr)
                return
        if fallback:
            self._invoke_handler(fallback, address, args, sender_addr)

    def _invoke_handler(
        self,
        handler: Callable,
        address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Invoke a handler, passing instance and sender_addr if supported."""
        try:
            sig = inspect.signature(handler)
            is_bound = inspect.ismethod(handler)
            pos_params = [
                p
                for p in sig.parameters.values()
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            expects_sender = (
                len(pos_params) >= 3 if is_bound else len(pos_params) >= 4
            ) or "sender_addr" in sig.parameters
        except (ValueError, TypeError):
            is_bound = inspect.ismethod(handler)
            expects_sender = False

        if is_bound:
            if expects_sender:
                handler(address, args, sender_addr)
            else:
                handler(address, args)
        else:
            if expects_sender:
                handler(self, address, args, sender_addr)
            else:
                handler(self, address, args)

    async def start(self) -> None:
        """Start listening on the configured socket."""
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _OSCProtocol(self),
            local_addr=(self._host, self._port),
        )

    def stop(self) -> None:
        """Close the socket transport."""
        if self._transport:
            self._transport.close()
            self._transport = None


class _OSCProtocol(asyncio.DatagramProtocol):
    def __init__(self, server: CoreOSCServer) -> None:
        self._server = server

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            address, args = parse_message(data)
            engine = getattr(self._server, "_engine", None)
            if (
                engine is not None
                and (address.startswith("/olc/") or address == "/ping")
                and address
                not in (
                    "/olc/unsubscribe",
                    "/olc/subscribe",
                    "/olc/channels/subscribe",
                )
            ):
                sub_mgr = getattr(engine, "osc_subscriptions", None)
                osc_cli = getattr(engine, "osc_client", None)
                if sub_mgr is not None and not sub_mgr.refresh_keepalive(
                    addr[0], addr[1]
                ):
                    reply_port = (
                        osc_cli._addr[1]
                        if osc_cli is not None and hasattr(osc_cli, "_addr")
                        else 8000
                    )
                    if sub_mgr.subscribe(addr[0], reply_port, "all"):
                        delegate = getattr(self._server, "_delegate", None)
                        if delegate is not None and hasattr(delegate, "send_full_sync"):
                            delegate.send_full_sync((addr[0], reply_port))
            self._server.dispatch(address, args, addr)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Server] Warning: Parse error from {addr}: {err}")


class EngineOSCServer(CoreOSCServer):
    """Core OSC server subclass implementing direct DMX/CoreEngine control paths."""

    @make_method("/olc/universe/*/set_channels")
    def _set_channels(self, address: str, args: list) -> None:
        if self._engine is None:
            return
        try:
            parts = address.split("/")
            universe_id = int(parts[3])
            if args and isinstance(args[0], str):
                channels = {int(k): int(v) for k, v in json.loads(args[0]).items()}
            else:
                channels = {}
                for i in range(0, len(args), 2):
                    if i + 1 < len(args):
                        channels[int(args[i])] = int(args[i + 1])

            delegate_app = getattr(self._delegate, "app", None)
            if delegate_app is not None and hasattr(delegate_app, "action_registry"):
                delegate_app.action_registry.execute(
                    "dmx.set_universe_levels", universe_id, channels
                )
            else:
                # Direct channel assignment fallback via CoreEngine
                self._engine.set_channels(universe_id, channels)  # type: ignore
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Engine] Error in set_channels: {err}")

    @make_method("/olc/universe/*/blackout")
    def _blackout(self, address: str, _args: list) -> None:
        if self._engine is None:
            return
        try:
            parts = address.split("/")
            universe_id = int(parts[3])
            delegate_app = getattr(self._delegate, "app", None)
            if delegate_app is not None and hasattr(delegate_app, "action_registry"):
                delegate_app.action_registry.execute("universe.blackout", universe_id)
            else:
                self._engine.blackout(universe_id)  # type: ignore
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Engine] Error in blackout: {err}")
