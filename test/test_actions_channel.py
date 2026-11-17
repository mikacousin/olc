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
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, -1.0, dtype=np.float64)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # 3. Track events
    received_events: list[tuple[int, float]] = []
    app.subscribe(
        "channel.level_changed", lambda chan, val: received_events.append((chan, val))
    )

    # 4. Execute: Set channel 5 to normalized intensity 0.5
    app.action_registry.execute("channel.set_level", 5, 0.5)

    # Assert DMX levels override was updated (0-indexed array)
    assert app.backend.dmx.levels["user"][4] == 0.5
    # Assert set_levels update was called
    mock_dmx.set_levels.assert_called_once()
    # Assert event was emitted
    assert received_events == [(5, 0.5)]

    # 5. Undo the action
    mock_dmx.set_levels.reset_mock()
    app.history.undo()

    # Assert DMX levels override was restored to -1.0
    assert app.backend.dmx.levels["user"][4] == -1.0
    mock_dmx.set_levels.assert_called_once()
    assert received_events == [(5, 0.5), (5, -1.0)]

    # 6. Redo the action
    mock_dmx.set_levels.reset_mock()
    app.history.redo()

    # Assert DMX levels override is back to 0.5
    assert app.backend.dmx.levels["user"][4] == 0.5
    mock_dmx.set_levels.assert_called_once()
    assert received_events == [(5, 0.5), (5, -1.0), (5, 0.5)]


def test_channel_set_level_action_validation_errors() -> None:
    """Test SetChannelLevelAction input value validation bounds."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Channel index < 1 should raise ValueError
    with pytest.raises(ValueError, match="Channel index must be between 1 and"):
        app.action_registry.execute("channel.set_level", 0, 0.5)

    # Channel index > MAX_CHANNELS should raise ValueError
    with pytest.raises(ValueError, match="Channel index must be between 1 and"):
        app.action_registry.execute("channel.set_level", MAX_CHANNELS + 1, 0.5)

    # Normalized Level < -1.0 should raise ValueError
    with pytest.raises(
        ValueError, match="Normalized level must be between -1.0 and 1.0"
    ):
        app.action_registry.execute("channel.set_level", 1, -1.5)

    # Normalized Level > 1.0 should raise ValueError
    with pytest.raises(
        ValueError, match="Normalized level must be between -1.0 and 1.0"
    ):
        app.action_registry.execute("channel.set_level", 1, 1.5)


def test_channel_set_level_action_without_backend() -> None:
    """Test SetChannelLevelAction with missing or None backend."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.backend = None

    # Should run and emit event without throwing AttributeError
    app.action_registry.execute("channel.set_level", 10, 0.5)

    # Try undoing/redoing without backend
    app.history.undo()
    app.history.redo()


def test_channel_set_level_action_feedback_and_repr() -> None:
    """Test SetChannelLevelAction feedback state dict and string representation."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.action_registry.execute("channel.set_level", 15, 0.8)
    action = app.action_registry.get("channel.set_level")

    assert action.get_feedback_state() == {
        "channel": 15,
        "level": 0.8,
        "normalized_level": 0.8,
        "active": True,
    }

    assert repr(action) == "<SetChannelLevelAction channel=15 level=0.8>"


def test_channel_set_level_normalized_and_16bit_device() -> None:
    """Test SetChannelLevelAction with normalized float and high-res device."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx = MagicMock()
    user_levels = [-1.0] * 1024
    mock_backend.dmx.levels = {"user": user_levels, "sequence": [0.0] * 1024}
    app.backend = mock_backend

    mock_device = MagicMock()
    mock_device.fixture_id = 5
    mock_device.set_intensity = MagicMock()
    app.lightshow.patch.devices = {5: mock_device}

    # Execute with normalized float 0.8
    app.action_registry.execute("channel.set_level", 5, 0.8)
    mock_device.set_intensity.assert_called_with(0.8)
    assert mock_backend.dmx.levels["user"][4] == 0.8

    action = app.action_registry.get("channel.set_level")
    assert action.get_feedback_state() == {
        "channel": 5,
        "level": 0.8,
        "normalized_level": 0.8,
        "active": True,
    }

    # Test release with -1.0
    app.action_registry.execute("channel.set_level", 5, -1.0)
    assert mock_backend.dmx.levels["user"][4] == -1.0
    mock_device.set_intensity.assert_called_with(0.0)


