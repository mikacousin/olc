# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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

import array
import threading
import time
import typing
from enum import IntEnum
from typing import Any

from gi.repository import GLib
from olc.define import MAX_CHANNELS, App

if typing.TYPE_CHECKING:
    from olc.cue import Cue
    from olc.group import Group
    from olc.main_fader import MainFader
    from olc.sequence import Sequence


def update_channel_display(channel: int) -> None:
    """Update channel levels display in LiveView

    Args:
        channel: Channel number (from 1 to MAX_CHANNELS)
    """
    seq_level = (App().lightshow.main_playback.steps[
        App().lightshow.main_playback.position].cue.channels.get(channel, 0))
    seq_next_level = App().lightshow.main_playback.get_next_channel_level(
        channel, seq_level)
    GLib.idle_add(App().window.live_view.update_channel_widget, channel, seq_next_level)


class FaderType(IntEnum):
    """Fader types"""

    NONE = 0
    PRESET = 1
    CHANNELS = 2
    SEQUENCE = 3
    GROUP = 13
    MAIN = 99


class Fader:
    """Abstraction for physical fader"""

    index: int
    text: str
    level: float
    old_level: float
    contents: Any

    def __init__(self, index: int, fader_bank):
        self.index = index
        self.fader_bank = fader_bank
        self.text = ""
        # Fader level (0.0 - 1.0)
        self.level = 0.0
        self.old_level = 0.0
        self.contents = None

    def set_level(self, level: float) -> None:
        """Set fader level

        Args:
            level: New level
        """
        # Set level
        self.level = level
        self.level_changed()
        # Send MIDI message to faders
        midi_name = f"fader_{self.index}"
        App().midi.messages.control_change.send(midi_name, round(level * 127))
        App().midi.messages.pitchwheel.send(midi_name, round(level * 16383) - 8192)
        # OSC
        if App().osc:
            page = 1
            index = self.index
            path = f"olc/fader/{page}/{index}/level"
            App().osc.client.send(path, ("i", round(level * 255)))

    def flash_on(self) -> None:
        """Flash fader at full"""
        self.old_level = self.level
        self.set_level(1.0)
        if App().virtual_console:
            App().virtual_console.faders[self.index - 1].set_value(255)

    def flash_off(self) -> None:
        """Stop flash"""
        self.set_level(self.old_level)
        if App().virtual_console:
            App().virtual_console.faders[self.index - 1].set_value(
                round(self.old_level * 255))

    def level_changed(self):
        """Fader level has changed"""


class FaderMain(Fader):
    """Fader with MainFader"""

    contents: MainFader

    def __init__(self, index: int, fader_bank):
        super().__init__(index, fader_bank)
        self.contents = App().backend.dmx.main_fader
        self.text = "Main Fader"
        self.level = self.contents.get_level()

    def level_changed(self) -> None:
        """Fader level has changed"""
        self.contents.set_level(self.level)
        App().window.main_fader.queue_draw()


class FaderGroup(Fader):
    """Fader with group"""

    contents: Group
    dmx: array.array
    channels: set

    def __init__(self, index: int, fader_bank, group: Group = None):
        super().__init__(index, fader_bank)
        self.contents = group
        self.dmx = array.array("B", [0] * MAX_CHANNELS)
        # Channels used by fader
        self.channels = set()
        if group:
            self.text = group.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        for channel in self.contents.channels:
            self.channels.add(channel)
        self.fader_bank.update_active_faders()

    def set_contents(self, group: Group) -> None:
        """Set group

        Args:
            group: Fader Group
        """
        self.contents = group
        self.text = self.contents.text
        self.update_channels()

    def level_changed(self) -> None:
        """Fader level has changed"""
        if self.contents:
            for channel, lvl in self.contents.channels.items():
                level = round(lvl * self.level)
                self.dmx[channel - 1] = level
                update_channel_display(channel)
            self.fader_bank.update_levels()
            App().backend.dmx.set_levels(self.channels)


class FaderPreset(Fader):
    """Fader with preset"""

    contents: Cue
    dmx: array.array
    channels: set

    def __init__(self, index: int, fader_bank, cue: Cue = None):
        super().__init__(index, fader_bank)
        self.contents = cue
        self.dmx = array.array("B", [0] * MAX_CHANNELS)
        # Channels used by fader
        self.channels = set()
        if cue:
            self.text = cue.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        for channel in self.contents.channels:
            self.channels.add(channel)
        self.fader_bank.update_active_faders()

    def set_contents(self, cue: Cue) -> None:
        """Set cue

        Args:
            cue: Cue to put in fader
        """
        self.contents = cue
        self.text = self.contents.text
        self.update_channels()

    def level_changed(self) -> None:
        """Fader level has changed"""
        if self.contents:
            for channel, lvl in self.contents.channels.items():
                level = round(lvl * self.level)
                self.dmx[channel - 1] = level
                update_channel_display(channel)
            self.fader_bank.update_levels()
            App().backend.dmx.set_levels(self.channels)


