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

from olc.define import is_float, is_int
from olc.files.read import ReadFile

if typing.TYPE_CHECKING:
    from olc.files.import_file import ImportFile
    from olc.files.parsed_data import ParsedData


class OlcParser(ReadFile):
    """Parse olc files"""

    data: ParsedData

    def __init__(self, imported: ImportFile):
        super().__init__(imported, compressed=True)
        self.data = imported.data.data

    def parse(self) -> None:
        """Parse file"""
        contents = json.loads(self.contents, object_hook=self._key_to_number)
        self.data["curves"] = contents.get("curves")
        self.data["patch"] = contents.get("patch")
        self.data["sequences"] = contents.get("sequences")
        self.data["presets"] = contents.get("cues")
        self.data["groups"] = contents.get("groups")
        self.data["faders"] = contents.get("faders")
        self.data["independents"] = contents.get("independents")
        self.data["midi"] = contents.get("midi_mapping")

    def _int_float_str(self, key):
        if is_int(key):
            return int(key)
        if is_float(key):
            return float(key)
        return key

    def _key_to_number(self, obj):
        return {self._int_float_str(k): v for k, v in obj.items()}
