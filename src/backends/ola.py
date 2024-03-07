# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from functools import partial
from typing import Optional

from gi.repository import GLib
from ola import OlaClient
from ola.ClientWrapper import ClientWrapper
from olc.backends import DMXBackend
from olc.define import NB_UNIVERSES, UNIVERSES, App
from olc.patch import DMXPatch


class OlaThread(threading.Thread):
    """Create OlaClient and receive universes updates"""

    wrapper: ClientWrapper
    client: OlaClient.OlaClient
    old_frame: list[array.array]
    patch: DMXPatch

    def __init__(self, patch: DMXPatch):
        super().__init__()
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()
        self.old_frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]
        self.patch = patch

    def run(self) -> None:
        """Register universes"""
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()
        for univ in UNIVERSES:
            self.client.RegisterUniverse(univ, self.client.REGISTER,
                                         partial(self.on_dmx, univ))
        self.wrapper.Run()

    def on_dmx(self, univ: int, dmxframe: array.array) -> None:
        """Executed when ola detect universe update

        Args:
            univ: universe
            dmxframe: 512 bytes with levels outputs
        """
        idx = UNIVERSES.index(univ)
        if App().tabs.tabs["patch_outputs"]:
            # Find diff between old and new DMX frames
            outputs = [
                index
                for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[idx]))
                if e1 != e2
            ]
            # Loop on outputs with different level
            for output in outputs:
                if self.patch.outputs.get(univ) and self.patch.outputs[univ].get(
                        output + 1):
                    GLib.idle_add(
                        App().tabs.tabs["patch_outputs"].outputs[output +
                                                                 (idx *
                                                                  512)].queue_draw)
        # Save DMX frame for next call
        self.old_frame[idx] = dmxframe

    def fetch_dmx(self, status: OlaClient.RequestStatus, univ: int,
                  dmxframe: array.array) -> None:
        """Fetch DMX

        Args:
            status: RequestStatus
            univ: DMX universe
            dmxframe: DMX data
        """
        if not status.Succeeded() or not dmxframe:
            return
        index = UNIVERSES.index(univ)
        self.old_frame[index] = dmxframe
        for output, level in enumerate(dmxframe):
            if univ in self.patch.outputs and output + 1 in self.patch.outputs[univ]:
                channel = self.patch.outputs.get(univ).get(output + 1)[0]
                App().backend.dmx.frame[index][output] = level
                next_level = App().lightshow.main_playback.get_next_channel_level(
                    channel, level)
                App().window.live_view.update_channel_widget(channel, next_level)
                if App().tabs.tabs["patch_outputs"]:
                    App().tabs.tabs["patch_outputs"].outputs[output +
                                                             (512 *
                                                              index)].queue_draw()


class Ola(DMXBackend):
    """Ola Backend"""

    olad_port: int
    olad_pid: Optional[subprocess.Popen]
    thread: OlaThread | None

    def __init__(self, patch, olad_port: int = 9090):
        super().__init__(patch)
        self.thread = None
        self.olad_port = olad_port
        self.olad_pid = None

        # Create OlaClient and start olad if needed
        try:
            self.thread = OlaThread(self.patch)
            self.olad_pid = None
        except OlaClient.OLADNotRunningException:
            if _is_port_in_use(self.olad_port):
                print(f"Olad port {self.olad_port} already in use")
                sys.exit()
            # Launch olad if not running
            cmd = ["olad", "--http-port", str(self.olad_port)]
            self.olad_pid = subprocess.Popen(cmd)  # pylint: disable=R1732
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
            self.thread = OlaThread(self.patch)
        self.thread.start()

    def stop(self) -> None:
        """Stop Ola backend"""
        super().stop()
        if self.thread:
            self.thread.wrapper.Stop()
        # Stop olad if we launched it
        if self.olad_pid:
            self.olad_pid.terminate()

    def send(self, universe: int, index: int) -> None:
        """Send DMX universe

        Args:
            universe: one in UNIVERSES
            index: Index of universe
        """
        if self.thread:
            self.thread.client.SendDmx(universe, self.dmx.frame[index])


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serversocket:
        return serversocket.connect_ex(("127.0.0.1", port)) == 0
