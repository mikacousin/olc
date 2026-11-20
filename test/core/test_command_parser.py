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
    ApplyPaletteCommandNode,
    AttributeCommandNode,
    BlockCueCommandNode,
    ChannelNumberNode,
    ChannelRangeNode,
    DeleteCueCommandNode,
    DeletePaletteCommandNode,
    GotoCueCommandNode,
    GroupSelectionNode,
    HomeCommandNode,
    IntensityCommandNode,
    LocateCommandNode,
    RecordCueCommandNode,
    RecordPaletteCommandNode,
    RelativeThruNode,
    SelectOnlyCommandNode,
    SneakCommandNode,
    UnblockCueCommandNode,
    UpdateCueCommandNode,
    UpdatePaletteCommandNode,
)
from olc.core.parser.highlighter import highlight_commandline_markup
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


def test_parser_channel_keyword_syntax() -> None:
    """Test explicit CHANNEL and CHAN keywords for selection."""
    parser = CommandParser()

    # CHANNEL single channel
    node1 = parser.parse("CHANNEL 5")
    assert isinstance(node1, SelectOnlyCommandNode)
    assert len(node1.selection.items) == 1
    assert isinstance(node1.selection.items[0], ChannelNumberNode)
    assert node1.selection.items[0].channel == 5

    # CHANNEL with range and AT FULL
    node2 = parser.parse("CHANNEL 1 THRU 10 AT FULL")
    assert isinstance(node2, IntensityCommandNode)
    assert node2.level == 100.0
    assert node2.selection is not None
    assert len(node2.selection.items) == 1
    assert isinstance(node2.selection.items[0], ChannelRangeNode)
    assert node2.selection.items[0].start == 1
    assert node2.selection.items[0].end == 10

    # CHAN abbreviation with AT OUT
    node3 = parser.parse("CHAN 2 AT OUT")
    assert isinstance(node3, IntensityCommandNode)
    assert node3.level == 0.0
    assert node3.selection is not None
    assert len(node3.selection.items) == 1
    assert isinstance(node3.selection.items[0], ChannelNumberNode)
    assert node3.selection.items[0].channel == 2

    # Multiple channels with CHANNEL keyword
    node4 = parser.parse("CHANNEL 1 + CHANNEL 3 THRU 5")
    assert isinstance(node4, SelectOnlyCommandNode)
    assert len(node4.selection.items) == 2


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


def test_highlight_commandline_markup() -> None:
    # 1. Empty string
    assert highlight_commandline_markup("") == ""

    # 2. Basic command: 1 THRU 10 AT 80
    markup = highlight_commandline_markup("1 THRU 10 AT 80")
    assert '<span foreground="#4FC3F7">1</span>' in markup
    assert '<span foreground="#FFB74D">THRU</span>' in markup
    assert '<span foreground="#4FC3F7">10</span>' in markup
    assert '<span foreground="#F06292" weight="bold">AT</span>' in markup
    assert '<span foreground="#4FC3F7">80</span>' in markup

    # 3. Attribute command with hex color and pan/tilt: 1 PAN 45 COLOR #FF8800
    markup_attr = highlight_commandline_markup("1 PAN 45 COLOR #FF8800")
    assert '<span foreground="#69F0AE" weight="bold">PAN</span>' in markup_attr
    assert '<span foreground="#69F0AE" weight="bold">COLOR</span>' in markup_attr
    assert '<span foreground="#FF8800" weight="bold">#FF8800</span>' in markup_attr

    # 4. Named color: COLOR RED
    markup_red = highlight_commandline_markup("COLOR RED")
    assert '<span foreground="#FF0000" weight="bold">RED</span>' in markup_red

    # 5. HTML escaping: safety against <, >, &
    markup_esc = highlight_commandline_markup('1 < 2 & "foo"')
    assert "&lt;" in markup_esc
    assert "&amp;" in markup_esc
    assert "< 2" not in markup_esc

    # 6. Mismatch characters: underline error
    markup_err = highlight_commandline_markup("1 $ 2")
    assert '<span foreground="#FF5252" underline="error">$</span>' in markup_err


