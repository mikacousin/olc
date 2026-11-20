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
from json import loads as json_loads

from olc.controllers.osc.parser import parse_osc_bool, parse_osc_normalized
from olc.controllers.osc.transport import make_method

if typing.TYPE_CHECKING:
    from olc.controllers.osc import Osc
    from olc.controllers.osc.channels_grid import ChannelsGridManager
    from olc.core.app import CoreApplication


class ChannelsRoutesMixin:
    """OSC routes for channels grid, selection & levels, park, and universes."""

    if typing.TYPE_CHECKING:
        app: CoreApplication
        channels_grid: ChannelsGridManager

        @property
        def osc(self) -> Osc | None: ...
        def _execute_action(
            self, name: str, *args: object, **kwargs: object
        ) -> object: ...
        def _is_momentary_press(self, args: list) -> bool: ...
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
        def _send_channels_page(
            self, sender_addr: tuple[str, int] | None = None
        ) -> None: ...

    @make_method("/olc/channels/subscribe")
    def _channels_subscribe(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Subscribe to channels topic with custom grid size and start channel."""
        osc = self.osc
        if osc is None:
            return

        if len(args) >= 1:
            try:
                self.channels_grid.grid_size = int(args[0])
            except (ValueError, TypeError):
                pass
        if len(args) >= 2:
            try:
                self.channels_grid.start_channel = int(args[1])
            except (ValueError, TypeError):
                pass

        host = sender_addr[0] if sender_addr else "127.0.0.1"
        port = sender_addr[1] if sender_addr else 8000
        osc.subscriptions.subscribe(host, port, "channels")
        self._send_direct((host, port), "/olc/subscribe/status", "OK", "channels")
        self.app.emit(
            "osc.subscribers_changed",
            osc.subscriptions.get_subscribers_snapshot(),
        )
        self._send_channels_page(sender_addr)

    @make_method("/olc/channels/page/+")
    def _channels_page_next(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Advance to next channel page."""
        if not self._is_momentary_press(args):
            return
        self.channels_grid.next_page()
        self._send_channels_page(sender_addr)

    @make_method("/olc/channels/page/-")
    def _channels_page_prev(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Go to previous channel page."""
        if not self._is_momentary_press(args):
            return
        self.channels_grid.prev_page()
        self._send_channels_page(sender_addr)

    @make_method("/olc/channels/start")
    def _channels_start(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Jump to a specific start channel."""
        if args:
            try:
                self.channels_grid.start_channel = int(args[0])
            except (ValueError, TypeError):
                pass
        self._send_channels_page(sender_addr)

    @make_method("/olc/channels/dump")
    def _channels_dump(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Dump JSON representation of current channels page."""
        if self.osc is None:
            return
        dump_json = self.channels_grid.get_page_snapshot_json()
        self._emit_osc(
            "channels", "/olc/channels/dump", dump_json, sender_addr=sender_addr
        )

    @make_method("/olc/channels/format")
    def _channels_format(self, _address: str, args: list) -> None:
        """Cycle or set active ChannelsView display format via OSC."""
        if args and isinstance(args[0], str):
            self._execute_action("gui.channels_format", args[0])
            return
        if self._is_momentary_press(args):
            self._execute_action("gui.channels_format")

    @make_method("/olc/channels/data")
    @make_method("/olc/channels/readout")
    def _channels_data(self, _address: str, args: list) -> None:
        """Toggle, cycle, or set active ChannelsView readout mode via OSC."""
        if args and isinstance(args[0], str):
            self._execute_action("gui.channels_data", args[0])
            return
        if self._is_momentary_press(args):
            self._execute_action("gui.channels_data")

    @make_method("/olc/channels/labels")
    def _channels_labels(self, _address: str, args: list) -> None:
        """Toggle or explicitly set fixture label visibility via OSC."""
        if not args or (
            isinstance(args[0], str) and args[0].strip().lower() == "toggle"
        ):
            self._execute_action("gui.channels_labels")
            return
        self._execute_action("gui.channels_labels", parse_osc_bool(args[0]))

    @make_method("/olc/channels/labels/toggle")
    def _channels_labels_toggle(self, _address: str, args: list) -> None:
        """Momentary toggle for fixture label visibility via OSC."""
        if self._is_momentary_press(args):
            self._execute_action("gui.channels_labels")

    @make_method("/olc/channels/flexi")
    def _channels_flexi(self, _address: str, args: list) -> None:
        """Cycle or set active ChannelsView Flexi view mode via OSC."""
        if args and isinstance(args[0], str):
            self._execute_action("gui.channels_flexi", args[0])
            return
        if self._is_momentary_press(args):
            self._execute_action("gui.channels_flexi")

    def _toggle_channel_selection(self, ch: int) -> None:
        selected = list(getattr(self.app, "selected_channels", []))
        if ch in selected:
            new_selected = [c for c in selected if c != ch]
        else:
            new_selected = [*selected, ch]
        self._execute_action("channel.select_channels", new_selected)

    @make_method("/olc/cell/*/touch")
    def _cell_touch(self, address: str, args: list) -> None:
        """Touch interaction on a grid cell (toggles selection)."""
        if not parse_osc_bool(args[0] if args else True):
            return

        parts = address.split("/")
        try:
            cell_idx = int(parts[3])
        except (IndexError, ValueError):
            return

        ch = self.channels_grid.get_channel_for_cell(cell_idx)
        if ch is not None:
            self._toggle_channel_selection(ch)

    @make_method("/olc/cell/*/level")
    def _cell_level(self, address: str, args: list) -> None:
        """Set level for the channel associated with a cell."""
        if not args:
            return
        parts = address.split("/")
        try:
            cell_idx = int(parts[3])
        except (IndexError, ValueError):
            return

        ch = self.channels_grid.get_channel_for_cell(cell_idx)
        if ch is not None:
            norm_level = parse_osc_normalized(args[0])
            self._execute_action("channel.set_level", ch, norm_level)

    @make_method("/olc/channel/*/touch")
    def _channel_touch(self, address: str, args: list) -> None:
        """Touch interaction on an absolute channel (toggles selection)."""
        if not parse_osc_bool(args[0] if args else True):
            return

        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return

        self._toggle_channel_selection(ch)

    @make_method("/olc/channel/*/level")
    def _channel_level(self, address: str, args: list) -> None:
        """Set level directly for an absolute channel."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return

        norm_level = parse_osc_normalized(args[0])
        self._execute_action("channel.set_level", ch, norm_level)

    @make_method("/olc/channel/*/park")
    def _channel_park(self, address: str, args: list) -> None:
        """Park a channel at a given level or current level."""
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        level = float(args[0]) if args else None
        self._execute_action("channel.park", ch, level)

    @make_method("/olc/channel/*/unpark")
    def _channel_unpark(self, address: str, _args: list) -> None:
        """Unpark a channel."""
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        self._execute_action("channel.unpark", ch)

    @make_method("/olc/address/*/*/park")
    def _address_park(self, address: str, args: list) -> None:
        """Park an address (univ, output) at a level."""
        parts = address.split("/")
        try:
            univ = int(parts[3])
            out = int(parts[4])
        except (IndexError, ValueError):
            return
        level = float(args[0]) if args else 1.0
        self._execute_action("address.park", (univ, out), level)

    @make_method("/olc/address/*/*/unpark")
    def _address_unpark(self, address: str, _args: list) -> None:
        """Unpark an address (univ, output)."""
        parts = address.split("/")
        try:
            univ = int(parts[3])
            out = int(parts[4])
        except (IndexError, ValueError):
            return
        self._execute_action("address.unpark", (univ, out))

    @make_method("/olc/park/unpark_all")
    def _park_unpark_all(self, _address: str, _args: list) -> None:
        """Unpark all parked channels and addresses."""
        self._execute_action("park.unpark_all")

    @make_method("/olc/channels/sneak")
    def _channels_sneak(self, _address: str, args: list) -> None:
        """Sneak selected channels (or all manual channels) with optional duration."""
        if not self._is_momentary_press(args):
            return
        duration: float | None = None
        if len(args) >= 2:
            try:
                duration = float(args[1])
            except (TypeError, ValueError):
                duration = None
        self._execute_action("channel.sneak", None, duration, True)

    @make_method("/olc/channel/*/sneak")
    def _channel_sneak(self, address: str, args: list) -> None:
        """Sneak a specific channel with optional duration."""
        if not self._is_momentary_press(args):
            return
        try:
            ch = int(address.split("/")[3])
        except (IndexError, ValueError):
            return
        duration: float | None = None
        if len(args) >= 2:
            try:
                duration = float(args[1])
            except (TypeError, ValueError):
                duration = None
        self._execute_action("channel.sneak", [ch], duration)

    @make_method("/olc/universe/*/set_channels")
    def _universe_set_channels(self, address: str, args: list) -> None:
        """Set DMX universe channel levels via JSON payload or channel/value pairs."""
        parts = address.split("/")
        if len(parts) < 5 or not args:
            return
        try:
            univ = int(parts[3])
            raw_payload = args[0]
            if isinstance(raw_payload, str):
                decoded = json_loads(raw_payload)
                if not isinstance(decoded, dict):
                    return
                channels = {int(k): int(v) for k, v in decoded.items()}
            elif isinstance(raw_payload, dict):
                channels = {int(k): int(v) for k, v in raw_payload.items()}
            else:
                channels = {
                    int(args[i]): int(args[i + 1]) for i in range(0, len(args) - 1, 2)
                }
        except (ValueError, TypeError, KeyError):
            return
        self._execute_action("dmx.set_universe_levels", univ, channels)

    @make_method("/olc/universe/*/blackout")
    def _universe_blackout(self, address: str, _args: list) -> None:
        """Blackout a specific DMX universe via OSC."""
        parts = address.split("/")
        if len(parts) < 5:
            return
        try:
            univ = int(parts[3])
        except ValueError:
            return
        self._execute_action("universe.blackout", univ)
