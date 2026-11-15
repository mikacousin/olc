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

from olc.dmx import Dmx

if typing.TYPE_CHECKING:
    from olc.core.engine import CoreEngine
    from olc.core.lightshow import LightShow
    from olc.patch import DMXPatch


# pylint: disable=too-few-public-methods
class DMXBackend:
    """Unified DMX Backend coordinating notification dispatch from CoreEngine."""

    dmx: Dmx
    patch: DMXPatch

    def __init__(self, lightshow: LightShow) -> None:
        self.dmx = Dmx(typing.cast(typing.Any, self), lightshow)
        self.patch = lightshow.patch
        self.bind_engine(lightshow.app.engine if lightshow.app is not None else None)

    def bind_engine(self, engine: CoreEngine | None) -> None:
        """Bind notification callbacks to the given CoreEngine instance."""
        if engine is not None:
            engine.set_notification_callbacks(
                artnet=self.notify_artnet,
                sacn=self.notify_sacn,
                enttec=self.notify_enttec,
                dmx_in=self.on_dmx_received,
            )

    def on_dmx_received(self, universe: int, data: list[int]) -> None:
        """Forward incoming DMX-In frames from CoreEngine into Dmx."""
        self.dmx.on_dmx_received(universe, data)

    def stop(self) -> None:
        """Stop backend"""
        self.dmx.stop()

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
        result = None
        attr = actions.get(action, None)
        if attr:
            if func := getattr(self, f"{attr}", None):
                result = func(*args, **kwargs)
        if (
            action.startswith("artnet-")
            and self.dmx
            and self.dmx.lightshow.app is not None
        ):
            self.dmx.lightshow.app.emit("artnet.devices_changed")
        return result

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
