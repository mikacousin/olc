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
import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from olc.core.backends.artnet import ArtNetManager
from olc.core.backends.artnet.artnet import Sender as ArtNetSenderClass
from olc.core.backends.enttec import DmxUsbProManager, resolve_port
from olc.core.backends.sacn import SacnManager
from olc.core.backends.sacn.merge import SacnMerger
from olc.core.dmxloop import DMXLoop
from olc.core.mergers import HTPMerger, LTPMerger
from olc.core.osc import CoreOSCClient, EngineOSCServer
from olc.core.senders import ArtNetSender, DmxUsbProSender, SACNSender
from olc.core.universe_config import (
    DmxUsbProSettings,
    Protocol,
    UniverseConfig,
    UniverseMap,
)
from olc.core.universe_data import DMXUniverse


class NetworkLoopThread(threading.Thread):
    """A thread dedicated to running an asyncio event loop for background network IO."""

    def __init__(self) -> None:
        super().__init__(name="NetworkLoop", daemon=True)
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()

    def run(self) -> None:
        """Run the asyncio event loop."""
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()

    def stop(self) -> None:
        """Stop the loop and join the thread."""
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.join()


@dataclass
class _RuntimeSlot:
    """Groups all runtime components for a single DMX universe."""

    universe: DMXUniverse
    htp_merger: HTPMerger | None = field(default=None)
    ltp_merger: LTPMerger | None = field(default=None)
    senders: list[ArtNetSender | SACNSender | DmxUsbProSender] = field(
        default_factory=list
    )


def _build_senders(  # pylint: disable=unexpected-keyword-arg,too-many-arguments,too-many-positional-arguments
    config: UniverseConfig,
    artnet_manager: ArtNetManager | None = None,
    dest_ip: str = "255.255.255.255",
    sacn_multicast: bool = True,
    dmx_usb_pro_manager: DmxUsbProManager | None = None,
    sacn_cid: bytes = b"",
) -> list[ArtNetSender | SACNSender | DmxUsbProSender]:
    """Create the network senders described by a UniverseConfig."""
    senders: list[ArtNetSender | SACNSender | DmxUsbProSender] = []
    if Protocol.ARTNET in config.protocols:
        # Compute Art-Net universe from net/sub/universe
        artnet_universe = (
            (config.artnet.net << 8) | (config.artnet.sub << 4) | config.universe_id
        )
        senders.append(
            ArtNetSender(
                ip=dest_ip,
                universe=artnet_universe,
                manager=artnet_manager,
                sync_active=config.artnet.sync_active,
            )
        )
    if Protocol.SACN in config.protocols:
        senders.append(
            SACNSender(
                universe=config.universe_id,
                priority=config.sacn.priority,
                sync_address=config.sacn.sync_address,
                multicast=sacn_multicast,
                ip=dest_ip,
                cid=sacn_cid,
            )
        )
    if Protocol.DMX_USB_PRO in config.protocols and dmx_usb_pro_manager is not None:
        senders.append(
            DmxUsbProSender(
                manager=dmx_usb_pro_manager,
                port_index=config.dmx_usb_pro.port_index,
            )
        )
    return senders


