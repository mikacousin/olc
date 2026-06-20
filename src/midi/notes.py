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

import typing

import mido
from gi.repository import Gdk, GLib
from olc.define import MAX_FADER_PAGE
from olc.zoom import zoom

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application
    from olc.independent import Independent
    from olc.midi import Midi


# Mapping for simple actions to avoid duplicating methods.
# Format: "action_name": ("virtual_console_widget_name",
#                         Gdk.KEY_*, "command_line_string")
# - virtual_console_widget_name: The attribute name in self.app_delegate.virtual_console
# to emit button events.
# - Gdk.KEY_*: The GDK keyval to simulate if the virtual console is not present.
# - command_line_string: A character to add directly to the command line
# (for numbers/dot).
SIMPLE_ACTION_MAPPING = {
    "at": ("at_level", Gdk.KEY_equal, None),
    "percent_plus": ("percent_plus", Gdk.KEY_exclam, None),
    "percent_minus": ("percent_minus", Gdk.KEY_colon, None),
    "time": ("time", Gdk.KEY_T, None),
    "delay": ("delay", Gdk.KEY_D, None),
    "ch": ("channel", Gdk.KEY_c, None),
    "thru": ("thru", Gdk.KEY_greater, None),
    "plus": ("plus", Gdk.KEY_plus, None),
    "minus": ("minus", Gdk.KEY_minus, None),
    "all": ("all", Gdk.KEY_a, None),
    "right": ("right", Gdk.KEY_Right, None),
    "left": ("left", Gdk.KEY_Left, None),
    "up": ("up", Gdk.KEY_Up, None),
    "down": ("down", Gdk.KEY_Down, None),
    "clear": ("clear", Gdk.KEY_BackSpace, None),
    "update": ("update", Gdk.KEY_U, None),
    "record": ("record", Gdk.KEY_R, None),
    "number_0": ("zero", None, "0"),
    "number_1": ("one", None, "1"),
    "number_2": ("two", None, "2"),
    "number_3": ("three", None, "3"),
    "number_4": ("four", None, "4"),
    "number_5": ("five", None, "5"),
    "number_6": ("six", None, "6"),
    "number_7": ("seven", None, "7"),
    "number_8": ("eight", None, "8"),
    "number_9": ("nine", None, "9"),
    "dot": ("dot", None, "."),
}


