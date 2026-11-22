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
from json import dumps as json_dumps

from olc.controllers.osc.parser import parse_osc_bool, parse_osc_normalized
from olc.controllers.osc.transport import make_method

if typing.TYPE_CHECKING:
    from olc.controllers.osc import Osc
    from olc.core.app import CoreApplication


class FadersRoutesMixin:
    """OSC routes for faders, fader pages, and independents."""

    if typing.TYPE_CHECKING:
        app: CoreApplication

        @property
        def osc(self) -> Osc | None: ...
        def _execute_action(
            self, name: str, *args: object, **kwargs: object
        ) -> object: ...
        def _is_momentary_press(self, args: list) -> bool: ...
        def _send(self, path: str, *args: object) -> None: ...
        def _send_direct(
            self,
            sender_addr: tuple[str, int] | None,
            path: str,
            *args: object,
        ) -> None: ...
        def send_full_sync(self) -> None: ...

    @make_method("/olc/fader/pageupdate")
    @make_method("/olc/sync")
    def _sub_launch(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        fader_bank = self.app.lightshow.fader_bank
        if self.osc is not None:
            self._send("/olc/fader/page", fader_bank.active_page)
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self._send(f"/olc/fader/1/{fader.index}/label", fader.text)
            self.send_full_sync()

    @make_method("/olc/fader/page+")
    def _fader_page_plus(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        fader_bank = self.app.lightshow.fader_bank
        target_page = fader_bank.get_next_page(1)
        self._execute_action("fader.set_page", target_page)

    @make_method("/olc/fader/page-")
    def _fader_page_minus(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        fader_bank = self.app.lightshow.fader_bank
        target_page = fader_bank.get_next_page(-1)
        self._execute_action("fader.set_page", target_page)

    @make_method("/olc/fader/1/*/level")
    def _fader_level(self, address: str, args: list) -> None:
        try:
            fader_index = int(address.split("/")[4])
            level = parse_osc_normalized(args[0]) if args else 0.0
            fader_bank = self.app.lightshow.fader_bank
            self._execute_action(
                "fader.set_level", fader_bank.active_page, fader_index, level
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_level: {err}")

    @make_method("/olc/fader/1/*/flash")
    def _fader_flash(self, address: str, args: list) -> None:
        try:
            pressed = parse_osc_bool(args[0]) if args else True
            fader_index = int(address.split("/")[4])
            fader_bank = self.app.lightshow.fader_bank
            self._execute_action(
                "fader.flash", fader_bank.active_page, fader_index, pressed
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_flash: {err}")

    @make_method("/olc/independent/*/level")
    def _independent_level(self, address: str, args: list) -> None:
        """Set independent level (0.0 to 1.0)."""
        if not args:
            return
        try:
            number = int(address.split("/")[3])
            level = parse_osc_normalized(args[0])
            self._execute_action("independent.set_level", number, level)
        except (IndexError, ValueError) as err:
            print(f"[OSC Delegate] Error in independent_level: {err}")

    @make_method("/olc/independent/*/button")
    def _independent_button(self, address: str, args: list) -> None:
        """Press or release independent button."""
        try:
            number = int(address.split("/")[3])
            pressed = parse_osc_bool(args[0]) if args else True
            level = 1.0 if pressed else 0.0
            self._execute_action("independent.set_level", number, level)
        except (IndexError, ValueError) as err:
            print(f"[OSC Delegate] Error in independent_button: {err}")

    @make_method("/olc/independent/dump")
    def _independent_dump(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Send dump of all independents."""
        if self.osc is None or sender_addr is None:
            return
        independents = getattr(self.app.lightshow, "independents", None)
        if independents is None:
            return
        data = []
        for inde in getattr(independents, "independents", []):
            data.append(
                {
                    "number": int(inde.number),
                    "level": float(inde.level),
                    "text": str(inde.text),
                    "type": str(getattr(inde, "inde_type", "knob")),
                    "channels": sorted(list(inde.channels)),
                }
            )
        self._send_direct(sender_addr, "/olc/independent/dump", json_dumps(data))
