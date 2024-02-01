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
import array
import threading
import time
from enum import IntEnum

from gi.repository import GLib
from olc.define import MAX_CHANNELS, App


def update_channel_display(channel: int) -> None:
    """Update channel levels display in LiveView

    Args:
        channel: Channel number (from 1 to MAX_CHANNELS)
    """
    seq_level = (App().sequence.steps[App().sequence.position].cue.channels.get(
        channel, 0))
    seq_next_level = App().sequence.get_next_channel_level(channel, seq_level)
    GLib.idle_add(
        App().window.live_view.update_channel_widget,
        channel,
        seq_next_level,
    )


class FaderType(IntEnum):
    """Fader types"""

    NONE = 0
    PRESET = 1
    CHANNELS = 2
    SEQUENCE = 3
    GROUP = 13
    GM = 99


class Master:
    """Master object, abstraction for faders

    Attributes:
        page: page number
        number: master number in page
        content_type: 0 = None, 1 = Preset, 2 = Channels, 3 = Sequence,
            13 = Group, 99 = GM
        content_value: number's object or array of channels
        text: text
        value: value (0-255)
    """

    page: int
    number: int
    content_type: int
    content_value: array.array | float
    text: str
    value: float

    def __init__(self, page, number, content_type, content_value):
        self.page = page
        self.number = number
        self.content_type = int(content_type)
        self.content_value = None
        self.text = ""
        # To store DMX values of the master
        self.dmx = array.array("B", [0] * MAX_CHANNELS)
        self.value = 0.0
        self.old_value = 0
        self.channels = set()

        if self.content_type == FaderType.NONE:
            pass
        elif self.content_type == FaderType.PRESET:
            self.content_value = float(content_value)
            if cue := next(mem for mem in App().memories
                           if mem.memory == self.content_value):
                self.text = cue.text
        elif self.content_type == FaderType.CHANNELS:
            self.text += "Ch"
            self.content_value = content_value
            for channel in content_value:
                self.text += f" {channel}"
        elif self.content_type == FaderType.SEQUENCE:
            self.content_value = float(content_value)
            if chaser := next(chsr for chsr in App().chasers
                              if chsr.index == self.content_value):
                self.text = chaser.text
        elif self.content_type == FaderType.GROUP:
            self.content_value = float(content_value)
            if group := next(grp for grp in App().groups
                             if grp.index == self.content_value):
                self.text = group.text
        elif self.content_type == FaderType.GM:
            self.text = "GM"
        else:
            print("Master Type : Unknown")
        self.update_channels()

    def update_channels(self) -> None:
        """Update channels of master"""
        self.channels.clear()
        if self.content_type == FaderType.PRESET:
            if cue := next(mem for mem in App().memories
                           if mem.memory == self.content_value):
                for channel in cue.channels:
                    self.channels.add(channel)
        elif self.content_type == FaderType.CHANNELS:
            for channel in self.content_value:
                self.channels.add(channel)
        elif self.content_type == FaderType.SEQUENCE:
            if chaser := next(chs for chs in App().chasers
                              if chs.index == self.content_value):
                self.channels = chaser.channels
        elif self.content_type == FaderType.GROUP:
            if group := next(grp for grp in App().groups
                             if grp.index == self.content_value):
                for channel in group.channels:
                    self.channels.add(channel)

    def set_content_type(self, content_type: int) -> None:
        """Set content type

        Args:
            content_type: Content type
        """
        self.content_type = content_type
        self.content_value = {} if content_type == FaderType.CHANNELS else -1
        if self.content_type == FaderType.GM:
            self.text = "GM"
            self.value = round(App().backend.dmx.grand_master.get_level() * 255)
        else:
            self.text = ""
        self.channels.clear()

    def set_content_value(self, value: float) -> None:
        """Set content value

        Args:
            value: Content value
        """
        self.content_value = value
        self.text = ""
        if self.content_type == FaderType.PRESET:
            for cue in App().memories:
                if cue.memory == value:
                    self.text = cue.text
                    break
        elif self.content_type == FaderType.GROUP:
            for grp in App().groups:
                if grp.index == value:
                    self.text = grp.text
                    break
        elif self.content_type == FaderType.SEQUENCE:
            for chaser in App().chasers:
                if chaser.index == value:
                    self.text = chaser.text
                    break
        self.update_channels()

    def set_level(self, value: int) -> None:
        """Set master level

        Args:
            value: New level
        """
        # Send MIDI message to faders
        midi_name = f"master_{self.number}"
        App().midi.messages.control_change.send(midi_name, int(value / 2))
        App().midi.messages.pitchwheel.send(midi_name,
                                            int(((value / 255) * 16383) - 8192))
        if App().osc:
            page = 1
            index = self.number
            path = f"olc/fader/{page}/{index}/level"
            App().osc.client.send(path, ("i", value))
        # Set value
        self.value = value
        self.level_changed()

    def flash_on(self) -> None:
        """Flash Master at full"""
        self.old_value = self.value
        self.set_level(255)
        if App().virtual_console:
            App().virtual_console.masters[self.number - 1].set_value(255)

    def flash_off(self) -> None:
        """Stop flash"""
        self.set_level(self.old_value)
        if App().virtual_console:
            App().virtual_console.masters[self.number - 1].set_value(self.old_value)

    def level_changed(self):
        """Master level has changed"""
        # Type : None
        if self.content_type == FaderType.NONE:
            return
        # Type : Preset
        if self.content_type == FaderType.PRESET:
            self._level_changed_preset()
        # Type: Channels
        elif self.content_type == FaderType.CHANNELS:
            self._level_changed_channels()
        # Type: Group
        elif self.content_type == FaderType.GROUP:
            self._level_changed_group()
        # Type: Chaser
        elif self.content_type == FaderType.SEQUENCE:
            self._level_changed_chaser()
        # Type: GM
        elif self.content_type == FaderType.GM:
            self._level_changed_gm()

    def _level_changed_gm(self):
        App().backend.dmx.grand_master.set_level(self.value / 255)
        App().window.grand_master.queue_draw()

    def _level_changed_preset(self):
        """New level and type is Preset"""
        if mem := next(cue for cue in App().memories
                       if cue.memory == self.content_value):
            for channel, level in mem.channels.items():
                level = 0 if self.value == 0 else round(level / (255 / self.value))
                self.dmx[channel - 1] = level
                update_channel_display(channel)
            App().backend.dmx.update_masters()
            App().backend.dmx.set_levels(self.channels)

    def _level_changed_channels(self):
        """New level and type is Channels"""
        for channel, lvl in self.content_value.items():
            level = 0 if self.value == 0 else int(round(lvl / (255 / self.value)))
            self.dmx[channel - 1] = level
            update_channel_display(channel)
        App().backend.dmx.update_masters()
        App().backend.dmx.set_levels(self.channels)

    def _level_changed_group(self):
        """New level and type is Group"""
        # Find group
        if group := next(grp for grp in App().groups
                         if grp.index == self.content_value):
            # Get Channels and Levels in group
            for channel, lvl in group.channels.items():
                # Calculate level
                level = 0 if self.value == 0 else round(lvl / (255 / self.value))
                # Update level in master array
                self.dmx[channel - 1] = level
                update_channel_display(channel)
            App().backend.dmx.update_masters()
            App().backend.dmx.set_levels(self.channels)

    def _level_changed_chaser(self):
        """New level and type is Chaser"""
        number = self.content_value
        # Look for the chaser
        for i, chaser in enumerate(App().chasers):
            if chaser.index == number:
                # If it was not running and master > 0
                if self.value and chaser.run is False:
                    # Start Chaser
                    App().chasers[i].run = True
                    App().chasers[i].thread = ThreadChaser(self, i, self.value)
                    App().chasers[i].thread.start()
                # If it was running and master > 0
                elif self.value and chaser.run is True:
                    # Update Max Level
                    App().chasers[i].thread.level_scale = self.value
                # If it was running an master go to 0
                elif self.value == 0 and chaser.run is True:
                    # Stop Chaser
                    App().chasers[i].run = False
                    App().chasers[i].thread.stop()
                    App().chasers[i].thread.join()
                    for channel in range(MAX_CHANNELS):
                        self.dmx[channel] = 0
                        update_channel_display(channel + 1)
                    App().backend.dmx.update_masters()
                    App().backend.dmx.set_levels(App().chasers[i].channels)
                    break


