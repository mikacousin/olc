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
from olc.sequence import Sequence
from olc.step import Step


class ParsedData:
    """To store imported information"""

    patch: dict[int, list]
    sequence: dict

    def __init__(self):
        self.patch = {}
        self.sequences = {}

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

    def import_main_playback(self, sequence: int) -> None:
        """Import Main Playback

        Args:
            sequence: Sequence number (Main Playback is always 1)
        """
        for cue_number, value in self.sequences[sequence]["cues"].items():
            found, step_seq = App().sequence.get_step(cue_number)
            if found:
                print(f"Cue {cue_number} in step {step_seq}, skipping")
            else:
                cue = Cue(0, cue_number, value.get("channels"), text=value.get("text"))
                self.insert_cue(cue)
                step = Step(sequence,
                            cue,
                            time_in=value.get("up_time"),
                            time_out=value.get("out_time"),
                            delay_in=value.get("up_delay"),
                            delay_out=value.get("out_delay"),
                            wait=value.get("wait"),
                            text=value.get("text"))
                App().sequence.insert_step(step_seq, step)

    def import_chaser(self, sequence: int) -> None:
        """Import Chaser

        Args:
            sequence: Sequence number
        """
        text = self.sequences[sequence]["text"]
        App().chasers.append(Sequence(sequence, type_seq="Chaser", text=text))
        del App().chasers[-1].steps[1:]
        for cue_number, value in self.sequences[sequence]["cues"].items():
            cue = Cue(sequence,
                      cue_number,
                      value.get("channels"),
                      text=value.get("text"))
            step = Step(sequence,
                        cue,
                        time_in=value.get("up_time"),
                        time_out=value.get("out_time"),
                        delay_in=value.get("up_delay"),
                        delay_out=value.get("out_delay"),
                        wait=value.get("wait"),
                        text=value.get("text"))
            App().chasers[-1].add_step(step)

    def insert_cue(self, cue: Cue) -> None:
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
