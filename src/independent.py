# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
import mido

from olc.define import App, MAX_CHANNELS


class Independent:
    """Independent object
    Control channels excluded from recording

    Attributes:
        number (int): independent number
        level (int): independent level (0-255)
        channels (set): channels present in independent
        levels (Dict[int, int]): channels levels
        text (str): independent text
        inde_type (str): knob or button
        dmx (array): DMX levels
    """

    def __init__(
        self,
        number,
        text="",
        levels=None,
        inde_type="knob",
    ):
        self.number = number
        self.level = 0
        self.channels = set()
        self.levels = levels or {}
        self.text = text
        self.inde_type = inde_type
        self.dmx = array.array("B", [0] * MAX_CHANNELS)

        self.update_channels()

    def update_channels(self):
        """Update set of channels"""
        for channel, level in self.levels.items():
            if level:
                self.channels.add(channel)

    def set_levels(self, levels):
        """Define channels and levels

        Args:
            levels (Dict[int, int]): channels levels
        """
        self.levels = levels
        self.channels = {channel for channel, level in levels.items() if level}

    def set_level(self, value: int) -> None:
        """Set independent level

        Args:
            value: New level
        """
        # Send MIDI message to knob leds
        midi_name = f"inde_{self.number}"
        channel, control = App().midi.control_change.control_change[midi_name]
        if control != -1:
            msg = mido.Message(
                "control_change",
                channel=channel,
                control=47 + self.number,
                value=32 + int((value / 255) * 12),
                time=0,
            )
            App().midi.queue.enqueue(msg)
        self.level = value
        self.update_dmx()

    def update_dmx(self):
        """Update DMX levels"""
        for channel, level in self.levels.items():
            dmx_lvl = round(level * (self.level / 255))
            self.dmx[channel - 1] = dmx_lvl
            next_level = App().sequence.get_next_channel_level(channel, dmx_lvl)
            App().window.live_view.update_channel_widget(channel, next_level)
        App().independents.update_dmx()
        App().dmx.set_levels(self.channels)


class Independents:
    """All independents

    Attributes:
        independents (list): list of independents
        channels (set): list of channels present in independents
    """

    def __init__(self):
        self.independents = []
        self.channels = set()
        self.dmx = array.array("B", [0] * MAX_CHANNELS)

        # Create 9 Independents
        for i in range(6):
            self.add(Independent(i + 1))
        for i in range(6, 9):
            self.add(Independent(i + 1, inde_type="button"))

    def update_dmx(self):
        """Update DMX levels"""
        for channel in self.channels:
            channel -= 1
            level_inde = -1
            for inde in self.independents:
                if channel + 1 in inde.channels and inde.dmx[channel] > level_inde:
                    level_inde = inde.dmx[channel]
            if level_inde != -1:
                self.dmx[channel] = level_inde

    def add(self, independent):
        """Add an independent

        Args:
            independent: Independent object

        Returns:
            True or False
        """
        number = independent.number
        for inde in self.independents:
            if inde.number == number:
                print("Independent already exist")
                return False
        self.independents.append(independent)
        self.update_channels()
        return True

    def update(self, independent):
        """Update independent

        Args:
            independent: Independent object
        """
        number = independent.number
        text = independent.text
        levels = independent.levels
        self.independents[number - 1].text = text
        self.independents[number - 1].set_levels(levels)
        self.update_channels()

    def get_channels(self):
        """
        Returns:
            (set) channels presents in all independent
        """
        return self.channels

    def update_channels(self):
        """Update set of channels present in all independents"""
        self.channels = set()
        for inde in self.independents:
            self.channels = self.channels | inde.channels
