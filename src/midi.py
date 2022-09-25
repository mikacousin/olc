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
from gi.repository import Gdk, GLib
from olc.define import App, MAX_FADER_PAGE


class MidiFader:
    """MIDI Faders"""

    def __init__(self):
        self.value = 0
        self.inverted = True

    def get_inverted(self):
        """
        Returns:
            inverted status
        """
        return self.inverted

    def set_inverted(self, inv):
        """Set inverted status

        Args:
            inv: True or False
        """
        if inv is False or inv is True:
            self.inverted = inv

    def get_value(self):
        """
        Returns:
            Fader's value
        """
        return self.value

    def set_value(self, value):
        """Set fader's value

        Args:
            value: New value
        """
        if 0 <= value < 128:
            self.value = value


class Midi:
    """MIDI messages from controllers"""

    def __init__(self):
        self.inports = []
        self.outports = []

        self.midi_learn = ""

        # Default MIDI notes values : "action": Channel, Note
        self.midi_notes = {
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
            "inde_7": [0, -1],
            "inde_8": [0, -1],
            "inde_9": [0, -1],
            "fader_page_plus": [0, 49],
            "fader_page_minus": [0, 48],
        }
        for i in range(10):
            self.midi_notes["number_" + str(i)] = [0, i]
        for i in range(1, 41):
            self.midi_notes["flash_" + str(i)] = [0, -1]
        # Default MIDI control change values : "action": Channel, CC
        self.midi_cc = {
            "wheel": [0, -1],
            "inde_1": [0, -1],
            "inde_2": [0, -1],
            "inde_3": [0, -1],
            "inde_4": [0, -1],
            "inde_5": [0, -1],
            "inde_6": [0, -1],
            "gm": [3, 108],
            "crossfade_out": [0, 8],
            "crossfade_in": [0, 9],
        }
        for i in range(1, 101):
            self.midi_cc["master_" + str(i)] = [0, -1]
        # Default MIDI pitchwheel values : "action": Channel
        self.midi_pw = {}
        for i in range(10):
            for j in range(10):
                self.midi_pw["master_" + str(j + (i * 10) + 1)] = j

        # Create xfade Faders
        self.xfade_out = MidiFader()
        self.xfade_in = MidiFader()

    def open_input(self, ports):
        """Open MIDI inputs

        Args:
            ports: MIDI ports to open
        """
        input_names = mido.get_input_names()
        for port in ports:
            if port in input_names:
                inport = mido.open_input(port)
                inport.callback = self.scan
                self.inports.append(inport)
            else:
                inport = mido.open_input()
                inport.callback = self.scan

    def open_output(self, ports):
        """Open MIDI outputs

        Args:
            ports: MIDI ports to open
        """
        output_names = mido.get_output_names()
        for port in ports:
            if port in output_names:
                outport = mido.open_output(port)
                self.outports.append(outport)
            else:
                outport = mido.open_output()

    def close_input(self):
        """Close MIDI inputs"""
        for inport in self.inports:
            inport.close()

    def close_output(self):
        """Close MIDI outputs"""
        for outport in self.outports:
            outport.close()

    def scan(self, msg):
        """Scan MIDI messages.
        Executed with mido callback, in another thread

        Args:
            msg: MIDI message
        """
        # print(msg)

        if self.midi_learn:
            self._learn(msg)
        else:
            # Find action actived
            if msg.type in ("note_on", "note_off"):
                self._scan_notes(msg)
            elif msg.type == "control_change":
                self._scan_cc(msg)
            elif msg.type == "pitchwheel":
                self._scan_pw(msg)

    def _scan_notes(self, msg):
        """Scan MIDI notes

        Args:
            msg: MIDI message
        """
        for key, value in self.midi_notes.items():
            if msg.channel == value[0] and msg.note == value[1]:
                if key[:6] == "flash_":
                    # We need to pass master number to flash function
                    GLib.idle_add(_function_flash, msg, int(key[6:]))
                elif key[:5] == "inde_":
                    GLib.idle_add(_function_inde_button, msg, int(key[5:]))
                else:
                    GLib.idle_add(globals()["_function_" + key], msg)

    def _scan_cc(self, msg):
        """Scan MIDI control changes

        Args:
            msg: MIDI message
        """
        for key, value in self.midi_cc.items():
            if msg.channel == value[0] and msg.control == value[1]:
                if key[:7] == "master_":
                    # We need to pass master number to masters function
                    GLib.idle_add(_function_master, msg, int(key[7:]))
                elif key[:5] == "inde_":
                    GLib.idle_add(_function_inde, msg, int(key[5:]))
                elif func := getattr(self, "_function_" + key, None):
                    GLib.idle_add(func, msg)

    def _scan_pw(self, msg):
        """Scan MIDI pitchwheel messages

        Args:
            msg: MIDI message
        """

        for _key, value in self.midi_pw.items():
            if msg.channel == value:
                val = ((msg.pitch + 8192) / 16383) * 255
                if App().virtual_console:
                    GLib.idle_add(App().virtual_console.masters[value].set_value, val)
                    GLib.idle_add(
                        App().virtual_console.master_moved,
                        App().virtual_console.masters[value],
                    )
                else:
                    if self.outports:
                        for outport in self.outports:
                            outport.send(msg)
                    page = App().fader_page
                    number = value + 1
                    master = None
                    for master in App().masters:
                        if master.page == page and master.number == number:
                            break
                    GLib.idle_add(master.set_level, val)
                break

    def _function_wheel(self, msg):
        """Wheel for channels level

        Args:
            msg: MIDI message
        """
        val = msg.value
        # Mackie mode
        if val > 64:
            direction = Gdk.ScrollDirection.DOWN
            step = val - 64
        elif val < 65:
            direction = Gdk.ScrollDirection.UP
            step = val
        """
        # Relative mode
        if val > 64:
            direction = Gdk.ScrollDirection.UP
            step = val - 64
        elif val < 64:
            direction = Gdk.ScrollDirection.DOWN
            step = 64 - val
        """
        if App().virtual_console:
            App().virtual_console.wheel.emit("moved", direction, step)
        else:
            sel = App().window.channels_view.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    for output in App().patch.channels[channel]:
                        out = output[0]
                        univ = output[1]
                        level = App().dmx.frame[univ][out - 1]
                        if direction == Gdk.ScrollDirection.UP:
                            App().dmx.user[channel] = min(level + step, 255)
                        elif direction == Gdk.ScrollDirection.DOWN:
                            App().dmx.user[channel] = max(level - step, 0)

    def _function_gm(self, msg):
        """Grand Master

        Args:
            msg: MIDI message
        """
        val = (msg.value / 127) * 255
        if App().virtual_console:
            App().virtual_console.scale_grand_master.set_value(val)
            App().virtual_console.grand_master_moved(
                App().virtual_console.scale_grand_master
            )
        else:
            App().dmx.grand_master = val
            App().window.grand_master.queue_draw()

    def _function_crossfade_out(self, msg):
        """Crossfade Out

        Args:
            msg: MIDI message
        """
        self._xfade(self.xfade_out, msg.value)

    def _function_crossfade_in(self, msg):
        """Crossfade Out

        Args:
            msg: MIDI message
        """
        self._xfade(self.xfade_in, msg.value)

    def _xfade(self, fader, value):
        App().crossfade.manual = True

        if fader.get_inverted():
            val = (value / 127) * 255
            fader.set_value(value)
        else:
            val = abs(((value - 127) / 127) * 255)
            fader.set_value(abs(value - 127))

        if fader == self.xfade_out:
            if App().virtual_console:
                App().virtual_console.scale_a.set_value(val)
            else:
                App().crossfade.scale_a.set_value(val)
                App().crossfade.scale_moved(App().crossfade.scale_a)
        elif fader == self.xfade_in:
            if App().virtual_console:
                App().virtual_console.scale_b.set_value(val)
            else:
                App().crossfade.scale_b.set_value(val)
                App().crossfade.scale_moved(App().crossfade.scale_b)
        if self.xfade_out.get_value() == 127 and self.xfade_in.get_value() == 127:
            if self.xfade_out.get_inverted():
                self.xfade_out.set_inverted(False)
                self.xfade_in.set_inverted(False)
            else:
                self.xfade_out.set_inverted(True)
                self.xfade_in.set_inverted(True)
            self.xfade_out.set_value(0)
            self.xfade_in.set_value(0)

    def _learn(self, msg):
        """Learn new MIDI control

        Args:
            msg: MIDI message
        """
        if self.outports:
            for outport in self.outports:
                GLib.idle_add(outport.send, msg)

        if self.midi_notes.get(self.midi_learn) and msg.type == "note_on":
            # MIDI notes:
            # Find if values are already used
            for key, value in self.midi_notes.items():
                if value[0] == msg.channel and value[1] == msg.note:
                    # Delete it
                    self.midi_notes.update({key: [0, -1]})
            # Learn new values
            self.midi_notes.update({self.midi_learn: [msg.channel, msg.note]})
        elif self.midi_cc.get(self.midi_learn) and msg.type == "control_change":
            # MIDI control change:
            # Find if values are already used
            for key, value in self.midi_cc.items():
                if value[0] == msg.channel and value[1] == msg.control:
                    # Delete it
                    self.midi_cc.update({key: [0, -1]})
            # Learn new values
            self.midi_cc.update({self.midi_learn: [msg.channel, msg.control]})


