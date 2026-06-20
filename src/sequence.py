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

import threading
import time
import typing
from typing import Optional

import numpy as np
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.step import Step

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.app import CoreApplication
    from olc.core.lightshow import LightShow


def get_cue(step: Step) -> typing.Any:  # noqa: ANN401
    """Get the cue object from step as Any to simplify type checking."""
    return step.cue


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

        # Step and Cue 0
        cue = Cue(0, 0.0)
        self.cues.add(cue)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

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
        if (
            self.on_go
            and self.thread
            and self.app is not None
            and self.app.midi is not None
        ):
            self.app.midi.button_off("playback.go")
            # Switch off Pause Led
            if not self.thread.pause.is_set():
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
            else:
                self.thread.pause.set()
            self.thread.stop()
            self.thread.join()
            self.on_go = False
            if self.app is not None and self.app.crossfade is not None:
                self.app.crossfade.scale_a.set_value(0)
                self.app.crossfade.scale_b.set_value(0)
            # Stop at the end
            self.position = min(self.position, self.last - 3)
            return True
        return False

    def update_channels(self) -> None:
        """Update channels present in sequence"""
        self.channels.clear()
        for step in self.steps:
            if step.cue is not None:
                for channel in step.cue.channels:
                    self.channels.add(channel)
        if self.app is not None and self.backend is not None:
            for channel, level in enumerate(self.backend.dmx.levels["user"]):
                if level != -1:
                    self.channels.add(channel + 1)

    def add_step(self, step: Step) -> None:
        """Add step at the end

        Args:
            step: Step number
        """
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        if step.cue is not None:
            for channel in step.cue.channels:
                self.channels.add(channel)

    def insert_step(self, index: int, step: Step) -> None:
        """Insert step at index

        Args:
            index: Index
            step: Step
        """
        self.steps.insert(index, step)
        self.last = len(self.steps)
        # Channels used in sequential
        if step.cue is not None:
            for channel in step.cue.channels:
                self.channels.add(channel)

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

    def get_next_channel_level(self, channel: int, level: int) -> int:
        """Get channel level in next cue

        Args:
            channel: channel number (1 - MAX_CHANNELS)
            level: level in active cue (0 - 255)

        Returns:
            level in next cue (0 - 255)
        """
        if (
            len(self.steps) > self.position + 1
            and self.last > 1
            and self.position < self.last - 1
        ):
            next_cue = self.steps[self.position + 1].cue
            next_level = (
                next_cue.channels.get(channel, 0) if next_cue is not None else 0
            )
        elif self.last:
            first_cue = self.steps[0].cue
            next_level = (
                first_cue.channels.get(channel, 0) if first_cue is not None else 0
            )
        else:
            next_level = level
        return next_level

    def sequence_plus(self) -> None:
        """Sequence +"""
        self.stop()

        # Jump to next Step
        position = self.position
        position += 1
        if position < self.last - 1:  # Stop on the last cue
            self.position += 1

            # Empty DMX user array
            if self.backend is not None and self.backend.dmx is not None:
                self.backend.dmx.levels["user"].fill(-1)
                self.update_channels()

                # Send DMX values
                self.backend.dmx.levels["sequence"][:] = get_cue(
                    self.steps[self.position]
                ).channels_array
                self.backend.dmx.set_levels()

    def sequence_minus(self) -> None:
        """Sequence -"""
        self.stop()

        # Jump to previous Step
        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1

            # Empty DMX user array
            if self.backend is not None and self.backend.dmx is not None:
                self.backend.dmx.levels["user"].fill(-1)
                self.update_channels()

                # Send DMX values
                self.backend.dmx.levels["sequence"][:] = get_cue(
                    self.steps[self.position]
                ).channels_array
                self.backend.dmx.set_levels()

    def goto(self, keystring: str) -> None:
        """Jump to cue number

        Args:
            keystring: Cue number
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

                # Emit event for GUI (GuiEventBridge) to setup times and view
                if self.app is not None:
                    core = getattr(self.app, "core", self.app)
                    core.emit(
                        "playback.goto_selected",
                        {
                            "old_pos": old_pos,
                            "next_step": next_step,
                            "keystring": keystring,
                            "total_time": self.steps[next_step].total_time,
                            "time_in": self.steps[next_step].time_in,
                            "time_out": self.steps[next_step].time_out,
                            "delay_in": self.steps[next_step].delay_in,
                            "delay_out": self.steps[next_step].delay_out,
                            "wait": self.steps[next_step].wait,
                            "channel_time": self.steps[next_step].channel_time,
                        },
                    )

                # Launch Go
                self.do_go(None, True)
                break

    def do_go(self, _action: Optional[Gio.SimpleAction], goto: bool = False) -> None:
        """Go

        Args:
            goto: True if Goto, False if Go (default)
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

            self.do_go(None)

        else:
            # Indicates that a Go is in progress
            self.on_go = True
            self.thread = ThreadGo(goto, self)
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


