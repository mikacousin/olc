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

import copy
import typing

from olc.channel_time import ChannelTime
from olc.core.action import Action
from olc.cue import Cue
from olc.sequence import Sequence
from olc.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class SequenceNewAction(Action):
    """Action to create a new sequence (chaser) in the lightshow."""

    name = "sequence.new"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.index_seq: float = 0.0
        self.created_chaser: Sequence | None = None

    def configure(self, index_seq: float) -> None:
        """Configure the action with the sequence index."""
        self.index_seq = index_seq

    def execute(self) -> None:
        lightshow = self.app.lightshow
        # Verify if sequence index already exists
        for chaser in lightshow.chasers:
            if chaser.index == self.index_seq:
                raise ValueError(f"Chaser sequence {self.index_seq} already exists.")
        if self.index_seq == 1.0:
            raise ValueError(
                "Chaser sequence cannot use index 1.0 (reserved for main playback)."
            )

        chaser = Sequence(self.index_seq, type_seq="Chaser", lightshow=lightshow)
        # Clear step 1+ as in the original GUI flow
        del chaser.steps[1:]
        chaser.last = len(chaser.steps)

        self.created_chaser = chaser
        lightshow.chasers.append(chaser)
        lightshow.set_modified()

        self.app.emit("sequence.created", chaser)

    def undo(self) -> None:
        if self.created_chaser:
            self.app.lightshow.chasers.remove(self.created_chaser)
            self.app.lightshow.set_modified()
            self.app.emit("sequence.deleted", self.created_chaser)

    def redo(self) -> None:
        if self.created_chaser:
            self.app.lightshow.chasers.append(self.created_chaser)
            self.app.lightshow.set_modified()
            self.app.emit("sequence.created", self.created_chaser)


class SequenceDeleteAction(Action):
    """Action to delete a chaser sequence."""

    name = "sequence.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.index_seq: float = 0.0
        self.deleted_chaser: Sequence | None = None
        self.deleted_index: int = -1

    def configure(self, index_seq: float) -> None:
        """Configure the action with the sequence index to delete."""
        self.index_seq = index_seq

    def execute(self) -> None:
        lightshow = self.app.lightshow
        chaser = lightshow.get_chaser(self.index_seq)
        if not chaser:
            raise ValueError(f"Chaser sequence {self.index_seq} does not exist.")

        self.deleted_chaser = chaser
        self.deleted_index = lightshow.chasers.index(chaser)

        lightshow.chasers.remove(chaser)
        lightshow.set_modified()

        self.app.emit("sequence.deleted", chaser)

    def undo(self) -> None:
        if self.deleted_chaser and self.deleted_index != -1:
            self.app.lightshow.chasers.insert(self.deleted_index, self.deleted_chaser)
            self.app.lightshow.set_modified()
            self.app.emit("sequence.created", self.deleted_chaser)

    def redo(self) -> None:
        if self.deleted_chaser:
            self.app.lightshow.chasers.remove(self.deleted_chaser)
            self.app.lightshow.set_modified()
            self.app.emit("sequence.deleted", self.deleted_chaser)


