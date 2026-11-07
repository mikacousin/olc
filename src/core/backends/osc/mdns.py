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
"""mDNS / DNS-SD Service Advertiser for OSC (_osc._udp).

Enables automatic discovery of Open Lighting Console by OSC controllers
(TouchOSC, QLab, Chataigne, etc.) on the local network.
Supports zeroconf package when available, with a resilient pure-python
multicast DNS-SD responder fallback when zeroconf is not installed.
"""

from __future__ import annotations

import logging
import select
import socket
import struct
import threading
import typing

logger = logging.getLogger("olc.osc.mdns")

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
SERVICE_TYPE = "_osc._udp.local."


def _encode_dns_name(name: str) -> bytes:
    """Encode a dotted domain name into DNS wire format."""
    parts = name.strip(".").split(".")
    encoded = bytearray()
    for part in parts:
        part_bytes = part.encode("utf-8")
        encoded.append(len(part_bytes))
        encoded.extend(part_bytes)
    encoded.append(0)
    return bytes(encoded)


def _encode_txt_record(properties: dict[str, str]) -> bytes:
    """Encode a dict of key-value pairs into DNS TXT RDATA wire format."""
    encoded = bytearray()
    for k, v in properties.items():
        entry = f"{k}={v}".encode("utf-8")
        encoded.append(len(entry))
        encoded.extend(entry)
    return bytes(encoded) if encoded else b"\x00"


def _build_response_packet(
    service_name: str,
    port: int,
    hostname: str,
    ip_address: str,
    properties: dict[str, str],
    ttl: int = 120,
) -> bytes:
    """Build a complete DNS-SD response packet for _osc._udp service."""
    # Header: ID=0, Flags=0x8400 (Authoritative Response, No error),
    # Questions=0, Answers=4 (PTR, SRV, TXT, A)
    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 4, 0, 0)

    full_service_name = f"{service_name}.{SERVICE_TYPE}"
    target_host = f"{hostname}.local."

    # 1. PTR Record: _osc._udp.local. -> <service_name>._osc._udp.local.
    ptr_name = _encode_dns_name(SERVICE_TYPE)
    ptr_rdata = _encode_dns_name(full_service_name)
    ptr_rr = (
        ptr_name + struct.pack("!HHIH", 0x000C, 0x0001, ttl, len(ptr_rdata)) + ptr_rdata
    )

    # 2. SRV Record: <service_name>._osc._udp.local. -> Port, Target host
    srv_name = _encode_dns_name(full_service_name)
    target_encoded = _encode_dns_name(target_host)
    srv_rdata = struct.pack("!HHH", 0, 0, port) + target_encoded
    srv_rr = (
        srv_name + struct.pack("!HHIH", 0x0021, 0x8001, ttl, len(srv_rdata)) + srv_rdata
    )

    # 3. TXT Record: Metadata properties
    txt_name = srv_name
    txt_rdata = _encode_txt_record(properties)
    txt_rr = (
        txt_name + struct.pack("!HHIH", 0x0010, 0x8001, ttl, len(txt_rdata)) + txt_rdata
    )

    # 4. A Record: <hostname>.local. -> IPv4
    a_name = target_encoded
    try:
        a_rdata = socket.inet_aton(str(ip_address))
    except (OSError, TypeError):
        a_rdata = socket.inet_aton("127.0.0.1")
    a_rr = a_name + struct.pack("!HHIH", 0x0001, 0x8001, ttl, 4) + a_rdata

    return header + ptr_rr + srv_rr + txt_rr + a_rr


