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
from olc.channel_time import ChannelTime
from olc.cue import Cue
from olc.curve import InterpolateCurve, LimitCurve, SegmentsCurve
from olc.define import App
from olc.fader import FaderType
from olc.files.import_dialog import Action
from olc.group import Group
from olc.sequence import Sequence
from olc.step import Step


class ParsedData:
    """To store imported information"""

    patch: dict[int, list]
    sequence: dict

    def __init__(self):
        self.data = {
            "console": {
                "console": "",
                "manufacturer": ""
            },
            "curves": {},
            "patch": {},
            "sequences": {
                1: {
                    "label": "",
                    "mode": "normal",
                    "steps": {},
                    "cues": {}
                }
            },
            "groups": {},
            "independents": {},
            "cues": {},
            "faders": {},
            "midi": {}
        }

    def clean(self):
        """Remove useless data"""
        # Remove Sequences without cue
        keys = []
        for sequence, values in self.data["sequences"].items():
            if not values.get("cues"):
                keys.append(sequence)
        for key in keys:
            self.data["sequences"].pop(key)
        # Transform fader of channels in fader with group
        index = 500.0
        for values in self.data["faders"].values():
            if values.get("type") == FaderType.CHANNELS:
                while True:
                    if index in self.data["groups"]:
                        index += 1
                    else:
                        break
                self.data["groups"][index] = {
                    "channels": values.get("contents"),
                    "label": str(index)
                }
                values["type"] = FaderType.GROUP
                values["contents"] = index
                index += 1

    def import_midi(self) -> None:
        """Import MIDI mapping"""
        if not self.data["midi"]:
            return
        for action, value in self.data["midi"]["note"].items():
            if value != [0, -1]:
                App().midi.messages.notes.notes[action] = value
        for action, value in self.data["midi"]["control_change"].items():
            if value != [0, -1]:
                App().midi.messages.control_change.control_change[action] = value
        for action, value in self.data["midi"]["pitchwheel"].items():
            if value != -1:
                App().midi.messages.pitchwheel.pitchwheel[action] = value

    def import_curves(self) -> None:
        """Import curves data"""
        if not self.data["curves"]:
            return
        for curve_nb, values in self.data["curves"].items():
            curve_type = values["type"]
            if curve_type == "LimitCurve":
                limit = values["limit"]
                curve = LimitCurve(limit=limit)
            elif curve_type == "SegmentsCurve":
                curve = SegmentsCurve()
            elif curve_type == "InterpolateCurve":
                curve = InterpolateCurve()
            App().lightshow.curves.curves[curve_nb] = curve
            if curve_type in ("SegmentsCurve", "InterpolateCurve"):
                points = values["points"]
                for point in points:
                    App().lightshow.curves.curves[curve_nb].add_point(
                        point[0], point[1])
            label = values.get("label")
            if label:
                curve.name = label

    def import_patch(self) -> None:
        """Import data patch"""
        for channel, values in self.data["patch"].items():
            for out in values:
                output = out["output"]
                universe = out["universe"]
                curve_nb = out.get("curve", 0)
                App().lightshow.patch.add_output(channel, output, universe, curve_nb)

    def import_groups(self) -> None:
        """Import groups data"""
        for group_number, values in self.data["groups"].items():
            channels = values.get("channels")
            label = values.get("label")
            group = None
            found = False
            for group in App().lightshow.groups:
                if group_number == group.index:
                    found = True
                    break
            if found:
                # If group exist, update it
                group.text = label
                group.channels = channels
            else:
                # Create new group
                App().lightshow.groups.append(Group(group_number, channels, label))

    def import_faders(self) -> None:
        """Import faders data"""
        for values in self.data["faders"].values():
            page = values.get("page")
            number = values.get("number")
            fader_type = values.get("type")
            contents = values.get("contents")
            if number <= 10:
                App().lightshow.fader_bank.set_fader(page, number, fader_type, contents)

    def import_independents(self) -> None:
        """Import independents data"""
        for inde_number, values in self.data["independents"].items():
            channels = values.get("channels")
            label = values.get("label")
            inde = None
            found = False
            for inde in App().lightshow.independents.independents:
                if inde_number == inde.number:
                    found = True
                    break
            if found:
                inde.text = label
                inde.levels = channels
                App().lightshow.independents.update(inde)

    def import_presets(self) -> None:
        """Import presets data"""
        for preset_number, values in self.data["cues"].items():
            channels = values.get("channels")
            label = values.get("label")
            found = False
            cue = None
            for cue in App().lightshow.cues:
                if cue.memory == preset_number:
                    found = True
                    break
            if found:
                cue.channels = channels
                cue.text = label
            else:
                cue = Cue(0, preset_number, channels, label)
                self._insert_cue(cue)

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
        for step, values in self.data["sequences"][sequence]["steps"].items():
            cue_number = values.get("cue")
            cue_channels = self.data["sequences"][sequence]["cues"][cue_number][
                "channels"]
            cue_text = self.data["sequences"][sequence]["cues"][cue_number]["label"]
            found = False
            cue = None
            for cue in App().lightshow.cues:
                if cue.memory == cue_number:
                    found = True
                    break
            if found:
                # If cue exist, update it
                cue.channels = cue_channels
                cue.text = cue_text
            else:
                # Else, create it
                cue = Cue(0, cue_number, cue_channels, text=cue_text)
                App().lightshow.cues.append(cue)
            channel_time = {}
            if values.get("channel_time"):
                for channel, times in values.get("channel_time").items():
                    channel_time[channel] = ChannelTime(times.get("delay", 0.0),
                                                        times.get("time", 0.0))
            # Create new step
            step = Step(sequence,
                        cue,
                        time_in=values.get("time_in"),
                        time_out=values.get("time_out"),
                        delay_in=values.get("delay_in", 0.0),
                        delay_out=values.get("delay_out", 0.0),
                        wait=values.get("wait", 0.0),
                        channel_time=channel_time,
                        text=values.get("label", ""))
            App().lightshow.main_playback.add_step(step)

    def _merge_main_playback(self, sequence: int) -> None:
        del App().lightshow.main_playback.steps[-1]
        for step, values in self.data["sequences"][sequence]["steps"].items():
            cue_number = values.get("cue")
            cue_channels = self.data["sequences"][sequence]["cues"][cue_number][
                "channels"]
            cue_text = self.data["sequences"][sequence]["cues"][cue_number]["label"]
            found, step_nb = App().lightshow.main_playback.get_step(cue_number)
            if found:
                # If cue exist, update it
                cue = App().lightshow.main_playback.steps[step_nb - 1].cue
                cue.channels = cue_channels
                cue.text = cue_text
                App().lightshow.main_playback.steps[step_nb -
                                                    1].text = values.get("label")
            else:
                cue = Cue(0, cue_number, cue_channels, text=cue_text)
                self._insert_cue(cue)
                channel_time = {}
                if values.get("channel_time"):
                    for channel, times in values.get("channel_time").items():
                        channel_time[channel] = ChannelTime(times.get("delay", 0.0),
                                                            times.get("time", 0.0))
                step = Step(sequence,
                            cue,
                            time_in=values.get("time_in"),
                            time_out=values.get("time_out"),
                            delay_in=values.get("delay_in", 0.0),
                            delay_out=values.get("delay_out", 0.0),
                            wait=values.get("wait", 0.0),
                            channel_time=channel_time,
                            text=values.get("label", ""))
                App().lightshow.main_playback.insert_step(step_nb, step)

    def import_chaser(self, sequence: int, action: Action) -> None:
        """Import Chaser

        Args:
            sequence: Sequence number
            action: Action type
        """
        label = self.data["sequences"][sequence]["label"]
        chaser = None
        index = None
        for index, chsr in enumerate(App().lightshow.chasers):
            if chsr.index == sequence:
                chaser = chsr
                break
        if not chaser:
            App().lightshow.chasers.append(
                Sequence(sequence, type_seq="Chaser", text=label))
            index = -1
            del App().lightshow.chasers[index].steps[1:]
        else:
            App().lightshow.chasers[index].text = label
        if action is Action.REPLACE:
            self._replace_chaser(sequence, index)
        elif action is Action.MERGE:
            self._merge_chaser(sequence, index)

    def _merge_chaser(self, sequence: int, index: int) -> None:
        for step, values in self.data["sequences"][sequence]["steps"].items():
            cue_number = values.get("cue")
            cue_channels = self.data["sequences"][sequence]["cues"][cue_number][
                "channels"]
            cue_text = self.data["sequences"][sequence]["cues"][cue_number]["label"]
            found, step_nb = App().lightshow.chasers[index].get_step(cue_number)
            if found:
                cue = App().lightshow.chasers[index].steps[step_nb - 1].cue
                cue.channels = cue_channels
                cue.text = cue_text
                App().lightshow.chasers[index].steps[step_nb -
                                                     1].text = values.get("label")
            else:
                cue = Cue(sequence, cue_number, cue_channels, text=cue_text)
                App().lightshow.chasers[index].cues.add(cue)
                channel_time = {}
                if values.get("channel_time"):
                    for channel, times in values.get("channel_time").items():
                        channel_time[channel] = ChannelTime(times.get("delay", 0.0),
                                                            times.get("time", 0.0))
                step = Step(sequence,
                            cue,
                            time_in=values.get("time_in"),
                            time_out=values.get("time_out"),
                            delay_in=values.get("delay_in", 0.0),
                            delay_out=values.get("delay_out", 0.0),
                            wait=values.get("wait", 0.0),
                            channel_time=channel_time,
                            text=values.get("label", ""))
                App().lightshow.chasers[index].insert_step(step_nb, step)

    def _replace_chaser(self, sequence: int, index: int) -> None:
        for step, values in self.data["sequences"][sequence]["steps"].items():
            cue_number = values.get("cue")
            cue_channels = self.data["sequences"][sequence]["cues"][cue_number][
                "channels"]
            cue_text = self.data["sequences"][sequence]["cues"][cue_number]["label"]
            found = False
            cue = None
            for cue in App().lightshow.chasers[index].cues:
                if cue.memory == cue_number:
                    found = True
                    break
            if found:
                # If cue exist, update it
                cue.channels = cue_channels
                cue.text = cue_text
            else:
                # Else, create it
                cue = Cue(sequence, cue_number, cue_channels, text=cue_text)
                App().lightshow.chasers[index].cues.add(cue)
            channel_time = {}
            if values.get("channel_time"):
                for channel, times in values.get("channel_time").items():
                    channel_time[channel] = ChannelTime(times.get("delay", 0.0),
                                                        times.get("time", 0.0))
            # Create new step
            step = Step(sequence,
                        cue,
                        time_in=values.get("time_in"),
                        time_out=values.get("time_out"),
                        delay_in=values.get("delay_in", 0.0),
                        delay_out=values.get("delay_out", 0.0),
                        wait=values.get("wait", 0.0),
                        channel_time=channel_time,
                        text=values.get("label", ""))
            App().lightshow.chasers[index].add_step(step)

    def _insert_cue(self, cue: Cue) -> None:
        """Insert cue in list cues

        Args:
            cue: Cue to insert
        """
        cue_number = cue.memory
        # Find cue position
        found = False
        index = 0
        for index, cue_seq in enumerate(App().lightshow.cues):
            if cue_seq.memory > cue_number:
                found = True
                break
        if not found:
            # Cue is at the end
            index += 1
        # Insert cue
        App().lightshow.cues.insert(index, cue)
        App().lightshow.main_playback.update_channels()