class SequenceInsertStepAction(Action):
    """Action to insert a step (and its associated Cue) in a sequence."""

    name = "sequence.insert_step"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.sequence_index: float = 0.0
        self.step_index: int = 0
        self.cue_number: float = 0.0
        self.channels: dict[int, int] = {}
        self.created_cue: Cue | None = None
        self.created_step: Step | None = None
        self.cue_already_existed: bool = False

    def configure(
        self,
        sequence_index: float,
        step_index: int,
        cue_number: float,
        channels: dict[int, int] | None = None,
    ) -> None:
        """Configure the step insertion with the sequence and cue details."""
        self.sequence_index = sequence_index
        self.step_index = step_index
        self.cue_number = cue_number
        self.channels = dict(channels) if channels is not None else {}

    def execute(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)
            if not sequence:
                raise ValueError(f"Sequence {self.sequence_index} does not exist.")

        # Check if the Cue already exists globally
        existing_cue = lightshow.cues.get(self.cue_number, int(self.sequence_index))
        if existing_cue is not None:
            self.cue_already_existed = True
            cue = existing_cue
        else:
            self.cue_already_existed = False
            cue = Cue(
                int(self.sequence_index), self.cue_number, copy.deepcopy(self.channels)
            )
            self.created_cue = cue
            if self.sequence_index == 1.0:
                lightshow.cues.insert(self.step_index, cue)

        step_object = Step(int(self.sequence_index), cue=cue)
        self.created_step = step_object
        sequence.insert_step(self.step_index, step_object)
        sequence.update_channels()
        lightshow.set_modified()

        self.app.emit("step.inserted", self.sequence_index, self.step_index)
        if not self.cue_already_existed:
            self.app.emit("cue.created", int(self.sequence_index), self.cue_number)

    def undo(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)

        if sequence and self.created_step in sequence.steps:
            sequence.steps.remove(self.created_step)
            sequence.last = len(sequence.steps)
            sequence.update_channels()

        if not self.cue_already_existed and self.created_cue:
            if self.sequence_index == 1.0:
                lightshow.cues.remove(self.created_cue)
            lightshow.main_playback.update_channels()
            lightshow.set_modified()
            self.app.emit("cue.deleted", int(self.sequence_index), self.cue_number)

        lightshow.set_modified()
        self.app.emit("step.deleted", self.sequence_index, self.step_index)

    def redo(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)
            if not sequence:
                return

        if not self.cue_already_existed and self.created_cue:
            if self.sequence_index == 1.0:
                lightshow.cues.insert(self.step_index, self.created_cue)

        if self.created_step:
            sequence.insert_step(self.step_index, self.created_step)
            sequence.update_channels()

        lightshow.set_modified()
        self.app.emit("step.inserted", self.sequence_index, self.step_index)
        if not self.cue_already_existed:
            self.app.emit("cue.created", int(self.sequence_index), self.cue_number)


class SequenceDeleteStepAction(Action):
    """Action to delete a step from a sequence."""

    name = "sequence.delete_step"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.sequence_index: float = 0.0
        self.step_index: int = 0
        self.deleted_step: Step | None = None

    def configure(self, sequence_index: float, step_index: int) -> None:
        """Configure the step deletion with sequence index and step index."""
        self.sequence_index = sequence_index
        self.step_index = step_index

    def execute(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)
            if not sequence:
                raise ValueError(f"Sequence {self.sequence_index} does not exist.")

        if self.step_index < 0 or self.step_index >= len(sequence.steps):
            raise IndexError("Step index out of range.")

        self.deleted_step = sequence.steps[self.step_index]
        sequence.steps.pop(self.step_index)
        sequence.last = len(sequence.steps)
        sequence.update_channels()
        lightshow.set_modified()

        self.app.emit("step.deleted", self.sequence_index, self.step_index)

    def undo(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)

        if sequence and self.deleted_step:
            sequence.insert_step(self.step_index, self.deleted_step)
            sequence.update_channels()
            lightshow.set_modified()
            self.app.emit("step.inserted", self.sequence_index, self.step_index)


# pylint: disable=too-many-instance-attributes
class StepUpdateTimesAction(Action):
    """Action to update a sequence step's timing values.

    Modifies time_in, time_out, delay_in, delay_out, and wait.
    """

    name = "step.update_times"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.sequence_index: float = 0.0
        self.step_index: int = 0
        self.time_in: float | None = None
        self.time_out: float | None = None
        self.delay_in: float | None = None
        self.delay_out: float | None = None
        self.wait: float | None = None
        self.old_times: dict[str, float] = {}

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def configure(
        self,
        sequence_index: float,
        step_index: int,
        time_in: float | None = None,
        time_out: float | None = None,
        delay_in: float | None = None,
        delay_out: float | None = None,
        wait: float | None = None,
    ) -> None:
        """Configure the timing updates for the step."""
        self.sequence_index = sequence_index
        self.step_index = step_index
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait

    def execute(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)
            if not sequence:
                raise ValueError(f"Sequence {self.sequence_index} does not exist.")

        if self.step_index < 0 or self.step_index >= len(sequence.steps):
            raise IndexError("Step index out of range.")

        step = sequence.steps[self.step_index]
        self.old_times = {
            "time_in": step.time_in,
            "time_out": step.time_out,
            "delay_in": step.delay_in,
            "delay_out": step.delay_out,
            "wait": step.wait,
        }

        if self.time_in is not None:
            step.time_in = self.time_in
        if self.time_out is not None:
            step.time_out = self.time_out
        if self.delay_in is not None:
            step.delay_in = self.delay_in
        if self.delay_out is not None:
            step.delay_out = self.delay_out
        if self.wait is not None:
            step.wait = self.wait

        step.update_total_time()
        lightshow.set_modified()

        self.app.emit("step.updated", self.sequence_index, self.step_index)

    def undo(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)

        if sequence:
            step = sequence.steps[self.step_index]
            step.time_in = self.old_times["time_in"]
            step.time_out = self.old_times["time_out"]
            step.delay_in = self.old_times["delay_in"]
            step.delay_out = self.old_times["delay_out"]
            step.wait = self.old_times["wait"]
            step.update_total_time()
            lightshow.set_modified()
            self.app.emit("step.updated", self.sequence_index, self.step_index)


