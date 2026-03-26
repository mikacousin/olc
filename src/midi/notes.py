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
from olc.define import MAX_FADER_PAGE, App
from olc.zoom import zoom

if typing.TYPE_CHECKING:
    from olc.independent import Independent


# Mapping for simple actions to avoid duplicating methods.
# Format: "action_name": ("virtual_console_widget_name",
#                         Gdk.KEY_*, "command_line_string")
# - virtual_console_widget_name: The attribute name in App().virtual_console to emit
# button events.
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


def _execute_midi_action(action: str, msg: mido.Message) -> None:
    """Execute generic MIDI action for buttons and keys."""
    mapping = SIMPLE_ACTION_MAPPING.get(action)
    if not mapping:
        return

    vc_attr, keyval, string_to_add = mapping

    if msg.velocity == 0:
        vc = App().virtual_console
        if vc and hasattr(vc, vc_attr):
            widget = getattr(vc, vc_attr)
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            widget.emit("button-release-event", event)
    elif msg.velocity == 127:
        vc = App().virtual_console
        if vc and hasattr(vc, vc_attr):
            widget = getattr(vc, vc_attr)
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            widget.emit("button-press-event", event)
        else:
            if string_to_add is not None:
                App().window.commandline.add_string(string_to_add)
            elif keyval is not None:
                event = Gdk.EventKey()
                event.keyval = keyval
                App().window.on_key_press_event(None, event)


