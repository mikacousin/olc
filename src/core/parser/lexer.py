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
"""Fast pure-Python lexical scanner for lighting console commands."""

from __future__ import annotations

import re

from olc.core.parser.tokens import Token, TokenType


class LexerError(Exception):
    """Raised when an unrecognized character or token is encountered."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} at position {position}")
        self.position = position


KEYWORDS: dict[str, TokenType] = {
    "THRU": TokenType.THRU,
    "AT": TokenType.AT,
    "FULL": TokenType.FULL,
    "OUT": TokenType.OUT,
    "RECORD": TokenType.RECORD,
    "REC": TokenType.RECORD,
    "UPDATE": TokenType.UPDATE,
    "CUE": TokenType.CUE,
    "SEQUENCE": TokenType.SEQUENCE,
    "SEQ": TokenType.SEQUENCE,
    "GROUP": TokenType.GROUP,
    "ALL": TokenType.ALL,
    "ODD": TokenType.ODD,
    "EVEN": TokenType.EVEN,
    "TIME": TokenType.TIME,
    "DELAY": TokenType.DELAY,
    "GOTO": TokenType.GOTO,
    "BLOCK": TokenType.BLOCK,
    "UNBLOCK": TokenType.UNBLOCK,
    "DELETE": TokenType.DELETE,
    # ML Attributes
    "PAN": TokenType.PAN,
    "TILT": TokenType.TILT,
    "COLOR": TokenType.COLOR,
    "COLOUR": TokenType.COLOR,
    "ZOOM": TokenType.ZOOM,
    "FOCUS": TokenType.FOCUS,
    "IRIS": TokenType.IRIS,
    "STROBE": TokenType.STROBE,
    "CCT": TokenType.CCT,
    "GOBO": TokenType.GOBO,
    "PRISM": TokenType.PRISM,
    "COLOR_WHEEL": TokenType.COLOR_WHEEL,
    "COLORWHEEL": TokenType.COLOR_WHEEL,
    "GOBO_WHEEL": TokenType.GOBO_WHEEL,
    "GOBOWHEEL": TokenType.GOBO_WHEEL,
}


# pylint: disable=too-few-public-methods
class CommandLexer:
    """Regex-based lexical scanner transforming text into a sequence of Tokens."""

    # Combined master regex pattern
    _TOKEN_RE = re.compile(
        r"""
        (?P<WHITESPACE>\s+)
        |(?P<HEX_COLOR>\#[0-9a-fA-F]{3,8})
        |(?P<STRING>"[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')
        |(?P<NUMBER>\d+(?:\.\d+)?|\.\d+)
        |(?P<AT>@)
        |(?P<PLUS>\+)
        |(?P<MINUS>-)
        |(?P<SLASH>/)
        |(?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*)
        |(?P<MISMATCH>.)
        """,
        re.VERBOSE,
    )

    def tokenize(self, text: str) -> list[Token]:  # pylint: disable=too-many-branches
        """Scans the entire input string and returns a list of Tokens ending with EOF.

        Args:
            text: Command string to tokenize.

        Returns:
            List of scanned Token objects.

        Raises:
            LexerError: If an invalid character is encountered.
        """
        tokens: list[Token] = []

        for match in self._TOKEN_RE.finditer(text):
            kind = match.lastgroup
            val = match.group()
            pos = match.start()

            if kind == "WHITESPACE":
                continue

            if kind == "NUMBER":
                num_val = float(val) if "." in val else int(val)
                tokens.append(Token(TokenType.NUMBER, num_val, val, pos))

            elif kind == "HEX_COLOR":
                tokens.append(Token(TokenType.HEX_COLOR, val.upper(), val, pos))

            elif kind == "STRING":
                # Strip quotes and handle simple unescaping
                unquoted = val[1:-1].replace(r"\"", '"').replace(r"\'", "'")
                tokens.append(Token(TokenType.STRING, unquoted, val, pos))

            elif kind == "AT":
                tokens.append(Token(TokenType.AT, "@", val, pos))

            elif kind == "PLUS":
                tokens.append(Token(TokenType.PLUS, "+", val, pos))

            elif kind == "MINUS":
                tokens.append(Token(TokenType.MINUS, "-", val, pos))

            elif kind == "SLASH":
                tokens.append(Token(TokenType.SLASH, "/", val, pos))

            elif kind == "IDENT":
                upper_val = val.upper()
                if upper_val in KEYWORDS:
                    tokens.append(Token(KEYWORDS[upper_val], upper_val, val, pos))
                else:
                    tokens.append(Token(TokenType.IDENT, val, val, pos))

            elif kind == "MISMATCH":
                raise LexerError(f"Unexpected character {val!r}", pos)

        # End Of File token
        tokens.append(Token(TokenType.EOF, None, "", len(text)))
        return tokens
