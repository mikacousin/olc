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
"""Token definitions for the industry-standard lighting command line parser."""

from __future__ import annotations

import dataclasses
import typing
from enum import Enum, auto


class TokenType(Enum):
    """Enumeration of all supported lexical token types."""

    # Literals
    NUMBER = auto()
    HEX_COLOR = auto()
    STRING = auto()

    # Operators and punctuation
    PLUS = auto()
    MINUS = auto()
    SLASH = auto()
    AT = auto()

    # Selection keywords
    THRU = auto()
    GROUP = auto()
    ALL = auto()
    ODD = auto()
    EVEN = auto()

    # Intensity keywords
    FULL = auto()
    OUT = auto()

    # Moving lights & Attribute keywords
    PAN = auto()
    TILT = auto()
    COLOR = auto()
    ZOOM = auto()
    FOCUS = auto()
    IRIS = auto()
    STROBE = auto()
    CCT = auto()
    GOBO = auto()
    PRISM = auto()
    COLOR_WHEEL = auto()
    GOBO_WHEEL = auto()

    # Playback & Cue keywords
    RECORD = auto()
    UPDATE = auto()
    CUE = auto()
    SEQUENCE = auto()
    TIME = auto()
    DELAY = auto()
    GOTO = auto()
    BLOCK = auto()
    UNBLOCK = auto()
    DELETE = auto()

    # Identifiers (unrecognized words / custom labels)
    IDENT = auto()

    # Special
    EOF = auto()


@dataclasses.dataclass(frozen=True)
class Token:
    """Represents a scanned lexical token with position and text payload."""

    type: TokenType
    value: typing.Any
    raw_text: str
    position: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, pos={self.position})"