class _NativeMDNSResponder:
    """Lightweight pure-python mDNS responder for DNS-SD service announcement."""

    def __init__(
        self,
        service_name: str,
        port: int,
        properties: dict[str, str],
    ) -> None:
        self.service_name = service_name
        self.port = port
        self.properties = properties
        self.hostname = socket.gethostname().split(".")[0]
        self.ip_address = self._resolve_local_ip()

        self._sock: typing.Optional[socket.socket] = None
        self._thread: typing.Optional[threading.Thread] = None
        self._running = False

    def _resolve_local_ip(self) -> str:
        """Attempt to find primary non-loopback local IPv4 address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("8.8.8.8", 80))
                return probe.getsockname()[0]
        except OSError:
            try:
                return socket.gethostbyname(self.hostname)
            except OSError:
                return "127.0.0.1"

    def start(self) -> bool:
        """Bind multicast UDP socket and start the responder loop."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass

            # Bind to mDNS port
            sock.bind(("", MDNS_PORT))

            # Join multicast group on all interfaces
            mreq = struct.pack("4sl", socket.inet_aton(MDNS_GROUP), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setblocking(False)
            self._sock = sock
        except OSError as err:
            logger.info("Could not bind native mDNS socket on port 5353: %s", err)
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="olc-mdns-responder", daemon=True
        )
        self._thread.start()

        # Announce service immediately on start (unsolicited announcement)
        self._announce(ttl=120)
        return True

    def _announce(self, ttl: int = 120) -> None:
        """Send multicast announcement response packet."""
        if self._sock is None:
            return
        packet = _build_response_packet(
            self.service_name,
            self.port,
            self.hostname,
            self.ip_address,
            self.properties,
            ttl=ttl,
        )
        try:
            self._sock.sendto(packet, (MDNS_GROUP, MDNS_PORT))
        except OSError as err:
            logger.debug("Failed to send mDNS multicast announcement: %s", err)

    def _loop(self) -> None:
        """Listen for incoming queries and answer _osc._udp queries."""
        query_pattern = b"_osc\x04_udp"
        while self._running and self._sock is not None:
            try:
                ready, _, _ = select.select([self._sock], [], [], 1.0)
                if not ready:
                    continue
                data, addr = self._sock.recvfrom(2048)
                if query_pattern in data:
                    # Respond with our service records
                    resp = _build_response_packet(
                        self.service_name,
                        self.port,
                        self.hostname,
                        self.ip_address,
                        self.properties,
                        ttl=120,
                    )
                    self._sock.sendto(resp, (MDNS_GROUP, MDNS_PORT))
            except (OSError, ValueError):
                break

    def stop(self) -> None:
        """Stop responder and announce service farewell (goodbye packet)."""
        if not self._running:
            return
        self._running = False
        # Send goodbye packet with TTL=0
        self._announce(ttl=0)
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)
            self._thread = None


class MDNSAdvertiser:
    """Manages mDNS / DNS-SD service announcement for Open Lighting Console."""

    def __init__(self) -> None:
        self.service_name = "Open Lighting Console"
        self.port: int = 9000
        self.properties: dict[str, str] = {
            "txtvers": "1",
            "name": "Open Lighting Console",
            "model": "OLC",
            "values": "normalized",
        }
        self._active: bool = False
        self._zeroconf_instance: typing.Any = None
        self._service_info: typing.Any = None
        self._native_responder: typing.Optional[_NativeMDNSResponder] = None

    @property
    def is_active(self) -> bool:
        """Whether the service is currently being advertised on mDNS."""
        return self._active

    def start(
        self,
        service_name: str = "Open Lighting Console",
        port: int = 9000,
        extra_properties: dict[str, str] | None = None,
    ) -> bool:
        """Advertise the OSC service on the network.

        Args:
            service_name: Visible service instance name.
            port: OSC server listening UDP port.
            extra_properties: Additional TXT record key-values.

        Returns:
            True if advertising started successfully, False otherwise.
        """
        if self._active:
            self.stop()

        self.service_name = service_name
        self.port = port
        if extra_properties:
            self.properties.update(extra_properties)

        # 1. Try python-zeroconf package first if available
        try:
            from zeroconf import ServiceInfo, Zeroconf  # type: ignore

            zc = Zeroconf()
            hostname = socket.gethostname().split(".")[0]
            server_fqdn = f"{hostname}.local."
            info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=f"{self.service_name}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton("0.0.0.0")],
                port=self.port,
                properties=self.properties,
                server=server_fqdn,
            )
            zc.register_service(info)
            self._zeroconf_instance = zc
            self._service_info = info
            self._active = True
            logger.info(
                "mDNS service '%s' registered via zeroconf library on port %d",
                self.service_name,
                self.port,
            )
            return True
        except (ImportError, Exception) as err:  # pylint: disable=broad-exception-caught
            logger.debug(
                "Zeroconf library not available or failed: %s. Using native responder.",
                err,
            )

        # 2. Fallback to native pure-python responder
        responder = _NativeMDNSResponder(
            service_name=self.service_name,
            port=self.port,
            properties=self.properties,
        )
        if responder.start():
            self._native_responder = responder
            self._active = True
            logger.info(
                "mDNS service '%s' registered via native responder on port %d",
                self.service_name,
                self.port,
            )
            return True

        self._active = False
        return False

    def stop(self) -> None:
        """Stop advertising the service and send goodbye records."""
        if not self._active:
            return

        if self._zeroconf_instance is not None and self._service_info is not None:
            try:
                self._zeroconf_instance.unregister_service(self._service_info)
                self._zeroconf_instance.close()
            except Exception as err:  # pylint: disable=broad-exception-caught
                logger.debug("Error while closing zeroconf: %s", err)
            self._zeroconf_instance = None
            self._service_info = None

        if self._native_responder is not None:
            self._native_responder.stop()
            self._native_responder = None

        self._active = False
        logger.info("mDNS service '%s' unregistered.", self.service_name)
