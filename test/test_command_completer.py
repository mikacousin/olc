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
"""Unit tests for CommandCompleter."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.parser.completer import CommandCompleter
from olc.core.parser.parser import CommandParser


def test_completer_empty_text_returns_root_commands() -> None:
    parser = CommandParser()
    completer = CommandCompleter(parser)

    text_before, prefix, candidates = completer.get_candidates("")
    assert text_before == ""
    assert prefix == ""
    assert "RECORD" in candidates
    assert "GOTO" in candidates
    assert "GROUP" in candidates
    assert "ALL" in candidates


def test_completer_number_tab_proposes_continuations_and_cycles() -> None:
    """User typing '1 Tab' must propose continuations and cycle through them."""
    parser = CommandParser()
    completer = CommandCompleter(parser)

    # 1. First Tab on '1'
    res1 = completer.complete("1")
    assert res1.has_completed is True
    assert res1.new_text == "1 THRU "
    assert "THRU" in res1.candidates
    assert "AT" in res1.candidates
    assert "+" in res1.candidates
    assert "-" in res1.candidates

    # 2. Second Tab immediately after cycles to next candidate 'AT'
    res2 = completer.complete(res1.new_text)
    assert res2.has_completed is True
    assert res2.new_text == "1 AT "

    # 3. Third Tab cycles to '+'
    res3 = completer.complete(res2.new_text)
    assert res3.has_completed is True
    assert res3.new_text == "1 + "


def test_completer_prefix_matching() -> None:
    parser = CommandParser()
    completer = CommandCompleter(parser)

    # '1 T' -> '1 THRU '
    res_thru = completer.complete("1 T")
    assert res_thru.has_completed is True
    assert res_thru.new_text == "1 THRU "

    # '1 AT F' -> '1 AT FULL '
    res_full = completer.complete("1 AT F")
    assert res_full.has_completed is True
    assert res_full.new_text == "1 AT FULL "

    # 'REC' -> 'RECORD '
    res_rec = completer.complete("REC")
    assert res_rec.has_completed is True
    assert res_rec.new_text == "RECORD "

    # 'GOTO C' -> 'GOTO CUE '
    res_cue = completer.complete("GOTO C")
    assert res_cue.has_completed is True
    assert res_cue.new_text == "GOTO CUE "


def test_completer_ambiguous_cycling() -> None:
    parser = CommandParser()
    completer = CommandCompleter(parser)

    # 'G' matches GOTO and GROUP
    res1 = completer.complete("G")
    assert res1.has_completed is True
    assert set(res1.candidates) == {"GROUP", "GOTO"}
    cand1 = res1.candidates[0]
    cand2 = res1.candidates[1]
    assert res1.new_text == f"{cand1} "

    # Second Tab cycles to second candidate
    res2 = completer.complete(res1.new_text)
    assert res2.has_completed is True
    assert res2.new_text == f"{cand2} "

    # Third Tab cycles back to first candidate
    res3 = completer.complete(res2.new_text)
    assert res3.has_completed is True
    assert res3.new_text == f"{cand1} "


def test_completer_show_cues_and_groups() -> None:
    parser = CommandParser()
    mock_show = MagicMock()

    # Mock cues
    cue1 = MagicMock()
    cue1.id = 1
    cue2 = MagicMock()
    cue2.id = 2.5
    cue3 = MagicMock()
    cue3.id = 5
    mock_show.cues = [cue1, cue2, cue3]

    # Mock groups
    mock_show.groups.groups = {2: MagicMock(), 4: MagicMock()}

    completer = CommandCompleter(parser, mock_show)

    # 1. GOTO CUE <Tab>
    res_cue = completer.complete("GOTO CUE")
    assert res_cue.has_completed is True
    assert "1" in res_cue.candidates
    assert "2.5" in res_cue.candidates
    assert "5" in res_cue.candidates
    assert res_cue.new_text == "GOTO CUE 1 "

    # 2. GROUP <Tab>
    res_group = completer.complete("GROUP")
    assert res_group.has_completed is True
    assert "2" in res_group.candidates
    assert "4" in res_group.candidates
    assert res_group.new_text == "GROUP 2 "


def test_completer_color_presets() -> None:
    parser = CommandParser()
    completer = CommandCompleter(parser)

    # '1 COLOR R' -> '1 COLOR RED '
    res_color = completer.complete("1 COLOR R")
    assert res_color.has_completed is True
    assert res_color.new_text == "1 COLOR RED "


def test_completer_reset_cycle_on_different_input() -> None:
    parser = CommandParser()
    completer = CommandCompleter(parser)

    res1 = completer.complete("1")
    assert res1.new_text == "1 THRU "

    # If user inputs something else manually
    completer.reset_cycle()
    res2 = completer.complete("1 AT")
    assert res2.new_text == "1 AT FULL "
