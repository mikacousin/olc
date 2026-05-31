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
from gettext import gettext as _
from typing import Callable

from olc.core.backends.artnet import ArtNetManager
from olc.core.backends.sacn import SacnManager
from olc.dmx import Dmx

if typing.TYPE_CHECKING:
    from olc.lightshow import LightShow
    from olc.patch import DMXPatch


# pylint: disable=too-few-public-methods
class DMXBackend:
    """Unified DMX Backend coordinating multiple active protocols from CoreEngine."""

    dmx: Dmx
    patch: DMXPatch
    artnet: ArtNetManager | None
    sacn: SacnManager | None

    def __init__(self, lightshow: LightShow) -> None:
        self.dmx = Dmx(typing.cast(typing.Any, self), lightshow)
        self.patch = lightshow.patch
        self.artnet = getattr(lightshow.app.engine, "_artnet_manager", None)
        self.sacn = getattr(lightshow.app.engine, "_sacn_manager", None)

        # Wire up callbacks on active managers
        if self.artnet is not None:
            self.artnet.notify = self.notify_artnet

        if self.sacn is not None:
            self.sacn.notify = self.notify_sacn

        if hasattr(lightshow.app.engine, "notify_enttec"):
            lightshow.app.engine.notify_enttec = self.notify_enttec

    def stop(self) -> None:
        """Stop backend"""
        self.dmx.thread.stop()

    def notify_artnet(
        self, action: str, *args: str | int, **kwargs: str
    ) -> None | Callable:
        """Dispatch Art-Net notifications to UI."""
        return self.notify(f"artnet-{action}", *args, **kwargs)

    def notify_sacn(
        self, action: str, *args: str | int, **kwargs: str
    ) -> None | Callable:
        """Dispatch sACN notifications to UI."""
        return self.notify(f"sacn-{action}", *args, **kwargs)

    def notify_enttec(
        self, universe: int, action: str, *args: str | int, **kwargs: str
    ) -> None | Callable:
        """Dispatch ENTTEC USB Pro notifications to UI."""
        return self.notify(f"enttec-{action}", universe, *args, **kwargs)

    def notify(self, action: str, *args: str | int, **kwargs: str) -> None | Callable:
        """Dispatch unified notifications to GTK UI."""
        actions = {
            "artnet-add-node": "_artnet_add_node",
            "artnet-del-node": "_artnet_del_node",
            "artnet-add-console": "_artnet_add_console",
            "artnet-del-console": "_artnet_del_console",
            "sacn-add-node": "_sacn_add_node",
            "sacn-del-node": "_sacn_del_node",
            "enttec-connect": "_enttec_connect",
            "enttec-connect-fail": "_enttec_connect_fail",
            "enttec-disconnect": "_enttec_disconnect",
        }
        attr = actions.get(action, None)
        if attr:
            if func := getattr(self, f"{attr}", None):
                return func(*args, **kwargs)
        return None

    def _artnet_add_node(self, ip: str, universe: int) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "New Art-Net Node detected",
                f"Send Universe {universe} to Node at {ip}.",
            )

    def _artnet_del_node(self, ip: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "Art-Net Node disconnected", f"Lost Node at {ip}."
            )

    def _artnet_add_console(self, ip: str, _universe: int) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "New Art-Net Console detected", f"Art-Net Console detected at {ip}."
            )

    def _artnet_del_console(self, ip: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "Art-Net Console disconnected", f"Lost Console at {ip}."
            )

    def _sacn_add_node(self, ip: str, universe: int) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "New sACN Source detected",
                f"Source at {ip} is sending Universe {universe}.",
            )

    def _sacn_del_node(self, ip: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                "sACN Source disconnected", f"Lost Source at {ip}."
            )

    def _enttec_connect(self, universe: int, port: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                _("DMX USB Pro connected"),
                _(
                    "Universe {universe}: ENTTEC device connected on port {port}."
                ).format(universe=universe, port=port),
            )

    def _enttec_connect_fail(self, universe: int, port: str, error: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                _("DMX USB Pro connection failed"),
                _(
                    "Universe {universe}: could not connect to ENTTEC "
                    "device on port {port} ({error})."
                ).format(universe=universe, port=port, error=error),
            )

    def _enttec_disconnect(self, universe: int, port: str, error: str) -> None:
        if self.dmx:
            self.dmx.trigger_notification(
                _("DMX USB Pro disconnected"),
                _(
                    "Universe {universe}: ENTTEC device on port {port} "
                    "was disconnected ({error})."
                ).format(universe=universe, port=port, error=error),
            )
