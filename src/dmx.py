# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Optional
from olc.define import DMX_INTERVAL, UNIVERSES, MAX_CHANNELS, NB_UNIVERSES, App
from olc.timer import RepeatedTimer


class Dmx:
    """Thread to send levels to Ola"""

    grand_master: int
    levels: dict[str, array.array]
    frame: list[array.array]
    user_outputs: dict[tuple[int, int], int]
    thread: RepeatedTimer

    def __init__(self):
        self.grand_master = 255
        # Dimmers levels
        self.levels = {
            "sequence": array.array("B", [0] * MAX_CHANNELS),
            "user": array.array("h", [-1] * MAX_CHANNELS),
            "masters": array.array("B", [0] * MAX_CHANNELS),
        }
        # DMX values send to Ola
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
            if not App().patch.is_patched(channel):
                continue
            outputs = App().patch.channels[channel]
            channel -= 1
            # Sequence
            level = self.levels["sequence"][channel]
            # User
            if not App().sequence.on_go and self.levels["user"][channel] != -1:
                level = self.levels["user"][channel]
            # Masters
            if self.levels["masters"][channel] > level:
                level = self.levels["masters"][channel]
            # Independents
            if App().independents.dmx[channel] > level:
                level = App().independents.dmx[channel]
            for out in outputs:
                output = out[0]
                universe = out[1]
                # Curve
                curve_numb = App().patch.outputs[universe][output][1]
                if curve_numb:
                    curve = App().curves.get_curve(curve_numb)
                    level = curve.values.get(level, 0)
                # Grand Master
                level = round(level * (self.grand_master / 255))
                # Update output level
                index = App().universes.index(universe)
                self.frame[index][output - 1] = level

    def send(self) -> None:
        """Send DMX values to Ola"""
        for universe in UNIVERSES:
            index = App().universes.index(universe)
            App().ola.thread.client.SendDmx(universe, self.frame[index])

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
        for universe in UNIVERSES:
            index = App().universes.index(universe)
            self.frame[index] = array.array("B", [0] * 512)
            App().ola.thread.client.SendDmx(universe, self.frame[index])

    def send_user_output(self, output: int, universe: int, level: int) -> None:
        """Send level to an output

        Args:
            output: Output number (1-512)
            universe: Universe number (one in UNIVERSES)
            level: Output level (0-255)
        """
        self.user_outputs[(output, universe)] = level
        index = App().universes.index(universe)
        self.frame[index][output - 1] = level
        if not level:
            self.user_outputs.pop((output, universe))
        App().ola.thread.client.SendDmx(universe, self.frame[index])

    def update_masters(self) -> None:
        """Update masters levels"""
        for channel in range(MAX_CHANNELS):
            if not App().patch.is_patched(channel + 1):
                continue
            level_master = -1
            for master in App().masters:
                if master.dmx[channel] > level_master:
                    level_master = master.dmx[channel]
            if level_master != -1:
                self.levels["masters"][channel] = level_master
