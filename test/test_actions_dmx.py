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
"""Unit tests for DMX actions (universe.blackout, dmx.set_universe_levels)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
from olc.core.app import CoreApplication
from olc.define import UNIVERSES


def test_universe_blackout_action_and_undo_redo() -> None:
    """Test universe.blackout execution with engine and backend, and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    mock_universe = MagicMock()
    initial_frame = np.full(512, 120, dtype=np.uint8)
    mock_universe.snapshot.return_value = initial_frame.copy()
    mock_engine.universe.return_value = mock_universe
    app.engine = mock_engine

    mock_backend = MagicMock()
    mock_backend.dmx.frame = [np.full(512, 120, dtype=np.uint8)]
    app.backend = mock_backend

    blackout_events: list[int] = []
    app.subscribe("universe.blackout_changed", blackout_events.append)

    # Execute blackout
    app.action_registry.execute("universe.blackout", 1)
    mock_universe.blackout.assert_called_once()
    assert np.all(mock_backend.dmx.frame[0] == 0)
    assert blackout_events == [1]

    # Undo
    app.history.undo()
    mock_universe.apply_array.assert_called_once()
    assert np.all(mock_backend.dmx.frame[0] == 120)
    assert blackout_events == [1, 1]

    # Redo
    app.history.redo()
    assert mock_universe.blackout.call_count == 2
    assert np.all(mock_backend.dmx.frame[0] == 0)
    assert blackout_events == [1, 1, 1]


def test_dmx_set_universe_levels_action() -> None:
    """Test dmx.set_universe_levels action execution with engine and backend."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine

    mock_backend = MagicMock()
    mock_backend.dmx.frame = [np.zeros(512, dtype=np.uint8)]
    app.backend = mock_backend

    dmx_events: list[tuple[int, dict[int, int]]] = []
    app.subscribe(
        "universe.dmx_changed",
        lambda uid, chs: dmx_events.append((uid, chs)),
    )

    app.action_registry.execute("dmx.set_universe_levels", 1, {0: 255, 5: 128})
    mock_engine.set_channels.assert_called_once_with(1, {0: 255, 5: 128})
    assert mock_backend.dmx.frame[0][0] == 255
    assert mock_backend.dmx.frame[0][5] == 128
    assert dmx_events == [(1, {0: 255, 5: 128})]
    assert len(app.history.undo_stack) == 0


def test_dmx_test_output_action_single_and_undo_redo() -> None:
    """Test dmx.test_output with a single output and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx.user_outputs = {}
    mock_backend.dmx.frame = [np.zeros(512, dtype=np.uint8)]

    def fake_send(out: int, univ: int, lvl: int) -> None:
        if lvl:
            mock_backend.dmx.user_outputs[(out, univ)] = lvl
        else:
            mock_backend.dmx.user_outputs.pop((out, univ), None)
        mock_backend.dmx.frame[univ - 1][out - 1] = lvl

    mock_backend.dmx.send_user_output.side_effect = fake_send
    app.backend = mock_backend

    events: list[tuple[int, int, int]] = []
    app.subscribe(
        "dmx.user_output_changed",
        lambda u, o, lvl: events.append((u, o, lvl)),
    )

    # Execute test output
    app.action_registry.execute("dmx.test_output", 10, 1, 255)
    assert mock_backend.dmx.user_outputs.get((10, 1)) == 255
    assert mock_backend.dmx.frame[0][9] == 255
    assert events == [(1, 10, 255)]

    # Undo
    app.history.undo()
    assert (10, 1) not in mock_backend.dmx.user_outputs
    assert mock_backend.dmx.frame[0][9] == 0
    assert events == [(1, 10, 255), (1, 10, 0)]

    # Redo
    app.history.redo()
    assert mock_backend.dmx.user_outputs.get((10, 1)) == 255
    assert mock_backend.dmx.frame[0][9] == 255
    assert events == [(1, 10, 255), (1, 10, 0), (1, 10, 255)]


