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
from typing import Optional

from olc.core.tracking import DEFAULT_MIB_FADE_TIME, TrackingEngine
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.sequence_threads import (
    ThreadGo,
    ThreadGoBack,
    _capture_device_states,
    _interpolate_device_states,
    _next_step,
    _parse_rgb_norm,
    get_cue,
)
from olc.step import Step

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.app import CoreApplication
    from olc.core.lightshow import LightShow
    from olc.patch import PatchManager


# pylint: disable=too-many-instance-attributes
class Sequence:
    """Sequence Object
    A Sequence is a collection of Steps
    """

    index: float
    type_seq: str
    text: str
    thread: Optional[ThreadGo | ThreadGoBack]
    lightshow: typing.Optional[LightShow]
    backend: typing.Any
    _on_go: bool

    def __init__(
        self,
        index: float,
        type_seq: str = "Normal",
        text: str = "",
        lightshow: typing.Optional[LightShow] = None,
    ) -> None:
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.lightshow = lightshow
        self.cues = set()
        self.steps: list[Step] = []
        self.position = 0
        self.last = 0
        # Flag to know if we have a Go in progress
        self._on_go = False
        # Channels present in this sequence
        self.channels: set[int] = set()
        # Flag for chasers
        self.run = False
        # Thread for Go and GoBack
        self.thread = None
        # Tracking mode (False = Cue-Only, True = Tracking for intensity)
        self.tracking_mode = False
        # Move In Black (MIB) pre-positioning and post-extinction fade time (s)
        self.mib_enabled = True
        self.mib_fade_time = DEFAULT_MIB_FADE_TIME
        self._cached_next_levels: tuple[typing.Any, list[int]] | None = None

        # Step and Cue 0
        cue = Cue(0, 0.0)
        self.cues.add(cue)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

    @property
    def patch(self) -> Optional[PatchManager]:
        """Get PatchManager from lightshow if available."""
        if self.lightshow is not None:
            return getattr(self.lightshow, "patch", None)
        return None

    def load_step(self, step_index: int) -> None:
        """Directly load and apply a sequence step state to DMX outputs."""
        if not self.steps or step_index < 0 or step_index >= len(self.steps):
            return
        self.invalidate_next_channel_levels_cache()
        self.position = step_index
        resolved = TrackingEngine.resolve_step_state(
            self, step_index, tracking_mode=self.tracking_mode, patch=self.patch
        )
        if self.backend is not None and hasattr(self.backend, "dmx"):
            n_ch = min(len(self.backend.dmx.levels["sequence"]), len(resolved.channels))
            self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]
            if self.patch is not None:
                for dev_id, params in resolved.device_values.items():
                    dev = self.patch.get_device(dev_id)
                    if dev is not None:
                        dev.apply_device_values(params)
            self.backend.dmx.set_levels()
        self.update_channels()

    @property
    def on_go(self) -> bool:
        """Check if a Go transition is in progress."""
        return getattr(self, "_on_go", False)

    @on_go.setter
    def on_go(self, value: bool) -> None:
        """Set the on_go transition flag and trigger event notifications."""
        if getattr(self, "_on_go", False) != value:
            self._on_go = value
            if self.app is not None:
                core = getattr(self.app, "core", self.app)
                # Update action registry feedback for MIDI bindings
                core.action_registry.trigger_feedback("playback.go")
                # Emit event for GUI (GuiEventBridge)
                core.emit(
                    "playback.go_triggered",
                    core.action_registry.get("playback.go").get_feedback_state(),
                )

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        if self.lightshow:
            return self.lightshow.app
        return None

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        if self.app is not None:
            return typing.cast(typing.Any, self.app).backend
        return None

    def stop(self) -> bool:
        """Stop Go

        Returns:
            True if Go to stop, else False
        """
        if self.on_go and self.thread:
            if self.app is not None and self.app.midi is not None:
                self.app.midi.button_off("playback.go")
            # Switch off Pause Led / Feedback
            if not self.thread.pause.is_set():
                self.thread.pause.set()
                if self.app is not None and self.app.midi is not None:
                    self.app.midi.button_off("playback.pause")
                if self.app is not None:
                    core = getattr(self.app, "core", self.app)
                    if hasattr(core, "action_registry"):
                        core.action_registry.trigger_feedback("playback.pause")
                    if hasattr(core, "emit"):
                        core.emit(
                            "playback.pause_triggered",
                            core.action_registry.get(
                                "playback.pause"
                            ).get_feedback_state()
                            if hasattr(core, "action_registry")
                            else {"active": False, "label": "PAUSE"},
                        )
            else:
                self.thread.pause.set()
            self.thread.stop()
            self.thread.join(timeout=1.0)
            self.thread = None
            self.on_go = False
            if self.app is not None and self.app.crossfade is not None:
                self.app.crossfade.scale_a.set_value(0)
                self.app.crossfade.scale_b.set_value(0)
            # Stop at the end
            self.position = min(self.position, self.last - 3)
            return True
        return False

    def _add_cue_channels(self, cue: Optional[Cue]) -> None:
        """Add conventional and multi-parameter device channels from cue."""
        if cue is None:
            return
        for channel in cue.channels:
            self.channels.add(channel)
        for dev_id in getattr(cue, "device_values", {}):
            if 1 <= dev_id <= MAX_CHANNELS:
                self.channels.add(dev_id)

    def update_channels(self) -> None:
        """Update channels present in sequence"""
        self.channels.clear()
        for step in self.steps:
            self._add_cue_channels(step.cue)
        if self.app is not None and self.backend is not None:
            for channel, level in enumerate(self.backend.dmx.levels["user"]):
                if level != -1:
                    self.channels.add(channel + 1)
        if self.patch is not None:
            for dev_id, dev in getattr(self.patch, "devices", {}).items():
                if (
                    1 <= dev_id <= MAX_CHANNELS
                    and float(getattr(dev, "intensity", 0.0)) > 0.0
                ):
                    self.channels.add(dev_id)

    def add_step(self, step: Step) -> None:
        """Add step at the end

        Args:
            step: Step number
        """
        self.invalidate_next_channel_levels_cache()
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        self._add_cue_channels(step.cue)

    def insert_step(self, index: int, step: Step) -> None:
        """Insert step at index

        Args:
            index: Index
            step: Step
        """
        self.invalidate_next_channel_levels_cache()
        self.steps.insert(index, step)
        self.last = len(self.steps)
        # Channels used in sequential
        self._add_cue_channels(step.cue)

    def get_step(self, cue: Optional[float] = None) -> tuple[bool, int]:
        """Get Cue Step

        Args:
            cue (float): Cue number

        Returns:
            found (bool), step (int)
        """
        found = False
        step = 0
        # Cue already exist ?
        for item in self.steps:
            if item.cue is not None and item.cue.number == cue:
                found = True
                break
            step += 1
        step -= 1
        # If new Cue, find step index
        if not found:
            exist = False
            step = 0
            for item in self.steps:
                if item.cue is not None and cue is not None and item.cue.number > cue:
                    exist = True
                    break
                step += 1
            if not exist:
                step += 1
        elif step:
            step += 1

        return found, step

    def get_next_cue(self, step: Optional[int] = None) -> Optional[float]:
        """Get next free Cue

        Args:
            step: Actual Cue Step number

        Returns:
            Cue number
        """
        if step is None:
            return None
        step_cue = self.steps[step].cue
        number = step_cue.number if step_cue is not None else 0.0
        if step >= self.last - 1:
            return number + 1

        next_step_cue = self.steps[step + 1].cue
        next_number = next_step_cue.number if next_step_cue is not None else 0.0
        return (
            ((next_number - number) / 2) + number
            if next_number != 0.0 and (next_number - number) <= 1
            else number + 1
        )

    def invalidate_next_channel_levels_cache(self) -> None:
        """Invalidate memoized next cue channel levels."""
        self._cached_next_levels = None

    def get_all_next_channel_levels(self) -> list[int] | None:
        """Get all channel levels in next cue as an array of 512 integers.

        Returns:
            List of levels indexed by channel (0 to 511), or None if no next cue.
        """
        if (
            len(self.steps) > self.position + 1
            and self.last > 1
            and self.position < self.last - 1
        ):
            target_step_idx = self.position + 1
        elif self.last and self.steps:
            target_step_idx = 0
        else:
            return None

        cache_key = (
            target_step_idx,
            self.tracking_mode,
            len(self.steps),
            getattr(self.patch, "_numpy_cache_dirty", None),
        )
        if (
            self._cached_next_levels is not None
            and self._cached_next_levels[0] == cache_key
        ):
            return self._cached_next_levels[1]

        resolved = TrackingEngine.resolve_step_state(
            self,
            target_step_idx,
            tracking_mode=self.tracking_mode,
            patch=self.patch,
            mib_enabled=False,
        )

        levels = [0] * MAX_CHANNELS
        for ch_idx in range(min(MAX_CHANNELS, len(resolved.channels))):
            levels[ch_idx] = int(resolved.channels[ch_idx])

        for ch_num, dev_vals in resolved.device_values.items():
            if 1 <= ch_num <= MAX_CHANNELS:
                dev_int = dev_vals.get("intensity")
                if isinstance(dev_int, (int, float)):
                    dev_lvl = round(
                        float(dev_int) * 255.0
                        if float(dev_int) <= 1.0
                        else float(dev_int)
                    )
                    levels[ch_num - 1] = max(
                        levels[ch_num - 1], 0, min(255, dev_lvl)
                    )

        self._cached_next_levels = (cache_key, levels)
        return levels

    def get_next_channel_level(self, channel: int, level: int) -> int:
        """Get channel level in next cue

        Args:
            channel: channel number (1 - MAX_CHANNELS)
            level: level in active cue (0 - 255)

        Returns:
            level in next cue (0 - 255)
        """
        levels = self.get_all_next_channel_levels()
        if levels is not None and 1 <= channel <= len(levels):
            return levels[channel - 1]
        return level

    def sequence_plus(self) -> None:
        """Sequence +"""
        self.stop()

        # Jump to next Step
        position = self.position + 1
        if position < self.last - 1:  # Stop on the last cue
            if self.backend is not None and self.backend.dmx is not None:
                self.backend.dmx.levels["user"].fill(-1)
            self.load_step(position)

    def sequence_minus(self) -> None:
        """Sequence -"""
        self.stop()

        # Jump to previous Step
        position = self.position - 1
        if position >= 0:
            if self.backend is not None and self.backend.dmx is not None:
                self.backend.dmx.levels["user"].fill(-1)
            self.load_step(position)

    def goto(self, keystring: str, override_time: Optional[float] = None) -> None:
        """Jump to cue number

        Args:
            keystring: Cue number
            override_time: Optional override fade time in seconds (0 = instant load)
        """
        old_pos = self.position

        if not keystring:
            return

        # Scan all cues
        for i, step in enumerate(self.steps):
            # Until we find the good one
            if float(get_cue(step).number) == float(keystring):
                # Position to the one just before
                self.position = i - 1
                next_step = self.position + 1

                eff_total = (
                    override_time
                    if override_time is not None
                    else self.steps[next_step].total_time
                )
                eff_in = (
                    override_time
                    if override_time is not None
                    else self.steps[next_step].time_in
                )
                eff_out = (
                    override_time
                    if override_time is not None
                    else self.steps[next_step].time_out
                )

                # Emit event for GUI (GuiEventBridge) to setup times and view
                if self.app is not None:
                    core = getattr(self.app, "core", self.app)
                    core.emit(
                        "playback.goto_selected",
                        {
                            "old_pos": old_pos,
                            "next_step": next_step,
                            "keystring": keystring,
                            "total_time": eff_total,
                            "time_in": eff_in,
                            "time_out": eff_out,
                            "delay_in": (
                                0.0
                                if override_time is not None
                                else self.steps[next_step].delay_in
                            ),
                            "delay_out": (
                                0.0
                                if override_time is not None
                                else self.steps[next_step].delay_out
                            ),
                            "wait": (
                                0.0
                                if override_time is not None
                                else self.steps[next_step].wait
                            ),
                            "channel_time": (
                                {}
                                if override_time is not None
                                else self.steps[next_step].channel_time
                            ),
                        },
                    )

                if override_time is not None and override_time <= 0.0:
                    self.stop()
                    if self.backend is not None and self.backend.dmx is not None:
                        self.backend.dmx.levels["user"].fill(-1)
                    self.load_step(i)
                    self.position = i - 1
                    next_after = _next_step(self)
                    if self.app is not None:
                        core = getattr(self.app, "core", self.app)
                        core.emit(
                            "playback.transition_completed",
                            {"next_step": next_after},
                        )
                else:
                    # Launch Go
                    self.do_go(None, True, override_time=override_time)
                break

    def do_go(
        self,
        _action: Optional[Gio.SimpleAction],
        goto: bool = False,
        override_time: Optional[float] = None,
    ) -> None:
        """Go

        Args:
            goto: True if Goto, False if Go (default)
            override_time: Optional override fade time in seconds
        """
        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_on("playback.go")
        # If Go is active, go to next cue
        if self.stop():
            # Launch another Go
            position = self.position
            position += 1
            if position < self.last - 1:
                self.position += 1
            else:
                self.position = 0
                position = 0
            self.on_go = False

            # Set main window's subtitle
            subtitle = (
                f"Mem. : {get_cue(self.steps[position]).number} "
                f"{self.steps[position].text} - Next Mem. : "
                f"{get_cue(self.steps[position + 1]).number} "
                f"{self.steps[position + 1].text}"
            )

            # Emit event for GUI (GuiEventBridge)
            if self.app is not None:
                core = getattr(self.app, "core", self.app)
                core.emit(
                    "playback.go_triggered_direct",
                    {
                        "position": position,
                        "subtitle": subtitle,
                        "total_time": self.steps[position + 1].total_time,
                        "time_in": self.steps[position + 1].time_in,
                        "time_out": self.steps[position + 1].time_out,
                        "delay_in": self.steps[position + 1].delay_in,
                        "delay_out": self.steps[position + 1].delay_out,
                        "wait": self.steps[position + 1].wait,
                        "channel_time": self.steps[position + 1].channel_time,
                    },
                )

            self.do_go(None, override_time=override_time)

        else:
            # Indicates that a Go is in progress
            self.on_go = True
            self.thread = ThreadGo(goto, self, override_time=override_time)
            self.thread.start()

    def go_back(self, _action: Optional[Gio.SimpleAction], _param: None) -> bool:
        """Go Back

        Returns:
            True or False
        """
        # Just return if we are at the beginning
        position = self.position
        if position <= 0:
            return False

        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_on("playback.go_back")

        self.stop()

        goback_time = 0.0
        if self.app is not None:
            goback_time = typing.cast(typing.Any, self.app.settings).get_double(
                "go-back-time"
            )

        subtitle = (
            f"Mem. : {get_cue(self.steps[position]).number} "
            f"{self.steps[position].text}"
            f" - Next Mem. : {get_cue(self.steps[position - 1]).number} "
            f"{self.steps[position - 1].text}"
        )

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.go_back_started",
                {
                    "position": position,
                    "subtitle": subtitle,
                    "goback_time": goback_time,
                },
            )

        self.on_go = True
        self.thread = ThreadGoBack(self)
        self.thread.start()
        return False

    def pause(self, _action: Optional[Gio.SimpleAction], _param: None) -> None:
        """Toggle pause"""
        if self.thread:
            if self.thread.pause.is_set():
                self.thread.pause.clear()
                if self.app is not None and self.app.midi is not None:
                    self.app.midi.button_on("playback.pause")
            else:
                self.thread.pause.set()
                if self.app is not None and self.app.midi is not None:
                    self.app.midi.button_off("playback.pause")
            if self.app is not None:
                core = getattr(self.app, "core", self.app)
                core.action_registry.trigger_feedback("playback.pause")
                core.emit(
                    "playback.pause_triggered",
                    core.action_registry.get("playback.pause").get_feedback_state(),
                )


__all__ = [
    "Sequence",
    "ThreadGo",
    "ThreadGoBack",
    "get_cue",
    "_capture_device_states",
    "_interpolate_device_states",
    "_next_step",
    "_parse_rgb_norm",
]
