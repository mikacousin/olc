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
# pylint: disable=protected-access,comparison-with-callable
import asyncio
import typing
from unittest.mock import MagicMock, patch

import serial
from olc.core.backends.enttec import DmxUsbProManager
from olc.core.senders import DmxUsbProSender
from olc.core.universe_data import DMXUniverse


class TestDmxUsbProManager:
    """Exhaustive test suite for DmxUsbProManager."""

    def test_init(self) -> None:
        """Verify that parameters are correctly initialized."""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        assert manager.port == "/dev/ttyUSB0"
        assert manager.loop is loop
        assert manager._serial is None
        assert manager._actual_port is None
        assert manager._connected is False
        assert manager._reconnect_task is None

    @patch("serial.Serial")
    def test_connect_specific_port_success(self, mock_serial_class: MagicMock) -> None:
        """Verify connection to a specific port is successful."""
        mock_serial = MagicMock()
        mock_serial.fileno.return_value = 10
        mock_serial_class.return_value = mock_serial

        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        manager = DmxUsbProManager(port="/dev/ttyUSB99", loop=loop)
        mock_notify = MagicMock()
        manager.notify = mock_notify

        # Call connect synchronously for test
        loop.run_until_complete = MagicMock()
        asyncio.run(manager._async_connect(is_initial=True))

        assert manager._connected is True
        assert manager._actual_port == "/dev/ttyUSB99"
        assert manager._serial is mock_serial
        mock_notify.assert_called_once_with("connect", "/dev/ttyUSB99")
        mock_serial_class.assert_called_once_with(
            port="/dev/ttyUSB99",
            baudrate=57600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=0.01,
        )
        loop.add_reader.assert_called_once_with(10, manager._on_bytes_received)

    @patch("serial.Serial")
    def test_connect_already_connected(self, mock_serial_class: MagicMock) -> None:
        """Verify connecting when already connected is a no-op."""
        manager = DmxUsbProManager(port="/dev/ttyUSB99")
        manager._connected = True
        asyncio.run(manager._async_connect())
        mock_serial_class.assert_not_called()

    @patch("serial.tools.list_ports.comports")
    @patch("serial.Serial")
    def test_connect_autodetect_found(
        self, mock_serial_class: MagicMock, mock_comports: MagicMock
    ) -> None:
        """Verify auto-detect finds the compatible FTDI port and connects."""
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyUSB_auto"
        mock_port.vid = 0x0403
        mock_port.pid = 0x6001
        mock_comports.return_value = [mock_port]

        mock_serial = MagicMock()
        mock_serial.fileno.return_value = 12
        mock_serial_class.return_value = mock_serial

        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        manager = DmxUsbProManager(port="Auto-detect", loop=loop)

        asyncio.run(manager._async_connect())

        assert manager._connected is True
        assert manager._actual_port == "/dev/ttyUSB_auto"
        mock_serial_class.assert_called_once()
        assert mock_serial_class.call_args[1]["port"] == "/dev/ttyUSB_auto"

    @patch("serial.tools.list_ports.comports")
    @patch("serial.Serial")
    def test_connect_autodetect_not_found(
        self, mock_serial_class: MagicMock, mock_comports: MagicMock
    ) -> None:
        """Verify auto-detect returns early if no compatible port is found."""
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyUSB_other"
        mock_port.vid = 0x1234
        mock_comports.return_value = [mock_port]

        manager = DmxUsbProManager(port="Auto-detect")
        asyncio.run(manager._async_connect())

        assert manager._connected is False
        mock_serial_class.assert_not_called()

    @patch("serial.tools.list_ports.comports")
    def test_connect_autodetect_exception_caught(
        self, mock_comports: MagicMock
    ) -> None:
        """Verify auto-detect logs and handles exception safely on list_ports error."""
        mock_comports.side_effect = Exception("System list ports failure")

        manager = DmxUsbProManager(port="Auto-detect")
        # Should not raise exception
        asyncio.run(manager._async_connect())
        assert manager._connected is False

    @patch("serial.Serial")
    def test_connect_failure_caught(self, mock_serial_class: MagicMock) -> None:
        """Verify connect catches SerialException safely and remains disconnected."""
        mock_serial_class.side_effect = Exception("Permission denied")

        manager = DmxUsbProManager(port="/dev/ttyUSB0")
        mock_notify = MagicMock()
        manager.notify = mock_notify

        # Should not raise exception
        asyncio.run(manager._async_connect(is_initial=True))
        assert manager._connected is False
        assert manager._serial is None
        mock_notify.assert_called_once_with(
            "connect-fail", "/dev/ttyUSB0", "Permission denied"
        )

    def test_start(self) -> None:
        """Verify start() schedules connect on event loop."""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.is_running.return_value = True

        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        manager.start()
        loop.create_task.assert_called_once()
        loop.create_task.call_args[0][0].close()

    def test_schedule_reconnect(self) -> None:
        """Verify _schedule_reconnect schedules reconnect task."""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.is_running.return_value = True

        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        assert manager._reconnect_task is None

        manager._schedule_reconnect()
        assert manager._reconnect_task is not None
        loop.create_task.assert_called_once()
        loop.create_task.call_args[0][0].close()

        # Scheduling again when task exists and not done does not schedule a new task
        manager._reconnect_task.done = MagicMock(return_value=False)
        loop.create_task.reset_mock()
        manager._schedule_reconnect()
        loop.create_task.assert_not_called()

    @patch("asyncio.sleep")
    def test_async_reconnect_loop(self, mock_sleep: MagicMock) -> None:
        """Verify that the reconnect task loops until connection succeeds."""
        mock_sleep.return_value = None  # don't actually sleep

        manager = DmxUsbProManager(port="/dev/ttyUSB0")
        mock_notify = MagicMock()
        manager.notify = mock_notify
        connect_call_count = 0

        async def fake_connect(is_initial: bool = False) -> None:  # pylint: disable=unused-argument
            nonlocal connect_call_count
            connect_call_count += 1
            if connect_call_count >= 3:
                manager._connected = True
                if manager.notify is not None:
                    manager.notify("connect", "/dev/ttyUSB0")

        typing.cast(typing.Any, manager)._async_connect = fake_connect
        asyncio.run(manager._async_reconnect())

        assert connect_call_count == 3
        assert manager._connected is True
        mock_notify.assert_called_once_with("connect", "/dev/ttyUSB0")

    def test_on_bytes_received_drain(self) -> None:
        """Verify _on_bytes_received drains serial input when bytes are available."""
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 42

        manager = DmxUsbProManager(port="/dev/ttyUSB0")
        manager._serial = mock_serial

        manager._on_bytes_received()
        mock_serial.read.assert_called_once_with(42)

    @patch("os.path.exists")
    def test_on_bytes_received_unplug_detected(self, mock_exists: MagicMock) -> None:
        """Verify _on_bytes_received detects device unplug and handles disconnect."""
        mock_exists.return_value = False  # path disappeared!
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.in_waiting = 0

        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        manager._serial = mock_serial
        manager._actual_port = "/dev/ttyUSB0"

        # Should schedule _handle_disconnect on the loop
        manager._on_bytes_received()
        loop.call_soon_threadsafe.assert_called_once()
        args = loop.call_soon_threadsafe.call_args[0]
        assert args[0] == manager._handle_disconnect
        assert isinstance(args[1], OSError)

    def test_handle_disconnect(self) -> None:
        """Verify disconnect stops connection and schedules reconnect."""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.is_running.return_value = True

        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        manager._connected = True
        manager._actual_port = "/dev/ttyUSB0"
        mock_notify = MagicMock()
        manager.notify = mock_notify
        typing.cast(typing.Any, manager).stop = MagicMock()
        typing.cast(typing.Any, manager)._schedule_reconnect = MagicMock()

        manager._handle_disconnect(OSError("Lost connection"))

        mock_notify.assert_called_once_with(
            "disconnect", "/dev/ttyUSB0", "Lost connection"
        )
        typing.cast(typing.Any, manager).stop.assert_called_once()
        typing.cast(typing.Any, manager)._schedule_reconnect.assert_called_once()

    def test_write_packet_not_connected(self) -> None:
        """Verify write_packet returns early without writing if not connected."""
        mock_serial = MagicMock()
        manager = DmxUsbProManager(port="/dev/ttyUSB0")
        manager._serial = mock_serial
        manager._connected = False

        manager.write_packet(b"\x7e\x06\x00\xe7")
        mock_serial.write.assert_not_called()

    def test_write_packet_success(self) -> None:
        """Verify write_packet writes and flushes packet when connected."""
        mock_serial = MagicMock()
        manager = DmxUsbProManager(port="/dev/ttyUSB0")
        manager._serial = mock_serial
        manager._connected = True

        packet = b"\x7e\x06\x00\xe7"
        manager.write_packet(packet)
        mock_serial.write.assert_called_once_with(packet)
        mock_serial.flush.assert_called_once()

    def test_write_packet_exception_with_loop(self) -> None:
        """Verify write exception schedules disconnect on event loop."""
        mock_serial = MagicMock()
        mock_serial.write.side_effect = Exception("Write failed")

        loop = MagicMock(spec=asyncio.AbstractEventLoop)
        loop.is_running.return_value = True

        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        manager._serial = mock_serial
        manager._connected = True

        manager.write_packet(b"\x7e\x06\x00\xe7")
        loop.call_soon_threadsafe.assert_called_once()
        args = loop.call_soon_threadsafe.call_args[0]
        assert args[0] == manager._handle_disconnect

    def test_write_packet_exception_without_loop(self) -> None:
        """Verify write exception stops manager immediately if loop not active."""
        mock_serial = MagicMock()
        mock_serial.write.side_effect = Exception("Write failed")

        manager = DmxUsbProManager(port="/dev/ttyUSB0")
        manager._serial = mock_serial
        manager._connected = True
        typing.cast(typing.Any, manager).stop = MagicMock()

        manager.write_packet(b"\x7e\x06\x00\xe7")
        typing.cast(typing.Any, manager).stop.assert_called_once()

    def test_stop(self) -> None:
        """Verify stop cleans up serial port, reader, and reconnect tasks."""
        mock_serial = MagicMock()
        mock_serial.fileno.return_value = 14

        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        manager = DmxUsbProManager(port="/dev/ttyUSB0", loop=loop)
        manager._serial = mock_serial
        manager._connected = True

        mock_task = MagicMock()
        manager._reconnect_task = mock_task

        manager.stop()

        assert manager._connected is False
        assert manager._serial is None
        loop.remove_reader.assert_called_once_with(14)
        mock_serial.close.assert_called_once()
        mock_task.cancel.assert_called_once()


