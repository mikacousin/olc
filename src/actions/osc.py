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
"""Actions for OSC networking configuration and server/client toggling."""

from __future__ import annotations

import typing

from gi.repository import GLib
from olc.core.action import Action
from olc.core.backends.osc.delegate import OSCDelegate

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class OscToggleAction(Action):
    """Action to enable or disable OSC networking."""

    name = "osc.toggle"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.enable: bool = False

    def configure(self, enable: bool) -> None:
        """Configure whether OSC networking should be enabled.

        Args:
            enable: True to start OSC server and client, False to stop them.
        """
        self.enable = enable

    def execute(self) -> None:
        """Execute OSC toggle."""
        settings = getattr(self.app, "settings", None)
        if settings is not None:
            if hasattr(settings, "set_value"):
                settings.set_value("osc", GLib.Variant("b", self.enable))
            elif hasattr(settings, "set_boolean"):
                settings.set_boolean("osc", self.enable)

        engine = getattr(self.app, "engine", None)
        if engine is not None:
            if self.enable:
                host = "127.0.0.1"
                client_port = 8000
                server_port = 9000
                if settings is not None:
                    if hasattr(settings, "get_string"):
                        host = settings.get_string("osc-host") or "127.0.0.1"
                    if hasattr(settings, "get_int"):
                        client_port = settings.get_int("osc-client-port") or 8000
                        server_port = settings.get_int("osc-server-port") or 9000
                engine.start_osc(
                    host=host,
                    client_port=client_port,
                    server_port=server_port,
                )
                core_app = getattr(self.app, "core", self.app)
                osc_delegate = OSCDelegate(core_app)
                self.app.osc_delegate = osc_delegate
                engine.register_osc_delegate(osc_delegate)
            else:
                engine.stop_osc()
                self.app.osc_delegate = None

        self.app.emit("osc.toggled", self.enable)


class OscSetConfigAction(Action):
    """Action to configure OSC target host and network ports."""

    name = "osc.set_config"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.host: typing.Optional[str] = None
        self.client_port: typing.Optional[int] = None
        self.server_port: typing.Optional[int] = None

        self.old_host: str = ""
        self.old_client_port: int = 0
        self.old_server_port: int = 0

    def configure(
        self,
        host: typing.Optional[str] = None,
        client_port: typing.Optional[int] = None,
        server_port: typing.Optional[int] = None,
    ) -> None:
        """Configure OSC target host and ports.

        Args:
            host: Target OSC client host name or IP address.
            client_port: Target OSC client port.
            server_port: Local OSC server listening port.
        """
        self.host = host
        self.client_port = client_port
        self.server_port = server_port

    def execute(self) -> None:
        """Apply new OSC network configuration."""
        settings = getattr(self.app, "settings", None)
        if settings is not None:
            if hasattr(settings, "get_string"):
                self.old_host = settings.get_string("osc-host")
            if hasattr(settings, "get_int"):
                self.old_client_port = settings.get_int("osc-client-port")
                self.old_server_port = settings.get_int("osc-server-port")

        target_host = self.host if self.host is not None else self.old_host
        target_client_port = (
            self.client_port if self.client_port is not None else self.old_client_port
        )
        target_server_port = (
            self.server_port if self.server_port is not None else self.old_server_port
        )

        self._apply_config(target_host, target_client_port, target_server_port)

    def undo(self) -> None:
        """Revert to previous OSC network configuration."""
        self._apply_config(self.old_host, self.old_client_port, self.old_server_port)

    def redo(self) -> None:
        """Reapply configured OSC network configuration."""
        target_host = self.host if self.host is not None else self.old_host
        target_client_port = (
            self.client_port if self.client_port is not None else self.old_client_port
        )
        target_server_port = (
            self.server_port if self.server_port is not None else self.old_server_port
        )
        self._apply_config(target_host, target_client_port, target_server_port)

    def _update_settings(self, host: str, client_port: int, server_port: int) -> None:
        settings = getattr(self.app, "settings", None)
        if settings is None:
            return

        if hasattr(settings, "set_value"):
            if host:
                settings.set_value("osc-host", GLib.Variant("s", host))
            if client_port > 0:
                settings.set_value("osc-client-port", GLib.Variant("i", client_port))
            if server_port > 0:
                settings.set_value("osc-server-port", GLib.Variant("i", server_port))
        else:
            if hasattr(settings, "set_string") and host:
                settings.set_string("osc-host", host)
            if hasattr(settings, "set_int"):
                if client_port > 0:
                    settings.set_int("osc-client-port", client_port)
                if server_port > 0:
                    settings.set_int("osc-server-port", server_port)

    def _update_engine(self, host: str, client_port: int, server_port: int) -> None:
        engine = getattr(self.app, "engine", None)
        if engine is None:
            return

        if host or client_port > 0:
            engine.update_osc_client(
                host=host, port=client_port if client_port > 0 else None
            )
        if server_port > 0:
            engine.update_osc_server(server_port)

    def _apply_config(self, host: str, client_port: int, server_port: int) -> None:
        self._update_settings(host, client_port, server_port)
        self._update_engine(host, client_port, server_port)
        self.app.emit("osc.config_changed", host, client_port, server_port)
