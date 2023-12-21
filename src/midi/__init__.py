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
from collections import deque
import mido
from olc.define import App
from olc.timer import RepeatedTimer
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
        self.controler_reset()

        # Send MIDI messages every 25 milliseconds
        self.queue = Queue()
        self.thread = RepeatedTimer(0.025, self.send)

    def stop(self) -> None:
        """Stop MIDI"""
        self.ports.poll.stop()
        self.thread.stop()
        self.controler_reset()
        self.ports.close()

    def send(self) -> None:
        """Send MIDI messages from the queue"""
        for msg in self.queue:
            for port in self.ports.ports:
                port.port.send(msg)

    def learn(self, msg: mido.Message) -> None:
        """Learn new MIDI control

        Args:
            msg: MIDI message
        """
        if self.ports.ports:
            self.queue.enqueue(msg)
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
        for port in self.ports.ports:
            # Clear LCD
            text = 56 * " "
            data = [0, 0, 102, 20, 18, 0] + [ord(c) for c in text]
            msg = mido.Message("sysex", data=data)
            port.port.send(msg)
            data = [0, 0, 102, 20, 18, 56] + [ord(c) for c in text]
            msg = mido.Message("sysex", data=data)
            port.port.send(msg)
            # Faders at 0
            for i in range(16):
                msg = mido.Message("pitchwheel", channel=i, pitch=-8192, time=0)
                port.port.send(msg)
            for i in range(48, 56):
                msg = mido.Message(
                    "control_change", channel=0, control=i, value=0, time=0
                )
                port.port.send(msg)
            port.port.reset()

    def gm_init(self) -> None:
        """Grand Master Fader"""
        midi_name = "gm"
        channel, control = self.control_change.control_change[midi_name]
        if control != -1:
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=int(App().dmx.grand_master / 2),
                time=0,
            )
            self.queue.enqueue(msg)
        channel = self.pitchwheel.pitchwheel.get(midi_name, -1)
        if channel != -1:
            val = int(((App().dmx.grand_master / 255) * 16383) - 8192)
            msg = mido.Message("pitchwheel", channel=channel, pitch=val, time=0)
            self.queue.enqueue(msg)

    def update_masters(self) -> None:
        """Send faders value and update display"""
        for master in App().masters:
            if master.page == App().fader_page:
                midi_name = f"master_{master.number}"
                channel, control = self.control_change.control_change[midi_name]
                if control != -1:
                    msg = mido.Message(
                        "control_change",
                        channel=channel,
                        control=control,
                        value=int(master.value / 2),
                        time=0,
                    )
                    self.queue.enqueue(msg)
                channel = self.pitchwheel.pitchwheel.get(midi_name, -1)
                if channel != -1:
                    val = int(((master.value / 255) * 16383) - 8192)
                    msg = mido.Message("pitchwheel", channel=channel, pitch=val, time=0)
                    self.queue.enqueue(msg)
        self.lcd.show_masters()


class Queue:
    """Queue implementation based on deque"""

    def __init__(self):
        self._elements = deque()

    def __len__(self):
        return len(self._elements)

    def __iter__(self):
        while len(self) > 0:
            yield self.dequeue()

    def enqueue(self, element):
        """Add a element

        Args:
            element: Element to add
        """
        self._elements.append(element)

    def dequeue(self):
        """Remove first element

        Returns:
            The first element
        """
        return self._elements.popleft()