def test_channel_selection_actions_undo_redo() -> None:
    """Test channel selection actions execution, undo, and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Subscribe to channels.selected_changed
    received_selections: list[list[int]] = []
    app.subscribe(
        "channels.selected_changed", lambda sel: received_selections.append(list(sel))
    )

    # 1. Test SelectActiveChannelAction
    app.commandline.set_string("5")
    app.action_registry.execute("channel.select_active")
    assert app.selected_channels == [5]
    assert app.last_selected_channel == 5
    assert received_selections[-1] == [5]

    # Undo
    app.history.undo()
    assert not app.selected_channels
    assert app.last_selected_channel is None

    assert received_selections[-1] == []

    # Redo
    app.history.redo()
    assert app.selected_channels == [5]
    assert app.last_selected_channel == 5
    assert received_selections[-1] == [5]

    # 2. Test SelectAddChannelAction
    app.commandline.set_string("10")
    app.action_registry.execute("channel.select_add")
    assert app.selected_channels == [5, 10]
    assert app.last_selected_channel == 10
    assert received_selections[-1] == [5, 10]

    # Undo
    app.history.undo()
    assert app.selected_channels == [5]
    assert app.last_selected_channel == 5
    assert received_selections[-1] == [5]

    # Redo
    app.history.redo()
    assert app.selected_channels == [5, 10]

    # 3. Test SelectThruChannelAction
    app.commandline.set_string("12")
    app.action_registry.execute("channel.select_thru")
    # should select from last_selected (10) thru 12, so 10, 11, 12. And 5 was already
    # selected.
    assert set(app.selected_channels) == {5, 10, 11, 12}
    assert app.last_selected_channel == 12

    # Undo
    app.history.undo()
    assert app.selected_channels == [5, 10]
    assert app.last_selected_channel == 10

    # Redo
    app.history.redo()
    assert set(app.selected_channels) == {5, 10, 11, 12}

    # 4. Test SelectRemoveChannelAction
    app.commandline.set_string("11")
    app.action_registry.execute("channel.select_remove")
    assert 11 not in app.selected_channels
    assert app.last_selected_channel == 11

    # Undo
    app.history.undo()
    assert 11 in app.selected_channels

    # Redo
    app.history.redo()
    assert 11 not in app.selected_channels


def test_select_channels_action_and_undo_redo() -> None:
    """Test channel.select_channels execution, feedback, undo, and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received_selections: list[list[int]] = []
    app.subscribe(
        "channels.selected_changed", lambda sel: received_selections.append(list(sel))
    )

    # 1. Execute: Select channels 1 to 5
    app.action_registry.execute("channel.select_channels", [1, 2, 3, 4, 5], 5)
    assert app.selected_channels == [1, 2, 3, 4, 5]
    assert app.last_selected_channel == 5
    assert received_selections[-1] == [1, 2, 3, 4, 5]

    action = app.action_registry.get("channel.select_channels")
    assert action.get_feedback_state() == {
        "selected_channels": [1, 2, 3, 4, 5],
        "count": 5,
        "last_selected": 5,
    }

    # 2. Select channels 10, 20
    app.action_registry.execute("channel.select_channels", [10, 20])
    assert app.selected_channels == [10, 20]
    assert app.last_selected_channel == 20

    # 3. Undo: restores [1..5]
    app.history.undo()
    assert app.selected_channels == [1, 2, 3, 4, 5]
    assert app.last_selected_channel == 5

    # 4. Undo: restores []
    app.history.undo()
    assert app.selected_channels == []
    assert app.last_selected_channel is None

    # 5. Redo: restores [1..5]
    app.history.redo()
    assert app.selected_channels == [1, 2, 3, 4, 5]

    # 6. Redo: restores [10, 20]
    app.history.redo()
    assert app.selected_channels == [10, 20]


def test_set_multi_channels_level_action() -> None:
    """Test multi-channels set level action execution, undo, and redo."""
    # 1. Initialize mock settings and core app
    settings = MagicMock()
    app = CoreApplication(settings)

    # 2. Mock Dmx backend
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, -1.0, dtype=np.float64)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # 3. Track events
    received_events: list[tuple[int, float]] = []
    app.subscribe(
        "channel.level_changed", lambda chan, val: received_events.append((chan, val))
    )

    # 4. Execute: Set channel 3 to 0.8, and channel 4 to 0.6
    app.action_registry.execute("channel.set_multi_levels", {3: 0.8, 4: 0.6})

    # Assert DMX levels override were updated
    assert app.backend.dmx.levels["user"][2] == 0.8
    assert app.backend.dmx.levels["user"][3] == 0.6
    # Assert set_levels update was called
    mock_dmx.set_levels.assert_called_once()
    # Assert events were emitted (order is not guaranteed, check set)
    assert set(received_events) == {(3, 0.8), (4, 0.6)}

    # 5. Undo the action
    mock_dmx.set_levels.reset_mock()
    received_events.clear()
    app.history.undo()

    # Assert DMX levels override were restored to -1.0
    assert app.backend.dmx.levels["user"][2] == -1.0
    assert app.backend.dmx.levels["user"][3] == -1.0
    mock_dmx.set_levels.assert_called_once()
    assert set(received_events) == {(3, -1.0), (4, -1.0)}

    # 6. Redo the action
    mock_dmx.set_levels.reset_mock()
    received_events.clear()
    app.history.redo()

    # Assert DMX levels override are back to modified values
    assert app.backend.dmx.levels["user"][2] == 0.8
    assert app.backend.dmx.levels["user"][3] == 0.6
    mock_dmx.set_levels.assert_called_once()
    assert set(received_events) == {(3, 0.8), (4, 0.6)}


