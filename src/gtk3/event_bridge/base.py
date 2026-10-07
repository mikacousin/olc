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
"""Base handler class for GUI event bridge components."""

from __future__ import annotations

import abc
import typing

from gi.repository import GLib

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


# pylint: disable=too-few-public-methods
class BaseEventBridgeHandler(abc.ABC):
    """Abstract base class for domain-specific GUI event bridge handlers.

    Provides access to the main Application instance and safe execution
    on the GTK main loop via GLib.idle_add.
    """

    def __init__(self, app: Application) -> None:
        """Initialize the handler with the main application.

        Args:
            app: The main application instance.
        """
        self.app = app

    @abc.abstractmethod
    def register(self) -> None:
        """Subscribe to Core events related to this handler's domain."""

    def _run_idle(self, func: typing.Callable[..., bool], *args: object) -> None:
        """Run callback in the GTK main loop safely."""
        GLib.idle_add(func, *args)
