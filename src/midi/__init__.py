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
from __future__ import annotations

import threading
import typing
from collections import deque
from dataclasses import dataclass

import mido
from olc.midi.control_change import MidiControlChanges
from olc.midi.fader import MIDIFader
from olc.midi.lcd import MackieLCD
from olc.midi.notes import MidiNotes
from olc.midi.pitchwheel import MidiPitchWheel
from olc.midi.ports import MidiPorts
from olc.midi.xfade import MidiXFade
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    from olc.application import Application
    from olc.fader import Fader, FaderBank


class Queue:
    """Queue implementation based on deque"""

    _elements: mido.Message

    def __init__(self) -> None:
        self._elements = deque()

    def __len__(self) -> int:
        return len(self._elements)

    def __iter__(self) -> typing.Iterator:
        while len(self) > 0:
            yield self.dequeue()

    def enqueue(self, element: mido.Message) -> None:
        """Add a element

        Args:
            element: Element to add
        """
        self._elements.append(element)

    def dequeue(self) -> mido.Message:
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

    def __init__(
        self,
        midi: Midi,
        app_delegate: Application,
        enqueue_cb: typing.Callable[[mido.Message], None],
        fader_bank: FaderBank,
    ) -> None:
        self.notes = MidiNotes(midi, app_delegate)
        self.control_change = MidiControlChanges()
        self.pitchwheel = MidiPitchWheel(midi, app_delegate)
        self.lcd = MackieLCD(enqueue_cb, fader_bank)


@dataclass
class MidiFaders:
    """MIDI Faders"""

    faders: list[MIDIFader]
    inde_faders: list[MIDIFader]

    def __init__(self) -> None:
        self.faders = []
        for _ in range(10):
            self.faders.append(MIDIFader())
        self.inde_faders = []
        for _ in range(6):
            self.inde_faders.append(MIDIFader())


class MidiSend:  # pylint: disable=R0903
    """Send MIDI messages"""

    ports: MidiPorts
    queue: Queue
    thread: RepeatedTimer

    def __init__(self, ports: MidiPorts) -> None:
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

    def __init__(
        self,
        app_delegate: Application,
        on_ports_changed: typing.Callable[[], None] | None = None,
    ) -> None:
        self.lightshow = app_delegate.lightshow
        self.learning = ""
        self.faders = MidiFaders()
        # Create crossfade Faders
        self.xfade = MidiXFade(self, app_delegate)
        # Create and Open MIDI ports
        self.ports = MidiPorts(self, app_delegate.settings, on_ports_changed)
        self.send = MidiSend(self.ports)
        self.messages = MidiMessages(
            self, app_delegate, self.enqueue, self.lightshow.fader_bank
        )
        self.controler_reset()

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
        self.lightshow.set_modified()

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
                msg = mido.Message(
                    "control_change", channel=0, control=i, value=0, time=0
                )
                port.port.send(msg)
            # Light off buttons
            for values in self.messages.notes.notes.values():
                channel, note = values
                if note != -1:
                    msg = mido.Message(
                        "note_on", channel=channel, note=note, velocity=0, time=0
                    )
                    port.port.send(msg)
            port.port.reset()

    def update_faders(self) -> None:
        """Send faders value and update LCD display"""
        fader_bank = self.lightshow.fader_bank
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

    def button_on(self, action: str, timer: float = 0) -> None:
        """Light on button

        Args:
            action: Action name
            timer: Optional time to light off
        """
        self.messages.notes.send(action, 127)
        if timer:
            threading.Timer(timer, self.messages.notes.send, [action, 0]).start()

    def button_off(self, action: str) -> None:
        """Light off button

        Args:
            action: Action name
        """
        self.messages.notes.send(action, 0)
