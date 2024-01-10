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

from olc.define import MAX_CHANNELS, App
from olc.sequence import update_ui


class Scale:
    """For faders"""

    def __init__(self):
        self.value = 0
        self.moved = False

    def set_value(self, value):
        """Set scale value

        Args:
            value: int
        """
        if 0 <= value < 256:
            self.value = value

    def get_value(self):
        """Return scale value

        Returns:
            int
        """
        return self.value


class CrossFade:
    """For Manual Crossfade"""

    def __init__(self):
        self.scale_a = Scale()
        self.scale_b = Scale()

        self.manual = False

    def scale_moved(self, scale):
        """On moved

        Args:
            scale: Scale object
        """
        scale.moved = True
        level = scale.get_value()

        if level not in (255, 0):
            App().sequence.on_go = True
            # If Go is sent, stop it
            if (
                App().crossfade.manual
                and App().sequence.thread
                and App().sequence.thread.is_alive()
            ):
                App().sequence.thread.stop()
                App().sequence.thread.join()

        if scale in (self.scale_a, self.scale_b):
            if App().sequence.last == 0:
                # If sequential is empty, don't do anything
                App().sequence.on_go = False
                return
            # Update sliders position
            self.update_slider(scale, level)

        if (
            self.scale_a.get_value() == 255
            and self.scale_b.get_value() == 255
            and self.scale_a.moved
            and self.scale_b.moved
        ):
            # In and Out Crossfades at Full
            self.at_full()

        if self.scale_a.get_value() == 0 and self.scale_b.get_value() == 0:
            # Stop Xfade if return to 0
            if not App().sequence.on_go:
                return
            self.scale_a.moved = False
            self.scale_b.moved = False
            self.manual = False
            App().sequence.on_go = False

    def at_full(self):
        """Slider A and B at Full"""
        if not App().sequence.on_go:
            return
        self.scale_a.moved = False
        self.scale_b.moved = False
        self.manual = False
        App().sequence.on_go = False
        # Empty array of levels enter by user
        App().backend.dmx.levels["user"] = array.array("h", [-1] * MAX_CHANNELS)
        App().sequence.update_channels()
        # Go to next step
        next_step = App().sequence.position + 1
        if next_step < App().sequence.last - 1:
            # Next step
            App().sequence.position += 1
            next_step += 1
        else:
            # Return to first step
            App().sequence.position = 0
            next_step = 1
        # Update UI
        App().window.playback.sequential.total_time = (
            App().sequence.steps[next_step].total_time
        )
        App().window.playback.sequential.time_in = (
            App().sequence.steps[next_step].time_in
        )
        App().window.playback.sequential.time_out = (
            App().sequence.steps[next_step].time_out
        )
        App().window.playback.sequential.delay_in = (
            App().sequence.steps[next_step].delay_in
        )
        App().window.playback.sequential.delay_out = (
            App().sequence.steps[next_step].delay_out
        )
        App().window.playback.sequential.wait = App().sequence.steps[next_step].wait
        App().window.playback.sequential.channel_time = (
            App().sequence.steps[next_step].channel_time
        )
        App().window.playback.sequential.position_a = 0
        App().window.playback.sequential.position_b = 0
        subtitle = (
            f"Mem. :{App().sequence.steps[App().sequence.position].cue.memory} "
            f"{App().sequence.steps[App().sequence.position].text} "
            f"- Next Mem. : {App().sequence.steps[next_step].cue.memory} "
            f"{App().sequence.steps[next_step].text}"
        )
        update_ui(App().sequence.position, subtitle)
        # If Wait
        if App().sequence.steps[next_step].wait:
            App().sequence.on_go = False
            App().sequence.do_go(None, None)

    def update_slider(self, scale, level):
        """Update sliders position

        Args:
            scale: Scale object
            level: int
        """
        total_time = App().sequence.steps[App().sequence.position + 1].total_time * 1000
        wait = App().sequence.steps[App().sequence.position + 1].wait * 1000
        position = (level / 255) * total_time
        if scale == self.scale_a:
            App().window.playback.sequential.position_a = (
                (App().window.playback.sequential.get_allocation().width - 32)
                / total_time
            ) * position
        elif scale == self.scale_b:
            App().window.playback.sequential.position_b = (
                (App().window.playback.sequential.get_allocation().width - 32)
                / total_time
            ) * position
        App().window.playback.sequential.queue_draw()
        # Update levels
        if position >= wait:
            for channel in range(1, MAX_CHANNELS + 1):
                if not App().backend.patch.is_patched(channel):
                    continue
                old_level = (
                    App()
                    .sequence.steps[App().sequence.position]
                    .cue.channels.get(channel, 0)
                )
                if App().sequence.position < App().sequence.last - 1:
                    next_level = (
                        App()
                        .sequence.steps[App().sequence.position + 1]
                        .cue.channels.get(channel, 0)
                    )
                else:
                    next_level = App().sequence.steps[0].cue.channels.get(channel, 0)
                if scale == self.scale_a:
                    update_a(channel, old_level, next_level, wait, position)
                elif scale == self.scale_b:
                    # Get SequentialWindow's width to place cursor
                    update_b(channel, old_level, next_level, wait, position)
                App().window.live_view.update_channel_widget(channel, next_level)
            App().backend.dmx.set_levels(App().sequence.channels)


