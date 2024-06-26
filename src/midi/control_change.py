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
from typing import Any, Dict, List, Tuple

import mido
from gi.repository import Gdk, GLib
from olc.define import App


class MidiControlChanges:
    """MIDI control change messages from controllers"""

    control_change: Dict[str, List[int]]

    def __init__(self):
        # Default MIDI control change values : "action": Channel, CC
        self.control_change = {
            "wheel": [0, 60],
            "inde_1": [0, 16],
            "inde_2": [0, 17],
            "inde_3": [0, 18],
            "inde_4": [0, 19],
            "inde_5": [0, 20],
            "inde_6": [0, 21],
            "inde_led_1": [0, 48],
            "inde_led_2": [0, 49],
            "inde_led_3": [0, 50],
            "inde_led_4": [0, 51],
            "inde_led_5": [0, 52],
            "inde_led_6": [0, 53],
            "crossfade_out": [0, 8],
            "crossfade_in": [0, 9],
        }
        for i in range(1, 101):
            self.control_change[f"fader_{i}"] = [0, -1]

    def reset(self) -> None:
        """Remove all MIDI control change"""
        for action in self.control_change:
            self.control_change[action] = [0, -1]

    def scan(self, port: str, msg: mido.Message) -> None:
        """Scan MIDI control changes

        Args:
            port: MIDI port name
            msg: MIDI message
        """
        for key, value in self.control_change.items():
            if msg.channel == value[0] and msg.control == value[1]:
                if key[:6] == "fader_":
                    # We need to pass fader number to faders function
                    GLib.idle_add(_function_fader, msg, int(key[6:]))
                elif key[:5] == "inde_":
                    GLib.idle_add(_function_inde, port, msg, int(key[5:]))
                elif key[:13] == "crossfade_out":
                    GLib.idle_add(App().midi.xfade.moved, msg,
                                  App().midi.xfade.fader_out)
                elif key[:12] == "crossfade_in":
                    GLib.idle_add(App().midi.xfade.moved, msg,
                                  App().midi.xfade.fader_in)
                elif func := getattr(self, f"_function_{key}", None):
                    GLib.idle_add(func, port, msg)

    def send(self, midi_name: str, value: int) -> None:
        """Send MIDI control change message

        Args:
            midi_name: action string
            value: value to send
        """
        channel, control = self.control_change[midi_name]
        if control != -1:
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=value,
                time=0,
            )
            App().midi.enqueue(msg)

    def learn(self, msg: mido.Message, learning: str) -> None:
        """Learn new MIDI Control Change control

        Args:
            msg: MIDI message
            learning: action to update
        """
        if self.control_change.get(learning):
            # Find if values are already used
            for key, value in self.control_change.items():
                if value[0] == msg.channel and value[1] == msg.control:
                    # Delete it
                    self.control_change.update({key: [0, -1]})
                # Learn new values
                self.control_change.update({learning: [msg.channel, msg.control]})

    def __get_step(self, msg: mido.Message,
                   port: str) -> Tuple[int, Gdk.ScrollDirection]:
        """Return direction and step value

        Args:
            msg: MIDI message
            port: MIDI port name

        Returns:
            step: Step value
            direction: Up or Down
        """
        relative1 = App().settings.get_strv("relative1")
        relative2 = App().settings.get_strv("relative2")
        makies = App().settings.get_strv("makie")
        absolutes = App().settings.get_strv("absolute")
        if port in relative1:
            if msg.value > 64:
                direction = Gdk.ScrollDirection.DOWN
                step = -(msg.value - 128)
            elif msg.value < 65:
                direction = Gdk.ScrollDirection.UP
                step = msg.value
        elif port in relative2:
            if msg.value > 64:
                direction = Gdk.ScrollDirection.UP
                step = msg.value - 64
            elif msg.value < 64:
                direction = Gdk.ScrollDirection.DOWN
                step = 64 - msg.value
        elif port in makies:
            if msg.value > 64:
                direction = Gdk.ScrollDirection.DOWN
                step = msg.value - 64
            elif msg.value < 65:
                direction = Gdk.ScrollDirection.UP
                step = msg.value
        elif port in absolutes:
            # Can't use absolute mode for wheel
            direction = Gdk.ScrollDirection.UP
            step = 0
        return step, direction

    def _function_wheel(self, port: str, msg: mido.Message) -> None:
        """Wheel for channels level

        Args:
            port: MIDI port name
            msg: MIDI message
        """
        step, direction = self.__get_step(msg, port)
        if App().virtual_console:
            App().virtual_console.wheel.emit("moved", direction, step)
        else:
            tab = App().window.get_active_tab()
            channels_view = None
            if tab == App().window.live_view.channels_view:
                channels_view = tab
            elif tab in (
                    App().tabs.tabs["groups"],
                    App().tabs.tabs["indes"],
                    App().tabs.tabs["faders"],
                    App().tabs.tabs["memories"],
                    App().tabs.tabs["sequences"],
            ):
                channels_view = tab.channels_view
            if channels_view:
                channels_view.wheel_level(step, direction)


