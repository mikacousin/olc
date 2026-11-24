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
    AddressItemNode,
    AddressLevelCommandNode,
    AddressNumberNode,
    AddressParkCommandNode,
    AddressRangeNode,
    AddressSelectionNode,
    AddressUnparkCommandNode,
    AllSelectionNode,
    ApplyEffectCommandNode,
    ApplyPaletteCommandNode,
    AttributeCommandNode,
    BlockCueCommandNode,
    ChannelCheckCommandNode,
    ChannelNumberNode,
    ChannelParkCommandNode,
    ChannelRangeNode,
    ChannelUnparkCommandNode,
    CommandNode,
    DeleteCueCommandNode,
    DeleteEffectCommandNode,
    DeleteGroupCommandNode,
    DeletePaletteCommandNode,
    EditEffectCommandNode,
    GotoCueCommandNode,
    GroupSelectionNode,
    HomeCommandNode,
    IntensityCommandNode,
    LabelGroupCommandNode,
    LocateCommandNode,
    ParkUnparkAllCommandNode,
    PatchCommandNode,
    RecordCueCommandNode,
    RecordGroupCommandNode,
    RecordPaletteCommandNode,
    RelativeThruNode,
    SelectionItemNode,
    SelectionNode,
    SelectOnlyCommandNode,
    SneakCommandNode,
    StopEffectCommandNode,
    UnblockCueCommandNode,
    UnpatchCommandNode,
    UpdateCueCommandNode,
    UpdateGroupCommandNode,
    UpdatePaletteCommandNode,
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

PALETTE_CATEGORY_TOKENS: dict[TokenType, str] = {
    TokenType.INTENSITY: "intensity",
    TokenType.FOCUS: "focus",
    TokenType.COLOR: "color",
    TokenType.BEAM: "beam",
}

PALETTE_SHORTHAND_TOKENS: dict[TokenType, str] = {
    TokenType.IP: "intensity",
    TokenType.FP: "focus",
    TokenType.CP: "color",
    TokenType.BP: "beam",
}