class MidiNotes:
    """MIDI messages from controllers"""

    notes: dict[str, list[int]]
    zoom: bool

    def __init__(self) -> None:
        self.zoom = False
        # Default MIDI notes values : "action": Channel, Note
        self.notes = {
            "go": [0, 94],
            "go_back": [0, 86],
            "pause": [0, 93],
            "seq_minus": [0, 91],
            "seq_plus": [0, 92],
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

    def reset(self) -> None:
        """Remove all MIDI note"""
        for action in self.notes:
            self.notes[action] = [0, -1]

    def scan(self, msg: mido.Message) -> None:
        """Scan MIDI notes

        Args:
            msg: MIDI message
        """
        for key, value in self.notes.items():
            if msg.channel == value[0] and msg.note == value[1]:
                if key[:6] == "flash_":
                    # We need to pass fader number to flash function
                    fader_index = int(key[6:])
                    page = int((fader_index - 1) / 10)
                    fader = int(fader_index - (page * 10))
                    if page + 1 == App().lightshow.fader_bank.active_page:
                        GLib.idle_add(_function_flash, msg, fader)
                elif key[:6] == "fader_":
                    fader_index = int(key[6:])
                    page = int((fader_index - 1) / 10)
                    fader = int(fader_index - (page * 10))
                    if page + 1 == App().lightshow.fader_bank.active_page:
                        GLib.idle_add(_function_fader, msg, fader)
                elif key[:5] == "inde_":
                    GLib.idle_add(self._function_inde_button, msg, int(key[5:]))
                elif key[:4] == "zoom":
                    GLib.idle_add(self._toggle_zoom, msg)
                elif key[:6] == "h_plus" or key[:6] == "v_plus":
                    GLib.idle_add(self._zoom_plus, msg)
                elif key[:7] == "h_minus" or key[:7] == "v_minus":
                    GLib.idle_add(self._zoom_minus, msg)
                elif key in SIMPLE_ACTION_MAPPING:
                    GLib.idle_add(_execute_midi_action, key, msg)
                else:
                    GLib.idle_add(globals()[f"_function_{key}"], msg)

    def send(self, midi_name: str, value: int) -> None:
        """Send MIDI note message

        Args:
            midi_name: action string
            value: MIDI note velocity
        """
        channel, note = self.notes[midi_name]
        if note != -1:
            msg = mido.Message(
                "note_on", channel=channel, note=note, velocity=value, time=0
            )
            App().midi.enqueue(msg)

    def learn(self, msg: mido.Message, learning: str) -> None:
        """Learn new MIDI Note control

        Args:
            msg: MIDI message
            learning: action to update
        """
        if not self.notes.get(learning):
            return
            # Find if values are already used
        for key, value in self.notes.items():
            if value[0] == msg.channel and value[1] == msg.note:
                if learning.startswith("flash_"):
                    # Don't delete flash button from other pages
                    index = int(key[6:])
                    page = index // 11 + 1
                    if page == App().lightshow.fader_bank.active_page:
                        self.notes.update({key: [0, -1]})
                else:
                    # Delete it
                    self.notes.update({key: [0, -1]})
        # Learn new values
        self.notes.update({learning: [msg.channel, msg.note]})

    def led_pause_off(self) -> None:
        """Toggle MIDI Led"""
        self.send("pause", 0)

    def _update_inde_button(self, inde: Independent, index: int, level: int) -> None:
        """Update Independent Button level

        Args:
            inde: Independent
            index: Independent Number
            level: Level (0-255)
        """
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
            inde = App().lightshow.independents.independents[6]
            if App().virtual_console:
                widget = App().virtual_console.independent7
        elif independent == 8:
            inde = App().lightshow.independents.independents[7]
            if App().virtual_console:
                widget = App().virtual_console.independent8
        elif independent == 9:
            inde = App().lightshow.independents.independents[8]
            if App().virtual_console:
                widget = App().virtual_console.independent9
        if msg.type == "note_off" or (
            msg.type == "note_on" and msg.velocity == 127 and inde and inde.level == 255
        ):
            if App().virtual_console and widget:
                widget.set_active(False)
            else:
                self._update_inde_button(inde, independent, 0)
        elif msg.type == "note_on" and msg.velocity == 127 and inde and inde.level == 0:
            if App().virtual_console and widget:
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
        if self.zoom:
            zoom("in")

    def _zoom_minus(self, _msg: mido.Message) -> None:
        """Zoom plus"""
        if self.zoom:
            zoom("out")


def _function_fader(msg: mido.Message, fader_index: int) -> None:
    """Send Fader position when released

    Args:
        msg: MIDI message
        fader_index: Fader number
    """
    if msg.velocity == 0:
        midi_name = f"fader_{fader_index}"
        fader = App().lightshow.fader_bank.get_fader(fader_index)

        App().midi.messages.control_change.send(midi_name, round(fader.level * 127))
        App().midi.messages.pitchwheel.send(
            midi_name, round(((fader.level * 16383) - 8192))
        )


def _function_flash(msg: mido.Message, fader_index: int) -> None:
    """Flash Fader

    Args:
        msg: MIDI message
        fader_index: Fader number
    """
    if msg.velocity == 0:
        App().midi.enqueue(msg)
        fader = App().lightshow.fader_bank.get_fader(fader_index)
        fader.flash_off()
    elif msg.velocity == 127:
        App().midi.enqueue(msg)
        fader = App().lightshow.fader_bank.get_fader(fader_index)
        fader.flash_on()


def _function_go(msg: mido.Message) -> None:
    """Go

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        # Go released
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.go_button.emit("button-release-event", event)
    elif msg.velocity == 127:
        # Go pressed
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.go_button.emit("button-press-event", event)
        else:
            App().lightshow.main_playback.do_go(None, None)


def _function_pause(msg: mido.Message) -> None:
    """Pause

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.pause.emit("button-release-event", event)
            App().virtual_console.pause.clicked()
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.pause.emit("button-press-event", event)
        else:
            App().lightshow.main_playback.pause(None, None)

    if App().lightshow.main_playback.on_go and App().lightshow.main_playback.thread:
        if App().lightshow.main_playback.thread.pause.is_set():
            message = mido.Message(
                "note_on", channel=msg.channel, note=msg.note, velocity=0, time=0
            )
            App().midi.enqueue(message)
        else:
            message = mido.Message(
                "note_on", channel=msg.channel, note=msg.note, velocity=127, time=0
            )
            App().midi.enqueue(message)


def _function_go_back(msg: mido.Message) -> None:
    """Go Back

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.goback.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.goback.emit("button-press-event", event)
        else:
            App().lightshow.main_playback.go_back(App(), None)


def _function_goto(msg: mido.Message) -> None:
    """Go to Cue

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.goto.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.goto.emit("button-press-event", event)
        else:
            App().lightshow.main_playback.goto(App().window.commandline.get_string())
            App().window.commandline.set_string("")


def _function_seq_minus(msg: mido.Message) -> None:
    """Seq -

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.seq_minus.emit("button-release-event", event)
        else:
            App().midi.enqueue(msg)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.seq_minus.emit("button-press-event", event)
        else:
            App().midi.enqueue(msg)
            App().lightshow.main_playback.sequence_minus()
            App().window.commandline.set_string("")


def _function_seq_plus(msg: mido.Message) -> None:
    """Seq +

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.seq_plus.emit("button-release-event", event)
        else:
            App().midi.enqueue(msg)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.seq_plus.emit("button-press-event", event)
        else:
            App().midi.enqueue(msg)
            App().lightshow.main_playback.sequence_plus()
            App().window.commandline.set_string("")


def _function_output(msg: mido.Message) -> None:
    """Output

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.output.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.output.emit("button-press-event", event)
        else:
            App().patch_outputs(None, None)


def _function_seq(msg: mido.Message) -> None:
    """Sequences

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.seq.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.seq.emit("button-press-event", event)
        else:
            App().lightshow.main_playback(None, None)


def _function_group(msg: mido.Message) -> None:
    """Groups

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.group.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.group.emit("button-press-event", event)
        else:
            App().groups_cb(None, None)


def _function_preset(msg: mido.Message) -> None:
    """Presets

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.preset.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.preset.emit("button-press-event", event)
        else:
            App().memories_cb(None, None)


def _function_track(msg: mido.Message) -> None:
    """Track channels

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.track.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.track.emit("button-press-event", event)
        else:
            App().track_channels(None, None)


def _function_page_plus(msg: mido.Message) -> None:
    """Increment Fader Page

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.fader_page_plus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.fader_page_plus.emit("button-press-event", event)
        else:
            App().lightshow.fader_bank.active_page += 1
            if App().lightshow.fader_bank.active_page > MAX_FADER_PAGE:
                App().lightshow.fader_bank.active_page = 1
            App().midi.update_faders()


def _function_page_minus(msg: mido.Message) -> None:
    """Decrement Fader Page

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.fader_page_minus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.fader_page_minus.emit("button-press-event", event)
        else:
            App().lightshow.fader_bank.active_page -= 1
            if App().lightshow.fader_bank.active_page < 1:
                App().lightshow.fader_bank.active_page = MAX_FADER_PAGE
            App().midi.update_faders()
