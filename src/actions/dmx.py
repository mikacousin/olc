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
"""Actions for real-time DMX and Universe level manipulation."""

from __future__ import annotations

import typing

import numpy as np
from olc.core.action import Action
from olc.define import UNIVERSES

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class UniverseBlackoutAction(Action):
    """Action to blackout a specific DMX universe."""

    name = "universe.blackout"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.old_frame: typing.Optional[np.ndarray] = None

    def configure(self, universe: int) -> None:
        """Configure the action with the universe to blackout.

        Args:
            universe: The DMX universe identifier.
        """
        self.universe = universe

    def execute(self) -> None:
        """Execute blackout on the configured universe."""
        self.old_frame = None

        if self.app.engine is not None:
            try:
                univ = self.app.engine.universe(self.universe)
                self.old_frame = univ.snapshot()
                univ.blackout()
            except KeyError:
                pass

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            if self.universe in UNIVERSES:
                idx = UNIVERSES.index(self.universe)
                if self.old_frame is None:
                    self.old_frame = backend.dmx.frame[idx].copy()
                backend.dmx.frame[idx].fill(0)

        self.app.emit("universe.blackout_changed", self.universe)

    def undo(self) -> None:
        """Restore universe channel levels prior to blackout."""
        if self.old_frame is not None:
            if self.app.engine is not None:
                try:
                    self.app.engine.universe(self.universe).apply_array(self.old_frame)
                except KeyError:
                    pass
            backend = getattr(self.app, "backend", None)
            if backend is not None and getattr(backend, "dmx", None) is not None:
                if self.universe in UNIVERSES:
                    idx = UNIVERSES.index(self.universe)
                    np.copyto(backend.dmx.frame[idx], self.old_frame)
        self.app.emit("universe.blackout_changed", self.universe)

    def redo(self) -> None:
        """Re-apply blackout on the configured universe."""
        if self.app.engine is not None:
            try:
                self.app.engine.universe(self.universe).blackout()
            except KeyError:
                pass
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            if self.universe in UNIVERSES:
                idx = UNIVERSES.index(self.universe)
                backend.dmx.frame[idx].fill(0)
        self.app.emit("universe.blackout_changed", self.universe)


class DmxSetUniverseLevelsAction(Action):
    """Action to set specific channel levels on a universe."""

    name = "dmx.set_universe_levels"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.channels: dict[int, int] = {}

    def configure(self, universe: int, channels: dict[int, int]) -> None:
        """Configure the action with target universe and channel levels.

        Args:
            universe: The DMX universe identifier.
            channels: Dictionary mapping channel index to DMX level (0-255).
        """
        self.universe = universe
        self.channels = dict(channels)

    def execute(self) -> None:
        """Apply channel levels to the target universe."""
        if self.app.engine is not None:
            try:
                self.app.engine.set_channels(self.universe, self.channels)
            except KeyError:
                pass

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            if self.universe in UNIVERSES:
                idx = UNIVERSES.index(self.universe)
                frame = backend.dmx.frame[idx]
                for ch, val in self.channels.items():
                    if 0 <= ch < 512:
                        frame[ch] = int(np.clip(val, 0, 255))

        self.app.emit("universe.dmx_changed", self.universe, self.channels)
