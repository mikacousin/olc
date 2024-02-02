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
from typing import Optional, Tuple

import liblo
from gi.repository import Gdk, GLib
from olc.define import MAX_FADER_PAGE, UNIVERSES, App
from olc.midi.fader import FaderState


class Osc:
    """OSC"""

    def __init__(self):
        self.client = OscClient()
        self.server = OscServer()

    def restart_server(self) -> None:
        """Restart OSC server"""
        self.server.free()
        self.server = OscServer()

    def stop(self) -> None:
        """Stop OSC"""
        self.client = None
        self.server.free()
        self.server = None


class OscClient:
    """OSC client"""

    def __init__(self):
        # Port to send data to the client
        self.port = App().settings.get_int("osc-client-port")
        # client's IP address
        self.host = App().settings.get_string("osc-host")

        try:
            self.target = liblo.Address(self.host, self.port)
        except liblo.AddressError as err:
            print(err)

    def target_changed(self, host: str = "", port: Optional[int] = None) -> None:
        """Client IP address or port have changed

        Args:
            host: IP address
            port: Port number
        """
        if host:
            self.host = host
        if port:
            self.port = port
        try:
            self.target = liblo.Address(self.host, self.port)
        except liblo.AddressError as err:
            print(err)

    def send(self, path, *args):
        """Send OSC message to the client

        Args:
            path: Gtk Path
            args: Arguments
        """
        liblo.send(self.target, path, *args)


