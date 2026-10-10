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
"""Unit tests for CommandExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.core.parser.ast_nodes import SelectOnlyCommandNode
from olc.core.parser.executor import CommandExecutor
from olc.core.parser.parser import CommandParser


def test_executor_resolve_selection() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    executor = CommandExecutor(app)
    parser = CommandParser()

    node1 = parser.parse("1 THRU 5")
    assert isinstance(node1, SelectOnlyCommandNode)
    assert executor.resolve_selection(node1.selection) == [1, 2, 3, 4, 5]

    node2 = parser.parse("1 THRU 10 - 4 - 6")
    assert isinstance(node2, SelectOnlyCommandNode)
    assert executor.resolve_selection(node2.selection) == [1, 2, 3, 5, 7, 8, 9, 10]

    node3 = parser.parse("1 THRU 10 ODD")
    assert isinstance(node3, SelectOnlyCommandNode)
    assert executor.resolve_selection(node3.selection) == [1, 3, 5, 7, 9]

    node4 = parser.parse("1 THRU 10 EVEN")
    assert isinstance(node4, SelectOnlyCommandNode)
    assert executor.resolve_selection(node4.selection) == [2, 4, 6, 8, 10]


def test_executor_select_only() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    executor = CommandExecutor(app)
    parser = CommandParser()

    cmd = parser.parse("1 THRU 4")
    res = executor.execute(cmd)

    assert res.success
    assert app.selected_channels == [1, 2, 3, 4]
    assert app.last_selected_channel == 4


def test_executor_intensity_absolute_and_relative() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    executor = CommandExecutor(app)
    parser = CommandParser()

    # 1 THRU 3 AT 80
    cmd1 = parser.parse("1 THRU 3 AT 80")
    res1 = executor.execute(cmd1)
    assert res1.success
    # 80% of 255 = 204
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 204

    # AT +10 (relative on active selection)
    cmd2 = parser.parse("AT + 10")
    res2 = executor.execute(cmd2)
    assert res2.success
    # 90% of 255 = 230
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 230

    # AT OUT
    cmd3 = parser.parse("AT OUT")
    res3 = executor.execute(cmd3)
    assert res3.success
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 0


def test_executor_record_and_goto_cue() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    executor = CommandExecutor(app)
    parser = CommandParser()

    # Turn on channels 1 and 2
    executor.execute(parser.parse("1 + 2 AT FULL"))

    # RECORD CUE 1 TIME 3 / 2
    cmd_rec = parser.parse("RECORD CUE 1 TIME 3 / 2 BLOCK")
    res_rec = executor.execute(cmd_rec)
    assert res_rec.success

    cue = app.lightshow.cues.get(1.0, 1)
    assert cue is not None
    assert cue.is_block is True
    assert cue.channels[1] == 255
    assert cue.channels[2] == 255

    step = next(
        (s for s in app.lightshow.main_playback.steps if s.cue and s.cue.number == 1.0),
        None,
    )
    assert step is not None
    assert step.time_in == 3.0
    assert step.time_out == 2.0

    # GOTO CUE 1
    cmd_goto = parser.parse("GOTO CUE 1")
    res_goto = executor.execute(cmd_goto)
    assert res_goto.success
