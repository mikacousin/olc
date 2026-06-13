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
import typing

import numpy as np
from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.step import Step


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
            self.app.core.lightshow.main_playback.on_go = True
            # If Go is sent, stop it
            if (
                self.manual
                and self.app.core.lightshow.main_playback.thread
                and self.app.core.lightshow.main_playback.thread.is_alive()
            ):
                self.app.core.lightshow.main_playback.thread.stop()
                self.app.core.lightshow.main_playback.thread.join()

        if scale in (self.scale_a, self.scale_b):
            if self.app.core.lightshow.main_playback.last == 0:
                # If sequential is empty, don't do anything
                self.app.core.lightshow.main_playback.on_go = False
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
            if not self.app.core.lightshow.main_playback.on_go:
                return
            self.scale_a.moved = False
            self.scale_b.moved = False
            self.manual = False
            self.app.core.lightshow.main_playback.on_go = False

    def at_full(self) -> None:
        """Slider A and B at Full"""
        if not self.app.core.lightshow.main_playback.on_go:
            return
        self.scale_a.moved = False
        self.scale_b.moved = False
        self.manual = False
        self.app.core.lightshow.main_playback.on_go = False
        # Empty array of levels enter by user
        self.app.backend.dmx.levels["user"] = np.full(MAX_CHANNELS, -1, dtype=np.int16)
        self.app.core.lightshow.main_playback.update_channels()
        # Go to next step
        next_step = self.app.core.lightshow.main_playback.position + 1
        if next_step < self.app.core.lightshow.main_playback.last - 1:
            # Next step
            self.app.core.lightshow.main_playback.position += 1
            next_step += 1
        else:
            # Return to first step
            self.app.core.lightshow.main_playback.position = 0
            next_step = 1
        # Update user interface
        cue = self.app.core.lightshow.main_playback.steps[
            self.app.core.lightshow.main_playback.position
        ].cue.memory
        cue_text = self.app.core.lightshow.main_playback.steps[
            self.app.core.lightshow.main_playback.position
        ].text
        next_cue = self.app.core.lightshow.main_playback.steps[next_step].cue.memory
        subtitle = (
            f"Mem. :{cue} {cue_text} "
            f"- Next Mem. : {next_cue} "
            f"{self.app.core.lightshow.main_playback.steps[next_step].text}"
        )
        self.app.core.emit("crossfade.at_full", next_step, subtitle)
        # If Wait
        if self.app.core.lightshow.main_playback.steps[next_step].wait:
            self.app.core.lightshow.main_playback.on_go = False
            self.app.core.action_registry.execute("playback.go")

    def update_slider(self, scale: Scale, level: int) -> None:
        """Update sliders position

        Args:
            scale: Scale object
            level: int
        """
        step_idx = self.app.core.lightshow.main_playback.position + 1
        step = self.app.core.lightshow.main_playback.steps[step_idx]
        total_time = step.total_time * 1000
        wait = step.wait * 1000
        position = (level / 255) * total_time

        self._update_ui_transition(scale, position, total_time, step_idx)

        # Update levels
        if position >= wait:
            sequence_levels = self.app.backend.dmx.levels["sequence"]

            if scale == self.scale_a:
                lvls = self._calculate_scale_a(position, step)
                sequence_levels[:] = np.clip(lvls, 0, 255).astype(np.uint8)
            elif scale == self.scale_b:
                lvls = self._calculate_scale_b(position, step)
                sequence_levels[:] = np.clip(lvls, 0, 255).astype(np.uint8)

            self.app.backend.dmx.set_levels()

    def _update_ui_transition(
        self, scale: Scale, position: float, total_time: float, step: int
    ) -> None:
        """Emit scale update events to be handled by the UI bridge."""
        scale_name = "scale_a" if scale == self.scale_a else "scale_b"
        self.app.core.emit(
            "crossfade.scale_updated", scale_name, position, total_time, step
        )

    def _apply_channel_times_a(
        self, lvls: np.ndarray, position: float, step: Step
    ) -> None:
        """Apply individual channel times for decays."""
        if not step.channel_time:
            return
        old_levels = self.app.core.lightshow.main_playback.steps[
            self.app.core.lightshow.main_playback.position
        ].cue.channels_array.astype(np.int32)

        next_step = self.app.core.lightshow.main_playback.position + 1
        if next_step >= self.app.core.lightshow.main_playback.last - 1:
            next_step = 0
        next_levels = self.app.core.lightshow.main_playback.steps[
            next_step
        ].cue.channels_array.astype(np.int32)

        wait = step.wait * 1000
        for channel, ct in step.channel_time.items():
            if next_levels[channel - 1] < old_levels[channel - 1]:
                if position < ct.delay * 1000 + wait:
                    lvl = old_levels[channel - 1]
                elif position < ct.delay * 1000 + ct.time * 1000 + wait:
                    factor = (position - ct.delay * 1000 - wait) / (ct.time * 1000)
                    lvl = old_levels[channel - 1] - abs(
                        int(
                            (next_levels[channel - 1] - old_levels[channel - 1])
                            * factor
                        )
                    )
                else:
                    lvl = next_levels[channel - 1]
                lvls[channel - 1] = lvl

    def _calculate_scale_a(self, position: float, step: Step) -> np.ndarray:
        """Calculate fade levels for Scale A (decays)."""
        main_pb = self.app.core.lightshow.main_playback
        old_levels = main_pb.steps[main_pb.position].cue.channels_array.astype(np.int32)

        next_step = main_pb.position + 1
        if next_step >= main_pb.last - 1:
            next_step = 0
        next_levels = main_pb.steps[next_step].cue.channels_array.astype(np.int32)

        user_levels = self.app.backend.dmx.levels["user"]

        # Base levels (no fade or after delay)
        if position <= (step.wait + step.delay_out) * 1000:
            lvls = old_levels.copy()
        elif position < (step.time_out + step.wait + step.delay_out) * 1000:
            factor = (position - step.wait * 1000 - step.delay_out * 1000) / (
                step.time_out * 1000
            )
            # Decays
            diff = (next_levels - old_levels) * factor
            lvls = np.round(old_levels - np.abs(diff)).astype(np.int32)
            # User overrides
            user_mask = (user_levels != -1) & (next_levels < user_levels)
            if np.any(user_mask):
                val = np.round(
                    user_levels - np.abs((next_levels - user_levels) * factor)
                )
                lvls[user_mask] = val[user_mask]
        else:
            lvls = next_levels.copy()

        self._apply_channel_times_a(lvls, position, step)
        return lvls

    def _apply_channel_times_b(
        self, lvls: np.ndarray, position: float, step: Step
    ) -> None:
        """Apply individual channel times for attacks."""
        if not step.channel_time:
            return
        old_levels = self.app.core.lightshow.main_playback.steps[
            self.app.core.lightshow.main_playback.position
        ].cue.channels_array.astype(np.int32)

        next_step = self.app.core.lightshow.main_playback.position + 1
        if next_step >= self.app.core.lightshow.main_playback.last - 1:
            next_step = 0
        next_levels = self.app.core.lightshow.main_playback.steps[
            next_step
        ].cue.channels_array.astype(np.int32)

        wait = step.wait * 1000
        for channel, ct in step.channel_time.items():
            if next_levels[channel - 1] > old_levels[channel - 1]:
                if position < ct.delay * 1000 + wait:
                    lvl = old_levels[channel - 1]
                elif position < ct.delay * 1000 + ct.time * 1000 + wait:
                    factor = (position - ct.delay * 1000 - wait) / (ct.time * 1000)
                    lvl = int(
                        (next_levels[channel - 1] - old_levels[channel - 1]) * factor
                        + old_levels[channel - 1]
                    )
                else:
                    lvl = next_levels[channel - 1]
                lvls[channel - 1] = lvl

    def _calculate_scale_b(self, position: float, step: Step) -> np.ndarray:
        """Calculate fade levels for Scale B (attacks)."""
        main_pb = self.app.core.lightshow.main_playback
        old_levels = main_pb.steps[main_pb.position].cue.channels_array.astype(np.int32)

        next_step = main_pb.position + 1
        if next_step >= main_pb.last - 1:
            next_step = 0
        next_levels = main_pb.steps[next_step].cue.channels_array.astype(np.int32)

        user_levels = self.app.backend.dmx.levels["user"]

        if position <= (step.wait + step.delay_in) * 1000:
            lvls = old_levels.copy()
        elif position < (step.time_in + step.wait + step.delay_in) * 1000:
            factor = (position - step.wait * 1000 - step.delay_in * 1000) / (
                step.time_in * 1000
            )
            # Attacks
            diff = (next_levels - old_levels) * factor
            lvls = np.round(old_levels + diff).astype(np.int32)
            # User overrides
            user_mask = (user_levels != -1) & (next_levels > user_levels)
            if np.any(user_mask):
                val = np.round(user_levels + (next_levels - user_levels) * factor)
                lvls[user_mask] = val[user_mask]
        else:
            lvls = next_levels.copy()

        self._apply_channel_times_b(lvls, position, step)
        return lvls
