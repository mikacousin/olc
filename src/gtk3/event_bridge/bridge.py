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
"""Main GUI event bridge facade orchestrating domain handlers."""

from __future__ import annotations

import typing

from gi.repository import GLib

from .channels import ChannelBridgeHandler
from .cues import CueBridgeHandler
from .faders import FaderBridgeHandler
from .groups_curves import GroupCurveBridgeHandler
from .patch_dmx import PatchDmxBridgeHandler
from .playback import PlaybackBridgeHandler
from .show_system import ShowSystemBridgeHandler

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class GuiEventBridge:
    """GuiEventBridge coordinates core events and GTK main-thread operations."""

    def __init__(self, app: Application) -> None:
        """Initialize the event bridge and register all domain handlers.

        Args:
            app: The main application instance.
        """
        self.app = app

        self.channels = ChannelBridgeHandler(app)
        self.cues = CueBridgeHandler(app)
        self.patch_dmx = PatchDmxBridgeHandler(app)
        self.faders = FaderBridgeHandler(app)
        self.groups_curves = GroupCurveBridgeHandler(app)
        self.playback = PlaybackBridgeHandler(app)
        self.show_system = ShowSystemBridgeHandler(app)

        self.channels.register()
        self.cues.register()
        self.patch_dmx.register()
        self.faders.register()
        self.groups_curves.register()
        self.playback.register()
        self.show_system.register()

    def sync_virtual_console(self) -> None:
        """Sync virtual console button states and crossfades with playback."""
        self.playback.sync_virtual_console()

    def _run_idle(self, func: typing.Callable[..., bool], *args: object) -> None:
        """Run callback in the GTK main loop safely.

        Args:
            func: The callable to run on idle.
            *args: Arguments for the function.
        """
        GLib.idle_add(func, *args)
