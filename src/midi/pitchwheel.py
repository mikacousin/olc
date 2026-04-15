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
import typing

import mido
from gi.repository import GLib

if typing.TYPE_CHECKING:
    from olc.application import Application
    from olc.midi import Midi


class MidiPitchWheel:
    """MIDI pitchwheel messages from controllers"""

    pitchwheel: dict[str, int]

    def __init__(self, midi: Midi, app_delegate: Application) -> None:
        self.midi = midi
        self.app_delegate = app_delegate
        # Default MIDI pitchwheel values : "action": Channel
        self.pitchwheel = {
            "crossfade_out": -1,
            "crossfade_in": -1,
        }
        for i in range(10):
            for j in range(9):
                self.pitchwheel[f"fader_{j + i * 10 + 1}"] = j

    def reset(self) -> None:
        """Remove all MIDI pitchwheel"""
        for action in self.pitchwheel:
            self.pitchwheel[action] = -1

    def scan(self, msg: mido.Message) -> None:
        """Scan MIDI pitchwheel messages

        Args:
            msg: MIDI message
        """
        for key, value in self.pitchwheel.items():
            if msg.channel == value:
                if key[:6] == "fader_":
                    self._update_fader(msg, int(key[6:]) - 1)
                    break
                if key[:13] == "crossfade_out":
                    GLib.idle_add(self.midi.xfade.moved, msg, self.midi.xfade.fader_out)
                elif key[:12] == "crossfade_in":
                    GLib.idle_add(self.midi.xfade.moved, msg, self.midi.xfade.fader_in)
                elif func := getattr(self, f"_function_{key}", None):
                    GLib.idle_add(func, None, msg)

    def send(self, midi_name: str, value: int) -> None:
        """Send MIDI pitchwheel message

        Args:
            midi_name: action string
            value: value to send
        """
        channel = self.pitchwheel.get(midi_name, -1)
        if channel != -1:
            msg = mido.Message("pitchwheel", channel=channel, pitch=value, time=0)
            self.midi.enqueue(msg)

    def learn(self, msg: mido.Message, learning: str) -> None:
        """Learn new MIDI Pitchwheel control

        Args:
            msg: MIDI message
            learning: action to update
        """
        if self.pitchwheel.get(learning):
            for key, channel in self.pitchwheel.items():
                if channel == msg.channel:
                    self.pitchwheel.update({key: -1})
            self.pitchwheel.update({learning: msg.channel})

    def _update_fader(self, msg: mido.Message, index: int) -> None:
        val = (msg.pitch + 8192) / 16383
        if self.app_delegate.virtual_console:
            GLib.idle_add(
                self.app_delegate.virtual_console.faders[index].set_value, val * 255
            )
            GLib.idle_add(
                self.app_delegate.virtual_console.fader_moved,
                self.app_delegate.virtual_console.faders[index],
            )
        else:
            number = index + 1
            fader = self.app_delegate.lightshow.fader_bank.get_fader(number)
            GLib.idle_add(fader.set_level, val)
