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
import logging
import re
import typing
from enum import Enum, auto

from olc.define import (
    MAX_ALLOWED_FADER_PAGES,
    MAX_CHANNELS,
    MAX_FADER_PER_PAGE,
    NB_UNIVERSES,
    UNIVERSES,
    string_to_time,
)
from olc.files.ascii.eos_devices import (
    build_device_from_definition,
    build_fixture_definition,
    decode_eos_cue_params,
    eos_param_id_to_olc_key,
    is_dimmer_personality,
    parse_eos_param_token,
)
from olc.files.ascii.eos_effects import (
    convert_eos_effect,
    new_eos_effect,
    parse_effect_data_value,
    record_eos_effect_line,
)
from olc.files.read import ReadFile
from olc.show.curve import LimitCurve
from olc.show.fader import LEGACY_FADER_TYPE_GROUP, FaderType
from olc.show.palette import PaletteCategory

LOGGER = logging.getLogger(__name__)
_TOKEN_SPLIT_RE = re.compile(r"[\t,/; =><@]+")

if typing.TYPE_CHECKING:
    from olc.files.import_file import ImportFile

_EOS_PALETTE_KEYWORDS: dict[str, PaletteCategory] = {
    "$intensitypalette": PaletteCategory.INTENSITY,
    "$focuspalette": PaletteCategory.FOCUS,
    "$colorpalette": PaletteCategory.COLOR,
    "$beampalette": PaletteCategory.BEAM,
}

_RAW_TEXT_KEYWORDS: frozenset[str] = frozenset(
    {
        "text",
        "$$text",
        "$$utext",
        "$$presettext",
        "$$manuf",
        "$$model",
        "$$dcid",
        "$$pers",
        "$$persslot",
        "$$perssltext",
        "$$notes",
        "$$title",
        "$$cuenotes",
    }
)

_PERSSLOT_RE = re.compile(
    r"^(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(.*))?$"
)


