# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
import array
from typing import Any, Optional

from olc.define import DMX_INTERVAL, MAX_CHANNELS, NB_UNIVERSES, UNIVERSES, App
from olc.main_fader import MainFader
from olc.patch import DMXPatch
from olc.timer import RepeatedTimer


class Dmx:
    """Send levels to backend"""

    backend: Any
    patch: DMXPatch
    main_fader: MainFader
    levels: dict[str, array.array]
    frame: list[array.array]
    user_outputs: dict[tuple[int, int], int]
    thread: RepeatedTimer

    def __init__(self, backend):
        self.backend = backend
        self.patch = App().lightshow.patch
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
            if not App(
            ).lightshow.main_playback.on_go and self.levels["user"][channel] != -1:
                level = self.levels["user"][channel]
            # Faders
            if self.levels["faders"][channel] > level:
                level = self.levels["faders"][channel]
            # Independents
            if App().lightshow.independents.dmx[channel] > level:
                level = App().lightshow.independents.dmx[channel]
            for out in outputs:
                output = out[0]
                universe = out[1]
                # Curve
                curve_numb = self.patch.outputs[universe][output][1]
                if curve_numb:
                    curve = App().lightshow.curves.get_curve(curve_numb)
                    level = curve.values.get(level, 0)
                # Main Fader
                level = round(level * self.main_fader.value)
                # Update output level
                index = UNIVERSES.index(universe)
                self.frame[index][output - 1] = level

    def send(self) -> None:
        """Send DMX values to Ola"""
        if self.backend:
            for index, universe in enumerate(UNIVERSES):
                self.backend.send(universe, index)

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
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
        self.backend.send(universe, index)
