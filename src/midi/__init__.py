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
from __future__ import annotations

import typing
from collections import deque
from dataclasses import dataclass

import mido
from olc.define import App
from olc.timer import RepeatedTimer

from .control_change import MidiControlChanges
from .fader import MIDIFader
from .lcd import MackieLCD
from .notes import MidiNotes
from .pitchwheel import MidiPitchWheel
from .ports import MidiPorts
from .xfade import MidiXFade

if typing.TYPE_CHECKING:
    from olc.fader import Fader


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


@dataclass
class MidiMessages:
    """MIDI Messages"""

    notes: MidiNotes
    control_change: MidiControlChanges
    pitchwheel: MidiPitchWheel
    lcd: MackieLCD

    def __init__(self):
        self.notes = MidiNotes()
        self.control_change = MidiControlChanges()
        self.pitchwheel = MidiPitchWheel()
        self.lcd = MackieLCD()


@dataclass
class MidiFaders:
    """MIDI Faders"""

    faders: list[MIDIFader]
    main_fader: MIDIFader
    inde_faders: list[MIDIFader]

    def __init__(self):
        self.faders = []
        for _ in range(10):
            self.faders.append(MIDIFader())
        self.main_fader = MIDIFader()
        self.inde_faders = []
        for _ in range(6):
            self.inde_faders.append(MIDIFader())


class MidiSend:  # pylint: disable=R0903
    """Send MIDI messages"""

    ports: MidiPorts
    queue: Queue
    thread: RepeatedTimer

    def __init__(self, ports):
        self.ports = ports
        # Send MIDI messages every 25 milliseconds
        self.queue = Queue()
        self.thread = RepeatedTimer(0.025, self.send)

    def send(self) -> None:
        """Send MIDI messages from the queue"""
        for msg in self.queue:
            for port in self.ports.ports:
                port.port.send(msg)


class Midi:
    """MIDI messages from controllers"""

    learning: str
    messages: MidiMessages
    faders: MidiFaders
    xfade: MidiXFade
    ports: MidiPorts
    send: MidiSend

    def __init__(self):
        self.learning = ""
        self.messages = MidiMessages()
        self.faders = MidiFaders()
        # Create crossfade Faders
        self.xfade = MidiXFade()
        # Create and Open MIDI ports
        self.ports = MidiPorts()
        self.controler_reset()
        self.send = MidiSend(self.ports)

    def stop(self) -> None:
        """Stop MIDI"""
        self.ports.poll.stop()
        self.send.thread.stop()
        self.controler_reset()
        self.ports.close()

    def enqueue(self, msg: mido.Message) -> None:
        """Enqueue MIDI messages to send

        Args:
            msg: MIDI message
        """
        self.send.queue.enqueue(msg)

    def learn(self, msg: mido.Message) -> None:
        """Learn new MIDI control

        Args:
            msg: MIDI message
        """
        if self.ports.ports:
            self.enqueue(msg)
        if msg.type == "note_on":
            self.messages.notes.learn(msg, self.learning)
        elif msg.type == "control_change":
            self.messages.control_change.learn(msg, self.learning)
        elif msg.type == "pitchwheel":
            self.messages.pitchwheel.learn(msg, self.learning)
        # Tag filename as modified
        App().lightshow.set_modified()

    def reset_messages(self) -> None:
        """Remove all MIDI messages"""
        self.messages.notes.reset()
        self.messages.control_change.reset()
        self.messages.pitchwheel.reset()

    def controler_reset(self) -> None:
        """Reset Mackie Controller"""
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
                msg = mido.Message("control_change",
                                   channel=0,
                                   control=i,
                                   value=0,
                                   time=0)
                port.port.send(msg)
            port.port.reset()

    def main_fader_init(self) -> None:
        """Main Fader"""
        midi_name = "main_fader"
        channel, control = self.messages.control_change.control_change[midi_name]
        if control != -1:
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=round(App().backend.dmx.main_fader.value * 127),
                time=0,
            )
            self.enqueue(msg)
        channel = self.messages.pitchwheel.pitchwheel.get(midi_name, -1)
        if channel != -1:
            val = round((App().backend.dmx.main_fader.value * 16383) - 8192)
            msg = mido.Message("pitchwheel", channel=channel, pitch=val, time=0)
            self.enqueue(msg)

    def update_faders(self) -> None:
        """Send faders value and update LCD display"""
        fader_bank = App().lightshow.fader_bank
        for fader in fader_bank.faders[fader_bank.active_page].values():
            midi_name = f"fader_{fader.index}"
            channel, control = self.messages.control_change.control_change[midi_name]
            if control != -1:
                msg = mido.Message(
                    "control_change",
                    channel=channel,
                    control=control,
                    value=round(fader.level * 127),
                    time=0,
                )
                self.enqueue(msg)
            channel = self.messages.pitchwheel.pitchwheel.get(midi_name, -1)
            if channel != -1:
                val = round((fader.level * 16383) - 8192)
                msg = mido.Message("pitchwheel", channel=channel, pitch=val, time=0)
                self.enqueue(msg)
        self.messages.lcd.show_faders()

    def update_fader(self, fader: Fader) -> None:
        """Send fader level and update LCD

        Args:
            fader: Fader to update
        """
        midi_name = f"fader_{fader.index}"
        channel, control = self.messages.control_change.control_change[midi_name]
        if control != -1:
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=round(fader.level * 127),
                time=0,
            )
            self.enqueue(msg)
        channel = self.messages.pitchwheel.pitchwheel.get(midi_name, -1)
        if channel != -1:
            val = round((fader.level * 16383) - 8192)
            msg = mido.Message("pitchwheel", channel=channel, pitch=val, time=0)
            self.enqueue(msg)
        self.messages.lcd.show_fader(fader)
