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
from enum import IntEnum

import numpy as np
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.cue import Cue
    from olc.fader_bank import FaderBank
    from olc.group import Group
    from olc.main_fader import MainFader
    from olc.sequence import Sequence


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
    contents: object

    def __init__(self, index: int, fader_bank: FaderBank) -> None:
        self.index = index
        self.fader_bank = fader_bank
        self.text = ""
        # Fader level (0.0 - 1.0)
        self.level = 0.0
        self.old_level = 0.0
        self.contents = None

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.fader_bank.app

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
        if self.app and hasattr(self.app, "midi") and self.app.midi:
            self.app.midi.messages.control_change.send(midi_name, round(level * 127))
            self.app.midi.messages.pitchwheel.send(
                midi_name, round(level * 16383) - 8192
            )
        # OSC
        if self.app and hasattr(self.app, "engine") and self.app.engine is not None:
            page = 1
            index = self.index
            path = f"/olc/fader/{page}/{index}/level"
            self.app.engine.send_osc(path, round(level * 255))

    def flash_on(self) -> None:
        """Flash fader at full"""
        self.old_level = self.level
        self.set_level(1.0)
        app_any = typing.cast(typing.Any, self.app)
        if (
            app_any
            and hasattr(app_any, "virtual_console")
            and app_any.virtual_console is not None
        ):
            app_any.virtual_console.faders[self.index - 1].set_value(255)

    def flash_off(self) -> None:
        """Stop flash"""
        self.set_level(self.old_level)
        app_any = typing.cast(typing.Any, self.app)
        if (
            app_any
            and hasattr(app_any, "virtual_console")
            and app_any.virtual_console is not None
        ):
            app_any.virtual_console.faders[self.index - 1].set_value(
                round(self.old_level * 255)
            )

    def level_changed(self) -> None:
        """Fader level has changed"""


class FaderMain(Fader):
    """Fader with MainFader"""

    contents: MainFader | None

    def __init__(self, index: int, fader_bank: FaderBank) -> None:
        super().__init__(index, fader_bank)
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            self.contents = self.app.backend.dmx.main_fader
        else:
            self.contents = None
        self.text = "Main Fader"
        self.level = self.contents.get_level() if self.contents else 0.0

    def level_changed(self) -> None:
        """Fader level has changed"""
        if self.contents:
            self.contents.set_level(self.level)
        if self.app and hasattr(self.app, "window") and self.app.window is not None:
            app_any = typing.cast(typing.Any, self.app)
            app_any.window.main_fader.queue_draw()
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            self.app.backend.dmx.set_levels()