# pylint: disable=too-many-instance-attributes
class ThreadGo(threading.Thread):
    """Thread object for Go"""

    sequence: Sequence
    old_channels_levels: np.ndarray
    total_time: float
    time_in: float
    time_out: float
    wait: float
    delay_in: float
    delay_out: float
    goto: bool
    backend: typing.Any

    def __init__(self, goto: bool, sequence: Sequence) -> None:
        threading.Thread.__init__(self, name="ThreadGo", daemon=True)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        # To save channels levels when user sends Go
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        next_step = self.sequence.position + 1
        self.total_time = self.sequence.steps[next_step].total_time * 1000
        self.time_in = self.sequence.steps[next_step].time_in * 1000
        self.time_out = self.sequence.steps[next_step].time_out * 1000
        self.wait = self.sequence.steps[next_step].wait * 1000
        self.delay_in = self.sequence.steps[next_step].delay_in * 1000
        self.delay_out = self.sequence.steps[next_step].delay_out * 1000
        self.goto = goto

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.sequence.app

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        return self.sequence.backend

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels when Go is sent"""
        self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
        user_levels = self.backend.dmx.levels["user"]
        user_mask = user_levels != -1
        self.old_channels_levels[user_mask] = user_levels[user_mask]

    def _finalize_go(self) -> None:
        """Finish load cue after sequence transition"""
        if self.sequence.position < self.sequence.last - 1:
            target_cue = get_cue(self.sequence.steps[self.sequence.position + 1])
        else:
            target_cue = get_cue(self.sequence.steps[0])

        # Block-copy levels to sequential dmx levels
        self.backend.dmx.levels["sequence"][:] = target_cue.channels_array

        self.sequence.on_go = False
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(0)
            self.app.crossfade.scale_b.set_value(0)
        self.backend.dmx.levels["user"].fill(-1)

        # Distribute DMX levels to frames
        self.backend.dmx.set_levels()

        self.sequence.update_channels()
        next_step = _next_step(self.sequence)

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.transition_completed",
                {
                    "next_step": next_step,
                },
            )

        if self.sequence.steps[next_step].wait:
            self.sequence.do_go(None)
        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_off("playback.go")

    def run(self) -> None:
        self._capture_start_levels()
        start_pause = None
        pause_time = 0.0
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time
        while i < self.total_time and not self._stopevent.is_set():
            if not self.pause.is_set():
                if not start_pause:
                    start_pause = time.time() * 1000
                self.pause.wait()
                pause_time += (time.time() * 1000) - start_pause
            else:
                start_pause = None
                i = (time.time() * 1000) - (start_time + pause_time)
                self.update_levels(i)
                time.sleep(0.05)

        if self._stopevent.is_set():
            return

        self._finalize_go()

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()

    def update_levels(self, i: float) -> None:
        """Update levels

        Args:
            i: Time spent
        """
        val = round((255 / self.total_time) * i)
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(val)
            self.app.crossfade.scale_b.set_value(val)

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.transition_progress",
                {
                    "time_spent": i,
                    "total_time": self.total_time,
                    "progress_val": val,
                    "sequence_position": self.sequence.position,
                },
            )

        # Wait for wait time
        if i > self.wait:
            if self.goto:
                self._do_goto(i)
            else:
                self._do_go(i)

    def _do_goto(self, i: float) -> None:
        """Goto

        Args:
            i: Time spent
        """
        self._do_go(i)

    def _do_go(self, i: float) -> None:
        """Go

        Args:
            i: Time spent
        """
        next_step = self.sequence.position + 1
        step = self.sequence.steps[next_step]

        lvls = self._calculate_transitions_go(i, step)
        self._apply_channel_times_go(lvls, i, step)

        self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0, 255).astype(np.uint8)
        self.backend.dmx.set_levels()

    def _calculate_transitions_go(self, i: float, step: Step) -> np.ndarray:
        """Calculate fade levels using array operations."""
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = get_cue(step).channels_array.astype(np.int32)
        lvls = old_levels.copy()

        # Decays (channels going down)
        decay_mask = next_levels < old_levels
        if np.any(decay_mask):
            progress_mask = (i > self.wait + step.delay_out * 1000) & (
                i < (step.time_out + step.wait + step.delay_out) * 1000
            )
            if np.any(progress_mask & decay_mask):
                factor = (i - self.wait - step.delay_out * 1000) / (
                    step.time_out * 1000
                )
                diff = (next_levels - old_levels) * factor
                decay_lvls = np.round(old_levels - np.abs(diff)).astype(np.int32)
                lvls[progress_mask & decay_mask] = decay_lvls[
                    progress_mask & decay_mask
                ]

            end_mask = i >= (step.time_out + step.wait + step.delay_out) * 1000
            lvls[end_mask & decay_mask] = next_levels[end_mask & decay_mask]

        # Attacks (channels going up)
        attack_mask = next_levels > old_levels
        if np.any(attack_mask):
            progress_mask = (i > self.wait + step.delay_in * 1000) & (
                i < (step.time_in + step.wait + step.delay_in) * 1000
            )
            if np.any(progress_mask & attack_mask):
                factor = (i - self.wait - step.delay_in * 1000) / (step.time_in * 1000)
                diff = (next_levels - old_levels) * factor
                attack_lvls = np.round(old_levels + diff).astype(np.int32)
                lvls[progress_mask & attack_mask] = attack_lvls[
                    progress_mask & attack_mask
                ]

            end_mask = i >= (step.time_in + step.wait + step.delay_in) * 1000
            lvls[end_mask & attack_mask] = next_levels[end_mask & attack_mask]

        return lvls

    def _apply_channel_times_go(self, lvls: np.ndarray, i: float, step: Step) -> None:
        """Apply individual channel times."""
        if not step.channel_time:
            return
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = get_cue(step).channels_array.astype(np.int32)
        for channel, ct in step.channel_time.items():
            o_lvl = old_levels[channel - 1]
            n_lvl = next_levels[channel - 1]
            if n_lvl < o_lvl:  # Decay
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = o_lvl - abs(int((n_lvl - o_lvl) * factor))
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl
            elif n_lvl > o_lvl:  # Attack
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = int((n_lvl - o_lvl) * factor + o_lvl)
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl


def _next_step(sequence: Sequence) -> int:
    """Next Step after Go

    Args:
        sequence: Main Playback

    Returns:
        Step
    """
    next_step = sequence.position + 1
    # If there is a next step
    if next_step < sequence.last - 1:
        sequence.position += 1
        next_step += 1
    # If no next step, go to beginning
    else:
        sequence.position = 0
        next_step = 1

    # Main window's subtitle
    subtitle = (
        f"Mem. : {get_cue(sequence.steps[sequence.position]).number} "
        f"{sequence.steps[sequence.position].text} - Next Mem. : "
        f"{get_cue(sequence.steps[next_step]).number} "
        f"{sequence.steps[next_step].text}"
    )

    # Emit event for GUI (GuiEventBridge)
    if sequence.app is not None:
        core = getattr(sequence.app, "core", sequence.app)
        core.emit(
            "playback.step_changed",
            {
                "position": sequence.position,
                "next_step": next_step,
                "subtitle": subtitle,
                "total_time": sequence.steps[next_step].total_time,
                "time_in": sequence.steps[next_step].time_in,
                "time_out": sequence.steps[next_step].time_out,
                "delay_in": sequence.steps[next_step].delay_in,
                "delay_out": sequence.steps[next_step].delay_out,
                "wait": sequence.steps[next_step].wait,
                "channel_time": sequence.steps[next_step].channel_time,
            },
        )
    return next_step


class ThreadGoBack(threading.Thread):
    """Thread Object for Go Back"""

    sequence: Sequence
    old_channels_levels: np.ndarray
    backend: typing.Any

    def __init__(self, sequence: Sequence) -> None:
        threading.Thread.__init__(self, name="ThreadGoBack", daemon=True)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        # To save channels levels when Go Back starts
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.sequence.app

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        return self.sequence.backend

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels when Go Back starts"""
        self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
        user_levels = self.backend.dmx.levels["user"]
        user_mask = user_levels != -1
        self.old_channels_levels[user_mask] = user_levels[user_mask]

    def _finalize_goback(self, prev_step: int) -> None:
        """Finish load cue after sequence transition"""
        target_cue = get_cue(self.sequence.steps[prev_step])

        # Block-copy levels to sequential dmx levels
        self.backend.dmx.levels["sequence"][:] = target_cue.channels_array

        self.sequence.on_go = False
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(0)
            self.app.crossfade.scale_b.set_value(0)
        self.backend.dmx.levels["user"].fill(-1)

        # Distribute DMX levels to frames
        self.backend.dmx.set_levels()

        self.sequence.update_channels()
        self.sequence.position = prev_step

        subtitle = (
            f"Mem. : {get_cue(self.sequence.steps[prev_step]).number} "
            f"{self.sequence.steps[prev_step].text} - Next Mem. : "
            f"{get_cue(self.sequence.steps[prev_step + 1]).number} "
            f"{self.sequence.steps[prev_step + 1].text}"
        )

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.goback_completed",
                {
                    "prev_step": prev_step,
                    "subtitle": subtitle,
                    "time_in": self.sequence.steps[prev_step + 1].time_in,
                    "time_out": self.sequence.steps[prev_step + 1].time_out,
                    "delay_in": self.sequence.steps[prev_step + 1].delay_in,
                    "delay_out": self.sequence.steps[prev_step + 1].delay_out,
                    "wait": self.sequence.steps[prev_step + 1].wait,
                    "total_time": self.sequence.steps[prev_step + 1].total_time,
                    "channel_time": self.sequence.steps[prev_step + 1].channel_time,
                },
            )

        if self.app is not None and self.app.midi is not None:
            self.app.midi.button_off("playback.go_back")

    def run(self) -> None:
        if self.sequence.last == 2:
            return

        prev_step = self.sequence.position - 1
        self._capture_start_levels()

        go_back_time = 0.0
        if self.app is not None:
            go_back_time = (
                typing.cast(typing.Any, self.app.settings).get_double("go-back-time")
                * 1000
            )
        pause_time = 0.0
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time
        start_pause = None
        while i < go_back_time and not self._stopevent.is_set():
            if not self.pause.is_set():
                if not start_pause:
                    start_pause = time.time() * 1000
                self.pause.wait()
                pause_time += (time.time() * 1000) - start_pause
            else:
                start_pause = None
                self.update_levels(go_back_time, i, self.sequence.position)
                time.sleep(0.05)
                i = (time.time() * 1000) - (start_time + pause_time)

        self._finalize_goback(prev_step)

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()

    def update_levels(self, go_back_time: float, i: float, position: int) -> None:
        """Update levels

        Args:
            go_back_time: Default GoBack time
            i: Time spent
            position: Step
        """
        val = round((255 / go_back_time) * i)
        if self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(val)
            self.app.crossfade.scale_b.set_value(val)

        # Emit event for GUI (GuiEventBridge)
        if self.app is not None:
            core = getattr(self.app, "core", self.app)
            core.emit(
                "playback.goback_progress",
                {
                    "time_spent": i,
                    "goback_time": go_back_time,
                    "position": position,
                    "progress_val": val,
                },
            )

        # Array-based fade
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = get_cue(self.sequence.steps[position - 1]).channels_array.astype(
            np.int32
        )
        factor = i / go_back_time
        diff = (next_levels - old_levels) * factor
        lvls = np.round(old_levels + diff).astype(np.int32)

        self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0, 255).astype(np.uint8)
        self.backend.dmx.set_levels()
