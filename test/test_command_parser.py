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
"""Unit tests for CommandParser."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import pytest

from olc.core.parser.ast_nodes import (
    AttributeCommandNode,
    BlockCueCommandNode,
    ChannelNumberNode,
    ChannelRangeNode,
    DeleteCueCommandNode,
    GotoCueCommandNode,
    GroupSelectionNode,
    IntensityCommandNode,
    RecordCueCommandNode,
    SelectOnlyCommandNode,
    UnblockCueCommandNode,
    UpdateCueCommandNode,
)
from olc.core.parser.parser import CommandParser, CommandSyntaxError
from olc.core.parser.tokens import TokenType


def test_parser_select_only() -> None:
    parser = CommandParser()
    node = parser.parse("1 THRU 10")
    assert isinstance(node, SelectOnlyCommandNode)
    assert len(node.selection.items) == 1
    assert isinstance(node.selection.items[0], ChannelRangeNode)
    assert node.selection.items[0].start == 1
    assert node.selection.items[0].end == 10
    assert node.selection.filter_mode == "all"


def test_parser_complex_selection() -> None:
    parser = CommandParser()
    node = parser.parse("1 + 3 THRU 5 + GROUP 2 - 4 ODD")
    assert isinstance(node, SelectOnlyCommandNode)
    items = node.selection.items
    assert len(items) == 3
    assert isinstance(items[0], ChannelNumberNode) and items[0].channel == 1
    assert (
        isinstance(items[1], ChannelRangeNode)
        and items[1].start == 3
        and items[1].end == 5
    )
    assert isinstance(items[2], GroupSelectionNode) and items[2].group_id == 2
    exclusions = node.selection.exclusions
    assert len(exclusions) == 1
    assert isinstance(exclusions[0], ChannelNumberNode) and exclusions[0].channel == 4
    assert node.selection.filter_mode == "odd"


def test_parser_intensity_command() -> None:
    parser = CommandParser()

    # Absolute percentage
    node1 = parser.parse("1 THRU 5 AT 80")
    assert isinstance(node1, IntensityCommandNode)
    assert node1.level == 80.0
    assert not node1.is_relative

    # Shortcut FULL
    node2 = parser.parse("1 AT FULL")
    assert isinstance(node2, IntensityCommandNode)
    assert node2.level == 100.0

    # Shortcut OUT
    node3 = parser.parse("1 AT OUT")
    assert isinstance(node3, IntensityCommandNode)
    assert node3.level == 0.0

    # Implicit selection (active channels)
    node4 = parser.parse("AT 50")
    assert isinstance(node4, IntensityCommandNode)
    assert node4.selection is None
    assert node4.level == 50.0

    # Relative intensity + / -
    node5 = parser.parse("1 AT + 10")
    assert isinstance(node5, IntensityCommandNode)
    assert node5.level == 10.0
    assert node5.is_relative

    node6 = parser.parse("1 AT - 15")
    assert isinstance(node6, IntensityCommandNode)
    assert node6.level == -15.0
    assert node6.is_relative


def test_parser_attributes_command() -> None:
    parser = CommandParser()

    node = parser.parse("1 PAN 45 TILT -30 COLOR #FF8800 ZOOM 20")
    assert isinstance(node, AttributeCommandNode)
    assert node.attributes["pan"] == 45.0
    assert node.attributes["tilt"] == -30.0
    assert node.attributes["color"] == "#FF8800"
    assert node.attributes["zoom"] == 20.0
    assert node.intensity_level is None


def test_parser_combined_intensity_and_attributes() -> None:
    parser = CommandParser()

    node = parser.parse("1 THRU 6 AT 80 PAN 90 TILT -15 COLOR RED")
    assert isinstance(node, AttributeCommandNode)
    assert node.intensity_level == 80.0
    assert node.attributes["pan"] == 90.0
    assert node.attributes["tilt"] == -15.0
    assert node.attributes["color"] == "RED"


def test_parser_cue_commands() -> None:
    parser = CommandParser()

    # Record Cue
    node1 = parser.parse("RECORD CUE 5 TIME 3 / 2 DELAY 1 BLOCK")
    assert isinstance(node1, RecordCueCommandNode)
    assert node1.cue_id == 5.0
    assert node1.time_in == 3.0
    assert node1.time_out == 2.0
    assert node1.delay == 1.0
    assert node1.is_block is True

    # Record Cue without CUE keyword
    node1b = parser.parse("RECORD 2.5 TIME 4")
    assert isinstance(node1b, RecordCueCommandNode)
    assert node1b.cue_id == 2.5
    assert node1b.time_in == 4.0
    assert node1b.time_out == 4.0

    # Update Cue
    node2 = parser.parse("UPDATE CUE 4")
    assert isinstance(node2, UpdateCueCommandNode)
    assert node2.cue_id == 4.0

    node2b = parser.parse("UPDATE")
    assert isinstance(node2b, UpdateCueCommandNode)
    assert node2b.cue_id is None

    # Goto Cue
    node3 = parser.parse("GOTO CUE 12 TIME 0")
    assert isinstance(node3, GotoCueCommandNode)
    assert node3.cue_id == 12.0
    assert node3.time == 0.0

    # Block / Unblock / Delete
    node4 = parser.parse("BLOCK CUE 8")
    assert isinstance(node4, BlockCueCommandNode)
    assert node4.cue_id == 8.0

    node5 = parser.parse("UNBLOCK CUE 8")
    assert isinstance(node5, UnblockCueCommandNode)
    assert node5.cue_id == 8.0

    node6 = parser.parse("DELETE CUE 4")
    assert isinstance(node6, DeleteCueCommandNode)
    assert node6.cue_id == 4.0


def test_parser_syntax_errors() -> None:
    parser = CommandParser()

    # Empty
    with pytest.raises(CommandSyntaxError):
        parser.parse("")

    # Trailing THRU without target
    with pytest.raises(CommandSyntaxError):
        parser.parse("1 THRU")

    # Intensity > 100
    with pytest.raises(CommandSyntaxError):
        parser.parse("1 AT 150")

    # Unexpected token after command
    with pytest.raises(CommandSyntaxError):
        parser.parse("1 AT 80 EXTRA_GARBAGE")


def test_parser_expected_tokens() -> None:
    parser = CommandParser()

    # Start of line
    expected_start = parser.get_expected_tokens("")
    assert TokenType.NUMBER in expected_start
    assert TokenType.RECORD in expected_start

    # After channel number (without space: can type more digits, ex 1 -> 12)
    expected_num = parser.get_expected_tokens("1")
    assert TokenType.NUMBER in expected_num
    assert TokenType.THRU in expected_num
    assert TokenType.AT in expected_num
    assert TokenType.PLUS in expected_num

    # After AT
    expected_at = parser.get_expected_tokens("1 AT")
    assert TokenType.NUMBER in expected_at
    assert TokenType.FULL in expected_at
    assert TokenType.OUT in expected_at

    # After GOTO CUE
    expected_goto_cue = parser.get_expected_tokens("GOTO CUE")
    assert TokenType.NUMBER in expected_goto_cue

    # After RECORD CUE
    expected_rec_cue = parser.get_expected_tokens("RECORD CUE")
    assert TokenType.NUMBER in expected_rec_cue
