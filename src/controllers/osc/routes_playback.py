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

from olc.controllers.osc.parser import parse_osc_bool, parse_osc_normalized
from olc.controllers.osc.transport import make_method

if typing.TYPE_CHECKING:
    from olc.controllers.osc import Osc
    from olc.core.app import CoreApplication


class PlaybackRoutesMixin:
    """OSC routes for playback, crossfade, main fader, and blackout."""

    if typing.TYPE_CHECKING:
        app: CoreApplication

        @property
        def osc(self) -> Osc | None: ...
        def _execute_action(
            self, name: str, *args: object, **kwargs: object
        ) -> object: ...
        def _is_momentary_press(self, args: list) -> bool: ...
        def _get_playback_telemetry(self) -> dict[str, object]: ...
        def _get_cues_dump_json(self) -> str: ...
        def _send_direct(
            self,
            sender_addr: tuple[str, int] | None,
            path: str,
            *args: object,
        ) -> None: ...
        def _emit_osc(
            self,
            topic: str,
            path: str,
            *args: object,
            sender_addr: tuple[str, int] | None = None,
        ) -> None: ...

    @make_method("/olc/key/go")
    def _go(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("playback.go")

    @make_method("/olc/key/pause")
    def _pause(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("playback.pause")

    @make_method("/olc/key/goback")
    def _goback(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("playback.go_back")

    @make_method("/olc/key/seq+")
    def _seq_plus(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("playback.sequence_plus")

    @make_method("/olc/key/seq-")
    def _seq_minus(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("playback.sequence_minus")

    @make_method("/olc/playback/goto_cue")
    @make_method("/olc/playback/goto")
    def _playback_goto_cue(self, _address: str, args: list) -> None:
        """Jump to a specific cue, with optional fade override time."""
        cmd_str = self.app.commandline.get_string().strip()
        if cmd_str and (not args or (len(args) == 1 and args[0] in (1, 1.0, True))):
            target: object = cmd_str
            self.app.commandline.set_string("")
        elif not args or (len(args) == 1 and not parse_osc_bool(args[0])):
            return
        else:
            target = args[0]
        override_time = float(args[1]) if len(args) >= 2 else None
        self._execute_action("playback.goto", target, override_time)

    @make_method("/olc/playback/active/cue")
    def _playback_query_active_cue(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Query currently active cue number."""
        if self.osc is not None and sender_addr is not None:
            telem = self._get_playback_telemetry()
            self._send_direct(
                sender_addr,
                "/olc/playback/active/cue",
                telem["active_cue"],
            )

    @make_method("/olc/playback/next/cue")
    def _playback_query_next_cue(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Query next cue number."""
        if self.osc is not None and sender_addr is not None:
            telem = self._get_playback_telemetry()
            self._send_direct(
                sender_addr,
                "/olc/playback/next/cue",
                telem["next_cue"],
            )

    @make_method("/olc/playback/state")
    def _playback_query_state(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Query current playback state (idle, running, paused)."""
        if self.osc is not None and sender_addr is not None:
            telem = self._get_playback_telemetry()
            self._send_direct(
                sender_addr,
                "/olc/playback/state",
                telem["state"],
            )

    @make_method("/olc/playback/dump")
    @make_method("/olc/cue/dump")
    def _playback_dump(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Export JSON dump of all cues in main playback."""
        if self.osc is None:
            return
        dump_json = self._get_cues_dump_json()
        self._emit_osc(
            "playback", "/olc/playback/dump", dump_json, sender_addr=sender_addr
        )

    @make_method("/olc/playback/xfade/a")
    def _playback_xfade_a(self, _address: str, args: list) -> None:
        """Set manual crossfade scale A (0.0 to 1.0)."""
        if not args:
            return
        level = parse_osc_normalized(args[0])
        self._execute_action("playback.manual_xfade", "a", level)

    @make_method("/olc/playback/xfade/b")
    def _playback_xfade_b(self, _address: str, args: list) -> None:
        """Set manual crossfade scale B (0.0 to 1.0)."""
        if not args:
            return
        level = parse_osc_normalized(args[0])
        self._execute_action("playback.manual_xfade", "b", level)

    @make_method("/olc/playback/xfade")
    def _playback_xfade(self, _address: str, args: list) -> None:
        """Adjust unified crossfade progress (0.0 = cue A, 1.0 = cue B)."""
        if not args:
            return
        progress = parse_osc_normalized(args[0])
        self._execute_action("playback.manual_xfade", "a", progress)
        self._execute_action("playback.manual_xfade", "b", progress)

    @make_method("/olc/mainfader")
    def _mainfader(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Set or query the Main Fader level."""
        if args:
            norm_val = parse_osc_normalized(args[0])
            self._execute_action("main_fader.set_level", norm_val)
        elif sender_addr is not None:
            lvl = float(getattr(self.app, "main_fader_level", 1.0))
            self._send_direct(sender_addr, "/olc/mainfader", lvl)

    @make_method("/olc/blackout")
    def _blackout(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Set or toggle the scenic blackout state."""
        if args:
            target_state = parse_osc_bool(args[0])
            self._execute_action("dmx.blackout_all", target_state)
        else:
            self._execute_action("dmx.blackout_all")

        if sender_addr is not None:
            curr_state = 1 if getattr(self.app, "blackout_active", False) else 0
            self._send_direct(sender_addr, "/olc/blackout", curr_state)
