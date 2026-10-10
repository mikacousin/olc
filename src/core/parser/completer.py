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
"""Intelligent auto-completion engine for lighting console command lines."""

from __future__ import annotations

import dataclasses
import typing

from olc.core.parser.executor import COLOR_PRESETS
from olc.core.parser.lexer import CommandLexer, LexerError
from olc.core.parser.parser import CommandParser
from olc.core.parser.tokens import TokenType

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow


@dataclasses.dataclass(frozen=True)
class CompletionResult:
    """Outcome of a command line auto-completion attempt."""

    new_text: str
    candidates: list[str]
    prefix: str
    has_completed: bool


TOKEN_TO_KEYWORD: dict[TokenType, str] = {
    TokenType.THRU: "THRU",
    TokenType.AT: "AT",
    TokenType.FULL: "FULL",
    TokenType.OUT: "OUT",
    TokenType.RECORD: "RECORD",
    TokenType.UPDATE: "UPDATE",
    TokenType.CUE: "CUE",
    TokenType.SEQUENCE: "SEQUENCE",
    TokenType.GROUP: "GROUP",
    TokenType.ALL: "ALL",
    TokenType.ODD: "ODD",
    TokenType.EVEN: "EVEN",
    TokenType.TIME: "TIME",
    TokenType.DELAY: "DELAY",
    TokenType.GOTO: "GOTO",
    TokenType.BLOCK: "BLOCK",
    TokenType.UNBLOCK: "UNBLOCK",
    TokenType.DELETE: "DELETE",
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.SLASH: "/",
    TokenType.PAN: "PAN",
    TokenType.TILT: "TILT",
    TokenType.COLOR: "COLOR",
    TokenType.ZOOM: "ZOOM",
    TokenType.FOCUS: "FOCUS",
    TokenType.IRIS: "IRIS",
    TokenType.STROBE: "STROBE",
    TokenType.CCT: "CCT",
    TokenType.GOBO: "GOBO",
    TokenType.PRISM: "PRISM",
    TokenType.COLOR_WHEEL: "COLOR_WHEEL",
    TokenType.GOBO_WHEEL: "GOBO_WHEEL",
}

KEYWORD_PRIORITY: list[str] = [
    "THRU",
    "AT",
    "FULL",
    "OUT",
    "+",
    "-",
    "/",
    "CUE",
    "GROUP",
    "ALL",
    "ODD",
    "EVEN",
    "RECORD",
    "UPDATE",
    "GOTO",
    "BLOCK",
    "UNBLOCK",
    "DELETE",
    "PAN",
    "TILT",
    "COLOR",
    "ZOOM",
    "FOCUS",
    "IRIS",
    "STROBE",
    "CCT",
    "GOBO",
    "PRISM",
    "COLOR_WHEEL",
    "GOBO_WHEEL",
    "TIME",
    "DELAY",
]


