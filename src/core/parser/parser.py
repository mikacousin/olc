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
"""Recursive descent LL(1) parser for industry standard lighting commands."""

from __future__ import annotations

import typing

from olc.core.parser.ast_nodes import (
    AllSelectionNode,
    AttributeCommandNode,
    BlockCueCommandNode,
    ChannelNumberNode,
    ChannelRangeNode,
    CommandNode,
    DeleteCueCommandNode,
    GotoCueCommandNode,
    GroupSelectionNode,
    IntensityCommandNode,
    RecordCueCommandNode,
    SelectionItemNode,
    SelectionNode,
    SelectOnlyCommandNode,
    UnblockCueCommandNode,
    UpdateCueCommandNode,
)
from olc.core.parser.lexer import CommandLexer, LexerError
from olc.core.parser.tokens import Token, TokenType


class CommandSyntaxError(Exception):
    """Raised when command syntax is invalid."""

    def __init__(self, message: str, position: int, token: Token | None = None) -> None:
        super().__init__(f"{message} (at position {position})")
        self.message = message
        self.position = position
        self.token = token


# Attribute token mapping
ATTRIBUTE_TOKENS = {
    TokenType.PAN: "pan",
    TokenType.TILT: "tilt",
    TokenType.COLOR: "color",
    TokenType.ZOOM: "zoom",
    TokenType.FOCUS: "focus",
    TokenType.IRIS: "iris",
    TokenType.STROBE: "strobe",
    TokenType.CCT: "cct",
    TokenType.GOBO: "gobo",
    TokenType.PRISM: "prism",
    TokenType.COLOR_WHEEL: "color_wheel",
    TokenType.GOBO_WHEEL: "gobo_wheel",
}