def test_parser_noun_first_cue_commands() -> None:
    parser = CommandParser()

    rec = parser.parse("CUE 5 RECORD TIME 3 / 2 DELAY 1 BLOCK")
    assert isinstance(rec, RecordCueCommandNode)
    assert rec.cue_id == 5.0
    assert rec.time_in == 3.0
    assert rec.time_out == 2.0
    assert rec.delay == 1.0
    assert rec.is_block is True

    upd = parser.parse("CUE 4 UPDATE")
    assert isinstance(upd, UpdateCueCommandNode)
    assert upd.cue_id == 4.0

    dele = parser.parse("CUE 4 DELETE")
    assert isinstance(dele, DeleteCueCommandNode)
    assert dele.cue_id == 4.0

    blk = parser.parse("CUE 8 BLOCK")
    assert isinstance(blk, BlockCueCommandNode)
    assert blk.cue_id == 8.0

    unblk = parser.parse("CUE 8 UNBLOCK")
    assert isinstance(unblk, UnblockCueCommandNode)
    assert unblk.cue_id == 8.0

    goto = parser.parse("CUE 12 GOTO TIME 0")
    assert isinstance(goto, GotoCueCommandNode)
    assert goto.cue_id == 12.0
    assert goto.time == 0.0


def test_parser_record_cue_ifcb_times() -> None:
    parser = CommandParser()

    node1 = parser.parse(
        "RECORD CUE 5 TIME 3 POSITION 1.5 DELAY 0.5 COLOR 4 BEAM DELAY 1 TIME 2"
    )
    assert isinstance(node1, RecordCueCommandNode)
    assert node1.cue_id == 5.0
    assert node1.time_in == 3.0
    assert node1.time_position == 1.5
    assert node1.delay_position == 0.5
    assert node1.time_color == 4.0
    assert node1.delay_color is None
    assert node1.time_beam == 2.0
    assert node1.delay_beam == 1.0

    node2 = parser.parse("CUE 6 RECORD TIME POSITION 2.5 DELAY COLOR 1.0")
    assert isinstance(node2, RecordCueCommandNode)
    assert node2.cue_id == 6.0
    assert node2.time_position == 2.5
    assert node2.delay_color == 1.0

    expected_after_cue_num = parser.get_expected_tokens("CUE 5 ")
    assert TokenType.RECORD in expected_after_cue_num
    assert TokenType.UPDATE in expected_after_cue_num
    assert TokenType.DELETE in expected_after_cue_num
    assert TokenType.GOTO in expected_after_cue_num

    expected_after_rec = parser.get_expected_tokens("CUE 5 RECORD ")
    assert TokenType.TIME in expected_after_rec
    assert TokenType.POSITION in expected_after_rec
    assert TokenType.COLOR in expected_after_rec
    assert TokenType.BEAM in expected_after_rec


def test_parser_home_and_locate() -> None:
    parser = CommandParser()

    # 1. Standalone HOME / LOCATE
    n1 = parser.parse("HOME")
    assert isinstance(n1, HomeCommandNode)
    assert n1.selection is None
    assert n1.category is None

    n2 = parser.parse("LOCATE")
    assert isinstance(n2, LocateCommandNode)
    assert n2.selection is None

    # 2. Selection + HOME / LOCATE
    n3 = parser.parse("1 HOME")
    assert isinstance(n3, HomeCommandNode)
    assert n3.selection is not None
    assert n3.category is None

    n4 = parser.parse("1 THRU 5 LOCATE")
    assert isinstance(n4, LocateCommandNode)
    assert n4.selection is not None

    # 3. Category filtering (POSITION HOME, COLOR HOME, HOME BEAM)
    n5 = parser.parse("1 POSITION HOME")
    assert isinstance(n5, HomeCommandNode)
    assert n5.category == "position"

    n6 = parser.parse("HOME COLOR")
    assert isinstance(n6, HomeCommandNode)
    assert n6.category == "color"