# pylint: disable=too-many-instance-attributes
class CommandCompleter:
    """Calculates auto-completions based on grammar expectations and show context."""

    def __init__(
        self, parser: CommandParser, lightshow: LightShow | None = None
    ) -> None:
        """Initialize the completer.

        Args:
            parser: CommandParser instance providing get_expected_tokens().
            lightshow: Optional LightShow instance providing cues and groups.
        """
        self.parser = parser
        self.lightshow = lightshow
        self.lexer = CommandLexer()

        # Cycling state
        self._in_cycle: bool = False
        self._cycle_index: int = 0
        self._cycle_candidates: list[str] = []
        self._cycle_text_before: str = ""
        self._cycle_prefix: str = ""
        self._last_completed_text: str = ""

    def reset_cycle(self) -> None:
        """Reset consecutive Tab completion cycling state."""
        self._in_cycle = False
        self._cycle_index = 0
        self._cycle_candidates = []
        self._cycle_text_before = ""
        self._cycle_prefix = ""
        self._last_completed_text = ""

    def get_candidates(self, text: str) -> tuple[str, str, list[str]]:
        """Inspect command text and return (text_before, prefix, candidates).

        Args:
            text: Current raw command line buffer.

        Returns:
            Tuple of (text_before, prefix, sorted_candidates).
        """
        trimmed = text.strip()
        if not trimmed:
            # Empty input: return root level commands
            expected = self.parser.get_expected_tokens("")
            candidates = self._tokens_to_candidates(expected)
            return ("", "", self._sort_candidates(candidates))

        # Check if the text ends with space (explicit continuation)
        if text.endswith(" "):
            expected = self.parser.get_expected_tokens(trimmed)
            candidates = self._tokens_to_candidates(expected, context=trimmed)
            text_before = text
            return (text_before, "", self._sort_candidates(candidates))

        # Check if the entire trimmed string is already a complete, valid token
        # (e.g. user typed '1', '10', '1 AT', 'GOTO CUE') and pressed Tab
        is_complete = self._is_complete_token(trimmed)
        if is_complete:
            expected = self.parser.get_expected_tokens(trimmed)
            candidates = self._tokens_to_candidates(expected, context=trimmed)
            if candidates:
                text_before = trimmed + " "
                return (text_before, "", self._sort_candidates(candidates))

        # Partial token under cursor
        last_space_idx = text.rfind(" ")
        if last_space_idx == -1:
            context = ""
            prefix = text
            text_before = ""
        else:
            context = text[:last_space_idx].strip()
            prefix = text[last_space_idx + 1 :]
            text_before = text[: last_space_idx + 1]

        expected = self.parser.get_expected_tokens(context)
        all_candidates = self._tokens_to_candidates(expected, context=context)
        prefix_upper = prefix.upper()

        matching = [c for c in all_candidates if c.upper().startswith(prefix_upper)]
        return (text_before, prefix, self._sort_candidates(matching))

    def complete(self, text: str) -> CompletionResult:
        """Perform auto-completion or advance Tab cycle.

        Args:
            text: Current command line buffer string.

        Returns:
            CompletionResult with the substituted text and candidates.
        """
        # 1. Continue existing Tab cycle if text matches last output
        if self._in_cycle and text == self._last_completed_text:
            if not self._cycle_candidates:
                return CompletionResult(text, [], self._cycle_prefix, False)

            self._cycle_index = (self._cycle_index + 1) % len(self._cycle_candidates)
            candidate = self._cycle_candidates[self._cycle_index]
            new_text = f"{self._cycle_text_before}{candidate} "
            self._last_completed_text = new_text
            return CompletionResult(
                new_text,
                self._cycle_candidates,
                self._cycle_prefix,
                True,
            )

        # 2. Fresh completion attempt
        text_before, prefix, candidates = self.get_candidates(text)
        if not candidates:
            self.reset_cycle()
            return CompletionResult(text, [], prefix, False)

        self._in_cycle = True
        self._cycle_index = 0
        self._cycle_candidates = candidates
        self._cycle_text_before = text_before
        self._cycle_prefix = prefix

        candidate = candidates[0]
        new_text = f"{text_before}{candidate} "
        self._last_completed_text = new_text
        return CompletionResult(new_text, candidates, prefix, True)

    def _is_complete_token(self, text: str) -> bool:
        """Return True if text forms a complete token/phrase allowing continuation."""
        try:
            tokens = self.lexer.tokenize(text)
            if not tokens or tokens[-1].type != TokenType.EOF:
                return False
            active = tokens[:-1]
            if not active:
                return False
            # Numbers, AT, FULL, OUT, ALL, CUE are complete tokens
            return active[-1].type in (
                TokenType.NUMBER,
                TokenType.AT,
                TokenType.FULL,
                TokenType.OUT,
                TokenType.ALL,
                TokenType.CUE,
                TokenType.GROUP,
            )
        except LexerError:
            return False

    def _tokens_to_candidates(
        self, expected: list[TokenType], context: str = ""
    ) -> list[str]:
        """Convert TokenType list and context into string candidates."""
        candidates: list[str] = []

        for tok in expected:
            if tok in TOKEN_TO_KEYWORD:
                candidates.append(TOKEN_TO_KEYWORD[tok])

        context_upper = context.upper().split()
        last_keyword = context_upper[-1] if context_upper else ""

        # Contextual show entities: Cues
        if TokenType.NUMBER in expected and last_keyword == "CUE" and self.lightshow:
            cues = self._get_show_cue_candidates()
            candidates.extend(cues)

        # Contextual show entities: Groups
        if TokenType.NUMBER in expected and last_keyword == "GROUP" and self.lightshow:
            groups = self._get_show_group_candidates()
            candidates.extend(groups)

        # Contextual presets: Colors
        if last_keyword in ("COLOR", "COLOUR"):
            candidates.extend(COLOR_PRESETS.keys())

        return list(dict.fromkeys(candidates))

    def _get_show_cue_candidates(self) -> list[str]:
        """Extract existing cue identifiers from the active LightShow."""
        if not self.lightshow or not hasattr(self.lightshow, "cues"):
            return []
        res: list[str] = []
        for cue in self.lightshow.cues:
            cid = getattr(cue, "id", None)
            if cid is not None:
                if isinstance(cid, (int, float)) and float(cid).is_integer():
                    formatted = str(int(cid))
                else:
                    formatted = str(cid)
                if formatted not in res:
                    res.append(formatted)
        return res

    def _get_show_group_candidates(self) -> list[str]:
        """Extract existing group identifiers from the active LightShow."""
        if not self.lightshow or not hasattr(self.lightshow, "groups"):
            return []
        groups_dict = getattr(self.lightshow.groups, "groups", None)
        if isinstance(groups_dict, dict):
            return [str(k) for k in sorted(groups_dict.keys())]
        return []

    def _sort_candidates(self, candidates: list[str]) -> list[str]:
        """Sort candidates putting high-priority keywords first."""
        priority_map = {kw: idx for idx, kw in enumerate(KEYWORD_PRIORITY)}
        return sorted(
            candidates,
            key=lambda c: (priority_map.get(c.upper(), 100), c),
        )