class FaderChannels(Fader):
    """Fader with channels"""

    contents: dict[int, int] | None
    dmx: array.array
    channels: set

    def __init__(self, index: int, fader_bank, channels: dict[int, int] | None = None):
        super().__init__(index, fader_bank)
        self.contents = channels
        self.dmx = array.array("B", [0] * MAX_CHANNELS)
        # Channels used by fader
        self.channels = set()
        if self.contents:
            self.text = "Ch"
            for channel in self.contents:
                self.text += f" {channel}"
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        if self.contents:
            for channel in self.contents:
                self.channels.add(channel)
        self.fader_bank.update_active_faders()

    def set_contents(self, channels: dict[int, int]) -> None:
        """Set cue

        Args:
            channels: Channels with level to put in fader
        """
        self.contents = channels
        if self.contents:
            self.text = "Ch"
            for channel in self.contents:
                self.text += f" {channel}"
        self.update_channels()

    def level_changed(self) -> None:
        """Fader level has changed"""
        if self.contents:
            for channel, lvl in self.contents.items():
                level = round(lvl * self.level)
                self.dmx[channel - 1] = level
                update_channel_display(channel)
            self.fader_bank.update_levels()
            App().backend.dmx.set_levels(self.channels)


class FaderSequence(Fader):
    """Fader with sequence"""

    contents: Sequence
    dmx: array.array
    channels: set

    def __init__(self, index: int, fader_bank, chaser: Sequence = None):
        super().__init__(index, fader_bank)
        self.contents = chaser
        self.dmx = array.array("B", [0] * MAX_CHANNELS)
        # Channels used by fader
        self.channels = set()
        if chaser:
            self.text = chaser.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels = self.contents.channels
        self.fader_bank.update_active_faders()

    def set_contents(self, chaser: Sequence) -> None:
        """Set cue

        Args:
            chaser: Chaser to put in fader
        """
        self.contents = chaser
        self.text = self.contents.text
        self.update_channels()

    def level_changed(self) -> None:
        """Fader level has changed"""
        if not self.contents:
            return
        # If it was not running and fader > 0
        if self.level and self.contents.run is False:
            # Start chaser
            self.contents.run = True
            self.contents.thread = ThreadChaser(self)
            self.contents.thread.start()
        # If it was running and fader > 0
        elif self.level and self.contents.run is True:
            # Update max level
            self.contents.thread.level_scale = round(self.level * 255)
        # If it was running and fader go to 0
        elif self.level == 0 and self.contents.run is True:
            # Stop chaser
            self.contents.run = False
            self.contents.thread.stop()
            self.contents.thread.join()
            for channel in self.channels:
                self.dmx[channel - 1] = 0
                update_channel_display(channel)
            self.fader_bank.update_levels()
            App().backend.dmx.set_levels(self.channels)


class ThreadChaser(threading.Thread):
    """Thread for chasers"""

    def __init__(self, fader):
        super().__init__()
        self.fader = fader
        self._stopevent = threading.Event()

    def run(self) -> None:
        position = 0
        while self.fader.contents.run:
            if position != self.fader.contents.last - 1:
                t_in = self.fader.contents.steps[position + 1].time_in
                t_out = self.fader.contents.steps[position + 1].time_out
            else:
                t_in = self.fader.contents.steps[1].time_in
                t_out = self.fader.contents.steps[1].time_out
            t_max = max([t_in, t_out])

            start_time = time.time() * 1000
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            while i < delay and self.fader.contents.run:
                self.update_levels(delay_in, delay_out, i, position)
                time.sleep(0.025)
                i = (time.time() * 1000) - start_time

            position += 1
            if position == self.fader.contents.last:
                position = 1

    def stop(self) -> None:
        """Stop thread"""
        self._stopevent.set()

    def update_levels(self, delay_in, delay_out, i, position):
        """Update levels

        Args:
            delay_in: Time In
            delay_out: Time Out
            i: Time spent
            position: Step
        """
        chaser = self.fader.contents
        # Only fader channels
        for channel in self.fader.channels:
            old_level = chaser.steps[position].cue.channels.get(channel, 0)
            seq_level = App().lightshow.main_playback.steps[
                App().lightshow.main_playback.position].cue.channels.get(channel, 0)
            old_level = max(old_level, seq_level)
            # Loop on cues
            if position < chaser.last - 1:
                next_level = chaser.steps[position + 1].cue.channels.get(channel, 0)
                next_level = max(next_level, seq_level)
            else:
                next_level = chaser.steps[1].cue.channels.get(channel, 0)
                next_level = max(next_level, seq_level)
                chaser.poition = 1
            # If level increases, use time in
            if next_level > old_level and i < delay_in:
                level = int(((next_level - old_level + 1) / delay_in) * i) + old_level
            # If level decreases, use time out
            elif next_level < old_level and i < delay_out:
                level = old_level - abs(
                    int(((next_level - old_level - 1) / delay_out) * i))
            # Else, level is already good
            else:
                level = next_level
            # Apply fader level
            level = round(level * self.fader.level)
            # Update fader level
            self.fader.dmx[channel - 1] = level
            update_channel_display(channel)
        self.fader.fader_bank.update_levels()
        App().backend.dmx.set_levels(self.fader.channels)
