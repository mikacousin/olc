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
"""Unit tests for CommandLexer."""

from __future__ import annotations

import pytest

from olc.core.parser.lexer import CommandLexer, LexerError
from olc.core.parser.tokens import TokenType


def test_lexer_numbers_and_punctuation() -> None:
    lexer = CommandLexer()
    tokens = lexer.tokenize("1 25 3.5 + - / @")
    types = [t.type for t in tokens]
    assert types == [
        TokenType.NUMBER,
        TokenType.NUMBER,
        TokenType.NUMBER,
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.SLASH,
        TokenType.AT,
        TokenType.EOF,
    ]
    assert tokens[0].value == 1
    assert tokens[1].value == 25
    assert tokens[2].value == 3.5


def test_lexer_keywords_case_insensitive() -> None:
    lexer = CommandLexer()
    cmd = (
        "thru THRU At full OUT record update cue seq group all odd even "
        "time delay goto block unblock delete"
    )
    tokens = lexer.tokenize(cmd)
    types = [t.type for t in tokens]
    assert types == [
        TokenType.THRU,
        TokenType.THRU,
        TokenType.AT,
        TokenType.FULL,
        TokenType.OUT,
        TokenType.RECORD,
        TokenType.UPDATE,
        TokenType.CUE,
        TokenType.SEQUENCE,
        TokenType.GROUP,
        TokenType.ALL,
        TokenType.ODD,
        TokenType.EVEN,
        TokenType.TIME,
        TokenType.DELAY,
        TokenType.GOTO,
        TokenType.BLOCK,
        TokenType.UNBLOCK,
        TokenType.DELETE,
        TokenType.EOF,
    ]


def test_lexer_attributes_and_colors() -> None:
    lexer = CommandLexer()
    cmd = "PAN TILT COLOR #FF8800 'Dots' ZOOM FOCUS IRIS STROBE CCT GOBO PRISM"
    tokens = lexer.tokenize(cmd)
    types = [t.type for t in tokens]
    assert types == [
        TokenType.PAN,
        TokenType.TILT,
        TokenType.COLOR,
        TokenType.HEX_COLOR,
        TokenType.STRING,
        TokenType.ZOOM,
        TokenType.FOCUS,
        TokenType.IRIS,
        TokenType.STROBE,
        TokenType.CCT,
        TokenType.GOBO,
        TokenType.PRISM,
        TokenType.EOF,
    ]
    assert tokens[3].value == "#FF8800"
    assert tokens[4].value == "Dots"


def test_lexer_invalid_character_raises() -> None:
    lexer = CommandLexer()
    with pytest.raises(LexerError) as exc_info:
        lexer.tokenize("1 THRU 10 $ 5")
    assert "Unexpected character '$'" in str(exc_info.value)
