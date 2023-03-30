# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
import array
import socket
import subprocess
import sys
import threading
import time
from typing import Optional
from functools import partial

from gi.repository import GLib
from ola import OlaClient
from ola.ClientWrapper import ClientWrapper
from olc.define import NB_UNIVERSES, App


class OlaThread(threading.Thread):
    """Create OlaClient and receive universes updates"""

    ola_client: OlaClient.OlaClient
    sock: OlaClient.OlaClient.GetSocket

    def __init__(self) -> None:
        threading.Thread.__init__(self)
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()

        self.old_frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]

    def run(self) -> None:
        """Register universes"""
        for univ in App().universes:
            self.ola_client.RegisterUniverse(
                univ, self.ola_client.REGISTER, partial(self.on_dmx, univ)
            )

    def on_dmx(self, univ: int, dmxframe: array.array) -> None:
        """Universe updates.

        Args:
            univ (int): universe
            dmxframe (array): 512 bytes with levels outputs
        """
        idx = App().universes.index(univ)
        if App().tabs.tabs["patch_outputs"]:
            # Find diff between old and new DMX frames
            diff = [
                (index, e1)
                for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[idx]))
                if e1 != e2
            ]
            # Loop on outputs with different level
            for output, level in diff:
                if App().patch.outputs.get(univ) and App().patch.outputs[univ].get(
                    output + 1
                ):
                    GLib.idle_add(
                        App()
                        .tabs.tabs["patch_outputs"]
                        .outputs[output + (idx * 512)]
                        .queue_draw
                    )
        # Save DMX frame for next call
        self.old_frame[idx] = dmxframe


class Ola:
    """To manage ola daemon"""

    olad_pid: Optional[subprocess.Popen]
    olad_port: int
    ola_thread: OlaThread

    def __init__(self, olad_port=9090):
        self.olad_port = olad_port

    def start(self):
        """Start ola daemon"""
        # Create OlaClient and start olad if needed
        try:
            self.ola_thread = OlaThread()
            self.olad_pid = None
        except OlaClient.OLADNotRunningException:
            if _is_port_in_use(self.olad_port):
                print(f"Olad port {self.olad_port} already in use")
                sys.exit()
            # Launch olad if not running
            self.olad_pid = subprocess.Popen(
                ["olad", "--http-port", str(self.olad_port)]
            )
            # Wait olad starting
            timeout = 15
            timer = 0.0
            wrapper = None
            while not wrapper:
                try:
                    wrapper = ClientWrapper()
                except (OlaClient.OLADNotRunningException, ConnectionError):
                    time.sleep(0.1)
                    timer += 0.1
                    if timer >= timeout:
                        print("Can't start olad")
                        break
            self.ola_thread = OlaThread()
        self.ola_thread.start()

    def stop(self) -> None:
        """Stop olad if we launched it"""
        if self.olad_pid:
            self.olad_pid.terminate()


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serversocket:
        return serversocket.connect_ex(("127.0.0.1", port)) == 0
