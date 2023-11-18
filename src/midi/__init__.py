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
import threading
import time
import mido
from olc.define import App
from .control_change import MidiControlChanges
from .notes import MidiNotes
from .ports import MidiPorts
from .pitchwheel import MidiPitchWheel
from .xfade import MidiFader
from .lcd import MackieLCD


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
        self.lcd = MackieLCD()

        # Create xfade Faders
        self.xfade_out = MidiFader()
        self.xfade_in = MidiFader()

        # Create and Open MIDI ports
        self.ports = MidiPorts()

        # Send MIDI messages every 25 milliseconds
        self.out = []
        self.rt = RepeatedTimer(.025, self.send)

    def stop(self) -> None:
        """Stop MIDI"""
        self.rt.stop()
        self.controler_reset()
        self.ports.close_output()
        self.ports.close_input()

    def send(self) -> None:
        """Send MIDI messages from the queue"""
        for msg in self.out:
            for outport in self.ports.outports:
                outport.send(msg)
        self.out.clear()

    def learn(self, msg: mido.Message) -> None:
        """Learn new MIDI control

        Args:
            msg: MIDI message
        """
        if self.ports.outports:
            self.out.append(msg)
        if msg.type == "note_on":
            self.notes.learn(msg, self.midi_learn)
        elif msg.type == "control_change":
            self.control_change.learn(msg, self.midi_learn)
        elif msg.type == "pitchwheel":
            self.pitchwheel.learn(msg, self.midi_learn)
        # Tag filename as modified
        App().ascii.set_modified()

    def get_midi_learn(self) -> str:
        """Return MIDI Learn string

        Returns:
            MIDI Learn action
        """
        return self.midi_learn

    def controler_reset(self) -> None:
        """Reset Mackie Controler"""
        for outport in self.ports.outports:
            # Clear LCD
            text = 56 * " "
            data = [0, 0, 102, 20, 18, 0] + [ord(c) for c in text]
            msg = mido.Message("sysex", data=data)
            outport.send(msg)
            data = [0, 0, 102, 20, 18, 56] + [ord(c) for c in text]
            msg = mido.Message("sysex", data=data)
            outport.send(msg)
            # Faders at 0
            for i in range(16):
                msg = mido.Message("pitchwheel", channel=i, pitch=-8192, time=0)
                outport.send(msg)

    def gm_init(self) -> None:
        """Grand Master Fader"""
        midi_name = "gm"
        item = App().midi.control_change.control_change[midi_name]
        if item[1] != -1:
            msg = mido.Message(
                "control_change",
                channel=item[0],
                control=item[1],
                value=int(App().dmx.grand_master / 2),
                time=0,
            )
            self.out.append(msg)
        item = App().midi.pitchwheel.pitchwheel.get(midi_name, -1)
        if item != -1:
            val = int(((App().dmx.grand_master / 255) * 16383) - 8192)
            msg = mido.Message("pitchwheel", channel=item, pitch=val, time=0)
            self.out.append(msg)


class RepeatedTimer:
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.next_call = time.time()
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self.next_call += self.interval
            self._timer = threading.Timer(self.next_call - time.time(), self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False
