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
from __future__ import annotations

import json
import typing
from typing import Any

from olc.curve import InterpolateCurve, LimitCurve, SegmentsCurve
from olc.define import App
from olc.fader import FaderType
from olc.files.write import WriteFile

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.sequence import Sequence


class OlcWriter(WriteFile):
    """Write olc file"""

    data: dict[str, Any]

    def __init__(self, file: Gio.File):
        super().__init__(file, compressed=True)
        self.data = {}
        self.data = {"application": "olc", "version": "0.8.5.beta"}

    def export(self) -> None:
        self._curves()
        self._patch()
        self._sequences()
        self._cues()
        self._groups()
        self._faders()
        self._independents()
        self._midi()

        json_str = json.dumps(self.data, indent=2, ensure_ascii=False, sort_keys=False)

        self.stream.write(bytes(json_str, "utf-8"))

    def _patch(self) -> None:
        self.data["patch"] = {}
        for channel, values in App().lightshow.patch.channels.items():
            if not App().lightshow.patch.is_patched(channel):
                continue
            self.data["patch"][channel] = []
            for outputs in values:
                output = outputs[0]
                univ = outputs[1]
                curve_num = App().lightshow.patch.outputs[univ][output][1]
                if curve_num:
                    self.data["patch"][channel].append({
                        "output": output,
                        "universe": univ,
                        "curve": curve_num
                    })
                else:
                    self.data["patch"][channel].append({
                        "output": output,
                        "universe": univ,
                    })
        if not self.data["patch"]:
            del self.data["patch"]

    def _sequences(self) -> None:
        self.data["sequences"] = {}
        self._do_sequence(App().lightshow.main_playback)
        for chaser in App().lightshow.chasers:
            self._do_sequence(chaser)

    def _do_sequence(self, sequence: Sequence) -> None:
        seq_index = sequence.index
        self.data["sequences"][seq_index] = {
            "label": sequence.text,
            "steps": {},
            "cues": {}
        }
        for index, step in enumerate(sequence.steps):
            if step.cue.memory == 0:
                continue
            self.data["sequences"][seq_index]["steps"][index] = {
                "cue": step.cue.memory,
                "time_in": step.time_in,
                "time_out": step.time_out,
            }
            if step.delay_in:
                self.data["sequences"][seq_index]["steps"][index][
                    "delay_in"] = step.delay_in
            if step.delay_out:
                self.data["sequences"][seq_index]["steps"][index][
                    "delay_out"] = step.delay_out
            if step.wait:
                self.data["sequences"][seq_index]["steps"][index]["wait"] = step.wait
            if step.channel_time:
                self.data["sequences"][seq_index]["steps"][index]["channel_time"] = {}
                for channel, times in step.channel_time.items():
                    self.data["sequences"][seq_index]["steps"][index]["channel_time"][
                        channel] = {
                            "delay": times.delay,
                            "time": times.time
                        }
            if step.text:
                self.data["sequences"][seq_index]["steps"][index]["label"] = step.text
            self.data["sequences"][seq_index]["cues"][step.cue.memory] = {
                "label": step.cue.text,
                "channels": step.cue.channels
            }

    def _cues(self) -> None:
        self.data["cues"] = {}
        for cue in App().lightshow.cues:
            self.data["cues"][cue.memory] = {
                "label": cue.text,
                "channels": cue.channels
            }

    def _groups(self) -> None:
        self.data["groups"] = {}
        for group in App().lightshow.groups:
            self.data["groups"][group.index] = {
                "label": group.text,
                "channels": group.channels
            }
        if not self.data["groups"]:
            del self.data["groups"]

    def _faders(self) -> None:
        self.data["faders"] = []
        for page, faders in App().lightshow.fader_bank.faders.items():
            for index, fader in faders.items():
                content_type = App().lightshow.fader_bank.get_fader_type(page, index)
                if content_type == FaderType.GROUP:
                    self.data["faders"].append({
                        "page": page,
                        "index": index,
                        "type": content_type,
                        "contents": fader.contents.index,
                        "text": fader.text
                    })
                elif content_type == FaderType.SEQUENCE:
                    self.data["faders"].append({
                        "page": page,
                        "index": index,
                        "type": content_type,
                        "contents": fader.contents.index,
                        "text": fader.text
                    })
                elif content_type == FaderType.PRESET:
                    self.data["faders"].append({
                        "page": page,
                        "index": index,
                        "type": content_type,
                        "contents": fader.contents.memory,
                        "text": fader.text
                    })
                elif content_type == FaderType.MAIN:
                    self.data["faders"].append({
                        "page": page,
                        "index": index,
                        "type": content_type,
                        "text": fader.text
                    })
        if not self.data["faders"]:
            del self.data["faders"]

    def _independents(self) -> None:
        self.data["independents"] = {}
        for inde in App().lightshow.independents.independents:
            self.data["independents"][inde.number] = {
                "type": inde.inde_type,
                "label": inde.text,
                "channels": inde.levels
            }

    def _curves(self) -> None:
        self.data["curves"] = {}
        for key, curve in App().lightshow.curves.curves.items():
            if key >= 10:
                curve_type = curve.__class__.__name__
                if isinstance(curve, LimitCurve):
                    self.data["curves"][key] = {
                        "type": curve_type,
                        "limit": curve.limit,
                        "label": curve.name
                    }
                elif isinstance(curve, (SegmentsCurve, InterpolateCurve)):
                    self.data["curves"][key] = {
                        "type": curve_type,
                        "points": curve.points,
                        "label": curve.name
                    }
        if not self.data["curves"]:
            del self.data["curves"]

    def _midi(self) -> None:
        self.data["midi_mapping"] = {}
        midi = App().midi.messages
        self.data["midi_mapping"]["note"] = midi.notes.notes
        self.data["midi_mapping"]["control_change"] = midi.control_change.control_change
        self.data["midi_mapping"]["pitchwheel"] = midi.pitchwheel.pitchwheel
