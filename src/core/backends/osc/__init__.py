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
"""OSC backend controller managing UDP transport, subscriptions, OSCQuery, and mDNS."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import typing

from olc.core.backends.osc.delegate import OSCDelegate
from olc.core.backends.osc.mdns import MDNSAdvertiser
from olc.core.backends.osc.oscquery import OSCQueryServer
from olc.core.backends.osc.transport import (
    CoreOSCClient,
    CoreOSCServer,
    OSCSubscriber,
    OSCSubscriptionManager,
    build_message,
    make_method,
    parse_message,
)

if typing.TYPE_CHECKING:
    import olc.core.backends.osc
    from olc.core.app import CoreApplication

__all__ = [
    "CoreOSCClient",
    "CoreOSCServer",
    "MDNSAdvertiser",
    "OSCDelegate",
    "OSCQueryServer",
    "OSCSubscriber",
    "OSCSubscriptionManager",
    "Osc",
    "build_message",
    "make_method",
    "parse_message",
]


class _OSCLoopThread(threading.Thread):
    """Dedicated background thread running the asyncio event loop for OSC I/O."""

    def __init__(self) -> None:
        super().__init__(name="OSCLoop", daemon=True)
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()

    def run(self) -> None:
        """Run the asyncio event loop until stopped."""
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()

    def stop(self) -> None:
        """Stop the asyncio event loop, join the thread, and close the loop."""
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.is_alive():
            self.join(timeout=2.0)
        if not self.loop.is_running() and not self.loop.is_closed():
            self.loop.close()


# pylint: disable=too-many-instance-attributes
class Osc:
    """Unified OSC controller owning UDP transport, delegate, OSCQuery, and mDNS."""

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the OSC backend.

        Args:
            app: CoreApplication owning this backend.
        """
        self.app = app
        self.lightshow = app.lightshow
        self._lock = threading.RLock()
        self._network_thread: _OSCLoopThread | None = None

        self.subscriptions = OSCSubscriptionManager()
        self.client: CoreOSCClient | None = None
        self.server: CoreOSCServer | None = None
        self.mdns: MDNSAdvertiser | None = None
        self.oscquery_server: OSCQueryServer | None = None
        self.delegate = OSCDelegate(
            self.app, osc=typing.cast("olc.core.backends.osc.Osc", self)
        )

    @property
    def is_running(self) -> bool:
        """Return True if the OSC UDP server is configured and active."""
        return self.server is not None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Ensure the dedicated asyncio thread is running and return its loop."""
        if self._network_thread is None:
            thread = _OSCLoopThread()
            thread.start()
            thread.ready.wait(timeout=2.0)
            self._network_thread = thread
        return self._network_thread.loop

    def start(
        self,
        host: str,
        client_port: int,
        server_port: int,
        enable_static_client: bool = False,
    ) -> None:
        """Start the OSC UDP server/client, OSCQuery HTTP server, and mDNS."""
        with self._lock:
            if self.server is not None or self.client is not None:
                self._stop_services()

            loop = self._ensure_loop()

            self.client = CoreOSCClient(host, client_port)
            self.subscriptions.set_socket(self.client.sock)
            if enable_static_client:
                self.subscriptions.subscribe(host, client_port, "all", is_static=True)

            self.server = CoreOSCServer(
                server_port,
                subscriptions=self.subscriptions,
                client=self.client,
            )
            self.server.register_delegate(self.delegate)

            asyncio.run_coroutine_threadsafe(self.server.start(), loop)

            http_port = server_port + 1
            self.oscquery_server = OSCQueryServer(
                host="0.0.0.0",
                http_port=http_port,
                on_client_connected=self._on_oscquery_client_connected,
            )
            asyncio.run_coroutine_threadsafe(
                self.oscquery_server.start(http_port=http_port, osc_port=server_port),
                loop,
            )

            self.mdns = MDNSAdvertiser()
            self.mdns.start(
                service_name="Open Lighting Console",
                port=server_port,
                http_port=http_port,
            )

            if enable_static_client:
                self.delegate.send_full_sync((host, client_port))

    def _on_oscquery_client_connected(self, client_ip: str) -> None:
        """Auto-subscribe and sync an OSCQuery client when it connects over HTTP."""
        if not client_ip:
            return
        reply_port = self.client.target[1] if self.client is not None else 8000
        self.subscriptions.subscribe(client_ip, reply_port, "all")
        self.delegate.send_full_sync((client_ip, reply_port))

    def _stop_services(self) -> list[concurrent.futures.Future[None]]:
        """Stop all OSC services and return any pending async shutdown futures."""
        futures: list[concurrent.futures.Future[None]] = []
        loop = self._network_thread.loop if self._network_thread is not None else None

        if self.oscquery_server is not None:
            if loop is not None:
                fut = asyncio.run_coroutine_threadsafe(
                    self.oscquery_server.stop(), loop
                )
                if isinstance(fut, concurrent.futures.Future):
                    futures.append(fut)
            self.oscquery_server = None

        if self.mdns is not None:
            self.mdns.stop()
            self.mdns = None

        if self.server is not None:
            old_server = self.server
            if loop is not None:
                loop.call_soon_threadsafe(old_server.stop)
            else:
                old_server.stop()
            self.server = None

        self.subscriptions.set_socket(None)
        if self.client is not None:
            self.client.close()
            self.client = None

        self.subscriptions.cleanup_expired(0.0)
        return futures

    def stop(self) -> None:
        """Stop all OSC networking services and tear down the OSC asyncio loop."""
        with self._lock:
            futures = self._stop_services()
            loop_thread = self._network_thread
            self._network_thread = None

        for fut in futures:
            try:
                fut.result(timeout=1.0)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if loop_thread is not None:
            loop_thread.stop()

    def set_static_client(self, enable: bool, host: str = "", port: int = 0) -> None:
        """Enable or disable the static fallback OSC client subscriber."""
        with self._lock:
            target_host = host
            target_port = port
            if self.client is not None:
                client_host, client_port = self.client.target
                if not target_host:
                    target_host = client_host
                if target_port <= 0:
                    target_port = client_port
            elif not target_host:
                target_host = "127.0.0.1"

            if target_port <= 0:
                target_port = 8000

            for sub in list(self.subscriptions.get_subscribers_snapshot()):
                if sub.get("is_static", False):
                    self.subscriptions.unsubscribe(sub["host"], sub["port"], "all")

            if enable:
                self.subscriptions.subscribe(
                    target_host, target_port, "all", is_static=True
                )
                self.delegate.send_full_sync((target_host, target_port))

    def update_client(self, host: str = "", port: int | None = None) -> None:
        """Update outgoing client IP or port settings."""
        with self._lock:
            if self.client is not None:
                old_host, old_port = self.client.target
                self.client.target_changed(host, port)
                new_host, new_port = self.client.target
                if self.subscriptions.unsubscribe(old_host, old_port, "all"):
                    self.subscriptions.subscribe(
                        new_host, new_port, "all", is_static=True
                    )

    def update_server(self, server_port: int) -> None:
        """Restart the OSC server, OSCQuery server, and mDNS on a new port."""
        with self._lock:
            if self.server is not None:
                loop = self._ensure_loop()
                old_server = self.server
                loop.call_soon_threadsafe(old_server.stop)

                self.server = CoreOSCServer(
                    server_port,
                    subscriptions=self.subscriptions,
                    client=self.client,
                )
                self.server.register_delegate(self.delegate)
                asyncio.run_coroutine_threadsafe(self.server.start(), loop)

                http_port = server_port + 1
                if self.oscquery_server is not None:
                    asyncio.run_coroutine_threadsafe(
                        self.oscquery_server.start(
                            http_port=http_port, osc_port=server_port
                        ),
                        loop,
                    )
                if self.mdns is not None:
                    self.mdns.start(
                        service_name="Open Lighting Console",
                        port=server_port,
                        http_port=http_port,
                    )

    def publish(self, topic: str, path: str, *args: object) -> None:
        """Publish an OSC message to subscribers of a topic."""
        self.subscriptions.publish(topic, path, *args)

    def send(self, path: str, *args: object) -> None:
        """Send an OSC message to subscribers listening to all/general topics."""
        self.subscriptions.publish("all", path, *args)

    def send_direct(self, host: str, port: int, path: str, *args: object) -> None:
        """Send an OSC message directly to a specific endpoint."""
        self.subscriptions.send_direct(host, port, path, *args)