class FaderGroup(Fader):
    """Fader with group"""

    contents: Group | None
    dmx: np.ndarray
    channels: set

    def __init__(
        self, index: int, fader_bank: FaderBank, group: Group | None = None
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = group
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        # Channels used by fader
        self.channels = set()
        if group:
            self.text = group.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        if self.contents is None:
            return
        for channel in self.contents.get_channels():
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
            for channel, lvl in self.contents.get_channels().items():
                level = round(lvl * self.level)
                self.dmx[channel - 1] = level
            self.fader_bank.update_levels()
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()


class FaderPreset(Fader):
    """Fader with preset"""

    contents: Cue | None
    dmx: np.ndarray
    channels: set

    def __init__(
        self, index: int, fader_bank: FaderBank, cue: Cue | None = None
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = cue
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        # Channels used by fader
        self.channels = set()
        if cue:
            self.text = cue.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        if self.contents is None:
            return
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
            self.fader_bank.update_levels()
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()


class FaderChannels(Fader):
    """Fader with channels"""

    contents: dict[int, int] | None
    dmx: np.ndarray
    channels: set

    def __init__(
        self, index: int, fader_bank: FaderBank, channels: dict[int, int] | None = None
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = channels
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
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
            self.fader_bank.update_levels()
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()


class FaderSequence(Fader):
    """Fader with sequence"""

    contents: Sequence | None
    dmx: np.ndarray
    channels: set

    def __init__(
        self, index: int, fader_bank: FaderBank, chaser: Sequence | None = None
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = chaser
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        # Channels used by fader
        self.channels = set()
        if chaser:
            self.text = chaser.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        if self.contents is None:
            return
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
        if self.contents is None:
            return
        chaser = typing.cast(typing.Any, self.contents)
        # If it was not running and fader > 0
        if self.level and chaser.run is False:
            # Start chaser
            chaser.run = True
            chaser.thread = ThreadChaser(self)
            chaser.thread.start()
        # If it was running and fader > 0
        elif self.level and chaser.run is True:
            # Update max level
            chaser.thread.level_scale = round(self.level * 255)
        # If it was running and fader go to 0
        elif self.level == 0 and chaser.run is True:
            # Stop chaser
            chaser.run = False
            chaser.thread.stop()
            chaser.thread.join()
            for channel in self.channels:
                self.dmx[channel - 1] = 0
            self.fader_bank.update_levels()
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()


class ThreadChaser(threading.Thread):
    """Thread for chasers"""

    def __init__(self, fader: FaderSequence) -> None:
        super().__init__()
        self.fader = fader
        self._stopevent = threading.Event()

    def run(self) -> None:
        position = 0
        chaser = typing.cast(typing.Any, self.fader.contents)
        if chaser is None:
            return
        while chaser.run:
            if position != chaser.last - 1:
                t_in = chaser.steps[position + 1].time_in
                t_out = chaser.steps[position + 1].time_out
            else:
                t_in = chaser.steps[1].time_in
                t_out = chaser.steps[1].time_out
            t_max = max([t_in, t_out])

            start_time = time.time() * 1000
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            while i < delay and chaser.run:
                self.update_levels(delay_in, delay_out, i, position)
                time.sleep(0.025)
                i = (time.time() * 1000) - start_time

            position += 1
            if position == chaser.last:
                position = 1

    def stop(self) -> None:
        """Stop thread"""
        self._stopevent.set()

    def update_levels(
        self, delay_in: float, delay_out: float, i: float, position: int
    ) -> None:
        """Update levels

        Args:
            delay_in: Time In
            delay_out: Time Out
            i: Time spent
            position: Step
        """
        chaser = typing.cast(typing.Any, self.fader.contents)
        if chaser is None:
            return
        # Only fader channels
        for channel in self.fader.channels:
            cue = chaser.steps[position].cue
            old_level = cue.channels.get(channel, 0) if cue else 0
            lightshow = self.fader.fader_bank.lightshow
            if lightshow and lightshow.main_playback:
                step_obj = lightshow.main_playback.steps[
                    lightshow.main_playback.position
                ]
                if step_obj and step_obj.cue:
                    seq_level = step_obj.cue.channels.get(channel, 0)
                else:
                    seq_level = 0
            else:
                seq_level = 0
            old_level = max(old_level, seq_level)
            # Loop on cues
            if position < chaser.last - 1:
                next_cue = chaser.steps[position + 1].cue
                next_level = next_cue.channels.get(channel, 0) if next_cue else 0
                next_level = max(next_level, seq_level)
            else:
                next_cue = chaser.steps[1].cue
                next_level = next_cue.channels.get(channel, 0) if next_cue else 0
                next_level = max(next_level, seq_level)
                chaser.position = 1
            # If level increases, use time in
            if next_level > old_level and i < delay_in:
                level = int(((next_level - old_level + 1) / delay_in) * i) + old_level
            # If level decreases, use time out
            elif next_level < old_level and i < delay_out:
                level = old_level - abs(
                    int(((next_level - old_level - 1) / delay_out) * i)
                )
            # Else, level is already good
            else:
                level = next_level
            # Apply fader level
            level = round(level * self.fader.level)
            # Update fader level
            self.fader.dmx[channel - 1] = level
        self.fader.fader_bank.update_levels()
        if (
            self.fader.app
            and hasattr(self.fader.app, "backend")
            and self.fader.app.backend
        ):
            self.fader.app.backend.dmx.set_levels()
