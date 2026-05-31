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
from gi.repository import GLib, Pango
from olc.cue import Cue
from olc.define import MAX_CHANNELS, App
from olc.step import Step

if typing.TYPE_CHECKING:
    from gi.repository import Gio


def update_ui(subtitle: str) -> None:
    """Update user interface when Step is in scene

    Args:
        subtitle: Memories number in header bar
    """
    # Update Sequential Tab
    App().window.playback.update_active_cues_display()
    App().window.playback.grid.queue_draw()
    # Cue times
    App().window.playback.display_times()
    # Update Main Window's Subtitle
    App().window.header.set_subtitle(subtitle)
    # Virtual Console crossfade
    if App().virtual_console and App().virtual_console.props.visible:
        if App().virtual_console.scale_a.get_inverted():
            App().virtual_console.scale_a.set_inverted(False)
            App().virtual_console.scale_b.set_inverted(False)
        else:
            App().virtual_console.scale_a.set_inverted(True)
            App().virtual_console.scale_b.set_inverted(True)
        App().virtual_console.scale_a.set_value(0)
        App().virtual_console.scale_b.set_value(0)


# pylint: disable=too-many-instance-attributes
class Sequence:
    """Sequence Object
    A Sequence is a collection of Steps
    """

    index: float
    type_seq: str
    text: str
    thread: Optional[ThreadGo | ThreadGoBack]

    def __init__(self, index: float, type_seq: str = "Normal", text: str = "") -> None:
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.cues = set()
        self.steps: list[Step] = []
        self.position = 0
        self.last = 0
        # Flag to know if we have a Go in progress
        self.on_go = False
        # Channels present in this sequence
        # self.channels = array.array("B", [0] * MAX_CHANNELS)
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

    def stop(self) -> bool:
        """Stop Go

        Returns:
            True if Go to stop, else False
        """
        if self.on_go and self.thread:
            App().midi.button_off("go")
            # Switch off Pause Led
            if not self.thread.pause.is_set():
                App().midi.messages.notes.led_pause_off()
                if App().virtual_console:
                    App().virtual_console.pause.pressed = False
                    App().virtual_console.pause.queue_draw()
            # Stop actual Thread
            self.thread.pause.set()
            self.thread.stop()
            self.thread.join()
            self.on_go = False
            # Stop at the end
            self.position = min(self.position, self.last - 3)
            return True
        return False

    def update_channels(self) -> None:
        """Update channels present in sequence"""
        self.channels.clear()
        for step in self.steps:
            for channel in step.cue.channels:
                self.channels.add(channel)
        for channel, level in enumerate(App().backend.dmx.levels["user"]):
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
            if item.cue.memory == cue:
                found = True
                break
            step += 1
        step -= 1
        # If new Cue, find step index
        if not found:
            exist = False
            step = 0
            for item in self.steps:
                if item.cue.memory > cue:
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
        memory = self.steps[step].cue.memory
        if step >= self.last - 1:
            return memory + 1

        next_memory = self.steps[step + 1].cue.memory
        return (
            ((next_memory - memory) / 2) + memory
            if next_memory != 0.0 and (next_memory - memory) <= 1
            else memory + 1
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
            next_level = self.steps[self.position + 1].cue.channels.get(channel, 0)
        elif self.last:
            next_level = self.steps[0].cue.channels.get(channel, 0)
        else:
            next_level = level
        return next_level

    def sequence_plus(self) -> None:
        """Sequence +"""
        App().midi.button_on("seq_plus", 0.1)
        self.stop()

        # Jump to next Step
        position = self.position
        position += 1
        if position < self.last - 1:  # Stop on the last cue
            self.position += 1
            App().window.playback.sequential.total_time = self.steps[
                position + 1
            ].total_time
            App().window.playback.sequential.time_in = self.steps[position + 1].time_in
            App().window.playback.sequential.time_out = self.steps[
                position + 1
            ].time_out
            App().window.playback.sequential.delay_in = self.steps[
                position + 1
            ].delay_in
            App().window.playback.sequential.delay_out = self.steps[
                position + 1
            ].delay_out
            App().window.playback.sequential.wait = self.steps[position + 1].wait
            App().window.playback.sequential.channel_time = self.steps[
                position + 1
            ].channel_time
            App().window.playback.sequential.position_a = 0
            App().window.playback.sequential.position_b = 0

            # Window's subtitle
            subtitle = (
                f"Mem. : {self.steps[position].cue.memory} {self.steps[position].text}"
                f" - Next Mem. : {self.steps[position + 1].cue.memory} "
                f"{self.steps[position + 1].text}"
            )
            # Update display
            update_ui(subtitle)

            # Empty DMX user array
            App().backend.dmx.levels["user"].fill(-1)
            self.update_channels()

            # Send DMX values
            App().backend.dmx.levels["sequence"][:] = (
                self.steps[position].cue.channels_array
            )
            App().backend.dmx.set_levels()

    def sequence_minus(self) -> None:
        """Sequence -"""
        App().midi.button_on("seq_minus", 0.1)
        self.stop()

        # Jump to previous Step
        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1
            # Always use times for next cue
            App().window.playback.sequential.total_time = self.steps[
                position + 1
            ].total_time
            App().window.playback.sequential.time_in = self.steps[position + 1].time_in
            App().window.playback.sequential.time_out = self.steps[
                position + 1
            ].time_out
            App().window.playback.sequential.delay_in = self.steps[
                position + 1
            ].delay_in
            App().window.playback.sequential.delay_out = self.steps[
                position + 1
            ].delay_out
            App().window.playback.sequential.wait = self.steps[position + 1].wait
            App().window.playback.sequential.channel_time = self.steps[
                position + 1
            ].channel_time
            App().window.playback.sequential.position_a = 0
            App().window.playback.sequential.position_b = 0

            # Window's subtitle
            subtitle = (
                f"Mem. : {self.steps[position].cue.memory} {self.steps[position].text}"
                f" - Next Mem. : {self.steps[position + 1].cue.memory} "
                f"{self.steps[position + 1].text}"
            )
            # Update display
            update_ui(subtitle)

            # Empty DMX user array
            App().backend.dmx.levels["user"].fill(-1)
            self.update_channels()

            # Send DMX values
            App().backend.dmx.levels["sequence"][:] = (
                self.steps[position].cue.channels_array
            )
            App().backend.dmx.set_levels()

    def goto(self, keystring: str) -> None:
        """Jump to cue number

        Args:
            keystring: Memory number
        """
        old_pos = self.position

        if not keystring:
            return

        # Scan all cues
        for i, step in enumerate(self.steps):
            # Until we find the good one
            if float(step.cue.memory) == float(keystring):
                # Position to the one just before
                self.position = i - 1
                # position = self.position
                next_step = self.position + 1
                # Redraw Sequential window with new times
                App().window.playback.sequential.total_time = self.steps[
                    next_step
                ].total_time
                App().window.playback.sequential.time_in = self.steps[next_step].time_in
                App().window.playback.sequential.time_out = self.steps[
                    next_step
                ].time_out
                App().window.playback.sequential.delay_in = self.steps[
                    next_step
                ].delay_in
                App().window.playback.sequential.delay_out = self.steps[
                    next_step
                ].delay_out
                App().window.playback.sequential.wait = self.steps[next_step].wait
                App().window.playback.sequential.channel_time = self.steps[
                    next_step
                ].channel_time
                App().window.playback.sequential.position_a = 0
                App().window.playback.sequential.position_b = 0

                # Update user interface
                App().window.playback.cues_liststore1[old_pos][9] = "#232729"
                App().window.playback.cues_liststore1[old_pos][10] = Pango.Weight.NORMAL
                App().window.playback.update_active_cues_display()
                App().window.playback.grid.queue_draw()

                # Launch Go
                self.do_go(None, True)
                break

    def do_go(self, _action: Optional[Gio.SimpleAction], goto: bool) -> None:
        """Go

        Args:
            goto: True if Goto, False if Go
        """
        App().midi.button_on("go")
        # If Go is active, go to next memory
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
            App().window.playback.sequential.total_time = self.steps[
                position + 1
            ].total_time
            App().window.playback.sequential.time_in = self.steps[position + 1].time_in
            App().window.playback.sequential.time_out = self.steps[
                position + 1
            ].time_out
            App().window.playback.sequential.delay_in = self.steps[
                position + 1
            ].delay_in
            App().window.playback.sequential.delay_out = self.steps[
                position + 1
            ].delay_out
            App().window.playback.sequential.wait = self.steps[position + 1].wait
            App().window.playback.sequential.channel_time = self.steps[
                position + 1
            ].channel_time
            App().window.playback.sequential.position_a = 0
            App().window.playback.sequential.position_b = 0

            # Set main window's subtitle
            subtitle = (
                f"Mem. : {self.steps[position].cue.memory} "
                f"{self.steps[position].text} - Next Mem. : "
                f"{self.steps[position + 1].cue.memory} "
                f"{self.steps[position + 1].text}"
            )

            # Update Sequential Tab
            App().window.playback.update_active_cues_display()
            App().window.playback.grid.queue_draw()
            App().window.playback.display_times()
            # Update Main Window's Subtitle
            App().window.header.set_subtitle(subtitle)

            self.do_go(None, False)

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

        App().midi.button_on("go_back")
        self.stop()

        goback_time = App().settings.get_double("go-back-time")

        App().window.playback.sequential.total_time = goback_time
        App().window.playback.sequential.time_in = goback_time
        App().window.playback.sequential.time_out = goback_time
        App().window.playback.sequential.delay_in = 0
        App().window.playback.sequential.delay_out = 0
        App().window.playback.sequential.wait = 0
        App().window.playback.sequential.channel_time = {}
        App().window.playback.sequential.position_a = 0
        App().window.playback.sequential.position_b = 0

        App().window.playback.grid.queue_draw()

        subtitle = (
            f"Mem. : {self.steps[position].cue.memory} {self.steps[position].text}"
            f" - Next Mem. : {self.steps[position - 1].cue.memory} "
            f"{self.steps[position - 1].text}"
        )
        App().window.header.set_subtitle(subtitle)

        self.on_go = True
        self.thread = ThreadGoBack(self)
        self.thread.start()
        return False

    def pause(self, _action: Optional[Gio.SimpleAction], _param: None) -> None:
        """Toggle pause"""
        if self.thread:
            if self.thread.pause.is_set():
                self.thread.pause.clear()
            else:
                self.thread.pause.set()


# pylint: disable=too-many-instance-attributes
class ThreadGo(threading.Thread):
    """Thread object for Go"""

    def __init__(self, goto: bool, sequence: Sequence) -> None:
        threading.Thread.__init__(self)
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

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels when Go is sent"""
        self.old_channels_levels = App().backend.dmx.levels["sequence"].copy()
        user_levels = App().backend.dmx.levels["user"]
        user_mask = user_levels != -1
        self.old_channels_levels[user_mask] = user_levels[user_mask]

    def _finalize_go(self) -> None:
        """Finish load memory after sequence transition"""
        if self.sequence.position < self.sequence.last - 1:
            target_cue = self.sequence.steps[self.sequence.position + 1].cue
        else:
            target_cue = self.sequence.steps[0].cue

        # Block-copy levels to sequential dmx levels
        App().backend.dmx.levels["sequence"][:] = target_cue.channels_array

        # Distribute DMX levels to frames
        App().backend.dmx.set_levels()

        self.sequence.on_go = False
        App().backend.dmx.levels["user"].fill(-1)
        self.sequence.update_channels()
        next_step = _next_step(self.sequence)
        if self.sequence.steps[next_step].wait:
            self.sequence.do_go(None, False)
        App().midi.button_off("go")

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
        # Update sliders position
        App().window.playback.sequential.position_a = (
            (App().window.playback.sequential.get_allocation().width - 32)
            / self.total_time
        ) * i
        App().window.playback.sequential.position_b = (
            (App().window.playback.sequential.get_allocation().width - 32)
            / self.total_time
        ) * i
        GLib.idle_add(App().window.playback.sequential.queue_draw)
        # Move Virtual Console crossfade
        if App().virtual_console and App().virtual_console.props.visible:
            val = round((255 / self.total_time) * i)
            GLib.idle_add(App().virtual_console.scale_a.set_value, val)
            GLib.idle_add(App().virtual_console.scale_b.set_value, val)
        # Show times left
        GLib.idle_add(App().window.playback.show_timeleft, i)
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

        App().backend.dmx.levels["sequence"][:] = np.clip(lvls, 0, 255).astype(np.uint8)
        App().backend.dmx.set_levels()

    def _calculate_transitions_go(
        self, i: float, step: Step
    ) -> np.ndarray:
        """Calculate fade levels using array operations."""
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = step.cue.channels_array.astype(np.int32)
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
                factor = (i - self.wait - step.delay_in * 1000) / (
                    step.time_in * 1000
                )
                diff = (next_levels - old_levels) * factor
                attack_lvls = np.round(old_levels + diff).astype(np.int32)
                lvls[progress_mask & attack_mask] = attack_lvls[
                    progress_mask & attack_mask
                ]

            end_mask = i >= (step.time_in + step.wait + step.delay_in) * 1000
            lvls[end_mask & attack_mask] = next_levels[end_mask & attack_mask]

        return lvls

    def _apply_channel_times_go(
        self, lvls: np.ndarray, i: float, step: Step
    ) -> None:
        """Apply individual channel times."""
        if not step.channel_time:
            return
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = step.cue.channels_array.astype(np.int32)
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
    # Update times for visual crossfade
    App().window.playback.sequential.total_time = sequence.steps[next_step].total_time
    App().window.playback.sequential.time_in = sequence.steps[next_step].time_in
    App().window.playback.sequential.time_out = sequence.steps[next_step].time_out
    App().window.playback.sequential.delay_in = sequence.steps[next_step].delay_in
    App().window.playback.sequential.delay_out = sequence.steps[next_step].delay_out
    App().window.playback.sequential.wait = sequence.steps[next_step].wait
    App().window.playback.sequential.channel_time = sequence.steps[
        next_step
    ].channel_time
    App().window.playback.sequential.position_a = 0
    App().window.playback.sequential.position_b = 0
    # Main window's subtitle
    subtitle = (
        f"Mem. : {sequence.steps[sequence.position].cue.memory} "
        f"{sequence.steps[sequence.position].text} - Next Mem. : "
        f"{sequence.steps[next_step].cue.memory} "
        f"{sequence.steps[next_step].text}"
    )
    # Update Gtk in main thread
    GLib.idle_add(update_ui, subtitle)
    return next_step


class ThreadGoBack(threading.Thread):
    """Thread Object for Go Back"""

    def __init__(self, sequence: Sequence) -> None:
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        # To save channels levels when Go Back starts
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels when Go Back starts"""
        self.old_channels_levels = App().backend.dmx.levels["sequence"].copy()
        user_levels = App().backend.dmx.levels["user"]
        user_mask = user_levels != -1
        self.old_channels_levels[user_mask] = user_levels[user_mask]

    def _finalize_goback(self, prev_step: int) -> None:
        """Finish load memory after sequence transition"""
        target_cue = self.sequence.steps[prev_step].cue

        # Block-copy levels to sequential dmx levels
        App().backend.dmx.levels["sequence"][:] = target_cue.channels_array

        # Distribute DMX levels to frames
        App().backend.dmx.set_levels()

        self.sequence.on_go = False
        App().backend.dmx.levels["user"].fill(-1)
        self.sequence.update_channels()
        self.sequence.position = prev_step
        App().window.playback.sequential.time_in = self.sequence.steps[
            prev_step + 1
        ].time_in
        App().window.playback.sequential.time_out = self.sequence.steps[
            prev_step + 1
        ].time_out
        App().window.playback.sequential.delay_in = self.sequence.steps[
            prev_step + 1
        ].delay_in
        App().window.playback.sequential.delay_out = self.sequence.steps[
            prev_step + 1
        ].delay_out
        App().window.playback.sequential.wait = self.sequence.steps[prev_step + 1].wait
        App().window.playback.sequential.total_time = self.sequence.steps[
            prev_step + 1
        ].total_time
        App().window.playback.sequential.channel_time = self.sequence.steps[
            prev_step + 1
        ].channel_time
        App().window.playback.sequential.position_a = 0
        App().window.playback.sequential.position_b = 0

        subtitle = (
            f"Mem. : {self.sequence.steps[prev_step].cue.memory} "
            f"{self.sequence.steps[prev_step].text} - Next Mem. : "
            f"{self.sequence.steps[prev_step + 1].cue.memory} "
            f"{self.sequence.steps[prev_step + 1].text}"
        )
        GLib.idle_add(update_ui, subtitle)
        App().midi.button_off("go_back")

    def run(self) -> None:
        if self.sequence.last == 2:
            return

        prev_step = self.sequence.position - 1
        self._capture_start_levels()

        go_back_time = App().settings.get_double("go-back-time") * 1000
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
        # Update sliders position
        allocation = App().window.playback.sequential.get_allocation()
        App().window.playback.sequential.position_a = (
            (allocation.width - 32) / go_back_time
        ) * i
        App().window.playback.sequential.position_b = (
            (allocation.width - 32) / go_back_time
        ) * i
        GLib.idle_add(App().window.playback.sequential.queue_draw)
        # Move Virtual Console crossfade
        if App().virtual_console and App().virtual_console.props.visible:
            val = round((255 / go_back_time) * i)
            GLib.idle_add(App().virtual_console.scale_a.set_value, val)
            GLib.idle_add(App().virtual_console.scale_b.set_value, val)
        # Countdown
        GLib.idle_add(App().window.playback.goback_countdown, i, go_back_time, position)

        # Array-based fade
        old_levels = self.old_channels_levels.astype(np.int32)
        next_levels = (
            self.sequence.steps[position - 1]
            .cue.channels_array.astype(np.int32)
        )
        factor = i / go_back_time
        diff = (next_levels - old_levels) * factor
        lvls = np.round(old_levels + diff).astype(np.int32)

        App().backend.dmx.levels["sequence"][:] = np.clip(lvls, 0, 255).astype(np.uint8)
        App().backend.dmx.set_levels()
