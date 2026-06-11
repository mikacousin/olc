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

from gi.repository import Gdk, GLib
from olc.core.osc import make_method
from olc.define import MAX_FADER_PAGE
from olc.midi.fader import FaderState

if typing.TYPE_CHECKING:
    from olc.application import Application


# pylint: disable=too-few-public-methods
class GUIOSCDelegate:
    """
    OSC Delegate class for the GUI Application.
    Maps legacy OSC routes directly to window UI and playback widgets.
    Uses GLib.idle_add to ensure all GUI operations run safely on the main thread.
    """

    def __init__(self, app: Application) -> None:
        self.app = app

    @make_method("/olc/command_line")
    def _commandline(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._commandline_safe)

    def _commandline_safe(self) -> None:
        if self.app.window and self.app.window.commandline and self.app.engine:
            self.app.engine.send_osc(
                "/olc/command_line", self.app.window.commandline.get_string()
            )

    def _execute_action(self, name: str) -> None:
        """Execute an action from the registry.

        Args:
            name: The action name.
        """
        self.app.core.action_registry.execute(name)

    @make_method("/olc/key/go")
    def _go(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._execute_action, "playback.go")

    @make_method("/olc/key/pause")
    def _pause(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._execute_action, "playback.pause")

    @make_method("/olc/key/goback")
    def _goback(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._execute_action, "playback.go_back")

    @make_method("/olc/key/seq+")
    def _seq_plus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._execute_action, "playback.sequence_plus")

    @make_method("/olc/key/seq-")
    def _seq_minus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._execute_action, "playback.sequence_minus")

    @make_method("/olc/key/clear")
    def _clear(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.set_string, "")

    @make_method("/olc/key/1")
    def _1(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "1")

    @make_method("/olc/key/2")
    def _2(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "2")

    @make_method("/olc/key/3")
    def _3(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "3")

    @make_method("/olc/key/4")
    def _4(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "4")

    @make_method("/olc/key/5")
    def _5(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "5")

    @make_method("/olc/key/6")
    def _6(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "6")

    @make_method("/olc/key/7")
    def _7(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "7")

    @make_method("/olc/key/8")
    def _8(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "8")

    @make_method("/olc/key/9")
    def _9(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "9")

    @make_method("/olc/key/0")
    def _0(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, "0")

    @make_method("/olc/key/.")
    def _period(self, _address: str, _args: list) -> None:
        if self.app.window is not None:
            GLib.idle_add(self.app.window.commandline.add_string, ".")

    @make_method("/olc/key/channel")
    def _channel(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_c)

    @make_method("/olc/key/all")
    def _all(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_a)

    @make_method("/olc/key/level")
    def _level(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_equal)

    @make_method("/olc/key/full")
    def _full(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._full_safe)

    def _full_safe(self) -> None:
        if self.app.settings.get_boolean("percent") and self.app.window is not None:
            self.app.window.commandline.set_string("100")
        elif self.app.window is not None:
            self.app.window.commandline.set_string("255")
        self._trigger_key(Gdk.KEY_equal)

    @make_method("/olc/key/thru")
    def _thru(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_greater)

    @make_method("/olc/key/+")
    def _plus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_plus)

    @make_method("/olc/key/-")
    def _minus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_minus)

    @make_method("/olc/key/+%")
    def _pluspercent(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_exclam)

    @make_method("/olc/key/-%")
    def _minuspercent(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._trigger_key, Gdk.KEY_colon)

    def _trigger_key(self, keyval: int) -> None:
        """Inject a keyboard event safely into the main window."""
        if self.app.window:
            event = Gdk.EventKey()
            event.keyval = keyval
            self.app.window.on_key_press_event(None, event)

    @make_method("/olc/fader/pageupdate")
    def _sub_launch(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._pageupdate_safe)

    def _pageupdate_safe(self) -> None:
        fader_bank = self.app.core.lightshow.fader_bank
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/fader/page", fader_bank.active_page)
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/label", fader.text
                )

    @make_method("/olc/fader/page+")
    def _fader_page_plus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._fader_page_plus_safe)

    def _fader_page_plus_safe(self) -> None:
        fader_bank = self.app.core.lightshow.fader_bank
        if self.app.virtual_console is not None:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            self.app.virtual_console.fader_page_plus.emit("button-press-event", event)
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            self.app.virtual_console.fader_page_plus.emit("button-release-event", event)
        else:
            fader_bank.active_page += 1
            if fader_bank.active_page > MAX_FADER_PAGE:
                fader_bank.active_page = 1
            if self.app.midi is not None:
                self.app.midi.update_faders()
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/fader/page", fader_bank.active_page)
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/label", fader.text
                )
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/level", round(fader.level * 255)
                )

    @make_method("/olc/fader/page-")
    def _fader_page_minus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self._fader_page_minus_safe)

    def _fader_page_minus_safe(self) -> None:
        fader_bank = self.app.core.lightshow.fader_bank
        if self.app.virtual_console:
            event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
            self.app.virtual_console.fader_page_minus.emit("button-press-event", event)
            event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
            self.app.virtual_console.fader_page_minus.emit(
                "button-release-event", event
            )
        else:
            fader_bank.active_page -= 1
            if fader_bank.active_page < 1:
                fader_bank.active_page = MAX_FADER_PAGE
            if self.app.midi is not None:
                self.app.midi.update_faders()
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/fader/page", fader_bank.active_page)
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/label", fader.text
                )
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/level", round(fader.level * 255)
                )

    @make_method("/olc/fader/1/*/level")
    def _fader_level(self, address: str, args: list) -> None:
        GLib.idle_add(self._fader_level_safe, address, args)

    def _fader_level_safe(self, address: str, args: list) -> None:
        try:
            fader_index = int(address.split("/")[4])
            level = args[0]
            if self.app.virtual_console:
                self.app.virtual_console.faders[fader_index - 1].set_value(level)
                self.app.virtual_console.fader_moved(
                    self.app.virtual_console.faders[fader_index - 1]
                )
            else:
                fader = self.app.core.lightshow.fader_bank.get_fader(fader_index)
                fader.set_level(level / 255)
                if self.app.midi is not None:
                    midi_fader = self.app.midi.faders.faders[fader_index - 1]
                    midi_value = midi_fader.value
                    if level > midi_value:
                        midi_fader.valid = FaderState.UP
                    elif level < midi_value:
                        midi_fader.valid = FaderState.DOWN
                    else:
                        midi_fader.valid = FaderState.VALID
            if self.app.engine is not None:
                self.app.engine.send_osc(address, level)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_level: {err}")

    @make_method("/olc/fader/1/*/flash")
    def _fader_flash(self, address: str, args: list) -> None:
        GLib.idle_add(self._fader_flash_safe, address, args)

    def _fader_flash_safe(self, address: str, args: list) -> None:
        try:
            pressed = args[0]
            fader_index = int(address.split("/")[4])
            fader = self.app.core.lightshow.fader_bank.get_fader(fader_index)
            if pressed:
                fader.flash_on()
            else:
                fader.flash_off()
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_flash: {err}")

    @make_method("/olc/patch/channel")
    def _patch_channel(self, _address: str, _args: list) -> None:
        GLib.idle_add(self.app.patch_by_outputs.patch_channel, True)

    @make_method("/olc/patch/output")
    def _patch_output(self, _address: str, _args: list) -> None:
        GLib.idle_add(self.app.patch_by_outputs.select_output)

    @make_method("/olc/patch/thru")
    def _patch_thru(self, _address: str, _args: list) -> None:
        GLib.idle_add(self.app.patch_by_outputs.thru)

    @make_method("/olc/patch/+")
    def _patch_plus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self.app.patch_by_outputs.add_output)

    @make_method("/olc/patch/-")
    def _patch_minus(self, _address: str, _args: list) -> None:
        GLib.idle_add(self.app.patch_by_outputs.del_output)

    @make_method(None)
    def _fallback(self, address: str, args: list) -> None:
        print(f"[OSC Delegate] Unknown message: {address} with args {args}")