def test_parser_sneak() -> None:
    parser = CommandParser()

    # 1. Standalone SNEAK
    n1 = parser.parse("SNEAK")
    assert isinstance(n1, SneakCommandNode)
    assert n1.selection is None
    assert n1.independents is None
    assert n1.duration is None

    # 2. SNEAK with duration
    n2 = parser.parse("SNEAK TIME 3.5")
    assert isinstance(n2, SneakCommandNode)
    assert n2.selection is None
    assert n2.duration == 3.5

    # 3. Noun-first selection SNEAK
    n3 = parser.parse("1 THRU 5 SNEAK")
    assert isinstance(n3, SneakCommandNode)
    assert n3.selection is not None
    assert n3.duration is None

    # 4. Verb-first SNEAK selection
    n4 = parser.parse("SNEAK 1 THRU 5")
    assert isinstance(n4, SneakCommandNode)
    assert n4.selection is not None
    assert n4.duration is None

    # 5. Selection + SNEAK + TIME
    n5 = parser.parse("1 + 3 SNEAK TIME 2")
    assert isinstance(n5, SneakCommandNode)
    assert n5.selection is not None
    assert n5.duration == 2.0

    # 6. Standalone SNEAK with direct duration (Eos convention)
    n6 = parser.parse("SNEAK 3")
    assert isinstance(n6, SneakCommandNode)
    assert n6.selection is None
    assert n6.duration == 3.0

    n6_zero = parser.parse("SNEAK 0")
    assert isinstance(n6_zero, SneakCommandNode)
    assert n6_zero.selection is None
    assert n6_zero.duration == 0.0

    # 7. Selection + SNEAK + direct duration
    n7 = parser.parse("1 THRU 5 SNEAK 3")
    assert isinstance(n7, SneakCommandNode)
    assert n7.selection is not None
    assert n7.duration == 3.0

    n8 = parser.parse("1 SNEAK 0")
    assert isinstance(n8, SneakCommandNode)
    assert n8.selection is not None
    assert n8.duration == 0.0

    # Expected tokens checks
    assert TokenType.NUMBER in parser.get_expected_tokens("SNEAK ")
    assert TokenType.TIME in parser.get_expected_tokens("SNEAK ")
    assert TokenType.NUMBER in parser.get_expected_tokens("1 THRU 5 SNEAK ")
    assert TokenType.TIME in parser.get_expected_tokens("1 THRU 5 SNEAK ")


def test_parser_independent_sneak() -> None:
    parser = CommandParser()

    # 1. INDEPENDENT 1 SNEAK
    n1 = parser.parse("INDEPENDENT 1 SNEAK")
    assert isinstance(n1, SneakCommandNode)
    assert n1.independents == [1]
    assert n1.duration is None

    # 2. INDEPENDENT 1 + 2 SNEAK TIME 4
    n2 = parser.parse("INDEPENDENT 1 + 2 SNEAK TIME 4")
    assert isinstance(n2, SneakCommandNode)
    assert n2.independents == [1, 2]
    assert n2.duration == 4.0

    # 3. INDE abbreviation
    n3 = parser.parse("INDE 3 SNEAK")
    assert isinstance(n3, SneakCommandNode)
    assert n3.independents == [3]


def test_parser_relative_selection() -> None:
    """Test relative selection with +, -, THRU and direct ODD/EVEN filters."""
    parser = CommandParser()

    # 1. Plus relative selection
    cmd1 = parser.parse("+ 5")
    assert isinstance(cmd1, SelectOnlyCommandNode)
    assert cmd1.selection.is_relative is True
    assert len(cmd1.selection.items) == 1
    assert isinstance(cmd1.selection.items[0], ChannelNumberNode)
    assert cmd1.selection.items[0].channel == 5

    # 2. Minus relative selection
    cmd2 = parser.parse("- 2")
    assert isinstance(cmd2, SelectOnlyCommandNode)
    assert cmd2.selection.is_relative is True
    assert len(cmd2.selection.exclusions) == 1
    assert isinstance(cmd2.selection.exclusions[0], ChannelNumberNode)
    assert cmd2.selection.exclusions[0].channel == 2

    # 3. Thru relative selection
    cmd3 = parser.parse("THRU 10")
    assert isinstance(cmd3, SelectOnlyCommandNode)
    assert cmd3.selection.is_relative is True
    assert len(cmd3.selection.items) == 1
    assert isinstance(cmd3.selection.items[0], RelativeThruNode)
    assert cmd3.selection.items[0].end == 10

    # 4. Relative selection with action
    cmd4 = parser.parse("+ 5 AT 80")
    assert isinstance(cmd4, IntensityCommandNode)
    assert cmd4.selection is not None
    assert cmd4.selection.is_relative is True
    assert cmd4.level == 80.0

    # 5. Direct ODD selection
    cmd5 = parser.parse("ODD")
    assert isinstance(cmd5, SelectOnlyCommandNode)
    assert cmd5.selection.is_relative is True
    assert cmd5.selection.filter_mode == "odd"

    # 6. Direct EVEN with AT FULL
    cmd6 = parser.parse("EVEN AT FULL")
    assert isinstance(cmd6, IntensityCommandNode)
    assert cmd6.selection is not None
    assert cmd6.selection.is_relative is True
    assert cmd6.selection.filter_mode == "even"
    assert cmd6.level == 100.0

    # 7. Direct ODD with SNEAK
    cmd7 = parser.parse("ODD SNEAK TIME 2")
    assert isinstance(cmd7, SneakCommandNode)
    assert cmd7.selection is not None
    assert cmd7.selection.is_relative is True
    assert cmd7.selection.filter_mode == "odd"
    assert cmd7.duration == 2.0


