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
import array
import typing

from olc.define import MAX_CHANNELS
from olc.sequence import update_ui


class Scale:
    """For faders"""

    def __init__(self) -> None:
        self.value = 0
        self.moved = False

    def set_value(self, value: int) -> None:
        """Set scale value

        Args:
            value: int
        """
        if 0 <= value < 256:
            self.value = value

    def get_value(self) -> int:
        """Return scale value

        Returns:
            int
        """
        return self.value


class CrossFade:
    """For Manual Crossfade"""

    def __init__(self, app: typing.Any) -> None:  # noqa: ANN401
        self.app = app
        self.scale_a = Scale()
        self.scale_b = Scale()

        self.manual = False

    def scale_moved(self, scale: Scale) -> None:
        """On moved

        Args:
            scale: Scale object
        """
        scale.moved = True
        level = scale.get_value()

        if level not in (255, 0):
            self.app.lightshow.main_playback.on_go = True
            # If Go is sent, stop it
            if (
                self.manual
                and self.app.lightshow.main_playback.thread
                and self.app.lightshow.main_playback.thread.is_alive()
            ):
                self.app.lightshow.main_playback.thread.stop()
                self.app.lightshow.main_playback.thread.join()

        if scale in (self.scale_a, self.scale_b):
            if self.app.lightshow.main_playback.last == 0:
                # If sequential is empty, don't do anything
                self.app.lightshow.main_playback.on_go = False
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
            # Stop crossfade if return to 0
            if not self.app.lightshow.main_playback.on_go:
                return
            self.scale_a.moved = False
            self.scale_b.moved = False
            self.manual = False
            self.app.lightshow.main_playback.on_go = False

    def at_full(self) -> None:
        """Slider A and B at Full"""
        if not self.app.lightshow.main_playback.on_go:
            return
        self.scale_a.moved = False
        self.scale_b.moved = False
        self.manual = False
        self.app.lightshow.main_playback.on_go = False
        # Empty array of levels enter by user
        self.app.backend.dmx.levels["user"] = array.array("h", [-1] * MAX_CHANNELS)
        self.app.lightshow.main_playback.update_channels()
        # Go to next step
        next_step = self.app.lightshow.main_playback.position + 1
        if next_step < self.app.lightshow.main_playback.last - 1:
            # Next step
            self.app.lightshow.main_playback.position += 1
            next_step += 1
        else:
            # Return to first step
            self.app.lightshow.main_playback.position = 0
            next_step = 1
        # Update user interface
        if self.app.window and self.app.window.playback:
            self.app.window.playback.sequential.total_time = (
                self.app.lightshow.main_playback.steps[next_step].total_time
            )
            self.app.window.playback.sequential.time_in = (
                self.app.lightshow.main_playback.steps[next_step].time_in
            )
            self.app.window.playback.sequential.time_out = (
                self.app.lightshow.main_playback.steps[next_step].time_out
            )
            self.app.window.playback.sequential.delay_in = (
                self.app.lightshow.main_playback.steps[next_step].delay_in
            )
            self.app.window.playback.sequential.delay_out = (
                self.app.lightshow.main_playback.steps[next_step].delay_out
            )
            self.app.window.playback.sequential.wait = (
                self.app.lightshow.main_playback.steps[next_step].wait
            )
            self.app.window.playback.sequential.channel_time = (
                self.app.lightshow.main_playback.steps[next_step].channel_time
            )
            self.app.window.playback.sequential.position_a = 0
            self.app.window.playback.sequential.position_b = 0
        cue = self.app.lightshow.main_playback.steps[
            self.app.lightshow.main_playback.position
        ].cue.memory
        cue_text = self.app.lightshow.main_playback.steps[
            self.app.lightshow.main_playback.position
        ].text
        next_cue = self.app.lightshow.main_playback.steps[next_step].cue.memory
        subtitle = (
            f"Mem. :{cue} {cue_text} "
            f"- Next Mem. : {next_cue} "
            f"{self.app.lightshow.main_playback.steps[next_step].text}"
        )
        update_ui(self.app.lightshow.main_playback.position, subtitle)
        # If Wait
        if self.app.lightshow.main_playback.steps[next_step].wait:
            self.app.lightshow.main_playback.on_go = False
            self.app.lightshow.main_playback.do_go(None, False)

    def update_slider(self, scale: Scale, level: int) -> None:
        """Update sliders position

        Args:
            scale: Scale object
            level: int
        """
        step = self.app.lightshow.main_playback.position + 1
        total_time = self.app.lightshow.main_playback.steps[step].total_time * 1000
        wait = self.app.lightshow.main_playback.steps[step].wait * 1000
        position = (level / 255) * total_time
        if self.app.window and self.app.window.playback:
            if scale == self.scale_a:
                self.app.window.playback.sequential.position_a = int(
                    (self.app.window.playback.sequential.get_allocation().width - 32)
                    / total_time
                    * position
                )
                self.app.window.playback.show_timeleft_out(position)
            elif scale == self.scale_b:
                self.app.window.playback.sequential.position_b = int(
                    (self.app.window.playback.sequential.get_allocation().width - 32)
                    / total_time
                    * position
                )
                self.app.window.playback.show_timeleft_in(position)
            # Global progress is that of the least advanced. Cues colors reflect this
            value = min(self.scale_a.get_value(), self.scale_b.get_value())
            progress = min(max(value / 255.0, 0.0), 1.0)
            self.app.window.playback.update_cue_crossfade_color(step, progress)
            # Redraw Sequential Widget
            self.app.window.playback.sequential.queue_draw()

        # Update levels
        if position >= wait:
            for channel in range(1, MAX_CHANNELS + 1):
                if not self.app.lightshow.patch.is_patched(channel):
                    continue
                old_level = self.app.lightshow.main_playback.steps[
                    self.app.lightshow.main_playback.position
                ].cue.channels.get(channel, 0)
                if (
                    self.app.lightshow.main_playback.position
                    < self.app.lightshow.main_playback.last - 1
                ):
                    next_level = self.app.lightshow.main_playback.steps[
                        self.app.lightshow.main_playback.position + 1
                    ].cue.channels.get(channel, 0)
                else:
                    next_level = self.app.lightshow.main_playback.steps[
                        0
                    ].cue.channels.get(channel, 0)
                if scale == self.scale_a:
                    self._update_a(channel, old_level, next_level, wait, position)
                elif scale == self.scale_b:
                    # Get SequentialWindow's width to place cursor
                    self._update_b(channel, old_level, next_level, wait, position)
                if self.app.window and self.app.window.live_view:
                    self.app.window.live_view.update_channel_widget(channel, next_level)
            self.app.backend.dmx.set_levels(self.app.lightshow.main_playback.channels)

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _update_a(
        self, channel: int, old_level: int, next_level: int, wait: float, pos: float
    ) -> None:
        """Update channel level with A Slider

        Args:
            channel: Channel to update
            old_level: Old level
            next_level: Next level
            wait: Wait value
            pos: Position in crossfade
        """
        time_out = (
            self.app.lightshow.main_playback.steps[
                self.app.lightshow.main_playback.position + 1
            ].time_out
            * 1000
        )
        delay_out = (
            self.app.lightshow.main_playback.steps[
                self.app.lightshow.main_playback.position + 1
            ].delay_out
            * 1000
        )
        # Channel Time
        lvl = self._update_a_channel_time(channel, old_level, next_level, wait, pos)
        user_level = self.app.backend.dmx.levels["user"][channel - 1]
        if user_level != -1 and next_level < user_level:
            # Update channel level with user changed
            if pos <= wait + delay_out:
                lvl = old_level
            elif wait + delay_out < pos < time_out + wait + delay_out:
                lvl = user_level - abs(
                    int(
                        ((next_level - user_level) / time_out)
                        * (pos - wait - delay_out)
                    )
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
                            ((next_level - old_level) / time_out)
                            * (pos - wait - delay_out)
                        )
                    )
                )
            else:
                lvl = next_level
        if lvl != -1:
            self.app.backend.dmx.levels["sequence"][channel - 1] = lvl

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _update_a_channel_time(
        self, channel: int, old_level: int, next_level: int, wait: float, pos: float
    ) -> int:
        """Update channel level in Channel Time

        Args:
            channel: Channel to update
            old_level: Old level
            next_level: Next level
            wait: Wait value
            pos: Position in crossfade

        Returns:
            channel level or -1
        """
        lvl = -1
        channel_time = self.app.lightshow.main_playback.steps[
            self.app.lightshow.main_playback.position + 1
        ].channel_time
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

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _update_b(
        self, channel: int, old_level: int, next_level: int, wait: float, pos: float
    ) -> None:
        """Update channel level with B Slider

        Args:
            channel: Channel to update
            old_level: Old level
            next_level: Next level
            wait: Wait value
            pos: Position in crossfade
        """
        lvl = -1
        time_in = (
            self.app.lightshow.main_playback.steps[
                self.app.lightshow.main_playback.position + 1
            ].time_in
            * 1000
        )
        delay_in = (
            self.app.lightshow.main_playback.steps[
                self.app.lightshow.main_playback.position + 1
            ].delay_in
            * 1000
        )
        # Channel Time
        lvl = self._update_b_channel_time(channel, old_level, next_level, wait, pos)
        user_level = self.app.backend.dmx.levels["user"][channel - 1]
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
            self.app.backend.dmx.levels["sequence"][channel - 1] = lvl

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _update_b_channel_time(
        self, channel: int, old_level: int, next_level: int, wait: float, pos: float
    ) -> int:
        """Update channel level in Channel Time

        Args:
            channel: Channel to update
            old_level: Old level
            next_level: Next level
            wait: Wait value
            pos: Position in crossfade

        Returns:
            channel level or -1
        """
        lvl = -1
        channel_time = self.app.lightshow.main_playback.steps[
            self.app.lightshow.main_playback.position + 1
        ].channel_time
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
