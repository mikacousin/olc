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
"""Unit tests for UndoAction, RedoAction and ActionRegistry."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
from olc.core.app import CoreApplication
from olc.define import MAX_CHANNELS


def test_undo_redo_actions() -> None:
    """Test calling edit.undo and edit.redo actions via ActionRegistry."""
    # 1. Initialize mock settings and core app
    settings = MagicMock()
    app = CoreApplication(settings)

    # 2. Mock Dmx backend
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    # levels structure: sequence, user, faders
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, -1, dtype=np.int16)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # 3. Track events
    received_events: list[tuple[int, int]] = []
    app.subscribe(
        "channel.level_changed", lambda chan, val: received_events.append((chan, val))
    )

    # 4. Execute: Set channel 10 to DMX intensity 200
    app.action_registry.execute("channel.set_level", 10, 200)

    # Assert DMX levels override was updated (0-indexed array)
    assert app.backend.dmx.levels["user"][9] == 200
    assert received_events == [(10, 200)]

    # 5. Execute "edit.undo" action via the registry
    mock_dmx.set_levels.reset_mock()
    app.action_registry.execute("edit.undo")

    # Assert DMX levels override was restored to -1
    assert app.backend.dmx.levels["user"][9] == -1
    assert received_events == [(10, 200), (10, -1)]

    # 6. Execute "edit.redo" action via the registry
    mock_dmx.set_levels.reset_mock()
    app.action_registry.execute("edit.redo")

    # Assert DMX levels override is back to 200
    assert app.backend.dmx.levels["user"][9] == 200
    assert received_events == [(10, 200), (10, -1), (10, 200)]


def test_sequential_undo_redo_actions() -> None:
    """Test calling multiple set channel level actions and undoing them in sequence."""
    # 1. Initialize mock settings and core app
    settings = MagicMock()
    app = CoreApplication(settings)

    # 2. Mock Dmx backend
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    # levels structure: sequence, user, faders
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, -1, dtype=np.int16)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # 3. Execute: Set channel 10 to 200, then channel 11 to 150
    app.action_registry.execute("channel.set_level", 10, 200)
    app.action_registry.execute("channel.set_level", 11, 150)

    # Assert DMX levels override are set correctly
    assert app.backend.dmx.levels["user"][9] == 200
    assert app.backend.dmx.levels["user"][10] == 150

    # 4. Undo the last action (channel 11 should restore to -1)
    app.action_registry.execute("edit.undo")
    assert app.backend.dmx.levels["user"][10] == -1
    assert app.backend.dmx.levels["user"][9] == 200

    # 5. Undo the first action (channel 10 should restore to -1)
    app.action_registry.execute("edit.undo")
    assert app.backend.dmx.levels["user"][9] == -1
    assert app.backend.dmx.levels["user"][10] == -1

    # 6. Redo the first action (channel 10 back to 200)
    app.action_registry.execute("edit.redo")
    assert app.backend.dmx.levels["user"][9] == 200
    assert app.backend.dmx.levels["user"][10] == -1

    # 7. Redo the second action (channel 11 back to 150)
    app.action_registry.execute("edit.redo")
    assert app.backend.dmx.levels["user"][9] == 200
    assert app.backend.dmx.levels["user"][10] == 150
