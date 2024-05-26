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
from typing import Any

from olc.command.ast import LevelOp, SelAddOp, SelMinusOp, SelOp, SelStart, TreeNode
from olc.command.lexer import Token, TokenType


class Parser:
    """Parse and interpret nodes

    This class must be subclassed and parse_statement implemented
    """

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.next_token_index: int = 0

    def eat(self, expected_token_type: TokenType) -> Token:
        """Returns the next token if it is of the expected type.

        Args:
            expected_token_type: Expected Token Type

        Returns:
            token

        Raises:
            SyntaxError: if the next token is not of the expected type

        """
        next_token = self.tokens[self.next_token_index]
        self.next_token_index += 1
        if next_token.type != expected_token_type:
            raise SyntaxError(next_token.type.title())
        return next_token

    def peek(self, skip: int = 0) -> TokenType | None:
        """Checks the type of an upcoming token without consuming it.

        Args:
            skip: tokens to skip

        Returns:
            Token type
        """
        peek_at = self.next_token_index + skip
        return self.tokens[peek_at].type if peek_at < len(self.tokens) else None

    def parse(self) -> list[TreeNode]:
        """Parses nodes tree

        Returns:
            Nodes list
        """
        command = []
        while self.peek() != TokenType.EOF:
            command.append(self.parse_command())
        self.eat(TokenType.EOF)
        return command

    def interpret(self, tree: list[TreeNode], context: Any) -> None:
        """Interprets nodes tree

        Args:
            tree: nodes
            context: Active widget
        """
        for node in tree:
            if type(node) in {SelStart, SelOp, SelAddOp, SelMinusOp, LevelOp}:
                node.eval(context)
            else:
                node.eval()

    def interpret_selec(self, tree: list[TreeNode], context: Any) -> None:
        """Interpret selection part

        Args:
            tree: nodes
            context: Active widget
        """
        for node in tree:
            if isinstance(node, SelOp):
                node.eval(context)

    def get_selection(self, tree) -> str:
        """Get selection string from first node

        Args:
            tree: nodes

        Returns:
            Selection string
        """
        selection = ""
        for node in tree:
            selection = node.get_selection()
        return selection

    def parse_command(self) -> TreeNode:
        """Parses statement

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError
