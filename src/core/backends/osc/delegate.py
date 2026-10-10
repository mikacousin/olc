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

import re
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
        self.app.subscribe("fader.page_changed", self._on_fader_page_changed)
        self.app.subscribe("fader.level_changed", self._on_fader_level_changed)
        self.app.subscribe("fader.changed", self._on_fader_changed)
        self.app.subscribe("commandline.changed", self._on_commandline_changed)
        self.app.subscribe(
            "patch.selected_outputs_changed", self._on_selected_outputs_changed
        )

    def _on_fader_page_changed(self, page: int) -> None:
        """Send OSC feedback when the active fader page changes."""
        if self.app.engine is not None:
            fader_bank = self.app.lightshow.fader_bank
            self.app.engine.send_osc("/olc/fader/page", page)
            for fader in fader_bank.faders[page].values():
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/label", fader.text
                )
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/level", round(fader.level * 255)
                )

    def _on_fader_level_changed(self, fader_index: int, level: float) -> None:
        """Send OSC feedback when a fader level changes."""
        if self.app.engine is not None:
            self.app.engine.send_osc(
                f"/olc/fader/1/{fader_index}/level", round(level * 255)
            )

    def _on_fader_changed(self, page: int, index: int) -> None:
        """Send OSC feedback when a fader label or assignment changes."""
        if self.app.engine is not None:
            fader_bank = self.app.lightshow.fader_bank
            if page == fader_bank.active_page:
                fader = fader_bank.faders[page][index]
                self.app.engine.send_osc(f"/olc/fader/1/{index}/label", fader.text)
                self.app.engine.send_osc(
                    f"/olc/fader/1/{index}/level", round(fader.level * 255)
                )

    def _on_commandline_changed(self, keystring: str) -> None:
        """Send OSC feedback when the logical command line changes."""
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/command_line", keystring)

    def _on_selected_outputs_changed(self) -> None:
        """Send OSC feedback when selected DMX outputs change."""
        if self.app.engine is not None:
            patch_by_outputs = self.app.lightshow.patch_by_outputs
            self.app.engine.send_osc(
                "/olc/patch/selected_outputs", patch_by_outputs.get_selected()
            )

    @make_method("/olc/command_line")
    def _commandline(self, _address: str, _args: list) -> None:
        if self.app.engine:
            self.app.engine.send_osc(
                "/olc/command_line", self.app.commandline.get_string()
            )

    @make_method("/olc/cmd")
    def _cmd(self, _address: str, args: list) -> None:
        """Execute a full command line string received via OSC.

        Strips any optional trailing ENTER keyword and triggers execution.
        Sends execution status feedback back on /olc/cmd/status if engine is running.

        Args:
            _address: The OSC address pattern (/olc/cmd).
            args: OSC arguments, expecting the command string as args[0].
        """
        if not args or not isinstance(args[0], str):
            return

        raw_cmd = args[0].strip()
        if not raw_cmd:
            return

        clean_cmd = re.sub(r"(?i)\s+ENTER$", "", raw_cmd).strip()
        self._execute_action("commandline.set", clean_cmd)
        result = self._execute_action("commandline.execute")

        if self.app.engine is not None and hasattr(result, "success"):
            status_msg = (
                "OK" if result.success else str(getattr(result, "message", "Error"))
            )
            self.app.engine.send_osc("/olc/cmd/status", status_msg)

    def _execute_action(self, name: str, *args: object) -> object:
        """Execute an action from the registry.

        Args:
            name: The action name.
            *args: Arguments for the action.

        Returns:
            The return value of the action.
        """
        return self.app.action_registry.execute(name, *args)

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
        self._execute_action("commandline.clear")

    @make_method("/olc/key/1")
    def _1(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "1")

    @make_method("/olc/key/2")
    def _2(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "2")

    @make_method("/olc/key/3")
    def _3(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "3")

    @make_method("/olc/key/4")
    def _4(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "4")

    @make_method("/olc/key/5")
    def _5(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "5")

    @make_method("/olc/key/6")
    def _6(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "6")

    @make_method("/olc/key/7")
    def _7(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "7")

    @make_method("/olc/key/8")
    def _8(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "8")

    @make_method("/olc/key/9")
    def _9(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "9")

    @make_method("/olc/key/0")
    def _0(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", "0")

    @make_method("/olc/key/.")
    def _period(self, _address: str, _args: list) -> None:
        self._execute_action("commandline.append_char", ".")

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
        target_page = fader_bank.active_page + 1
        if self.app is not None and hasattr(self.app, "action_registry"):
            self.app.action_registry.execute("fader.set_page", target_page)
        else:
            if target_page > MAX_FADER_PAGE:
                target_page = 1
            fader_bank.active_page = target_page
            self.app.emit("fader.page_changed", target_page)

    @make_method("/olc/fader/page-")
    def _fader_page_minus(self, _address: str, _args: list) -> None:
        fader_bank = self.app.lightshow.fader_bank
        target_page = fader_bank.active_page - 1
        if self.app is not None and hasattr(self.app, "action_registry"):
            self.app.action_registry.execute("fader.set_page", target_page)
        else:
            if target_page < 1:
                target_page = MAX_FADER_PAGE
            fader_bank.active_page = target_page
            self.app.emit("fader.page_changed", target_page)

    @make_method("/olc/fader/1/*/level")
    def _fader_level(self, address: str, args: list) -> None:
        try:
            fader_index = int(address.split("/")[4])
            level = args[0]

            fader_bank = self.app.lightshow.fader_bank
            if self.app is not None and hasattr(self.app, "action_registry"):
                self.app.action_registry.execute(
                    "fader.set_level", fader_bank.active_page, fader_index, level / 255
                )
            else:
                fader = fader_bank.get_fader(fader_index)
                fader.set_level(level / 255)
                self.app.emit("fader.level_changed", fader_index, level / 255)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_level: {err}")

    @make_method("/olc/fader/1/*/flash")
    def _fader_flash(self, address: str, args: list) -> None:
        try:
            pressed = bool(args[0])
            fader_index = int(address.split("/")[4])
            fader_bank = self.app.lightshow.fader_bank
            if self.app is not None and hasattr(self.app, "action_registry"):
                self.app.action_registry.execute(
                    "fader.flash", fader_bank.active_page, fader_index, pressed
                )
            else:
                fader = fader_bank.get_fader(fader_index)
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