def test_parser_patch_command() -> None:
    from olc.core.parser.ast_nodes import (
        AddressNumberNode,
        AddressRangeNode,
        PatchCommandNode,
    )

    parser = CommandParser()

    # 1. Single address: 1 PATCH AT 10
    p1 = parser.parse("1 PATCH AT 10")
    assert isinstance(p1, PatchCommandNode)
    assert len(p1.addresses.items) == 1
    assert isinstance(p1.addresses.items[0], AddressNumberNode)
    assert p1.addresses.items[0].universe == 1
    assert p1.addresses.items[0].output == 10

    # 2. Range with THRU, +, - and universe/address: 1 PATCH AT 10 THRU 15 + 2/5 - 12
    p2 = parser.parse("1 PATCH AT 10 THRU 15 + 2/5 - 12")
    assert isinstance(p2, PatchCommandNode)
    assert len(p2.addresses.items) == 2
    assert isinstance(p2.addresses.items[0], AddressRangeNode)
    assert p2.addresses.items[0].start == 10
    assert p2.addresses.items[0].end == 15
    assert isinstance(p2.addresses.items[1], AddressNumberNode)
    assert p2.addresses.items[1].universe == 2
    assert p2.addresses.items[1].output == 5
    assert len(p2.addresses.exclusions) == 1
    assert isinstance(p2.addresses.exclusions[0], AddressNumberNode)
    assert p2.addresses.exclusions[0].output == 12

    # 3. Unpatch variants
    from olc.core.parser.ast_nodes import UnpatchCommandNode

    u1 = parser.parse("1 THRU 4 UNPATCH")
    assert isinstance(u1, UnpatchCommandNode)
    assert u1.selection is not None
    assert u1.addresses is None

    u2 = parser.parse("1 UNPATCH AT 10 THRU 12")
    assert isinstance(u2, UnpatchCommandNode)
    assert u2.selection is not None
    assert u2.addresses is not None

    u3 = parser.parse("ADDRESS 10 THRU 15 UNPATCH")
    assert isinstance(u3, UnpatchCommandNode)
    assert u3.selection is None
    assert u3.addresses is not None


def test_parser_address_at_level_and_park() -> None:
    """Test ADDRESS ... AT <level> (test output) vs ADDRESS ... PARK AT <level>."""
    from olc.core.parser.ast_nodes import (
        AddressLevelCommandNode,
        AddressParkCommandNode,
    )

    parser = CommandParser()

    n1 = parser.parse("ADDRESS 10 AT 50")
    assert isinstance(n1, AddressLevelCommandNode)
    assert n1.level == 50.0

    n2 = parser.parse("ADDRESS 2/1 THRU 10 AT FULL")
    assert isinstance(n2, AddressLevelCommandNode)
    assert n2.level == 100.0

    n3 = parser.parse("ADDRESS 10 AT OUT")
    assert isinstance(n3, AddressLevelCommandNode)
    assert n3.level == 0.0

    n4 = parser.parse("ADDRESS 10 AT")
    assert isinstance(n4, AddressLevelCommandNode)
    assert n4.level is None

    p1 = parser.parse("ADDRESS 10 PARK AT 50")
    assert isinstance(p1, AddressParkCommandNode)
    assert p1.level == 50.0


