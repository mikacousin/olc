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

from olc.core.action import Action
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class SetChannelLevelAction(Action):
    """Action to set the DMX user-override level of a channel.

    Supports Undo/Redo by capturing the previous user level.
    """

    name = "channel.set_level"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.channel: int = 1
        self.level: int = -1
        self.old_level: int = -1

    def configure(self, channel: int, level: int) -> None:
        """Configure the action with the target channel and level.

        Args:
            channel: The 1-indexed channel number (1 to MAX_CHANNELS).
            level: The DMX intensity (0 to 255, or -1 to release override).
        """
        self.channel = channel
        self.level = level

    def execute(self) -> None:
        """Execute the action, setting the DMX channel level."""
        channel = self.channel
        level = self.level

        # Validate channel and level bounds
        if not 1 <= channel <= MAX_CHANNELS:
            raise ValueError(
                f"Channel index must be between 1 and {MAX_CHANNELS}. Got {channel}."
            )
        if not -1 <= level <= 255:
            raise ValueError(f"DMX Level must be between -1 and 255. Got {level}.")

        # Access backend dmx override levels if initialized
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            # Capture the current override level (0-indexed in NumPy array)
            self.old_level = int(backend.dmx.levels["user"][channel - 1])
            # Set the new override level
            backend.dmx.levels["user"][channel - 1] = level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()
        else:
            self.old_level = -1

        # Emit the event so subscribers (like GUI) can refresh
        self.app.emit("channel.level_changed", channel, level)

    def undo(self) -> None:
        """Undo the channel level change, restoring its previous value."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            backend.dmx.levels["user"][self.channel - 1] = self.old_level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        self.app.emit("channel.level_changed", self.channel, self.old_level)

    def redo(self) -> None:
        """Redo the channel level change."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            backend.dmx.levels["user"][self.channel - 1] = self.level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        self.app.emit("channel.level_changed", self.channel, self.level)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the channel."""
        return {
            "channel": self.channel,
            "level": self.level,
            "active": self.level > 0,
        }

    def __repr__(self) -> str:
        return f"<SetChannelLevelAction channel={self.channel} level={self.level}>"
