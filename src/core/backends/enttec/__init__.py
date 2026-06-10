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
"""Manager for ENTTEC DMX USB PRO output and connection state."""

from __future__ import annotations

import asyncio
import os
from typing import Callable

import serial
import serial.tools.list_ports


class DmxUsbProManager:
    """
    Manages ENTTEC DMX USB PRO serial connections, auto-detection,
    asyncio read loops, and error recovery for CoreEngine.
    """

    def __init__(
        self,
        port: str = "Auto-detect",
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize connection parameters."""
        self.port = port
        self.loop = loop
        self._serial = None
        self._actual_port = None
        self._connected = False
        self._reconnect_task = None
        self.notify: Callable[[str, *object], None] | None = None

    def start(self) -> None:
        """Start the background connection task."""
        if self.loop and self.loop.is_running():
            self.loop.create_task(self._async_connect(is_initial=True))

    async def _async_connect(self, is_initial: bool = False) -> None:
        """Attempt to open the serial connection or search for compatible ports."""
        if self._connected:
            return

        port_to_open = self.port
        if port_to_open == "Auto-detect":
            try:
                detected_ports = [
                    p.device
                    for p in serial.tools.list_ports.comports()
                    if p.vid == 0x0403 and p.pid == 0x6001
                ]
                if detected_ports:
                    port_to_open = detected_ports[0]
                else:
                    return
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[DMX USB PRO] Error listing ports: {e}")
                return

        try:
            # Open port in non-blocking mode or with timeouts
            self._serial = serial.Serial(
                port=port_to_open,
                baudrate=57600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0,  # non-blocking reads
                write_timeout=0.01,  # very short write timeout so engine doesn't jitter
            )
            self._actual_port = port_to_open
            self._connected = True
            if self.notify is not None:
                self.notify("connect", port_to_open)

            # Register reader on loop
            if self.loop:
                self.loop.add_reader(self._serial.fileno(), self._on_bytes_received)
        except Exception as e:  # pylint: disable=broad-exception-caught
            if is_initial:
                if self.notify is not None:
                    self.notify("connect-fail", port_to_open, str(e))
            else:
                print(f"[DMX USB PRO] Failed to connect to {port_to_open}: {e}")

    def _schedule_reconnect(self) -> None:
        """Schedule a background reconnection task if none is active."""
        if self.loop and self.loop.is_running():
            if self._reconnect_task is None or self._reconnect_task.done():
                self._reconnect_task = self.loop.create_task(self._async_reconnect())

    async def _async_reconnect(self) -> None:
        """Loop trying to reconnect to the serial port periodically."""
        while not self._connected:
            await asyncio.sleep(2.0)
            try:
                await self._async_connect(is_initial=False)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[DMX USB PRO] Reconnection attempt failed: {e}")

    def _on_bytes_received(self) -> None:
        """Callback triggered when the serial file descriptor is marked readable."""
        if not self._serial or not self._serial.is_open:
            return
        try:
            # Drain incoming bytes
            in_waiting = self._serial.in_waiting
            if in_waiting > 0:
                self._serial.read(in_waiting)
            else:
                # Descriptor was marked readable, but 0 bytes available.
                # Check if device was unplugged
                if self._actual_port and not os.path.exists(self._actual_port):
                    raise OSError("USB serial device unplugged (path disappeared)")
        except Exception as e:  # pylint: disable=broad-exception-caught
            if self.loop:
                self.loop.call_soon_threadsafe(self._handle_disconnect, e)

    def _handle_disconnect(self, error: Exception) -> None:
        """Perform cleanup and schedule reconnection when connection is lost."""
        if self.notify is not None:
            self.notify("disconnect", self._actual_port or "Unknown port", str(error))
        self.stop()
        self._schedule_reconnect()

    def write_packet(self, packet: bytes) -> None:
        """Write a formatted packet directly to the serial port."""
        if not self._connected or self._serial is None:
            return

        try:
            self._serial.write(packet)
            self._serial.flush()
        except Exception as e:  # pylint: disable=broad-exception-caught
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(self._handle_disconnect, e)
            else:
                self.stop()

    def stop(self) -> None:
        """Stop connection, release resources and cancel reconnect task."""
        self._connected = False
        if self.loop and self._serial:
            try:
                self.loop.remove_reader(self._serial.fileno())
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        if self._serial:
            try:
                self._serial.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._serial = None
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
