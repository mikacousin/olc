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
from __future__ import annotations

import typing

import sacn
from gi.repository import GLib
from olc.backends import DMXBackend
from olc.define import NB_UNIVERSES, UNIVERSES

if typing.TYPE_CHECKING:
    from olc.lightshow import LightShow


class Sacn(DMXBackend):
    """Sacn Backend"""

    sender: sacn.sACNsender
    receiver: sacn.sACNreceiver
    old_frame: list[tuple[int, ...]]

    def __init__(self, lightshow: LightShow) -> None:
        self.sender = sacn.sACNsender()
        self.sender.start()
        self.receiver = sacn.sACNreceiver()
        self.receiver.start()
        for universe in UNIVERSES:
            try:
                self.receiver.join_multicast(universe)
            except OSError as error:
                print(f"sACN Network error, starting in offline mode: {error}")
                break

            self.sender.activate_output(universe)
            if sender := self.sender[universe]:
                sender.multicast = True
            self.receiver.register_listener(
                "universe", self.receive_packet, universe=universe
            )
        self.old_frame = [(0,) * 512 for _ in range(NB_UNIVERSES)]
        super().__init__(lightshow)

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
        if sender := self.sender[universe]:
            sender.dmx_data = tuple(self.dmx.frame[index])

    def receive_packet(self, packet: sacn.DataPacket) -> None:
        """Callback when receive sACN packets

        Args:
            packet: sACN data
        """
        univ = packet.universe
        idx = UNIVERSES.index(univ)
        # Find diff between old and new DMX frames
        outputs = [
            index
            for index, (e1, e2) in enumerate(
                zip(packet.dmxData, self.old_frame[idx], strict=True)
            )
            if e1 != e2
        ]
        if outputs:
            dmx = typing.cast(typing.Any, self.dmx)
            GLib.idle_add(dmx.trigger_output_callbacks, univ, outputs)
        # Save DMX frame for next call
        self.old_frame[idx] = packet.dmxData
