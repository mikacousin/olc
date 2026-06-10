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

    def dispatch(self, address: str, args: list) -> None:
        """Route the received message to matching handlers."""
        fallback = None
        for pattern, handler in self._handlers:
            if pattern is None:
                fallback = handler
            elif pattern == address:
                self._invoke_handler(handler, address, args)
                return
            elif fnmatch.fnmatch(address, pattern):
                self._invoke_handler(handler, address, args)
                return
        if fallback:
            self._invoke_handler(fallback, address, args)

    def _invoke_handler(self, handler: Callable, address: str, args: list) -> None:
        """Invoke a handler, passing the instance if unbound."""
        if inspect.ismethod(handler):
            # Bound method (already has 'self')
            handler(address, args)
        else:
            # Unbound method (pass the server instance as first argument)
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
            self._server.dispatch(address, args)
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
            # Direct channel assignment via CoreEngine
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
            self._engine.blackout(universe_id)  # type: ignore
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Engine] Error in blackout: {err}")
