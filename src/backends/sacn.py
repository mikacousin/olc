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
import sacn
from gi.repository import GLib
from olc.backends import DMXBackend
from olc.define import App, NB_UNIVERSES, UNIVERSES


class Sacn(DMXBackend):
    """Sacn Backend"""

    sender: sacn.sACNsender
    receiver: sacn.sACNreceiver
    old_frame: list[tuple[int]]

    def __init__(self):
        self.sender = sacn.sACNsender()
        self.sender.start()
        self.receiver = sacn.sACNreceiver()
        self.receiver.start()
        for universe in UNIVERSES:
            self.sender.activate_output(universe)
            self.sender[universe].multicast = True
            self.receiver.join_multicast(universe)
            self.receiver.register_listener(
                "universe", self.receive_packet, universe=universe
            )
        self.old_frame = [(0,) * 512 for _ in range(NB_UNIVERSES)]
        super().__init__()

    def stop(self) -> None:
        """Stop sACN backend"""
        super().stop()
        self.sender.stop()
        for universe in UNIVERSES:
            self.receiver.leave_multicast(universe)
        self.receiver.stop()

    def send(self, universe: int, index: int) -> None:
        """Send sACN universe

        Args:
            universe: one in UNIVERSES
            index: Index of universe
        """
        self.sender[universe].dmx_data = tuple(self.dmx.frame[index])

    def receive_packet(self, packet: sacn.DataPacket) -> None:
        """Callback when receive sACN packets

        Args:
            packet: sACN data
        """
        univ = packet.universe
        idx = UNIVERSES.index(univ)
        if App().tabs.tabs["patch_outputs"]:
            # Find diff between old and new DMX frames
            outputs = [
                index
                for index, (e1, e2) in enumerate(
                    zip(packet.dmxData, self.old_frame[idx])
                )
                if e1 != e2
            ]
            # Loop on outputs with different level
            for output in outputs:
                if self.patch.outputs.get(univ) and self.patch.outputs[univ].get(
                    output + 1
                ):
                    GLib.idle_add(
                        App()
                        .tabs.tabs["patch_outputs"]
                        .outputs[output + (idx * 512)]
                        .queue_draw
                    )
        # Save DMX frame for next call
        self.old_frame[idx] = packet.dmxData
