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
from typing import Dict
import mido
from gi.repository import GLib
from olc.define import App
import olc.midi.xfade


class MidiPitchWheel:
    """MIDI pitchwheel messages from controllers"""

    pitchwheel: Dict[str, int]

    def __init__(self):
        # Default MIDI pitchwheel values : "action": Channel
        self.pitchwheel = {
            "crossfade_out": -1,
            "crossfade_in": -1,
            "gm": 8,
        }
        for i in range(10):
            for j in range(8):
                self.pitchwheel[f"master_{str(j + i * 10 + 1)}"] = j

    def scan(self, msg: mido.Message) -> None:
        """Scan MIDI pitchwheel messages

        Args:
            msg: MIDI message
        """
        for key, value in self.pitchwheel.items():
            if msg.channel == value:
                if key[:7] == "master_":
                    _update_master(msg, int(key[7:]) - 1)
                    break
                if key[:13] == "crossfade_out":
                    GLib.idle_add(olc.midi_xfade.xfade_out, msg)
                elif key[:12] == "crossfade_in":
                    GLib.idle_add(olc.midi_xfade.xfade_in, msg)
                elif func := getattr(self, f"_function_{key}", None):
                    GLib.idle_add(func, None, msg)

    def learn(self, msg: mido.Message, midi_learn: str) -> None:
        """Learn new MIDI Pitchwheel control

        Args:
            msg: MIDI message
            midi_learn: action to update
        """
        if self.pitchwheel.get(midi_learn):
            for key, channel in self.pitchwheel.items():
                if channel == msg.channel:
                    self.pitchwheel.update({key: -1})
            self.pitchwheel.update({midi_learn: msg.channel})

    def _function_gm(self, _port: str, msg: mido.Message) -> None:
        """Grand Master

        Args:
            msg: MIDI message
        """
        val = ((msg.pitch + 8192) / 16383) * 255
        if App().virtual_console:
            App().virtual_console.scale_grand_master.set_value(val)
            App().virtual_console.grand_master_moved(
                App().virtual_console.scale_grand_master
            )
        else:
            App().dmx.grand_master = val
            App().window.grand_master.queue_draw()


def _update_master(msg: mido.Message, index: int) -> None:
    val = ((msg.pitch + 8192) / 16383) * 255
    if App().virtual_console:
        GLib.idle_add(App().virtual_console.masters[index].set_value, val)
        GLib.idle_add(
            App().virtual_console.master_moved, App().virtual_console.masters[index]
        )
    else:
        page = App().fader_page
        number = index + 1
        master = None
        for master in App().masters:
            if master.page == page and master.number == number:
                break
        GLib.idle_add(master.set_level, val)
