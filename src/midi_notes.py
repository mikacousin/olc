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
from __future__ import annotations
from typing import Dict, List
import typing
import mido
from gi.repository import Gdk, GLib
from olc.define import App, MAX_FADER_PAGE

if typing.TYPE_CHECKING:
    from olc.independent import Independent
    from olc.widgets_button import ButtonWidget


class MidiNotes:
    """MIDI messages from controllers"""

    notes: Dict[str, List[int]]

    def __init__(self):

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
            "fader_page_plus": [0, 49],
            "fader_page_minus": [0, 48],
        }
        for i in range(10):
            self.notes["number_" + str(i)] = [0, -1]
        for i in range(10):
            for j in range(10):
                if j < 8:
                    self.notes["flash_" + str(j + (i * 10) + 1)] = [0, 24 + j]
                elif j == 8:
                    self.notes["flash_" + str(j + (i * 10) + 1)] = [0, 84]
                else:
                    self.notes["flash_" + str(j + (i * 10) + 1)] = [0, -1]

    def scan(self, msg: mido.Message) -> None:
        """Scan MIDI notes

        Args:
            msg: MIDI message
        """
        if not App().virtual_console:
            if App().midi.ports.outports:
                for outport in App().midi.ports.outports:
                    outport.send(msg)
        for key, value in self.notes.items():
            if msg.channel == value[0] and msg.note == value[1]:
                if key[:6] == "flash_":
                    # We need to pass fader number to flash function
                    master = int(key[6:])
                    page = int((master - 1) / 10)
                    fader = int(master - (page * 10))
                    if page + 1 == App().fader_page:
                        GLib.idle_add(_function_flash, msg, fader)
                elif key[:5] == "inde_":
                    GLib.idle_add(self._function_inde_button, msg, int(key[5:]))
                else:
                    GLib.idle_add(globals()["_function_" + key], msg)

    def learn(self, msg: mido.Message, midi_learn: str) -> None:
        """Learn new MIDI Note control

        Args:
            msg: MIDI message
            midi_learn: action to update
        """
        if self.notes.get(midi_learn):
            # Find if values are already used
            for key, value in self.notes.items():
                if value[0] == msg.channel and value[1] == msg.note:
                    if midi_learn[:6] == "flash_":
                        # Don't delete flash button from other pages
                        index = int(key[6:])
                        page = int(index / 11) + 1
                        if page == App().fader_page:
                            self.notes.update({key: [0, -1]})
                    else:
                        # Delete it
                        self.notes.update({key: [0, -1]})
            # Learn new values
            self.notes.update({midi_learn: [msg.channel, msg.note]})

    def led_pause_off(self) -> None:
        """Toggle MIDI Led"""
        item = self.notes["pause"]
        for output in App().midi.ports.outports:
            if item[1] != -1:
                msg = mido.Message(
                    "note_on", channel=item[0], note=item[1], velocity=0, time=0
                )
                output.send(msg)

    def __update_inde_button(self, inde: Independent, index: int, level: int) -> None:
        """Update Independent Button level

        Args:
            inde: Independent
            index: Independent Number
            level: Level (0-255)
        """
        inde.level = level
        inde.update_dmx()
        if level == 0:
            velocity = 0
        else:
            velocity = 127
        for outport in App().midi.ports.outports:
            item = self.notes["inde_" + str(index)]
            msg = mido.Message(
                "note_on", channel=item[0], note=item[1], velocity=velocity, time=0
            )
            GLib.idle_add(outport.send, msg)

    def _function_inde_button(self, msg: mido.Message, independent: int) -> None:
        """Toggle independent button

        Args:
            msg: MIDI message
            independent: Independent number
        """
        if independent == 7:
            inde = App().independents.independents[6]
            if App().virtual_console:
                widget = App().virtual_console.independent7
        elif independent == 8:
            inde = App().independents.independents[7]
            if App().virtual_console:
                widget = App().virtual_console.independent8
        elif independent == 9:
            inde = App().independents.independents[8]
            if App().virtual_console:
                widget = App().virtual_console.independent9
        if msg.type == "note_off" or (
            msg.type == "note_on" and msg.velocity == 127 and inde.level == 255
        ):
            if App().virtual_console:
                widget.set_active(False)
            else:
                self.__update_inde_button(inde, independent, 0)
        elif msg.type == "note_on" and msg.velocity == 127 and inde.level == 0:
            if App().virtual_console:
                widget.set_active(True)
            else:
                self.__update_inde_button(inde, independent, 255)


