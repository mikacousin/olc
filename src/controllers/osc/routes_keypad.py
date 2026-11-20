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

_OSC_PALETTE_CAT_MAP: dict[str, str] = {
    "intensity": "intensity",
    "intens": "intensity",
    "ip": "intensity",
    "focus": "focus",
    "fp": "focus",
    "color": "color",
    "colour": "color",
    "cp": "color",
    "beam": "beam",
    "bp": "beam",
    "preset": "preset",
    "pr": "preset",
}


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

    @make_method("/olc/key/record_cmd")
    def _record_cmd_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "RECORD ")

    @make_method("/olc/key/update_cmd")
    def _update_cmd_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", "UPDATE ")

    @make_method("/olc/key/palette")
    def _palette_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " PALETTE ")

    @make_method("/olc/key/preset")
    def _preset_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " PRESET ")

    @make_method("/olc/key/intensity")
    def _intensity_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " INTENSITY ")

    @make_method("/olc/key/focus")
    def _focus_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " FOCUS ")

    @make_method("/olc/key/color")
    def _color_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " COLOR ")

    @make_method("/olc/key/beam")
    def _beam_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " BEAM ")

    @make_method("/olc/key/effect")
    def _effect_key(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.append_char", " EFFECT ")

    @make_method("/olc/effect/stop_all")
    def _effect_stop_all(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("effect.stop")

    @make_method("/olc/effect/tap_tempo")
    def _effect_tap_tempo(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        eff_num: float | None = None
        if args and isinstance(args[0], (int, float)) and not isinstance(args[0], bool):
            val = float(args[0])
            if val not in (0.0, 1.0):
                eff_num = val
        self._execute_action("effect.tap_tempo", eff_num)

    @make_method("/olc/effect/*/*")
    def _direct_effect(self, address: str, args: list) -> None:
        parts = address.strip("/").split("/")
        if len(parts) < 4:
            return
        try:
            number = float(parts[2])
        except ValueError:
            return
        subcmd = parts[3].lower()
        if subcmd == "start":
            if self._is_momentary_press(args):
                self._execute_action("effect.apply", number)
        elif subcmd == "stop":
            if self._is_momentary_press(args):
                self._execute_action("effect.stop", number=number)
        elif subcmd == "rate" and args:
            try:
                raw_rate = float(args[0])
            except (TypeError, ValueError):
                return
            scale = raw_rate / 100.0 if raw_rate > 10.0 else max(0.01, raw_rate)
            app = getattr(self, "app", None)
            engine = getattr(app, "effects_engine", None) if app is not None else None
            if engine is not None:
                matched = False
                for inst in engine.get_active_instances():
                    if inst.effect_number == round(number, 3):
                        inst.rate_scale = scale
                        matched = True
                if matched:
                    engine.tick()
                else:
                    self._execute_action(
                        "effect.update", number, rate=round(scale * 100.0, 2)
                    )
        elif subcmd == "size" and args:
            try:
                raw_size = float(args[0])
            except (TypeError, ValueError):
                return
            scale = raw_size / 100.0 if raw_size > 10.0 else max(0.0, raw_size)
            app = getattr(self, "app", None)
            engine = getattr(app, "effects_engine", None) if app is not None else None
            if engine is not None:
                matched = False
                for inst in engine.get_active_instances():
                    if inst.effect_number == round(number, 3):
                        inst.size_scale = scale
                        matched = True
                if matched:
                    engine.tick()
                else:
                    self._execute_action(
                        "effect.update", number, size=round(scale * 100.0, 2)
                    )
        elif subcmd == "tap_tempo":
            if self._is_momentary_press(args):
                self._execute_action("effect.tap_tempo", number)

    @make_method("/olc/palette/*/*")
    def _direct_palette(self, address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        parts = address.strip("/").split("/")
        if len(parts) < 4:
            return
        category = _OSC_PALETTE_CAT_MAP.get(parts[2].lower())
        if category is None:
            return
        try:
            number = float(parts[3])
        except ValueError:
            return
        self._execute_action("palette.apply", category, number)

    @make_method("/olc/preset/*")
    def _direct_preset(self, address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        parts = address.strip("/").split("/")
        if len(parts) < 3:
            return
        try:
            number = float(parts[2])
        except ValueError:
            return
        self._execute_action("palette.apply", "preset", number)

    @make_method("/olc/key/enter")
    def _enter(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.execute")

    @make_method("/olc/key/backspace")
    def _backspace(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.backspace")
