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

from olc.core.osc import make_method
from olc.define import MAX_FADER_PAGE

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


# pylint: disable=too-few-public-methods
class OSCDelegate:
    """OSC Delegate class for the headless Core Application.

    Maps legacy OSC routes directly to unified logic Actions.
    Completely decoupled from any graphical user interface libraries.
    """

    def __init__(self, app: CoreApplication) -> None:
        self.app = app

    @make_method("/olc/command_line")
    def _commandline(self, _address: str, _args: list) -> None:
        if self.app.engine:
            self.app.engine.send_osc(
                "/olc/command_line", self.app.commandline.get_string()
            )

    def _execute_action(self, name: str) -> None:
        """Execute an action from the registry.

        Args:
            name: The action name.
        """
        self.app.action_registry.execute(name)

    @make_method("/olc/key/go")
    def _go(self, _address: str, _args: list) -> None:
        self._execute_action("playback.go")

    @make_method("/olc/key/pause")
    def _pause(self, _address: str, _args: list) -> None:
        self._execute_action("playback.pause")

    @make_method("/olc/key/goback")
    def _goback(self, _address: str, _args: list) -> None:
        self._execute_action("playback.go_back")

    @make_method("/olc/key/seq+")
    def _seq_plus(self, _address: str, _args: list) -> None:
        self._execute_action("playback.sequence_plus")

    @make_method("/olc/key/seq-")
    def _seq_minus(self, _address: str, _args: list) -> None:
        self._execute_action("playback.sequence_minus")

    @make_method("/olc/key/clear")
    def _clear(self, _address: str, _args: list) -> None:
        self.app.commandline.set_string("")

    @make_method("/olc/key/1")
    def _1(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("1")

    @make_method("/olc/key/2")
    def _2(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("2")

    @make_method("/olc/key/3")
    def _3(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("3")

    @make_method("/olc/key/4")
    def _4(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("4")

    @make_method("/olc/key/5")
    def _5(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("5")

    @make_method("/olc/key/6")
    def _6(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("6")

    @make_method("/olc/key/7")
    def _7(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("7")

    @make_method("/olc/key/8")
    def _8(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("8")

    @make_method("/olc/key/9")
    def _9(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("9")

    @make_method("/olc/key/0")
    def _0(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string("0")

    @make_method("/olc/key/.")
    def _period(self, _address: str, _args: list) -> None:
        self.app.commandline.add_string(".")

    @make_method("/olc/key/channel")
    def _channel(self, _address: str, _args: list) -> None:
        self._execute_action("channel.select_active")

    @make_method("/olc/key/all")
    def _all(self, _address: str, _args: list) -> None:
        self._execute_action("channel.select_all")

    @make_method("/olc/key/level")
    def _level(self, _address: str, _args: list) -> None:
        self._execute_action("channel.set_level_from_cmd")

    @make_method("/olc/key/full")
    def _full(self, _address: str, _args: list) -> None:
        self._execute_action("channel.set_level_full")

    @make_method("/olc/key/thru")
    def _thru(self, _address: str, _args: list) -> None:
        self._execute_action("channel.select_thru")

    @make_method("/olc/key/+")
    def _plus(self, _address: str, _args: list) -> None:
        self._execute_action("channel.select_add")

    @make_method("/olc/key/-")
    def _minus(self, _address: str, _args: list) -> None:
        self._execute_action("channel.select_remove")

    @make_method("/olc/key/+%")
    def _pluspercent(self, _address: str, _args: list) -> None:
        self._execute_action("channel.level_plus")

    @make_method("/olc/key/-%")
    def _minuspercent(self, _address: str, _args: list) -> None:
        self._execute_action("channel.level_minus")

    @make_method("/olc/fader/pageupdate")
    def _sub_launch(self, _address: str, _args: list) -> None:
        fader_bank = self.app.lightshow.fader_bank
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/fader/page", fader_bank.active_page)
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/label", fader.text
                )

    @make_method("/olc/fader/page+")
    def _fader_page_plus(self, _address: str, _args: list) -> None:
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.active_page += 1
        if fader_bank.active_page > MAX_FADER_PAGE:
            fader_bank.active_page = 1

        self.app.emit("fader.page_changed", fader_bank.active_page)

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
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.active_page -= 1
        if fader_bank.active_page < 1:
            fader_bank.active_page = MAX_FADER_PAGE

        self.app.emit("fader.page_changed", fader_bank.active_page)

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
        try:
            fader_index = int(address.split("/")[4])
            level = args[0]

            fader = self.app.lightshow.fader_bank.get_fader(fader_index)
            fader.set_level(level / 255)

            self.app.emit("fader.level_changed", fader_index, level)

            if self.app.engine is not None:
                self.app.engine.send_osc(address, level)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_level: {err}")

    @make_method("/olc/fader/1/*/flash")
    def _fader_flash(self, address: str, args: list) -> None:
        try:
            pressed = args[0]
            fader_index = int(address.split("/")[4])
            fader = self.app.lightshow.fader_bank.get_fader(fader_index)
            if pressed:
                fader.flash_on()
            else:
                fader.flash_off()

            self.app.emit("fader.flash_changed", fader_index, pressed)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_flash: {err}")

    @make_method("/olc/patch/channel")
    def _patch_channel(self, _address: str, _args: list) -> None:
        self.app.lightshow.patch_by_outputs.patch_channel(True)

    @make_method("/olc/patch/output")
    def _patch_output(self, _address: str, _args: list) -> None:
        self.app.lightshow.patch_by_outputs.select_output()

    @make_method("/olc/patch/thru")
    def _patch_thru(self, _address: str, _args: list) -> None:
        self.app.lightshow.patch_by_outputs.thru()

    @make_method("/olc/patch/+")
    def _patch_plus(self, _address: str, _args: list) -> None:
        self.app.lightshow.patch_by_outputs.add_output()

    @make_method("/olc/patch/-")
    def _patch_minus(self, _address: str, _args: list) -> None:
        self.app.lightshow.patch_by_outputs.del_output()

    @make_method(None)
    def _fallback(self, address: str, args: list) -> None:
        print(f"[OSC Delegate] Unknown message: {address} with args {args}")
