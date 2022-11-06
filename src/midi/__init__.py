# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from gi.repository import GLib
from .control_change import MidiControlChanges
from .notes import MidiNotes
from .ports import MidiPorts
from .pitchwheel import MidiPitchWheel
from .xfade import MidiFader


class Midi:
    """MIDI messages from controllers"""

    ports: MidiPorts
    midi_learn: str
    notes: MidiNotes
    control_change: MidiControlChanges
    pitchwheel: MidiPitchWheel
    xfade_out: MidiFader
    xfade_in: MidiFader

    def __init__(self):
        self.midi_learn = ""

        self.notes = MidiNotes()
        self.control_change = MidiControlChanges()
        self.pitchwheel = MidiPitchWheel()

        # Create xfade Faders
        self.xfade_out = MidiFader()
        self.xfade_in = MidiFader()

        # Create and Open MIDI ports
        self.ports = MidiPorts()

    def learn(self, msg: mido.Message) -> None:
        """Learn new MIDI control

        Args:
            msg: MIDI message
        """
        if self.ports.outports:
            for outport in self.ports.outports:
                GLib.idle_add(outport.send, msg)

        if msg.type == "note_on":
            self.notes.learn(msg, self.midi_learn)
        elif msg.type == "control_change":
            self.control_change.learn(msg, self.midi_learn)
        elif msg.type == "pitchwheel":
            self.pitchwheel.learn(msg, self.midi_learn)

    def get_midi_learn(self) -> str:
        """Return MIDI Learn string

        Returns:
            MIDI Learn action
        """
        return self.midi_learn
