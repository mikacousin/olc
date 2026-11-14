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
from typing import Deque

import mido

from olc.core.backends.midi.control_change import MidiControlChanges
from olc.core.backends.midi.fader import MIDIFader
from olc.core.backends.midi.lcd import MackieLCD
from olc.core.backends.midi.notes import MidiNotes
from olc.core.backends.midi.pitchwheel import MidiPitchWheel
from olc.core.backends.midi.ports import MidiPorts, StrvSettings
from olc.core.backends.midi.xfade import MidiXFade
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    import olc.core.backends.midi
    from olc.core.app import CoreApplication
    from olc.fader import Fader, FaderBank


class Queue:
    """Queue implementation based on deque"""

    _elements: Deque[mido.Message]

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
        app: CoreApplication,
        enqueue_cb: typing.Callable[[mido.Message], None],
        fader_bank: FaderBank,
    ) -> None:
        self.notes = MidiNotes(typing.cast("olc.core.backends.midi.Midi", midi), app)
        self.control_change = MidiControlChanges(
            typing.cast("olc.core.backends.midi.Midi", midi), app
        )
        self.pitchwheel = MidiPitchWheel(
            typing.cast("olc.core.backends.midi.Midi", midi), app
        )
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


# pylint: disable=too-few-public-methods
class MidiSend:
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
                # print("MIDI sent:", msg)
                port.port.send(msg)