class State(Enum):
    """States for AsciiParser"""

    START = auto()
    NO_PRIMARY = auto()
    NEW_CUE = auto()
    NEW_GROUP = auto()
    NEW_SUB = auto()
    NEW_MPRIMARY = auto()
    NEW_PRESET = auto()
    NEW_EOS_PRESET = auto()
    NEW_PALETTE = auto()
    NEW_FADER = auto()
    NEW_PERSONALITY = auto()
    NEW_PATCH = auto()
    NEW_CURVE = auto()
    NEW_FADERDEF = auto()
    NEW_EFFECT = auto()
    IN_CUE = auto()
    IN_GROUP = auto()
    IN_SUB = auto()
    IN_SEQUENCE = auto()
    IN_INDEPENDENT = auto()
    IN_PRESET = auto()
    IN_EOS_PRESET = auto()
    IN_PALETTE = auto()
    IN_FADER = auto()
    IN_PERSONALITY = auto()
    IN_PATCH = auto()
    IN_CURVE = auto()
    IN_FADERDEF = auto()
    IN_EFFECT = auto()


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
                "$$title",
                "$$automark",
                "$$homepreset",
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
        self._registered_fdefs: dict[tuple[str, str], dict[str, typing.Any]] = {}
        self._pers_fdef_info: dict[int, tuple[dict[str, typing.Any], str]] = {}
        self._palette_raw_params: dict[
            tuple[str, float], dict[int, dict[int, float]]
        ] = {}
        self._palette_raw_refs: dict[
            tuple[str, float], dict[int, dict[int, tuple[str, float]]]
        ] = {}
        self._sub_raw_params: dict[int, dict[int, dict[int, float]]] = {}
        self._sub_raw_refs: dict[int, dict[int, dict[int, tuple[str, float]]]] = {}
        self._cue_raw_params: dict[tuple[int, float], dict[int, dict[int, float]]] = {}
        self._cue_raw_refs: dict[
            tuple[int, float], dict[int, dict[int, tuple[str, float]]]
        ] = {}
        self.subs: dict[int, dict[str, typing.Any]] = {}
        self._sub_preset_numbers: dict[int, float] = {}
        self._raw_effects: dict[float, dict[str, typing.Any]] = {}
        self._cue_effects: dict[tuple[int, float], dict[str, typing.Any]] = {}
        self._sub_effects: dict[int, dict[str, typing.Any]] = {}
        self._cue_chan_moves: dict[tuple[int, float], dict[int, float]] = {}
        self._cue_execute_subs: dict[tuple[int, float], float] = {}
        self._eos_automark: bool | None = None
        self.current = {
            "step": 0,
            "cue": 0.0,
            "cue_part": 1,
            "part_timing": {
                "time_in": None,
                "delay_in": 0.0,
                "time_out": None,
                "delay_out": 0.0,
            },
            "channel_time": (0.0, 0.0),
            "sequence": 1,
            "group": 0.0,
            "independent": 0,
            "preset": 0.0,
            "eos_preset": 0.0,
            "palette": None,
            "fader": 0,
            "personality": 0,
            "patch_channel": 0,
            "patch_output": None,
            "curve": 0,
            "sub": 0,
            "faderdef": -1,
            "utext_active": False,
            "pending_wait": {},
        }

    def parse(self) -> None:
        """Parse file line by line, then resolve palettes and references."""
        for line in self.contents.splitlines():
            line = line.strip()
            if line:
                loop = self._do_parse(line)
                if not loop:
                    break
        self._finalize_personalities()
        self._finalize_effects()
        self._finalize_unmounted_subs()
        self._resolve_palettes_and_refs()
        self._resolve_effect_refs()
        self._finalize_eos_tracking()

    def _do_parse(self, line: str) -> bool:
        """Parse line

        Args:
            line: string to parse

        Returns:
            True to continue reading loop, False to stop it
        """
        # Tokenize
        tokens = _TOKEN_SPLIT_RE.split(line)
        self.keyword = tokens[0].lower()
        # Specials keywords
        if self.keyword == "enddata":
            # Stop loop
            return False
        if self.keyword[0] == "!":
            # Ignore comment line
            return True
        if self.keyword == "$paramtype":
            parts = line.split(None, 3)
            self.args = parts[1:]
        elif self.keyword in _RAW_TEXT_KEYWORDS:
            # Preserve case, punctuation, HTML entities (&#8594;), and raw spacing
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
        elif self.state is State.NEW_EOS_PRESET:
            self._new_eos_preset()
        elif self.state is State.IN_EOS_PRESET:
            self._do_eos_preset()
        elif self.state is State.NEW_PALETTE:
            self._new_palette()
        elif self.state is State.IN_PALETTE:
            self._do_palette()
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
        elif self.state is State.NEW_CURVE:
            self._new_curve()
        elif self.state is State.IN_CURVE:
            self._do_curve()
        elif self.state is State.NEW_SUB:
            self._new_sub()
        elif self.state is State.IN_SUB:
            self._do_sub()
        elif self.state is State.NEW_FADERDEF:
            self._new_faderdef()
        elif self.state is State.IN_FADERDEF:
            self._do_faderdef()
        elif self.state is State.NEW_EFFECT:
            self._new_effect()
        elif self.state is State.IN_EFFECT:
            self._do_effect()

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
        elif self.keyword == "$$title" and self.args:
            self.data.setdefault("show_metadata", {})["title"] = html.unescape(
                self.args[0]
            )
        elif self.keyword == "$$automark":
            if self.args and self.args[0] in ("0", "false", "off"):
                self._eos_automark = False
            else:
                self._eos_automark = True
        elif self.keyword == "$$homepreset" and self.args:
            try:
                self.data.setdefault("show_metadata", {})["home_preset"] = float(
                    self.args[0]
                )
            except ValueError:
                pass

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
        self.current["cue_part"] = 1
        self.current["part_timing"] = {
            "time_in": None,
            "delay_in": 0.0,
            "time_out": None,
            "delay_out": 0.0,
        }
        self.current["utext_active"] = False
        cue_key = (seq_number, cue_number)
        self._cue_raw_params[cue_key] = {}
        self._cue_raw_refs[cue_key] = {}
        self.state = State.IN_CUE

    def _apply_part_channel_time(
        self,
        step: dict[str, typing.Any],
        channel: int,
        level: float | None = None,
    ) -> None:
        """Record per-channel part time on *step* when inside Eos Part > 1."""
        if int(self.current.get("cue_part", 1)) <= 1:
            return
        pt = self.current["part_timing"]
        t_in, d_in = pt.get("time_in"), float(pt.get("delay_in", 0.0))
        t_out, d_out = pt.get("time_out"), float(pt.get("delay_out", 0.0))
        if level == 0.0 and t_out is not None:
            delay_val, time_val = d_out, float(t_out)
        elif t_in is not None:
            delay_val, time_val = d_in, float(t_in)
        elif t_out is not None:
            delay_val, time_val = d_out, float(t_out)
        else:
            return
        step["channel_time"][channel] = {"delay": delay_val, "time": time_val}

    def _do_cue(self) -> None:
        # Missed keywords: link
        cues = self.data["sequences"][self.current["sequence"]]["cues"]
        steps = self.data["sequences"][self.current["sequence"]]["steps"]
        step = steps[self.current["step"]]
        cue = cues[self.current["cue"]]
        cue_part = int(self.current.get("cue_part", 1))
        if self.keyword == "part" and self.args:
            try:
                self.current["cue_part"] = max(1, int(self.args[0]))
            except ValueError:
                return
            self.current["part_timing"] = {
                "time_in": None,
                "delay_in": 0.0,
                "time_out": None,
                "delay_out": 0.0,
            }
            self.current["utext_active"] = False
        elif self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                if channel <= MAX_CHANNELS:
                    level = self._get_level(self.args[index + 1])
                    cue["channels"][channel] = level
                    self._apply_part_channel_time(step, channel, level)
        elif self.keyword in ("down", "$$timedown") and self.args:
            time = string_to_time(self.args[0])
            if not time and self.keyword == "down":
                time = self.default_time
            delay = string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            if cue_part > 1:
                self.current["part_timing"]["time_out"] = time
                self.current["part_timing"]["delay_out"] = delay
            else:
                step["time_out"] = time
                step["delay_out"] = delay
        elif self.keyword in ("up", "$$timeup") and self.args:
            time = string_to_time(self.args[0])
            if not time and self.keyword == "up":
                time = self.default_time
            delay = string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            if cue_part > 1:
                self.current["part_timing"]["time_in"] = time
                self.current["part_timing"]["delay_in"] = delay
            else:
                step["time_in"] = time
                step["delay_in"] = delay
        elif self.keyword == "$$timeposition" and self.args:
            if cue_part == 1:
                step["time_position"] = string_to_time(self.args[0])
                step["delay_position"] = (
                    string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
                )
        elif self.keyword == "$$timecolor" and self.args:
            if cue_part == 1:
                step["time_color"] = string_to_time(self.args[0])
                step["delay_color"] = (
                    string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
                )
        elif self.keyword == "$$timegraphic" and self.args:
            if cue_part == 1:
                step["time_beam"] = string_to_time(self.args[0])
                step["delay_beam"] = (
                    string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
                )
        elif self.keyword in ("text", "$$text", "$$utext", "$$presettext"):
            if cue_part == 1 or not step["label"]:
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
        elif self.keyword == "$$intblock":
            cue["is_int_block"] = True
        elif self.keyword == "$$assert":
            cue["is_assert"] = True
        elif self.keyword == "$$cuenotes" and self.args:
            note_text = html.unescape(self.args[0])
            if cue.get("notes"):
                cue["notes"] = f"{cue['notes']}\n{note_text}"
            else:
                cue["notes"] = note_text
        elif (
            self.keyword == "$$action"
            and len(self.args) >= 3
            and self.args[0] == "execute"
            and self.args[1] == "s"
        ):
            try:
                cue_key = (int(self.current["sequence"]), float(self.current["cue"]))
                self._cue_execute_subs[cue_key] = float(self.args[2])
            except ValueError:
                pass
        elif self.keyword == "$$chanmove":
            cue_key = (int(self.current["sequence"]), float(self.current["cue"]))
            moves = self._cue_chan_moves.setdefault(cue_key, {})
            for index in range(0, len(self.args) - 1, 2):
                try:
                    channel = int(self.args[index])
                    level = self._get_level(self.args[index + 1])
                except ValueError:
                    continue
                if 1 <= channel <= MAX_CHANNELS:
                    moves[channel] = level
                    self._apply_part_channel_time(step, channel, level)
        elif self.keyword in ("$$effectchan", "$$effectdata"):
            cue_key = (int(self.current["sequence"]), float(self.current["cue"]))
            self._record_effect_call(
                self._cue_effects.setdefault(cue_key, self._new_effect_store())
            )
        elif self.keyword == "$$param" and len(self.args) >= 3:
            cue_key = (int(self.current["sequence"]), float(self.current["cue"]))
            self._record_param_line(
                self._cue_raw_params.setdefault(cue_key, {}),
                self._cue_raw_refs.setdefault(cue_key, {}),
            )
            if cue_part > 1:
                try:
                    ch_param = int(self.args[0])
                except ValueError:
                    ch_param = 0
                if (
                    1 <= ch_param <= MAX_CHANNELS
                    and ch_param not in step["channel_time"]
                ):
                    self._apply_part_channel_time(step, ch_param, level=None)
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

    def _record_param_line(
        self,
        raw_params_by_ch: dict[int, dict[int, float]],
        raw_refs_by_ch: dict[int, dict[int, tuple[str, float]]],
    ) -> None:
        """Record numeric values and palette references from a $$Param line."""
        try:
            channel = int(self.args[0])
        except (IndexError, ValueError):
            return
        if not 1 <= channel <= MAX_CHANNELS:
            return
        ch_raw = raw_params_by_ch.setdefault(channel, {})
        ch_refs = raw_refs_by_ch.setdefault(channel, {})
        for index in range(1, len(self.args) - 1, 2):
            try:
                p_id = int(self.args[index])
            except ValueError:
                continue
            raw_val, pal_ref = parse_eos_param_token(self.args[index + 1])
            if raw_val is not None:
                ch_raw[p_id] = raw_val
            elif pal_ref is not None:
                ch_refs[p_id] = pal_ref

    def _new_palette(self) -> None:
        category = _EOS_PALETTE_KEYWORDS.get(self.keyword)
        if category is None or not self.args:
            self.state = State.NO_PRIMARY
            return
        number = float(self.args[0])
        cat_val = category.value
        pal_dict = self.data.setdefault("palettes", {}).setdefault(cat_val, {})
        pal_dict[number] = {
            "category": cat_val,
            "number": number,
            "label": "",
            "channels": {},
        }
        key = (cat_val, number)
        self._palette_raw_params[key] = {}
        self._palette_raw_refs[key] = {}
        self.current["palette"] = key
        self.current["utext_active"] = False
        self.state = State.IN_PALETTE

    def _do_palette(self) -> None:
        pal_key = self.current.get("palette")
        if pal_key is None:
            return
        cat_val, number = pal_key
        pal = self.data.get("palettes", {}).get(cat_val, {}).get(number)
        if pal is None:
            return
        if self.keyword in ("text", "$$text", "$$utext", "$$presettext"):
            self._apply_label(pal)
        elif self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                if 1 <= channel <= MAX_CHANNELS:
                    pal["channels"][channel] = self._get_level(self.args[index + 1])
        elif self.keyword == "$$param" and len(self.args) >= 3:
            self._record_param_line(
                self._palette_raw_params.setdefault(pal_key, {}),
                self._palette_raw_refs.setdefault(pal_key, {}),
            )

    def _new_eos_preset(self) -> None:
        if not self.args:
            self.state = State.NO_PRIMARY
            return
        number = float(self.args[0])
        presets = self.data.setdefault("palettes", {}).setdefault(
            PaletteCategory.PRESET.value, {}
        )
        presets[number] = {
            "category": PaletteCategory.PRESET.value,
            "number": number,
            "label": "",
            "channels": {},
        }
        key = (PaletteCategory.PRESET.value, number)
        self._palette_raw_params[key] = {}
        self._palette_raw_refs[key] = {}
        self.current["eos_preset"] = number
        self.current["utext_active"] = False
        self.state = State.IN_EOS_PRESET

    def _do_eos_preset(self) -> None:
        presets = self.data.get("palettes", {}).get(PaletteCategory.PRESET.value, {})
        preset = presets.get(self.current["eos_preset"])
        if preset is None:
            return
        if self.keyword in ("text", "$$text", "$$utext", "$$presettext"):
            self._apply_label(preset)
        elif self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                if 1 <= channel <= MAX_CHANNELS:
                    preset["channels"][channel] = self._get_level(self.args[index + 1])
        elif self.keyword == "$$param" and len(self.args) >= 3:
            key = (PaletteCategory.PRESET.value, float(self.current["eos_preset"]))
            self._record_param_line(
                self._palette_raw_params.setdefault(key, {}),
                self._palette_raw_refs.setdefault(key, {}),
            )

    def _new_group(self) -> None:
        group_number = float(self.args[0])
        self.data["groups"][group_number] = {"label": "", "channels": []}
        self.current["group"] = group_number
        self.current["utext_active"] = False
        self.state = State.IN_GROUP

    def _do_group(self) -> None:
        grp = self.data["groups"][self.current["group"]]
        if self.keyword in ("text", "$$text", "$$utext", "$$presettext"):
            self._apply_label(grp)
        elif self.keyword == "chan":
            legacy_levels = grp.setdefault("legacy_levels", {})
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                if 1 <= channel <= MAX_CHANNELS:
                    if channel not in grp["channels"]:
                        grp["channels"].append(channel)
                    legacy_levels[channel] = self._get_level(self.args[index + 1])
        elif self.keyword == "$$chanlist":
            for arg in self.args:
                channel = int(arg)
                if 1 <= channel <= MAX_CHANNELS and channel not in grp["channels"]:
                    grp["channels"].append(channel)

    def _new_fader(self) -> None:
        page = int(self.args[0])
        number = int(self.args[1])
        fader_type = int(self.args[2])
        raw_contents = float(self.args[3])
        contents: int | float | None = None
        if raw_contents != 0.0:
            contents = int(raw_contents) if raw_contents.is_integer() else raw_contents
        if self._is_console("nicobats", "dlight") and fader_type == FaderType.CHANNELS:
            # DLight uses channels type for groups -> migrate via legacy group path
            fader_type = LEGACY_FADER_TYPE_GROUP
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
        elif fader_type == FaderType.EFFECT:
            self.data["faders"][index] = {
                "page": page,
                "number": number,
                "type": fader_type,
                "contents": contents,
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
            self.current["fader"] = index
            self.state = State.IN_FADER

    def _do_fader(self) -> None:
        fader = self.data["faders"].get(self.current.get("fader"))
        if not isinstance(fader, dict):
            return
        if self.keyword == "chan" and isinstance(fader.get("contents"), dict):
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                level = self._get_level(self.args[index + 1])
                fader["contents"][channel] = level
        elif self.keyword == "$$chanlist":
            eff_chs = fader.setdefault("effect_channels", [])
            for arg in self.args:
                try:
                    ch = int(arg)
                except ValueError:
                    continue
                if 1 <= ch <= MAX_CHANNELS and ch not in eff_chs:
                    eff_chs.append(ch)
        elif self.keyword == "$$effectmode" and self.args:
            mode = self.args[0].strip().lower()
            if mode in ("size", "rate", "both"):
                fader["control_mode"] = mode
        elif self.keyword == "$$exclude" and "9" in self.args:
            fader["exempt_grand_master"] = True
        elif self.keyword == "$$intensitymaster":
            fader["intensity_master"] = True
        elif self.keyword == "$$fixed":
            fader["fixed"] = True

    def _get_level(self, level: str) -> float:
        if level.startswith("h"):
            hex_part = level[1:]
            denom = 65535.0 if len(hex_part) > 2 else 255.0
            return int(hex_part, 16) / denom
        return float(level) / 100.0

    def _new_personality(self) -> None:
        pers_id = int(self.args[0])
        self.personalities[pers_id] = {
            "manufacturer": "",
            "model": f"Personality {pers_id}",
            "dcid": "",
            "footprint": 1,
            "virtual_int": False,
            "notes": "",
            "channels": [],
        }
        self.current["personality"] = pers_id
        self.state = State.IN_PERSONALITY

    def _do_personality(self) -> None:
        pers = self.personalities.get(self.current["personality"])
        if pers is None:
            return
        if self.keyword == "$$manuf" and self.args:
            pers["manufacturer"] = self.args[0].strip()
        elif self.keyword == "$$model" and self.args:
            pers["model"] = self.args[0].strip()
        elif self.keyword == "$$dcid" and self.args:
            pers["dcid"] = self.args[0].strip()
        elif self.keyword == "$$footprint" and self.args:
            pers["footprint"] = int(self.args[0])
        elif self.keyword == "$$virtualint":
            pers["virtual_int"] = True
        elif self.keyword == "$$notes" and self.args:
            pers["notes"] = f"{pers.get('notes', '')}{html.unescape(self.args[0])}"
        elif self.keyword == "$$perschan" and len(self.args) >= 5:
            pers["channels"].append(
                {
                    "param_id": int(self.args[0]),
                    "bytes": int(self.args[1]),
                    "offset_coarse": int(self.args[2]),
                    "offset_fine": int(self.args[3]),
                    "default": int(self.args[4]),
                    "snap": len(self.args) > 5 and self.args[5] == "s",
                    "phys_min": 0.0,
                    "phys_max": 1.0,
                    "slots": 0,
                    "slot_list": [],
                }
            )
        elif self.keyword == "$$persslot" and self.args and pers["channels"]:
            ch_def = pers["channels"][-1]
            if match := _PERSSLOT_RE.match(self.args[0].strip()):
                d_min = int(match.group(1))
                d_max = int(match.group(2))
                d_snap = int(match.group(3))
                p_min = float(match.group(4))
                p_max = float(match.group(5))
                label = html.unescape((match.group(6) or "").strip())
                ch_def["slot_list"].append(
                    {
                        "dmx_min": d_min,
                        "dmx_max": d_max,
                        "dmx_snap": d_snap,
                        "phys_min": p_min,
                        "phys_max": p_max,
                        "label": label,
                    }
                )
                if ch_def["slots"] == 0:
                    ch_def["phys_min"] = p_min
                    ch_def["phys_max"] = p_max
                else:
                    ch_def["phys_min"] = min(ch_def["phys_min"], p_min)
                    ch_def["phys_max"] = max(ch_def["phys_max"], p_max)
                ch_def["slots"] += 1
        elif (
            self.keyword == "$$perssltext"
            and self.args
            and pers["channels"]
            and pers["channels"][-1]["slot_list"]
        ):
            pers["channels"][-1]["slot_list"][-1]["label"] = html.unescape(
                self.args[0].strip()
            )

    def _register_personality_definition(
        self, pers_id: int
    ) -> tuple[dict[str, typing.Any], str] | None:
        """Build and register a FixtureDefinition dict for non-dimmer *pers_id*."""
        if pers_id in self._pers_fdef_info:
            return self._pers_fdef_info[pers_id]
        pers = self.personalities.get(pers_id)
        if pers is None or is_dimmer_personality(pers, self.param_types):
            return None

        fdef_dict = build_fixture_definition(pers_id, pers, self.param_types)
        if fdef_dict is None:
            return None

        key = (fdef_dict["manufacturer"].lower(), fdef_dict["model"].lower())
        if key not in self._registered_fdefs:
            self._registered_fdefs[key] = fdef_dict
            self.data.setdefault("fixture_definitions", []).append(fdef_dict)
            result = (fdef_dict, str(fdef_dict["dmx_modes"][0]["name"]))
        else:
            existing = self._registered_fdefs[key]
            new_mode = fdef_dict["dmx_modes"][0]
            existing_names = {m["name"] for m in existing["dmx_modes"]}
            if new_mode["name"] in existing_names:
                new_mode["name"] = f"{new_mode['name']} ({pers_id})"
            existing["dmx_modes"].append(new_mode)
            if "color_profile" not in existing and "color_profile" in fdef_dict:
                existing["color_profile"] = fdef_dict["color_profile"]
            result = (existing, str(new_mode["name"]))

        self._pers_fdef_info[pers_id] = result
        return result

    def _finalize_personalities(self) -> None:
        """Register all non-dimmer $Personality definitions, even unpatched."""
        for pers_id in self.personalities:
            self._register_personality_definition(pers_id)

    def _new_patch(self) -> None:
        if len(self.args) < 3:
            self.state = State.NO_PRIMARY
            return
        channel = int(self.args[0])
        pers_id = int(self.args[1])
        dmx_addr = int(self.args[2])
        # args[3] in Eos $Patch is address_mode (1=port/offset, 0=edmx), not curve_id.
        curve_id = 0

        if channel > MAX_CHANNELS or dmx_addr < 1:
            self.state = State.NO_PRIMARY
            return

        self.channel_personality[channel] = pers_id
        self.current["patch_channel"] = channel
        self.current["patch_output"] = None
        self.current["utext_active"] = False
        pers = self.personalities.get(pers_id)

        if pers is None or is_dimmer_personality(pers, self.param_types):
            univ_index = (dmx_addr - 1) // 512
            if univ_index < NB_UNIVERSES:
                univ = UNIVERSES[univ_index]
                address = dmx_addr - (512 * univ_index)
                existing = self.data["patch"].get(channel, [])
                if not any(
                    out["output"] == address and out["universe"] == univ
                    for out in existing
                ):
                    self._add_patch(channel, dmx_addr, 1.0)
                self.current["patch_output"] = (address, univ)
        else:
            registered = self._register_personality_definition(pers_id)
            if registered is not None:
                fdef_dict, mode_name = registered
                device_dict = build_device_from_definition(
                    channel, dmx_addr, curve_id, fdef_dict, mode_name=mode_name
                )
                if device_dict is not None:
                    self.data.setdefault("devices", {})[channel] = device_dict

        self.state = State.IN_PATCH

    def _do_patch_device(self) -> None:
        ch = self.current.get("patch_channel", 0)
        dev = self.data.get("devices", {}).get(ch)
        if dev is not None and self.keyword == "$$pers" and self.args:
            pers_id = self.channel_personality.get(ch)
            if pers_id is None or pers_id not in self.personalities:
                model = self.args[0].strip()
                dev["model"] = model
                dev["label"] = f"{model} {ch}"
        elif self.keyword == "$$curve" and self.args:
            try:
                curve_num = int(float(self.args[0]))
                param_num = int(float(self.args[1])) if len(self.args) >= 2 else 1
            except ValueError:
                return
            if param_num != 1:
                return
            if dev is not None:
                dev["curve_id"] = curve_num
            elif ch in self.data["patch"]:
                target_out = self.current.get("patch_output")
                for out in reversed(self.data["patch"][ch]):
                    if (
                        target_out is None
                        or (out["output"], out["universe"]) == target_out
                    ):
                        out["curve"] = curve_num
                        break
        elif self.keyword in ("text", "$$text", "$$utext"):
            if dev is not None:
                self._apply_label(dev, key="label")
            elif ch in self.data["patch"]:
                target_out = self.current.get("patch_output")
                for out in reversed(self.data["patch"][ch]):
                    if (
                        target_out is None
                        or (out["output"], out["universe"]) == target_out
                    ):
                        self._apply_label(out, key="label")
                        break
        elif self.keyword == "$$options" and dev is not None and self.args:
            self._apply_patch_options(dev, "".join(self.args).lower())

    @staticmethod
    def _apply_patch_options(dev: dict[str, typing.Any], flags: str) -> None:
        """Apply Eos $$Options flags (P=flip pan, T=flip tilt, S=swap pan/tilt)."""
        channels = dev.get("channels", [])
        if "p" in flags:
            for ch_dict in channels:
                if ch_dict.get("channel_type") == "pan":
                    ch_dict["physical_min"], ch_dict["physical_max"] = (
                        ch_dict["physical_max"],
                        ch_dict["physical_min"],
                    )
        if "t" in flags:
            for ch_dict in channels:
                if ch_dict.get("channel_type") == "tilt":
                    ch_dict["physical_min"], ch_dict["physical_max"] = (
                        ch_dict["physical_max"],
                        ch_dict["physical_min"],
                    )
        if "s" in flags:
            pan_chs = {
                (bool(c.get("fine")), bool(c.get("ultra_fine"))): c
                for c in channels
                if c.get("channel_type") == "pan"
            }
            tilt_chs = {
                (bool(c.get("fine")), bool(c.get("ultra_fine"))): c
                for c in channels
                if c.get("channel_type") == "tilt"
            }
            for res_key, p_ch in pan_chs.items():
                if (t_ch := tilt_chs.get(res_key)) is not None:
                    p_ch["universe"], t_ch["universe"] = (
                        t_ch["universe"],
                        p_ch["universe"],
                    )
                    p_ch["address"], t_ch["address"] = (
                        t_ch["address"],
                        p_ch["address"],
                    )

    def _new_curve(self) -> None:
        if not self.args:
            self.state = State.NO_PRIMARY
            return
        curve_id = int(self.args[0])
        self.data["curves"][curve_id] = {
            "type": "SegmentsCurve",
            "label": "",
            "points": [],
            "normalized": False,
        }
        self.current["curve"] = curve_id
        self.current["utext_active"] = False
        self.state = State.IN_CURVE

    def _do_curve(self) -> None:
        curve = self.data["curves"].get(self.current["curve"])
        if curve is None:
            return
        if self.keyword in ("text", "$$text", "$$utext"):
            self._apply_label(curve)
        elif self.keyword == "$$interpolated":
            curve["type"] = "InterpolateCurve"
        elif self.keyword == "$$stepped":
            curve["type"] = "SteppedCurve"
        elif self.keyword == "$$curvedata":
            for index in range(0, len(self.args) - 1, 2):
                x = max(0, min(255, int(self.args[index])))
                y = max(0, min(255, int(self.args[index + 1])))
                curve["points"].append([x, y])
        elif self.keyword == "$$curvepoint" and not curve["points"]:
            for index in range(0, len(self.args) - 1, 2):
                x = max(0, min(255, round(float(self.args[index]) * 2.55)))
                y = max(0, min(255, round(float(self.args[index + 1]) * 2.55)))
                curve["points"].append([x, y])

    def _new_sub(self) -> None:
        if not self.args:
            self.state = State.NO_PRIMARY
            return
        sub_id = int(self.args[0])
        self.subs[sub_id] = {
            "label": "",
            "channels": {},
            "exempt_gm": False,
            "intensity_master": False,
        }
        self._sub_raw_params[sub_id] = {}
        self._sub_raw_refs[sub_id] = {}
        self.current["sub"] = sub_id
        self.current["utext_active"] = False
        self.state = State.IN_SUB

    def _do_sub(self) -> None:
        sub_id = int(self.current["sub"])
        sub = self.subs.get(sub_id)
        if sub is None:
            return
        if self.keyword in ("text", "$$text", "$$utext"):
            self._apply_label(sub)
        elif self.keyword == "$$exclude" and self.args:
            try:
                if int(self.args[0]) & 8:
                    sub["exempt_gm"] = True
            except ValueError:
                pass
        elif self.keyword == "$$intensitymaster" or (
            self.keyword == "$$master" and self.args and self.args[0] == "8"
        ):
            sub["intensity_master"] = True
        elif self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                if channel <= MAX_CHANNELS:
                    sub["channels"][channel] = self._get_level(self.args[index + 1])
        elif self.keyword in ("$$effectchan", "$$effectdata"):
            self._record_effect_call(
                self._sub_effects.setdefault(sub_id, self._new_effect_store())
            )
        elif self.keyword == "$$param" and len(self.args) >= 3:
            self._record_param_line(
                self._sub_raw_params.setdefault(sub_id, {}),
                self._sub_raw_refs.setdefault(sub_id, {}),
            )
            channel = int(self.args[0])
            if channel <= MAX_CHANNELS and channel not in sub["channels"]:
                for index in range(1, len(self.args) - 1, 2):
                    try:
                        p_id = int(self.args[index])
                    except ValueError:
                        continue
                    raw_val, _ref = parse_eos_param_token(self.args[index + 1])
                    if p_id == 1 and raw_val is not None:
                        max_raw = 65535.0 if raw_val > 255.0 else 255.0
                        sub["channels"][channel] = max(0.0, min(1.0, raw_val / max_raw))

    def _new_effect(self) -> None:
        if not self.args:
            self.state = State.NO_PRIMARY
            return
        try:
            number = float(self.args[0])
        except ValueError:
            self.state = State.NO_PRIMARY
            return
        self._raw_effects[number] = new_eos_effect(number)
        self.current["effect"] = number
        self.current["utext_active"] = False
        self.state = State.IN_EFFECT

    def _do_effect(self) -> None:
        raw = self._raw_effects.get(self.current.get("effect", -1.0))
        if raw is None:
            return
        if self.keyword in ("text", "$$text", "$$utext"):
            self._apply_label(raw)
        else:
            record_eos_effect_line(raw, self.keyword, self.args)

    def _finalize_effects(self) -> None:
        """Convert accumulated Eos $Effect blocks into OLC effect dictionaries."""
        if not self._raw_effects:
            return
        effects = self.data.setdefault("effects", [])
        for number in sorted(self._raw_effects):
            effects.append(
                convert_eos_effect(self._raw_effects[number], self.param_types)
            )

    def _finalize_unmounted_subs(self) -> None:
        """Promote non-empty unmounted Eos Subs into Presets (Option A)."""
        presets: dict[float, typing.Any] | None = None
        for sub_id in sorted(self.subs):
            if sub_id in self._sub_preset_numbers:
                continue
            sub_fx = self._sub_effects.get(sub_id)
            has_fx = bool(
                sub_fx
                and any(e > 0.0 and c for e, c in sub_fx.get("chans", {}).items())
            )
            sub = self.subs[sub_id]
            has_static = bool(
                sub["channels"]
                or self._sub_raw_params.get(sub_id)
                or self._sub_raw_refs.get(sub_id)
            )
            if has_fx or not has_static:
                continue
            if presets is None:
                presets = self.data.setdefault("palettes", {}).setdefault(
                    PaletteCategory.PRESET.value, {}
                )
            preset_num = float(sub_id)
            while preset_num in presets:
                preset_num += 1.0
            self._sub_preset_numbers[sub_id] = preset_num
            presets[preset_num] = {
                "category": PaletteCategory.PRESET.value,
                "number": preset_num,
                "label": sub["label"] or f"Sub {sub_id}",
                "channels": dict(sub["channels"]),
            }

    @staticmethod
    def _new_effect_store() -> dict[str, typing.Any]:
        return {"chans": {}, "data": {}}

    def _record_effect_call(self, store: dict[str, typing.Any]) -> None:
        """Record one $$EffectChan / $$EffectData line into *store*."""
        try:
            if self.keyword == "$$effectchan" and len(self.args) >= 2:
                eff = round(float(self.args[0]), 3)
                channel = int(self.args[1])
                store["chans"].setdefault(eff, [])
                if channel not in store["chans"][eff]:
                    store["chans"][eff].append(channel)
            elif self.keyword == "$$effectdata" and len(self.args) >= 3:
                eff = round(float(self.args[0]), 3)
                parsed = parse_effect_data_value(self.args[1], self.args[2])
                if parsed is not None:
                    store["data"].setdefault(eff, {})[parsed[0]] = parsed[1]
        except ValueError:
            return

    @staticmethod
    def _build_effect_refs(
        store: dict[str, typing.Any],
        running: dict[float, list[int]],
    ) -> dict[int, dict[str, typing.Any]]:
        """Build Cue.effect_refs-style mapping from a recorded effect store."""
        refs: dict[int, dict[str, typing.Any]] = {}
        data = store["data"]
        for eff, chans in store["chans"].items():
            if eff == 0.0:
                for ch in chans:
                    refs[ch] = {"stop": True}
                    for run_chs in running.values():
                        if ch in run_chs:
                            run_chs.remove(ch)
                continue
            overrides = data.get(eff, {})
            for idx, ch in enumerate(chans):
                refs[ch] = {
                    "effect": eff,
                    "order_index": idx,
                    "channels": list(chans),
                    "rate_scale": float(overrides.get("rate_scale", 1.0)),
                    "size_scale": float(overrides.get("size_scale", 1.0)),
                }
            running[eff] = list(chans)
        # Data-only updates on an already running (tracked) effect
        for eff, overrides in data.items():
            if eff in store["chans"] or eff == 0.0:
                continue
            chans = running.get(eff)
            if not chans:
                continue
            for idx, ch in enumerate(chans):
                refs[ch] = {
                    "effect": eff,
                    "order_index": idx,
                    "channels": list(chans),
                    "rate_scale": float(overrides.get("rate_scale", 1.0)),
                    "size_scale": float(overrides.get("size_scale", 1.0)),
                }
        return refs

    def _resolve_effect_refs(self) -> None:
        """Attach recorded effect calls to each Cue of each sequence, in step order."""
        for seq_num, seq in self.data.get("sequences", {}).items():
            running: dict[float, list[int]] = {}
            steps = seq.get("steps", {})
            for step_nb in sorted(steps):
                cue_num = steps[step_nb].get("cue")
                store = self._cue_effects.get((int(seq_num), float(cue_num)))
                if store is None:
                    continue
                refs = self._build_effect_refs(store, running)
                if refs:
                    seq["cues"][cue_num]["effect_refs"] = refs

    def _finalize_eos_tracking(self) -> None:
        """Apply Eos $$ChanMove transitions and enable tracking on Eos CueLists."""
        if self._eos_automark is not None:
            for seq in self.data.get("sequences", {}).values():
                seq["mib_enabled"] = self._eos_automark
        if not self._is_console("etc", "eos"):
            return
        devices = self.data.get("devices", {})
        for seq_num, seq in self.data.get("sequences", {}).items():
            steps = seq.get("steps", {})
            cues = seq.get("cues", {})
            seq_int = int(seq_num)
            seq_has_moves = any(
                bool(
                    self._cue_chan_moves.get(
                        (seq_int, float(step_data.get("cue", 0.0)))
                    )
                )
                for step_data in steps.values()
            )
            seq_has_effects = any(
                bool(cues.get(step_data.get("cue"), {}).get("effect_refs"))
                for step_data in steps.values()
            )
            if seq_has_moves or seq_has_effects:
                seq["tracking_mode"] = True
            seq["mib_enabled"] = bool(self._eos_automark)
            if not seq_has_moves:
                continue

            tracked_dev_chans: set[int] = set(devices.keys())
            for step_nb in sorted(steps):
                cue_num = steps[step_nb].get("cue")
                cue = cues.get(cue_num)
                if not isinstance(cue, dict):
                    continue
                for ch, dvals in cue.get("device_values", {}).items():
                    if isinstance(dvals, dict) and "intensity" in dvals:
                        tracked_dev_chans.add(int(ch))
                moves = self._cue_chan_moves.get((seq_int, float(cue_num)), {})
                if cue.get("is_block") or cue.get("is_int_block"):
                    channels = cue.setdefault("channels", {})
                    channels.update(moves)
                else:
                    new_channels = dict(moves)
                    for ch, dvals in cue.get("device_values", {}).items():
                        if (
                            isinstance(dvals, dict)
                            and "intensity" in dvals
                            and ch not in new_channels
                        ):
                            new_channels[ch] = float(dvals["intensity"])
                    cue["channels"] = new_channels

                for ch, lvl in cue["channels"].items():
                    if ch in tracked_dev_chans:
                        cue.setdefault("device_values", {}).setdefault(ch, {})[
                            "intensity"
                        ] = float(lvl)

    def _new_faderdef(self) -> None:
        if not self.args:
            self.current["faderdef"] = -1
            self.state = State.NO_PRIMARY
            return
        fader_num = int(self.args[0])
        max_faders = MAX_ALLOWED_FADER_PAGES * MAX_FADER_PER_PAGE
        if not 1 <= fader_num <= max_faders:
            LOGGER.debug(
                "Ignoring Eos $FaderDef %d outside OLC fader range 1..%d",
                fader_num,
                max_faders,
            )
            self.current["faderdef"] = -1
            self.state = State.IN_FADERDEF
            return
        page = ((fader_num - 1) // MAX_FADER_PER_PAGE) + 1
        number = ((fader_num - 1) % MAX_FADER_PER_PAGE) + 1
        index = fader_num - 1
        self.current["faderdef"] = index
        self.current["faderdef_page"] = page
        self.current["faderdef_number"] = number
        self.state = State.IN_FADERDEF

    def _do_faderdef(self) -> None:
        index = self.current.get("faderdef", -1)
        if index < 0 or self.keyword != "$$target" or not self.args:
            return
        page = int(self.current.get("faderdef_page", 1))
        number = int(self.current.get("faderdef_number", 1))
        target_type = self.args[0]
        if target_type == "s" and len(self.args) >= 2:
            sub_id = int(self.args[1])
            sub = self.subs.get(sub_id)
            sub_fx = self._sub_effects.get(sub_id)
            running_effs = (
                [(e, c) for e, c in sub_fx["chans"].items() if e > 0.0 and c]
                if sub_fx
                else []
            )
            if running_effs:
                eff_num, eff_chans = running_effs[0]
                fader_entry: dict[str, typing.Any] = {
                    "page": page,
                    "number": number,
                    "type": FaderType.EFFECT,
                    "contents": eff_num,
                    "effect_channels": list(eff_chans),
                }
                if sub is not None:
                    if sub["channels"]:
                        fader_entry["base_channels"] = dict(sub["channels"])
                    if sub["label"]:
                        fader_entry["text"] = sub["label"]
                    if sub.get("exempt_gm"):
                        fader_entry["exempt_grand_master"] = True
                self.data["faders"][index] = fader_entry
                return
            if sub and (
                sub["channels"]
                or self._sub_raw_params.get(sub_id)
                or self._sub_raw_refs.get(sub_id)
            ):
                presets = self.data.setdefault("palettes", {}).setdefault(
                    PaletteCategory.PRESET.value, {}
                )
                if sub_id in self._sub_preset_numbers:
                    preset_num = self._sub_preset_numbers[sub_id]
                else:
                    preset_num = float(sub_id)
                    while preset_num in presets:
                        preset_num += 1.0
                    self._sub_preset_numbers[sub_id] = preset_num
                    presets[preset_num] = {
                        "category": PaletteCategory.PRESET.value,
                        "number": preset_num,
                        "label": sub["label"] or f"Sub {sub_id}",
                        "channels": dict(sub["channels"]),
                    }
                preset_fader_entry: dict[str, typing.Any] = {
                    "page": page,
                    "number": number,
                    "type": FaderType.PRESET,
                    "contents": preset_num,
                }
                if sub.get("exempt_gm"):
                    preset_fader_entry["exempt_grand_master"] = True
                if sub.get("intensity_master"):
                    preset_fader_entry["intensity_master"] = True
                self.data["faders"][index] = preset_fader_entry
        elif target_type == "cl" and len(self.args) >= 2:
            seq_id = int(self.args[1])
            self.data["faders"][index] = {
                "page": page,
                "number": number,
                "type": FaderType.SEQUENCE,
                "contents": seq_id,
            }
        elif target_type == "gm":
            self.data["faders"][index] = {
                "page": page,
                "number": number,
                "type": FaderType.MAIN,
                "contents": None,
            }

    def _set_state(self) -> None:
        if self.state is State.START and self.keyword in self.tokens["basic"]:
            self.state = State.NO_PRIMARY
        elif self.keyword == "$personality":
            self.state = State.NEW_PERSONALITY
        elif self.keyword == "$patch":
            self.state = State.NEW_PATCH
        elif self.keyword == "$curve":
            self.state = State.NEW_CURVE
        elif self.keyword == "$faderdef":
            self.state = State.NEW_FADERDEF
        elif self.keyword == "$effect":
            self.state = State.NEW_EFFECT
        elif self.keyword in ("$sequence", "$cuelist", "$specialfunction"):
            self.state = State.NEW_MPRIMARY
        elif self.keyword in ("cue", "$cue"):
            self.state = State.NEW_CUE
        elif self.keyword in _EOS_PALETTE_KEYWORDS:
            self.state = State.NEW_PALETTE
        elif self.keyword == "group" and self._is_console("etc", "eos"):
            self.state = State.NEW_EOS_PRESET
        elif self.keyword == "$group" or (
            self.keyword == "group"
            and not self._is_console("avab", "congo")
            and not self._is_console("etc", "eos")
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

    def _apply_resolved_params(
        self,
        target: dict[str, typing.Any],
        raw_by_ch: dict[int, dict[int, float]],
        refs_by_ch: dict[int, dict[int, tuple[str, float]]],
        *,
        store_resolved_key: tuple[str, float] | None = None,
    ) -> None:
        """Merge raw parameters and palette references onto *target* dict."""
        palettes_data = self.data.get("palettes", {})
        for ch in sorted(set(raw_by_ch.keys()) | set(refs_by_ch.keys())):
            pers_id = self.channel_personality.get(ch)
            pers = self.personalities.get(pers_id) if pers_id is not None else None
            merged: dict[int, float] = dict(raw_by_ch.get(ch, {}))
            ref_intensity: float | None = None
            for p_id, (ref_cat, ref_num) in sorted(refs_by_ch.get(ch, {}).items()):
                src_raw = self._palette_raw_params.get((ref_cat, ref_num), {}).get(
                    ch, {}
                )
                if p_id in src_raw:
                    merged[p_id] = src_raw[p_id]
                elif p_id == 1 or self.param_types.get(p_id, "").lower() == "intens":
                    src_pal = palettes_data.get(ref_cat, {}).get(ref_num)
                    if isinstance(src_pal, dict) and ch in src_pal.get("channels", {}):
                        ref_intensity = float(src_pal["channels"][ch])
                olc_key = eos_param_id_to_olc_key(p_id, self.param_types, pers=pers)
                if olc_key is not None:
                    pal_refs_ch = target.setdefault("palette_refs", {}).setdefault(
                        ch, {}
                    )
                    if olc_key not in pal_refs_ch:
                        pal_refs_ch[olc_key] = [ref_cat, ref_num]
            if store_resolved_key is not None and merged:
                self._palette_raw_params.setdefault(store_resolved_key, {})[ch] = merged

            dev_vals, intensity_val = decode_eos_cue_params(
                list(merged.items()), pers, self.param_types
            )
            if ref_intensity is not None and intensity_val is None:
                intensity_val = ref_intensity
                dev_vals["intensity"] = ref_intensity
            if dev_vals:
                target.setdefault("device_values", {})[ch] = dev_vals
            if intensity_val is not None and ch not in target.setdefault(
                "channels", {}
            ):
                target["channels"][ch] = intensity_val

    def _resolve_palettes_and_refs(self) -> None:
        """Pass 2: decode base palettes and resolve refs on Presets, Subs, and Cues."""
        base_cats = (
            PaletteCategory.INTENSITY.value,
            PaletteCategory.FOCUS.value,
            PaletteCategory.COLOR.value,
            PaletteCategory.BEAM.value,
        )
        all_pal_keys = list(
            set(self._palette_raw_params.keys()) | set(self._palette_raw_refs.keys())
        )
        palettes_data = self.data.get("palettes", {})

        # 1. Decode base IFCB palettes first
        for key in all_pal_keys:
            cat_val, num = key
            if cat_val not in base_cats:
                continue
            target = palettes_data.get(cat_val, {}).get(num)
            if target is not None:
                self._apply_resolved_params(
                    target,
                    self._palette_raw_params.get(key, {}),
                    self._palette_raw_refs.get(key, {}),
                    store_resolved_key=key,
                )

        # 2. Resolve Eos Presets (may reference base palettes, e.g. PR110 -> BP2)
        preset_cat = PaletteCategory.PRESET.value
        for key in all_pal_keys:
            cat_val, num = key
            if cat_val != preset_cat:
                continue
            target = palettes_data.get(preset_cat, {}).get(num)
            if target is not None:
                self._apply_resolved_params(
                    target,
                    self._palette_raw_params.get(key, {}),
                    self._palette_raw_refs.get(key, {}),
                    store_resolved_key=key,
                )

        # 3. Resolve mounted Subs backed by $$Param lines
        for sub_id, preset_num in self._sub_preset_numbers.items():
            raw_by_ch = self._sub_raw_params.get(sub_id, {})
            refs_by_ch = self._sub_raw_refs.get(sub_id, {})
            if not raw_by_ch and not refs_by_ch:
                continue
            target = palettes_data.get(preset_cat, {}).get(preset_num)
            if target is not None:
                self._apply_resolved_params(target, raw_by_ch, refs_by_ch)

        # 4. Resolve Cue parameters and palette/preset references
        all_cue_keys = list(
            set(self._cue_raw_params.keys()) | set(self._cue_raw_refs.keys())
        )
        sequences_data = self.data.get("sequences", {})
        for seq_num, cue_num in all_cue_keys:
            cue = sequences_data.get(seq_num, {}).get("cues", {}).get(cue_num)
            if cue is not None:
                self._apply_resolved_params(
                    cue,
                    self._cue_raw_params.get((seq_num, cue_num), {}),
                    self._cue_raw_refs.get((seq_num, cue_num), {}),
                )

        # 5. Resolve Cue $$Action Execute S <sub_id> -> Preset number
        for (seq_num, cue_num), sub_ref in self._cue_execute_subs.items():
            preset_num = (
                self._sub_preset_numbers.get(int(sub_ref))
                if float(sub_ref).is_integer()
                else None
            )
            if preset_num is None and not self._is_console("etc", "eos"):
                preset_num = float(sub_ref)
            cue = sequences_data.get(seq_num, {}).get("cues", {}).get(cue_num)
            if preset_num is not None and cue is not None:
                cue["execute_preset"] = preset_num