def test_parser_channel_check() -> None:
    """Test CHECK command syntax (<sel> CHECK [AT <level>], <sel> AT <level> CHECK)."""
    from olc.core.parser.ast_nodes import ChannelCheckCommandNode

    parser = CommandParser()

    c1 = parser.parse("1 CHECK")
    assert isinstance(c1, ChannelCheckCommandNode)
    assert c1.level is None

    c2 = parser.parse("1 CHECK AT 50")
    assert isinstance(c2, ChannelCheckCommandNode)
    assert c2.level == 50.0

    c3 = parser.parse("1 AT 50 CHECK")
    assert isinstance(c3, ChannelCheckCommandNode)
    assert c3.level == 50.0

    c4 = parser.parse("1 CHECK AT OUT")
    assert isinstance(c4, ChannelCheckCommandNode)
    assert c4.level == 0.0

    assert TokenType.AT in parser.get_expected_tokens("1 CHECK")
    assert TokenType.CHECK in parser.get_expected_tokens("1 AT 50")


_CONTRACT_CORPUS: tuple[str, ...] = (
    "1 AT 50",
    "1 THRU 5 + 8 - 3 AT FULL",
    "1 ODD AT OUT",
    "ALL AT 25",
    "CHANNEL 1 AT +10",
    "GROUP 2 AT -10",
    "1 CHECK",
    "1 CHECK AT 80",
    "1 AT 50 CHECK",
    "1 CHECK AT OUT",
    "ADDRESS 1/10 AT 50",
    "ADDRESS 1/10 AT OUT",
    "ADDRESS 1/10 PARK AT 50",
    "ADDRESS 1/10 UNPARK",
    "ADDRESS 1/10 UNPATCH",
    "1 PATCH AT 1/10",
    "1 THRU 4 UNPATCH",
    "1 THRU 4 UNPATCH AT 1/10",
    "PARK ALL",
    "UNPARK ALL",
    "PARK 1 AT 50",
    "1 PARK",
    "1 PARK AT 50",
    "1 UNPARK",
    "CUE 1 RECORD",
    "RECORD CUE 1 TIME 3",
    "RECORD CUE 1 TIME 3/5 DELAY 1 BLOCK",
    "CUE 1 GOTO TIME 2",
    "GOTO CUE 1 TIME 2",
    "CUE 1 UPDATE",
    "UPDATE CUE 1",
    "CUE 1 BLOCK",
    "CUE 1 UNBLOCK",
    "CUE 1 DELETE",
    "1 SNEAK",
    "1 SNEAK TIME 2",
    "SNEAK TIME 2",
    "SNEAK 1 THRU 4 TIME 2",
    "1 HOME",
    "HOME POSITION",
    "POSITION HOME",
    "1 POSITION HOME",
    "1 LOCATE",
    "1 PAN 50",
    "INDEPENDENT 1 SNEAK TIME 2",
    "INDEPENDENT ALL SNEAK",
    "1 INTENSITY PALETTE 3",
    "1 FOCUS PALETTE 12",
    "1 COLOR PALETTE 2",
    "1 BEAM PALETTE 1",
    "1 PRESET 1",
    "1 CP 2",
    "1 IP 3",
    "1 FP 12",
    "1 BP 1",
    "COLOR PALETTE 2",
    "PRESET 1",
    "RECORD INTENSITY PALETTE 3",
    "RECORD FOCUS PALETTE 10",
    "RECORD COLOR PALETTE 2",
    "RECORD BEAM PALETTE 1",
    "RECORD PRESET 1",
    "RECORD FP 10",
    "UPDATE COLOR PALETTE 2",
    "UPDATE PRESET 1",
    "DELETE BEAM PALETTE 1",
    "DELETE PRESET 1",
)