# pylint: disable=too-many-instance-attributes
class Midi:
    """MIDI messages from controllers"""

    learning: str
    messages: MidiMessages
    faders: MidiFaders
    xfade: MidiXFade
    ports: MidiPorts
    send: MidiSend
    app: CoreApplication
    app_delegate: CoreApplication
    _pause_blink_timer: RepeatedTimer | None
    _pause_blink_state: bool

    def __init__(
        self,
        app: CoreApplication,
        on_ports_changed: typing.Callable[[], None] | None = None,
    ) -> None:
        self.app = app
        self.app_delegate = app
        self.core = app.core
        self.lightshow = app.core.lightshow
        self.learning = ""
        self.faders = MidiFaders()
        # Create crossfade Faders
        self.xfade = MidiXFade(typing.cast("olc.core.backends.midi.Midi", self), app)
        # Create and Open MIDI ports
        self.ports = MidiPorts(
            typing.cast("olc.core.backends.midi.Midi", self),
            typing.cast("StrvSettings | None", getattr(app, "settings", None)),
            on_ports_changed,
        )
        self.send = MidiSend(self.ports)
        self.messages = MidiMessages(self, app, self.enqueue, self.lightshow.fader_bank)
        self._pause_blink_timer = None
        self._pause_blink_state = False
        self.controler_reset()
        self._subscribe_core_events()

    def _subscribe_core_events(self) -> None:
        """Subscribe to Core events to drive hardware feedback (headless safe)."""
        core = self.core
        core.subscribe("fader.page_changed", self._on_fader_page_changed)
        core.subscribe("fader.level_changed", self._on_fader_level_changed)
        core.subscribe("fader.flash_changed", self._on_fader_flash_changed)
        core.subscribe("fader.changed", self._on_fader_changed)
        core.subscribe("group.updated", self._on_group_updated)
        core.subscribe("independent.level_changed", self._on_independent_changed)
        core.subscribe("show.new", self._on_show_changed)
        core.subscribe("show.loaded", self._on_show_changed)
        core.subscribe("show.imported", self._on_show_changed)
        core.subscribe("playback.go_started", self._on_playback_go_started)
        core.subscribe("playback.go_triggered", self._on_playback_go_triggered)
        core.subscribe("playback.go_back_started", self._on_playback_go_back_started)
        core.subscribe("playback.pause_triggered", self._on_playback_pause_triggered)
        core.subscribe(
            "playback.transition_completed", self._on_playback_transition_completed
        )
        core.subscribe("playback.goback_completed", self._on_playback_goback_completed)
        core.subscribe("playback.stopped", self._on_playback_stopped)
        core.subscribe("playback.xfade_moved", self._on_playback_xfade_moved)

    def _on_fader_page_changed(self, _page: int) -> None:
        """Sync MIDI faders and LCD when the fader page changes."""
        fader_bank = self.lightshow.fader_bank
        for fader in fader_bank.faders[fader_bank.active_page].values():
            if 0 < fader.index <= len(self.faders.faders):
                self.faders.faders[fader.index - 1].set_state(fader.level)
        self.update_faders()

    def _on_fader_level_changed(self, fader_index: int, level: float) -> None:
        """Update MIDI fader anchor state and controller feedback on level change."""
        if 0 < fader_index <= len(self.faders.faders):
            self.faders.faders[fader_index - 1].set_state(level)
        midi_name = f"fader_{fader_index}"
        self.messages.control_change.send(midi_name, round(level * 127))
        self.messages.pitchwheel.send(midi_name, round(level * 16383) - 8192)

    def _on_fader_flash_changed(self, fader_index: int, _pressed: bool) -> None:
        """Send controller fader feedback when a flash button changes level."""
        fader = self.lightshow.fader_bank.get_fader(fader_index)
        midi_name = f"fader_{fader_index}"
        self.messages.control_change.send(midi_name, round(fader.level * 127))
        self.messages.pitchwheel.send(midi_name, round(fader.level * 16383) - 8192)

    def _on_fader_changed(self, page: int, index: int) -> None:
        """Refresh controller when a fader assignment changes."""
        fader_bank = self.lightshow.fader_bank
        if page == fader_bank.active_page and index in fader_bank.faders.get(page, {}):
            self.update_fader(fader_bank.faders[page][index])
        else:
            self.update_faders()

    def _on_group_updated(self, group: typing.Any) -> None:  # noqa: ANN401
        """Refresh LCD names when a group (possibly bound to a fader) changes."""
        for faders in self.lightshow.fader_bank.faders.values():
            for fader in faders.values():
                if fader.contents is group:
                    fader.text = group.text
        self.messages.lcd.show_faders()

    def _on_independent_changed(self, number: int, level: float) -> None:
        """Send independent feedback (motor fader state, LEDs) to controller."""
        if number <= 6:
            self.faders.inde_faders[number - 1].set_state(round(level * 255))
            self.messages.control_change.send(
                f"inde_led_{number}", 32 + int(level * 12)
            )
        else:
            velocity = 0 if level < 0.5 else 127
            self.messages.notes.send(f"inde_{number}", velocity)

    def _on_show_changed(self, *_args: typing.Any) -> None:  # noqa: ANN401
        """Resync controller after a show is created, loaded or imported."""
        self.update_faders()

    def _on_playback_go_started(self, *_args: typing.Any) -> None:  # noqa: ANN401
        """Light on GO button LED when playback transition starts."""
        self.button_on("playback.go")

    def _on_playback_go_triggered(
        self, data: dict[str, typing.Any] | None = None
    ) -> None:
        """Light on GO button LED when playback.go action triggers."""
        if isinstance(data, dict) and data.get("active"):
            self.button_on("playback.go")

    def _on_playback_go_back_started(self, *_args: typing.Any) -> None:  # noqa: ANN401
        """Light on Go Back button LED when go-back starts."""
        self.button_on("playback.go_back")

    def _on_playback_pause_triggered(
        self, data: dict[str, typing.Any] | None = None
    ) -> None:
        """Update Pause button LED blinking state from pause feedback payload."""
        if isinstance(data, dict) and data.get("active"):
            self.button_on("playback.pause")
        else:
            self.button_off("playback.pause")

    def _on_playback_transition_completed(
        self,
        *_args: typing.Any,  # noqa: ANN401
    ) -> None:
        """Light off GO button LED when transition completes."""
        self.button_off("playback.go")

    def _on_playback_goback_completed(
        self,
        *_args: typing.Any,  # noqa: ANN401
    ) -> None:
        """Light off Go Back button LED when go-back completes."""
        self.button_off("playback.go_back")

    def _on_playback_stopped(self, *_args: typing.Any) -> None:  # noqa: ANN401
        """Light off GO and Pause button LEDs when playback stops."""
        self.button_off("playback.go")
        self.button_off("playback.pause")

    def _on_playback_xfade_moved(self, fader_key: str, val_255: int) -> None:
        """Sync MIDI manual crossfade fader anchor states."""
        if fader_key == "a":
            self.xfade.fader_out.set_state(int(val_255))
        elif fader_key == "b":
            self.xfade.fader_in.set_state(int(val_255))

    def stop(self) -> None:
        """Stop MIDI"""
        if self._pause_blink_timer is not None:
            self._pause_blink_timer.stop()
            self._pause_blink_timer = None
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

        core = getattr(self.app, "core", None)
        if core is not None and hasattr(core, "action_registry") and self.learning:
            if msg.type == "note_on":
                core.action_registry.execute(
                    "midi.assign_mapping",
                    "note",
                    self.learning,
                    msg.channel,
                    msg.note,
                )
                return
            if msg.type == "control_change":
                core.action_registry.execute(
                    "midi.assign_mapping",
                    "control_change",
                    self.learning,
                    msg.channel,
                    msg.control,
                )
                return
            if msg.type == "pitchwheel":
                core.action_registry.execute(
                    "midi.assign_mapping",
                    "pitchwheel",
                    self.learning,
                    msg.channel,
                    msg.pitch,
                )
                return

        if msg.type == "note_on":
            self.messages.notes.learn(msg, self.learning)
        elif msg.type == "control_change":
            self.messages.control_change.learn(msg, self.learning)
            self.messages.notes.learn_cc(msg, self.learning)
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
            for values in self.messages.notes.cc_notes.values():
                channel, control = values
                if control != -1:
                    msg = mido.Message(
                        "control_change",
                        channel=channel,
                        control=control,
                        value=0,
                        time=0,
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
        if action == "playback.pause":
            if self._pause_blink_timer is not None:
                self._pause_blink_timer.stop()
            self._pause_blink_state = True
            self.messages.notes.send("playback.pause", 127)
            self._pause_blink_timer = RepeatedTimer(0.5, self._blink_pause_led)
        else:
            self.messages.notes.send(action, 127)
            if timer:
                threading.Timer(timer, self.messages.notes.send, [action, 0]).start()

    def button_off(self, action: str) -> None:
        """Light off button

        Args:
            action: Action name
        """
        if action == "playback.pause":
            if self._pause_blink_timer is not None:
                self._pause_blink_timer.stop()
                self._pause_blink_timer = None
            self.messages.notes.send("playback.pause", 0)
        else:
            self.messages.notes.send(action, 0)

    def _blink_pause_led(self) -> None:
        """Toggle pause MIDI LED state for blinking effect"""
        self._pause_blink_state = not self._pause_blink_state
        self.messages.notes.send(
            "playback.pause", 127 if self._pause_blink_state else 0
        )

    def send_cc(self, channel: int, control: int, value: int) -> None:
        """Send a Control Change message.

        Args:
            channel: The MIDI channel (0-15).
            control: The CC control number.
            value: The CC value (0-127).
        """
        msg = mido.Message(
            "control_change",
            channel=channel,
            control=control,
            value=value,
            time=0,
        )
        self.enqueue(msg)

    def to_dict(self) -> dict[str, dict[str, typing.Any]]:
        """Serialize MIDI mappings for show file storage."""
        return {
            "note": self.messages.notes.notes,
            "note_cc": self.messages.notes.cc_notes,
            "control_change": self.messages.control_change.control_change,
            "pitchwheel": self.messages.pitchwheel.pitchwheel,
        }

    def from_dict(self, midi_data: dict[str, typing.Any]) -> None:
        """Restore MIDI mappings from parsed show data."""
        legacy_mapping = {
            "go": "playback.go",
            "go_back": "playback.go_back",
            "pause": "playback.pause",
            "seq_plus": "playback.sequence_plus",
            "seq_minus": "playback.sequence_minus",
        }

        for action, value in midi_data.get("note", {}).items():
            if value != [0, -1]:
                normalized_action = legacy_mapping.get(action, action)
                if normalized_action in self.messages.notes.notes:
                    self.messages.notes.notes[normalized_action] = value
        note_cc = midi_data.get("note_cc")
        if note_cc:
            for action, value in note_cc.items():
                if value != [0, -1]:
                    normalized_action = legacy_mapping.get(action, action)
                    if normalized_action in self.messages.notes.cc_notes:
                        self.messages.notes.cc_notes[normalized_action] = value
        for action, value in midi_data.get("control_change", {}).items():
            if value != [0, -1]:
                self.messages.control_change.control_change[action] = value
        for action, value in midi_data.get("pitchwheel", {}).items():
            if value != -1:
                self.messages.pitchwheel.pitchwheel[action] = value
