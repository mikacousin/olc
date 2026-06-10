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
"""Unit tests for SetChannelLevelAction and HistoryManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from olc.core.app import CoreApplication
from olc.define import MAX_CHANNELS


def test_channel_set_level_action_and_undo_redo() -> None:
    """Test channel set level action execution, undo, and redo."""
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

    # 4. Execute: Set channel 5 to DMX intensity 128
    app.action_registry.execute("channel.set_level", 5, 128)

    # Assert DMX levels override was updated (0-indexed array)
    assert app.backend.dmx.levels["user"][4] == 128
    # Assert set_levels update was called
    mock_dmx.set_levels.assert_called_once()
    # Assert event was emitted
    assert received_events == [(5, 128)]

    # 5. Undo the action
    mock_dmx.set_levels.reset_mock()
    app.history.undo()

    # Assert DMX levels override was restored to -1
    assert app.backend.dmx.levels["user"][4] == -1
    mock_dmx.set_levels.assert_called_once()
    assert received_events == [(5, 128), (5, -1)]

    # 6. Redo the action
    mock_dmx.set_levels.reset_mock()
    app.history.redo()

    # Assert DMX levels override is back to 128
    assert app.backend.dmx.levels["user"][4] == 128
    mock_dmx.set_levels.assert_called_once()
    assert received_events == [(5, 128), (5, -1), (5, 128)]


def test_channel_set_level_action_validation_errors() -> None:
    """Test SetChannelLevelAction input value validation bounds."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Channel index < 1 should raise ValueError
    with pytest.raises(ValueError, match="Channel index must be between 1 and"):
        app.action_registry.execute("channel.set_level", 0, 100)

    # Channel index > MAX_CHANNELS should raise ValueError
    with pytest.raises(ValueError, match="Channel index must be between 1 and"):
        app.action_registry.execute("channel.set_level", MAX_CHANNELS + 1, 100)

    # DMX Level < -1 should raise ValueError
    with pytest.raises(ValueError, match="DMX Level must be between -1 and 255"):
        app.action_registry.execute("channel.set_level", 1, -2)

    # DMX Level > 255 should raise ValueError
    with pytest.raises(ValueError, match="DMX Level must be between -1 and 255"):
        app.action_registry.execute("channel.set_level", 1, 256)


def test_channel_set_level_action_without_backend() -> None:
    """Test SetChannelLevelAction with missing or None backend."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.backend = None

    # Should run and emit event without throwing AttributeError
    app.action_registry.execute("channel.set_level", 10, 100)

    # Try undoing/redoing without backend
    app.history.undo()
    app.history.redo()


def test_channel_set_level_action_feedback_and_repr() -> None:
    """Test SetChannelLevelAction feedback state dict and string representation."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.action_registry.execute("channel.set_level", 15, 200)
    action = app.action_registry.get("channel.set_level")

    assert action.get_feedback_state() == {
        "channel": 15,
        "level": 200,
        "active": True,
    }

    assert repr(action) == "<SetChannelLevelAction channel=15 level=200>"
