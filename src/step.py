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
class Step:
    """Step
    A Step is used to store times and a Cue in a Sequence
    """

    def __init__(
        self,
        sequence=0,
        cue=None,
        time_in=5.0,
        time_out=5.0,
        delay_in=0.0,
        delay_out=0.0,
        wait=0.0,
        channel_time=None,
        text="",
    ):
        self.sequence = sequence
        self.cue = cue
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        if channel_time is None:
            channel_time = {}
        self.channel_time = channel_time
        self.text = text

        self.update_total_time()

    def update_total_time(self):
        """Calculate Total Time"""
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            self.total_time = self.time_in + self.delay_in + self.wait
        else:
            self.total_time = self.time_out + self.delay_out + self.wait

        for channel in self.channel_time.keys():
            if (
                self.channel_time[channel].delay
                + self.channel_time[channel].time
                + self.wait
                > self.total_time
            ):
                self.total_time = (
                    self.channel_time[channel].delay
                    + self.channel_time[channel].time
                    + self.wait
                )

    def set_time_in(self, time_in):
        """Set Time In

        Args:
            time_in: Time In
        """
        self.time_in = time_in
        self.update_total_time()

    def set_time_out(self, time_out):
        """Set Time Out

        Args:
            time_out: Time Out
        """
        self.time_out = time_out
        self.update_total_time()

    def set_delay_in(self, delay_in):
        """Set Delay In

        Args:
            delay_in: Delay In
        """
        self.delay_in = delay_in
        self.update_total_time()

    def set_delay_out(self, delay_out):
        """Set Delay Out

        Args:
            delay_out: Delay Out
        """
        self.delay_out = delay_out
        self.update_total_time()

    def set_wait(self, wait):
        """Set Wait

        Args:
            wait: Wait
        """
        self.wait = wait
        self.update_total_time()

    def set_time(self, time):
        """Set Time In and Time Out

        Args:
            time: Time
        """
        self.time_in = time
        self.time_out = time
        self.update_total_time()

    def set_delay(self, delay):
        """Set Delay In and Out

        Args:
            delay: Delay
        """
        self.delay_in = delay
        self.delay_out = delay
        self.update_total_time()