def test_dmx_test_output_action_multiple() -> None:
    """Test dmx.test_output with multiple outputs simultaneously."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx.user_outputs = {}
    mock_backend.dmx.frame = [np.zeros(512, dtype=np.uint8)]

    def fake_send(out: int, univ: int, lvl: int) -> None:
        if lvl:
            mock_backend.dmx.user_outputs[(out, univ)] = lvl
        else:
            mock_backend.dmx.user_outputs.pop((out, univ), None)
        mock_backend.dmx.frame[univ - 1][out - 1] = lvl

    mock_backend.dmx.send_user_output.side_effect = fake_send
    app.backend = mock_backend

    targets = [(1, 1), (2, 1), (3, 1)]
    app.action_registry.execute("dmx.test_output", targets, 1, 180)
    assert mock_backend.dmx.user_outputs.get((1, 1)) == 180
    assert mock_backend.dmx.user_outputs.get((2, 1)) == 180
    assert mock_backend.dmx.user_outputs.get((3, 1)) == 180

    app.history.undo()
    assert (1, 1) not in mock_backend.dmx.user_outputs
    assert (2, 1) not in mock_backend.dmx.user_outputs
    assert (3, 1) not in mock_backend.dmx.user_outputs


def test_dmx_clear_user_outputs_action_and_undo_redo() -> None:
    """Test dmx.clear_user_outputs clearing test outputs and restoring on undo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx.user_outputs = {(5, 1): 200, (12, 1): 150}

    def fake_send(out: int, univ: int, lvl: int) -> None:
        if lvl:
            mock_backend.dmx.user_outputs[(out, univ)] = lvl
        else:
            mock_backend.dmx.user_outputs.pop((out, univ), None)

    mock_backend.dmx.send_user_output.side_effect = fake_send
    app.backend = mock_backend

    cleared_events: list[bool] = []
    app.subscribe("dmx.user_outputs_cleared", lambda: cleared_events.append(True))
    changed_events: list[bool] = []
    app.subscribe("dmx.user_outputs_changed", lambda: changed_events.append(True))

    # Execute clear
    app.action_registry.execute("dmx.clear_user_outputs")
    assert len(mock_backend.dmx.user_outputs) == 0
    assert cleared_events == [True]

    # Undo
    app.history.undo()
    assert mock_backend.dmx.user_outputs == {(5, 1): 200, (12, 1): 150}
    assert changed_events == [True]

    # Redo
    app.history.redo()
    assert len(mock_backend.dmx.user_outputs) == 0
    assert cleared_events == [True, True]


def test_dmx_blackout_all_action_and_undo_redo() -> None:
    """Test dmx.blackout_all across all universes with undo and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    engine_universes: dict[int, MagicMock] = {}
    for univ_id in UNIVERSES:
        u_mock = MagicMock()
        u_mock.snapshot.return_value = np.full(512, 75, dtype=np.uint8)
        engine_universes[univ_id] = u_mock

    mock_engine.universe.side_effect = lambda uid: engine_universes[uid]
    app.engine = mock_engine

    mock_backend = MagicMock()
    mock_backend.dmx.frame = [
        np.full(512, 75, dtype=np.uint8) for _ in range(len(UNIVERSES))
    ]
    app.backend = mock_backend

    blackout_all_events: list[bool] = []
    app.subscribe(
        "dmx.blackout_all_changed",
        blackout_all_events.append,
    )

    # Execute blackout_all
    app.action_registry.execute("dmx.blackout_all")
    for u_mock in engine_universes.values():
        u_mock.blackout.assert_called_once()
    for frame in mock_backend.dmx.frame:
        assert np.all(frame == 0)
    assert blackout_all_events == [True]

    # Undo
    app.history.undo()
    for u_mock in engine_universes.values():
        u_mock.apply_array.assert_called_once()
    for frame in mock_backend.dmx.frame:
        assert np.all(frame == 75)
    assert blackout_all_events == [True, False]

    # Redo
    app.history.redo()
    for frame in mock_backend.dmx.frame:
        assert np.all(frame == 0)
    assert blackout_all_events == [True, False, True]