def test_parser_palette_and_preset_commands() -> None:
    """Verify IFCB palette and preset commands plus non-regression with attributes."""
    parser = CommandParser()

    n_ip = parser.parse("1 INTENSITY PALETTE 3")
    assert isinstance(n_ip, ApplyPaletteCommandNode)
    assert n_ip.selection is not None
    assert n_ip.category == "intensity"
    assert n_ip.palette_id == 3.0

    n_fp = parser.parse("1 THRU 4 FOCUS PALETTE 12")
    assert isinstance(n_fp, ApplyPaletteCommandNode)
    assert n_fp.selection is not None
    assert n_fp.category == "focus"
    assert n_fp.palette_id == 12.0

    n_cp = parser.parse("COLOR PALETTE 2")
    assert isinstance(n_cp, ApplyPaletteCommandNode)
    assert n_cp.selection is None
    assert n_cp.category == "color"
    assert n_cp.palette_id == 2.0

    n_bp = parser.parse("1 BP 1")
    assert isinstance(n_bp, ApplyPaletteCommandNode)
    assert n_bp.category == "beam"
    assert n_bp.palette_id == 1.0

    n_pr = parser.parse("1 PRESET 2.5")
    assert isinstance(n_pr, ApplyPaletteCommandNode)
    assert n_pr.category == "preset"
    assert n_pr.palette_id == 2.5

    r_pal = parser.parse("RECORD COLOR PALETTE 2")
    assert isinstance(r_pal, RecordPaletteCommandNode)
    assert r_pal.category == "color"
    assert r_pal.palette_id == 2.0

    r_fp = parser.parse("RECORD FP 10")
    assert isinstance(r_fp, RecordPaletteCommandNode)
    assert r_fp.category == "focus"
    assert r_fp.palette_id == 10.0

    u_pal = parser.parse("UPDATE PRESET 1")
    assert isinstance(u_pal, UpdatePaletteCommandNode)
    assert u_pal.category == "preset"
    assert u_pal.palette_id == 1.0

    d_pal = parser.parse("DELETE BEAM PALETTE 1")
    assert isinstance(d_pal, DeletePaletteCommandNode)
    assert d_pal.category == "beam"
    assert d_pal.palette_id == 1.0

    # Non-regression: attributes, HOME, and RECORD CUE timing remain intact
    attr_col = parser.parse("1 COLOR RED")
    assert isinstance(attr_col, AttributeCommandNode)
    assert attr_col.attributes["color"] == "RED"

    attr_foc = parser.parse("1 FOCUS 50")
    assert isinstance(attr_foc, AttributeCommandNode)
    assert attr_foc.attributes["focus"] == 50.0

    home_col = parser.parse("1 COLOR HOME")
    assert isinstance(home_col, HomeCommandNode)
    assert home_col.category == "color"

    rec_cue = parser.parse("RECORD CUE 1 COLOR 2")
    assert isinstance(rec_cue, RecordCueCommandNode)
    assert rec_cue.cue_id == 1.0
    assert rec_cue.time_color == 2.0


def test_parser_expected_tokens_contract() -> None:
    """Every valid command prefix must expect the next token in its grammar."""
    parser = CommandParser()

    for cmd in _CONTRACT_CORPUS:
        # Verify the command itself is valid
        parser.parse(cmd)
        tokens = parser.lexer.tokenize(cmd)[:-1]
        for idx, tok in enumerate(tokens):
            prefix = " ".join(t.raw_text for t in tokens[:idx])
            if prefix:
                prefix += " "
            expected = parser.get_expected_tokens(prefix)
            assert tok.type in expected, (
                f"Expected {tok.type.name} for prefix {prefix!r} in {cmd!r}, "
                f"got {[t.name for t in expected]}"
            )

    # Negative checks: ADDRESS 1/2 only allows UNPATCH, UNPARK, PARK, AT, +, -, THRU
    addr_expected = set(parser.get_expected_tokens("ADDRESS 1/2 "))
    assert {
        TokenType.UNPATCH,
        TokenType.UNPARK,
        TokenType.PARK,
        TokenType.AT,
    } <= addr_expected
    assert TokenType.CHECK not in addr_expected
    assert TokenType.ODD not in addr_expected
    assert TokenType.HOME not in addr_expected

    # Palette expectations: PALETTE only after category keywords, never at root
    assert TokenType.PALETTE not in parser.get_expected_tokens("")
    assert TokenType.PALETTE not in parser.get_expected_tokens("1 ")
    assert TokenType.PALETTE in parser.get_expected_tokens("1 COLOR ")
    assert TokenType.PALETTE in parser.get_expected_tokens("1 FOCUS ")
    assert TokenType.PALETTE in parser.get_expected_tokens("1 BEAM ")
    assert TokenType.PALETTE in parser.get_expected_tokens("1 INTENSITY ")
    assert TokenType.PALETTE in parser.get_expected_tokens("RECORD FOCUS ")
