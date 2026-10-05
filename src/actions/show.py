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
"""Actions for show life cycle and file management."""

from __future__ import annotations

import typing

from olc.core.action import Action
from olc.independent import Independents
from olc.sequence import Sequence

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class ShowNewAction(Action):
    """Action to reset and create a new blank show."""

    name = "show.new"
    can_undo = False

    def execute(self) -> None:
        """Reset all show data to default empty/1:1 state and clear history."""
        lightshow = self.app.lightshow

        # Stop and clear chasers
        for chaser in list(lightshow.chasers):
            if getattr(chaser, "run", False) and getattr(chaser, "thread", None):
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        del lightshow.chasers[:]

        # Reset cues and groups
        lightshow.cues.clear()
        lightshow.groups.clear()

        # Reset user curves
        if hasattr(lightshow, "curves"):
            lightshow.curves.reset()

        # Reset fader bank
        if hasattr(lightshow, "fader_bank"):
            lightshow.fader_bank.reset_faders()

        # Reset independents
        lightshow.independents = Independents(lightshow)

        # Reset patch 1:1
        lightshow.patch.patch_1on1()

        # Reset main playback
        lightshow.main_playback = Sequence(1, text="Main Playback", lightshow=lightshow)
        lightshow.main_playback.position = 0
        lightshow.main_playback.update_channels()

        # Reset DMX levels
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            backend.dmx.levels["sequence"][:] = 0
            backend.dmx.levels["user"][:] = -1
            if getattr(backend.dmx, "main_fader", None):
                backend.dmx.main_fader.set_level(1.0)
            backend.dmx.set_levels()

        # Clear channel selection
        if hasattr(self.app, "live_selection"):
            self.app.live_selection.selected_channels = []
            self.app.live_selection.last_selected_channel = None

        # Reset file metadata
        lightshow.file = None
        lightshow.file_path = None
        lightshow.basename = ""
        lightshow.set_not_modified()

        # Clear undo/redo history
        self.app.history.clear()

        # Emit event
        self.app.emit("show.new")


class ShowResetUserLevelsAction(Action):
    """Action to clear manual user channel overrides with Undo/Redo."""

    name = "show.reset_user_levels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_levels: dict[int, int] = {}

    def execute(self) -> None:
        """Reset all manual user channel overrides to -1."""
        self.old_levels = {}
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels["user"]
            for idx, lvl in enumerate(user_levels):
                if lvl != -1:
                    self.old_levels[idx + 1] = int(lvl)
            user_levels.fill(-1)
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.old_levels:
            self.app.emit("channel.level_changed", ch, -1)
        self.app.emit("show.user_levels_reset")

    def undo(self) -> None:
        """Restore previous manual user channel levels."""
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels["user"]
            for ch, lvl in self.old_levels.items():
                if 1 <= ch <= len(user_levels):
                    user_levels[ch - 1] = lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch, lvl in self.old_levels.items():
            self.app.emit("channel.level_changed", ch, lvl)
        self.app.emit("show.user_levels_restored")

    def redo(self) -> None:
        """Re-apply user levels reset."""
        self.execute()