class ThreadChaser(threading.Thread):
    """Thread for chasers"""

    def __init__(self, master, chaser, level_scale, name=""):
        threading.Thread.__init__(self)
        self.master = master
        self.chaser = chaser
        self.level_scale = level_scale
        self.name = name
        self._stopevent = threading.Event()

    def run(self):
        position = 0

        while App().chasers[self.chaser].run:
            # Next Step Time In and Time Out
            if position != App().chasers[self.chaser].last - 1:
                t_in = App().chasers[self.chaser].steps[position + 1].time_in
                t_out = App().chasers[self.chaser].steps[position + 1].time_out
            else:
                t_in = App().chasers[self.chaser].steps[1].time_in
                t_out = App().chasers[self.chaser].steps[1].time_out

            # Longest Time
            t_max = max([t_in, t_out])

            start_time = time.time() * 1000  # actual time in ms
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            # Loop on longest time
            while i < delay and App().chasers[self.chaser].run:
                # Update levels
                self.update_levels(delay_in, delay_out, i, position)
                time.sleep(0.05)
                i = (time.time() * 1000) - start_time

            position += 1
            if position == App().chasers[self.chaser].last:
                position = 1

    def stop(self):
        """Stop thread"""
        self._stopevent.set()

    def update_levels(self, delay_in, delay_out, i, position):
        """Update levels every 50ms

        Args:
            delay_in: Time In
            delay_out: Time Out
            i: Time spent
            position: Step
        """
        for channel in App().backend.patch.channels:
            # Change only channels in chaser
            if channel in App().chasers[self.chaser].channels:
                # Start level
                old_level = (
                    App().chasers[self.chaser].steps[position].cue.channels.get(
                        channel, 0))
                # Level in the sequence
                seq_level = (
                    App().sequence.steps[App().sequence.position].cue.channels.get(
                        channel, 0))
                old_level = max(old_level, seq_level)
                # Loop on cues and come back at first step
                if position < App().chasers[self.chaser].last - 1:
                    next_level = (App().chasers[self.chaser].steps[position +
                                                                   1].cue.channels.get(
                                                                       channel, 0))
                    next_level = max(next_level, seq_level)
                else:
                    next_level = (App().chasers[self.chaser].steps[1].cue.channels.get(
                        channel, 0))
                    next_level = max(next_level, seq_level)
                    App().chasers[self.chaser].position = 1
                # If level increases, use time In
                if next_level > old_level and i < delay_in:
                    level = (int(
                        ((next_level - old_level + 1) / delay_in) * i) + old_level)
                # If level decreases, use time Out
                elif next_level < old_level and i < delay_out:
                    level = old_level - abs(
                        int(((next_level - old_level - 1) / delay_out) * i))
                # Else, level is already good
                else:
                    level = next_level
                # Apply Grand Master to level
                level = int(round(level / (255 / self.level_scale)))
                # Update master level
                self.master.dmx[channel - 1] = level
                update_channel_display(channel)
        App().backend.dmx.update_masters()
        App().backend.dmx.set_levels(App().chasers[self.chaser].channels)
