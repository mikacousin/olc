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

from olc.controllers.osc.transport import make_method
from olc.devices.builtin import create_dimmer_definition

if typing.TYPE_CHECKING:
    from olc.controllers.osc import Osc
    from olc.core.app import CoreApplication


class PatchRoutesMixin:
    """OSC routes for fixture and dimmer patching."""

    if typing.TYPE_CHECKING:
        app: CoreApplication

        @property
        def osc(self) -> Osc | None: ...
        def _execute_action(
            self, name: str, *args: object, **kwargs: object
        ) -> object: ...
        def _send_patch_status(
            self,
            status: str,
            command: str,
            message: str,
            sender_addr: tuple[str, int] | None = None,
        ) -> None: ...
        def _emit_osc(
            self,
            topic: str,
            path: str,
            *args: object,
            sender_addr: tuple[str, int] | None = None,
        ) -> None: ...

    @make_method("/olc/patch/dimmer")
    def _patch_dimmer(self, address: str, args: list) -> None:
        """Patch a dimmer device (Generic:Dimmer) directly via OSC.

        Args:
            address: The OSC address (/olc/patch/dimmer).
            args: [device_id, universe, address] or [device_id, "universe/address"].
        """
        try:
            if not args or len(args) < 2:
                self._send_patch_status(
                    "ERROR",
                    address,
                    "Usage: [device_id, universe, address] or [device_id, 'univ/addr']",
                )
                return

            device_id = int(args[0])
            if len(args) == 2 and isinstance(args[1], str):
                addr_str = args[1].strip()
                if "/" in addr_str:
                    parts = addr_str.split("/")
                elif "." in addr_str:
                    parts = addr_str.split(".")
                else:
                    self._send_patch_status(
                        "ERROR",
                        address,
                        f"Invalid address '{args[1]}', expected 'universe/address'",
                    )
                    return
                if len(parts) != 2:
                    self._send_patch_status(
                        "ERROR",
                        address,
                        f"Invalid address '{args[1]}', expected 'universe/address'",
                    )
                    return
                try:
                    universe = int(parts[0])
                    dmx_address = int(parts[1])
                except ValueError:
                    self._send_patch_status(
                        "ERROR",
                        address,
                        f"Invalid integer in address '{args[1]}'",
                    )
                    return
            elif len(args) >= 3:
                universe = int(args[1])
                dmx_address = int(args[2])
            else:
                self._send_patch_status(
                    "ERROR", address, "Invalid arguments for patch dimmer"
                )
                return

            fixture_lib = self.app.lightshow.fixture_library
            dimmer_def = fixture_lib.get_by_key("Generic:Dimmer")
            if dimmer_def is None:
                dimmer_def = create_dimmer_definition(fine=False)

            self._execute_action(
                "patch.device",
                device_id,
                dimmer_def,
                universe,
                dmx_address,
                None,
                "",
            )
            self._send_patch_status(
                "OK", address, f"Device {device_id} patched to {universe}/{dmx_address}"
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err))

    @make_method("/olc/patch/device")
    def _patch_device(self, address: str, args: list) -> None:
        """Patch a lighting fixture device directly via OSC.

        Args:
            address: The OSC address (/olc/patch/device).
            args: [device_id, fixture_key, universe, address, (mode_name), (label)].
        """
        try:
            if not args or len(args) < 4:
                self._send_patch_status(
                    "ERROR",
                    address,
                    "Usage: [device_id, fixture_key, universe, address, (mode), (lbl)]",
                )
                return

            device_id = int(args[0])
            fixture_key = str(args[1])
            universe = int(args[2])
            dmx_address = int(args[3])
            mode_name = str(args[4]).strip() if len(args) > 4 and args[4] else None
            if mode_name and mode_name.lower() == "default":
                mode_name = None
            label = str(args[5]) if len(args) > 5 and args[5] else ""

            fixture_lib = self.app.lightshow.fixture_library
            fixture_def = fixture_lib.get_by_key(fixture_key)

            if fixture_def is None:
                self._send_patch_status(
                    "ERROR",
                    address,
                    f"Fixture definition '{fixture_key}' not found in library",
                )
                return

            self._execute_action(
                "patch.device",
                device_id,
                fixture_def,
                universe,
                dmx_address,
                mode_name,
                label,
            )
            self._send_patch_status(
                "OK",
                address,
                f"Device {device_id} ({fixture_def.full_name}) "
                f"patched to {universe}/{dmx_address}",
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err))

    @make_method("/olc/patch/unpatch")
    def _patch_unpatch(self, address: str, args: list) -> None:
        """Unpatch a lighting device via OSC.

        Args:
            address: The OSC address (/olc/patch/unpatch).
            args: [device_id: int].
        """
        try:
            if not args:
                self._send_patch_status("ERROR", address, "Usage: [device_id: int]")
                return

            device_id = int(args[0])
            self._execute_action("patch.unpatch_device", device_id)
            self._send_patch_status("OK", address, f"Device {device_id} unpatched")
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err))

    @make_method("/olc/patch/1on1")
    def _patch_1on1(self, address: str, _args: list) -> None:
        """Reset patch to 1:1 dimmers via OSC."""
        try:
            self._execute_action("patch.set_1on1")
            self._send_patch_status("OK", address, "Patch reset to 1:1")
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err))

    @make_method("/olc/patch/clear")
    def _patch_clear(self, address: str, _args: list) -> None:
        """Clear all patch assignments via OSC."""
        try:
            self._execute_action("patch.clear")
            self._send_patch_status("OK", address, "Patch cleared")
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err))

    @make_method("/olc/patch/curve")
    def _patch_curve(self, address: str, args: list) -> None:
        """Set transfer curve for a device via OSC.

        Args:
            address: The OSC address (/olc/patch/curve).
            args: [device_id: int, curve_id: int].
        """
        try:
            if not args or len(args) < 2:
                self._send_patch_status(
                    "ERROR", address, "Usage: [device_id: int, curve_id: int]"
                )
                return

            device_id = int(args[0])
            curve_id = int(args[1])
            self._execute_action("patch.set_device_curve", device_id, curve_id)
            self._send_patch_status(
                "OK", address, f"Device {device_id} curve set to {curve_id}"
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err))

    @make_method("/olc/patch/get")
    def _patch_get(
        self,
        address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Query patch state of a single device via OSC.

        Sends response on /olc/patch/device/info.
        """
        try:
            if not args or self.osc is None:
                return

            device_id = int(args[0])
            dev = self.app.lightshow.patch.get_device(device_id)
            if dev is not None:
                model_name = f"{dev.manufacturer}:{dev.model}"
                self._emit_osc(
                    "patch",
                    "/olc/patch/device/info",
                    dev.fixture_id,
                    dev.universe,
                    dev.address,
                    dev.channel_count(),
                    model_name,
                    dev.label,
                    sender_addr=sender_addr,
                )
            else:
                self._emit_osc(
                    "patch",
                    "/olc/patch/device/info",
                    device_id,
                    0,
                    0,
                    0,
                    "",
                    "",
                    sender_addr=sender_addr,
                )
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._send_patch_status("ERROR", address, str(err), sender_addr)

    @make_method("/olc/patch/dump")
    def _patch_dump(
        self,
        _address: str,
        _args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Export JSON dump of all patched devices via OSC."""
        if self.osc is None:
            return

        devices = sorted(
            self.app.lightshow.patch.devices.values(), key=lambda d: d.fixture_id
        )
        dump_data = [
            {
                "device_id": d.fixture_id,
                "universe": d.universe,
                "address": d.address,
                "footprint": d.channel_count(),
                "model": f"{d.manufacturer}:{d.model}",
                "mode": d.mode_name,
                "label": d.label,
            }
            for d in devices
        ]
        dump_json = json_dumps(dump_data)
        self._emit_osc("patch", "/olc/patch/dump", dump_json, sender_addr=sender_addr)
