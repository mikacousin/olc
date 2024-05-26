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
from olc.command.ast import (ChanNumber, Level, LevelOp, NoneNode, SelAddOp, SelMinusOp,
                             SelOp, SelStart, TreeNode)
from olc.command.lexer import TokenType
from olc.command.parser import Parser


class ParserDirect(Parser):
    """Grammar:

    command = selection ( level ) EOF
    selection = SEL_CHAN EOF | SEL_CHAN CHAN_NUMBER ( selec_add | selec_minus
                                                      | THRU CHAN_NUMBER)*
    selec_add = PLUS EOF | PLUS CHAN_NUMBER ( THRU CHAN_NUMBER )
    selec_minus = MINUS EOF | MINUS CHAN_NUMBER ( THRU CHAN_NUMBER )
    level = AT EOF | AT LEVEL ( THRU LEVEL )
    """

    def parse_command(self) -> TreeNode:
        """Parses command line

        Returns:
            Nodes
        """
        selection = self._selection()
        if self.peek() == TokenType.AT:
            level = self._level(selection)
            return level
        return selection

    def _selection(self) -> SelOp:
        try:
            self.eat(TokenType.SEL_CHAN)
        except SyntaxError as error:
            raise SyntaxError(f"Start with Chan, not {error}") from error

        channel = self._get_chan_number()
        result = SelStart(channel)

        while (next_token_type :=
               self.peek()) in {TokenType.PLUS, TokenType.MINUS, TokenType.THRU}:
            if next_token_type == TokenType.PLUS:
                result = self._selec_add(result)
            elif next_token_type == TokenType.MINUS:
                result = self._selec_minus(result)
            else:
                self.eat(TokenType.THRU)
                to_channel = self._get_chan_number()
                result = SelAddOp("thru", result, channel, to_channel)

        return result

    def _selec_add(self, result) -> SelAddOp:
        self.eat(TokenType.PLUS)
        channel = self._get_chan_number()
        if self.peek() == TokenType.THRU:
            self.eat(TokenType.THRU)
            to_channel = self._get_chan_number()
            return SelAddOp("thru", result, channel, to_channel)
        return SelAddOp("+", result, channel)

    def _selec_minus(self, result) -> SelMinusOp:
        self.eat(TokenType.MINUS)
        channel = self._get_chan_number()
        if self.peek() == TokenType.THRU:
            self.eat(TokenType.THRU)
            to_channel = self._get_chan_number()
            return SelMinusOp("thru", result, channel, to_channel)
        return SelMinusOp("-", result, channel)

    def _level(self, selection) -> LevelOp:
        op = "at"
        self.eat(TokenType.AT)
        level = self._get_level()
        if self.peek() == TokenType.THRU:
            self.eat(TokenType.THRU)
            to_level = self._get_level()
            return LevelOp(selection, "thru", level, to_level)
        return LevelOp(selection, op, level, None)

    def _get_chan_number(self) -> ChanNumber | NoneNode:
        if self.peek() == TokenType.EOF:
            return NoneNode()
        try:
            channel = ChanNumber(self.eat(TokenType.INT).value)
            return channel
        except SyntaxError as error:
            raise SyntaxError(f"Need channel number not {error}") from error

    def _get_level(self) -> Level | NoneNode:
        if self.peek() == TokenType.EOF:
            return NoneNode()
        try:
            level = Level(self.eat(TokenType.INT).value)
            return level
        except SyntaxError as error:
            raise SyntaxError(f"Enter Level not {error}") from error
