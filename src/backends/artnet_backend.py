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
from typing import Callable

from gi.repository import GLib
from olc.backends import DMXBackend
from olc.backends.artnet import Artnet
from olc.define import UNIVERSES

if typing.TYPE_CHECKING:
    from olc.dmx import Dmx
    from olc.lightshow import LightShow
    from olc.patch import DMXPatch


# pylint: disable=too-few-public-methods
class Callback:
    """Callback on ArtDmx packet reception"""

    patch: DMXPatch
    old_frame: dict[int, list[int]]

    def __init__(self, patch: DMXPatch, dmx: Dmx | None = None) -> None:
        self.patch = patch
        self.dmx = dmx
        self.old_frame = {}
        for universe in UNIVERSES:
            self.old_frame[universe] = [0] * 512

    def receive_packet(self, universe: int, packet: list[int]) -> None:
        """Callback when receive Art-Net packets

        Args:
            universe: ArtDmx packet universe
            packet: Art-Net data
        """
        # Find diff between old and new DMX frames
        outputs = [
            index
            for index, (e1, e2) in enumerate(
                zip(packet, self.old_frame[universe], strict=True)
            )
            if e1 != e2
        ]

        if outputs and self.dmx:
            GLib.idle_add(self.dmx.trigger_output_callbacks, universe, outputs)

        # Save DMX frame for next call
        self.old_frame[universe] = packet


class ArtnetBackend(DMXBackend):
    """Art-Net Backend"""

    artnet: Artnet

    def __init__(self, lightshow: LightShow) -> None:
        super().__init__(lightshow)
        self.artnet = Artnet(
            universes=UNIVERSES,
            notify=self.notify,
            on_artdmx_cb=Callback(lightshow.patch, self.dmx).receive_packet,
        )

    def stop(self) -> None:
        """Stop Art-Net backend"""
        super().stop()
        self.artnet.stop()

    def send(self, universe: int, index: int) -> None:
        """Send Art-Net universe

        Args:
            universe: one in UNIVERSES
            index: Index of universe
        """
        self.artnet.send(universe, bytes(self.dmx.frame[index]))

    def notify(self, action: str, *args: str | int, **kwargs: str) -> None | Callable:
        """Dispatch Notifications

        Args:
            action: One of the predefined actions
            *args: list of arguments
            **kwargs: dict of arguments

        Returns:
            Callable
        """
        actions = {
            "add-node": "_add_node",
            "del-node": "_del_node",
            "node-modified": "_node_modified",
            "add-console": "_add_console",
            "del-console": "_del_console",
        }
        attr = actions.get(action, None)
        if attr:
            if func := getattr(self, f"{attr}", None):
                return func(*args, **kwargs)
        return None

    def _add_node(self, ip: str, universe: int) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "New Node detected", f"Send Universe {universe} to Node at {ip}."
            )

    def _del_node(self, ip: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification("Node deconnected", f"Lost Node at {ip}.")

    def _node_modified(self, name: str, attribute: str, old: int, new: int) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "Node modified",
                f"Art-Net Node {name}: {attribute} updated from {old} to {new}.",
            )

    def _add_console(self, ip: str, _universe: int) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "New Console detected", f"Art-Net Console detected at {ip}."
            )

    def _del_console(self, ip: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "Console deconnected", f"Lost Console at {ip}."
            )