class OscServer(liblo.ServerThread):
    """OSC server"""

    def __init__(self):
        # Port to listen data from the client
        self.serv_port = App().settings.get_int("osc-server-port")
        # Create Thread server
        super().__init__(self.serv_port)
        # Launch server
        self.start()

    @liblo.make_method("/olc/command_line", None)
    def _commandline(self, _path, _args, _types):
        App().osc.client.send("/olc/command_line",
                              ("s", App().window.commandline.get_string()))

    @liblo.make_method("/olc/key/go", None)
    def _go(self, _path, _args, _types):
        GLib.idle_add(App().lightshow.main_playback.do_go, None, None)

    @liblo.make_method("/olc/key/pause", None)
    def _pause(self, _path, _args, _types):
        GLib.idle_add(App().lightshow.main_playback.pause, None, None)

    @liblo.make_method("/olc/key/goback", None)
    def _goback(self, _path, _args, _types):
        GLib.idle_add(App().lightshow.main_playback.go_back, None, None)

    @liblo.make_method("/olc/key/seq+", None)
    def _seq_plus(self, _path, _args, _types):
        GLib.idle_add(App().lightshow.main_playback.sequence_plus)

    @liblo.make_method("/olc/key/seq-", None)
    def _seq_minus(self, _path, _args, _types):
        GLib.idle_add(App().lightshow.main_playback.sequence_minus)

    @liblo.make_method("/olc/key/clear", None)
    def _clear(self, _path, _args, _types):
        App().window.commandline.set_string("")

    @liblo.make_method("/olc/key/1", None)
    def _1(self, _path, _args, _types):
        App().window.commandline.add_string("1")

    @liblo.make_method("/olc/key/2", None)
    def _2(self, _path, _args, _types):
        App().window.commandline.add_string("2")

    @liblo.make_method("/olc/key/3", None)
    def _3(self, _path, _args, _types):
        App().window.commandline.add_string("3")

    @liblo.make_method("/olc/key/4", None)
    def _4(self, _path, _args, _types):
        App().window.commandline.add_string("4")

    @liblo.make_method("/olc/key/5", None)
    def _5(self, _path, _args, _types):
        App().window.commandline.add_string("5")

    @liblo.make_method("/olc/key/6", None)
    def _6(self, _path, _args, _types):
        App().window.commandline.add_string("6")

    @liblo.make_method("/olc/key/7", None)
    def _7(self, _path, _args, _types):
        App().window.commandline.add_string("7")

    @liblo.make_method("/olc/key/8", None)
    def _8(self, _path, _args, _types):
        App().window.commandline.add_string("8")

    @liblo.make_method("/olc/key/9", None)
    def _9(self, _path, _args, _types):
        App().window.commandline.add_string("9")

    @liblo.make_method("/olc/key/0", None)
    def _0(self, _path, _args, _types):
        App().window.commandline.add_string("0")

    @liblo.make_method("/olc/key/.", None)
    def _period(self, _path, _args, _types):
        App().window.commandline.add_string(".")

    @liblo.make_method("/olc/key/channel", None)
    def _channel(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_c
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/all", None)
    def _all(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_a
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/level", None)
    def _level(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_equal
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/full", None)
    def _full(self, _path, _args, _types):
        if App().settings.get_boolean("percent"):
            App().window.commandline.set_string("100")
        else:
            App().window.commandline.set_string("255")
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_equal
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/thru", None)
    def _thru(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_greater
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/+", None)
    def _plus(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_plus
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/-", None)
    def _minus(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_minus
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/+%", None)
    def _pluspercent(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_exclam
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/key/-%", None)
    def _minuspercent(self, _path, _args, _types):
        event = Gdk.EventKey()
        event.keyval = Gdk.KEY_colon
        App().window.on_key_press_event(None, event)

    @liblo.make_method("/olc/fader/pageupdate", None)
    def _sub_launch(self, _path, _args, _types):
        App().osc.client.send("/olc/fader/page", ("i", App().fader_page))
        for fader in App().lightshow.faders:
            if fader.page == App().fader_page:
                App().osc.client.send(f"/olc/fader/1/{fader.number}/label",
                                      ("s", fader.text))

    @liblo.make_method("/olc/fader/page+", None)
    def _fader_page_plus(self, _path, _args, _types):
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.fader_page_plus.emit("button-press-event", event)
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.fader_page_plus.emit("button-release-event", event)
        else:
            App().fader_page += 1
            if App().fader_page > MAX_FADER_PAGE:
                App().fader_page = 1
            App().midi.update_masters()
        App().osc.client.send("/olc/fader/page", ("i", App().fader_page))
        for fader in App().lightshow.faders:
            if fader.page == App().fader_page:
                App().osc.client.send(f"/olc/fader/1/{fader.number}/label",
                                      ("s", fader.text))

    @liblo.make_method("/olc/fader/page-", None)
    def _fader_page_minus(self, _path, _args, _types):
        if App().virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            App().virtual_console.fader_page_minus.emit("button-press-event", event)
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            App().virtual_console.fader_page_minus.emit("button-release-event", event)
        else:
            App().fader_page -= 1
            if App().fader_page < 1:
                App().fader_page = MAX_FADER_PAGE
            App().midi.update_masters()
        App().osc.client.send("/olc/fader/page", ("i", App().fader_page))
        for fader in App().lightshow.faders:
            if fader.page == App().fader_page:
                App().osc.client.send(f"/olc/fader/1/{fader.number}/label",
                                      ("s", fader.text))

    @liblo.make_method("/olc/fader/1/1/level", "i")
    @liblo.make_method("/olc/fader/1/2/level", "i")
    @liblo.make_method("/olc/fader/1/3/level", "i")
    @liblo.make_method("/olc/fader/1/4/level", "i")
    @liblo.make_method("/olc/fader/1/5/level", "i")
    @liblo.make_method("/olc/fader/1/6/level", "i")
    @liblo.make_method("/olc/fader/1/7/level", "i")
    @liblo.make_method("/olc/fader/1/8/level", "i")
    @liblo.make_method("/olc/fader/1/9/level", "i")
    @liblo.make_method("/olc/fader/1/10/level", "i")
    def _fader_level(self, path, args, _types):
        fader_index = int(path.split("/")[4])
        level = args[0]
        if App().virtual_console:
            GLib.idle_add(App().virtual_console.masters[fader_index - 1].set_value,
                          level)
            GLib.idle_add(
                App().virtual_console.master_moved,
                App().virtual_console.masters[fader_index - 1],
            )
        else:
            fader = None
            for fader in App().lightshow.faders:
                if fader.page == App().fader_page and fader.number == fader_index:
                    break
            fader.set_level(level)
            midi_fader = App().midi.faders.faders[fader_index - 1]
            midi_value = midi_fader.value
            if level > midi_value:
                midi_fader.valid = FaderState.UP
            elif level < midi_value:
                midi_fader.valid = FaderState.DOWN
            else:
                midi_fader.valid = FaderState.VALID
        App().osc.client.send(path, ("i", level))

    @liblo.make_method("/olc/fader/1/1/flash", "i")
    @liblo.make_method("/olc/fader/1/2/flash", "i")
    @liblo.make_method("/olc/fader/1/3/flash", "i")
    @liblo.make_method("/olc/fader/1/4/flash", "i")
    @liblo.make_method("/olc/fader/1/5/flash", "i")
    @liblo.make_method("/olc/fader/1/6/flash", "i")
    @liblo.make_method("/olc/fader/1/7/flash", "i")
    @liblo.make_method("/olc/fader/1/8/flash", "i")
    @liblo.make_method("/olc/fader/1/9/flash", "i")
    @liblo.make_method("/olc/fader/1/10/flash", "i")
    def _fader_flash(self, path, args, _types):
        pressed = args[0]
        fader_index = int(path.split("/")[4])
        fader = None
        for fader in App().lightshow.faders:
            if fader.page == App().fader_page and fader.number == fader_index:
                break
        if pressed:
            fader.flash_on()
        else:
            fader.flash_off()

    @liblo.make_method("/olc/patch/channel", None)
    def _patch_channel(self, _path, _args, _types):
        App().lightshow.patch.by_outputs.patch_channel(True)

    @liblo.make_method("/olc/patch/output", None)
    def _patch_output(self, _path, _args, _types):
        App().lightshow.patch.by_outputs.select_output()

    @liblo.make_method("/olc/patch/thru", None)
    def _patch_thru(self, _path, _args, _types):
        App().lightshow.patch.by_outputs.thru()

    @liblo.make_method("/olc/patch/+", None)
    def _patch_plus(self, _path, _args, _types):
        App().lightshow.patch.by_outputs.add_output()

    @liblo.make_method("/olc/patch/-", None)
    def _patch_minus(self, _path, _args, _types):
        App().lightshow.patch.by_outputs.del_output()

    @liblo.make_method(None, None)
    def _fallback(self, path, args, types, src):
        print(f"Got unknown message '{path}' from '{src.url}'")
        for a, t in zip(args, types):
            print(f"received argument {a} of type {t}")

    def _string_to_output(self) -> Tuple[Optional[int], Optional[int]]:
        output = None
        universe = None
        keystring = App().window.commandline.get_string()
        if not keystring:
            keystring = "0"
        if "." in keystring:
            if keystring.index("."):
                split = keystring.split(".")
                output = int(split[0])
                if 0 < output <= 512:
                    universe = int(split[1])
        else:
            output = int(keystring)
            universe = UNIVERSES[0]
        return (output, universe)
