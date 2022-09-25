# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
import socket

from gi.repository import Gdk, GLib
from olc.define import App


class WingPlayback:
    """Enttec Wing Playback"""

    def __init__(self):
        self.old_message = bytes(28)

        self.address = ("", 3330)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.address)

        self.fd = self.sock.fileno()

        GLib.unix_fd_add_full(
            0, self.fd, GLib.IOCondition.IN, self.incoming_connection_cb, None
        )

    def incoming_connection_cb(self, _fd, _condition, _data):
        """Listen messages

        Returns:
            True
        """
        message = self.sock.recv(1024)
        if message[:4] == b"WODD":
            # print("Wing output data", message[0:4])
            # print("Wing firmware :", message[4])
            # print("Wing flags :", message[5])

            # Go
            if not message[6] & 16:
                # Go pressed
                App().sequence.do_go(None, None)
                # if message[6] & 16: Go is released
            # Back
            if not message[6] & 32:
                # Back pressed
                App().sequence.go_back(None, None)
            # message[6] & 64: PageDown
            # message[6] & 128: PageUp
            # TODO: Flashes don't work
            """
            if message[7] & 1:
                # Flash 10 (Key 39) released")
                _function_flash(False, 10)
            else:
                # Flash 10 (Key 39) pressed")
                _function_flash(True, 10)
            if message[7] & 2:
                # Flash 9 (Key 38) released")
                _function_flash(False, 9)
            else:
                # Flash 9 (Key 38) pressed")
                _function_flash(True, 9)
            if message[7] & 4:
                # Flash 8 (Key 37) released")
                _function_flash(False, 8)
            else:
                # Flash 8 (Key 37) pressed")
                _function_flash(True, 8)
            if message[7] & 8:
                # Flash 7 (Key 36) released")
                _function_flash(False, 7)
            else:
                # Flash 7 (Key 36) pressed")
                _function_flash(True, 7)
            if message[7] & 16:
                # Flash 6 (Key 35) released")
                _function_flash(False, 6)
            else:
                # Flash 6 (Key 35) pressed")
                _function_flash(True, 6)
            if message[7] & 32:
                # Flash 5 (Key 34) released")
                _function_flash(False, 5)
            else:
                # Flash 5 (Key 34) pressed")
                _function_flash(True, 5)
            if message[7] & 64:
                # Flash 4 (Key 33) released")
                _function_flash(False, 4)
            else:
                # Flash 4 (Key 33) pressed")
                _function_flash(True, 4)
            if message[7] & 128:
                # Flash 3 (Key 32) released")
                _function_flash(False, 3)
            else:
                # Flash 3 (Key 32) pressed")
                _function_flash(True, 3)
            if message[8] & 1:
                # Flash 2 (Key 31) released")
                _function_flash(False, 2)
            else:
                # Flash 2 (Key 31) pressed")
                _function_flash(True, 2)
            if message[8] & 2:
                # Flash 1 (Key 30) released
                _function_flash(False, 1)
            else:
                # Flash 1 (Key 30) pressed
                _function_flash(True, 1)
            """

            # Faders
            if App().virtual_console:
                for i in range(10):
                    if self.old_message[i + 15] != message[i + 15]:
                        App().virtual_console.masters[i].set_value(message[i + 15])
                        App().virtual_console.master_moved(
                            App().virtual_console.masters[i]
                        )
            else:
                for i in range(10):
                    if self.old_message[i + 15] != message[i + 15]:
                        App().masters[i].set_level(int(message[i + 15]))

            self.old_message = message

        return True


def _function_flash(pressed, master_index):
    """Flash Master

    Args:
        pressed: Button pressed or released
        master_index: Master number
    """
    if pressed:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.flashes[master_index - 1].emit(
                "button-press-event", event
            )
        else:
            master = None
            for master in App().masters:
                if master.page == App().fader_page and master.number == master_index:
                    break
            master.old_value = master.value
            master.set_level(255)
    elif App().virtual_console:
        event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
        App().virtual_console.flashes[master_index - 1].emit(
            "button-release-event", event
        )
    else:
        master = None
        for master in App().masters:
            if master.page == App().fader_page and master.number == master_index:
                break
        master.set_level(master.old_value)
