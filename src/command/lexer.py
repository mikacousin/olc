# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2024 Mika Cousin <mika.cousin@gmail.com>
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
from dataclasses import dataclass
from enum import StrEnum, auto
from string import ascii_letters, digits
from typing import Any, Generator


class TokenType(StrEnum):
    """All supported tokens"""

    INT = auto()
    SEL_CHAN = auto()
    PLUS = auto()
    MINUS = auto()
    THRU = auto()
    AT = auto()
    EOF = auto()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


CHARS_AS_TOKENS: dict[str, TokenType] = {"+": TokenType.PLUS, "-": TokenType.MINUS}

KEYWORDS_AS_TOKENS: dict[str, TokenType] = {
    "at": TokenType.AT,
    "chan": TokenType.SEL_CHAN,
    "thru": TokenType.THRU
}

LEGAL_NAME_CHARACTERS = ascii_letters
LEGAL_NAME_START_CHARACTERS = ascii_letters


@dataclass
class Token:
    """Token is defined by a type and a value"""

    type: TokenType
    value: Any = None

    def __repr__(self) -> str:
        if self.value is not None:
            return f"{self.__class__.__name__}({self.type!r}, {self.value!r})"
        return f"{self.__class__.__name__}({self.type!r})"


class Lexer:
    """Create tokens from string"""

    def __init__(self, code: str) -> None:
        self.code = code
        self.ptr: int = 0

    def consume_int(self) -> int:
        """Reads an integer.

        Returns:
            integer
        """
        start = self.ptr
        while self.ptr < len(self.code) and self.code[self.ptr] in digits:
            self.ptr += 1
        return int(self.code[start:self.ptr])

    def consume_name(self) -> str:
        """Consumes a sequence of characters.

        Returns:
            string
        """
        start = self.ptr
        self.ptr += 1
        while (self.ptr < len(self.code)
               and self.code[self.ptr] in LEGAL_NAME_CHARACTERS):
            self.ptr += 1
        return self.code[start:self.ptr]

    def next_token(self) -> Token:
        """Create next token

        Returns:
            token

        Raises:
            RuntimeError: if can't find token
        """
        while self.ptr < len(self.code) and self.code[self.ptr] == " ":
            self.ptr += 1

        if self.ptr == len(self.code):
            return Token(TokenType.EOF)

        char = self.code[self.ptr]

        if char in CHARS_AS_TOKENS:
            self.ptr += 1
            return Token(CHARS_AS_TOKENS[char])
        if char in LEGAL_NAME_START_CHARACTERS:
            name = self.consume_name()
            keyword_token_type = KEYWORDS_AS_TOKENS.get(name, None)
            if keyword_token_type:
                return Token(keyword_token_type)
        if char in digits:
            integer = self.consume_int()
            return Token(TokenType.INT, integer)
        raise RuntimeError(f"Can't tokenize {char!r}.")

    def __iter__(self) -> Generator[Token, None, None]:
        while (token := self.next_token()).type != TokenType.EOF:
            yield token
        yield token  # Yield the EOF token too.
