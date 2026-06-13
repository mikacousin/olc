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

from olc.actions import register_all_actions
from olc.core.crossfade import CrossFade
from olc.core.event import EventDispatcher
from olc.core.history import HistoryManager
from olc.core.registry import ActionRegistry
from olc.lightshow import LightShow

if typing.TYPE_CHECKING:
    import olc.core.app
    from olc.backends import DMXBackend
    from olc.core.engine import CoreEngine
    from olc.midi import Midi


# pylint: disable=too-many-instance-attributes
class CoreApplication(EventDispatcher):
    """The headless core application managing engines, midi, and actions.

    Acts as the single source of truth for the entire application logic.
    Decoupled from all GTK graphical interfaces.
    """

    backend: typing.Optional[DMXBackend]
    engine: typing.Optional[CoreEngine]
    midi: typing.Optional[Midi]
    crossfade: typing.Optional[CrossFade]

    @property
    def core(self) -> CoreApplication:
        """Return self as the core application."""
        return self

    def __init__(self, settings: object, app: object = None) -> None:
        """Initialize the CoreApplication.

        Args:
            settings: Configuration settings instance.
            app: Optional parent application instance.
        """
        super().__init__()
        self.settings = settings

        # Load standard LightShow state model
        self.lightshow = LightShow(typing.cast(typing.Any, app or self))

        # Initialize engines as None (to be attached by launcher or Gtk)
        self.backend = None
        self.engine = None
        self.midi = None

        # For crossfade
        app_delegate = app if app is not None else self
        self.crossfade = CrossFade(typing.cast(typing.Any, app_delegate))

        # Action and Undo/Redo plumbing layers
        self.action_registry = ActionRegistry(
            typing.cast("olc.core.app.CoreApplication", self)
        )
        self.history = HistoryManager(typing.cast("olc.core.app.CoreApplication", self))

        # Auto-register action classes from the actions package
        self._register_actions()

    def _register_actions(self) -> None:
        """Register all concrete actions from the actions package."""
        register_all_actions(self.action_registry)

    def start(self) -> None:
        """Start backend hardware and communications services."""
        if self.engine:
            self.engine.start()
        # OSC and MIDI are started by their respective managers/launchers

    def stop(self) -> None:
        """Gracefully stop DMX and MIDI services."""
        if self.midi:
            self.midi.stop()
        if self.engine:
            self.engine.stop()
