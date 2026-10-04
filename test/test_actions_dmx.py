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
from olc.actions.dmx import DmxSetUniverseLevelsAction, UniverseBlackoutAction
from olc.actions.patch import (
    DmxSetUniverseLevelsAction as PatchDmx,
)
from olc.actions.patch import (
    UniverseBlackoutAction as PatchBlackout,
)
from olc.core.app import CoreApplication


def test_dmx_actions_backward_compatible_reexport() -> None:
    """Test backwards-compatibility re-exports in olc.actions.patch."""
    assert PatchDmx is DmxSetUniverseLevelsAction
    assert PatchBlackout is UniverseBlackoutAction


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
