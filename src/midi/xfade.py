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
import mido
from olc.define import App

from .fader import MIDIFader


class MidiXFade:
    """MIDI manual Crossfade"""

    def __init__(self):
        self.fader_in = MIDIFader()
        self.fader_out = MIDIFader()
        self.inverted = True

    def get_inverted(self) -> bool:
        """
        Returns:
            inverted status
        """
        return self.inverted

    def set_inverted(self, invert: bool) -> None:
        """Set inverted status

        Args:
            invert: True or False
        """
        self.inverted = invert

    def moved(self, msg: mido.Message, midi_fader) -> None:
        """Fader moved

        Args:
            msg: MIDI message
            midi_fader: Crossfade MIDI fader
        """
        App().midi.enqueue(msg)
        if midi_fader is self.fader_in:
            xfade_val = App().crossfade.scale_b.value
        else:
            xfade_val = App().crossfade.scale_a.value
        if msg.type == "pitchwheel":
            val = (msg.pitch + 8192) / 16383
        elif msg.type == "control_change":
            val = msg.value / 127
        if self.get_inverted():
            val = val * 255
        else:
            val = abs((val - 1) * 255)
        if not midi_fader.is_valid(val, xfade_val):
            return
        self._xfade(midi_fader, val)

    def _xfade(self, fader: MIDIFader, value: float) -> None:
        """Manual Crossfade

        Args:
            fader : In or Out
            value : fader value (0 - 255)
        """
        App().crossfade.manual = True

        if self.fader_out.get_value() == 255 and self.fader_in.get_value() == 255:
            if self.get_inverted():
                self.set_inverted(False)
                self.set_inverted(False)
            else:
                self.set_inverted(True)
                self.set_inverted(True)
            self.fader_out.value = 0
            self.fader_in.value = 0

        if fader == self.fader_out:
            if App().virtual_console:
                App().virtual_console.scale_a.set_value(value)
            else:
                App().crossfade.scale_a.set_value(value)
                App().crossfade.scale_moved(App().crossfade.scale_a)
        elif fader == self.fader_in:
            if App().virtual_console:
                App().virtual_console.scale_b.set_value(value)
            else:
                App().crossfade.scale_b.set_value(value)
                App().crossfade.scale_moved(App().crossfade.scale_b)