class CoreEngine:  # pylint: disable=too-many-instance-attributes,too-many-branches,protected-access,unexpected-keyword-arg
    """
    Orchestrates DMX output for all universes declared in a UniverseMap.

    A single DMXLoop thread drives all universes at the target frequency.
    Each universe has its own DMXUniverse buffer and optional merger components.

    Usage::

        universe_map = UniverseMap(8)
        universe_map.enable_protocol(1, Protocol.ARTNET)

        engine = CoreEngine(universe_map, hz=44.0)
        engine.start()

        engine.set_channels(1, {0: 255, 1: 128})

        engine.stop()
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        universe_map: UniverseMap,
        hz: float = 44.0,
        monitor_port: int | None = None,
        monitor_fps: float = 15.0,
        no_listen: bool = False,
        loopback: bool = False,
        no_transmit: bool = False,
    ) -> None:
        self._map = universe_map
        self._lock = threading.Lock()
        self._no_listen = no_listen
        self._loopback = loopback
        self._no_transmit = no_transmit

        self.osc_server = None
        self.osc_client = None
        self._osc_delegate = None

        # Raise soft open files limit to support 1024+ universes
        try:
            import resource  # pylint: disable=import-outside-toplevel

            hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
        except (ImportError, OSError):
            pass

        # Start network event loop thread
        self._network_thread = NetworkLoopThread()
        self._network_thread.start()
        self._network_thread.ready.wait()

        # Initialize Art-Net manager
        self._artnet_manager = ArtNetManager(
            universe_map,
            on_dmx_received=self._on_artnet_dmx_received,
            loop=self._network_thread.loop,
        )

        # Initialize sACN manager
        self._sacn_manager = SacnManager(
            universe_map,
            on_dmx_received=self._on_sacn_dmx_received,
            loop=self._network_thread.loop,
            no_transmit=no_transmit,
            no_listen=no_listen,
        )

        # Initialize DMX USB Pro managers registry
        self._dmx_usb_pro_managers: dict[str, DmxUsbProManager] = {}
        self.notify_enttec: Callable | None = None

        # Build one runtime slot per universe declared in the map
        self._slots: dict[int, _RuntimeSlot] = {}
        for config in universe_map:
            dmx_usb_pro_manager = None
            if not no_transmit and Protocol.DMX_USB_PRO in config.protocols:
                port = resolve_port(config.dmx_usb_pro.port)
                if port not in self._dmx_usb_pro_managers:
                    dmx_usb_pro_manager = DmxUsbProManager(
                        port=port,
                        loop=self._network_thread.loop,
                        configs_provider=lambda p=port: self._get_dmx_usb_pro_configs(
                            p
                        ),
                    )
                    dmx_usb_pro_manager.notify = lambda action, *args, p=port: (
                        self._notify_enttec_for_port(p, action, *args)
                    )
                    self._dmx_usb_pro_managers[port] = dmx_usb_pro_manager
                else:
                    dmx_usb_pro_manager = self._dmx_usb_pro_managers[port]

            self._slots[config.universe_id] = _RuntimeSlot(
                universe=DMXUniverse(config.universe_id),
                senders=[]
                if no_transmit
                else _build_senders(
                    config,
                    self._artnet_manager,
                    dest_ip="127.0.0.1" if loopback else "255.255.255.255",
                    sacn_multicast=not loopback,
                    dmx_usb_pro_manager=dmx_usb_pro_manager,
                    sacn_cid=self._sacn_manager._cid,
                ),
            )

        self._loop = DMXLoop(send_fn=self._send_all, hz=hz)

        # ZeroMQ monitoring setup
        self._zmq_ctx = None
        self._zmq_pub = None
        self._monitor_interval = 1.0 / monitor_fps if monitor_fps > 0 else 0.0
        self._last_monitor_time = 0.0

        if monitor_port is not None:
            try:
                import zmq  # pylint: disable=import-outside-toplevel

                self._zmq_ctx = zmq.Context()
                self._zmq_pub = self._zmq_ctx.socket(zmq.PUB)
                self._zmq_pub.bind(f"tcp://127.0.0.1:{monitor_port}")
            except Exception as err:  # pylint: disable=broad-exception-caught
                print(
                    "[ZMQ] Warning: Failed to bind to monitor port"
                    f" {monitor_port} ({err})."
                )
                self._zmq_pub = None
                self._zmq_ctx = None

    def start(self) -> None:
        """Start the DMX output loop."""
        if self._artnet_manager is not None and any(
            Protocol.ARTNET in c.protocols for c in self._map
        ):
            self._artnet_manager.start()
        if self._sacn_manager is not None and any(
            Protocol.SACN in c.protocols for c in self._map
        ):
            self._sacn_manager.start()
        for manager in self._dmx_usb_pro_managers.values():
            manager.start()
        if not self._no_transmit:
            self._loop.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the DMX output loop."""
        self.stop_osc()
        self._loop.stop(timeout=timeout)
        if self._artnet_manager is not None:
            self._artnet_manager.stop()
        if self._sacn_manager is not None:
            self._sacn_manager.stop()
        for manager in self._dmx_usb_pro_managers.values():
            manager.stop()
        if self._network_thread is not None:
            self._network_thread.stop()
        if self._zmq_pub is not None:
            self._zmq_pub.close()
        if self._zmq_ctx is not None:
            self._zmq_ctx.term()

    @property
    def is_running(self) -> bool:
        """Returns True if the loop is active."""
        return self._loop.is_running

    @property
    def universe_map(self) -> UniverseMap:
        """Return the UniverseMap configuration."""
        return self._map

    @property
    def sacn_manager(self) -> SacnManager:
        """Return the sACN manager."""
        return self._sacn_manager

    def __enter__(self) -> "CoreEngine":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def universe(self, uid: int) -> DMXUniverse:
        """Return the DMXUniverse buffer for a given universe id."""
        return self._get_slot(uid).universe

    def _add_htp_merger(self, uid: int, num_sources: int) -> None:
        """Attach an HTPMerger to a universe slot."""
        slot = self._get_slot(uid)
        with self._lock:
            slot.htp_merger = HTPMerger(num_sources)

    def _add_ltp_merger(self, uid: int, num_sources: int) -> None:
        """Attach an LTPMerger to a universe slot."""
        slot = self._get_slot(uid)
        with self._lock:
            slot.ltp_merger = LTPMerger(num_sources)

    def _get_dmx_usb_pro_configs(self, port: str) -> list[DmxUsbProSettings]:
        """Get all active DMX USB Pro configurations for a given port."""
        configs = []
        for c in self._map:
            if not self._no_transmit and Protocol.DMX_USB_PRO in c.protocols:
                if resolve_port(c.dmx_usb_pro.port) == port:
                    configs.append(c.dmx_usb_pro)
        return configs

    def _notify_enttec_for_port(self, port: str, action: str, *args: object) -> None:
        """Notify Enttec events for all universes sharing this port."""
        if not self.notify_enttec:
            return
        for c in self._map:
            if not self._no_transmit and Protocol.DMX_USB_PRO in c.protocols:
                if resolve_port(c.dmx_usb_pro.port) == port:
                    self.notify_enttec(c.universe_id, action, *args)  # pylint: disable=not-callable

    def _reload_dmx_usb_pro(
        self, uid: int, config: UniverseConfig
    ) -> DmxUsbProManager | None:
        """Stop old DmxUsbProManagers no longer needed, and get/create manager for
        config.
        """
        # Clean up managers that are no longer needed by ANY universe
        needed_ports = set()
        for c in self._map:
            if not self._no_transmit and Protocol.DMX_USB_PRO in c.protocols:
                needed_ports.add(resolve_port(c.dmx_usb_pro.port))

        for port in list(self._dmx_usb_pro_managers.keys()):
            if port not in needed_ports:
                self._dmx_usb_pro_managers.pop(port).stop()

        dmx_usb_pro_manager = None
        if not self._no_transmit and Protocol.DMX_USB_PRO in config.protocols:
            port = resolve_port(config.dmx_usb_pro.port)
            if port not in self._dmx_usb_pro_managers:
                dmx_usb_pro_manager = DmxUsbProManager(
                    port=port,
                    loop=self._network_thread.loop,
                    configs_provider=lambda p=port: self._get_dmx_usb_pro_configs(p),
                )
                dmx_usb_pro_manager.notify = lambda action, *args, p=port: (
                    self._notify_enttec_for_port(p, action, *args)
                )
                self._dmx_usb_pro_managers[port] = dmx_usb_pro_manager
                if self.is_running:
                    dmx_usb_pro_manager.start()
            else:
                dmx_usb_pro_manager = self._dmx_usb_pro_managers[port]
                if dmx_usb_pro_manager.is_connected and self.notify_enttec:
                    self.notify_enttec(uid, "connect", port)  # pylint: disable=not-callable
        return dmx_usb_pro_manager

    def _reload_artnet(self, uid: int, config: UniverseConfig) -> None:
        """Update Art-Net manager configuration for a universe reload."""
        self._artnet_manager.universes = [
            c.universe_id for c in self._map if Protocol.ARTNET in c.protocols
        ]
        self._artnet_manager.listeners.universes = self._artnet_manager.universes
        self._artnet_manager.discovery.universes = self._artnet_manager.universes
        if Protocol.ARTNET in config.protocols:
            if uid not in self._artnet_manager.senders:
                self._artnet_manager.senders[uid] = ArtNetSenderClass(
                    uid, self._artnet_manager._notify_forwarder
                )
            if self.is_running:
                self._artnet_manager.start()
        else:
            self._artnet_manager.senders.pop(uid, None)
            if self.is_running and not self._artnet_manager.universes:
                self._artnet_manager.stop()

    def _reload_sacn(self, uid: int, config: UniverseConfig) -> None:
        """Update sACN manager configuration for a universe reload."""
        old_universes = list(self._sacn_manager.universes)
        self._sacn_manager.universes = [
            c.universe_id for c in self._map if Protocol.SACN in c.protocols
        ]
        if Protocol.SACN in config.protocols:
            if uid not in old_universes:
                self._sacn_manager.network.join_multicast(uid)
            if uid not in self._sacn_manager.mergers:
                self._sacn_manager.mergers[uid] = SacnMerger(
                    universe=uid,
                    callback=self._sacn_manager._handle_incoming_dmx,
                )
            if not self._no_transmit:
                if uid not in self._sacn_manager.senders:
                    self._sacn_manager.senders[uid] = SACNSender(
                        universe=uid, multicast=True, cid=self._sacn_manager._cid
                    )
            sync_addr = config.sacn.sync_address
            if sync_addr > 0:
                self._sacn_manager.network.join_multicast(sync_addr)
            if self.is_running:
                self._sacn_manager.start()
        else:
            if uid in old_universes:
                self._sacn_manager.network.leave_multicast(uid)
            self._sacn_manager.mergers.pop(uid, None)
            if uid in self._sacn_manager.senders:
                self._sacn_manager.senders.pop(uid).close()
            if self.is_running and not self._sacn_manager.universes:
                self._sacn_manager.stop()

    def reload_universe(self, uid: int) -> None:
        """
        Rebuild the senders for a universe from its current UniverseConfig.
        Useful when the user changes the protocol settings at runtime.
        """
        config = self._map[uid]
        dest_ip = "127.0.0.1" if self._loopback else "255.255.255.255"
        sacn_multicast = not self._loopback

        dmx_usb_pro_manager = self._reload_dmx_usb_pro(uid, config)

        new_senders = (
            []
            if self._no_transmit
            else _build_senders(
                config,
                self._artnet_manager,
                dest_ip=dest_ip,
                sacn_multicast=sacn_multicast,
                dmx_usb_pro_manager=dmx_usb_pro_manager,
                sacn_cid=self._sacn_manager._cid,
            )
        )
        with self._lock:
            self._get_slot(uid).senders = new_senders

        self._reload_artnet(uid, config)
        self._reload_sacn(uid, config)

    def blackout(self, uid: int) -> None:
        """Zero all channels of a universe immediately."""
        self._get_slot(uid).universe.blackout()

    def set_channels(self, uid: int, channels: dict[int, int]) -> None:
        """Write a dict of {channel: value} to a universe."""
        self._get_slot(uid).universe.set_channels(channels)

    def _htp_write(self, uid: int, source_id: int, channels: dict[int, int]) -> None:
        """
        Write channels for a source via the HTP merger.
        Raises RuntimeError if no HTPMerger is attached to this universe.
        """
        slot = self._get_slot(uid)
        if slot.htp_merger is None:
            raise RuntimeError(
                f"Universe {uid} has no HTPMerger."
                f" Call add_htp_merger({uid}, ...) first."
            )
        slot.htp_merger.write(source_id, channels)
        slot.htp_merger.get_output(out=slot.universe.array)

    def _ltp_write(self, uid: int, source_id: int, channels: dict[int, int]) -> None:
        """
        Write channels for a source via the LTP merger.
        Raises RuntimeError if no LTPMerger is attached to this universe.
        """
        slot = self._get_slot(uid)
        if slot.ltp_merger is None:
            raise RuntimeError(
                f"Universe {uid} has no LTPMerger."
                f" Call add_ltp_merger({uid}, ...) first."
            )
        slot.ltp_merger.write(source_id, channels)
        slot.ltp_merger.get_output(out=slot.universe.array)

    @property
    def frame_count(self) -> int:
        """Total frames sent since start."""
        return self._loop.frame_count

    @property
    def effective_hz(self) -> float:
        """Average output frequency since start."""
        return self._loop.effective_hz

    def start_osc(self, host: str, client_port: int, server_port: int) -> None:
        """Start the OSC server and client asynchronously in the network loop."""
        with self._lock:
            if self.osc_server is not None or self.osc_client is not None:
                self.stop_osc()

            self.osc_client = CoreOSCClient(host, client_port)
            self.osc_server = EngineOSCServer(server_port, engine=self)
            if self._osc_delegate is not None:
                self.osc_server.register_delegate(self._osc_delegate)

            # Schedule the server start in the background event loop
            asyncio.run_coroutine_threadsafe(
                self.osc_server.start(), self._network_thread.loop
            )

    def stop_osc(self) -> None:
        """Stop the OSC server and client."""
        with self._lock:
            if self.osc_server is not None:
                # Stop the server asynchronously
                self._network_thread.loop.call_soon_threadsafe(self.osc_server.stop)
                self.osc_server = None
            if self.osc_client is not None:
                self.osc_client.close()
                self.osc_client = None

    def update_osc_client(self, host: str = "", port: int | None = None) -> None:
        """Update client IP or port settings."""
        with self._lock:
            if self.osc_client is not None:
                self.osc_client.target_changed(host, port)

    def update_osc_server(self, server_port: int) -> None:
        """Restart the OSC server on a new port."""
        with self._lock:
            if self.osc_server is not None:
                # Stop the old one
                old_server = self.osc_server
                self._network_thread.loop.call_soon_threadsafe(old_server.stop)

                # Start the new one
                self.osc_server = EngineOSCServer(server_port, engine=self)
                if self._osc_delegate is not None:
                    self.osc_server.register_delegate(self._osc_delegate)
                asyncio.run_coroutine_threadsafe(
                    self.osc_server.start(), self._network_thread.loop
                )

    def register_osc_delegate(self, delegate: object) -> None:
        """Register a delegate for GUI-specific OSC callbacks."""
        with self._lock:
            self._osc_delegate = delegate
            if self.osc_server is not None:
                self.osc_server.register_delegate(delegate)

    def send_osc(self, path: str, *args: object) -> None:
        """Send an OSC message to the client target."""
        with self._lock:
            if self.osc_client is not None:
                self.osc_client.send(path, *args)

    def _send_all(self) -> None:
        """Called by DMXLoop on every tick. Dispatches to senders."""
        # pylint: disable=too-many-locals
        with self._lock:
            active_sync_addresses = set()
            artnet_sync_needed = False

            for slot in self._slots.values():
                for sender in slot.senders:
                    try:
                        sender.send(slot.universe)
                        is_sacn = isinstance(sender, SACNSender)
                        is_artnet = isinstance(sender, ArtNetSender)
                        if is_sacn and getattr(sender, "_sync_address", 0) > 0:
                            active_sync_addresses.add(sender._sync_address)
                        elif is_artnet and getattr(sender, "_sync_active", False):
                            artnet_sync_needed = True
                    except OSError:
                        pass

            # Send a synchronization packet for each active sync address
            if active_sync_addresses and self._sacn_manager is not None:
                for sync_addr in active_sync_addresses:
                    self._sacn_manager.send_sync(sync_addr)

            # Send an ArtSync packet if active
            if artnet_sync_needed and self._artnet_manager is not None:
                self._artnet_manager.send_sync()

            # ZeroMQ Monitoring Publisher
            if self._zmq_pub is None:
                return
            now = time.monotonic()
            if now - self._last_monitor_time < self._monitor_interval:
                return
            self._last_monitor_time = now
            for uid, slot in self._slots.items():
                protocols = []
                if uid in self._map:
                    config = self._map[uid]
                    for p in config.protocols:
                        if p.name == "ARTNET":
                            name = "Art-Net"
                            if config.artnet.sync_active:
                                name += " [bold yellow](Sync)[/bold yellow]"
                            protocols.append(name)
                        elif p.name == "SACN":
                            name = "sACN"
                            if config.sacn.sync_address > 0:
                                name += " [bold yellow](Sync)[/bold yellow]"
                            protocols.append(name)
                        else:
                            protocols.append(p.name)
                metadata = {
                    "hz": self.effective_hz,
                    "frames": self.frame_count,
                    "protocols": protocols,
                }
                meta_bytes = json.dumps(metadata).encode("utf-8")
                topic = f"universe:{uid}".encode("ascii")
                # Multipart: [Topic, Metadata JSON, Raw DMX Bytes]
                self._zmq_pub.send_multipart(
                    [topic, meta_bytes, slot.universe.array.tobytes()]
                )

    def _get_slot(self, uid: int) -> _RuntimeSlot:
        if uid not in self._slots:
            raise KeyError(f"Universe {uid} is not registered in this CoreEngine.")
        return self._slots[uid]

    def _on_artnet_dmx_received(self, universe_id: int, data: list[int]) -> None:
        """Callback when an external ArtDmx packet is received."""
        if self._no_listen:
            return
        try:
            slot = self._get_slot(universe_id)
        except KeyError:
            return

        channels = dict(enumerate(data))
        with self._lock:
            slot.universe.set_channels(channels)

    def _on_sacn_dmx_received(self, universe_id: int, data: list[int]) -> None:
        """Callback when an external sACN packet is received."""
        if self._no_listen:
            return
        try:
            slot = self._get_slot(universe_id)
        except KeyError:
            return

        channels = dict(enumerate(data))
        with self._lock:
            slot.universe.set_channels(channels)