class CommandParser:
    """Predictive recursive descent parser generating AST from token streams."""

    def __init__(self) -> None:
        self.lexer = CommandLexer()
        self.tokens: list[Token] = []
        self.pos: int = 0
        self._probe_expected: list[TokenType] | None = None

    def _record_expected(self, *types: TokenType) -> None:
        """Record expected token types when probing at EOF."""
        if self._probe_expected is not None and self.current.type == TokenType.EOF:
            for t in types:
                if t not in self._probe_expected:
                    self._probe_expected.append(t)

    def _peek_is(self, *types: TokenType) -> bool:
        """Check if current token matches *types, recording expectations at EOF."""
        self._record_expected(*types)
        return self.current.type in types

    @property
    def current(self) -> Token:
        """Return the current token under the cursor."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def peek(self) -> Token:
        """Peek at the current token without consuming it."""
        return self.current

    def peek_ahead(self, offset: int = 1) -> Token:
        """Peek at the token offset positions ahead of current cursor."""
        target_pos = self.pos + offset
        if target_pos < len(self.tokens):
            return self.tokens[target_pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        """Consume and return current token."""
        tok = self.current
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def match(self, *expected_types: TokenType) -> bool:
        """Check if current token matches any expected type; if so, advance."""
        self._record_expected(*expected_types)
        if self.current.type in expected_types:
            self.advance()
            return True
        return False

    def expect(self, expected_type: TokenType, error_msg: str) -> Token:
        """Consume current token if it matches expected_type, otherwise raise."""
        self._record_expected(expected_type)
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
        if self._peek_is(TokenType.CUE, TokenType.SEQUENCE):
            return self._parse_cue_first_command()

        if self._peek_is(TokenType.RECORD):
            return self._parse_record_cue()

        if self._peek_is(TokenType.UPDATE):
            return self._parse_update_cue()

        if self._peek_is(TokenType.GOTO):
            return self._parse_goto_cue()

        if self._peek_is(TokenType.BLOCK):
            return self._parse_block_cue()

        if self._peek_is(TokenType.UNBLOCK):
            return self._parse_unblock_cue()

        if self._peek_is(TokenType.DELETE):
            return self._parse_delete_cue()

        if self._peek_is(TokenType.LABEL):
            return self._parse_label_command()

        if self._peek_is(TokenType.SNEAK):
            return self._parse_sneak_command(selection=None)

        if self._peek_is(TokenType.STOP):
            return self._parse_stop_effect_command(selection=None)

        if self._peek_is(TokenType.EFFECT):
            return self._parse_effect_command(selection=None)

        if self._peek_is(TokenType.INDEPENDENT):
            return self._parse_independent_command()

        if self._peek_is(TokenType.PARK):
            self.advance()
            if self.match(TokenType.ALL):
                return ParkUnparkAllCommandNode()
            if self.match(TokenType.AT):
                if self.peek().type == TokenType.EOF:
                    self._record_expected(
                        TokenType.NUMBER,
                        TokenType.FULL,
                        TokenType.OUT,
                        TokenType.PLUS,
                        TokenType.MINUS,
                    )
                    return ChannelUnparkCommandNode(selection=None)
                level, _ = self._parse_intensity_value()
                return ChannelParkCommandNode(selection=None, level=level)
            if self._peek_is(TokenType.NUMBER, TokenType.CHANNEL, TokenType.GROUP):
                sel = self._parse_selection()
                lvl = None
                if self.match(TokenType.AT):
                    if self.peek().type == TokenType.EOF:
                        self._record_expected(
                            TokenType.NUMBER,
                            TokenType.FULL,
                            TokenType.OUT,
                            TokenType.PLUS,
                            TokenType.MINUS,
                        )
                    else:
                        lvl, _ = self._parse_intensity_value()
                return ChannelParkCommandNode(selection=sel, level=lvl)
            return ChannelParkCommandNode(selection=None, level=None)

        if self._peek_is(TokenType.UNPARK):
            self.advance()
            if self.match(TokenType.ALL):
                return ParkUnparkAllCommandNode()
            if self._peek_is(TokenType.ADDRESS):
                addrs = self._parse_address_selection()
                return AddressUnparkCommandNode(addresses=addrs)
            if self._peek_is(TokenType.NUMBER, TokenType.CHANNEL, TokenType.GROUP):
                sel = self._parse_selection()
                return ChannelUnparkCommandNode(selection=sel)
            return ChannelUnparkCommandNode(selection=None)

        if self._peek_is(TokenType.ADDRESS):
            addrs = self._parse_address_selection()
            if self.match(TokenType.UNPATCH):
                return UnpatchCommandNode(selection=None, addresses=addrs)
            if self.match(TokenType.UNPARK):
                return AddressUnparkCommandNode(addresses=addrs)
            if self.match(TokenType.PARK):
                if self.match(TokenType.AT):
                    if self.peek().type == TokenType.EOF:
                        self._record_expected(
                            TokenType.NUMBER,
                            TokenType.FULL,
                            TokenType.OUT,
                            TokenType.PLUS,
                            TokenType.MINUS,
                        )
                        return AddressUnparkCommandNode(addresses=addrs)
                    lvl, _ = self._parse_intensity_value()
                    return AddressParkCommandNode(addresses=addrs, level=lvl)
                return AddressParkCommandNode(addresses=addrs, level=100.0)
            if self.match(TokenType.AT):
                if self.peek().type == TokenType.EOF:
                    self._record_expected(
                        TokenType.NUMBER,
                        TokenType.FULL,
                        TokenType.OUT,
                        TokenType.PLUS,
                        TokenType.MINUS,
                    )
                    return AddressLevelCommandNode(addresses=addrs, level=None)
                lvl, _ = self._parse_intensity_value()
                return AddressLevelCommandNode(addresses=addrs, level=lvl)
            raise CommandSyntaxError(
                f"Expected PARK, UNPARK, or AT after ADDRESS, "
                f"got {self.peek().raw_text!r}",
                self.peek().position,
                self.peek(),
            )

        # Standalone LOCATE / HOME (implicit selection)
        if self._peek_is(TokenType.LOCATE):
            self.advance()
            return LocateCommandNode(selection=None)

        if self._peek_is(TokenType.HOME):
            self.advance()
            cat = None
            if self._peek_is(TokenType.POSITION, TokenType.COLOR, TokenType.BEAM):
                cat = self.advance().raw_text.lower()
            return HomeCommandNode(selection=None, category=cat)

        if self._peek_is(TokenType.POSITION, TokenType.COLOR, TokenType.BEAM):
            if (
                self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.HOME
            ):
                cat_tok = self.advance()
                self.advance()  # consume HOME
                return HomeCommandNode(
                    selection=None, category=cat_tok.raw_text.lower()
                )
            if (
                self._probe_expected is not None
                and self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.EOF
                and TokenType.HOME not in self._probe_expected
            ):
                self._probe_expected.append(TokenType.HOME)

        palette_cmd = self._try_parse_apply_palette(selection=None)
        if palette_cmd is not None:
            return palette_cmd

        # Relative selection starting with +, -, or THRU (applies to active selection)
        if self._peek_is(TokenType.PLUS, TokenType.MINUS, TokenType.THRU):
            selection = self._parse_relative_selection()
        # Relative odd/even filter starting directly on active selection
        elif self._peek_is(TokenType.ODD, TokenType.EVEN):
            selection = self._parse_relative_filter_selection()
        # Check if command starts directly with an intensity or attribute
        # (implicit selection on currently active fixtures)
        elif self._peek_is(TokenType.AT, *ATTRIBUTE_TOKENS.keys()):
            return self._parse_action_clause(selection=None)
        else:
            # Otherwise, starts with channel selection
            selection = self._parse_selection()

        if self._probe_expected is None and self.peek().type == TokenType.EOF:
            return SelectOnlyCommandNode(selection)

        if self.match(TokenType.PATCH):
            self.expect(TokenType.AT, "Expected AT after PATCH")
            addrs = self._parse_address_selection(require_address_kw=False)
            return PatchCommandNode(selection=selection, addresses=addrs)

        if self.match(TokenType.UNPATCH):
            addrs = None
            if self.match(TokenType.AT):
                addrs = self._parse_address_selection(require_address_kw=False)
            return UnpatchCommandNode(selection=selection, addresses=addrs)

        if self.match(TokenType.CHECK):
            if self.match(TokenType.AT):
                if self.peek().type == TokenType.EOF:
                    self._record_expected(
                        TokenType.NUMBER,
                        TokenType.FULL,
                        TokenType.OUT,
                        TokenType.PLUS,
                        TokenType.MINUS,
                    )
                    return ChannelCheckCommandNode(selection=selection, level=0.0)
                lvl, _ = self._parse_intensity_value()
                return ChannelCheckCommandNode(selection=selection, level=lvl)
            return ChannelCheckCommandNode(selection=selection, level=None)

        if self.match(TokenType.UNPARK):
            return ChannelUnparkCommandNode(selection=selection)

        if self.match(TokenType.PARK):
            if self.match(TokenType.AT):
                if self.peek().type == TokenType.EOF:
                    self._record_expected(
                        TokenType.NUMBER,
                        TokenType.FULL,
                        TokenType.OUT,
                        TokenType.PLUS,
                        TokenType.MINUS,
                    )
                    return ChannelUnparkCommandNode(selection=selection)
                level, _ = self._parse_intensity_value()
                return ChannelParkCommandNode(selection=selection, level=level)
            return ChannelParkCommandNode(selection=selection, level=None)

        if self._peek_is(TokenType.SNEAK):
            return self._parse_sneak_command(selection=selection)

        if self._peek_is(TokenType.STOP):
            return self._parse_stop_effect_command(selection=selection)

        if self._peek_is(TokenType.EFFECT):
            return self._parse_effect_command(selection=selection)

        if self._peek_is(TokenType.LOCATE):
            self.advance()
            return LocateCommandNode(selection=selection)

        if self._peek_is(TokenType.HOME):
            self.advance()
            cat = None
            if self._peek_is(TokenType.POSITION, TokenType.COLOR, TokenType.BEAM):
                cat = self.advance().raw_text.lower()
            return HomeCommandNode(selection=selection, category=cat)

        if self._peek_is(TokenType.POSITION, TokenType.COLOR, TokenType.BEAM):
            if (
                self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.HOME
            ):
                cat_tok = self.advance()
                self.advance()  # consume HOME
                return HomeCommandNode(
                    selection=selection, category=cat_tok.raw_text.lower()
                )
            if (
                self._probe_expected is not None
                and self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.EOF
                and TokenType.HOME not in self._probe_expected
            ):
                self._probe_expected.append(TokenType.HOME)

        palette_cmd = self._try_parse_apply_palette(selection=selection)
        if palette_cmd is not None:
            return palette_cmd

        if self.match(TokenType.RECORD):
            self.expect(
                TokenType.GROUP, "Expected GROUP after RECORD with channel selection"
            )
            return self._parse_record_group(selection=selection)

        if self.match(TokenType.UPDATE):
            self.expect(
                TokenType.GROUP, "Expected GROUP after UPDATE with channel selection"
            )
            tok_num = self.expect(
                TokenType.NUMBER, "Expected Group number after UPDATE GROUP"
            )
            return UpdateGroupCommandNode(
                group_id=float(tok_num.value), selection=selection
            )

        if (
            len(selection.items) == 1
            and isinstance(selection.items[0], GroupSelectionNode)
            and not selection.exclusions
            and selection.filter_mode == "all"
            and not selection.is_relative
            and self.match(TokenType.LABEL)
        ):
            lbl_tok = self._expect_label_token()
            return LabelGroupCommandNode(
                group_id=selection.items[0].group_id,
                label=str(lbl_tok.value),
            )

        return self._parse_action_clause(selection)

    # --- Palette & Preset Commands ---

    def _parse_palette_spec(self) -> tuple[str, float] | None:
        """Parse `<cat> PALETTE <n>`, `IP|FP|CP|BP <n>`, or `PRESET <n>`."""
        if self._peek_is(*PALETTE_CATEGORY_TOKENS.keys()):
            cat_tok = self.advance()
            category = PALETTE_CATEGORY_TOKENS[cat_tok.type]
            self.expect(
                TokenType.PALETTE,
                f"Expected PALETTE after {cat_tok.raw_text.upper()}",
            )
            num_tok = self.expect(TokenType.NUMBER, "Expected palette number")
            return category, float(num_tok.value)

        if self._peek_is(*PALETTE_SHORTHAND_TOKENS.keys()):
            short_tok = self.advance()
            category = PALETTE_SHORTHAND_TOKENS[short_tok.type]
            num_tok = self.expect(TokenType.NUMBER, "Expected palette number")
            return category, float(num_tok.value)

        if self._peek_is(TokenType.PRESET):
            self.advance()
            num_tok = self.expect(TokenType.NUMBER, "Expected preset number")
            return "preset", float(num_tok.value)

        return None

    def _parse_optional_palette_mode(self) -> str | None:
        """Parse optional BY TYPE, SELECTIVE, or UNIVERSAL modifier."""
        if self.match(TokenType.BY):
            self.expect(TokenType.TYPE, "Expected TYPE after BY")
            return "by_type"
        if self.match(TokenType.SELECTIVE):
            return "selective"
        if self.match(TokenType.UNIVERSAL):
            return "universal"
        return None

    def _try_parse_apply_palette(
        self, selection: SelectionNode | None
    ) -> ApplyPaletteCommandNode | None:
        """Attempt to parse a palette or preset recall without stealing attributes."""
        if self._peek_is(TokenType.PRESET):
            self.advance()
            num_tok = self.expect(TokenType.NUMBER, "Expected preset number")
            return ApplyPaletteCommandNode(
                selection=selection,
                category="preset",
                palette_id=float(num_tok.value),
                absolute=self.match(TokenType.ABSOLUTE),
            )

        if self._peek_is(*PALETTE_SHORTHAND_TOKENS.keys()):
            short_tok = self.advance()
            category = PALETTE_SHORTHAND_TOKENS[short_tok.type]
            num_tok = self.expect(TokenType.NUMBER, "Expected palette number")
            return ApplyPaletteCommandNode(
                selection=selection,
                category=category,
                palette_id=float(num_tok.value),
                absolute=self.match(TokenType.ABSOLUTE),
            )

        if self._peek_is(TokenType.INTENSITY):
            self.advance()
            self.expect(TokenType.PALETTE, "Expected PALETTE after INTENSITY")
            num_tok = self.expect(TokenType.NUMBER, "Expected palette number")
            return ApplyPaletteCommandNode(
                selection=selection,
                category="intensity",
                palette_id=float(num_tok.value),
                absolute=self.match(TokenType.ABSOLUTE),
            )

        if self._peek_is(TokenType.FOCUS, TokenType.COLOR, TokenType.BEAM):
            next_tok = self.peek_ahead(1)
            if next_tok.type == TokenType.PALETTE:
                cat_tok = self.advance()
                self.advance()  # Consume PALETTE
                num_tok = self.expect(TokenType.NUMBER, "Expected palette number")
                return ApplyPaletteCommandNode(
                    selection=selection,
                    category=PALETTE_CATEGORY_TOKENS[cat_tok.type],
                    palette_id=float(num_tok.value),
                    absolute=self.match(TokenType.ABSOLUTE),
                )
            if (
                self._probe_expected is not None
                and next_tok.type == TokenType.EOF
                and TokenType.PALETTE not in self._probe_expected
            ):
                self._probe_expected.append(TokenType.PALETTE)

        return None

    # --- Sneak Commands ---

    def _parse_optional_duration(self) -> float | None:
        """Parse optional TIME <number> or <number> duration."""
        if self.match(TokenType.TIME):
            tok = self.expect(TokenType.NUMBER, "Expected duration number after TIME")
            return float(tok.value)
        if self._peek_is(TokenType.NUMBER):
            tok = self.advance()
            return float(tok.value)
        return None

    def _parse_sneak_command(
        self, selection: SelectionNode | None = None
    ) -> SneakCommandNode:
        self.advance()  # consume SNEAK
        dur: float | None = None
        if selection is None:
            if self._peek_is(TokenType.CHANNEL, TokenType.GROUP):
                selection = self._parse_selection()
                dur = self._parse_optional_duration()
            elif self._peek_is(TokenType.TIME):
                dur = self._parse_optional_duration()
            elif self._peek_is(TokenType.NUMBER):
                next_tok = self.peek_ahead(1)
                if next_tok.type in (TokenType.THRU, TokenType.PLUS, TokenType.MINUS):
                    selection = self._parse_selection()
                    dur = self._parse_optional_duration()
                else:
                    # Isolated number after SNEAK: direct duration (ETC Eos syntax)
                    dur = float(self.advance().value)
                    self._record_expected(
                        TokenType.THRU, TokenType.PLUS, TokenType.MINUS
                    )
        else:
            dur = self._parse_optional_duration()

        return SneakCommandNode(selection=selection, independents=None, duration=dur)

    def _parse_independent_command(self) -> CommandNode:
        self.advance()  # consume INDEPENDENT
        tok = self.peek()
        indes: list[int] = []
        if self._peek_is(TokenType.ALL):
            self.advance()
            indes = list(range(1, 10))
        elif self._peek_is(TokenType.NUMBER):
            num_tok = self.advance()
            indes = [int(num_tok.value)]
            while self.match(TokenType.PLUS):
                next_num = self.expect(
                    TokenType.NUMBER, "Expected independent number after +"
                )
                indes.append(int(next_num.value))
        else:
            raise CommandSyntaxError(
                "Expected independent number (1-9) or ALL after INDEPENDENT",
                tok.position,
                tok,
            )

        if self.match(TokenType.SNEAK):
            dur = self._parse_optional_duration()
            return SneakCommandNode(selection=None, independents=indes, duration=dur)

        peek_tok = self.peek()
        raise CommandSyntaxError(
            "Expected SNEAK after INDEPENDENT", peek_tok.position, peek_tok
        )

    # --- Cue Commands ---

    def _parse_optional_sequence_prefix(self) -> int:
        """Parse optional `SEQ <num>` prefix before a CUE command, defaulting to 1."""
        if self.match(TokenType.SEQUENCE):
            tok_seq = self.expect(
                TokenType.NUMBER, "Expected Sequence number after SEQUENCE"
            )
            return int(float(tok_seq.value))
        return 1

    def _parse_cue_first_command(  # pylint: disable=too-many-return-statements
        self,
    ) -> CommandNode:
        """Parse noun-first cue commands (e.g. [SEQ 2] CUE 5 RECORD TIME 3)."""
        seq_id = self._parse_optional_sequence_prefix()
        self.expect(TokenType.CUE, "Expected CUE after SEQUENCE")
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after CUE")
        cue_id = float(tok_num.value)

        tok_action = self.peek()
        if self.match(TokenType.RECORD):
            return self._parse_record_cue_options(cue_id, sequence_id=seq_id)
        if self.match(TokenType.UPDATE):
            return UpdateCueCommandNode(cue_id=cue_id, sequence_id=seq_id)
        if self.match(TokenType.DELETE):
            return DeleteCueCommandNode(cue_id=cue_id, sequence_id=seq_id)
        if self.match(TokenType.BLOCK):
            return BlockCueCommandNode(cue_id=cue_id, sequence_id=seq_id)
        if self.match(TokenType.UNBLOCK):
            return UnblockCueCommandNode(cue_id=cue_id, sequence_id=seq_id)
        if self.match(TokenType.GOTO):
            fade_time: float | None = None
            if self.match(TokenType.TIME):
                tok_time = self.expect(
                    TokenType.NUMBER, "Expected fade time after TIME"
                )
                fade_time = float(tok_time.value)
            return GotoCueCommandNode(cue_id=cue_id, time=fade_time, sequence_id=seq_id)

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
        self, cue_id: float, sequence_id: int = 1
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
                if self._peek_is(*family_tokens):
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
                if self._peek_is(*family_tokens):
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
            elif self._peek_is(*family_tokens):
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

        self._record_expected(
            TokenType.TIME,
            TokenType.DELAY,
            *family_tokens,
            TokenType.BLOCK,
        )

        return RecordCueCommandNode(
            cue_id=cue_id,
            sequence_id=sequence_id,
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

    def _expect_label_token(self) -> Token:
        """Expect a STRING or IDENT token for an object label."""
        if self._peek_is(TokenType.STRING, TokenType.IDENT):
            return self.advance()
        tok = self.peek()
        raise CommandSyntaxError(
            f"Expected label string after LABEL, got {tok.raw_text!r}",
            tok.position,
            tok,
        )

    def _parse_optional_label(self) -> str | None:
        if self.match(TokenType.LABEL):
            return str(self._expect_label_token().value)
        return None

    def _parse_record_group(
        self, selection: SelectionNode | None = None
    ) -> RecordGroupCommandNode:
        group_id: float | None = None
        if self._peek_is(TokenType.NUMBER):
            group_id = float(self.advance().value)
        label = self._parse_optional_label()
        return RecordGroupCommandNode(
            group_id=group_id, selection=selection, label=label
        )

    def _parse_label_command(self) -> LabelGroupCommandNode:
        self.advance()  # Consume LABEL
        self.expect(TokenType.GROUP, "Expected GROUP after LABEL")
        tok_num = self.expect(
            TokenType.NUMBER, "Expected Group number after LABEL GROUP"
        )
        lbl_tok = self._expect_label_token()
        return LabelGroupCommandNode(
            group_id=float(tok_num.value),
            label=str(lbl_tok.value),
        )

    def _parse_record_cue(
        self,
    ) -> RecordCueCommandNode | RecordPaletteCommandNode | RecordGroupCommandNode:
        self.advance()  # Consume RECORD
        if self.match(TokenType.GROUP):
            return self._parse_record_group(selection=None)

        spec = self._parse_palette_spec()
        if spec is not None:
            mode = self._parse_optional_palette_mode()
            return RecordPaletteCommandNode(
                category=spec[0], palette_id=spec[1], mode=mode
            )

        seq_id = self._parse_optional_sequence_prefix()
        self.match(TokenType.CUE)  # Optional CUE keyword

        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after RECORD")
        cue_id = float(tok_num.value)
        return self._parse_record_cue_options(cue_id, sequence_id=seq_id)

    def _parse_update_cue(
        self,
    ) -> UpdateCueCommandNode | UpdatePaletteCommandNode | UpdateGroupCommandNode:
        self.advance()  # Consume UPDATE
        if self.match(TokenType.GROUP):
            tok_num = self.expect(
                TokenType.NUMBER, "Expected Group number after UPDATE GROUP"
            )
            return UpdateGroupCommandNode(group_id=float(tok_num.value), selection=None)

        spec = self._parse_palette_spec()
        if spec is not None:
            selective = self.match(TokenType.SELECTIVE)
            return UpdatePaletteCommandNode(
                category=spec[0], palette_id=spec[1], selective=selective
            )

        seq_id = self._parse_optional_sequence_prefix()
        self.match(TokenType.CUE)  # Optional CUE keyword

        cue_id: float | None = None
        if self._peek_is(TokenType.NUMBER):
            cue_id = float(self.advance().value)

        return UpdateCueCommandNode(cue_id=cue_id, sequence_id=seq_id)

    def _parse_goto_cue(self) -> GotoCueCommandNode:
        self.advance()  # Consume GOTO
        seq_id = self._parse_optional_sequence_prefix()
        self.match(TokenType.CUE)  # Optional CUE keyword

        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after GOTO")
        cue_id = float(tok_num.value)

        fade_time: float | None = None
        if self.match(TokenType.TIME):
            tok_time = self.expect(TokenType.NUMBER, "Expected fade time after TIME")
            fade_time = float(tok_time.value)

        return GotoCueCommandNode(cue_id=cue_id, time=fade_time, sequence_id=seq_id)

    def _parse_block_cue(self) -> BlockCueCommandNode:
        self.advance()  # Consume BLOCK
        seq_id = self._parse_optional_sequence_prefix()
        self.match(TokenType.CUE)  # Optional CUE keyword
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after BLOCK")
        return BlockCueCommandNode(cue_id=float(tok_num.value), sequence_id=seq_id)

    def _parse_unblock_cue(self) -> UnblockCueCommandNode:
        self.advance()  # Consume UNBLOCK
        seq_id = self._parse_optional_sequence_prefix()
        self.match(TokenType.CUE)  # Optional CUE keyword
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after UNBLOCK")
        return UnblockCueCommandNode(cue_id=float(tok_num.value), sequence_id=seq_id)

    def _parse_delete_cue(
        self,
    ) -> (
        DeleteCueCommandNode
        | DeletePaletteCommandNode
        | DeleteEffectCommandNode
        | DeleteGroupCommandNode
    ):
        self.advance()  # Consume DELETE
        if self.match(TokenType.GROUP):
            tok_grp = self.expect(
                TokenType.NUMBER, "Expected Group number after DELETE GROUP"
            )
            return DeleteGroupCommandNode(group_id=float(tok_grp.value))

        if self.match(TokenType.EFFECT):
            tok_fx = self.expect(
                TokenType.NUMBER, "Expected Effect number after DELETE EFFECT"
            )
            return DeleteEffectCommandNode(effect_id=float(tok_fx.value))

        spec = self._parse_palette_spec()
        if spec is not None:
            return DeletePaletteCommandNode(category=spec[0], palette_id=spec[1])

        seq_id = self._parse_optional_sequence_prefix()
        self.match(TokenType.CUE)  # Optional CUE keyword
        tok_num = self.expect(TokenType.NUMBER, "Expected Cue number after DELETE")
        return DeleteCueCommandNode(cue_id=float(tok_num.value), sequence_id=seq_id)

    # --- Effect Commands ---

    def _parse_stop_effect_command(
        self, selection: SelectionNode | None = None
    ) -> StopEffectCommandNode:
        """Parse `[<selection>] STOP [EFFECT [<num>]]`."""
        self.advance()  # Consume STOP / STOMP
        self.match(TokenType.EFFECT)  # Optional EFFECT after STOP / STOMP
        effect_id: float | None = None
        if self._peek_is(TokenType.NUMBER):
            effect_id = float(self.advance().value)
        return StopEffectCommandNode(selection=selection, effect_id=effect_id)

    def _parse_effect_command(  # pylint: disable=too-many-branches
        self, selection: SelectionNode | None = None
    ) -> ApplyEffectCommandNode | StopEffectCommandNode | EditEffectCommandNode:
        """Parse `[<selection>] EFFECT [<num>] [RATE <r>] [SIZE <s>] ...`."""
        self.advance()  # Consume EFFECT / FX

        # Eos stomp syntax: `<selection> EFFECT` or `<selection> EFFECT AT`
        if self.peek().type == TokenType.EOF:
            self._record_expected(TokenType.NUMBER, TokenType.AT)
            if selection is not None:
                return StopEffectCommandNode(selection=selection, effect_id=None)
            tok = self.peek()
            raise CommandSyntaxError(
                "Expected effect number after EFFECT", tok.position, tok
            )

        if self.match(TokenType.AT):
            if self.peek().type == TokenType.EOF:
                self._record_expected(TokenType.NUMBER)
                if selection is not None:
                    return StopEffectCommandNode(selection=selection, effect_id=None)
                tok = self.peek()
                raise CommandSyntaxError(
                    "Expected effect number after EFFECT AT", tok.position, tok
                )

        tok_num = self.expect(TokenType.NUMBER, "Expected effect number after EFFECT")
        effect_id = float(tok_num.value)

        rate: float | None = None
        size: float | None = None
        groups: int | None = None
        blocks: int | None = None
        wings: int | None = None
        label: str | None = None

        while self.peek().type != TokenType.EOF:
            if self.match(TokenType.RATE):
                tok_r = self.expect(TokenType.NUMBER, "Expected number after RATE")
                rate = float(tok_r.value)
            elif self.match(TokenType.SIZE):
                tok_s = self.expect(TokenType.NUMBER, "Expected number after SIZE")
                size = float(tok_s.value)
            elif self.match(TokenType.GROUPS):
                tok_g = self.expect(TokenType.NUMBER, "Expected integer after GROUPS")
                groups = int(tok_g.value)
            elif self.match(TokenType.BLOCKS):
                tok_b = self.expect(TokenType.NUMBER, "Expected integer after BLOCKS")
                blocks = int(tok_b.value)
            elif self.match(TokenType.WINGS):
                tok_w = self.expect(TokenType.NUMBER, "Expected integer after WINGS")
                wings = int(tok_w.value)
            elif self.match(TokenType.LABEL):
                if self._peek_is(TokenType.STRING, TokenType.IDENT):
                    label = str(self.advance().value)
                else:
                    tok = self.peek()
                    raise CommandSyntaxError(
                        f"Expected label string after LABEL, got {tok.raw_text!r}",
                        tok.position,
                        tok,
                    )
            elif selection is None and self._peek_is(TokenType.STRING):
                label = str(self.advance().value)
            else:
                break

        self._record_expected(
            TokenType.RATE,
            TokenType.SIZE,
            TokenType.GROUPS,
            TokenType.BLOCKS,
            TokenType.WINGS,
            TokenType.LABEL,
        )

        has_modifiers = any(
            v is not None for v in (rate, size, groups, blocks, wings, label)
        )
        if selection is None and (label is not None or has_modifiers):
            return EditEffectCommandNode(
                effect_id=effect_id,
                rate=rate,
                size=size,
                groups=groups,
                blocks=blocks,
                wings=wings,
                label=label,
            )

        return ApplyEffectCommandNode(
            selection=selection,
            effect_id=effect_id,
            rate=rate,
            size=size,
            groups=groups,
            blocks=blocks,
            wings=wings,
        )

    # --- Address Selection Parsing ---

    def _parse_address_item(self) -> AddressItemNode:
        """Parse a single address or address range: 12, 1/12, 1/1 THRU 10."""
        self.match(TokenType.ADDRESS)

        first_num_tok = self.expect(
            TokenType.NUMBER, "Expected address or universe number"
        )
        first_val = int(first_num_tok.value)

        universe = 1
        output = first_val
        if self.match(TokenType.SLASH):
            second_num_tok = self.expect(
                TokenType.NUMBER, "Expected output address after '/'"
            )
            universe = first_val
            output = int(second_num_tok.value)

        if self.match(TokenType.THRU):
            end_first_tok = self.expect(
                TokenType.NUMBER, "Expected target address after THRU"
            )
            end_val = int(end_first_tok.value)
            if self.match(TokenType.SLASH):
                end_second_tok = self.expect(
                    TokenType.NUMBER, "Expected target address after '/'"
                )
                end_output = int(end_second_tok.value)
            else:
                end_output = end_val
            return AddressRangeNode(universe=universe, start=output, end=end_output)

        return AddressNumberNode(universe=universe, output=output)

    def _parse_address_selection(
        self, *, require_address_kw: bool = True
    ) -> AddressSelectionNode:
        items: list[AddressItemNode] = []
        exclusions: list[AddressItemNode] = []

        if require_address_kw:
            self.expect(TokenType.ADDRESS, "Expected ADDRESS")
        else:
            self.match(TokenType.ADDRESS)
        items.append(self._parse_address_item())

        while True:
            if self.match(TokenType.PLUS):
                items.append(self._parse_address_item())
            elif self.match(TokenType.MINUS):
                exclusions.append(self._parse_address_item())
            else:
                break

        return AddressSelectionNode(items=items, exclusions=exclusions)

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

    def _parse_relative_selection(self) -> SelectionNode:
        """Parse a selection that starts relatively with +, -, or THRU."""
        items: list[SelectionItemNode] = []
        exclusions: list[SelectionItemNode] = []

        if self.match(TokenType.PLUS):
            items.append(self._parse_selection_item())
        elif self.match(TokenType.MINUS):
            exclusions.append(self._parse_selection_item())
        elif self.match(TokenType.THRU):
            end_tok = self.expect(
                TokenType.NUMBER, "Expected target channel number after THRU"
            )
            items.append(RelativeThruNode(end=int(end_tok.value)))

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
            is_relative=True,
        )

    def _parse_relative_filter_selection(self) -> SelectionNode:
        """Parse an odd/even filter applying directly to current selection."""
        tok = self.advance()
        filter_mode: typing.Literal["all", "odd", "even"] = (
            "odd" if tok.type == TokenType.ODD else "even"
        )
        return SelectionNode(
            items=[],
            exclusions=[],
            filter_mode=filter_mode,
            is_relative=True,
        )

    def _parse_selection_item(self) -> SelectionItemNode:
        # Optional CHANNEL / CHAN prefix (e.g. CHANNEL 1, CHAN 1 THRU 10)
        self.match(TokenType.CHANNEL)

        if self._peek_is(TokenType.ALL):
            self.advance()
            return AllSelectionNode()

        if self._peek_is(TokenType.GROUP):
            self.advance()
            num_tok = self.expect(TokenType.NUMBER, "Expected group number after GROUP")
            return GroupSelectionNode(group_id=float(num_tok.value))

        if self._peek_is(TokenType.NUMBER):
            start_val = int(self.advance().value)
            if self.match(TokenType.THRU):
                end_tok = self.expect(
                    TokenType.NUMBER, "Expected target channel number after THRU"
                )
                end_val = int(end_tok.value)
                return ChannelRangeNode(start=start_val, end=end_val)
            return ChannelNumberNode(channel=start_val)

        tok = self.peek()
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

        self._record_expected(TokenType.AT, *ATTRIBUTE_TOKENS.keys())

        # Allow '<selection> AT <level> CHECK'
        if (
            selection is not None
            and intensity_level is not None
            and self.match(TokenType.CHECK)
        ):
            return ChannelCheckCommandNode(selection=selection, level=intensity_level)

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
        if self._peek_is(TokenType.FULL):
            self.advance()
            return (100.0, False)

        if self._peek_is(TokenType.OUT):
            self.advance()
            return (0.0, False)

        if self._peek_is(TokenType.PLUS):
            self.advance()
            num_tok = self.expect(
                TokenType.NUMBER, "Expected number after '+' for relative intensity"
            )
            return (float(num_tok.value), True)

        if self._peek_is(TokenType.MINUS):
            self.advance()
            num_tok = self.expect(
                TokenType.NUMBER, "Expected number after '-' for relative intensity"
            )
            return (-float(num_tok.value), True)

        if self._peek_is(TokenType.NUMBER):
            tok = self.advance()
            val = float(tok.value)
            if not 0.0 <= val <= 100.0:
                raise CommandSyntaxError(
                    f"Intensity level must be between 0 and 100, got {val}",
                    tok.position,
                    tok,
                )
            return (val, False)

        tok = self.peek()
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
        # Handle color values (#FF8800, "RED", or identifier RED)
        if attr_type == TokenType.COLOR:
            if self._peek_is(TokenType.HEX_COLOR, TokenType.STRING, TokenType.IDENT):
                return self.advance().value
            tok = self.peek()
            raise CommandSyntaxError(
                f"Expected color hex code or name, got {tok.raw_text!r}",
                tok.position,
                tok,
            )

        # Handle signed numerical angles/values (PAN -45, TILT +30, ZOOM 25)
        sign = 1.0
        if self._peek_is(TokenType.MINUS):
            sign = -1.0
            self.advance()
        elif self._peek_is(TokenType.PLUS):
            self.advance()

        if self._peek_is(TokenType.NUMBER):
            return sign * float(self.advance().value)

        # String or ident for gobos/wheels (e.g. GOBO "Open", GOBO 2)
        if self._peek_is(TokenType.STRING, TokenType.IDENT):
            return self.advance().value

        tok = self.peek()
        raise CommandSyntaxError(
            f"Expected value for attribute {attr_type.name}, got {tok.raw_text!r}",
            tok.position,
            tok,
        )

    def get_expected_tokens(self, text: str) -> list[TokenType]:
        """Inspect a partial command string and return expected token types next.

        Probes the recursive-descent parser at EOF so valid continuations stay in
        sync with the grammar automatically.
        """
        trimmed = text.strip()
        try:
            tokens = self.lexer.tokenize(trimmed)
        except LexerError:
            return []

        if not tokens or tokens[-1].type != TokenType.EOF:
            return []

        active_tokens = tokens[:-1]
        self.tokens = tokens
        self.pos = 0
        self._probe_expected = []
        try:
            self._parse_command()
        except CommandSyntaxError:
            pass
        finally:
            expected = list(self._probe_expected or [])
            self._probe_expected = None

        if (
            active_tokens
            and active_tokens[-1].type == TokenType.NUMBER
            and not text.endswith(" ")
            and TokenType.NUMBER not in expected
        ):
            expected.append(TokenType.NUMBER)

        return expected
