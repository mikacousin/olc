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

from olc.controllers.osc.transport import make_method


class KeypadRoutesMixin:
    """OSC routes for virtual console keypad keys."""

    if typing.TYPE_CHECKING:

        def _execute_action(
            self, name: str, *args: object, **kwargs: object
        ) -> object: ...
        def _is_momentary_press(self, args: list) -> bool: ...

    @make_method("/olc/key/clear")
    def _clear(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.clear")

    @make_method("/olc/key/1")
    def _1(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "1")

    @make_method("/olc/key/2")
    def _2(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "2")

    @make_method("/olc/key/3")
    def _3(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "3")

    @make_method("/olc/key/4")
    def _4(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "4")

    @make_method("/olc/key/5")
    def _5(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "5")

    @make_method("/olc/key/6")
    def _6(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "6")

    @make_method("/olc/key/7")
    def _7(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "7")

    @make_method("/olc/key/8")
    def _8(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "8")

    @make_method("/olc/key/9")
    def _9(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "9")

    @make_method("/olc/key/0")
    def _0(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "0")

    @make_method("/olc/key/.")
    def _period(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", ".")

    @make_method("/olc/key/channel")
    def _channel(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "CHANNEL ")

    @make_method("/olc/key/all")
    def _all(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "ALL")

    @make_method("/olc/key/at")
    @make_method("/olc/key/level")
    def _level(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " AT ")

    @make_method("/olc/key/full")
    def _full(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " AT FULL")

    @make_method("/olc/key/thru")
    def _thru(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " THRU ")

    @make_method("/olc/key/+")
    def _plus(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " + ")

    @make_method("/olc/key/-")
    def _minus(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " - ")

    @make_method("/olc/key/+%")
    def _pluspercent(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " AT + 10")

    @make_method("/olc/key/-%")
    def _minuspercent(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " AT - 10")

    @make_method("/olc/key/out")
    def _out(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " AT OUT")

    @make_method("/olc/key/cue")
    def _cue_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "CUE ")

    @make_method("/olc/key/record")
    def _record_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "RECORD CUE ")

    @make_method("/olc/key/update")
    def _update_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "UPDATE CUE ")

    @make_method("/olc/key/delete")
    def _delete_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "DELETE ")

    @make_method("/olc/key/time")
    def _time_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " TIME ")

    @make_method("/olc/key/delay")
    def _delay_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " DELAY ")

    @make_method("/olc/key/group")
    def _group_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "GROUP ")

    @make_method("/olc/key/sneak")
    def _sneak_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " SNEAK ")

    @make_method("/olc/key/check")
    def _check_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " CHECK ")

    @make_method("/olc/key/enter")
    def _enter(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.execute")

    @make_method("/olc/key/backspace")
    def _backspace(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.backspace")
