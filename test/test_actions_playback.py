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
        go_triggered_events.append,
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
        pause_triggered_events.append,
    )

    app.action_registry.execute("playback.pause")

    mock_playback.pause.assert_called_once_with(None, None)
    assert len(pause_triggered_events) == 1
    assert pause_triggered_events[0] == {"active": True, "label": "PAUSE"}


def test_go_back_action_execution() -> None:
    """Test execution and event dispatching for GoBackAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    mock_playback.on_go = True
    app.lightshow.main_playback = mock_playback

    go_back_triggered_events = []
    app.subscribe(
        "playback.go_back_triggered",
        go_back_triggered_events.append,
    )

    app.action_registry.execute("playback.go_back")

    mock_playback.go_back.assert_called_once_with(None, None)
    assert len(go_back_triggered_events) == 1
    assert go_back_triggered_events[0] == {"active": True, "label": "GOBACK"}


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
        seq_plus_triggered_events.append,
    )

    app.action_registry.execute("playback.sequence_plus")

    mock_playback.sequence_plus.assert_called_once()
    assert len(seq_plus_triggered_events) == 1
    feedback = seq_plus_triggered_events[0]
    assert feedback["active"] is False
    assert feedback["label"] == "SEQ+"
    assert feedback["position"] == 4
    assert feedback["timer"] == 0.1


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
        seq_minus_triggered_events.append,
    )

    app.action_registry.execute("playback.sequence_minus")

    mock_playback.sequence_minus.assert_called_once()
    assert len(seq_minus_triggered_events) == 1
    feedback = seq_minus_triggered_events[0]
    assert feedback["active"] is False
    assert feedback["label"] == "SEQ-"
    assert feedback["position"] == 3
    assert feedback["timer"] == 0.1


def test_goto_action_execution() -> None:
    """Test execution and event dispatching for PlaybackGotoAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    app.lightshow.main_playback = mock_playback

    goto_triggered_events = []
    app.subscribe(
        "playback.goto_triggered",
        goto_triggered_events.append,
    )

    app.action_registry.execute("playback.goto", "2.5")

    mock_playback.goto.assert_called_once_with("2.5")
    assert len(goto_triggered_events) == 1
    assert goto_triggered_events[0] == {
        "active": False,
        "label": "GOTO",
        "target": "2.5",
    }
    action = app.action_registry.get("playback.goto")
    assert action.get_feedback_state() == {
        "active": False,
        "label": "GOTO",
        "target": "2.5",
    }


def test_manual_xfade_action_execution() -> None:
    """Test execution and event dispatching for PlaybackManualXFadeAction."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_crossfade = MagicMock()
    mock_scale_a = MagicMock()
    mock_scale_b = MagicMock()
    mock_crossfade.scale_a = mock_scale_a
    mock_crossfade.scale_b = mock_scale_b
    app.crossfade = mock_crossfade

    xfade_events = []
    app.subscribe("playback.xfade_moved", lambda f, val: xfade_events.append((f, val)))

    # Execute fader A
    app.action_registry.execute("playback.manual_xfade", "a", 150)
    assert mock_crossfade.manual is True
    mock_scale_a.set_value.assert_called_once_with(150)
    mock_crossfade.scale_moved.assert_called_once_with(mock_scale_a)
    assert xfade_events == [("a", 150)]

    # Execute fader B with clamping
    mock_crossfade.scale_moved.reset_mock()
    app.action_registry.execute("playback.manual_xfade", "crossfade_in", 300)
    mock_scale_b.set_value.assert_called_once_with(255)
    mock_crossfade.scale_moved.assert_called_once_with(mock_scale_b)
    assert xfade_events == [("a", 150), ("b", 255)]


def test_playback_step_navigate_action_feedback_with_steps() -> None:
    """Test detailed feedback state of PlaybackStepNavigateAction when steps exist."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_playback = MagicMock()
    mock_playback.position = 0
    mock_playback.last = 2

    # Step 0
    step0 = MagicMock()
    step0.text = "Cue 1 text"
    cue0 = MagicMock()
    cue0.number = 1.0
    step0.cue = cue0

    # Step 1 (next)
    step1 = MagicMock()
    step1.text = "Cue 2 text"
    step1.total_time = 5.0
    step1.time_in = 3.0
    step1.time_out = 3.0
    step1.delay_in = 1.0
    step1.delay_out = 1.0
    step1.wait = 0.5
    step1.channel_time = False
    cue1 = MagicMock()
    cue1.number = 2.0
    step1.cue = cue1

    mock_playback.steps = [step0, step1]
    app.lightshow.main_playback = mock_playback

    app.action_registry.execute("playback.sequence_plus")
    action = app.action_registry.get("playback.sequence_plus")
    feedback = action.get_feedback_state()

    assert feedback["cue_number"] == 1.0
    assert feedback["cue_text"] == "Cue 1 text"
    assert feedback["next_cue_number"] == 2.0
    assert feedback["next_cue_text"] == "Cue 2 text"
    assert feedback["next_total_time"] == 5.0
    assert feedback["next_delay_in"] == 1.0
