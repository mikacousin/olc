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
from typing import Any, Callable

import serial
import serial.tools.list_ports


def resolve_port(port: str) -> str:
    """Resolve 'Auto-detect' to the first compatible FTDI serial port."""
    if port == "Auto-detect":
        try:
            detected_ports = [
                p.device
                for p in serial.tools.list_ports.comports()
                if p.vid == 0x0403 and p.pid == 0x6001
            ]
            if detected_ports:
                return detected_ports[0]
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[DMX USB PRO] Error resolving Auto-detect port: {e}")
    return port


# pylint: disable=too-many-instance-attributes
class DmxUsbProManager:
    """
    Manages ENTTEC DMX USB PRO serial connections, auto-detection,
    asyncio read loops, and error recovery for CoreEngine.
    """

    def __init__(
        self,
        port: str = "Auto-detect",
        loop: asyncio.AbstractEventLoop | None = None,
        configs_provider: Callable[[], list[Any]] | None = None,
    ) -> None:
        """Initialize connection parameters."""
        self.port = port
        self.loop = loop
        self.configs_provider = configs_provider
        self._serial = None
        self._actual_port = None
        self._connected = False
        self._reconnect_task = None
        self.notify: Callable[[str, *object], None] | None = None

    @property
    def is_connected(self) -> bool:
        """Return True if the manager is currently connected to the serial port."""
        return self._connected

    def start(self) -> None:
        """Start the background connection task."""
        if self.loop and self.loop.is_running():
            self.loop.create_task(self._async_connect(is_initial=True))

    def _is_mk2(self) -> bool:
        """Determine if the device is an Enttec DMX USB Pro MK2."""
        if self.configs_provider:
            configs = self.configs_provider()
            if any(getattr(cfg, "model", "Auto-detect") == "Pro V1" for cfg in configs):
                return False
            if any(
                getattr(cfg, "model", "Auto-detect") == "Pro Mk2"
                or getattr(cfg, "port_index", 1) == 2
                for cfg in configs
            ):
                return True

        if self._actual_port:
            try:
                actual_real = os.path.realpath(self._actual_port)
                for p in serial.tools.list_ports.comports():
                    p_real = os.path.realpath(p.device)
                    if p_real == actual_real or p.device == self._actual_port:
                        desc = (p.description or "").upper()
                        prod = (p.product or "").upper()
                        if (
                            "MK2" in desc
                            or "MK2" in prod
                            or "MK II" in desc
                            or "MK II" in prod
                        ):
                            return True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[DMX USB PRO] Error checking port descriptions: {e}")
        return False

    async def _async_connect(self, is_initial: bool = False) -> None:
        """Attempt to open the serial connection or search for compatible ports."""
        if self._connected:
            return

        port_to_open = resolve_port(self.port)
        if port_to_open == "Auto-detect":
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
                write_timeout=0.5,
            )
            # Clear RTS line
            try:
                self._serial.rts = False
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[DMX USB PRO] Warning: could not clear RTS line: {e}")

            # Flush any residual input data
            self._serial.reset_input_buffer()

            self._actual_port = port_to_open
            self._connected = True

            is_mk2 = self._is_mk2()
            print(
                f"[DMX USB PRO] Connected to {port_to_open} (Detected model: "
                f"{'Pro Mk2' if is_mk2 else 'Pro V1'})"
            )

            # If it is a Pro Mk2, initialize API2 mode and enable both ports as outputs
            if is_mk2:
                # Wait for serial line to settle
                await asyncio.sleep(0.15)
                # API2 key activation:
                # SOM, 0x0D, 0x04, 0x00, 0xAD, 0x88, 0xD0, 0xC8, EOM
                self._serial.write(b"\x7e\x0d\x04\x00\xad\x88\xd0\xc8\xe7")
                self._serial.flush()
                await asyncio.sleep(0.05)
                # Port assignment request: SOM, 0xCB, 0x02, 0x00, 0x01, 0x01, EOM
                self._serial.write(b"\x7e\xcb\x02\x00\x01\x01\xe7")
                self._serial.flush()

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
            print(f"[DMX USB PRO] Write error on {self._actual_port or 'port'}: {e}")
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
