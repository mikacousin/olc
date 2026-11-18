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

import html
import re
import typing
from enum import Enum, auto

from olc.define import MAX_CHANNELS, NB_UNIVERSES, UNIVERSES, string_to_time
from olc.files.ascii.eos_devices import (
    build_device_and_definition,
    decode_eos_cue_params,
    is_dimmer_personality,
)
from olc.files.read import ReadFile
from olc.show.curve import LimitCurve
from olc.show.fader import FaderType

if typing.TYPE_CHECKING:
    from olc.files.import_file import ImportFile


class State(Enum):
    """States for AsciiParser"""

    START = auto()
    NO_PRIMARY = auto()
    NEW_CUE = auto()
    NEW_GROUP = auto()
    NEW_SUB = auto()
    NEW_MPRIMARY = auto()
    NEW_PRESET = auto()
    NEW_FADER = auto()
    NEW_PERSONALITY = auto()
    NEW_PATCH = auto()
    IN_CUE = auto()
    IN_GROUP = auto()
    IN_SUB = auto()
    IN_SEQUENCE = auto()
    IN_INDEPENDENT = auto()
    IN_PRESET = auto()
    IN_FADER = auto()
    IN_PERSONALITY = auto()
    IN_PATCH = auto()


# pylint: disable=too-many-instance-attributes
class AsciiParser(ReadFile):
    """To Parse ASCII Light Cue files"""

    tokens: dict[str, tuple[str, ...]]
    state: State
    keyword: str
    args: list[str]
    current: dict[str, typing.Any]

    def __init__(
        self,
        imported: ImportFile,
        default_time: float,
        importation: bool = True,
    ) -> None:
        super().__init__(imported, window=imported.window, importation=importation)
        self.lightshow = imported.lightshow
        self.data = imported.data.data
        self.default_time = default_time
        self.tokens = {
            "basic": (
                "clear",
                "console",
                "ident",
                "manufacturer",
                "patch",
                "set",
                "$paramtype",
            ),
            "cue": (
                "chan",
                "down",
                "followon",
                "link",
                "part",
                "text",
                "up",
                "$$block",
                "$$dwell",
                "$$param",
                "$$parttime",
                "$$parttimechan",
                "$$presettext",
                "$$text",
                "$$timecolor",
                "$$timedown",
                "$$timegraphic",
                "$$timeposition",
                "$$timeup",
                "$$utext",
                "$$wait",
            ),
        }
        self.state = State.START
        self.keyword = ""
        self.args = []
        self.param_types: dict[int, str] = {}
        self.personalities: dict[int, dict[str, typing.Any]] = {}
        self.channel_personality: dict[int, int] = {}
        self._registered_fdef_keys: set[tuple[str, str]] = set()
        self._cue_raw_params: dict[int, list[tuple[int, float]]] = {}
        self.current = {
            "step": 0,
            "cue": 0.0,
            "channel_time": (0.0, 0.0),
            "sequence": 1,
            "group": 0.0,
            "independent": 0,
            "preset": 0.0,
            "fader": 0,
            "personality": 0,
            "patch_channel": 0,
            "utext_active": False,
            "pending_wait": {},
        }

    def parse(self) -> None:
        """Parse file line by line"""
        for line in self.contents.splitlines():
            line = line.strip()
            if line:
                loop = self._do_parse(line)
                if not loop:
                    break

    def _do_parse(self, line: str) -> bool:
        """Parse line

        Args:
            line: string to parse

        Returns:
            True to continue reading loop, False to stop it
        """
        # Tokenize
        tokens = re.split(r"[\t,/; =><@]+", line)
        self.keyword = tokens[0].lower()
        # Specials keywords
        if self.keyword == "enddata":
            # Stop loop
            return False
        if self.keyword[0] == "!":
            # Ignore comment line
            return True
        if self.keyword in ("text", "$$text", "$$utext", "$$presettext"):
            # Preserve punctuation, HTML entities (&#8594;), and raw spacing
            parts = line.split(None, 1)
            self.args = [parts[1]] if len(parts) > 1 else []
        else:
            self.args = tokens[1:]
            # Remove comments at end of line
            for num, arg in enumerate(self.args):
                idx = arg.rfind("!")
                if idx >= 0:
                    self.args[num] = self.args[num][:idx]
                    self.args = self.args[: num + 1]
            self.args = [arg.lower() for arg in self.args if arg != ""]

        self._set_state()
        self._do_action()

        return True

    def _do_action(self) -> None:
        if self.keyword in self.tokens["basic"]:
            self._do_basic()
        elif self.state is State.NEW_MPRIMARY:
            self._new_mprimary()
        elif self.state is State.IN_SEQUENCE:
            self._do_sequence()
        elif self.state is State.NEW_CUE:
            self._new_cue()
        elif self.state is State.IN_CUE:
            self._do_cue()
        elif self.state is State.NEW_GROUP:
            self._new_group()
        elif self.state is State.IN_GROUP:
            self._do_group()
        elif self.state is State.IN_INDEPENDENT:
            self._do_independent()
        elif self.state is State.NEW_PRESET:
            self._new_preset()
        elif self.state is State.IN_PRESET:
            self._do_preset()
        elif self.state is State.NEW_FADER:
            self._new_fader()
        elif self.state is State.IN_FADER:
            self._do_fader()
        elif self.state is State.NEW_PERSONALITY:
            self._new_personality()
        elif self.state is State.IN_PERSONALITY:
            self._do_personality()
        elif self.state is State.NEW_PATCH:
            self._new_patch()
        elif self.state is State.IN_PATCH:
            self._do_patch_device()

    def _do_basic(self) -> None:
        if self.keyword == "ident":
            if self.args[0] != "3:0":
                print("Unexpected protocol version")
        elif self.keyword == "manufacturer":
            self.data["console"]["manufacturer"] = self.args[0]
        elif self.keyword == "console":
            self.data["console"]["console"] = self.args[0]
        if self.keyword == "clear":
            # Lets user choose
            pass
        elif self.keyword == "patch":
            self._do_patch()
        elif self.keyword == "set":
            # Not implemented
            pass
        elif self.keyword == "$paramtype" and len(self.args) >= 3:
            self.param_types[int(self.args[0])] = self.args[2]

    def _do_patch(self) -> None:
        # self.args[0] is Page Patch, not used
        for index in range(1, len(self.args), 3):
            channel, dimmer, lvl = self.args[index : index + 3]
            level = self._get_level(lvl)
            self._add_patch(int(channel), int(dimmer), level)

    def _add_patch(self, channel: int, dimmer: int, level: float) -> None:
        """Add patch info to stored data

        Args:
            channel: Channel (1 - MAX_CHANNELS)
            dimmer: Dimmer (1 - 512 * NB_UNIVERSES)
            level: Proportional level (1 - 255)
        """
        univ_index = int((dimmer - 1) / 512)
        if univ_index < NB_UNIVERSES:
            univ = UNIVERSES[univ_index]
            if channel <= MAX_CHANNELS:
                address = dimmer - (512 * univ_index)
                curve_nb = 0
                if level < 1.0:
                    limit_dmx = int(round(level * 255.0))
                    curve_nb = self.lightshow.curves.find_limit_curve(limit_dmx)
                    if not curve_nb:
                        curve_nb = self.lightshow.curves.add_curve(
                            LimitCurve(limit_dmx)
                        )
                    self.data["curves"][curve_nb] = {
                        "type": "LimitCurve",
                        "limit": limit_dmx,
                    }
                if channel not in self.data["patch"]:
                    self.data["patch"][channel] = [
                        {"output": address, "universe": univ, "curve": curve_nb}
                    ]
                else:
                    self.data["patch"][channel].append(
                        {"output": address, "universe": univ, "curve": curve_nb}
                    )

    def _apply_label(self, target: dict[str, typing.Any], key: str = "label") -> None:
        """Apply Text / $$Text / $$UText to *target*, decoding HTML entities."""
        raw = self.args[0] if self.args else ""
        if self.keyword == "$$utext":
            decoded = html.unescape(raw)
            if self.current["utext_active"]:
                target[key] = f"{target.get(key, '')}{decoded}"
            else:
                target[key] = decoded
                self.current["utext_active"] = True
        else:
            target[key] = raw
            self.current["utext_active"] = False

    def _ensure_sequence(self, seq_number: int, mode: str = "normal") -> None:
        """Ensure sequence entry exists in parsed data."""
        if seq_number not in self.data["sequences"]:
            self.data["sequences"][seq_number] = {
                "label": "",
                "mode": mode,
                "steps": {},
                "cues": {},
            }

    def _new_mprimary(self) -> None:
        if self.keyword in ("$sequence", "$cuelist"):
            mode = "normal"
            seq_number = int(self.args[0])
            if self._is_console("nicobats", "dlight") and seq_number == 0:
                # DLight MainPlayback is number 0, need to be number 1
                seq_number = 1
            if (
                self._is_console("avab", "congo")
                and len(self.args) > 1
                and int(self.args[1]) == 1
            ):
                mode = "chaser"
            self._ensure_sequence(seq_number, mode=mode)
            self.data["sequences"][seq_number]["mode"] = mode
            self.current["sequence"] = seq_number
            self.current["step"] = len(self.data["sequences"][seq_number]["steps"])
            self.current["utext_active"] = False
            self.state = State.IN_SEQUENCE
        elif self.keyword == "$specialfunction":
            # Parameters not implemented:
            # ftype = self.args[1]  # 0: inclusive, 1: Inhibit, 2: Exclusive
            # button_mode = self.args[2]  # 0: Momentary, 1: Toggling
            number = int(self.args[0])
            self.data["independents"][number] = {"label": "", "channels": {}}
            self.current["independent"] = number
            self.current["utext_active"] = False
            self.state = State.IN_INDEPENDENT

    def _do_sequence(self) -> None:
        if self.keyword in ("text", "$$text", "$$utext"):
            self._apply_label(self.data["sequences"][self.current["sequence"]])

    def _do_independent(self) -> None:
        if self.keyword in ("text", "$$text"):
            label = " ".join(self.args)
            self.data["independents"][self.current["independent"]]["label"] = label
        if self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                level = self._get_level(self.args[index + 1])
                self.data["independents"][self.current["independent"]]["channels"][
                    channel
                ] = level

    def _new_cue(self) -> None:
        if self.keyword == "cue":
            # CUE cue_number [cuelist_number]
            cue_number = float(self.args[0])
            seq_number = (
                int(self.args[1])
                if len(self.args) >= 2
                else int(self.current["sequence"])
            )
        else:
            # $CUE sequence_number cue_number
            seq_number = int(self.args[0])
            cue_number = float(self.args[1])

        self._ensure_sequence(seq_number, mode="normal")
        self.current["sequence"] = seq_number
        steps = self.data["sequences"][seq_number]["steps"]
        step_nb = len(steps) + 1
        self.current["step"] = step_nb
        wait_val = float(self.current["pending_wait"].pop(seq_number, 0.0))

        steps[step_nb] = {
            "cue": cue_number,
            "time_in": self.default_time,
            "time_out": self.default_time,
            "delay_in": 0.0,
            "delay_out": 0.0,
            "wait": wait_val,
            "channel_time": {},
            "label": "",
        }
        self.data["sequences"][seq_number]["cues"][cue_number] = {
            "label": "",
            "channels": {},
        }
        self.current["cue"] = cue_number
        self.current["utext_active"] = False
        self._cue_raw_params = {}
        self.state = State.IN_CUE

    def _do_cue(self) -> None:
        # Missed keywords: link, part
        cues = self.data["sequences"][self.current["sequence"]]["cues"]
        steps = self.data["sequences"][self.current["sequence"]]["steps"]
        step = steps[self.current["step"]]
        cue = cues[self.current["cue"]]
        if self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                if channel <= MAX_CHANNELS:
                    level = self._get_level(self.args[index + 1])
                    cue["channels"][channel] = level
        elif self.keyword in ("down", "$$timedown") and self.args:
            time = string_to_time(self.args[0])
            if not time and self.keyword == "down":
                time = self.default_time
            delay = string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            step["time_out"] = time
            step["delay_out"] = delay
        elif self.keyword in ("up", "$$timeup") and self.args:
            time = string_to_time(self.args[0])
            if not time and self.keyword == "up":
                time = self.default_time
            delay = string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            step["time_in"] = time
            step["delay_in"] = delay
        elif self.keyword == "$$timeposition" and self.args:
            step["time_position"] = string_to_time(self.args[0])
            step["delay_position"] = (
                string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            )
        elif self.keyword == "$$timecolor" and self.args:
            step["time_color"] = string_to_time(self.args[0])
            step["delay_color"] = (
                string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            )
        elif self.keyword == "$$timegraphic" and self.args:
            step["time_beam"] = string_to_time(self.args[0])
            step["delay_beam"] = (
                string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            )
        elif self.keyword in ("text", "$$text", "$$utext", "$$presettext"):
            self._apply_label(step)
            cue["label"] = step["label"]
        elif self.keyword in ("$$wait", "$$dwell", "followon") and self.args:
            # Eos executes wait/follow at the end of cue N; OLC executes wait at
            # the start of cue N+1, so queue it for the next step in this sequence.
            self.current["pending_wait"][self.current["sequence"]] = string_to_time(
                self.args[0]
            )
        elif self.keyword == "$$block":
            cue["is_block"] = True
        elif self.keyword == "$$param" and len(self.args) >= 3:
            channel = int(self.args[0])
            if channel <= MAX_CHANNELS:
                raw_list = self._cue_raw_params.setdefault(channel, [])
                for index in range(1, len(self.args) - 1, 2):
                    try:
                        p_id = int(self.args[index])
                        raw_val = float(self.args[index + 1])
                    except ValueError:
                        # Palette references (e.g. cp106, fp12, bp5) are skipped for now
                        continue
                    raw_list.append((p_id, raw_val))
                pers_id = self.channel_personality.get(channel)
                pers = self.personalities.get(pers_id) if pers_id is not None else None
                dev_vals, intensity_val = decode_eos_cue_params(
                    raw_list, pers, self.param_types
                )
                if dev_vals:
                    cue.setdefault("device_values", {})[channel] = dev_vals
                if intensity_val is not None and channel not in cue["channels"]:
                    cue["channels"][channel] = intensity_val
        elif self.keyword == "$$parttime":
            delay = string_to_time(self.args[0])
            time = string_to_time(self.args[1])
            self.current["channel_time"] = (delay, time)
        elif self.keyword == "$$parttimechan":
            for arg in self.args:
                steps[self.current["step"]]["channel_time"][int(arg)] = {
                    "delay": self.current["channel_time"][0],
                    "time": self.current["channel_time"][1],
                }

    def _new_preset(self) -> None:
        number = float(self.args[0])
        self.data["cues"][number] = {"label": "", "channels": {}}
        self.current["preset"] = number
        self.state = State.IN_PRESET

    def _do_preset(self) -> None:
        if self.keyword in ("text", "$$text"):
            label = " ".join(self.args)
            self.data["cues"][self.current["preset"]]["label"] = label
        elif self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                level = self._get_level(self.args[index + 1])
                self.data["cues"][self.current["preset"]]["channels"][channel] = level

    def _new_group(self) -> None:
        group_number = float(self.args[0])
        self.data["groups"][group_number] = {"label": "", "channels": {}}
        self.current["group"] = group_number
        self.state = State.IN_GROUP

    def _do_group(self) -> None:
        if self.keyword in ("text", "$$text", "$$presettext"):
            label = " ".join(self.args)
            self.data["groups"][self.current["group"]]["label"] = label
        elif self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                level = self._get_level(self.args[index + 1])
                self.data["groups"][self.current["group"]]["channels"][channel] = level

    def _new_fader(self) -> None:
        page = int(self.args[0])
        number = int(self.args[1])
        fader_type = int(self.args[2])
        contents = int(self.args[3]) if int(self.args[3]) else None
        if self._is_console("nicobats", "dlight") and fader_type == FaderType.CHANNELS:
            # DLight use channels type for groups
            fader_type = FaderType.GROUP
        index = number - 1 + ((page - 1) * 10)
        if fader_type == FaderType.CHANNELS:
            self.data["faders"][index] = {
                "page": page,
                "number": number,
                "type": fader_type,
                "contents": {},
            }
            self.current["fader"] = index
            self.state = State.IN_FADER
        else:
            self.data["faders"][index] = {
                "page": page,
                "number": number,
                "type": fader_type,
                "contents": contents,
            }
            self.state = State.NO_PRIMARY

    def _do_fader(self) -> None:
        if self.keyword in "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                level = self._get_level(self.args[index + 1])
                self.data["faders"][self.current["fader"]]["contents"][channel] = level

    def _get_level(self, level: str) -> float:
        if level[0] == "h":
            return int(level[1:], 16) / 255.0
        return float(level) / 100.0

    def _new_personality(self) -> None:
        pers_id = int(self.args[0])
        self.personalities[pers_id] = {
            "manufacturer": "",
            "model": f"Personality {pers_id}",
            "dcid": "",
            "footprint": 1,
            "virtual_int": False,
            "channels": [],
        }
        self.current["personality"] = pers_id
        self.state = State.IN_PERSONALITY

    def _do_personality(self) -> None:
        pers = self.personalities.get(self.current["personality"])
        if pers is None:
            return
        if self.keyword == "$$manuf" and self.args:
            pers["manufacturer"] = " ".join(self.args)
        elif self.keyword == "$$model" and self.args:
            pers["model"] = " ".join(self.args)
        elif self.keyword == "$$dcid" and self.args:
            pers["dcid"] = self.args[0]
        elif self.keyword == "$$footprint" and self.args:
            pers["footprint"] = int(self.args[0])
        elif self.keyword == "$$virtualint":
            pers["virtual_int"] = True
        elif self.keyword == "$$perschan" and len(self.args) >= 5:
            pers["channels"].append(
                {
                    "param_id": int(self.args[0]),
                    "bytes": int(self.args[1]),
                    "offset_coarse": int(self.args[2]),
                    "offset_fine": int(self.args[3]),
                    "default": int(self.args[4]),
                    "phys_min": 0.0,
                    "phys_max": 1.0,
                    "slots": 0,
                }
            )
        elif self.keyword == "$$persslot" and len(self.args) >= 5 and pers["channels"]:
            ch_def = pers["channels"][-1]
            p_min = float(self.args[3])
            p_max = float(self.args[4])
            if ch_def["slots"] == 0:
                ch_def["phys_min"] = p_min
                ch_def["phys_max"] = p_max
            else:
                ch_def["phys_min"] = min(ch_def["phys_min"], p_min)
                ch_def["phys_max"] = max(ch_def["phys_max"], p_max)
            ch_def["slots"] += 1

    def _new_patch(self) -> None:
        if len(self.args) < 3:
            self.state = State.NO_PRIMARY
            return
        channel = int(self.args[0])
        pers_id = int(self.args[1])
        dmx_addr = int(self.args[2])
        curve_id = int(self.args[3]) if len(self.args) > 3 else 0

        if channel > MAX_CHANNELS or dmx_addr < 1:
            self.state = State.NO_PRIMARY
            return

        self.channel_personality[channel] = pers_id
        self.current["patch_channel"] = channel
        pers = self.personalities.get(pers_id)

        if pers is None or is_dimmer_personality(pers, self.param_types):
            self._add_patch(channel, dmx_addr, 1.0)
            if curve_id and channel in self.data["patch"]:
                self.data["patch"][channel][-1]["curve"] = curve_id
        else:
            built = build_device_and_definition(
                channel, pers_id, dmx_addr, curve_id, pers, self.param_types
            )
            if built is not None:
                device_dict, fdef_dict = built
                self.data.setdefault("devices", {})[channel] = device_dict
                key = (fdef_dict["manufacturer"], fdef_dict["model"])
                if key not in self._registered_fdef_keys:
                    self._registered_fdef_keys.add(key)
                    self.data.setdefault("fixture_definitions", []).append(fdef_dict)

        self.state = State.IN_PATCH

    def _do_patch_device(self) -> None:
        ch = self.current.get("patch_channel", 0)
        dev = self.data.get("devices", {}).get(ch)
        if dev is not None and self.keyword == "$$pers" and self.args:
            model = " ".join(self.args)
            dev["model"] = model
            dev["label"] = f"{model} {ch}"

    def _set_state(self) -> None:
        if self.state is State.START and self.keyword in self.tokens["basic"]:
            self.state = State.NO_PRIMARY
        elif self.keyword == "$personality":
            self.state = State.NEW_PERSONALITY
        elif self.keyword == "$patch":
            self.state = State.NEW_PATCH
        elif self.keyword in ("$sequence", "$cuelist", "$specialfunction"):
            self.state = State.NEW_MPRIMARY
        elif self.keyword in ("cue", "$cue"):
            self.state = State.NEW_CUE
        elif self.keyword == "$group" or (
            self.keyword == "group" and not self._is_console("avab", "congo")
        ):
            self.state = State.NEW_GROUP
        elif (
            self.keyword == "$preset"
            and (
                self._is_console("nicobats", "dlight")
                or self._is_console("avab", "vlc")
            )
        ) or (self.keyword == "group" and self._is_console("avab", "congo")):
            self.state = State.NEW_PRESET
        elif self.keyword == "$mastpageitem":
            self.state = State.NEW_FADER
        elif self.keyword == "sub":
            self.state = State.NEW_SUB
        elif (
            self.state in (State.START, State.NO_PRIMARY)
            and self.keyword in self.tokens["cue"]
        ):
            # print(f"{self.keyword} before a primary keyword, skipping")
            self.state = State.NO_PRIMARY

    def _is_console(self, manufacturer: str, console: str) -> bool:
        if (
            manufacturer == self.data["console"]["manufacturer"]
            and console == self.data["console"]["console"]
        ):
            return True
        return False
