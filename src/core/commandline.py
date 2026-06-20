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
"""Logical command line state model."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class CoreCommandLine:
    """Logical command line state helper, decoupled from the GUI."""

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the logical command line.

        Args:
            app: The core application instance.
        """
        self.app = app
        self._keystring: str = ""

    def update(self) -> None:
        """Send state changes via OSC and emit local core events."""
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/command_line", self._keystring)
        self.app.emit("commandline.changed", self._keystring)

    def add_string(self, string: str) -> None:
        """Add a string segment to the current command line.

        Args:
            string: The string to append.
        """
        self._keystring += string
        self.update()

    def set_string(self, string: str) -> None:
        """Set the exact command line string.

        Args:
            string: The new command line string.
        """
        self._keystring = string
        self.update()

    def get_string(self) -> str:
        """Return the current command line string.

        Returns:
            The raw keystring.
        """
        return self._keystring