def _function_flash(msg: mido.Message, fader_index: int) -> None:
    """Flash Master

    Args:
        msg: MIDI message
        fader_index: Master number
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.flashes[fader_index - 1].emit(
                "button-release-event", event
            )
        else:
            master = None
            for master in App().masters:
                if master.page == App().fader_page and master.number == fader_index:
                    break
            master.set_level(master.old_value)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.flashes[fader_index - 1].emit(
                "button-press-event", event
            )
        else:
            master = None
            for master in App().masters:
                if master.page == App().fader_page and master.number == fader_index:
                    break
            master.old_value = master.value
            master.set_level(255)


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
            App().sequence.do_go(None, None)


def _function_at(msg: mido.Message) -> None:
    """At level

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.at_level.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.at_level.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_equal
            App().window.on_key_press_event(None, event)


def _function_percent_plus(msg: mido.Message) -> None:
    """% +

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.percent_plus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.percent_plus.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_exclam
            App().window.on_key_press_event(None, event)


def _function_percent_minus(msg: mido.Message) -> None:
    """% -

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.percent_minus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.percent_minus.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_colon
            App().window.on_key_press_event(None, event)


def _function_time(msg: mido.Message) -> None:
    """Time

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.time.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.time.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_T
            App().window.on_key_press_event(None, event)


def _function_delay(msg: mido.Message) -> None:
    """Delay

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.delay.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.delay.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_D
            App().window.on_key_press_event(None, event)


def _function_ch(msg: mido.Message) -> None:
    """Channel

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.channel.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.channel.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_c
            App().window.on_key_press_event(None, event)


def _function_thru(msg: mido.Message) -> None:
    """Thru

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.thru.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.thru.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_greater
            App().window.on_key_press_event(None, event)


def _function_plus(msg: mido.Message) -> None:
    """Channel +

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.plus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.plus.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_plus
            App().window.on_key_press_event(None, event)


def _function_minus(msg: mido.Message) -> None:
    """Channel -

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.minus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.minus.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_minus
            App().window.on_key_press_event(None, event)


def _function_all(msg: mido.Message) -> None:
    """All Channels

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.all.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.all.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_a
            App().window.on_key_press_event(None, event)


def _function_right(msg: mido.Message) -> None:
    """Right

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.right.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.right.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Right
            App().window.on_key_press_event(None, event)


def _function_left(msg: mido.Message) -> None:
    """Left

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.left.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.left.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Left
            App().window.on_key_press_event(None, event)


def _function_up(msg: mido.Message) -> None:
    """Up

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.up.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.up.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Up
            App().window.on_key_press_event(None, event)


def _function_down(msg: mido.Message) -> None:
    """Down

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.down.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.down.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Down
            App().window.on_key_press_event(None, event)


def _function_clear(msg: mido.Message) -> None:
    """Clear keyboard

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.clear.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.clear.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_BackSpace
            App().window.on_key_press_event(None, event)


def _function_number_0(msg: mido.Message) -> None:
    """0

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.zero.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.zero.emit("button-press-event", event)
        else:
            App().window.keystring += "0"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def do_numbers(msg: mido.Message, widget: ButtonWidget, keystring: str) -> None:
    """Action for numbers

    Args:
        msg: MIDI message
        widget: Number widget
        keystring: String to add to buffer
    """
    if msg.velocity == 0:
        if widget:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            widget.emit("button-release-event", event)
    elif msg.velocity == 127:
        if widget:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            widget.emit("button-press-event", event)
        else:
            App().window.keystring += keystring
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_1(msg: mido.Message) -> None:
    """1

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.one, "1")
    else:
        do_numbers(msg, None, "1")