# pylint: disable=too-many-public-methods
class MidiNotes:
    """MIDI messages from controllers"""

    notes: dict[str, list[int]]
    cc_notes: dict[str, list[int]]
    zoom: bool

    def __init__(self, midi: Midi, app_delegate: Application) -> None:
        self.midi = midi
        self.app_delegate = app_delegate
        self.zoom = False
        # Default MIDI notes values : "action": Channel, Note
        self.notes = {
            "playback.go": [0, 94],
            "playback.go_back": [0, 86],
            "playback.pause": [0, 93],
            "playback.sequence_minus": [0, 91],
            "playback.sequence_plus": [0, 92],
            "output": [0, -1],
            "seq": [0, -1],
            "group": [0, -1],
            "preset": [0, -1],
            "track": [0, -1],
            "goto": [0, -1],
            "clear": [0, -1],
            "dot": [0, -1],
            "right": [0, -1],
            "left": [0, -1],
            "up": [0, -1],
            "down": [0, -1],
            "ch": [0, -1],
            "thru": [0, -1],
            "plus": [0, -1],
            "minus": [0, -1],
            "all": [0, -1],
            "at": [0, -1],
            "percent_plus": [0, -1],
            "percent_minus": [0, -1],
            "update": [0, -1],
            "record": [0, -1],
            "time": [0, -1],
            "delay": [0, -1],
            "inde_7": [0, 32],
            "inde_8": [0, 33],
            "inde_9": [0, 34],
            "page_plus": [0, 49],
            "page_minus": [0, 48],
            "zoom_on": [0, 100],
            "h_plus": [0, 99],
            "h_minus": [0, 98],
            "v_plus": [0, 97],
            "v_minus": [0, 96],
        }
        for i in range(10):
            self.notes[f"number_{i}"] = [0, -1]
        for i in range(10):
            for j in range(10):
                if j < 8:
                    self.notes[f"flash_{j + i * 10 + 1}"] = [0, 24 + j]
                elif j == 8:
                    self.notes[f"flash_{j + i * 10 + 1}"] = [0, 84]
                else:
                    self.notes[f"flash_{j + i * 10 + 1}"] = [0, -1]
                if j < 8:
                    self.notes[f"fader_{j + i * 10 + 1}"] = [0, 104 + j]
                else:
                    self.notes[f"fader_{j + i * 10 + 1}"] = [0, -1]
        self.cc_notes = {action: [0, -1] for action in self.notes}

    def reset(self) -> None:
        """Remove all MIDI note"""
        for action in self.notes:
            self.notes[action] = [0, -1]
        for action in self.cc_notes:
            self.cc_notes[action] = [0, -1]

    # pylint: disable=too-many-branches
    def _dispatch(self, key: str, msg: mido.Message) -> None:
        """Dispatch a MIDI action to its handler

        Args:
            key: Action key
            msg: (Simulated) MIDI note message
        """
        if key[:6] == "flash_":
            # We need to pass fader number to flash function
            fader_index = int(key[6:])
            page = int((fader_index - 1) / 10)
            fader = int(fader_index - (page * 10))
            if page + 1 == self.app_delegate.core.lightshow.fader_bank.active_page:
                GLib.idle_add(self.flash, msg, fader)
        elif key[:6] == "fader_":
            fader_index = int(key[6:])
            page = int((fader_index - 1) / 10)
            fader = int(fader_index - (page * 10))
            if page + 1 == self.app_delegate.core.lightshow.fader_bank.active_page:
                GLib.idle_add(self.fader, msg, fader)
        elif key[:5] == "inde_":
            GLib.idle_add(self._function_inde_button, msg, int(key[5:]))
        elif key[:4] == "zoom":
            GLib.idle_add(self._toggle_zoom, msg)
        elif key[:6] == "h_plus" or key[:6] == "v_plus":
            GLib.idle_add(self._zoom_plus, msg)
        elif key[:7] == "h_minus" or key[:7] == "v_minus":
            GLib.idle_add(self._zoom_minus, msg)
        elif key in SIMPLE_ACTION_MAPPING:
            GLib.idle_add(self._execute_midi_action, key, msg)
        else:
            method_name = key.rsplit(".", maxsplit=1)[-1]
            func = getattr(self, f"_function_{method_name}", None) or getattr(
                self, method_name, None
            )
            if func:
                GLib.idle_add(func, msg)

    def scan(self, msg: mido.Message) -> None:
        """Scan MIDI notes

        Args:
            msg: MIDI message
        """
        for key, value in list(self.notes.items()):
            if msg.channel == value[0] and msg.note == value[1]:
                self._dispatch(key, msg)

    def scan_cc(self, msg: mido.Message) -> None:
        """Scan MIDI CC for button actions

        Args:
            msg: MIDI message
        """
        for key, value in list(self.cc_notes.items()):
            if msg.channel == value[0] and msg.control == value[1]:
                note_type = "note_on" if msg.value > 0 else "note_off"
                velocity = 127 if msg.value > 0 else 0
                simulated_msg = mido.Message(
                    note_type,
                    channel=msg.channel,
                    note=0,
                    velocity=velocity,
                    time=msg.time,
                )
                self._dispatch(key, simulated_msg)

    def send(self, midi_name: str, value: int) -> None:
        """Send MIDI note or CC message

        Args:
            midi_name: action string
            value: MIDI note velocity
        """
        channel, control = self.cc_notes[midi_name]
        if control != -1:
            cc_value = 127 if value > 0 else 0
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=cc_value,
                time=0,
            )
            self.midi.enqueue(msg)
        else:
            channel, note = self.notes[midi_name]
            if note != -1:
                msg = mido.Message(
                    "note_on", channel=channel, note=note, velocity=value, time=0
                )
                self.midi.enqueue(msg)

    def learn(self, msg: mido.Message, learning: str) -> None:
        """Learn new MIDI Note control

        Args:
            msg: MIDI message
            learning: action to update
        """
        if not self.notes.get(learning):
            return
        # Find if values are already used
        for key, value in list(self.notes.items()):
            if value[0] == msg.channel and value[1] == msg.note:
                if learning.startswith("flash_"):
                    # Don't delete flash button from other pages
                    index = int(key[6:])
                    page = index // 11 + 1
                    if page == self.app_delegate.core.lightshow.fader_bank.active_page:
                        self.notes.update({key: [0, -1]})
                else:
                    # Delete it
                    self.notes.update({key: [0, -1]})
        # Learn new values
        self.notes.update({learning: [msg.channel, msg.note]})
        self.cc_notes.update({learning: [0, -1]})

    def learn_cc(self, msg: mido.Message, learning: str) -> None:
        """Learn new MIDI CC control for button action

        Args:
            msg: MIDI message
            learning: action to update
        """
        if learning not in self.cc_notes:
            return
        # Find if values are already used
        for key, value in list(self.cc_notes.items()):
            if value[0] == msg.channel and value[1] == msg.control:
                if learning.startswith("flash_"):
                    # Don't delete flash button from other pages
                    index = int(key[6:])
                    page = index // 11 + 1
                    if page == self.app_delegate.core.lightshow.fader_bank.active_page:
                        self.cc_notes.update({key: [0, -1]})
                else:
                    # Delete it
                    self.cc_notes.update({key: [0, -1]})
        # Learn new values
        self.cc_notes.update({learning: [msg.channel, msg.control]})
        self.notes.update({learning: [0, -1]})

    def led_pause_off(self) -> None:
        """Toggle MIDI Led"""
        self.send("playback.pause", 0)

    def _update_inde_button(
        self, inde: Independent | None, index: int, level: int
    ) -> None:
        """Update Independent Button level

        Args:
            inde: Independent
            index: Independent Number
            level: Level (0-255)
        """
        if inde is None:
            return
        inde.level = level
        inde.update_dmx()
        velocity = 0 if level == 0 else 127
        self.send(f"inde_{index}", velocity)

    def _function_inde_button(self, msg: mido.Message, independent: int) -> None:
        """Toggle independent button

        Args:
            msg: MIDI message
            independent: Independent number
        """
        inde = None
        widget = None
        if independent == 7:
            inde = self.app_delegate.core.lightshow.independents.independents[6]
            if self.app_delegate.virtual_console:
                widget = self.app_delegate.virtual_console.independent7
        elif independent == 8:
            inde = self.app_delegate.core.lightshow.independents.independents[7]
            if self.app_delegate.virtual_console:
                widget = self.app_delegate.virtual_console.independent8
        elif independent == 9:
            inde = self.app_delegate.core.lightshow.independents.independents[8]
            if self.app_delegate.virtual_console:
                widget = self.app_delegate.virtual_console.independent9
        if msg.type == "note_off" or (
            msg.type == "note_on" and msg.velocity == 127 and inde and inde.level == 255
        ):
            if self.app_delegate.virtual_console and widget:
                widget.set_active(False)
            else:
                self._update_inde_button(inde, independent, 0)
        elif msg.type == "note_on" and msg.velocity == 127 and inde and inde.level == 0:
            if self.app_delegate.virtual_console and widget:
                widget.set_active(True)
            else:
                self._update_inde_button(inde, independent, 255)

    def _toggle_zoom(self, msg: mido.Message) -> None:
        """Zoom On/Off

        Args:
            msg: MIDI message
        """
        if msg.velocity == 127 and self.zoom:
            self.zoom = False
        elif msg.velocity == 127 and not self.zoom:
            self.zoom = True

    def _zoom_plus(self, _msg: mido.Message) -> None:
        """Zoom plus"""
        if self.zoom and self.app_delegate.window is not None:
            zoom("in", self.app_delegate.window)

    def _zoom_minus(self, _msg: mido.Message) -> None:
        """Zoom plus"""
        if self.zoom and self.app_delegate.window is not None:
            zoom("out", self.app_delegate.window)

    def fader(self, msg: mido.Message, fader_index: int) -> None:
        """Send Fader position when released

        Args:
            msg: MIDI message
            fader_index: Fader number
        """
        if msg.velocity == 0:
            midi_name = f"fader_{fader_index}"
            fader = self.app_delegate.core.lightshow.fader_bank.get_fader(fader_index)

            self.midi.messages.control_change.send(midi_name, round(fader.level * 127))
            self.midi.messages.pitchwheel.send(
                midi_name, round(((fader.level * 16383) - 8192))
            )

    def flash(self, msg: mido.Message, fader_index: int) -> None:
        """Flash Fader

        Args:
            msg: MIDI message
            fader_index: Fader number
        """
        if msg.velocity == 0:
            self.send(f"flash_{fader_index}", 0)
            fader = self.app_delegate.core.lightshow.fader_bank.get_fader(fader_index)
            fader.flash_off()
        elif msg.velocity == 127:
            self.send(f"flash_{fader_index}", 127)
            fader = self.app_delegate.core.lightshow.fader_bank.get_fader(fader_index)
            fader.flash_on()

    def go(self, msg: mido.Message) -> None:
        """Go

        Args:
            msg: MIDI message
        """
        if msg.velocity == 127:
            self.app_delegate.core.action_registry.execute("playback.go")

    def pause(self, msg: mido.Message) -> None:
        """Pause

        Args:
            msg: MIDI message
        """
        if msg.velocity == 127:
            self.app_delegate.core.action_registry.execute("playback.pause")

    def go_back(self, msg: mido.Message) -> None:
        """Go Back

        Args:
            msg: MIDI message
        """
        if msg.velocity == 127:
            self.app_delegate.core.action_registry.execute("playback.go_back")

    def goto(self, msg: mido.Message) -> None:
        """Go to Cue

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.goto.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.goto.emit("button-press-event", event)
            else:
                self.app_delegate.core.lightshow.main_playback.goto(
                    self.app_delegate.core.commandline.get_string()
                )
                self.app_delegate.core.commandline.set_string("")

    def sequence_minus(self, msg: mido.Message) -> None:
        """Seq -

        Args:
            msg: MIDI message
        """
        if msg.velocity == 127:
            self.app_delegate.core.action_registry.execute("playback.sequence_minus")
            self.app_delegate.core.commandline.set_string("")
            self.send("playback.sequence_minus", 127)
        elif msg.velocity == 0:
            self.send("playback.sequence_minus", 0)

    def sequence_plus(self, msg: mido.Message) -> None:
        """Seq +

        Args:
            msg: MIDI message
        """
        if msg.velocity == 127:
            self.app_delegate.core.action_registry.execute("playback.sequence_plus")
            self.app_delegate.core.commandline.set_string("")
            self.send("playback.sequence_plus", 127)
        elif msg.velocity == 0:
            self.send("playback.sequence_plus", 0)

    def output(self, msg: mido.Message) -> None:
        """Output

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.output.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.output.emit(
                    "button-press-event", event
                )
            else:
                self.app_delegate.patch_outputs(None, None)

    def seq(self, msg: mido.Message) -> None:
        """Sequences

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.seq.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.seq.emit("button-press-event", event)
            else:
                self.app_delegate.sequences(None, None)

    def group(self, msg: mido.Message) -> None:
        """Groups

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.group.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.group.emit(
                    "button-press-event", event
                )
            else:
                self.app_delegate.groups_cb(None, None)

    def preset(self, msg: mido.Message) -> None:
        """Presets

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.preset.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.preset.emit(
                    "button-press-event", event
                )
            else:
                self.app_delegate.memories_cb(None, None)

    def track(self, msg: mido.Message) -> None:
        """Track channels

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.track.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.track.emit(
                    "button-press-event", event
                )
            else:
                self.app_delegate.track_channels(None, None)

    def page_plus(self, msg: mido.Message) -> None:
        """Increment Fader Page

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.fader_page_plus.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.fader_page_plus.emit(
                    "button-press-event", event
                )
            else:
                self.app_delegate.core.lightshow.fader_bank.active_page += 1
                if (
                    self.app_delegate.core.lightshow.fader_bank.active_page
                    > MAX_FADER_PAGE
                ):
                    self.app_delegate.core.lightshow.fader_bank.active_page = 1
                self.midi.update_faders()

    def page_minus(self, msg: mido.Message) -> None:
        """Decrement Fader Page

        Args:
            msg: MIDI message
        """
        if msg.velocity == 0:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.app_delegate.virtual_console.fader_page_minus.emit(
                    "button-release-event", event
                )
        elif msg.velocity == 127:
            if self.app_delegate.virtual_console:
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                self.app_delegate.virtual_console.fader_page_minus.emit(
                    "button-press-event", event
                )
            else:
                self.app_delegate.core.lightshow.fader_bank.active_page -= 1
                if self.app_delegate.core.lightshow.fader_bank.active_page < 1:
                    self.app_delegate.core.lightshow.fader_bank.active_page = (
                        MAX_FADER_PAGE
                    )
                self.midi.update_faders()

    def _execute_midi_action(self, action: str, msg: mido.Message) -> None:
        """Execute generic MIDI action for buttons and keys."""
        mapping = SIMPLE_ACTION_MAPPING.get(action)
        if not mapping:
            return

        vc_attr, keyval, string_to_add = mapping

        if msg.velocity == 0:
            vc = self.app_delegate.virtual_console
            if vc and hasattr(vc, vc_attr):
                widget = getattr(vc, vc_attr)
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                widget.emit("button-release-event", event)
        elif msg.velocity == 127:
            vc = self.app_delegate.virtual_console
            if vc and hasattr(vc, vc_attr):
                widget = getattr(vc, vc_attr)
                event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                widget.emit("button-press-event", event)
            else:
                if string_to_add is not None:
                    self.app_delegate.core.commandline.add_string(string_to_add)
                elif keyval is not None and self.app_delegate.window:
                    event = Gdk.EventKey()
                    event.keyval = keyval
                    self.app_delegate.window.on_key_press_event(None, event)