def update_a(channel, old_level, next_level, wait, pos):
    """Update channel level with A Slider

    Args:
        channel: Channel to update
        old_level: Old level
        next_level: Next level
        wait: Wait value
        pos: Position in xfade
    """
    time_out = App().sequence.steps[App().sequence.position + 1].time_out * 1000
    delay_out = App().sequence.steps[App().sequence.position + 1].delay_out * 1000
    # Channel Time
    lvl = _update_a_channel_time(channel, old_level, next_level, wait, pos)
    user_level = App().backend.dmx.levels["user"][channel - 1]
    if user_level != -1 and next_level < user_level:
        # Update channel level with user changed
        if pos <= wait + delay_out:
            lvl = old_level
        elif wait + delay_out < pos < time_out + wait + delay_out:
            lvl = user_level - abs(
                int(((next_level - user_level) / time_out) * (pos - wait - delay_out))
            )
        else:
            lvl = next_level
    elif next_level < old_level:
        # Normal sequential
        if pos <= wait + delay_out:
            lvl = old_level
        elif wait + delay_out < pos < time_out + wait + delay_out:
            lvl = old_level - abs(
                int(
                    round(
                        ((next_level - old_level) / time_out) * (pos - wait - delay_out)
                    )
                )
            )
        else:
            lvl = next_level
    if lvl != -1:
        App().backend.dmx.levels["sequence"][channel - 1] = lvl


def _update_a_channel_time(channel, old_level, next_level, wait, pos):
    """Update channel level in Channel Time

    Args:
        channel: Channel to update
        old_level: Old level
        next_level: Next level
        wait: Wait value
        pos: Position in xfade

    Returns:
        channel level or -1
    """
    lvl = -1
    channel_time = App().sequence.steps[App().sequence.position + 1].channel_time
    if channel in channel_time and next_level < old_level:
        ct_delay = channel_time[channel].delay * 1000
        ct_time = channel_time[channel].time * 1000
        if pos < ct_delay + wait:
            lvl = old_level
        elif ct_delay + wait <= pos < ct_delay + ct_time + wait:
            lvl = old_level - abs(
                int(((next_level - old_level) / ct_time) * (pos - ct_delay - wait))
            )
        else:
            lvl = next_level
    return lvl


def update_b(channel, old_level, next_level, wait, pos):
    """Update channel level with B Slider

    Args:
        channel: Channel to update
        old_level: Old level
        next_level: Next level
        wait: Wait value
        pos: Position in xfade
    """
    lvl = -1
    time_in = App().sequence.steps[App().sequence.position + 1].time_in * 1000
    delay_in = App().sequence.steps[App().sequence.position + 1].delay_in * 1000
    # Channel Time
    lvl = _update_b_channel_time(channel, old_level, next_level, wait, pos)
    user_level = App().backend.dmx.levels["user"][channel - 1]
    if user_level != -1 and next_level > user_level:
        # User change channel's value
        if pos <= wait + delay_in:
            lvl = old_level
        elif wait + delay_in < pos < time_in + wait + delay_in:
            lvl = int(
                ((next_level - user_level) / time_in) * (pos - wait - delay_in)
                + user_level
            )
        else:
            lvl = next_level
    elif next_level > old_level:
        # Normal channel
        if pos <= wait + delay_in:
            lvl = old_level
        elif wait + delay_in < pos < time_in + wait + delay_in:
            lvl = int(
                ((next_level - old_level) / time_in) * (pos - wait - delay_in)
                + old_level
            )
        else:
            lvl = next_level
    if lvl != -1:
        App().backend.dmx.levels["sequence"][channel - 1] = lvl


def _update_b_channel_time(channel, old_level, next_level, wait, pos):
    """Update channel level in Channel Time

    Args:
        channel: Channel to update
        old_level: Old level
        next_level: Next level
        wait: Wait value
        pos: Position in xfade

    Returns:
        channel level or -1
    """
    lvl = -1
    channel_time = App().sequence.steps[App().sequence.position + 1].channel_time
    if channel in channel_time and next_level > old_level:
        # Channel Time
        ct_delay = channel_time[channel].delay * 1000
        ct_time = channel_time[channel].time * 1000
        if pos < ct_delay + wait:
            lvl = old_level
        elif ct_delay + wait <= pos < ct_delay + ct_time + wait:
            lvl = int(
                ((next_level - old_level) / ct_time) * (pos - ct_delay - wait)
                + old_level
            )
        else:
            lvl = next_level
    return lvl
