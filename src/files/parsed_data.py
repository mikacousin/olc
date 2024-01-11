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
from olc.cue import Cue
from olc.curve import LimitCurve
from olc.define import App
from olc.files.import_dialog import Action
from olc.sequence import Sequence
from olc.step import Step


class ParsedData:
    """To store imported information"""

    patch: dict[int, list]
    sequence: dict

    def __init__(self):
        self.patch = {}
        self.sequences = {1: {"mode": "normal", "steps": [], "cues": {}}}

    def import_patch(self) -> None:
        """Import data patch"""
        for channel, item in self.patch.items():
            for out in item:
                output, univers, level = out
                # Create Curve if needed
                curve = 0
                if level != 255:
                    if not App().curves.find_limit_curve(level):
                        curve = App().curves.add_curve(LimitCurve(level))
                App().backend.patch.add_output(channel, output, univers, curve)

    def import_main_playback(self, sequence: int, action: Action) -> None:
        """Import Main Playback

        Args:
            sequence: Sequence number (Main Playback is always 1)
            action: Action type
        """
        if action is Action.REPLACE:
            self._replace_main_playback(sequence)
        elif action is Action.MERGE:
            self._merge_main_playback(sequence)

    def _replace_main_playback(self, sequence: int) -> None:
        for cue_number in self.sequences[sequence]["steps"]:
            value = self.sequences[sequence]["cues"][cue_number]
            # Cue already exist ?
            found = False
            cue = None
            for cue in App().memories:
                if cue.memory == cue_number:
                    found = True
                    break
            if found:
                # If cue exist, update it
                cue.channels = value.get("channels")
                cue.text = value.get("text")
            else:
                # Else, create it
                cue = Cue(0, cue_number, value.get("channels"), text=value.get("text"))
                App().memories.append(cue)
            # Create new step
            step = Step(sequence,
                        cue,
                        time_in=value.get("up_time"),
                        time_out=value.get("out_time"),
                        delay_in=value.get("up_delay"),
                        delay_out=value.get("out_delay"),
                        wait=value.get("wait"),
                        text=value.get("text"))
            App().sequence.add_step(step)

    def _merge_main_playback(self, sequence: int) -> None:
        del App().sequence.steps[-1]
        for cue_number, value in self.sequences[sequence]["cues"].items():
            found, step_seq = App().sequence.get_step(cue_number)
            if found:
                # If cue exist, update it
                cue = App().sequence.steps[step_seq - 1].cue
                cue.channels = value.get("channels")
                cue.text = value.get("text")
                App().sequence.steps[step_seq - 1].text = value.get("text")
            else:
                cue = Cue(0, cue_number, value.get("channels"), text=value.get("text"))
                self._insert_cue(cue)
                step = Step(sequence,
                            cue,
                            time_in=value.get("up_time"),
                            time_out=value.get("out_time"),
                            delay_in=value.get("up_delay"),
                            delay_out=value.get("out_delay"),
                            wait=value.get("wait"),
                            text=value.get("text"))
                App().sequence.insert_step(step_seq, step)

    def import_chaser(self, sequence: int, action: Action) -> None:
        """Import Chaser

        Args:
            sequence: Sequence number
            action: Action type
        """
        text = self.sequences[sequence]["text"]
        chaser = None
        index = None
        for index, chsr in enumerate(App().chasers):
            if chsr.index == sequence:
                chaser = chsr
                break
        if not chaser:
            App().chasers.append(Sequence(sequence, type_seq="Chaser", text=text))
            index = -1
            del App().chasers[index].steps[1:]
        else:
            App().chasers[index].text = text
        if action is Action.REPLACE:
            self._replace_chaser(sequence, index)
        elif action is Action.MERGE:
            self._merge_chaser(sequence, index)

    def _merge_chaser(self, sequence: int, index: int) -> None:
        for cue_number, value in self.sequences[sequence]["cues"].items():
            found, step_seq = App().chasers[index].get_step(cue_number)
            if found:
                cue = App().chasers[index].steps[step_seq - 1].cue
                cue.channels = value.get("channels")
                cue.text = value.get("text")
                App().chasers[index].steps[step_seq - 1].text = value.get("text")
            else:
                cue = Cue(sequence,
                          cue_number,
                          value.get("channels"),
                          text=value.get("text"))
                App().chasers[index].cues.add(cue)
                step = Step(sequence,
                            cue,
                            time_in=value.get("up_time"),
                            time_out=value.get("out_time"),
                            delay_in=value.get("up_delay"),
                            delay_out=value.get("out_delay"),
                            wait=value.get("wait"),
                            text=value.get("text"))
                App().chasers[index].insert_step(step_seq, step)

    def _replace_chaser(self, sequence: int, index: int) -> None:
        for cue_number in self.sequences[sequence]["steps"]:
            value = self.sequences[sequence]["cues"][cue_number]
            # Cue already exist ?
            found = False
            cue = None
            for cue in App().chasers[index].cues:
                if cue.memory == cue_number:
                    found = True
                    break
            if found:
                # If cue exist, update it
                cue.channels = value.get("channels")
                cue.text = value.get("text")
            else:
                cue = Cue(sequence,
                          cue_number,
                          value.get("channels"),
                          text=value.get("text"))
                App().chasers[index].cues.add(cue)
            step = Step(sequence,
                        cue,
                        time_in=value.get("up_time"),
                        time_out=value.get("out_time"),
                        delay_in=value.get("up_delay"),
                        delay_out=value.get("out_delay"),
                        wait=value.get("wait"),
                        text=value.get("text"))
            App().chasers[index].add_step(step)

    def _insert_cue(self, cue: Cue) -> None:
        """Insert cue in list cues

        Args:
            cue: Cue to insert
        """
        cue_number = cue.memory
        # Find cue position
        found = False
        index = 0
        for index, cue_seq in enumerate(App().memories):
            if cue_seq.memory > cue_number:
                found = True
                break
        if not found:
            # Cue is at the end
            index += 1
        # Insert cue
        App().memories.insert(index, cue)
        App().sequence.update_channels()
