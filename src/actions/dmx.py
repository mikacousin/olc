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


class DmxTestOutputAction(Action):
    """Action to set a test level on DMX output(s)."""

    name = "dmx.test_output"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.targets: list[tuple[int, int]] = []
        self.level: int = 255
        self.old_levels: dict[tuple[int, int], int] = {}

    def configure(
        self,
        output: int | list[tuple[int, int]],
        universe: int = 1,
        level: int = 255,
    ) -> None:
        """Configure the action with target output(s) and test level.

        Args:
            output: Single output (1-512) or list of (output, universe) tuples.
            universe: DMX universe identifier if output is an integer.
            level: Level to apply (0-255).
        """
        if isinstance(output, list):
            self.targets = list(output)
            self.level = level if level != 255 else (universe if universe != 1 else 255)
        else:
            self.targets = [(output, universe)]
            self.level = level

    def execute(self) -> None:
        """Apply test level to configured outputs."""
        backend = getattr(self.app, "backend", None)
        self.old_levels = {}
        for out, univ in self.targets:
            old = 0
            if backend is not None and getattr(backend, "dmx", None) is not None:
                old = backend.dmx.user_outputs.get((out, univ), 0)
                backend.dmx.send_user_output(out, univ, self.level)
            elif self.app.engine is not None:
                try:
                    old = int(self.app.engine.universe(univ).array[out - 1])
                    self.app.engine.universe(univ).array[out - 1] = self.level
                except (KeyError, IndexError, AttributeError):
                    pass
            self.old_levels[(out, univ)] = old
            self.app.emit("dmx.user_output_changed", univ, out, self.level)

    def undo(self) -> None:
        """Restore previous output levels prior to test."""
        backend = getattr(self.app, "backend", None)
        for (out, univ), old in self.old_levels.items():
            if backend is not None and getattr(backend, "dmx", None) is not None:
                backend.dmx.send_user_output(out, univ, old)
            elif self.app.engine is not None:
                try:
                    self.app.engine.universe(univ).array[out - 1] = old
                except (KeyError, IndexError, AttributeError):
                    pass
            self.app.emit("dmx.user_output_changed", univ, out, old)

    def redo(self) -> None:
        """Re-apply test level to target outputs."""
        backend = getattr(self.app, "backend", None)
        for out, univ in self.targets:
            if backend is not None and getattr(backend, "dmx", None) is not None:
                backend.dmx.send_user_output(out, univ, self.level)
            elif self.app.engine is not None:
                try:
                    self.app.engine.universe(univ).array[out - 1] = self.level
                except (KeyError, IndexError, AttributeError):
                    pass
            self.app.emit("dmx.user_output_changed", univ, out, self.level)


class DmxClearUserOutputsAction(Action):
    """Action to clear all active test/user output overrides."""

    name = "dmx.clear_user_outputs"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_user_outputs: dict[tuple[int, int], int] = {}

    def execute(self) -> None:
        """Clear all active user outputs, setting them back to 0."""
        backend = getattr(self.app, "backend", None)
        self.old_user_outputs = {}
        if backend is not None and getattr(backend, "dmx", None) is not None:
            self.old_user_outputs = dict(backend.dmx.user_outputs)
            for out, univ in list(self.old_user_outputs.keys()):
                backend.dmx.send_user_output(out, univ, 0)
            backend.dmx.user_outputs.clear()
        self.app.emit("dmx.user_outputs_cleared")

    def undo(self) -> None:
        """Restore previous user output levels prior to clear."""
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            for (out, univ), lvl in self.old_user_outputs.items():
                backend.dmx.send_user_output(out, univ, lvl)
                self.app.emit("dmx.user_output_changed", univ, out, lvl)
        self.app.emit("dmx.user_outputs_changed")

    def redo(self) -> None:
        """Re-apply clear on user outputs."""
        self.execute()


class DmxBlackoutAllAction(Action):
    """Action to blackout all DMX universes simultaneously."""

    name = "dmx.blackout_all"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_frames: dict[int, np.ndarray] = {}

    def execute(self) -> None:
        """Execute blackout on all universes."""
        self.old_frames = {}

        for universe in UNIVERSES:
            if self.app.engine is not None:
                try:
                    univ = self.app.engine.universe(universe)
                    self.old_frames[universe] = univ.snapshot()
                    univ.blackout()
                except KeyError:
                    pass

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            for idx, universe in enumerate(UNIVERSES):
                if universe not in self.old_frames:
                    self.old_frames[universe] = backend.dmx.frame[idx].copy()
                backend.dmx.frame[idx].fill(0)

        self.app.emit("dmx.blackout_all_changed", True)

    def undo(self) -> None:
        """Restore all universes prior to blackout."""
        for universe, old_frame in self.old_frames.items():
            if self.app.engine is not None:
                try:
                    self.app.engine.universe(universe).apply_array(old_frame)
                except KeyError:
                    pass
            backend = getattr(self.app, "backend", None)
            if backend is not None and getattr(backend, "dmx", None) is not None:
                if universe in UNIVERSES:
                    idx = UNIVERSES.index(universe)
                    np.copyto(backend.dmx.frame[idx], old_frame)

        self.app.emit("dmx.blackout_all_changed", False)

    def redo(self) -> None:
        """Re-apply blackout on all universes."""
        for universe in UNIVERSES:
            if self.app.engine is not None:
                try:
                    self.app.engine.universe(universe).blackout()
                except KeyError:
                    pass
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            for idx in range(len(UNIVERSES)):
                backend.dmx.frame[idx].fill(0)

        self.app.emit("dmx.blackout_all_changed", True)