def _function_number_2(msg: mido.Message) -> None:
    """2

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.two, "2")
    else:
        do_numbers(msg, None, "2")


def _function_number_3(msg: mido.Message) -> None:
    """3

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.three, "3")
    else:
        do_numbers(msg, None, "3")


def _function_number_4(msg: mido.Message) -> None:
    """4

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.four, "4")
    else:
        do_numbers(msg, None, "4")


def _function_number_5(msg: mido.Message) -> None:
    """5

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.five, "5")
    else:
        do_numbers(msg, None, "5")


def _function_number_6(msg: mido.Message) -> None:
    """6

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.six, "6")
    else:
        do_numbers(msg, None, "6")


def _function_number_7(msg: mido.Message) -> None:
    """7

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.seven, "7")
    else:
        do_numbers(msg, None, "7")


def _function_number_8(msg: mido.Message) -> None:
    """8

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.eight, "8")
    else:
        do_numbers(msg, None, "8")


def _function_number_9(msg: mido.Message) -> None:
    """9

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.nine, "9")
    else:
        do_numbers(msg, None, "9")


def _function_dot(msg: mido.Message) -> None:
    """Dot

    Args:
        msg: MIDI message
    """
    if App().virtual_console:
        do_numbers(msg, App().virtual_console.dot, ".")
    else:
        do_numbers(msg, None, ".")


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
            App().sequence.pause(None, None)

    if App().sequence.on_go:
        if App().sequence.thread and App().sequence.thread.pause.is_set():
            for output in App().midi.ports.outports:
                message = mido.Message(
                    "note_on", channel=msg.channel, note=msg.note, velocity=0, time=0
                )
                output.send(message)
        elif App().sequence.thread:
            for output in App().midi.ports.outports:
                message = mido.Message(
                    "note_on", channel=msg.channel, note=msg.note, velocity=127, time=0
                )
                output.send(message)


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
            App().sequence.go_back(App(), None)


def _function_goto(msg: mido.Message) -> None:
    """Goto Cue

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
            App().sequence.goto(App().window.keystring)
            App().window.keystring = ""
            App().window.statusbar.push(App().window.context_id, "")


def _function_seq_minus(msg: mido.Message) -> None:
    """Seq -

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.seq_minus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.seq_minus.emit("button-press-event", event)
        else:
            App().sequence.sequence_minus()
            App().window.keystring = ""
            App().window.statusbar.push(App().window.context_id, "")


def _function_seq_plus(msg: mido.Message) -> None:
    """Seq +

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.seq_plus.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.seq_plus.emit("button-press-event", event)
        else:
            App().sequence.sequence_plus()
            App().window.keystring = ""
            App().window.statusbar.push(App().window.context_id, "")


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
            App().sequences(None, None)


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


def _function_update(msg: mido.Message) -> None:
    """Update Cue

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.update.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.update.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_U
            App().window.on_key_press_event(None, event)


def _function_record(msg: mido.Message) -> None:
    """Record Cue

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.record.emit("button-release-event", event)
    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.record.emit("button-press-event", event)
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_R
            App().window.on_key_press_event(None, event)


def _function_fader_page_plus(msg: mido.Message) -> None:
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
            App().fader_page += 1
            if App().fader_page > MAX_FADER_PAGE:
                App().fader_page = 1
            for master in App().masters:
                if master.page == App().fader_page:
                    val = int(((master.value / 255) * 16383) - 8192)
                    msg = mido.Message(
                        "pitchwheel", channel=master.number - 1, pitch=val, time=0
                    )
                    for outport in App().midi.ports.outports:
                        outport.send(msg)


def _function_fader_page_minus(msg: mido.Message) -> None:
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
            App().fader_page -= 1
            if App().fader_page < 1:
                App().fader_page = MAX_FADER_PAGE
            for master in App().masters:
                if master.page == App().fader_page:
                    val = int(((master.value / 255) * 16383) - 8192)
                    msg = mido.Message(
                        "pitchwheel", channel=master.number - 1, pitch=val, time=0
                    )
                    for outport in App().midi.ports.outports:
                        outport.send(msg)
