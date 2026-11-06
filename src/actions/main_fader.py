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

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class MainFaderSetLevelAction(Action):
    """Action to set the Main Fader output master level."""

    name = "main_fader.set_level"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.level: float = 1.0
        self.old_level: float = 1.0

    def configure(self, level: float) -> None:
        """Configure the target Main Fader level.

        Args:
            level: Level between 0.0 and 1.0 (or normalized if > 1.0).
        """
        raw_val = float(level)
        if raw_val > 1.0:
            raw_val = raw_val / 255.0
        self.level = max(0.0, min(1.0, raw_val))

    def execute(self) -> None:
        """Apply the configured Main Fader level."""
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

        if hasattr(self.app, "main_fader_level"):
            self.old_level = float(getattr(self.app, "main_fader_level", 1.0))
        elif backend_dmx is not None and hasattr(backend_dmx, "main_fader"):
            self.old_level = float(backend_dmx.main_fader.value)
        else:
            self.old_level = 1.0

        self.app.main_fader_level = self.level

        if backend_dmx is not None and hasattr(backend_dmx, "main_fader"):
            backend_dmx.main_fader.set_level(self.level)
            if type(backend_dmx).__name__ == "Dmx":
                backend_dmx.set_levels()
                backend_dmx.send()

        # Synchronize any virtual faders assigned to Main Fader
        fader_bank = getattr(self.app.lightshow, "fader_bank", None)
        if fader_bank is not None:
            for page_faders in fader_bank.faders.values():
                for fader in page_faders.values():
                    if type(fader).__name__ == "FaderMain":
                        fader.level = self.level

        self.app.emit("main_fader.level_changed", self.level)

    def undo(self) -> None:
        """Restore the previous Main Fader level."""
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

        self.app.main_fader_level = self.old_level

        if backend_dmx is not None and hasattr(backend_dmx, "main_fader"):
            backend_dmx.main_fader.set_level(self.old_level)
            if type(backend_dmx).__name__ == "Dmx":
                backend_dmx.set_levels()
                backend_dmx.send()

        fader_bank = getattr(self.app.lightshow, "fader_bank", None)
        if fader_bank is not None:
            for page_faders in fader_bank.faders.values():
                for fader in page_faders.values():
                    if type(fader).__name__ == "FaderMain":
                        fader.level = self.old_level

        self.app.emit("main_fader.level_changed", self.old_level)

    def redo(self) -> None:
        """Re-apply the target Main Fader level."""
        self.execute()
