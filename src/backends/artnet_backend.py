# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2025 Mika Cousin <mika.cousin@gmail.com>
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

from gi.repository import Gio, GLib

from ..backends import DMXBackend
from ..define import UNIVERSES, App
from .artnet import Artnet

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from ..patch import DMXPatch


# pylint: disable=too-few-public-methods
class Callback:
    """Callback on ArtDmx packet reception"""

    patch: DMXPatch
    old_frame: dict[int, list[int]]

    def __init__(self, patch: DMXPatch) -> None:
        self.patch = patch
        self.old_frame = {}
        for universe in UNIVERSES:
            self.old_frame[universe] = [0] * 512

    def receive_packet(self, universe: int, packet: list[int]) -> None:
        """Callback when receive Art-Net packets

        Args:
            universe: ArtDmx packet universe
            packet: Art-Net data
        """
        try:
            idx = UNIVERSES.index(universe)
        except ValueError:
            # If received packet for a universe we don't use
            return

        if App().tabs.tabs["patch_outputs"]:
            # Find diff between old and new DMX frames
            outputs = [
                index
                for index, (e1, e2) in enumerate(
                    zip(packet, self.old_frame[universe], strict=True)
                )
                if e1 != e2
            ]
            # Loop on outputs with different level
            for output in outputs:
                if self.patch.outputs.get(universe) and self.patch.outputs[
                    universe
                ].get(output + 1):
                    GLib.idle_add(
                        App()
                        .tabs.tabs["patch_outputs"]
                        .outputs[output + (idx * 512)]
                        .queue_draw
                    )
        # Save DMX frame for next call
        self.old_frame[universe] = packet


class ArtnetBackend(DMXBackend):
    """Art-Net Backend"""

    artnet: Artnet

    def __init__(self, patch: DMXPatch) -> None:
        self.artnet = Artnet(
            universes=UNIVERSES,
            notify=self.notify,
            on_artdmx_cb=Callback(patch).receive_packet,
        )
        super().__init__(patch)

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
        self.artnet.send(universe, self.dmx.frame[index])

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
        notification = Gio.Notification()
        notification.set_title("New Node detected")
        notification.set_body(f"Send Universe {universe} to Node at {ip}.")
        App().send_notification(None, notification)

    def _del_node(self, ip: str) -> None:
        notification = Gio.Notification()
        notification.set_title("Node deconnected")
        notification.set_body(f"Lost Node at {ip}.")
        App().send_notification(None, notification)

    def _node_modified(self, name: str, attribute: str, old: int, new: int) -> None:
        notification = Gio.Notification()
        notification.set_title("Node modified")
        notification.set_body(
            f"Art-Net Node {name}: {attribute} updated from {old} to {new}."
        )
        App().send_notification(None, notification)

    def _add_console(self, ip: str, _universe: int) -> None:
        notification = Gio.Notification()
        notification.set_title("New Console detected")
        notification.set_body(f"Art-Net Console detected at {ip}.")
        App().send_notification(None, notification)

    def _del_console(self, ip: str) -> None:
        notification = Gio.Notification()
        notification.set_title("Console deconnected")
        notification.set_body(f"Lost Console at {ip}.")
        App().send_notification(None, notification)
