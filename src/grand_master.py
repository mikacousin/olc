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
import mido
from olc.define import App


class GrandMaster:
    """Grand Master"""

    value: float

    def __init__(self):
        self.value = 1.0

    def set_level(self, value: float) -> None:
        """Set Grand Master level

        Args:
            value: New level (0 - 1)
        """
        # MIDI
        channel, control = App().midi.control_change.control_change["gm"]
        if control != -1:
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=round(value * 127),
                time=0,
            )
            App().midi.queue.enqueue(msg)
        channel = App().midi.pitchwheel.pitchwheel.get("gm", -1)
        if channel != -1:
            val = round((value * 16383) - 8192)
            msg = mido.Message("pitchwheel", channel=channel, pitch=val, time=0)
            App().midi.queue.enqueue(msg)
        # OSC
        if App().osc:
            # Not implemented
            pass
        self.value = value

    def get_level(self) -> float:
        """Get Grand Master level

        Returns:
            level (0 - 1)
        """
        return self.value
