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

from olc.core.backends.osc.channels_grid import ChannelsGridManager
from olc.core.backends.osc.parser import parse_osc_bool, parse_osc_normalized
from olc.core.osc import make_method
from olc.core.selection import SelectAddAction, SelectRemoveAction
from olc.define import MAX_FADER_PAGE
from olc.devices.builtin import create_dimmer_definition
from olc.devices.color_pick import KELVIN_MAX, KELVIN_MIN, kelvin_to_srgb
from olc.devices.device import COLOR_CHANNEL_TYPES, ChannelType
from olc.sequence import get_cue

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
        self.app.subscribe("playback.xfade_moved", self._on_xfade_moved)

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
            self._send_channels_page()
            count = len(self.app.lightshow.patch.devices)
            self.app.engine.publish_osc("patch", "/olc/patch/changed", count)

    def _send_faders_page(self, sender_addr: tuple[str, int] | None = None) -> None:
        """Send active fader page and all fader labels and levels."""
        if self.app.engine is None:
            return
        fader_bank = self.app.lightshow.fader_bank
        page = fader_bank.active_page
        page_lbl = f"Page {page}"
        if sender_addr is not None:
            host, port = sender_addr
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/fader/page", page
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/fader/page/label", page_lbl
            )
        self.app.engine.publish_osc("faders", "/olc/fader/page", page)
        self.app.engine.publish_osc("faders", "/olc/fader/page/label", page_lbl)
        for fader in fader_bank.faders[page].values():
            lbl_path = f"/olc/fader/1/{fader.index}/label"
            lvl_path = f"/olc/fader/1/{fader.index}/level"
            lbl_txt = fader.text or f"Fader {fader.index}"
            lvl_val = float(fader.level)
            if sender_addr is not None:
                host, port = sender_addr
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, lbl_path, lbl_txt
                )
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, lvl_path, lvl_val
                )
            self.app.engine.publish_osc("faders", lbl_path, fader.text)
            self.app.engine.publish_osc("faders", lvl_path, lvl_val)

    def _on_fader_page_changed(self, page: int) -> None:
        """Send OSC feedback when the active fader page changes."""
        if self.app.engine is not None:
            fader_bank = self.app.lightshow.fader_bank
            self.app.engine.publish_osc("faders", "/olc/fader/page", page)
            self.app.engine.publish_osc(
                "faders", "/olc/fader/page/label", f"Page {page}"
            )
            for fader in fader_bank.faders[page].values():
                self.app.engine.publish_osc(
                    "faders", f"/olc/fader/1/{fader.index}/label", fader.text
                )
                self.app.engine.publish_osc(
                    "faders",
                    f"/olc/fader/1/{fader.index}/level",
                    float(fader.level),
                )

    def _on_fader_level_changed(self, fader_index: int, level: float) -> None:
        """Send OSC feedback when a fader level changes."""
        if self.app.engine is not None:
            self._send_channels_page()
            self.app.engine.publish_osc(
                "faders", f"/olc/fader/1/{fader_index}/level", float(level)
            )

    def _on_fader_flash_changed(self, fader_index: int, pressed: bool) -> None:
        """Refresh channel grid and publish flash state on fader flash change."""
        if self.app.engine is not None:
            self.app.engine.publish_osc(
                "faders", f"/olc/fader/1/{fader_index}/flash", 1 if pressed else 0
            )
        self._send_channels_page()

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
                    float(fader.level),
                )

    def _send_independents_telemetry(
        self, sender_addr: tuple[str, int] | None = None
    ) -> None:
        """Send telemetry for all 9 independents."""
        if self.app.engine is None:
            return
        independents = getattr(self.app.lightshow, "independents", None)
        if independents is None:
            return
        for inde in getattr(independents, "independents", []):
            num = int(inde.number)
            lvl = float(inde.level)
            lbl = str(inde.text or f"Inde {num}")
            type_str = str(getattr(inde, "inde_type", "knob"))
            if sender_addr is not None:
                host, port = sender_addr
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, f"/olc/independent/{num}/level", lvl
                )
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, f"/olc/independent/{num}/label", lbl
                )
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, f"/olc/independent/{num}/type", type_str
                )
            self.app.engine.publish_osc(
                "independents", f"/olc/independent/{num}/level", lvl
            )
            self.app.engine.publish_osc(
                "independents", f"/olc/independent/{num}/label", lbl
            )
            self.app.engine.publish_osc(
                "independents", f"/olc/independent/{num}/type", type_str
            )

    def _on_independent_level_changed(self, number: int, level: float) -> None:
        """Send OSC feedback when an independent level changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc(
                "independents", f"/olc/independent/{number}/level", float(level)
            )
            self._send_channels_page()

    def _on_independent_text_changed(self, number: int, text: str) -> None:
        """Send OSC feedback when an independent label changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc(
                "independents", f"/olc/independent/{number}/label", str(text)
            )

    def _on_independent_channels_changed(self, _number: int) -> None:
        """Refresh channel grid telemetry on independent channel change."""
        self._send_channels_page()

    def _on_xfade_moved(self, fader_key: str, val_255: int) -> None:
        """Publish manual crossfade slider position."""
        if self.app.engine is not None:
            norm_val = round(float(val_255) / 255.0, 4)
            self.app.engine.publish_osc(
                "playback", f"/olc/playback/xfade/{fader_key}", norm_val
            )

    def _on_commandline_changed(self, keystring: str) -> None:
        """Send OSC feedback when the logical command line changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc("commandline", "/olc/command_line", keystring)

    def _on_commandline_error(self, err_msg: str) -> None:
        """Send OSC status feedback when a command line error occurs."""
        if self.app.engine is not None:
            self.app.engine.publish_osc("commandline", "/olc/cmd/status", str(err_msg))

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
        if self.app.engine is None:
            return

        telem = self._get_playback_telemetry()
        blackout = 1 if getattr(self.app, "blackout_active", False) else 0
        mf_level = float(getattr(self.app, "main_fader_level", 1.0))

        if sender_addr is not None:
            host, port = sender_addr
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/playback/active/cue", telem["active_cue"]
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/playback/active/text", telem["active_text"]
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/playback/next/cue", telem["next_cue"]
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/playback/next/text", telem["next_text"]
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/playback/state", telem["state"]
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/blackout", blackout
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/mainfader", mf_level
            )

        self.app.engine.publish_osc(
            "playback", "/olc/playback/active/cue", telem["active_cue"]
        )
        self.app.engine.publish_osc(
            "playback", "/olc/playback/active/text", telem["active_text"]
        )
        self.app.engine.publish_osc(
            "playback", "/olc/playback/next/cue", telem["next_cue"]
        )
        self.app.engine.publish_osc(
            "playback", "/olc/playback/next/text", telem["next_text"]
        )
        self.app.engine.publish_osc("playback", "/olc/playback/state", telem["state"])

    def _on_transition_progress(self, data: dict[str, typing.Any]) -> None:
        """Publish fade progress on /olc/playback/progress."""
        if self.app.engine is not None:
            total_time = float(data.get("total_time", 0.0))
            time_spent = float(data.get("time_spent", 0.0))
            if total_time > 0:
                ratio = min(1.0, max(0.0, time_spent / total_time))
            else:
                ratio = 1.0
            self.app.engine.publish_osc(
                "playback", "/olc/playback/progress", float(ratio)
            )

    def _on_goback_progress(self, data: dict[str, typing.Any]) -> None:
        """Publish goback progress on /olc/playback/progress."""
        if self.app.engine is not None:
            goback_time = float(data.get("goback_time", 0.0))
            time_spent = float(data.get("time_spent", 0.0))
            ratio = (
                min(1.0, max(0.0, time_spent / goback_time)) if goback_time > 0 else 1.0
            )
            self.app.engine.publish_osc(
                "playback", "/olc/playback/progress", float(ratio)
            )

    def _on_transition_completed(self, _data: dict[str, typing.Any]) -> None:
        """Publish completed progress and refresh telemetry."""
        if self.app.engine is not None:
            self.app.engine.publish_osc("playback", "/olc/playback/progress", 1.0)
            self._send_playback_telemetry()
            self._send_channels_page()
            self.app.engine.publish_osc("playback", "/olc/playback/progress", 0.0)

    def _on_playback_triggered(self, _data: object = None) -> None:
        """Publish updated telemetry when a playback action is triggered."""
        self._send_playback_telemetry()
        self._send_channels_page()

    def _on_pause_triggered(self, feedback: dict[str, typing.Any]) -> None:
        """Publish pause state change."""
        if self.app.engine is not None:
            is_paused = bool(feedback.get("active", False))
            state = "paused" if is_paused else "running"
            self.app.engine.publish_osc("playback", "/olc/playback/state", state)

    def _on_main_fader_level_changed(self, level: float) -> None:
        """Publish Main Fader level changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc("playback", "/olc/mainfader", float(level))
            self._send_channels_page()

    def _on_blackout_changed(self, state: bool) -> None:
        """Publish Blackout state changes."""
        if self.app.engine is not None:
            self.app.engine.publish_osc("playback", "/olc/blackout", 1 if state else 0)
            self._send_channels_page()

    def _on_channel_level_changed(self, channel: int, _level: int) -> None:
        """Publish updated cell level and color if channel is on current page."""
        if self.app.engine is None:
            return
        cell_idx = self.channels_grid.get_cell_for_channel(channel)
        norm_lvl = max(0.0, float(_level) / 255.0) if _level >= 0 else 0.0
        if cell_idx is not None:
            info = self.channels_grid.get_cell_info(cell_idx)
            self._send_cell_telemetry(info)
            norm_lvl = float(info["level"])

        self.app.engine.publish_osc(
            "channels", f"/olc/channel/{channel}/level", norm_lvl
        )
        selected_channels = getattr(self.app, "selected_channels", [])
        if channel in selected_channels:
            self.app.engine.publish_osc("channels", "/olc/selected/intensity", norm_lvl)

    def _publish_color_components(
        self,
        r: float,
        g: float,
        b: float,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Publish RGB tuple, individual R/G/B channels, and Hue/Sat components."""
        if self.app.engine is None:
            return
        rf, gf, bf = float(r), float(g), float(b)
        hf, sf, _vf = colorsys.rgb_to_hsv(
            max(0.0, min(1.0, rf)),
            max(0.0, min(1.0, gf)),
            max(0.0, min(1.0, bf)),
        )
        if sender_addr is not None:
            host, port = sender_addr
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/selected/color/rgb", rf, gf, bf
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/selected/color/r", rf
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/selected/color/g", gf
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/selected/color/b", bf
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/selected/color/hue", float(hf)
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/selected/color/sat", float(sf)
            )
        self.app.engine.publish_osc("channels", "/olc/selected/color/rgb", rf, gf, bf)
        self.app.engine.publish_osc("channels", "/olc/selected/color/r", rf)
        self.app.engine.publish_osc("channels", "/olc/selected/color/g", gf)
        self.app.engine.publish_osc("channels", "/olc/selected/color/b", bf)
        self.app.engine.publish_osc("channels", "/olc/selected/color/hue", float(hf))
        self.app.engine.publish_osc("channels", "/olc/selected/color/sat", float(sf))

    def _send_selected_fixture_telemetry(
        self,
        channels: list[int],
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Publish parameters and color of the last selected fixture."""
        if self.app.engine is None or not channels:
            return
        last_ch = channels[-1]
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
        if backend_dmx is not None and 1 <= last_ch <= 1024:
            try:
                comp_lvl, _ = backend_dmx.get_composite_level(last_ch - 1)
                mult = float(getattr(backend_dmx, "effective_intensity_mult", 1.0))
                int_norm = round(min(255.0, max(0.0, comp_lvl * mult)) / 255.0, 3)
                if sender_addr is not None:
                    self.app.engine.osc_subscriptions.send_direct(
                        sender_addr[0],
                        sender_addr[1],
                        "/olc/selected/intensity",
                        float(int_norm),
                    )
                self.app.engine.publish_osc(
                    "channels", "/olc/selected/intensity", float(int_norm)
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
            if sender_addr is not None:
                self.app.engine.osc_subscriptions.send_direct(
                    sender_addr[0], sender_addr[1], "/olc/selected/pan", pan_val
                )
                if pan_norm is not None:
                    self.app.engine.osc_subscriptions.send_direct(
                        sender_addr[0],
                        sender_addr[1],
                        "/olc/selected/pan/norm",
                        float(pan_norm),
                    )
            self.app.engine.publish_osc("channels", "/olc/selected/pan", pan_val)
            if pan_norm is not None:
                self.app.engine.publish_osc(
                    "channels", "/olc/selected/pan/norm", float(pan_norm)
                )

        if dev.get_channel(ChannelType.TILT) is not None:
            tilt_val = float(dev.tilt_degrees)
            tilt_norm = dev.get_parameter_normalized(ChannelType.TILT)
            if sender_addr is not None:
                self.app.engine.osc_subscriptions.send_direct(
                    sender_addr[0], sender_addr[1], "/olc/selected/tilt", tilt_val
                )
                if tilt_norm is not None:
                    self.app.engine.osc_subscriptions.send_direct(
                        sender_addr[0],
                        sender_addr[1],
                        "/olc/selected/tilt/norm",
                        float(tilt_norm),
                    )
            self.app.engine.publish_osc("channels", "/olc/selected/tilt", tilt_val)
            if tilt_norm is not None:
                self.app.engine.publish_osc(
                    "channels", "/olc/selected/tilt/norm", float(tilt_norm)
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
                    if sender_addr is not None:
                        self.app.engine.osc_subscriptions.send_direct(
                            sender_addr[0], sender_addr[1], sub_path, f_val
                        )
                    self.app.engine.publish_osc("channels", sub_path, f_val)
        if dev.get_channel(ChannelType.COLOR_TEMP) is not None:
            kelvin_val = getattr(dev, "color_temp_kelvin", None)
            if kelvin_val is not None:
                kf = float(kelvin_val)
                if sender_addr is not None:
                    self.app.engine.osc_subscriptions.send_direct(
                        sender_addr[0],
                        sender_addr[1],
                        "/olc/selected/color/kelvin",
                        kf,
                    )
                self.app.engine.publish_osc(
                    "channels", "/olc/selected/color/kelvin", kf
                )
        has_color = any(c.channel_type in COLOR_CHANNEL_TYPES for c in dev.channels)
        if has_color:
            srgb = dev.color_srgb
            self._publish_color_components(srgb.r, srgb.g, srgb.b, sender_addr)

    def _on_channels_selected_changed(self, channels: list[int]) -> None:
        """Publish updated selection states on visible cells and selected fixtures."""
        if self.app.engine is None:
            return

        for cell_idx in range(1, self.channels_grid.grid_size + 1):
            ch = self.channels_grid.get_channel_for_cell(cell_idx)
            is_sel = 1 if (ch is not None and ch in channels) else 0
            self.app.engine.publish_osc(
                "channels", f"/olc/cell/{cell_idx}/selected", is_sel
            )

        self._send_selected_fixture_telemetry(channels)

    def _on_device_parameters_changed(self, channels: list[int]) -> None:
        """Publish updated coordinates when fixture parameters change."""
        self._send_selected_fixture_telemetry(channels)

    def _on_device_color_changed(
        self, _channels: list[int], color: tuple[float, float, float] | None
    ) -> None:
        """Publish updated color when fixture color changes."""
        if self.app.engine is None:
            return
        if color is not None:
            self._publish_color_components(color[0], color[1], color[2])
        elif _channels:
            self._send_selected_fixture_telemetry(_channels)

    def _send_cell_telemetry(
        self, info: dict[str, typing.Any], sender_addr: tuple[str, int] | None = None
    ) -> None:
        """Send individual cell telemetry."""
        if self.app.engine is None:
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
            if sender_addr is not None:
                self.app.engine.osc_subscriptions.send_direct(
                    sender_addr[0], sender_addr[1], addr, val
                )
            self.app.engine.publish_osc("channels", addr, val)

    def _send_channels_page(self, sender_addr: tuple[str, int] | None = None) -> None:
        """Send full channels page info and all cell states."""
        if self.app.engine is None:
            return

        page_info = self.channels_grid.page_info
        cur_p, tot_p, start_ch, end_ch = page_info
        page_lbl = f"Page {cur_p}/{tot_p} (Ch {start_ch}-{end_ch})"
        if sender_addr is not None:
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/channels/page/info", *page_info
            )
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/channels/page/label", page_lbl
            )
        self.app.engine.publish_osc("channels", "/olc/channels/page/info", *page_info)
        self.app.engine.publish_osc("channels", "/olc/channels/page/label", page_lbl)

        for cell_idx in range(1, self.channels_grid.grid_size + 1):
            info = self.channels_grid.get_cell_info(cell_idx)
            self._send_cell_telemetry(info, sender_addr)

    def send_full_sync(self, sender_addr: tuple[str, int] | None = None) -> None:
        """Send full state synchronization for all OSC topics."""
        if self.app.engine is None:
            return
        self._send_playback_telemetry(sender_addr)
        self._send_channels_page(sender_addr)
        self._send_faders_page(sender_addr)
        self._send_independents_telemetry(sender_addr)
        selected = getattr(self.app, "selected_channels", [])
        if selected:
            self._send_selected_fixture_telemetry(selected, sender_addr)
        cmd_str = self.app.commandline.get_string()
        if sender_addr is not None:
            host, port = sender_addr
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/command_line", cmd_str
            )
            self.app.engine.osc_subscriptions.send_direct(
                host, port, "/olc/cmd/status", "OK"
            )
        self.app.engine.publish_osc("commandline", "/olc/command_line", cmd_str)
        self.app.engine.publish_osc("commandline", "/olc/cmd/status", "OK")

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
            osc_cli = getattr(self.app.engine, "osc_client", None)
            if osc_cli is not None and hasattr(osc_cli, "_addr"):
                port = int(osc_cli._addr[1])

        self.app.engine.osc_subscriptions.subscribe(host, port, topic)
        self.app.engine.osc_subscriptions.send_direct(
            host, port, "/olc/subscribe/status", "OK", topic
        )
        self.app.emit(
            "osc.subscribers_changed",
            self.app.engine.osc_subscriptions.get_subscribers_snapshot(),
        )

        target_addr = (host, port) if sender_addr is not None else None

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

        if topic in ("playback", "all"):
            self._send_playback_telemetry(target_addr)
            dump_json = self._get_cues_dump_json()
            if target_addr is not None:
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, "/olc/playback/dump", dump_json
                )

        if topic in ("channels", "all"):
            self._send_channels_page(target_addr)
            selected = getattr(self.app, "selected_channels", [])
            if selected:
                self._send_selected_fixture_telemetry(selected, target_addr)

        if topic in ("faders", "all"):
            self._send_faders_page(target_addr)

        if topic in ("commandline", "all"):
            cmd_str = self.app.commandline.get_string()
            if target_addr is not None:
                self.app.engine.osc_subscriptions.send_direct(
                    host, port, "/olc/command_line", cmd_str
                )
            self.app.engine.publish_osc("commandline", "/olc/command_line", cmd_str)

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
    @make_method("/ping")
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

        if (
            self.app.engine is not None
            and hasattr(result, "success")
            and result.success
        ):
            self.app.engine.publish_osc("commandline", "/olc/cmd/status", "OK")

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
        if self.app.engine is not None and sender_addr is not None:
            telem = self._get_playback_telemetry()
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0],
                sender_addr[1],
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
        if self.app.engine is not None and sender_addr is not None:
            telem = self._get_playback_telemetry()
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0],
                sender_addr[1],
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
        if self.app.engine is not None and sender_addr is not None:
            telem = self._get_playback_telemetry()
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0],
                sender_addr[1],
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
        if self.app.engine is None:
            return
        dump_json = self._get_cues_dump_json()
        if sender_addr is not None:
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/playback/dump", dump_json
            )
        self.app.engine.publish_osc("playback", "/olc/playback/dump", dump_json)

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
        elif self.app.engine is not None and sender_addr is not None:
            lvl = float(getattr(self.app, "main_fader_level", 1.0))
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/mainfader", lvl
            )

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

        if self.app.engine is not None and sender_addr is not None:
            curr_state = 1 if getattr(self.app, "blackout_active", False) else 0
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/blackout", curr_state
            )

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

    @make_method("/olc/key/enter")
    def _enter(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.execute")

    @make_method("/olc/key/backspace")
    def _backspace(self, _address: str, args: list) -> None:
        if self._is_momentary_press(args):
            self._execute_action("commandline.backspace")

    @make_method("/olc/fader/pageupdate")
    @make_method("/olc/sync")
    def _sub_launch(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
        fader_bank = self.app.lightshow.fader_bank
        if self.app.engine is not None:
            self.app.engine.send_osc("/olc/fader/page", fader_bank.active_page)
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self.app.engine.send_osc(
                    f"/olc/fader/1/{fader.index}/label", fader.text
                )
            self.send_full_sync()

    @make_method("/olc/fader/page+")
    def _fader_page_plus(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
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
    def _fader_page_minus(self, _address: str, args: list) -> None:
        if not self._is_momentary_press(args):
            return
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
            level = parse_osc_normalized(args[0]) if args else 0.0

            fader_bank = self.app.lightshow.fader_bank
            if self.app is not None and hasattr(self.app, "action_registry"):
                self.app.action_registry.execute(
                    "fader.set_level", fader_bank.active_page, fader_index, level
                )
            else:
                fader = fader_bank.get_fader(fader_index)
                fader.set_level(level)
                self.app.emit("fader.level_changed", fader_index, level)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"[OSC Delegate] Error in fader_level: {err}")

    @make_method("/olc/fader/1/*/flash")
    def _fader_flash(self, address: str, args: list) -> None:
        try:
            pressed = parse_osc_bool(args[0]) if args else True
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
        if self.app.engine is None or sender_addr is None:
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
        self.app.engine.osc_subscriptions.send_direct(
            sender_addr[0], sender_addr[1], "/olc/independent/dump", json_dumps(data)
        )

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

    @make_method("/olc/channels/subscribe")
    def _channels_subscribe(
        self,
        _address: str,
        args: list,
        sender_addr: tuple[str, int] | None = None,
    ) -> None:
        """Subscribe to channels topic with custom grid size and start channel."""
        if self.app.engine is None:
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
        self.app.engine.osc_subscriptions.subscribe(host, port, "channels")
        self.app.engine.osc_subscriptions.send_direct(
            host, port, "/olc/subscribe/status", "OK", "channels"
        )
        self.app.emit(
            "osc.subscribers_changed",
            self.app.engine.osc_subscriptions.get_subscribers_snapshot(),
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
        if self.app.engine is None:
            return
        dump_json = self.channels_grid.get_page_snapshot_json()
        if sender_addr is not None:
            self.app.engine.osc_subscriptions.send_direct(
                sender_addr[0], sender_addr[1], "/olc/channels/dump", dump_json
            )
        self.app.engine.publish_osc("channels", "/olc/channels/dump", dump_json)

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
            selected = getattr(self.app, "selected_channels", [])
            if ch in selected:
                self.app.live_selection.execute_action(SelectRemoveAction, ch)
            else:
                self.app.live_selection.execute_action(SelectAddAction, ch)

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

        selected = getattr(self.app, "selected_channels", [])
        if ch in selected:
            self.app.live_selection.execute_action(SelectRemoveAction, ch)
        else:
            self.app.live_selection.execute_action(SelectAddAction, ch)

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

    @make_method("/olc/wheel/intensity")
    def _wheel_intensity(self, _address: str, args: list) -> None:
        """Adjust selected channels level relatively with encoder wheel."""
        delta = float(args[0]) if args else 1.0
        step = round(abs(delta))
        direction = 1 if delta >= 0 else -1
        self._execute_action("channel.wheel_adjust", step, direction)

    @make_method("/olc/wheel/pan")
    def _wheel_pan(self, _address: str, args: list) -> None:
        """Adjust selected fixtures pan relatively in degrees."""
        delta = float(args[0]) if args else 1.0
        self._execute_action("device.adjust_pan_tilt", delta, 0.0)

    @make_method("/olc/wheel/tilt")
    def _wheel_tilt(self, _address: str, args: list) -> None:
        """Adjust selected fixtures tilt relatively in degrees."""
        delta = float(args[0]) if args else 1.0
        self._execute_action("device.adjust_pan_tilt", 0.0, delta)

    @make_method("/olc/wheel/zoom")
    def _wheel_zoom(self, _address: str, args: list) -> None:
        """Adjust selected fixtures zoom relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "zoom", delta)

    @make_method("/olc/wheel/focus")
    def _wheel_focus(self, _address: str, args: list) -> None:
        """Adjust selected fixtures focus relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "focus", delta)

    @make_method("/olc/wheel/iris")
    def _wheel_iris(self, _address: str, args: list) -> None:
        """Adjust selected fixtures iris relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "iris", delta)

    @make_method("/olc/wheel/strobe")
    def _wheel_strobe(self, _address: str, args: list) -> None:
        """Adjust selected fixtures strobe relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "strobe", delta)

    @make_method("/olc/wheel/frost")
    def _wheel_frost(self, _address: str, args: list) -> None:
        """Adjust selected fixtures frost filter relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "frost", delta)

    @make_method("/olc/wheel/gobo")
    def _wheel_gobo(self, _address: str, args: list) -> None:
        """Adjust selected fixtures gobo wheel relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "gobo_wheel", delta)

    @make_method("/olc/wheel/prism")
    def _wheel_prism(self, _address: str, args: list) -> None:
        """Adjust selected fixtures prism relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "prism", delta)

    @make_method("/olc/wheel/cct")
    @make_method("/olc/wheel/kelvin")
    def _wheel_kelvin(self, _address: str, args: list) -> None:
        """Adjust selected fixtures color temperature relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "color_temp", delta)

    @make_method("/olc/wheel/param/*")
    def _wheel_param_generic(self, address: str, args: list) -> None:
        """Adjust selected fixtures generic parameter relatively."""
        parts = address.split("/")
        if len(parts) >= 5:
            param_name = parts[4]
            delta = float(args[0]) if args else 0.05
            self._execute_action("device.adjust_parameter", param_name, delta)

    @make_method("/olc/selected/intensity")
    def _selected_intensity(self, _address: str, args: list) -> None:
        """Set normalized intensity [0.0..1.0] on all selected channels."""
        if not args:
            return
        norm_level = parse_osc_normalized(args[0])
        for ch in list(getattr(self.app, "selected_channels", [])):
            self._execute_action("channel.set_level", ch, norm_level)

    @make_method("/olc/selected/pan")
    def _selected_pan(self, _address: str, args: list) -> None:
        """Set absolute pan coordinate in degrees on selected fixtures."""
        if args:
            val = float(args[0])
            self._execute_action("device.set_pan_tilt", val, None)

    @make_method("/olc/selected/pan/norm")
    def _selected_pan_norm(self, _address: str, args: list) -> None:
        """Set normalized pan [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "pan", norm)

    @make_method("/olc/selected/tilt")
    def _selected_tilt(self, _address: str, args: list) -> None:
        """Set absolute tilt coordinate in degrees on selected fixtures."""
        if args:
            val = float(args[0])
            self._execute_action("device.set_pan_tilt", None, val)

    @make_method("/olc/selected/tilt/norm")
    def _selected_tilt_norm(self, _address: str, args: list) -> None:
        """Set normalized tilt [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "tilt", norm)

    def _get_selected_srgb(self) -> tuple[float, float, float]:
        """Return current (r, g, b) of the last selected fixture or (1, 1, 1)."""
        selected = getattr(self.app, "selected_channels", [])
        patch = getattr(self.app.lightshow, "patch", None)
        if selected and patch is not None:
            dev = patch.devices.get(selected[-1])
            if dev is not None:
                srgb = getattr(dev, "color_srgb", None)
                if srgb is not None:
                    return (float(srgb.r), float(srgb.g), float(srgb.b))
        return (1.0, 1.0, 1.0)

    @make_method("/olc/selected/color/rgb")
    def _selected_color_rgb(self, _address: str, args: list) -> None:
        """Set RGB color on selected fixtures."""
        if len(args) >= 3:
            r = float(args[0])
            g = float(args[1])
            b = float(args[2])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/r")
    def _selected_color_r(self, _address: str, args: list) -> None:
        """Set red component [0.0..1.0] on selected fixtures."""
        if args:
            _, g, b = self._get_selected_srgb()
            r = parse_osc_normalized(args[0])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/g")
    def _selected_color_g(self, _address: str, args: list) -> None:
        """Set green component [0.0..1.0] on selected fixtures."""
        if args:
            r, _, b = self._get_selected_srgb()
            g = parse_osc_normalized(args[0])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/b")
    def _selected_color_b(self, _address: str, args: list) -> None:
        """Set blue component [0.0..1.0] on selected fixtures."""
        if args:
            r, g, _ = self._get_selected_srgb()
            b = parse_osc_normalized(args[0])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/hue")
    def _selected_color_hue(self, _address: str, args: list) -> None:
        """Set hue component [0.0..1.0] on selected fixtures."""
        if args:
            r, g, b = self._get_selected_srgb()
            _, s, v = colorsys.rgb_to_hsv(r, g, b)
            if v < 0.01:
                v = 1.0
            if s < 0.01:
                s = 1.0
            h = parse_osc_normalized(args[0])
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            self._execute_action("device.set_color", nr, ng, nb)

    @make_method("/olc/selected/color/sat")
    def _selected_color_sat(self, _address: str, args: list) -> None:
        """Set saturation component [0.0..1.0] on selected fixtures."""
        if args:
            r, g, b = self._get_selected_srgb()
            h, _, v = colorsys.rgb_to_hsv(r, g, b)
            if v < 0.01:
                v = 1.0
            s = parse_osc_normalized(args[0])
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            self._execute_action("device.set_color", nr, ng, nb)

    @make_method("/olc/selected/color/hsv")
    def _selected_color_hsv(self, _address: str, args: list) -> None:
        """Set HSV color on selected fixtures (converts to RGB)."""
        if len(args) >= 2:
            h = float(args[0])
            s = float(args[1])
            v = float(args[2]) if len(args) >= 3 else 1.0
            if h > 1.0:
                h = h / 360.0
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/zoom")
    def _selected_zoom(self, _address: str, args: list) -> None:
        """Set normalized zoom [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "zoom", norm)

    @make_method("/olc/selected/zoom/degrees")
    def _selected_zoom_degrees(self, _address: str, args: list) -> None:
        """Set physical zoom angle in degrees on selected fixtures."""
        if args:
            deg = float(args[0])
            self._execute_action("device.set_parameter", "zoom", deg, is_physical=True)

    @make_method("/olc/selected/focus")
    def _selected_focus(self, _address: str, args: list) -> None:
        """Set normalized focus [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "focus", norm)

    @make_method("/olc/selected/focus/meters")
    def _selected_focus_meters(self, _address: str, args: list) -> None:
        """Set physical focus distance in meters on selected fixtures."""
        if args:
            dist = float(args[0])
            self._execute_action(
                "device.set_parameter", "focus", dist, is_physical=True
            )

    @make_method("/olc/selected/iris")
    def _selected_iris(self, _address: str, args: list) -> None:
        """Set normalized iris aperture [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "iris", norm)

    @make_method("/olc/selected/strobe")
    def _selected_strobe(self, _address: str, args: list) -> None:
        """Set normalized strobe frequency [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "strobe", norm)

    @make_method("/olc/selected/strobe/hz")
    def _selected_strobe_hz(self, _address: str, args: list) -> None:
        """Set physical strobe frequency in Hz on selected fixtures."""
        if args:
            freq = float(args[0])
            self._execute_action(
                "device.set_parameter", "strobe", freq, is_physical=True
            )

    @make_method("/olc/selected/frost")
    def _selected_frost(self, _address: str, args: list) -> None:
        """Set normalized frost filter [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "frost", norm)

    @make_method("/olc/selected/gobo")
    def _selected_gobo(self, _address: str, args: list) -> None:
        """Set gobo wheel normalized position or index on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "gobo_wheel", norm)

    @make_method("/olc/selected/prism")
    def _selected_prism(self, _address: str, args: list) -> None:
        """Set prism normalized level or insertion on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "prism", norm)

    def _apply_kelvin_to_selected(self, k: float) -> None:
        """Apply Kelvin value (normalized 0..1 or physical K) to selected fixtures."""
        if 0.0 <= k <= 1.0:
            self._execute_action("device.set_parameter", "color_temp", k)
            kelvin_val = KELVIN_MIN + k * (KELVIN_MAX - KELVIN_MIN)
        else:
            self._execute_action(
                "device.set_parameter", "color_temp", k, is_physical=True
            )
            kelvin_val = k

        patch = self.app.lightshow.patch
        color_only_ids: list[int] = []
        for ch_id in self.app.selected_channels:
            dev = patch.devices.get(ch_id)
            if dev is None:
                continue
            if dev.get_channel(ChannelType.COLOR_TEMP) is None and any(
                dev.get_channel(ct) is not None for ct in COLOR_CHANNEL_TYPES
            ):
                color_only_ids.append(ch_id)
        if color_only_ids:
            r, g, b = kelvin_to_srgb(kelvin_val)
            self._execute_action("device.set_color", r, g, b, channels=color_only_ids)

    @make_method("/olc/selected/color/kelvin")
    @make_method("/olc/selected/cct")
    def _selected_color_kelvin(self, _address: str, args: list) -> None:
        """Set color temperature in Kelvin on selected fixtures."""
        if args:
            self._apply_kelvin_to_selected(float(args[0]))

    @make_method("/olc/selected/color/kelvin/*")
    def _selected_color_kelvin_preset(self, address: str, args: list) -> None:
        """Set color temperature preset in Kelvin."""
        if not self._is_momentary_press(args):
            return
        parts = address.split("/")
        if len(parts) >= 6:
            try:
                k = float(parts[5])
                self._apply_kelvin_to_selected(k)
            except ValueError:
                pass

    @make_method("/olc/selected/param/*")
    def _selected_param_generic(self, address: str, args: list) -> None:
        """Set generic normalized parameter on selected fixtures."""
        if not args:
            return
        parts = address.split("/")
        if len(parts) >= 5:
            param_name = parts[4]
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", param_name, norm)

    @make_method("/olc/device/*/zoom")
    def _device_zoom(self, address: str, args: list) -> None:
        """Set normalized zoom for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "zoom", norm, channels=[ch])

    @make_method("/olc/device/*/focus")
    def _device_focus(self, address: str, args: list) -> None:
        """Set normalized focus for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "focus", norm, channels=[ch])

    @make_method("/olc/device/*/iris")
    def _device_iris(self, address: str, args: list) -> None:
        """Set normalized iris for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "iris", norm, channels=[ch])

    @make_method("/olc/device/*/strobe")
    def _device_strobe(self, address: str, args: list) -> None:
        """Set normalized strobe for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "strobe", norm, channels=[ch])

    @make_method("/olc/device/*/frost")
    def _device_frost(self, address: str, args: list) -> None:
        """Set normalized frost for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "frost", norm, channels=[ch])

    @make_method("/olc/device/*/gobo")
    def _device_gobo(self, address: str, args: list) -> None:
        """Set normalized gobo for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "gobo_wheel", norm, channels=[ch])

    @make_method("/olc/device/*/prism")
    def _device_prism(self, address: str, args: list) -> None:
        """Set normalized prism for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "prism", norm, channels=[ch])

    @make_method("/olc/device/*/pan")
    def _device_pan(self, address: str, args: list) -> None:
        """Set absolute pan coordinate in degrees for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        val = float(args[0])
        self._execute_action("device.set_pan_tilt", val, None, channels=[ch])

    @make_method("/olc/device/*/tilt")
    def _device_tilt(self, address: str, args: list) -> None:
        """Set absolute tilt coordinate in degrees for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        val = float(args[0])
        self._execute_action("device.set_pan_tilt", None, val, channels=[ch])

    @make_method("/olc/device/*/color/rgb")
    def _device_color_rgb(self, address: str, args: list) -> None:
        """Set RGB color for a specific device."""
        if len(args) < 3:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        r = float(args[0])
        g = float(args[1])
        b = float(args[2])
        self._execute_action("device.set_color", r, g, b, channels=[ch])

    @make_method("/olc/device/*/param/*")
    def _device_param_generic(self, address: str, args: list) -> None:
        """Set generic normalized parameter for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
            param_name = parts[5]
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", param_name, norm, channels=[ch])

    @make_method(None)
    def _fallback(self, address: str, args: list) -> None:
        print(f"[OSC Delegate] Unknown message: {address} with args {args}")
