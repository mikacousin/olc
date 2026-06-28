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

import threading
import typing

from olc.actions import register_all_actions
from olc.core.commandline import CoreCommandLine
from olc.core.crossfade import CrossFade
from olc.core.event import EventDispatcher
from olc.core.history import HistoryManager
from olc.core.lightshow import LightShow
from olc.core.registry import ActionRegistry
from olc.core.selection import SelectionManager

if typing.TYPE_CHECKING:
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
    commandline: CoreCommandLine
    live_selection: SelectionManager
    action_registry: ActionRegistry
    history: HistoryManager
    selected_cue: typing.Optional[tuple[float, int]]
    selected_group: typing.Optional[float]

    @property
    def core(self) -> CoreApplication:
        """Return self as the core application."""
        return self

    def __init__(
        self,
        settings: object,
        app: object = None,
        lightshow: typing.Optional[LightShow] = None,
    ) -> None:
        """Initialize the CoreApplication.

        Args:
            settings: Configuration settings instance.
            app: Optional parent application instance.
            lightshow: Optional pre-instantiated LightShow model.
        """
        super().__init__()
        self.settings = settings

        # Load standard LightShow state model
        if lightshow is not None:
            self.lightshow = lightshow
            self.lightshow.app = typing.cast(typing.Any, app or self)
        else:
            self.lightshow = LightShow(typing.cast(typing.Any, app or self))

        # Initialize engines as None (to be attached by launcher or Gtk)
        self.backend = None
        self.engine = None
        self.midi = None

        # For crossfade
        app_delegate = app if app is not None else self
        self.crossfade = CrossFade(typing.cast(typing.Any, app_delegate))

        # Command line logical state helper
        self.commandline = CoreCommandLine(typing.cast(typing.Any, self))

        # Action and Undo/Redo plumbing layers
        self.action_registry = ActionRegistry(typing.cast(typing.Any, self))
        self.history = HistoryManager(typing.cast(typing.Any, self))

        # Logical selection states
        self.live_selection = SelectionManager(
            commandline=self.commandline,
            on_changed_callback=self._on_live_selection_changed,
            history_manager=self.history,
            get_level_callback=self.get_channel_level,
        )
        self.selected_cue: typing.Optional[tuple[float, int]] = None
        self.selected_group: typing.Optional[float] = None
        self.zoom_level: float = 1.0
        self.active_tab: str = "channels"
        self._is_zooming: bool = False
        self._zoom_start_level: float = 1.0
        self._zoom_timer: typing.Optional[threading.Timer] = None

        # Auto-register action classes from the actions package
        self._register_actions()

    @property
    def selected_channels(self) -> list[int]:
        """Get the live selection channels."""
        return self.live_selection.selected_channels

    @selected_channels.setter
    def selected_channels(self, value: list[int]) -> None:
        """Set the live selection channels."""
        self.live_selection.selected_channels = value

    @property
    def last_selected_channel(self) -> typing.Optional[int]:
        """Get the last selected live channel."""
        return self.live_selection.last_selected_channel

    @last_selected_channel.setter
    def last_selected_channel(self, value: typing.Optional[int]) -> None:
        """Set the last selected live channel."""
        self.live_selection.last_selected_channel = value

    def _on_live_selection_changed(self, channels: list[int]) -> None:
        """Propagate live selection changes to listeners."""
        self.emit("channels.selected_changed", channels)

    def get_channel_level(self, channel: int) -> int:
        """Get the current level of a channel in the active backend/dmx state."""
        backend = getattr(self, "backend", None)
        if backend and backend.dmx:
            try:
                return int(backend.dmx.levels["user"][channel - 1])
            except (IndexError, TypeError, KeyError):
                pass
        return 0

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
        if self.backend:
            self.backend.stop()
        if self.midi:
            self.midi.stop()
        if self.engine:
            self.engine.stop()

    def zoom(self, direction: str) -> None:
        """Adjust zoom level with debouncing, emitting events in real-time.

        Args:
            direction: Zoom direction, "in" or "out".
        """
        if not self._is_zooming:
            self._is_zooming = True
            self._zoom_start_level = self.zoom_level

        current_zoom = self.zoom_level
        if direction == "in":
            new_zoom = min(current_zoom + 0.05, 2.0)
        else:
            new_zoom = max(current_zoom - 0.05, 0.5)

        self.zoom_level = new_zoom
        self.emit("gui.zoom_changed", new_zoom)

        if self._zoom_timer is not None:
            self._zoom_timer.cancel()

        self._zoom_timer = threading.Timer(0.6, self._finalize_zoom)
        self._zoom_timer.start()

    def _finalize_zoom(self) -> None:
        """Callback to finalize continuous zoom by executing Core Action."""
        self._is_zooming = False
        self._zoom_timer = None
        final_zoom = self.zoom_level
        self.zoom_level = self._zoom_start_level
        self.action_registry.execute("gui.zoom", final_zoom)
