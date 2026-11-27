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

from olc.core.playback_arbitrator import PlaybackPriority, parse_playback_priority
from olc.core.tracking import DEFAULT_MIB_FADE_TIME, TrackingEngine
from olc.define import MAX_CHANNELS
from olc.show.cue import Cue
from olc.show.sequence_threads import (
    ThreadGo,
    ThreadGoBack,
    _apply_resolved_device_values,
    _capture_device_states,
    _emit_device_changes,
    _interpolate_device_states,
    _next_step,
    _notify_runner,
    _parse_rgb_norm,
    _sync_resolved_effects,
    apply_arbitrated_output,
    get_cue,
    is_main_sequence,
)
from olc.show.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.lightshow import LightShow
    from olc.show.patch import PatchManager


# pylint: disable=too-many-instance-attributes
class Sequence:
    """Sequence Object
    A Sequence is a collection of Steps
    """

    index: float
    text: str
    thread: Optional[ThreadGo | ThreadGoBack]
    lightshow: typing.Optional[LightShow]
    backend: typing.Any
    _on_go: bool

    def __init__(
        self,
        index: float,
        text: str = "",
        lightshow: typing.Optional[LightShow] = None,
    ) -> None:
        self.index = index
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
        # Thread for Go and GoBack
        self.thread = None
        # Tracking mode (False = Cue-Only, True = Tracking for intensity)
        self.tracking_mode = False
        # Move In Black (MIB) pre-positioning and post-extinction fade time (s)
        self.mib_enabled = True
        self.mib_fade_time = DEFAULT_MIB_FADE_TIME
        # Multi-sequence playback options
        self.priority: PlaybackPriority = PlaybackPriority.NORMAL
        self.htp_intensity: bool = True
        self.auto_start: bool = False
        self.auto_stop: bool = False
        self.off_on_overwritten: bool = False
        self.wrap_around: bool = False
        self.release_on_end: bool = False
        self.release_time: float = 0.0
        self._cached_next_levels: tuple[typing.Any, list[int]] | None = None
        self._loop_counters: dict[int, int] = {}

        # Step and Cue 0
        cue = Cue(0, 0.0)
        self.cues.add(cue)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

    def playback_options_to_dict(self) -> dict[str, typing.Any]:
        """Serialize non-default multi-sequence playback options."""
        data: dict[str, typing.Any] = {}
        if self.priority is not PlaybackPriority.NORMAL:
            data["priority"] = int(self.priority)
        if not self.htp_intensity:
            data["htp_intensity"] = False
        if self.auto_start:
            data["auto_start"] = True
        if self.auto_stop:
            data["auto_stop"] = True
        if self.off_on_overwritten:
            data["off_on_overwritten"] = True
        if self.wrap_around:
            data["wrap_around"] = True
        if self.release_on_end:
            data["release_on_end"] = True
        if self.release_time > 0.0:
            data["release_time"] = float(self.release_time)
        return data

    def apply_playback_options(self, data: typing.Mapping[str, typing.Any]) -> None:
        """Restore multi-sequence playback options from a serialized dictionary."""
        if "priority" in data:
            self.priority = parse_playback_priority(data["priority"])
        if "htp_intensity" in data:
            self.htp_intensity = bool(data["htp_intensity"])
        if "auto_start" in data:
            self.auto_start = bool(data["auto_start"])
        if "auto_stop" in data:
            self.auto_stop = bool(data["auto_stop"])
        if "off_on_overwritten" in data:
            self.off_on_overwritten = bool(data["off_on_overwritten"])
        if "wrap_around" in data:
            self.wrap_around = bool(data["wrap_around"])
        if "release_on_end" in data:
            self.release_on_end = bool(data["release_on_end"])
        if "release_time" in data:
            self.release_time = max(0.0, float(data["release_time"]))

    @property
    def patch(self) -> Optional[PatchManager]:
        """Get PatchManager from lightshow if available."""
        if self.lightshow is not None:
            return getattr(self.lightshow, "patch", None)
        return None

    def load_step(self, step_index: int, *, fader_level: float | None = None) -> None:
        """Directly load and apply a sequence step state to DMX outputs."""
        if not self.steps or step_index < 0 or step_index >= len(self.steps):
            return
        engine = getattr(self.app, "playback_engine", None) if self.app else None
        if engine is not None:
            engine.cancel_release_fade(self.index)
        self.invalidate_next_channel_levels_cache()
        self.position = step_index
        resolved = TrackingEngine.resolve_step_state(
            self, step_index, tracking_mode=self.tracking_mode, patch=self.patch
        )
        cue = self.steps[step_index].cue
        cue_num = getattr(cue, "number", None)
        is_assert = bool(getattr(cue, "is_assert", False))
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            existing_state = arb.get_state(self.index)
            eff_fader = (
                fader_level
                if fader_level is not None
                else (existing_state.fader_level if existing_state is not None else 1.0)
            )
            composed = arb.set_sequence_output(
                self.index,
                resolved.channels,
                resolved.device_values,
                priority=self.priority,
                htp_intensity=self.htp_intensity,
                fader_level=eff_fader,
                cue_number=cue_num,
                off_on_overwritten=self.off_on_overwritten,
                assert_all=is_assert,
            )
            apply_arbitrated_output(
                self.app,
                self.backend,
                self.patch,
                composed,
                force_assert=is_assert,
            )
            _sync_resolved_effects(
                self.app, resolved, fade_time=0.0, clear_live_state=True
            )
            _notify_runner(self, "active", fade_progress=0.0, fade_remaining=0.0)
        elif self.backend is not None and hasattr(self.backend, "dmx"):
            n_ch = min(len(self.backend.dmx.levels["sequence"]), len(resolved.channels))
            self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]
            if self.patch is not None:
                _apply_resolved_device_values(self.patch, resolved, self.app)
            _sync_resolved_effects(
                self.app, resolved, fade_time=0.0, clear_live_state=True
            )
            _notify_runner(self, "active", fade_progress=0.0, fade_remaining=0.0)
            self.backend.dmx.set_levels()
        else:
            _sync_resolved_effects(
                self.app, resolved, fade_time=0.0, clear_live_state=True
            )
            _notify_runner(self, "active", fade_progress=0.0, fade_remaining=0.0)
        self.update_channels()

    def release(self, fade_time: float | None = None) -> None:
        """Stop this sequence and release its ownership back to lower layers."""
        eff_time = (
            float(fade_time)
            if fade_time is not None
            else float(getattr(self, "release_time", 0.0) or 0.0)
        )
        engine = getattr(self.app, "playback_engine", None) if self.app else None
        if eff_time > 0.0 and engine is not None:
            engine.release(self.index, fade_time=eff_time)
            return
        if engine is not None:
            engine.cancel_release_fade(self.index)
        self.stop()
        self.on_go = False
        self.position = 0
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            composed, released_to_home = arb.release_sequence(self.index)
            apply_arbitrated_output(
                self.app,
                self.backend,
                self.patch,
                composed,
                released_to_home=released_to_home,
            )
        if self.app is not None and hasattr(self.app, "emit"):
            self.app.emit("playback.sequence_released", self.index)
        _notify_runner(self, "idle", fade_progress=0.0, fade_remaining=0.0)

    def assert_playback(self) -> None:
        """Reclaim ownership of all channels and parameters held by this sequence."""
        engine = getattr(self.app, "playback_engine", None) if self.app else None
        if engine is not None:
            engine.cancel_release_fade(self.index)
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            composed = arb.assert_sequence(self.index)
            apply_arbitrated_output(
                self.app,
                self.backend,
                self.patch,
                composed,
                force_assert=True,
            )
        if self.app is not None and hasattr(self.app, "emit"):
            self.app.emit("playback.sequence_asserted", self.index)

    @property
    def on_go(self) -> bool:
        """Check if a Go transition is in progress."""
        return getattr(self, "_on_go", False)

    @on_go.setter
    def on_go(self, value: bool) -> None:
        """Set the on_go transition flag and trigger event notifications."""
        if getattr(self, "_on_go", False) != value:
            self._on_go = value
            if self.app is not None and is_main_sequence(self):
                # Update action registry feedback for MIDI bindings
                self.app.action_registry.trigger_feedback("playback.go")
                # Emit event for GUI (GuiEventBridge)
                self.app.emit(
                    "playback.go_triggered",
                    self.app.action_registry.get("playback.go").get_feedback_state(),
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
            is_main = is_main_sequence(self)
            # Switch off Pause Led / Feedback
            if not self.thread.pause.is_set():
                self.thread.pause.set()
                if is_main and self.app is not None:
                    if hasattr(self.app, "action_registry"):
                        self.app.action_registry.trigger_feedback("playback.pause")
                    if hasattr(self.app, "emit"):
                        self.app.emit(
                            "playback.pause_triggered",
                            self.app.action_registry.get(
                                "playback.pause"
                            ).get_feedback_state()
                            if hasattr(self.app, "action_registry")
                            else {"active": False, "label": "PAUSE"},
                        )
            else:
                self.thread.pause.set()
            self.thread.stop()
            self.thread.join(timeout=1.0)
            self.thread = None
            self.on_go = False
            if is_main and self.app is not None and hasattr(self.app, "emit"):
                self.app.emit("playback.stopped")
            if is_main and self.app is not None and self.app.crossfade is not None:
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
                if level >= 0.0:
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
                    levels[ch_num - 1] = max(levels[ch_num - 1], 0, min(255, dev_lvl))

        self._cached_next_levels = (cache_key, levels)
        return levels

    def get_next_channel_level(self, channel: int, level: float) -> float:
        """Get channel level in next cue

        Args:
            channel: channel number (1 - MAX_CHANNELS)
            level: normalized level in active cue (0.0 - 1.0)

        Returns:
            normalized level in next cue (0.0 - 1.0)
        """
        levels = self.get_all_next_channel_levels()
        if levels is not None and 1 <= channel <= len(levels):
            return float(levels[channel - 1])
        return level

    def sequence_plus(self) -> None:
        """Sequence +"""
        self.stop()

        # Jump to next Step
        position = self.position + 1
        if position < self.last - 1:  # Stop on the last cue
            self.load_step(position)

    def sequence_minus(self) -> None:
        """Sequence -"""
        self.stop()

        # Jump to previous Step
        position = self.position - 1
        if position >= 0:
            self.load_step(position)

    def resolve_next_step_index(
        self,
        active_pos: int,
        *,
        consume_loop: bool = False,
    ) -> int:
        """Resolve next step index from *active_pos*, honoring link/loop."""
        if 0 <= active_pos < len(self.steps):
            step = self.steps[active_pos]
            link_cue = getattr(step, "link_cue", None)
            if link_cue is not None:
                target_idx = next(
                    (
                        idx
                        for idx in range(1, max(1, self.last - 1))
                        if (c := self.steps[idx].cue) is not None
                        and abs(float(c.number) - float(link_cue)) < 1e-4
                    ),
                    None,
                )
                if target_idx is not None:
                    loop_limit = int(getattr(step, "loop_count", 0))
                    used = self._loop_counters.get(active_pos, 0)
                    if loop_limit == 0 or used < loop_limit:
                        if consume_loop and loop_limit > 0:
                            self._loop_counters[active_pos] = used + 1
                        return target_idx
                    if consume_loop:
                        self._loop_counters[active_pos] = 0
        nxt = active_pos + 1
        return nxt if nxt < self.last else 1

    def goto(self, keystring: str, override_time: Optional[float] = None) -> None:
        """Jump to cue number

        Args:
            keystring: Cue number
            override_time: Optional override fade time in seconds (0 = instant load)
        """
        old_pos = self.position
        self._loop_counters.clear()

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
                is_main = is_main_sequence(self)
                if is_main and self.app is not None:
                    self.app.emit(
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
                            "curve_id": (
                                0
                                if override_time is not None
                                else int(getattr(self.steps[next_step], "curve_id", 0))
                            ),
                        },
                    )

                if override_time is not None and override_time <= 0.0:
                    self.stop()
                    self.load_step(i)
                    next_after = _next_step(
                        typing.cast(typing.Any, self), target_step=i
                    )
                    if is_main and self.app is not None:
                        self.app.emit(
                            "playback.transition_completed",
                            {"next_step": next_after},
                        )
                else:
                    # Launch Go
                    self.do_go(None, True, override_time=override_time)
                break

    def do_go(
        self,
        _action: object,
        goto: bool = False,
        override_time: Optional[float] = None,
    ) -> None:
        """Go

        Args:
            goto: True if Goto, False if Go (default)
            override_time: Optional override fade time in seconds
        """
        engine = getattr(self.app, "playback_engine", None) if self.app else None
        if engine is not None:
            engine.cancel_release_fade(self.index)
        # If Go is active, go to next cue
        if self.stop():
            # Launch another Go
            landed = (
                getattr(self.thread, "target_step", self.position + 1)
                if self.thread is not None
                else self.position + 1
            )
            if landed < self.last - 1:
                self.position = landed
                position = landed
            else:
                self.position = 0
                position = 0
            self.on_go = False

            next_idx = self.resolve_next_step_index(position, consume_loop=False)
            # Set main window's subtitle
            subtitle = (
                f"Cue : {get_cue(self.steps[position]).number} "
                f"{self.steps[position].text} - Next Cue : "
                f"{get_cue(self.steps[next_idx]).number} "
                f"{self.steps[next_idx].text}"
            )

            # Emit event for GUI (GuiEventBridge)
            if is_main_sequence(self) and self.app is not None:
                self.app.emit(
                    "playback.go_triggered_direct",
                    {
                        "position": position,
                        "subtitle": subtitle,
                        "total_time": self.steps[next_idx].total_time,
                        "time_in": self.steps[next_idx].time_in,
                        "time_out": self.steps[next_idx].time_out,
                        "delay_in": self.steps[next_idx].delay_in,
                        "delay_out": self.steps[next_idx].delay_out,
                        "wait": self.steps[next_idx].wait,
                        "channel_time": self.steps[next_idx].channel_time,
                        "curve_id": int(getattr(self.steps[next_idx], "curve_id", 0)),
                    },
                )

            self.do_go(None, override_time=override_time)

        else:
            peek_next = self.resolve_next_step_index(self.position, consume_loop=False)
            if (
                not goto
                and self.last > 2
                and self.position >= self.last - 2
                and peek_next >= self.last - 1
            ):
                if self.release_on_end:
                    self.release()
                    return
                if self.wrap_around:
                    self.position = 0
            # Indicates that a Go is in progress
            self.on_go = True
            _notify_runner(self, "fading", fade_progress=0.0, fade_remaining=0.0)
            if (
                is_main_sequence(self)
                and self.app is not None
                and hasattr(self.app, "emit")
            ):
                self.app.emit("playback.go_started")
            self.thread = ThreadGo(
                goto, typing.cast(typing.Any, self), override_time=override_time
            )
            self.thread.start()

    def go_back(self, _action: object, _param: None) -> bool:
        """Go Back

        Returns:
            True or False
        """
        # Just return if we are at the beginning
        position = self.position
        if position <= 0:
            return False

        self.stop()

        goback_time = 0.0
        if self.app is not None:
            goback_time = typing.cast(typing.Any, self.app.settings).get_double(
                "go-back-time"
            )

        subtitle = (
            f"Cue : {get_cue(self.steps[position]).number} "
            f"{self.steps[position].text}"
            f" - Next Cue : {get_cue(self.steps[position - 1]).number} "
            f"{self.steps[position - 1].text}"
        )

        # Emit event for GUI (GuiEventBridge)
        if is_main_sequence(self) and self.app is not None:
            self.app.emit(
                "playback.go_back_started",
                {
                    "position": position,
                    "subtitle": subtitle,
                    "goback_time": goback_time,
                },
            )

        self.on_go = True
        self.thread = ThreadGoBack(typing.cast(typing.Any, self))
        self.thread.start()
        return False

    def pause(self, _action: object, _param: None) -> None:
        """Toggle pause"""
        if self.thread:
            if self.thread.pause.is_set():
                self.thread.pause.clear()
                _notify_runner(self, "paused")
            else:
                self.thread.pause.set()
                _notify_runner(self, "fading")
            if is_main_sequence(self) and self.app is not None:
                self.app.action_registry.trigger_feedback("playback.pause")
                self.app.emit(
                    "playback.pause_triggered",
                    self.app.action_registry.get("playback.pause").get_feedback_state(),
                )


__all__ = [
    "Sequence",
    "ThreadGo",
    "ThreadGoBack",
    "get_cue",
    "_apply_resolved_device_values",
    "_capture_device_states",
    "_emit_device_changes",
    "_interpolate_device_states",
    "_next_step",
    "_parse_rgb_norm",
]
