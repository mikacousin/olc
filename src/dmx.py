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

import array
import typing
from typing import Callable, Optional

from olc.define import DMX_INTERVAL, MAX_CHANNELS, NB_UNIVERSES, UNIVERSES
from olc.main_fader import MainFader
from olc.patch import DMXPatch
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    from olc.backends import DMXBackend
    from olc.lightshow import LightShow


# pylint: disable=too-many-instance-attributes
class Dmx:
    """Send levels to backend"""

    backend: Optional[DMXBackend]
    patch: DMXPatch
    main_fader: MainFader
    levels: dict[str, array.array]
    frame: list[array.array]
    user_outputs: dict[tuple[int, int], int]
    thread: RepeatedTimer
    output_callbacks: list[Callable[[int, list[int]], None]]
    notification_callbacks: list[Callable[[str, str], None]]

    def __init__(self, backend: Optional[DMXBackend], lightshow: LightShow) -> None:
        self.backend = backend
        self.lightshow = lightshow
        self.patch = self.lightshow.patch
        self.main_fader = MainFader()
        # Dimmers levels
        self.levels = {
            "sequence": array.array("B", [0] * MAX_CHANNELS),
            "user": array.array("h", [-1] * MAX_CHANNELS),
            "faders": array.array("B", [0] * MAX_CHANNELS),
        }
        # DMX values
        self.frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]
        self._old_frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]
        # To test outputs
        self.user_outputs = {}
        # Callbacks for UI updates
        self.output_callbacks = []
        # Callbacks for notifications
        self.notification_callbacks = []
        # Thread to send DMX every DMX_INTERVAL ms
        self.thread = RepeatedTimer(DMX_INTERVAL / 1000, self.send)

    def set_levels(self, channels: Optional[set[int]] = None) -> None:
        """Set DMX frame levels

        Args:
            channels: Channels to modify
        """
        if not channels:
            channels = set(range(1, MAX_CHANNELS + 1))
        for channel in channels:
            if not self.patch.is_patched(channel):
                continue
            outputs = self.patch.channels[channel]
            channel -= 1
            # Sequence
            level = self.levels["sequence"][channel]
            # User
            if (
                not self.lightshow.main_playback.on_go
                and self.levels["user"][channel] != -1
            ):
                level = self.levels["user"][channel]
            # Faders
            if self.levels["faders"][channel] > level:
                level = self.levels["faders"][channel]
            # Independents
            if self.lightshow.independents.dmx[channel] > level:
                level = self.lightshow.independents.dmx[channel]
            for out in outputs:
                output = out[0]
                universe = out[1]
                if universe and output:
                    # Curve
                    curve_numb = self.patch.outputs[universe][output][1]
                    if curve_numb:
                        curve = self.lightshow.curves.get_curve(curve_numb)
                        if curve:
                            level = curve.values.get(level, 0)
                    # Main Fader
                    level = round(level * self.main_fader.value)
                    index = UNIVERSES.index(universe)
                    # Update output level
                    self.frame[index][output - 1] = level

    def send(self) -> None:
        """Send DMX values to Ola"""
        if self.backend:
            for index, universe in enumerate(UNIVERSES):
                self.backend.send(universe, index)

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
        if self.backend:
            for index, universe in enumerate(UNIVERSES):
                self.frame[index] = array.array("B", [0] * 512)
                self.backend.send(universe, index)

    def send_user_output(self, output: int, universe: int, level: int) -> None:
        """Send level to an output

        Args:
            output: Output number (1-512)
            universe: Universe number (one in UNIVERSES)
            level: Output level (0-255)
        """
        self.user_outputs[(output, universe)] = level
        index = UNIVERSES.index(universe)
        self.frame[index][output - 1] = level
        if not level:
            self.user_outputs.pop((output, universe))
        if self.backend:
            self.backend.send(universe, index)

    def add_output_callback(self, callback: Callable[[int, list[int]], None]) -> None:
        """Register a callback for output level changes."""
        if callback not in self.output_callbacks:
            self.output_callbacks.append(callback)

    def remove_output_callback(
        self, callback: Callable[[int, list[int]], None]
    ) -> None:
        """Remove a callback for output level changes."""
        if callback in self.output_callbacks:
            self.output_callbacks.remove(callback)

    def trigger_output_callbacks(self, universe: int, outputs: list[int]) -> None:
        """Trigger registered callbacks.

        Args:
            universe: Universe number
            outputs: List of changed output indices
        """
        for callback in self.output_callbacks:
            callback(universe, outputs)

    def add_notification_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for notifications."""
        if callback not in self.notification_callbacks:
            self.notification_callbacks.append(callback)

    def trigger_notification(self, title: str, body: str) -> None:
        """Trigger registered notification callbacks.

        Args:
            title: Notification title
            body: Notification body text
        """
        for callback in self.notification_callbacks:
            callback(title, body)
