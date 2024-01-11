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
import re
from enum import Enum, auto

from olc.define import MAX_CHANNELS, NB_UNIVERSES, UNIVERSES, string_to_time
from olc.files.read import ReadFile


class State(Enum):
    """States for AsciiParser"""

    START = auto()
    NO_PRIMARY = auto()
    NEW_CUE = auto()
    NEW_GROUP = auto()
    NEW_SUB = auto()
    NEW_MPRIMARY = auto()
    IN_CUE = auto()
    IN_GROUP = auto()
    IN_SUB = auto()
    IN_MPRIMARY = auto()


class AsciiParser(ReadFile):
    """To Parse ASCII Light Cue files"""

    tokens: dict[str, set[str]]
    state: State
    keyword: str
    args: list[str]
    console: dict[str, str]
    current: dict

    def __init__(self, file, data):
        super().__init__(file)
        self.data = data
        self.tokens = {
            "basic": (
                "clear",
                "console",
                "ident",
                "manufacturer",
                "patch",
                "set",
            ),
            "cue": (
                "chan",
                "down",
                "followon",
                "link",
                "part",
                "text",
                "up",
                "$$wait",
                "$$parttime",
                "$$parttimechan",
            ),
        }
        self.state = State.START
        self.keyword = ""
        self.args = []
        self.console = {"console": "", "manufacturer": ""}
        self.current = {
            "cue": 0,
            "channel_time": (0, 0),
            "sequence": 1,
        }

    def do_parse(self, line: str) -> bool:
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
        self.args = tokens[1:]
        # Remove comments at end of line but allow "!" in text
        if self.keyword not in ("text", "$$text", "$$presettext"):
            for num, arg in enumerate(self.args):
                idx = arg.rfind("!")
                if idx >= 0:
                    self.args[num] = self.args[num][:idx]
                    self.args = self.args[:num + 1]
            self.args = [arg.lower() for arg in self.args if arg != ""]
        else:
            # Remove empty args
            self.args = [arg for arg in self.args if arg != ""]

        self._set_state()
        self._do_action()

        return True

    def _do_action(self) -> None:
        if self.keyword in self.tokens["basic"]:
            self._do_basic()
        elif self.state is State.NEW_MPRIMARY:
            self._new_mprimary()
        elif self.state is State.IN_MPRIMARY:
            self._do_mprimary()
        elif self.state is State.NEW_CUE:
            self._new_cue()
        elif self.state is State.IN_CUE:
            self._do_cue()

    def _do_basic(self) -> None:
        if self.keyword == "ident":
            if self.args[0] != "3:0":
                print("Unexpected protocol version")
        elif self.keyword == "manufacturer":
            self.console["manufacturer"] = self.args[0]
        elif self.keyword == "console":
            self.console["console"] = self.args[0]
        if self.keyword == "clear":
            arg = self.args[0]
            print(f"TODO: Clear {arg}")
        elif self.keyword == "patch":
            self._do_patch()
        elif self.keyword == "set":
            print(f"TODO: Set {self.args}")

    def _do_patch(self) -> None:
        # self.args[0] is Page Patch, not used
        for index in range(1, len(self.args), 3):
            channel, dimmer, lvl = self.args[index:index + 3]
            level = self._get_level(lvl)
            self._add_patch(int(channel), int(dimmer), level)

    def _add_patch(self, channel: int, dimmer: int, level: int) -> None:
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
            if channel not in self.data.patch:
                self.data.patch[channel] = [(address, univ, level)]
            else:
                self.data.patch[channel].append((address, univ, level))

    def _new_mprimary(self) -> None:
        if self.keyword == "$sequence":
            mode = "normal"
            seq_number = int(self.args[0])
            self.data.sequences[seq_number] = {}
            if self._is_console("avab", "congo"):
                if int(self.args[1]) == 1:
                    mode = "chaser"
            elif seq_number > 1:
                mode = "chaser"
            self.data.sequences[seq_number]["mode"] = mode
            self.data.sequences[seq_number]["steps"] = []
            self.data.sequences[seq_number]["cues"] = {}
            self.current["sequence"] = seq_number
            self.state = State.IN_MPRIMARY

    def _do_mprimary(self) -> None:
        if self.keyword in ("text", "$$text"):
            text = " ".join(self.args)
            self.data.sequences[self.current["sequence"]]["text"] = text

    def _new_cue(self) -> None:
        if self.keyword == "cue":
            # CUE cue_number
            cue_number = float(self.args[0])
        else:
            # $CUE sequence_number cue_number
            cue_number = float(self.args[1])
        self.data.sequences[self.current["sequence"]]["steps"].append(cue_number)
        self.data.sequences[self.current["sequence"]]["cues"][cue_number] = {
            "out_time": 0.0,
            "out_delay": 0.0,
            "up_time": 0.0,
            "up_delay": 0.0,
            "wait": 0.0,
            "channels": {},
            "text": "",
            "channel_time": {},
        }
        self.current["cue"] = cue_number
        self.state = State.IN_CUE

    def _do_cue(self) -> None:
        # Missed keywords: followon, link, part
        cues = self.data.sequences[self.current["sequence"]]["cues"]
        if self.keyword == "chan":
            for index in range(0, len(self.args), 2):
                channel = int(self.args[index])
                level = self._get_level(self.args[index + 1])
                cues[self.current["cue"]]["channels"][channel] = level
        elif self.keyword == "down":
            time = string_to_time(self.args[0])
            delay = string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            cues[self.current["cue"]]["out_time"] = time
            cues[self.current["cue"]]["out_delay"] = delay
        elif self.keyword == "up":
            time = string_to_time(self.args[0])
            delay = string_to_time(self.args[1]) if len(self.args) > 1 else 0.0
            cues[self.current["cue"]]["up_time"] = time
            cues[self.current["cue"]]["up_delay"] = delay
        elif self.keyword in ("text", "$$text", "$$presettext"):
            text = " ".join(self.args)
            cues[self.current["cue"]]["text"] = text
        elif self.keyword == "$$wait":
            time = string_to_time(self.args[0])
            cues[self.current["cue"]]["wait"] = time
        elif self.keyword == "$$parttime":
            delay = string_to_time(self.args[0])
            time = string_to_time(self.args[1])
            self.current["channel_time"] = (delay, time)
            cues[self.current["cue"]]["channel_time"][(delay, time)] = set()
        elif self.keyword == "$$parttimechan":
            for arg in self.args:
                cues[self.current["cue"]]["channel_time"][
                    self.current["channel_time"]].add(arg)

    def _get_level(self, level: str) -> int:
        if level[0] == "h":
            return int(level[1:], 16)
        return round((int(level) / 100) * 255)

    def _set_state(self) -> None:
        if self.state is State.START and self.keyword in self.tokens["basic"]:
            self.state = State.NO_PRIMARY
        elif (self.state
              in (State.START, State.NO_PRIMARY, State.IN_CUE, State.IN_MPRIMARY)
              and self.keyword == "$sequence"):
            self.state = State.NEW_MPRIMARY
        elif self.state in (
                State.START,
                State.NO_PRIMARY,
                State.IN_CUE,
                State.IN_MPRIMARY,
        ) and self.keyword in ("cue", "$cue"):
            self.state = State.NEW_CUE
        elif self.state in (
                State.START,
                State.NO_PRIMARY,
                State.IN_CUE,
                State.IN_MPRIMARY,
        ) and self.keyword in ("group", "$group"):
            self.state = State.NEW_GROUP
        elif (self.state
              in (State.START, State.NO_PRIMARY, State.IN_CUE, State.IN_MPRIMARY)
              and self.keyword == "sub"):
            self.state = State.NEW_SUB
        elif (self.state in (State.START, State.NO_PRIMARY)
              and self.keyword in self.tokens["cue"]):
            print(f"{self.keyword} before a primary keyword, skipping")
            self.state = State.NO_PRIMARY

    def _is_console(self, manufacturer: str, console: str) -> bool:
        if (manufacturer == self.console["manufacturer"]
                and console == self.console["console"]):
            return True
        return False
