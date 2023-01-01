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


class MidiFader:
    """MIDI Faders"""

    value: int
    inverted: bool

    def __init__(self):
        self.value = 0
        self.inverted = True

    def get_inverted(self) -> bool:
        """
        Returns:
            inverted status
        """
        return self.inverted

    def set_inverted(self, inv: bool) -> None:
        """Set inverted status

        Args:
            inv: True or False
        """
        self.inverted = inv

    def get_value(self) -> int:
        """
        Returns:
            Fader's value
        """
        return self.value

    def set_value(self, value: int) -> None:
        """Set fader's value

        Args:
            value: New value
        """
        if 0 <= value < 16384:
            self.value = value


def xfade_out(msg: mido.Message) -> None:
    """Crossfade Out

    Args:
        msg: MIDI message
    """
    if msg.type == "pitchwheel":
        _xfade(App().midi.xfade_out, msg.pitch + 8192)
    elif msg.type == "control_change":
        _xfade(App().midi.xfade_out, round((msg.value / 127) * 16383))


def xfade_in(msg: mido.Message) -> None:
    """Crossfade In

    Args:
        msg: MIDI message
    """
    if msg.type == "pitchwheel":
        _xfade(App().midi.xfade_in, msg.pitch + 8192)
    elif msg.type == "control_change":
        _xfade(App().midi.xfade_in, round((msg.value / 127) * 16383))


def _xfade(fader: MidiFader, value: int) -> None:
    """Crossfade

    Args:
        fader : In or Out
        value : fader value (0 - 16383)
    """
    App().crossfade.manual = True

    if fader.get_inverted():
        val = (value / 16383) * 255
        fader.set_value(value)
    else:
        val = abs(((value - 16383) / 16383) * 255)
        fader.set_value(abs(value - 16383))

    if fader == App().midi.xfade_out:
        if App().virtual_console:
            App().virtual_console.scale_a.set_value(val)
        else:
            App().crossfade.scale_a.set_value(val)
            App().crossfade.scale_moved(App().crossfade.scale_a)
    elif fader == App().midi.xfade_in:
        if App().virtual_console:
            App().virtual_console.scale_b.set_value(val)
        else:
            App().crossfade.scale_b.set_value(val)
            App().crossfade.scale_moved(App().crossfade.scale_b)
    if (
        App().midi.xfade_out.get_value() == 16383
        and App().midi.xfade_in.get_value() == 16383
    ):
        if App().midi.xfade_out.get_inverted():
            App().midi.xfade_out.set_inverted(False)
            App().midi.xfade_in.set_inverted(False)
        else:
            App().midi.xfade_out.set_inverted(True)
            App().midi.xfade_in.set_inverted(True)
        App().midi.xfade_out.set_value(0)
        App().midi.xfade_in.set_value(0)
