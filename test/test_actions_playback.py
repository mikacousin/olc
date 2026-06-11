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
"""Unit tests for GoAction and PauseAction."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication


def test_playback_actions_with_missing_playback() -> None:
    """Test playback actions when main_playback is not initialized or None."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.main_playback = None  # ty: ignore[invalid-assignment]

    # Should return early without crash
    app.action_registry.execute("playback.go")
    app.action_registry.execute("playback.pause")
    app.action_registry.execute("playback.sequence_plus")
    app.action_registry.execute("playback.sequence_minus")


def test_go_action_execution() -> None:
    """Test execution and event dispatching for GoAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    mock_playback.on_go = True
    app.lightshow.main_playback = mock_playback

    go_triggered_events = []
    app.subscribe(
        "playback.go_triggered",
        lambda state: go_triggered_events.append(state),
    )

    app.action_registry.execute("playback.go")

    mock_playback.do_go.assert_called_once_with(None)
    assert len(go_triggered_events) == 1
    assert go_triggered_events[0] == {"active": True, "label": "GO"}


def test_pause_action_execution() -> None:
    """Test execution and event dispatching for PauseAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    # Mock thread and pause event to check paused state
    mock_thread = MagicMock()
    mock_thread.pause.is_set.return_value = False  # False means paused
    mock_playback.thread = mock_thread
    mock_playback.on_go = True
    app.lightshow.main_playback = mock_playback

    pause_triggered_events = []
    app.subscribe(
        "playback.pause_triggered",
        lambda state: pause_triggered_events.append(state),
    )

    app.action_registry.execute("playback.pause")

    mock_playback.pause.assert_called_once_with(None, None)
    assert len(pause_triggered_events) == 1
    assert pause_triggered_events[0] == {"active": True, "label": "PAUSE"}


def test_sequence_plus_action_execution() -> None:
    """Test execution and event dispatching for SequencePlusAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    mock_playback.position = 4
    app.lightshow.main_playback = mock_playback

    seq_plus_triggered_events = []
    app.subscribe(
        "playback.sequence_plus_triggered",
        lambda state: seq_plus_triggered_events.append(state),
    )

    app.action_registry.execute("playback.sequence_plus")

    mock_playback.sequence_plus.assert_called_once()
    assert len(seq_plus_triggered_events) == 1
    assert seq_plus_triggered_events[0] == {
        "active": False,
        "label": "SEQ+",
        "position": 4,
    }


def test_sequence_minus_action_execution() -> None:
    """Test execution and event dispatching for SequenceMinusAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    mock_playback.position = 3
    app.lightshow.main_playback = mock_playback

    seq_minus_triggered_events = []
    app.subscribe(
        "playback.sequence_minus_triggered",
        lambda state: seq_minus_triggered_events.append(state),
    )

    app.action_registry.execute("playback.sequence_minus")

    mock_playback.sequence_minus.assert_called_once()
    assert len(seq_minus_triggered_events) == 1
    assert seq_minus_triggered_events[0] == {
        "active": False,
        "label": "SEQ-",
        "position": 3,
    }