def _function_fader(msg: mido.Message, fader_index: int) -> None:
    """Faders

    Args:
        msg: MIDI message
        fader_index: Fader number
    """
    val = msg.value / 127
    midi_fader = App().midi.faders.faders[fader_index - 1]
    fader = App().lightshow.fader_bank.get_fader(fader_index)
    if not midi_fader.is_valid(val, fader.value):
        return
    if App().virtual_console:
        App().virtual_console.faders[fader_index - 1].set_value(val * 255)
        App().virtual_console.fader_moved(App().virtual_console.faders[fader_index - 1])
    else:
        GLib.idle_add(fader.set_level, val)


def _function_inde(port: str, msg: mido.Message, independent: int):
    """Change independent knob level

    Args:
        port: MIDI port name
        msg: MIDI message
        independent: Independent number
    """
    relative1 = App().settings.get_strv("relative1")
    relative2 = App().settings.get_strv("relative2")
    makies = App().settings.get_strv("makie")
    absolutes = App().settings.get_strv("absolute")
    if port in relative1:
        # Relative1 mode (value: 1-64 positive, 127-65 negative)
        if msg.value > 64:
            step = msg.value - 128
        elif msg.value < 65:
            step = msg.value
        inde, val = _new_inde_value(independent, step)
        _update_inde(independent, inde, val)
    elif port in relative2:
        # Relative2 mode (value: 65-127 positive, 63-0 negative)
        step = msg.value - 64 if msg.value > 64 else -(64 - msg.value)
        inde, val = _new_inde_value(independent, step)
        _update_inde(independent, inde, val)
    elif port in makies:
        # Mackie mode (value: 0-64 positive, 65-127 negative)
        if msg.value > 64:
            step = -(msg.value - 64)
        elif msg.value < 65:
            step = msg.value
        inde, val = _new_inde_value(independent, step)
        _update_inde(independent, inde, val)
    elif port in absolutes:
        # Absolute mode (value: 0-127)
        inde, _ = _new_inde_value(independent, 0)
        val = round((msg.value / 127) * 255)
        fader = App().midi.faders.inde_faders[independent - 1]
        if not fader.is_valid(val, inde.level):
            return
        _update_inde(independent, inde, val)


def _new_inde_value(independent: int, step: int) -> Tuple[Any, int]:
    inde = None
    for inde in App().lightshow.independents.independents:
        if inde.number == independent:
            val = inde.level + step
            if val < 0:
                val = 0
            elif val > 255:
                val = 255
            break
    return inde, val


def _update_inde(independent: int, inde, val: int) -> None:
    if App().virtual_console:
        if independent == 1:
            widget = App().virtual_console.independent1
        elif independent == 2:
            widget = App().virtual_console.independent2
        elif independent == 3:
            widget = App().virtual_console.independent3
        elif independent == 4:
            widget = App().virtual_console.independent4
        elif independent == 5:
            widget = App().virtual_console.independent5
        elif independent == 6:
            widget = App().virtual_console.independent6
        widget.value = val
        widget.emit("changed")
        widget.queue_draw()
    else:
        inde.set_level(val)
