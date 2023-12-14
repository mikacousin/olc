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
from typing import List
from olc.define import DMX_INTERVAL, UNIVERSES, MAX_CHANNELS, NB_UNIVERSES, App
from olc.timer import RepeatedTimer


class Dmx:
    """Thread to send levels to Ola"""

    grand_master: int
    frame: List[array.array]
    sequence: array.array
    user: array.array

    def __init__(self):
        self.grand_master = 255
        # Dimers levels
        self.sequence = array.array("B", [0] * MAX_CHANNELS)
        # User levels
        self.user = array.array("h", [-1] * MAX_CHANNELS)
        # To test outputs
        self.user_outputs = {}
        # DMX values send to Ola
        self.frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]
        self._old_frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]
        self.thread = RepeatedTimer(DMX_INTERVAL / 1000, self.send)

    def set_levels(self) -> None:
        """Set DMX frame levels"""
        for channel, outputs in App().patch.channels.items():
            if not App().patch.is_patched(channel):
                continue
            channel -= 1
            # Level in Sequence
            level = self.sequence[channel]
            if not App().sequence.on_go and self.user[channel] != -1:
                # If not on Go, use user level
                level = self.user[channel]
            for master in App().masters:
                # If master level is bigger, use it
                if master.dmx[channel] > level:
                    level = master.dmx[channel]
            # Independents
            level_inde = -1
            for inde in App().independents.independents:
                if channel + 1 in inde.channels and inde.dmx[channel] > level_inde:
                    level_inde = inde.dmx[channel]
            if level_inde != -1:
                level = level_inde
            for i in outputs:
                output = i[0]
                universe = i[1]
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
            outputs = [
                idx
                for idx, (e1, e2) in enumerate(
                    zip(self.frame[index], self._old_frame[index])
                )
                if e1 != e2
            ]
            if outputs:
                App().ola.thread.client.SendDmx(universe, self.frame[index])
                self._old_frame[index] = self.frame[index][:]

    def _send_user_outputs(self, univ) -> List[int]:
        """Outputs at level on user demand

        Args:
            univ: Universes with level modification

        Returns:
            Universes with level modification updated
        """
        user_outputs_to_delete = []
        for output, level in self.user_outputs.items():
            out = output[0]
            universe = output[1]
            if universe not in univ:
                univ.append(universe)
            index = App().universes.index(universe)
            self.frame[index][out - 1] = level
            if not level:
                user_outputs_to_delete.append(output)
        for output in user_outputs_to_delete:
            self.user_outputs.pop(output)
        return univ

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