class CommandParser:
    """Predictive recursive descent parser generating AST from token streams."""

    def __init__(self) -> None:
        self.lexer = CommandLexer()
        self.tokens: list[Token] = []
        self.pos: int = 0

    @property
    def current(self) -> Token:
        """Return the current token under the cursor."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def peek(self) -> Token:
        """Peek at the current token without consuming it."""
        return self.current

    def advance(self) -> Token:
        """Consume and return current token."""
        tok = self.current
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def match(self, *expected_types: TokenType) -> bool:
        """Check if current token matches any expected type; if so, advance."""
        if self.current.type in expected_types:
            self.advance()
            return True
        return False

    def expect(self, expected_type: TokenType, error_msg: str) -> Token:
        """Consume current token if it matches expected_type, otherwise raise."""
        tok = self.current
        if tok.type != expected_type:
            raise CommandSyntaxError(
                f"{error_msg}, got {tok.raw_text!r} ({tok.type.name})",
                tok.position,
                tok,
            )
        self.advance()
        return tok

    def parse(self, text: str) -> CommandNode:
        """Parse a full command string into an AST CommandNode.

        Args:
            text: Raw command string to parse.

        Returns:
            Root CommandNode representing the instruction.

        Raises:
            CommandSyntaxError: If syntax is invalid.
        """
        trimmed = text.strip()
        if not trimmed:
            raise CommandSyntaxError("Empty command line", 0)

        try:
            self.tokens = self.lexer.tokenize(trimmed)
        except LexerError as exc:
            raise CommandSyntaxError(str(exc), exc.position) from exc

        self.pos = 0
        node = self._parse_command()

        if self.current.type != TokenType.EOF:
            raise CommandSyntaxError(
                f"Unexpected token {self.current.raw_text!r} after command",
                self.current.position,
                self.current,
            )

        return node

    # --- Top Level Commands ---

    def _parse_command(self) -> CommandNode:  # pylint: disable=too-many-return-statements
        tok = self.peek()

        if tok.type == TokenType.CUE:
            return self._parse_cue_first_command()

        if tok.type == TokenType.RECORD:
            return self._parse_record_cue()

        if tok.type == TokenType.UPDATE:
            return self._parse_update_cue()

        if tok.type == TokenType.GOTO:
            return self._parse_goto_cue()

        if tok.type == TokenType.BLOCK:
            return self._parse_block_cue()

        if tok.type == TokenType.UNBLOCK:
            return self._parse_unblock_cue()

        if tok.type == TokenType.DELETE:
            return self._parse_delete_cue()

        # Check if command starts directly with an intensity or attribute
        # (implicit selection on currently active fixtures)
        if tok.type == TokenType.AT or tok.type in ATTRIBUTE_TOKENS:
            return self._parse_action_clause(selection=None)

        # Otherwise, starts with channel selection
        selection = self._parse_selection()

        if self.peek().type == TokenType.EOF:
            return SelectOnlyCommandNode(selection)

        return self._parse_action_clause(selection)

    # --- Cue Commands ---

    def _parse_cue_first_command(  # pylint: disable=too-many-return-statements
        self,
    ) -> CommandNode:
        """Parse noun-first cue commands (e.g. CUE 5 RECORD TIME 3, CUE 4 UPDATE)."""
        self.advance()  # Consume CUE
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after CUE")
        cue_id = float(tok_num.value)

        tok_action = self.peek()
        if self.match(TokenType.RECORD):
            return self._parse_record_cue_options(cue_id)
        if self.match(TokenType.UPDATE):
            return UpdateCueCommandNode(cue_id=cue_id)
        if self.match(TokenType.DELETE):
            return DeleteCueCommandNode(cue_id=cue_id)
        if self.match(TokenType.BLOCK):
            return BlockCueCommandNode(cue_id=cue_id)
        if self.match(TokenType.UNBLOCK):
            return UnblockCueCommandNode(cue_id=cue_id)
        if self.match(TokenType.GOTO):
            fade_time: float | None = None
            if self.match(TokenType.TIME):
                tok_time = self.expect(
                    TokenType.NUMBER, "Expected fade time after TIME"
                )
                fade_time = float(tok_time.value)
            return GotoCueCommandNode(cue_id=cue_id, time=fade_time)

        raise CommandSyntaxError(
            f"Expected cue action (RECORD, UPDATE, DELETE, BLOCK, UNBLOCK, GOTO) "
            f"after CUE {tok_num.raw_text}, got {tok_action.raw_text!r}",
            tok_action.position,
            tok_action,
        )

    def _parse_family_timing_clause(
        self, family_tok: TokenType
    ) -> tuple[float | None, float | None]:
        """Parse [TIME] <t> [DELAY <d>] or DELAY <d> [TIME <t>] for a family."""
        fam_time: float | None = None
        fam_delay: float | None = None
        fam_name = family_tok.name

        if self.match(TokenType.DELAY):
            tok_d = self.expect(
                TokenType.NUMBER, f"Expected delay value in seconds after {fam_name}"
            )
            fam_delay = float(tok_d.value)
            if self.match(TokenType.TIME):
                tok_t = self.expect(
                    TokenType.NUMBER, f"Expected time value in seconds after {fam_name}"
                )
                fam_time = float(tok_t.value)
        else:
            self.match(TokenType.TIME)
            tok_t = self.expect(
                TokenType.NUMBER, f"Expected time value in seconds after {fam_name}"
            )
            fam_time = float(tok_t.value)
            if self.match(TokenType.DELAY):
                tok_d = self.expect(
                    TokenType.NUMBER,
                    f"Expected delay value in seconds after {fam_name}",
                )
                fam_delay = float(tok_d.value)

        return fam_time, fam_delay

    def _parse_record_cue_options(  # pylint: disable=too-many-locals,too-many-branches
        self, cue_id: float
    ) -> RecordCueCommandNode:
        """Parse TIME, DELAY, BLOCK and IFCB family modifiers for RECORD CUE."""
        time_in: float | None = None
        time_out: float | None = None
        delay: float | None = None
        is_block = False
        family_times: dict[TokenType, float | None] = {
            TokenType.POSITION: None,
            TokenType.COLOR: None,
            TokenType.BEAM: None,
        }
        family_delays: dict[TokenType, float | None] = {
            TokenType.POSITION: None,
            TokenType.COLOR: None,
            TokenType.BEAM: None,
        }
        family_tokens = (TokenType.POSITION, TokenType.COLOR, TokenType.BEAM)

        while self.peek().type != TokenType.EOF:
            if self.match(TokenType.TIME):
                if self.peek().type in family_tokens:
                    fam_tok = self.advance().type
                    tok_ft = self.expect(
                        TokenType.NUMBER, "Expected family time value in seconds"
                    )
                    family_times[fam_tok] = float(tok_ft.value)
                else:
                    tok_t1 = self.expect(
                        TokenType.NUMBER, "Expected time value in seconds"
                    )
                    time_in = float(tok_t1.value)
                    if self.match(TokenType.SLASH):
                        tok_t2 = self.expect(
                            TokenType.NUMBER, "Expected out-fade time value after '/'"
                        )
                        time_out = float(tok_t2.value)
                    else:
                        time_out = time_in
            elif self.match(TokenType.DELAY):
                if self.peek().type in family_tokens:
                    fam_tok = self.advance().type
                    tok_fd = self.expect(
                        TokenType.NUMBER, "Expected family delay value in seconds"
                    )
                    family_delays[fam_tok] = float(tok_fd.value)
                else:
                    tok_del = self.expect(
                        TokenType.NUMBER, "Expected delay value in seconds"
                    )
                    delay = float(tok_del.value)
            elif self.peek().type in family_tokens:
                fam_tok = self.advance().type
                f_time, f_delay = self._parse_family_timing_clause(fam_tok)
                if f_time is not None:
                    family_times[fam_tok] = f_time
                if f_delay is not None:
                    family_delays[fam_tok] = f_delay
            elif self.match(TokenType.BLOCK):
                is_block = True
            else:
                break

        return RecordCueCommandNode(
            cue_id=cue_id,
            time_in=time_in,
            time_out=time_out,
            delay=delay,
            is_block=is_block,
            time_position=family_times[TokenType.POSITION],
            delay_position=family_delays[TokenType.POSITION],
            time_color=family_times[TokenType.COLOR],
            delay_color=family_delays[TokenType.COLOR],
            time_beam=family_times[TokenType.BEAM],
            delay_beam=family_delays[TokenType.BEAM],
        )

    def _parse_record_cue(self) -> RecordCueCommandNode:
        self.advance()  # Consume RECORD
        self.match(TokenType.CUE)  # Optional CUE keyword

        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after RECORD")
        cue_id = float(tok_num.value)
        return self._parse_record_cue_options(cue_id)

    def _parse_update_cue(self) -> UpdateCueCommandNode:
        self.advance()  # Consume UPDATE
        self.match(TokenType.CUE)  # Optional CUE keyword

        cue_id: float | None = None
        if self.peek().type == TokenType.NUMBER:
            cue_id = float(self.advance().value)

        return UpdateCueCommandNode(cue_id=cue_id)

    def _parse_goto_cue(self) -> GotoCueCommandNode:
        self.advance()  # Consume GOTO
        self.match(TokenType.CUE)  # Optional CUE keyword

        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after GOTO")
        cue_id = float(tok_num.value)

        fade_time: float | None = None
        if self.match(TokenType.TIME):
            tok_time = self.expect(TokenType.NUMBER, "Expected fade time after TIME")
            fade_time = float(tok_time.value)

        return GotoCueCommandNode(cue_id=cue_id, time=fade_time)

    def _parse_block_cue(self) -> BlockCueCommandNode:
        self.advance()  # Consume BLOCK
        self.match(TokenType.CUE)  # Optional CUE keyword
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after BLOCK")
        return BlockCueCommandNode(cue_id=float(tok_num.value))

    def _parse_unblock_cue(self) -> UnblockCueCommandNode:
        self.advance()  # Consume UNBLOCK
        self.match(TokenType.CUE)  # Optional CUE keyword
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after UNBLOCK")
        return UnblockCueCommandNode(cue_id=float(tok_num.value))

    def _parse_delete_cue(self) -> DeleteCueCommandNode:
        self.advance()  # Consume DELETE
        self.match(TokenType.CUE)  # Optional CUE keyword
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after DELETE")
        return DeleteCueCommandNode(cue_id=float(tok_num.value))

    # --- Selection Parsing ---

    def _parse_selection(self) -> SelectionNode:
        items: list[SelectionItemNode] = []
        exclusions: list[SelectionItemNode] = []

        # First item (positive)
        first_item = self._parse_selection_item()
        items.append(first_item)

        # Subsequent additions (+) or exclusions (-)
        while True:
            if self.match(TokenType.PLUS):
                items.append(self._parse_selection_item())
            elif self.match(TokenType.MINUS):
                exclusions.append(self._parse_selection_item())
            else:
                break

        # Check for ODD / EVEN filter
        filter_mode: typing.Literal["all", "odd", "even"] = "all"
        if self.match(TokenType.ODD):
            filter_mode = "odd"
        elif self.match(TokenType.EVEN):
            filter_mode = "even"

        return SelectionNode(
            items=items,
            exclusions=exclusions,
            filter_mode=filter_mode,
        )

    def _parse_selection_item(self) -> SelectionItemNode:
        tok = self.peek()

        if tok.type == TokenType.ALL:
            self.advance()
            return AllSelectionNode()

        if tok.type == TokenType.GROUP:
            self.advance()
            num_tok = self.expect(TokenType.NUMBER, "Expected group number after GROUP")
            return GroupSelectionNode(group_id=int(num_tok.value))

        if tok.type == TokenType.NUMBER:
            start_val = int(self.advance().value)
            if self.match(TokenType.THRU):
                end_tok = self.expect(
                    TokenType.NUMBER, "Expected target channel number after THRU"
                )
                end_val = int(end_tok.value)
                return ChannelRangeNode(start=start_val, end=end_val)
            return ChannelNumberNode(channel=start_val)

        raise CommandSyntaxError(
            f"Expected channel number, GROUP or ALL, got {tok.raw_text!r}",
            tok.position,
            tok,
        )

    # --- Action Clause Parsing (Intensity & Attributes) ---

    def _parse_action_clause(self, selection: SelectionNode | None) -> CommandNode:
        intensity_level: float | None = None
        is_intensity_relative = False
        attributes: dict[str, typing.Any] = {}

        while self.peek().type != TokenType.EOF:
            tok = self.peek()

            if tok.type == TokenType.AT:
                self.advance()  # Consume AT
                level, relative = self._parse_intensity_value()
                intensity_level = level
                is_intensity_relative = relative

            elif tok.type in ATTRIBUTE_TOKENS:
                attr_name = ATTRIBUTE_TOKENS[tok.type]
                self.advance()  # Consume attribute keyword
                val = self._parse_attribute_value(tok.type)
                attributes[attr_name] = val

            else:
                break

        # Validate that at least one action was specified
        if intensity_level is None and not attributes:
            err = (
                f"Expected AT level or attribute assignment, "
                f"got {self.peek().raw_text!r}"
            )
            raise CommandSyntaxError(
                err,
                self.peek().position,
                self.peek(),
            )

        if not attributes and intensity_level is not None:
            return IntensityCommandNode(
                selection=selection,
                level=intensity_level,
                is_relative=is_intensity_relative,
            )

        return AttributeCommandNode(
            selection=selection,
            attributes=attributes,
            intensity_level=intensity_level,
            is_intensity_relative=is_intensity_relative,
        )

    def _parse_intensity_value(self) -> tuple[float, bool]:
        tok = self.peek()

        if tok.type == TokenType.FULL:
            self.advance()
            return (100.0, False)

        if tok.type == TokenType.OUT:
            self.advance()
            return (0.0, False)

        if tok.type == TokenType.PLUS:
            self.advance()
            num_tok = self.expect(
                TokenType.NUMBER, "Expected number after '+' for relative intensity"
            )
            return (float(num_tok.value), True)

        if tok.type == TokenType.MINUS:
            self.advance()
            num_tok = self.expect(
                TokenType.NUMBER, "Expected number after '-' for relative intensity"
            )
            return (-float(num_tok.value), True)

        if tok.type == TokenType.NUMBER:
            self.advance()
            val = float(tok.value)
            if not 0.0 <= val <= 100.0:
                raise CommandSyntaxError(
                    f"Intensity level must be between 0 and 100, got {val}",
                    tok.position,
                    tok,
                )
            return (val, False)

        msg = (
            f"Expected intensity level (0..100, FULL, OUT, +N, -N), "
            f"got {tok.raw_text!r}"
        )
        raise CommandSyntaxError(
            msg,
            tok.position,
            tok,
        )

    def _parse_attribute_value(self, attr_type: TokenType) -> object:
        tok = self.peek()

        # Handle color values (#FF8800, "RED", or identifier RED)
        if attr_type == TokenType.COLOR:
            if tok.type in (TokenType.HEX_COLOR, TokenType.STRING, TokenType.IDENT):
                self.advance()
                return tok.value
            raise CommandSyntaxError(
                f"Expected color hex code or name, got {tok.raw_text!r}",
                tok.position,
                tok,
            )

        # Handle signed numerical angles/values (PAN -45, TILT +30, ZOOM 25)
        sign = 1.0
        if tok.type == TokenType.MINUS:
            sign = -1.0
            self.advance()
            tok = self.peek()
        elif tok.type == TokenType.PLUS:
            self.advance()
            tok = self.peek()

        if tok.type == TokenType.NUMBER:
            self.advance()
            return sign * float(tok.value)

        # String or ident for gobos/wheels (e.g. GOBO "Open", GOBO 2)
        if tok.type in (TokenType.STRING, TokenType.IDENT):
            self.advance()
            return tok.value

        raise CommandSyntaxError(
            f"Expected value for attribute {attr_type.name}, got {tok.raw_text!r}",
            tok.position,
            tok,
        )

    @staticmethod
    def _get_record_expected_tokens(
        active_tokens: list[Token], text: str
    ) -> list[TokenType]:
        """Return expected tokens within a RECORD CUE options clause."""
        last = active_tokens[-1]
        prev = active_tokens[-2].type if len(active_tokens) >= 2 else None
        families = (TokenType.POSITION, TokenType.COLOR, TokenType.BEAM)

        if last.type in (TokenType.TIME, TokenType.DELAY):
            if prev in families:
                return [TokenType.NUMBER]
            return [TokenType.NUMBER, *families]

        if last.type in families:
            if prev in (TokenType.TIME, TokenType.DELAY):
                return [TokenType.NUMBER]
            return [TokenType.NUMBER, TokenType.TIME, TokenType.DELAY]

        if last.type == TokenType.SLASH:
            return [TokenType.NUMBER]

        res = [
            TokenType.TIME,
            TokenType.DELAY,
            TokenType.BLOCK,
            *families,
        ]
        if last.type == TokenType.NUMBER and prev == TokenType.TIME:
            res.insert(0, TokenType.SLASH)
        if last.type == TokenType.NUMBER and not text.endswith(" "):
            res.append(TokenType.NUMBER)
        return res

    @staticmethod
    def _get_goto_expected_tokens(
        active_tokens: list[Token], text: str
    ) -> list[TokenType]:
        """Return expected tokens within a GOTO CUE options clause."""
        last = active_tokens[-1]
        if last.type == TokenType.TIME:
            return [TokenType.NUMBER]
        if all(t.type != TokenType.TIME for t in active_tokens):
            res = [TokenType.TIME]
            if last.type == TokenType.NUMBER and not text.endswith(" "):
                res.append(TokenType.NUMBER)
            return res
        return []

    def _get_cue_expected_tokens(  # pylint: disable=too-many-return-statements
        self, active_tokens: list[Token], text: str
    ) -> list[TokenType] | None:
        """Return expected tokens when the command starts with a cue keyword."""
        first = active_tokens[0].type

        if first == TokenType.CUE:
            if len(active_tokens) == 1:
                return [TokenType.NUMBER]
            if len(active_tokens) == 2 and active_tokens[1].type == TokenType.NUMBER:
                res = [
                    TokenType.RECORD,
                    TokenType.UPDATE,
                    TokenType.GOTO,
                    TokenType.BLOCK,
                    TokenType.UNBLOCK,
                    TokenType.DELETE,
                ]
                if not text.endswith(" "):
                    res.append(TokenType.NUMBER)
                return res
            if active_tokens[2].type == TokenType.RECORD:
                return self._get_record_expected_tokens(active_tokens, text)
            if active_tokens[2].type == TokenType.GOTO:
                return self._get_goto_expected_tokens(active_tokens, text)
            return []

        if first in (
            TokenType.RECORD,
            TokenType.GOTO,
            TokenType.UPDATE,
            TokenType.BLOCK,
            TokenType.UNBLOCK,
            TokenType.DELETE,
        ):
            if len(active_tokens) == 1:
                return [TokenType.CUE, TokenType.NUMBER]
            if len(active_tokens) == 2 and active_tokens[1].type == TokenType.CUE:
                return [TokenType.NUMBER]
            if first == TokenType.RECORD:
                return self._get_record_expected_tokens(active_tokens, text)
            if first == TokenType.GOTO:
                return self._get_goto_expected_tokens(active_tokens, text)
            return []

        return None

    def get_expected_tokens(  # pylint: disable=too-many-return-statements,too-many-branches
        self, text: str
    ) -> list[TokenType]:
        """Inspect a partial command string and return expected token types next.

        Useful for GUI feedback, auto-completion, and dynamic button enablement.
        """
        trimmed = text.strip()
        if not trimmed:
            return [
                TokenType.NUMBER,
                TokenType.CUE,
                TokenType.GROUP,
                TokenType.ALL,
                TokenType.RECORD,
                TokenType.UPDATE,
                TokenType.GOTO,
                TokenType.BLOCK,
                TokenType.UNBLOCK,
                TokenType.DELETE,
                TokenType.AT,
            ]

        try:
            tokens = self.lexer.tokenize(trimmed)
        except LexerError:
            return []

        if not tokens or tokens[-1].type != TokenType.EOF:
            return []

        # Remove EOF for inspection
        active_tokens = tokens[:-1]
        if not active_tokens:
            return []

        cue_expected = self._get_cue_expected_tokens(active_tokens, text)
        if cue_expected is not None:
            return cue_expected

        last = active_tokens[-1]

        if last.type in (TokenType.NUMBER, TokenType.ALL):
            res = [
                TokenType.THRU,
                TokenType.PLUS,
                TokenType.MINUS,
                TokenType.ODD,
                TokenType.EVEN,
                TokenType.AT,
                *ATTRIBUTE_TOKENS.keys(),
            ]
            # If the user is currently typing a multi-digit number (no trailing space),
            # allow entering more digits
            if last.type == TokenType.NUMBER and not text.endswith(" "):
                res.append(TokenType.NUMBER)
            return res

        if last.type == TokenType.THRU:
            return [TokenType.NUMBER]

        if last.type in (TokenType.PLUS, TokenType.MINUS):
            return [TokenType.NUMBER, TokenType.GROUP]

        if last.type == TokenType.AT:
            return [
                TokenType.NUMBER,
                TokenType.FULL,
                TokenType.OUT,
                TokenType.PLUS,
                TokenType.MINUS,
            ]

        if last.type in ATTRIBUTE_TOKENS:
            if last.type == TokenType.COLOR:
                return [TokenType.HEX_COLOR, TokenType.STRING, TokenType.IDENT]
            return [TokenType.NUMBER, TokenType.STRING, TokenType.IDENT]

        if last.type == TokenType.GROUP:
            return [TokenType.NUMBER]

        return []
