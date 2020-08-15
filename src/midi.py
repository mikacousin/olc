"""MIDI Contollers"""

import mido
from gi.repository import Gdk, GLib

from olc.define import App


class MidiFader:
    """MIDI Faders"""

    def __init__(self):
        self.value = 0
        self.inverted = True

    def get_inverted(self):
        """Return inverted status"""
        return self.inverted

    def set_inverted(self, inv):
        """Set inverted status"""
        if inv is False or inv is True:
            self.inverted = inv

    def get_value(self):
        """Return fader's value"""
        return self.value

    def set_value(self, value):
        """Set fader's value"""
        if 0 <= value < 128:
            self.value = value


class Midi:
    """MIDI messages from controllers"""

    def __init__(self):
        self.inports = []

        self.midi_learn = ""

        # Default MIDI notes values : "action": Channel, Note
        self.midi_notes = {
            "go": [0, 11],
            "go_back": [0, -1],
            "seq_minus": [0, 12],
            "seq_plus": [0, 13],
            "output": [0, -1],
            "seq": [0, -1],
            "group": [0, -1],
            "preset": [0, -1],
            "track": [0, -1],
            "goto": [0, -1],
            "number_0": [0, 0],
            "number_1": [0, 1],
            "number_2": [0, 2],
            "number_3": [0, 3],
            "number_4": [0, 4],
            "number_5": [0, 5],
            "number_6": [0, 6],
            "number_7": [0, 7],
            "number_8": [0, 8],
            "number_9": [0, 9],
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
            "flash_1": [0, -1],
            "flash_2": [0, -1],
            "flash_3": [0, -1],
            "flash_4": [0, -1],
            "flash_5": [0, -1],
            "flash_6": [0, -1],
            "flash_7": [0, -1],
            "flash_8": [0, -1],
            "flash_9": [0, -1],
            "flash_10": [0, -1],
            "flash_11": [0, -1],
            "flash_12": [0, -1],
            "flash_13": [0, -1],
            "flash_14": [0, -1],
            "flash_15": [0, -1],
            "flash_16": [0, -1],
            "flash_17": [0, -1],
            "flash_18": [0, -1],
            "flash_19": [0, -1],
            "flash_20": [0, -1],
            "flash_21": [0, -1],
            "flash_22": [0, -1],
            "flash_23": [0, -1],
            "flash_24": [0, -1],
            "flash_25": [0, -1],
            "flash_26": [0, -1],
            "flash_27": [0, -1],
            "flash_28": [0, -1],
            "flash_29": [0, -1],
            "flash_30": [0, -1],
            "flash_31": [0, -1],
            "flash_32": [0, -1],
            "flash_33": [0, -1],
            "flash_34": [0, -1],
            "flash_35": [0, -1],
            "flash_36": [0, -1],
            "flash_37": [0, -1],
            "flash_38": [0, -1],
            "flash_39": [0, -1],
            "flash_40": [0, -1],
        }
        # Default MIDI control change values : "action": Channel, CC
        self.midi_cc = {
            "gm": [3, 108],
            "master_1": [0, 1],
            "master_2": [0, 2],
            "master_3": [0, 3],
            "master_4": [0, 4],
            "master_5": [0, 5],
            "master_6": [0, 6],
            "master_7": [0, 7],
            "master_8": [0, -1],
            "master_9": [0, -1],
            "master_10": [0, -1],
            "master_11": [0, -1],
            "master_12": [0, -1],
            "master_13": [0, -1],
            "master_14": [0, -1],
            "master_15": [0, -1],
            "master_16": [0, -1],
            "master_17": [0, -1],
            "master_18": [0, -1],
            "master_19": [0, -1],
            "master_20": [0, -1],
            "master_21": [0, -1],
            "master_22": [0, -1],
            "master_23": [0, -1],
            "master_24": [0, -1],
            "master_25": [0, -1],
            "master_26": [0, -1],
            "master_27": [0, -1],
            "master_28": [0, -1],
            "master_29": [0, -1],
            "master_30": [0, -1],
            "master_31": [0, -1],
            "master_32": [0, -1],
            "master_33": [0, -1],
            "master_34": [0, -1],
            "master_35": [0, -1],
            "master_36": [0, -1],
            "master_37": [0, -1],
            "master_38": [0, -1],
            "master_39": [0, -1],
            "master_40": [0, -1],
            "crossfade_out": [0, 8],
            "crossfade_in": [0, 9],
        }

        # Create xfade Faders
        self.xfade_out = MidiFader()
        self.xfade_in = MidiFader()

    def open_input(self, ports):
        """Open MIDI inputs"""
        input_names = mido.get_input_names()
        for port in ports:
            if port in input_names:
                inport = mido.open_input(port)
                inport.callback = self.scan
                self.inports.append(inport)
            else:
                inport = mido.open_input()
                inport.callback = self.scan

    def close_input(self):
        """Close MIDI inputs"""
        for inport in self.inports:
            inport.close()

    def scan(self, msg):
        """Scan MIDI messages.
        Executed with mido callback, in another thread
        """
        # print(msg)

        if self.midi_learn:
            self._learn(msg)

        # Find action actived
        if msg.type in ("note_on", "note_off"):
            for key, value in self.midi_notes.items():
                if msg.channel == value[0] and msg.note == value[1]:
                    if key[:6] == "flash_":
                        # We need to pass master number to flash function
                        GLib.idle_add(_function_flash, msg, int(key[6:]))
                    else:
                        func = getattr(self, "_function_" + key, None)
                        if func:
                            GLib.idle_add(func, msg)
        elif msg.type == "control_change":
            for key, value in self.midi_cc.items():
                if msg.channel == value[0] and msg.control == value[1]:
                    if key[:7] == "master_":
                        # We need to pass master number to masters function
                        GLib.idle_add(_function_master, msg, int(key[7:]))
                    else:
                        func = getattr(self, "_function_" + key, None)
                        if func:
                            GLib.idle_add(func, msg)

    def _function_at(self, msg):
        """At level"""
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

    def _function_percent_plus(self, msg):
        """% +"""
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

    def _function_percent_minus(self, msg):
        """% -"""
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

    def _function_ch(self, msg):
        """Channel"""
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

    def _function_thru(self, msg):
        """Thru"""
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

    def _function_plus(self, msg):
        """Channel +"""
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

    def _function_minus(self, msg):
        """Channel -"""
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

    def _function_all(self, msg):
        """All Channels"""
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

    def _function_right(self, msg):
        """Right"""
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

    def _function_left(self, msg):
        """Left"""
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

    def _function_up(self, msg):
        """Up"""
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

    def _function_down(self, msg):
        """Down"""
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

    def _function_clear(self, msg):
        """Clear keyboard"""
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

    def _function_number_0(self, msg):
        """0"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_1(self, msg):
        """1"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_2(self, msg):
        """2"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_3(self, msg):
        """3"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_4(self, msg):
        """4"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_5(self, msg):
        """5"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_6(self, msg):
        """6"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_7(self, msg):
        """7"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_8(self, msg):
        """8"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_number_9(self, msg):
        """9"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_dot(self, msg):
        """Dot"""
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
                App().window.statusbar.push(
                    App().window.context_id, App().window.keystring
                )

    def _function_go(self, msg):
        """Go"""
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

    def _function_go_back(self, msg):
        """Go Back"""
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

    def _function_goto(self, msg):
        """Goto Cue"""
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

    def _function_seq_minus(self, msg):
        """Seq -"""
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

    def _function_seq_plus(self, msg):
        """Seq +"""
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

    def _function_output(self, msg):
        """Output"""
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

    def _function_seq(self, msg):
        """Sequences"""
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

    def _function_group(self, msg):
        """Groups"""
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

    def _function_preset(self, msg):
        """Presets"""
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

    def _function_track(self, msg):
        """Track channels"""
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

    def _function_update(self, msg):
        """Update Cue"""
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

    def _function_record(self, msg):
        """Record Cue"""
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

    def _function_gm(self, msg):
        """Grand Master"""
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
        """Crossfade Out"""
        self._xfade(self.xfade_out, msg.value)

    def _function_crossfade_in(self, msg):
        """Crossfade Out"""
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
                App().virtual_console.scale_moved(App().virtual_console.scale_a)
            else:
                App().crossfade.scale_a.set_value(val)
                App().crossfade.scale_moved(App().crossfade.scale_a)
        elif fader == self.xfade_in:
            App().virtual_console.scale_b.set_value(val)
            App().virtual_console.scale_moved(App().virtual_console.scale_b)
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
        """Learn new MIDI control"""
        if self.midi_notes.get(self.midi_learn) and msg.type == "note_on":
            # MIDI notes:
            # Find if values are alreadu used
            for key, value in self.midi_notes.items():
                if value[0] == msg.channel and value[1] == msg.note:
                    # Delete it
                    self.midi_notes.update({key: [0, -1]})
            # Learn new values
            self.midi_notes.update({self.midi_learn: [msg.channel, msg.note]})
        elif self.midi_cc.get(self.midi_learn) and msg.type == "control_change":
            # MIDI control change:
            # Find if values are alreadu used
            for key, value in self.midi_cc.items():
                if value[0] == msg.channel and value[1] == msg.control:
                    # Delete it
                    self.midi_cc.update({key: [0, -1]})
            # Learn new values
            self.midi_cc.update({self.midi_learn: [msg.channel, msg.control]})


def _function_master(msg, master_index):
    """Masters"""
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
        master.value = val
        master.level_changed()


def _function_flash(msg, master_index):
    """Flash Master"""
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
            master.value = master.old_value
            master.level_changed()

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
            master.value = 255
            master.level_changed()