class TestDmxUsbProSender:
    """Exhaustive test suite for DmxUsbProSender."""

    def test_sender_formats_packet_and_delegates(self) -> None:
        """Verify that send() formats the ENTTEC packet correctly and sends it."""
        mock_manager = MagicMock(spec=DmxUsbProManager)
        sender = DmxUsbProSender(manager=mock_manager)

        univ = DMXUniverse()
        univ[0] = 255
        univ[1] = 128
        univ[2] = 64

        sender.send(univ)

        mock_manager.write_packet.assert_called_once()
        packet = mock_manager.write_packet.call_args[0][0]

        # ENTTEC DMX USB PRO Format:
        # 0x7E, 6 (TX DMX), Length LSB/MSB, 0x00 (Start code), DMX, 0xE7
        assert packet[0] == 0x7E  # Start delimiter
        assert packet[1] == 6  # TX Label
        assert packet[2] == 0x01  # Length LSB (513 & 0xFF)
        assert packet[3] == 0x02  # Length MSB (513 >> 8)
        assert packet[4] == 0x00  # Start code

        # DMX data verification
        assert packet[5] == 255
        assert packet[6] == 128
        assert packet[7] == 64

        # End delimiter
        assert packet[-1] == 0xE7

    def test_sender_handles_exceptions_gracefully(self) -> None:
        """Verify sender catches write errors and doesn't crash."""
        mock_manager = MagicMock(spec=DmxUsbProManager)
        mock_manager.write_packet.side_effect = Exception("Serial connection dead")

        sender = DmxUsbProSender(manager=mock_manager)
        univ = DMXUniverse()

        # Should not raise exception
        sender.send(univ)
        mock_manager.write_packet.assert_called_once()

    def test_sender_close(self) -> None:
        """Verify close is callable."""
        mock_manager = MagicMock(spec=DmxUsbProManager)
        sender = DmxUsbProSender(manager=mock_manager)
        sender.close()
