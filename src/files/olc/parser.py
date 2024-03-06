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
    json: dict

    def __init__(self, imported: ImportFile):
        super().__init__(imported, compressed=True)
        self.data = imported.data.data
        self.json = {}

    def parse(self) -> None:
        """Parse file"""
        self.json = json.loads(self.contents, object_hook=self._key_to_number)
        self.data["curves"] = self.json.get("curves")
        self.data["patch"] = self.json["patch"]
        self.data["sequences"] = self.json["sequences"]
        self.data["presets"] = self.json["cues"]
        self.data["groups"] = self.json["groups"]
        self.data["faders"] = self.json["faders"]
        self.data["independents"] = self.json["independents"]
        self.data["midi"] = self.json["midi_mapping"]

    def _int_float_str(self, key):
        if is_int(key):
            return int(key)
        if is_float(key):
            return float(key)
        return key

    def _key_to_number(self, obj):
        return {self._int_float_str(k): v for k, v in obj.items()}