class StepUpdateTextAction(Action):
    """Action to update a sequence step's descriptive text."""

    name = "step.update_text"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.sequence_index: float = 0.0
        self.step_index: int = 0
        self.text: str = ""
        self.old_text: str = ""

    def configure(self, sequence_index: float, step_index: int, text: str) -> None:
        """Configure the text update for the step."""
        self.sequence_index = sequence_index
        self.step_index = step_index
        self.text = text

    def execute(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)
            if not sequence:
                raise ValueError(f"Sequence {self.sequence_index} does not exist.")

        if self.step_index < 0 or self.step_index >= len(sequence.steps):
            raise IndexError("Step index out of range.")

        step = sequence.steps[self.step_index]
        self.old_text = step.text
        step.text = self.text

        lightshow.set_modified()
        self.app.emit("step.updated", self.sequence_index, self.step_index)

    def undo(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)

        if sequence:
            step = sequence.steps[self.step_index]
            step.text = self.old_text
            lightshow.set_modified()
            self.app.emit("step.updated", self.sequence_index, self.step_index)


# pylint: disable=too-many-instance-attributes
class StepUpdateChannelTimeAction(Action):
    """Action to update individual channel fade/delay times inside a step.

    Adds, updates, or removes times as needed.
    """

    name = "step.update_channel_time"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.sequence_index: float = 0.0
        self.step_index: int = 0
        self.channel: int = 0
        self.delay: float | None = None
        self.time: float | None = None
        self.old_state_existed: bool = False
        self.old_delay: float = 0.0
        self.old_time: float = 0.0

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def configure(
        self,
        sequence_index: float,
        step_index: int,
        channel: int,
        delay: float | None = None,
        time: float | None = None,
    ) -> None:
        """Configure the individual channel time update for the step."""
        self.sequence_index = sequence_index
        self.step_index = step_index
        self.channel = channel
        self.delay = delay
        self.time = time

    def execute(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)
            if not sequence:
                raise ValueError(f"Sequence {self.sequence_index} does not exist.")

        if self.step_index < 0 or self.step_index >= len(sequence.steps):
            raise IndexError("Step index out of range.")

        step = sequence.steps[self.step_index]
        self.old_state_existed = self.channel in step.channel_time
        if self.old_state_existed:
            self.old_delay = step.channel_time[self.channel].delay
            self.old_time = step.channel_time[self.channel].time

        new_delay = (
            self.delay
            if self.delay is not None
            else (self.old_delay if self.old_state_existed else 0.0)
        )
        new_time = (
            self.time
            if self.time is not None
            else (self.old_time if self.old_state_existed else 0.0)
        )

        if new_delay == 0.0 and new_time == 0.0:
            if self.channel in step.channel_time:
                del step.channel_time[self.channel]
        else:
            if self.channel not in step.channel_time:
                step.channel_time[self.channel] = ChannelTime(0.0, 0.0)
            step.channel_time[self.channel].delay = new_delay
            step.channel_time[self.channel].time = new_time

        step.update_total_time()
        lightshow.set_modified()

        self.app.emit("step.updated", self.sequence_index, self.step_index)

    def undo(self) -> None:
        lightshow = self.app.lightshow
        if self.sequence_index == 1.0:
            sequence = lightshow.main_playback
        else:
            sequence = lightshow.get_chaser(self.sequence_index)

        if sequence:
            step = sequence.steps[self.step_index]
            if not self.old_state_existed:
                if self.channel in step.channel_time:
                    del step.channel_time[self.channel]
            else:
                if self.channel not in step.channel_time:
                    step.channel_time[self.channel] = ChannelTime(0.0, 0.0)
                step.channel_time[self.channel].delay = self.old_delay
                step.channel_time[self.channel].time = self.old_time

            step.update_total_time()
            lightshow.set_modified()
            self.app.emit("step.updated", self.sequence_index, self.step_index)
