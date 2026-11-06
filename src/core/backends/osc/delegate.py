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
from json import dumps as json_dumps

from olc.core.osc import make_method
from olc.define import MAX_FADER_PAGE
from olc.devices.builtin import create_dimmer_definition

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
        self.app.subscribe("patch.changed", self._on_patch_changed)

    def _send_patch_status(
        self,
        status: str,
        command: str,
        message: str,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Send OSC status feedback for patch operations."""
        if self.app.engine is not None:
            if sender_addr is not None:
                self.app.engine.osc_subscriptions.send_direct(
                    sender_addr[0],
                    sender_addr[1],
                    "/olc/patch/status",
                    status,
                    command,
                    message,
                )
            self.app.engine.publish_osc(
                "patch", "/olc/patch/status", status, command, message
            )

    def _on_patch_changed(self) -> None:
        """Send OSC notification when the patch changes."""
        if self.app.engine is not None:
            count = len(self.app.lightshow.patch.devices)
            self.app.engine.publish_osc("patch", "/olc/patch/changed", count)

    def _on_fader_page_changed(self, page: int) -> None:
        """Send OSC feedback when the active fader page changes."""
        if self.app.engine is not None:
            fader_bank = self.app.lightshow.fader_bank
            self.app.engine.publish_osc("faders", "/olc/fader/page", page)
            for fader in fader_bank.faders[page].values():
                self.app.engine.publish_osc(
                    "faders", f"/olc/fader/1/{fader.index}/label", fader.text
                )
                self.app.engine.publish_osc(
                    "faders",
                    f"/olc/fader/1/{fader.index}/level",
                    round(fader.level * 255),
                )

    def _on_fader_level_changed(self, fader_index: int, level: float) -> None:
        """Send OSC feedback when a fader level changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc(
                "faders", f"/olc/fader/1/{fader_index}/level", round(level * 255)
            )

    def _on_fader_changed(self, page: int, index: int) -> None:
        """Send OSC feedback when a fader label or assignment changes."""
        if self.app.engine is not None:
            fader_bank = self.app.lightshow.fader_bank
            if page == fader_bank.active_page:
                fader = fader_bank.faders[page][index]
                self.app.engine.publish_osc(
                    "faders", f"/olc/fader/1/{index}/label", fader.text
                )
                self.app.engine.publish_osc(
                    "faders",
                    f"/olc/fader/1/{index}/level",
                    round(fader.level * 255),
                )

    def _on_commandline_changed(self, keystring: str) -> None:
        """Send OSC feedback when the logical command line changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc("commandline", "/olc/command_line", keystring)

    @make_method("/olc/subscribe")
    def _subscribe(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Subscribe a remote client to an OSC topic.

        Supported topics: patch, faders, playback, commandline, all.
        """
        if self.app.engine is None:
            return

        topic = str(args[0]).strip().lower() if args else "all"
        host = sender_addr[0] if sender_addr else "127.0.0.1"
        port = sender_addr[1] if sender_addr else 8000

        if len(args) >= 2:
            try:
                port = int(args[1])
            except (ValueError, TypeError):
                pass

        self.app.engine.osc_subscriptions.subscribe(host, port, topic)
        self.app.engine.osc_subscriptions.send_direct(
            host, port, "/olc/subscribe/status", "OK", topic
        )
        self.app.emit(
            "osc.subscribers_changed",
            self.app.engine.osc_subscriptions.get_subscribers_snapshot(),
        )

        if topic in ("patch", "all"):
            devices = sorted(
                self.app.lightshow.patch.devices.values(), key=lambda d: d.device_id
            )
            dump_data = [
                {
                    "device_id": d.device_id,
                    "universe": d.universe,
                    "address": d.address,
                    "footprint": d.channel_count(),
                    "model": f"{d.manufacturer}:{d.model}",
                    "mode": d.mode_name,
                    "label": d.label,
                }
                for d in devices
            ]
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/patch/dump", json_dumps(dump_data)
            )

    @make_method("/olc/unsubscribe")
    def _unsubscribe(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Unsubscribe a client from an OSC topic."""
        if self.app.engine is None:
            return

        topic = str(args[0]).strip().lower() if args else "all"
        host = sender_addr[0] if sender_addr else "127.0.0.1"
        port = sender_addr[1] if sender_addr else 8000

        if len(args) >= 2:
            try:
                port = int(args[1])
            except (ValueError, TypeError):
                pass

        self.app.engine.osc_subscriptions.unsubscribe(host, port, topic)
        self.app.engine.osc_subscriptions.send_direct(
            host, port, "/olc/subscribe/status", "OK", "unsubscribed"
        )
        self.app.emit(
            "osc.subscribers_changed",
            self.app.engine.osc_subscriptions.get_subscribers_snapshot(),
        )

    @make_method("/olc/ping")
    def _ping(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Handle keepalive ping from an OSC client."""
        if self.app.engine is None or sender_addr is None:
            return

        host, port = sender_addr
        self.app.engine.osc_subscriptions.refresh_keepalive(host, port)
        token = args[0] if args else 0
        self.app.engine.osc_subscriptions.send_direct(host, port, "/olc/pong", token)

    @make_method("/olc/command_line")
    def _commandline(self, _address: str, _args: list) -> None:
        if self.app.engine:
            self.app.engine.publish_osc(
                "commandline",
                "/olc/command_line",
                self.app.commandline.get_string(),
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
            self.app.engine.publish_osc("commandline", "/olc/cmd/status", status_msg)

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

    @make_method("/olc/patch/dimmer")
    def _patch_dimmer(self, address: str, args: list) -> None:
        """Patch a dimmer device (Generic:Dimmer) directly via OSC.

        Args:
            address: The OSC address (/olc/patch/dimmer).
            args: [device_id, universe, address] or [device_id, "universe.address"].
        """
        try:
            if not args or len(args) < 2:
                self._send_patch_status(
                    "ERROR",
                    address,
                    "Usage: [device_id, universe, address] or [device_id, 'univ.addr']",
                )
                return

            device_id = int(args[0])
            if len(args) == 2 and isinstance(args[1], str):
                parts = args[1].split(".")
                if len(parts) != 2:
                    self._send_patch_status(
                        "ERROR",
                        address,
                        f"Invalid address '{args[1]}', expected 'universe.address'",
                    )
                    return
                universe = int(parts[0])
                dmx_address = int(parts[1])
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
                "OK", address, f"Device {device_id} patched to {universe}.{dmx_address}"
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
                aliases = {
                    "rgb": "Generic:LED RGB",
                    "generic:rgb": "Generic:LED RGB",
                    "rgbw": "Generic:LED RGBW",
                    "generic:rgbw": "Generic:LED RGBW",
                    "rgba": "Generic:LED RGBA",
                    "generic:rgba": "Generic:LED RGBA",
                    "dimmer": "Generic:Dimmer",
                    "generic:dimmer": "Generic:Dimmer",
                    "moving_head": "Generic:Moving Head Spot",
                    "generic:moving_head": "Generic:Moving Head Spot",
                }
                alias = aliases.get(fixture_key.lower().strip())
                if alias:
                    fixture_def = fixture_lib.get_by_key(alias)

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
                f"patched to {universe}.{dmx_address}",
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
            if not args or self.app.engine is None:
                return

            device_id = int(args[0])
            dev = self.app.lightshow.patch.get_device(device_id)
            if dev is not None:
                model_name = f"{dev.manufacturer}:{dev.model}"
                if sender_addr is not None:
                    self.app.engine.osc_subscriptions.send_direct(
                        sender_addr[0],
                        sender_addr[1],
                        "/olc/patch/device/info",
                        dev.device_id,
                        dev.universe,
                        dev.address,
                        dev.channel_count(),
                        model_name,
                        dev.label,
                    )
                self.app.engine.publish_osc(
                    "patch",
                    "/olc/patch/device/info",
                    dev.device_id,
                    dev.universe,
                    dev.address,
                    dev.channel_count(),
                    model_name,
                    dev.label,
                )
            else:
                if sender_addr is not None:
                    self.app.engine.osc_subscriptions.send_direct(
                        sender_addr[0],
                        sender_addr[1],
                        "/olc/patch/device/info",
                        device_id,
                        0,
                        0,
                        0,
                        "",
                        "",
                    )
                self.app.engine.publish_osc(
                    "patch",
                    "/olc/patch/device/info",
                    device_id,
                    0,
                    0,
                    0,
                    "",
                    "",
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
        if self.app.engine is None:
            return

        devices = sorted(
            self.app.lightshow.patch.devices.values(), key=lambda d: d.device_id
        )
        dump_data = [
            {
                "device_id": d.device_id,
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
        if sender_addr is not None:
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/patch/dump", dump_json
            )
        self.app.engine.publish_osc("patch", "/olc/patch/dump", dump_json)

    @make_method(None)
    def _fallback(self, address: str, args: list) -> None:
        print(f"[OSC Delegate] Unknown message: {address} with args {args}")