def _function_master(msg, master_index):
    """Masters

    Args:
        msg: MIDI message
        master_index: Master number
    """
    val = (msg.value / 127) * 255
    if App().virtual_console:
        App().virtual_console.masters[master_index - 1].set_value(val)
        App().virtual_console.master_moved(
            App().virtual_console.masters[master_index - 1]
        )
    else:
        page = int((master_index - 1) / 20) + 1
        number = master_index if page == 1 else int(master_index / 2)
        master = None
        for master in App().masters:
            if master.page == page and master.number == number:
                break
        master.set_level(val)


def _function_flash(msg, master_index):
    """Flash Master

    Args:
        msg: MIDI message
        master_index: Master number
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.flashes[master_index - 1].emit(
                "button-release-event", event
            )
        else:
            page = int((master_index - 1) / 20) + 1
            number = master_index if page == 1 else int(master_index / 2)
            master = None
            for master in App().masters:
                if master.page == page and master.number == number:
                    break
            master.set_level(master.old_value)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.flashes[master_index - 1].emit(
                "button-press-event", event
            )
        else:
            page = int((master_index - 1) / 20) + 1
            number = master_index if page == 1 else int(master_index / 2)
            master = None
            for master in App().masters:
                if master.page == page and master.number == number:
                    break
            master.old_value = master.value
            master.set_level(255)


def _function_inde(msg, independent):
    """Change independent knob level

    Args:
        msg: MIDI message
        independent: Independent number
    """
    if App().virtual_console:
        val = (msg.value / 127) * 255
        if independent == 1:
            App().virtual_console.independent1.value = val
            App().virtual_console.independent1.emit("changed")
            App().virtual_console.independent1.queue_draw()
        elif independent == 2:
            App().virtual_console.independent2.value = val
            App().virtual_console.independent2.emit("changed")
            App().virtual_console.independent2.queue_draw()
        elif independent == 3:
            App().virtual_console.independent3.value = val
            App().virtual_console.independent3.emit("changed")
            App().virtual_console.independent3.queue_draw()
        elif independent == 4:
            App().virtual_console.independent4.value = val
            App().virtual_console.independent4.emit("changed")
            App().virtual_console.independent4.queue_draw()
        elif independent == 5:
            App().virtual_console.independent5.value = val
            App().virtual_console.independent5.emit("changed")
            App().virtual_console.independent5.queue_draw()
        elif independent == 6:
            App().virtual_console.independent6.value = val
            App().virtual_console.independent6.emit("changed")
            App().virtual_console.independent6.queue_draw()


def _function_inde_button(msg, independent):
    """Toggle independent button

    Args:
        msg: MIDI message
        independent: Independent number
    """
    if independent == 7:
        inde = App().independents.independents[6]
    elif independent == 8:
        inde = App().independents.independents[7]
    elif independent == 9:
        inde = App().independents.independents[8]
    if msg.type == "note_off" or (
        msg.type == "note_on" and msg.velocity == 127 and inde.level == 255
    ):
        if independent == 7:
            if App().virtual_console:
                App().virtual_console.independent7.set_active(False)
            else:
                App().independents.independents[6].level = 0
                App().independents.independents[6].update_dmx()
                for outport in App().midi.outports:
                    item = App().midi.midi_notes["inde_7"]
                    if item[1] != -1:
                        msg = mido.Message(
                            "note_on", channel=item[0], note=item[1], velocity=0, time=0
                        )
                        GLib.idle_add(outport.send, msg)
        elif independent == 8:
            if App().virtual_console:
                App().virtual_console.independent8.set_active(False)
            else:
                App().independents.independents[7].level = 0
                App().independents.independents[7].update_dmx()
                for outport in App().midi.outports:
                    item = App().midi.midi_notes["inde_8"]
                    if item[1] != -1:
                        msg = mido.Message(
                            "note_on", channel=item[0], note=item[1], velocity=0, time=0
                        )
                        GLib.idle_add(outport.send, msg)
        elif independent == 9:
            if App().virtual_console:
                App().virtual_console.independent9.set_active(False)
            else:
                App().independents.independents[8].level = 0
                App().independents.independents[8].update_dmx()
                for outport in App().midi.outports:
                    item = App().midi.midi_notes["inde_9"]
                    if item[1] != -1:
                        msg = mido.Message(
                            "note_on", channel=item[0], note=item[1], velocity=0, time=0
                        )
                        GLib.idle_add(outport.send, msg)
    elif msg.type == "note_on" and msg.velocity == 127 and inde.level == 0:
        if independent == 7:
            if App().virtual_console:
                App().virtual_console.independent7.set_active(True)
            else:
                App().independents.independents[6].level = 255
                App().independents.independents[6].update_dmx()
                for outport in App().midi.outports:
                    item = App().midi.midi_notes["inde_7"]
                    if item[1] != -1:
                        msg = mido.Message(
                            "note_on",
                            channel=item[0],
                            note=item[1],
                            velocity=127,
                            time=0,
                        )
                        GLib.idle_add(outport.send, msg)
        elif independent == 8:
            if App().virtual_console:
                App().virtual_console.independent8.set_active(True)
            else:
                App().independents.independents[7].level = 255
                App().independents.independents[7].update_dmx()
                for outport in App().midi.outports:
                    item = App().midi.midi_notes["inde_8"]
                    if item[1] != -1:
                        msg = mido.Message(
                            "note_on",
                            channel=item[0],
                            note=item[1],
                            velocity=127,
                            time=0,
                        )
                        GLib.idle_add(outport.send, msg)
        elif independent == 9:
            if App().virtual_console:
                App().virtual_console.independent9.set_active(True)
            else:
                App().independents.independents[8].level = 255
                App().independents.independents[8].update_dmx()
                for outport in App().midi.outports:
                    item = App().midi.midi_notes["inde_9"]
                    if item[1] != -1:
                        msg = mido.Message(
                            "note_on",
                            channel=item[0],
                            note=item[1],
                            velocity=127,
                            time=0,
                        )
                        GLib.idle_add(outport.send, msg)


def _function_go(msg):
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


def _function_at(msg):
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


def _function_percent_plus(msg):
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


def _function_percent_minus(msg):
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


def _function_time(msg):
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


def _function_delay(msg):
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


def _function_ch(msg):
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


def _function_thru(msg):
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


def _function_plus(msg):
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


def _function_minus(msg):
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


def _function_all(msg):
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


def _function_right(msg):
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


def _function_left(msg):
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


def _function_up(msg):
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


def _function_down(msg):
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


def _function_clear(msg):
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


def _function_number_0(msg):
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


def _function_number_1(msg):
    """1

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.one.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.one.emit("button-press-event", event)
        else:
            App().window.keystring += "1"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_2(msg):
    """2

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.two.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.two.emit("button-press-event", event)
        else:
            App().window.keystring += "2"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_3(msg):
    """3

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.three.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.three.emit("button-press-event", event)
        else:
            App().window.keystring += "3"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_4(msg):
    """4

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.four.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.four.emit("button-press-event", event)
        else:
            App().window.keystring += "4"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_5(msg):
    """5

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.five.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.five.emit("button-press-event", event)
        else:
            App().window.keystring += "5"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_6(msg):
    """6

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.six.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.six.emit("button-press-event", event)
        else:
            App().window.keystring += "6"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_7(msg):
    """7

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.seven.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.seven.emit("button-press-event", event)
        else:
            App().window.keystring += "7"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_8(msg):
    """8

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.eight.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.eight.emit("button-press-event", event)
        else:
            App().window.keystring += "8"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_number_9(msg):
    """9

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.nine.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.nine.emit("button-press-event", event)
        else:
            App().window.keystring += "9"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_dot(msg):
    """Dot

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.dot.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.dot.emit("button-press-event", event)
        else:
            App().window.keystring += "."
            App().window.statusbar.push(App().window.context_id, App().window.keystring)


def _function_pause(msg):
    """Pause

    Args:
        msg: MIDI message
    """
    if msg.velocity == 0:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.pause.emit("button-release-event", event)

    elif msg.velocity == 127:
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.pause.emit("button-press-event", event)
        else:
            App().sequence.pause(App(), None)


def _function_go_back(msg):
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


def _function_goto(msg):
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


def _function_seq_minus(msg):
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


def _function_seq_plus(msg):
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


def _function_output(msg):
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


def _function_seq(msg):
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


def _function_group(msg):
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


def _function_preset(msg):
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


def _function_track(msg):
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


def _function_update(msg):
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


def _function_record(msg):
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


def _function_fader_page_plus(msg):
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
            if App().virtual_console:
                App().virtual_console.page_number.set_label(str(App().fader_page))
                for master in App().masters:
                    if master.page == App().fader_page:
                        text = "master_" + str(
                            master.number + ((App().fader_page - 1) * 10)
                        )
                        App().virtual_console.masters[master.number - 1].text = text
                        App().virtual_console.masters[master.number - 1].set_value(
                            master.value
                        )
                        App().virtual_console.flashes[
                            master.number - 1
                        ].label = master.text
                        App().virtual_console.flashes[master.number - 1].queue_draw()
            else:
                for master in App().masters:
                    if master.page == App().fader_page:
                        val = int(((master.value / 255) * 16383) - 8192)
                        msg = mido.Message(
                            "pitchwheel", channel=master.number - 1, pitch=val, time=0
                        )
                        for outport in App().midi.outports:
                            outport.send(msg)


def _function_fader_page_minus(msg):
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
            if App().virtual_console:
                App().virtual_console.page_number.set_label(str(App().fader_page))
                for master in App().masters:
                    if master.page == App().fader_page:
                        text = "master_" + str(
                            master.number + ((App().fader_page - 1) * 10)
                        )
                        App().virtual_console.masters[master.number - 1].text = text
                        App().virtual_console.masters[master.number - 1].set_value(
                            master.value
                        )
                        App().virtual_console.flashes[
                            master.number - 1
                        ].label = master.text
                        App().virtual_console.flashes[master.number - 1].queue_draw()
            else:
                for master in App().masters:
                    if master.page == App().fader_page:
                        val = int(((master.value / 255) * 16383) - 8192)
                        msg = mido.Message(
                            "pitchwheel", channel=master.number - 1, pitch=val, time=0
                        )
                        for outport in App().midi.outports:
                            outport.send(msg)