def test_channel_wheel_adjust_action_and_undo_redo() -> None:
    """Test channel.wheel_adjust action execution, bounds clamping, and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, 100.0 / 255.0, dtype=np.float64)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # Select channels 1 and 2
    app.selected_channels = [1, 2]

    # Adjust UP by 25
    app.action_registry.execute("channel.wheel_adjust", 25, 1)
    assert app.backend.dmx.levels["user"][0] == pytest.approx(125.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(125.0 / 255.0)

    # Undo
    app.history.undo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(100.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(100.0 / 255.0)

    # Redo
    app.history.redo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(125.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(125.0 / 255.0)

    # Adjust DOWN with clamping at 0.0
    app.action_registry.execute("channel.wheel_adjust", 200, -1)
    assert app.backend.dmx.levels["user"][0] == 0.0
    assert app.backend.dmx.levels["user"][1] == 0.0

    # Undo clamping
    app.history.undo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(125.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(125.0 / 255.0)


def test_channel_level_plus_minus_and_undo_redo() -> None:
    """Test channel.level_plus and channel.level_minus actions."""
    settings = MagicMock()
    settings.get_int.return_value = 10
    settings.get_boolean.return_value = False
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, 50.0 / 255.0, dtype=np.float64)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    app.selected_channels = [1, 2]

    # Test level_plus
    app.action_registry.execute("channel.level_plus")
    assert app.backend.dmx.levels["user"][0] == pytest.approx(60.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(60.0 / 255.0)

    # Undo level_plus
    app.history.undo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(50.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(50.0 / 255.0)

    # Redo level_plus
    app.history.redo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(60.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(60.0 / 255.0)

    # Test level_minus
    app.action_registry.execute("channel.level_minus")
    assert app.backend.dmx.levels["user"][0] == pytest.approx(50.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(50.0 / 255.0)

    # Undo level_minus
    app.history.undo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(60.0 / 255.0)
    assert app.backend.dmx.levels["user"][1] == pytest.approx(60.0 / 255.0)

    # Test with percent mode enabled
    settings.get_boolean.return_value = True
    app.action_registry.execute("channel.level_plus")
    assert app.backend.dmx.levels["user"][0] > 60.0 / 255.0

    app.history.undo()
    assert app.backend.dmx.levels["user"][0] == pytest.approx(60.0 / 255.0)


def test_channel_set_level_from_cmd() -> None:
    """Test channel.set_level_from_cmd action."""
    settings = MagicMock()
    settings.get_boolean.return_value = False
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, 20.0 / 255.0, dtype=np.float64)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    app.selected_channels = [3, 4]

    # Test set_level_from_cmd
    app.commandline.set_string("128")
    app.action_registry.execute("channel.set_level_from_cmd")
    assert app.backend.dmx.levels["user"][2] == pytest.approx(128.0 / 255.0)
    assert app.backend.dmx.levels["user"][3] == pytest.approx(128.0 / 255.0)
    assert app.commandline.get_string() == ""

    # Undo
    app.history.undo()
    assert app.backend.dmx.levels["user"][2] == pytest.approx(20.0 / 255.0)
    assert app.backend.dmx.levels["user"][3] == pytest.approx(20.0 / 255.0)

    # Redo
    app.history.redo()
    assert app.backend.dmx.levels["user"][2] == pytest.approx(128.0 / 255.0)
    assert app.backend.dmx.levels["user"][3] == pytest.approx(128.0 / 255.0)

    # Test set_level_from_cmd with percent mode
    settings.get_boolean.return_value = True
    app.commandline.set_string("50")
    app.action_registry.execute("channel.set_level_from_cmd")
    assert app.backend.dmx.levels["user"][2] == pytest.approx(0.5)


def test_channel_level_actions_empty_selection() -> None:
    """Test level actions when no channel is selected."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": np.full(MAX_CHANNELS, 0, dtype=np.int16)}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    app.selected_channels = []

    # None of these should throw
    app.action_registry.execute("channel.wheel_adjust", 10, 1)
    app.action_registry.execute("channel.level_plus")
    app.action_registry.execute("channel.level_minus")
    app.commandline.set_string("100")
    app.action_registry.execute("channel.set_level_from_cmd")
    # Command line should remain untouched if no channel was selected
    assert app.commandline.get_string() == "100"
