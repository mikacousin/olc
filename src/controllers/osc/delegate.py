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

import colorsys
import re
import typing
from json import dumps as json_dumps

from olc.controllers.osc.channels_grid import ChannelsGridManager
from olc.controllers.osc.parser import parse_osc_bool
from olc.controllers.osc.routes_channels import ChannelsRoutesMixin
from olc.controllers.osc.routes_devices import DevicesRoutesMixin
from olc.controllers.osc.routes_faders import FadersRoutesMixin
from olc.controllers.osc.routes_keypad import KeypadRoutesMixin
from olc.controllers.osc.routes_patch import PatchRoutesMixin
from olc.controllers.osc.routes_playback import PlaybackRoutesMixin
from olc.controllers.osc.transport import make_method
from olc.devices.device import COLOR_CHANNEL_TYPES, ChannelType
from olc.show.sequence import get_cue

if typing.TYPE_CHECKING:
    from olc.controllers.osc import Osc
    from olc.core.app import CoreApplication


# pylint: disable=too-few-public-methods
class OSCDelegate(
    PlaybackRoutesMixin,
    KeypadRoutesMixin,
    FadersRoutesMixin,
    PatchRoutesMixin,
    ChannelsRoutesMixin,
    DevicesRoutesMixin,
):
    """OSC Delegate class for the headless Core Application.

    Maps legacy OSC routes directly to unified logic Actions.
    Completely decoupled from any graphical user interface libraries.
    """

    def __init__(self, app: CoreApplication, osc: Osc | None = None) -> None:
        self.app = app
        self._osc = osc
        self.channels_grid = ChannelsGridManager(app)
        self.app.subscribe("fader.page_changed", self._on_fader_page_changed)
        self.app.subscribe("fader.level_changed", self._on_fader_level_changed)
        self.app.subscribe("fader.flash_changed", self._on_fader_flash_changed)
        self.app.subscribe("fader.changed", self._on_fader_changed)
        self.app.subscribe("commandline.changed", self._on_commandline_changed)
        self.app.subscribe("commandline.error", self._on_commandline_error)
        self.app.subscribe("patch.changed", self._on_patch_changed)
        self.app.subscribe("channel.level_changed", self._on_channel_level_changed)
        self.app.subscribe(
            "channels.selected_changed", self._on_channels_selected_changed
        )
        self.app.subscribe(
            "device.parameters_changed", self._on_device_parameters_changed
        )
        self.app.subscribe("device.color_changed", self._on_device_color_changed)
        self.app.subscribe("playback.transition_progress", self._on_transition_progress)
        self.app.subscribe("playback.goback_progress", self._on_goback_progress)
        self.app.subscribe(
            "playback.transition_completed", self._on_transition_completed
        )
        self.app.subscribe("playback.goback_completed", self._on_transition_completed)
        self.app.subscribe("playback.go_triggered", self._on_playback_triggered)
        self.app.subscribe("playback.go_triggered_direct", self._on_playback_triggered)
        self.app.subscribe("playback.go_back_triggered", self._on_playback_triggered)
        self.app.subscribe("playback.goto_triggered", self._on_playback_triggered)
        self.app.subscribe("playback.step_changed", self._on_playback_triggered)
        self.app.subscribe(
            "playback.sequence_plus_triggered", self._on_playback_triggered
        )
        self.app.subscribe(
            "playback.sequence_minus_triggered", self._on_playback_triggered
        )
        self.app.subscribe("playback.pause_triggered", self._on_pause_triggered)
        self.app.subscribe(
            "main_fader.level_changed", self._on_main_fader_level_changed
        )
        self.app.subscribe("dmx.blackout_all_changed", self._on_blackout_changed)
        self.app.subscribe("show.loaded", self._on_show_changed)
        self.app.subscribe("show.new", self._on_show_changed)
        self.app.subscribe("cue.created", self._on_cues_changed)
        self.app.subscribe("cue.updated", self._on_cues_changed)
        self.app.subscribe("cue.deleted", self._on_cues_changed)
        self.app.subscribe("step.inserted", self._on_cues_changed)
        self.app.subscribe("step.updated", self._on_cues_changed)
        self.app.subscribe("step.deleted", self._on_cues_changed)
        self.app.subscribe(
            "independent.level_changed", self._on_independent_level_changed
        )
        self.app.subscribe(
            "independent.channels_changed", self._on_independent_channels_changed
        )
        self.app.subscribe(
            "independent.text_changed", self._on_independent_text_changed
        )
        self.app.subscribe("park.changed", self._on_park_changed)
        self.app.subscribe("playback.xfade_moved", self._on_xfade_moved)

    def _send_patch_status(
        self,
        status: str,
        command: str,
        message: str,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Send OSC status feedback for patch operations."""
        self._emit_osc(
            "patch",
            "/olc/patch/status",
            status,
            command,
            message,
            sender_addr=sender_addr,
        )

    @property
    def osc(self) -> Osc | None:
        """Return the attached Osc facade, falling back to app.osc."""
        if self._osc is not None:
            return self._osc
        return getattr(self.app, "osc", None)

    def _publish(self, topic: str, path: str, *args: object) -> None:
        """Publish an OSC message to subscribed clients if OSC is active."""
        osc = self.osc
        if osc is not None:
            osc.publish(topic, path, *args)

    def _send(self, path: str, *args: object) -> None:
        """Send an OSC message to the configured default client."""
        osc = self.osc
        if osc is not None:
            osc.send(path, *args)

    def _send_direct(
        self,
        sender_addr: tuple[str, int] | None,
        path: str,
        *args: object,
    ) -> None:
        """Send an OSC message directly to a requester address if present."""
        if sender_addr is None:
            return
        osc = self.osc
        if osc is not None:
            osc.send_direct(sender_addr[0], sender_addr[1], path, *args)

    def _emit_osc(
        self,
        topic: str,
        path: str,
        *args: object,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Send direct reply (if sender_addr given) and publish to topic."""
        self._send_direct(sender_addr, path, *args)
        self._publish(topic, path, *args)

    def _on_patch_changed(self) -> None:
        """Send OSC notification when the patch changes."""
        if self.osc is not None:
            self._send_channels_page()
            count = len(self.app.lightshow.patch.devices)
            self._publish("patch", "/olc/patch/changed", count)

    def _send_faders_page(self, sender_addr: tuple[str, int] | None = None) -> None:
        """Send active fader page and all fader labels and levels."""
        if self.osc is None:
            return
        fader_bank = self.app.lightshow.fader_bank
        page = fader_bank.active_page
        page_lbl = f"Page {page}"
        self._emit_osc("faders", "/olc/fader/page", page, sender_addr=sender_addr)
        self._emit_osc(
            "faders", "/olc/fader/page/label", page_lbl, sender_addr=sender_addr
        )
        for fader in fader_bank.iter_page_faders(page):
            lbl_path = f"/olc/fader/1/{fader.index}/label"
            lvl_path = f"/olc/fader/1/{fader.index}/level"
            lbl_txt = fader.text or f"Fader {fader.index}"
            lvl_val = float(fader.level)
            self._send_direct(sender_addr, lbl_path, lbl_txt)
            self._send_direct(sender_addr, lvl_path, lvl_val)
            self._publish("faders", lbl_path, fader.text)
            self._publish("faders", lvl_path, lvl_val)

    def _on_fader_page_changed(self, page: int) -> None:
        """Send OSC feedback when the active fader page changes."""
        if self.osc is not None:
            fader_bank = self.app.lightshow.fader_bank
            self._publish("faders", "/olc/fader/page", page)
            self._publish("faders", "/olc/fader/page/label", f"Page {page}")
            for fader in fader_bank.iter_page_faders(page):
                self._publish("faders", f"/olc/fader/1/{fader.index}/label", fader.text)
                self._publish(
                    "faders",
                    f"/olc/fader/1/{fader.index}/level",
                    float(fader.level),
                )

    def _on_fader_level_changed(self, fader_index: int, level: float) -> None:
        """Send OSC feedback when a fader level changes."""
        if self.osc is not None:
            self._send_channels_page()
            self._publish("faders", f"/olc/fader/1/{fader_index}/level", float(level))

    def _on_fader_flash_changed(self, fader_index: int, pressed: bool) -> None:
        """Refresh channel grid and publish flash state on fader flash change."""
        self._publish(
            "faders", f"/olc/fader/1/{fader_index}/flash", 1 if pressed else 0
        )
        self._send_channels_page()

    def _on_fader_changed(self, page: int, index: int) -> None:
        """Send OSC feedback when a fader label or assignment changes."""
        if self.osc is not None:
            fader_bank = self.app.lightshow.fader_bank
            if (
                page == fader_bank.active_page
                or fader_bank.resolve_page(fader_bank.active_page, index) == page
            ):
                fader = fader_bank.get_fader(index)
                self._publish("faders", f"/olc/fader/1/{index}/label", fader.text)
                self._publish(
                    "faders",
                    f"/olc/fader/1/{index}/level",
                    float(fader.level),
                )

    def _send_independents_telemetry(
        self, sender_addr: tuple[str, int] | None = None
    ) -> None:
        """Send telemetry for all 9 independents."""
        if self.osc is None:
            return
        independents = getattr(self.app.lightshow, "independents", None)
        if independents is None:
            return
        for inde in getattr(independents, "independents", []):
            num = int(inde.number)
            lvl = float(inde.level)
            lbl = str(inde.text or f"Inde {num}")
            type_str = str(getattr(inde, "inde_type", "knob"))
            self._emit_osc(
                "independents",
                f"/olc/independent/{num}/level",
                lvl,
                sender_addr=sender_addr,
            )
            self._emit_osc(
                "independents",
                f"/olc/independent/{num}/label",
                lbl,
                sender_addr=sender_addr,
            )
            self._emit_osc(
                "independents",
                f"/olc/independent/{num}/type",
                type_str,
                sender_addr=sender_addr,
            )

    def _on_independent_level_changed(self, number: int, level: float) -> None:
        """Send OSC feedback when an independent level changes."""
        if self.osc is not None:
            self._publish(
                "independents", f"/olc/independent/{number}/level", float(level)
            )
            self._send_channels_page()

    def _on_independent_text_changed(self, number: int, text: str) -> None:
        """Send OSC feedback when an independent label changes."""
        self._publish("independents", f"/olc/independent/{number}/label", str(text))

    def _on_independent_channels_changed(self, _number: int) -> None:
        """Refresh channel grid telemetry on independent channel change."""
        self._send_channels_page()

    def _on_xfade_moved(self, fader_key: str, val_255: int) -> None:
        """Publish manual crossfade slider position."""
        if self.osc is not None:
            norm_val = round(float(val_255) / 255.0, 4)
            self._publish("playback", f"/olc/playback/xfade/{fader_key}", norm_val)

    def _on_commandline_changed(self, keystring: str) -> None:
        """Send OSC feedback when the logical command line changes."""
        self._publish("commandline", "/olc/command_line", keystring)

    def _on_commandline_error(self, err_msg: str) -> None:
        """Send OSC status feedback when a command line error occurs."""
        self._publish("commandline", "/olc/cmd/status", str(err_msg))

    def _on_show_changed(self, *_args: object) -> None:
        """Synchronize all OSC telemetry when a show is created or loaded."""
        self.send_full_sync()

    def _on_cues_changed(self, *_args: object) -> None:
        """Refresh playback telemetry when cues or sequence steps are modified."""
        self._send_playback_telemetry()

    def _get_playback_telemetry(self) -> dict[str, typing.Any]:
        """Extract current playback cue and state information."""
        active_cue = 0.0
        active_text = ""
        next_cue = 0.0
        next_text = ""
        state = "idle"

        main_playback = getattr(self.app.lightshow, "main_playback", None)
        if main_playback is not None and hasattr(main_playback, "steps"):
            pos = getattr(main_playback, "position", 0)
            steps = main_playback.steps
            if 0 <= pos < len(steps):
                step = steps[pos]
                cue = get_cue(step)
                if cue is not None:
                    active_cue = float(cue.number)
                active_text = str(getattr(step, "text", ""))

            next_pos = pos + 1
            if 0 <= next_pos < len(steps):
                next_step = steps[next_pos]
                n_cue = get_cue(next_step)
                if n_cue is not None:
                    next_cue = float(n_cue.number)
                next_text = str(getattr(next_step, "text", ""))

            if getattr(main_playback, "on_go", False):
                thread = getattr(main_playback, "thread", None)
                if (
                    thread is not None
                    and hasattr(thread, "pause")
                    and not thread.pause.is_set()
                ):
                    state = "paused"
                else:
                    state = "running"
            else:
                state = "idle"

        return {
            "active_cue": active_cue,
            "active_text": active_text,
            "next_cue": next_cue,
            "next_text": next_text,
            "state": state,
        }

    def _get_cues_dump_json(self) -> str:
        """Export JSON dump of all cues in main playback."""
        main_playback = getattr(self.app.lightshow, "main_playback", None)
        cues_data: list[dict[str, typing.Any]] = []
        if main_playback is not None and hasattr(main_playback, "steps"):
            for idx, step in enumerate(main_playback.steps):
                cue = get_cue(step)
                if cue is not None:
                    cues_data.append(
                        {
                            "step": idx,
                            "cue": float(cue.number),
                            "text": str(getattr(step, "text", "")),
                            "time_in": float(getattr(step, "time_in", 5.0)),
                            "time_out": float(getattr(step, "time_out", 5.0)),
                            "delay_in": float(getattr(step, "delay_in", 0.0)),
                            "delay_out": float(getattr(step, "delay_out", 0.0)),
                            "wait": float(getattr(step, "wait", 0.0)),
                            "total_time": float(getattr(step, "total_time", 5.0)),
                        }
                    )
        return json_dumps(cues_data)

    def _send_playback_telemetry(
        self, sender_addr: tuple[str, int] | None = None
    ) -> None:
        """Send complete playback telemetry to subscribers and/or sender."""
        if self.osc is None:
            return

        telem = self._get_playback_telemetry()
        blackout = 1 if getattr(self.app, "blackout_active", False) else 0
        mf_level = float(getattr(self.app, "main_fader_level", 1.0))

        self._send_direct(sender_addr, "/olc/blackout", blackout)
        self._send_direct(sender_addr, "/olc/mainfader", mf_level)
        self._emit_osc(
            "playback",
            "/olc/playback/active/cue",
            telem["active_cue"],
            sender_addr=sender_addr,
        )
        self._emit_osc(
            "playback",
            "/olc/playback/active/text",
            telem["active_text"],
            sender_addr=sender_addr,
        )
        self._emit_osc(
            "playback",
            "/olc/playback/next/cue",
            telem["next_cue"],
            sender_addr=sender_addr,
        )
        self._emit_osc(
            "playback",
            "/olc/playback/next/text",
            telem["next_text"],
            sender_addr=sender_addr,
        )
        self._emit_osc(
            "playback", "/olc/playback/state", telem["state"], sender_addr=sender_addr
        )

    def _on_transition_progress(self, data: dict[str, typing.Any]) -> None:
        """Publish fade progress on /olc/playback/progress."""
        if self.osc is not None:
            total_time = float(data.get("total_time", 0.0))
            time_spent = float(data.get("time_spent", 0.0))
            if total_time > 0:
                ratio = min(1.0, max(0.0, time_spent / total_time))
            else:
                ratio = 1.0
            self._publish("playback", "/olc/playback/progress", float(ratio))

    def _on_goback_progress(self, data: dict[str, typing.Any]) -> None:
        """Publish goback progress on /olc/playback/progress."""
        if self.osc is not None:
            goback_time = float(data.get("goback_time", 0.0))
            time_spent = float(data.get("time_spent", 0.0))
            ratio = (
                min(1.0, max(0.0, time_spent / goback_time)) if goback_time > 0 else 1.0
            )
            self._publish("playback", "/olc/playback/progress", float(ratio))

    def _on_transition_completed(self, _data: dict[str, typing.Any]) -> None:
        """Publish completed progress and refresh telemetry."""
        if self.osc is not None:
            self._publish("playback", "/olc/playback/progress", 1.0)
            self._send_playback_telemetry()
            self._send_channels_page()
            self._publish("playback", "/olc/playback/progress", 0.0)

    def _on_playback_triggered(self, _data: object = None) -> None:
        """Publish updated telemetry when a playback action is triggered."""
        self._send_playback_telemetry()
        self._send_channels_page()

    def _on_pause_triggered(self, feedback: dict[str, typing.Any]) -> None:
        """Publish pause state change."""
        if self.osc is not None:
            is_paused = bool(feedback.get("active", False))
            state = "paused" if is_paused else "running"
            self._publish("playback", "/olc/playback/state", state)

    def _on_main_fader_level_changed(self, level: float) -> None:
        """Publish Main Fader level changes."""
        if self.osc is not None:
            self._publish("playback", "/olc/mainfader", float(level))
            self._send_channels_page()

    def _on_blackout_changed(self, state: bool) -> None:
        """Publish Blackout state changes."""
        if self.osc is not None:
            self._publish("playback", "/olc/blackout", 1 if state else 0)
            self._send_channels_page()

    def _on_park_changed(self, count: int) -> None:
        """Publish park active state changes."""
        if self.osc is not None:
            self._publish("park", "/olc/park/active", int(count))
            self._send_channels_page()

    def _on_channel_level_changed(self, channel: int, _level: int) -> None:
        """Publish updated cell level and color if channel is on current page."""
        if self.osc is None:
            return
        cell_idx = self.channels_grid.get_cell_for_channel(channel)
        norm_lvl = max(0.0, float(_level) / 255.0) if _level >= 0 else 0.0
        if cell_idx is not None:
            info = self.channels_grid.get_cell_info(cell_idx)
            self._send_cell_telemetry(info)
            norm_lvl = float(info["level"])

        self._publish("channels", f"/olc/channel/{channel}/level", norm_lvl)
        selected_channels = getattr(self.app, "selected_channels", [])
        if channel in selected_channels:
            self._publish("channels", "/olc/selected/intensity", norm_lvl)

    def _publish_color_components(
        self,
        r: float,
        g: float,
        b: float,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Publish RGB tuple, individual R/G/B channels, and Hue/Sat components."""
        if self.osc is None:
            return
        rf, gf, bf = float(r), float(g), float(b)
        hf, sf, _vf = colorsys.rgb_to_hsv(
            max(0.0, min(1.0, rf)),
            max(0.0, min(1.0, gf)),
            max(0.0, min(1.0, bf)),
        )
        self._emit_osc(
            "channels", "/olc/selected/color/rgb", rf, gf, bf, sender_addr=sender_addr
        )
        self._emit_osc("channels", "/olc/selected/color/r", rf, sender_addr=sender_addr)
        self._emit_osc("channels", "/olc/selected/color/g", gf, sender_addr=sender_addr)
        self._emit_osc("channels", "/olc/selected/color/b", bf, sender_addr=sender_addr)
        self._emit_osc(
            "channels", "/olc/selected/color/hue", float(hf), sender_addr=sender_addr
        )
        self._emit_osc(
            "channels", "/olc/selected/color/sat", float(sf), sender_addr=sender_addr
        )

    def _send_selected_fixture_telemetry(
        self,
        channels: list[int],
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Publish parameters and color of the last selected fixture."""
        if self.osc is None or not channels:
            return
        last_ch = channels[-1]
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
        if backend_dmx is not None and 1 <= last_ch <= 1024:
            try:
                comp_lvl, _ = backend_dmx.get_composite_level(last_ch - 1)
                mult = float(getattr(backend_dmx, "effective_intensity_mult", 1.0))
                int_norm = round(min(1.0, max(0.0, comp_lvl * mult)), 4)
                self._emit_osc(
                    "channels",
                    "/olc/selected/intensity",
                    float(int_norm),
                    sender_addr=sender_addr,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return
        dev = patch.devices.get(last_ch)
        if dev is None:
            return

        if dev.get_channel(ChannelType.PAN) is not None:
            pan_val = float(dev.pan_degrees)
            pan_norm = dev.get_parameter_normalized(ChannelType.PAN)
            self._emit_osc(
                "channels", "/olc/selected/pan", pan_val, sender_addr=sender_addr
            )
            if pan_norm is not None:
                self._emit_osc(
                    "channels",
                    "/olc/selected/pan/norm",
                    float(pan_norm),
                    sender_addr=sender_addr,
                )

        if dev.get_channel(ChannelType.TILT) is not None:
            tilt_val = float(dev.tilt_degrees)
            tilt_norm = dev.get_parameter_normalized(ChannelType.TILT)
            self._emit_osc(
                "channels", "/olc/selected/tilt", tilt_val, sender_addr=sender_addr
            )
            if tilt_norm is not None:
                self._emit_osc(
                    "channels",
                    "/olc/selected/tilt/norm",
                    float(tilt_norm),
                    sender_addr=sender_addr,
                )
        for ch_type, sub_path in (
            (ChannelType.ZOOM, "/olc/selected/zoom"),
            (ChannelType.FOCUS, "/olc/selected/focus"),
            (ChannelType.IRIS, "/olc/selected/iris"),
            (ChannelType.STROBE, "/olc/selected/strobe"),
            (ChannelType.FROST, "/olc/selected/frost"),
            (ChannelType.GOBO_WHEEL, "/olc/selected/gobo"),
            (ChannelType.PRISM, "/olc/selected/prism"),
        ):
            if dev.get_channel(ch_type) is not None:
                val = dev.get_parameter_normalized(ch_type)
                if val is not None:
                    f_val = float(val)
                    self._emit_osc("channels", sub_path, f_val, sender_addr=sender_addr)
        if dev.get_channel(ChannelType.COLOR_TEMP) is not None:
            kelvin_val = getattr(dev, "color_temp_kelvin", None)
            if kelvin_val is not None:
                kf = float(kelvin_val)
                self._emit_osc(
                    "channels",
                    "/olc/selected/color/kelvin",
                    kf,
                    sender_addr=sender_addr,
                )
        has_color = any(c.channel_type in COLOR_CHANNEL_TYPES for c in dev.channels)
        if has_color:
            srgb = dev.color_srgb
            self._publish_color_components(srgb.r, srgb.g, srgb.b, sender_addr)

    def _on_channels_selected_changed(self, channels: list[int]) -> None:
        """Publish updated selection states on visible cells and selected fixtures."""
        if self.osc is None:
            return

        for cell_idx in range(1, self.channels_grid.grid_size + 1):
            ch = self.channels_grid.get_channel_for_cell(cell_idx)
            is_sel = 1 if (ch is not None and ch in channels) else 0
            self._publish("channels", f"/olc/cell/{cell_idx}/selected", is_sel)

        self._send_selected_fixture_telemetry(channels)

    def _on_device_parameters_changed(self, channels: list[int]) -> None:
        """Publish updated coordinates when fixture parameters change."""
        self._send_selected_fixture_telemetry(channels)

    def _on_device_color_changed(
        self, _channels: list[int], color: tuple[float, float, float] | None
    ) -> None:
        """Publish updated color when fixture color changes."""
        if self.osc is None:
            return
        if color is not None:
            self._publish_color_components(color[0], color[1], color[2])
        elif _channels:
            self._send_selected_fixture_telemetry(_channels)

    def _send_cell_telemetry(
        self, info: dict[str, typing.Any], sender_addr: tuple[str, int] | None = None
    ) -> None:
        """Send individual cell telemetry."""
        if self.osc is None:
            return
        cell_idx = info["cell"]
        prefix = f"/olc/cell/{cell_idx}"

        messages = [
            (f"{prefix}/channel", info["channel"]),
            (f"{prefix}/level", float(info["level"])),
            (f"{prefix}/label", str(info["label"])),
            (f"{prefix}/selected", int(info["selected"])),
            (f"{prefix}/color", str(info["color"])),
        ]
        for addr, val in messages:
            self._emit_osc("channels", addr, val, sender_addr=sender_addr)

    def _send_channels_page(self, sender_addr: tuple[str, int] | None = None) -> None:
        """Send full channels page info and all cell states."""
        if self.osc is None:
            return

        page_info = self.channels_grid.page_info
        cur_p, tot_p, start_ch, end_ch = page_info
        page_lbl = f"Page {cur_p}/{tot_p} (Ch {start_ch}-{end_ch})"
        self._emit_osc(
            "channels",
            "/olc/channels/page/info",
            *page_info,
            sender_addr=sender_addr,
        )
        self._emit_osc(
            "channels",
            "/olc/channels/page/label",
            page_lbl,
            sender_addr=sender_addr,
        )

        for cell_idx in range(1, self.channels_grid.grid_size + 1):
            info = self.channels_grid.get_cell_info(cell_idx)
            self._send_cell_telemetry(info, sender_addr)

    def send_full_sync(self, sender_addr: tuple[str, int] | None = None) -> None:
        """Send full state synchronization for all OSC topics."""
        if self.osc is None:
            return
        self._send_playback_telemetry(sender_addr)
        self._send_channels_page(sender_addr)
        self._send_faders_page(sender_addr)
        self._send_independents_telemetry(sender_addr)
        selected = getattr(self.app, "selected_channels", [])
        if selected:
            self._send_selected_fixture_telemetry(selected, sender_addr)
        cmd_str = self.app.commandline.get_string()
        self._emit_osc(
            "commandline", "/olc/command_line", cmd_str, sender_addr=sender_addr
        )
        self._emit_osc("commandline", "/olc/cmd/status", "OK", sender_addr=sender_addr)

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
        osc = self.osc
        if osc is None:
            return

        valid_topics = (
            "patch",
            "faders",
            "playback",
            "channels",
            "commandline",
            "all",
        )
        if (
            args
            and isinstance(args[0], str)
            and args[0].strip().lower() in valid_topics
        ):
            topic = args[0].strip().lower()
        else:
            topic = "all"

        host = sender_addr[0] if sender_addr else "127.0.0.1"
        port = sender_addr[1] if sender_addr else 8000

        if len(args) >= 2:
            try:
                port = int(args[1])
            except (ValueError, TypeError):
                pass
        elif args and not isinstance(args[0], str):
            osc_cli = osc.client
            if osc_cli is not None:
                port = int(osc_cli.target[1])

        osc.subscriptions.subscribe(host, port, topic)
        self._send_direct((host, port), "/olc/subscribe/status", "OK", topic)
        self.app.emit(
            "osc.subscribers_changed",
            osc.subscriptions.get_subscribers_snapshot(),
        )

        target_addr = (host, port) if sender_addr is not None else None

        if topic in ("patch", "all"):
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
            self._send_direct((host, port), "/olc/patch/dump", json_dumps(dump_data))

        if topic in ("playback", "all"):
            self._send_playback_telemetry(target_addr)
            dump_json = self._get_cues_dump_json()
            self._send_direct(target_addr, "/olc/playback/dump", dump_json)

        if topic in ("channels", "all"):
            self._send_channels_page(target_addr)
            selected = getattr(self.app, "selected_channels", [])
            if selected:
                self._send_selected_fixture_telemetry(selected, target_addr)

        if topic in ("faders", "all"):
            self._send_faders_page(target_addr)

        if topic in ("commandline", "all"):
            cmd_str = self.app.commandline.get_string()
            self._emit_osc(
                "commandline",
                "/olc/command_line",
                cmd_str,
                sender_addr=target_addr,
            )

    @make_method("/olc/unsubscribe")
    def _unsubscribe(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Unsubscribe a client from an OSC topic."""
        osc = self.osc
        if osc is None:
            return

        topic = str(args[0]).strip().lower() if args else "all"
        host = sender_addr[0] if sender_addr else "127.0.0.1"
        port = sender_addr[1] if sender_addr else 8000

        if len(args) >= 2:
            try:
                port = int(args[1])
            except (ValueError, TypeError):
                pass

        osc.subscriptions.unsubscribe(host, port, topic)
        self._send_direct((host, port), "/olc/subscribe/status", "OK", "unsubscribed")
        self.app.emit(
            "osc.subscribers_changed",
            osc.subscriptions.get_subscribers_snapshot(),
        )

    @make_method("/olc/ping")
    @make_method("/ping")
    def _ping(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Handle keepalive ping from an OSC client."""
        osc = self.osc
        if osc is None or sender_addr is None:
            return

        host, port = sender_addr
        osc.subscriptions.refresh_keepalive(host, port)
        token = args[0] if args else 0
        self._send_direct((host, port), "/olc/pong", token)

    @make_method("/olc/command_line")
    def _commandline(self, _address: str, _args: list) -> None:
        if self.osc is not None:
            self._publish(
                "commandline",
                "/olc/command_line",
                self.app.commandline.get_string(),
            )

    @make_method("/olc/cmd")
    def _cmd(self, _address: str, args: list) -> None:
        """Execute a full command line string received via OSC.

        Strips any optional trailing ENTER keyword and triggers execution.
        Sends execution status feedback back on /olc/cmd/status if OSC is running.

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

        if self.osc is not None and hasattr(result, "success") and result.success:
            self._publish("commandline", "/olc/cmd/status", "OK")

    def _execute_action(self, name: str, *args: object, **kwargs: object) -> object:
        """Execute an action from the registry.

        Args:
            name: The action name.
            *args: Arguments for the action.
            **kwargs: Keyword arguments for the action.

        Returns:
            The return value of the action.
        """
        return self.app.action_registry.execute(name, *args, **kwargs)

    @staticmethod
    def _is_momentary_press(args: list) -> bool:
        """Return True if a momentary key/button OSC payload represents a press."""
        return not args or parse_osc_bool(args[0])

    @make_method(None)
    def _fallback(self, address: str, args: list) -> None:
        print(f"[OSC Delegate] Unknown message: {address} with args {args}")
