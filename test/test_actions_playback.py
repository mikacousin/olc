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

import numpy as np
import pytest

from olc.core.app import CoreApplication
from olc.cue import Cue
from olc.devices.builtin import create_moving_head_definition, create_rgb_definition
from olc.step import Step


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


def test_playback_record_cue_auto_and_undo_redo() -> None:
    """Test playback.record_cue with automatic next cue allocation and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Patch channel 1 to output 1 universe 1, and channel 2 to output 2 universe 1
    app.lightshow.patch.patch_empty()
    app.lightshow.patch.add_output(1, 1, 1, 0)
    app.lightshow.patch.add_output(2, 2, 1, 0)

    # Set mock backend with live frame levels
    mock_backend = MagicMock()
    frame = np.zeros(512, dtype=np.uint8)
    frame[0] = 200  # output 1 -> 200
    frame[1] = 150  # output 2 -> 150
    mock_backend.dmx.frame = [frame] + [np.zeros(512, dtype=np.uint8) for _ in range(3)]
    app.backend = mock_backend

    recorded_events: list[tuple[float, int, float]] = []
    app.subscribe(
        "playback.cue_recorded",
        lambda s, st, c: recorded_events.append((s, st, c)),
    )

    initial_step_count = len(app.lightshow.main_playback.steps)
    initial_cue_count = len(app.lightshow.cues)
    initial_pos = app.lightshow.main_playback.position

    # Execute record cue
    app.action_registry.execute("playback.record_cue")

    assert len(app.lightshow.cues) == initial_cue_count + 1
    assert len(app.lightshow.main_playback.steps) == initial_step_count + 1
    new_cue = app.lightshow.cues.get(1.0, 1)
    assert new_cue is not None
    assert new_cue.channels == {1: 200, 2: 150}
    assert app.lightshow.main_playback.position == initial_pos + 1
    assert len(recorded_events) == 1

    # Undo
    app.history.undo()
    assert len(app.lightshow.cues) == initial_cue_count
    assert len(app.lightshow.main_playback.steps) == initial_step_count
    assert app.lightshow.cues.get(1.0, 1) is None
    assert app.lightshow.main_playback.position == initial_pos
    assert len(recorded_events) == 2

    # Redo
    app.history.redo()
    assert len(app.lightshow.cues) == initial_cue_count + 1
    assert len(app.lightshow.main_playback.steps) == initial_step_count + 1
    assert app.lightshow.cues.get(1.0, 1) is not None
    assert app.lightshow.main_playback.position == initial_pos + 1
    assert len(recorded_events) == 3


def test_playback_record_cue_explicit_number_and_step() -> None:
    """Test playback.record_cue with explicit cue number and step."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.patch.patch_empty()
    app.lightshow.patch.add_output(3, 3, 1, 0)
    mock_backend = MagicMock()
    frame = np.zeros(512, dtype=np.uint8)
    frame[2] = 255  # output 3 -> 255
    mock_backend.dmx.frame = [frame] + [np.zeros(512, dtype=np.uint8) for _ in range(3)]
    app.backend = mock_backend

    app.action_registry.execute("playback.record_cue", 5.5, 1)
    cue = app.lightshow.cues.get(5.5, 1)
    assert cue is not None
    assert cue.channels == {3: 255}
    assert app.lightshow.main_playback.position == 1

    app.history.undo()
    assert app.lightshow.cues.get(5.5, 1) is None


def test_playback_update_active_step_and_undo_redo() -> None:
    """Test playback.update_active_step updating cue levels and restoring on undo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.patch.patch_empty()
    app.lightshow.patch.add_output(1, 1, 1, 0)
    app.lightshow.patch.add_output(2, 2, 1, 0)

    # Create initial cue and step in main playback
    initial_cue = Cue(1, 2.0, {1: 100, 2: 80})
    app.lightshow.cues.add(initial_cue)
    step = Step(1, cue=initial_cue)
    app.lightshow.main_playback.insert_step(1, step)
    app.lightshow.main_playback.position = 1

    # Stage changes: channel 1 is at 255, channel 2 at 0
    mock_backend = MagicMock()
    frame = np.zeros(512, dtype=np.uint8)
    frame[0] = 255
    frame[1] = 0
    mock_backend.dmx.frame = [frame] + [np.zeros(512, dtype=np.uint8) for _ in range(3)]
    app.backend = mock_backend

    cue_updated_events: list[tuple[int, float]] = []
    app.subscribe(
        "cue.updated",
        lambda seq, num: cue_updated_events.append((seq, num)),
    )

    # Execute update_active_step
    app.action_registry.execute("playback.update_active_step", 2.0)
    assert initial_cue.channels[1] == 255
    assert initial_cue.channels[2] == 0
    assert cue_updated_events == [(1, 2.0)]

    # Undo
    app.history.undo()
    assert initial_cue.channels[1] == 100
    assert initial_cue.channels[2] == 80
    assert len(cue_updated_events) == 2

    # Redo
    app.history.redo()
    assert initial_cue.channels[1] == 255
    assert initial_cue.channels[2] == 0
    assert len(cue_updated_events) == 3


def test_playback_record_and_update_multi_parameter_devices_and_virtual_dimmer() -> (
    None
):
    """Verify record_cue, update_active_step, and channel actions capture devices."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.patch.patch_empty()

    mh = app.lightshow.patch.patch_device(1, create_moving_head_definition(), 1, 1)
    led = app.lightshow.patch.patch_device(2, create_rgb_definition(), 1, 20)

    mock_backend = MagicMock()
    mock_backend.dmx.frame = [np.zeros(512, dtype=np.uint8) for _ in range(4)]
    mock_backend.dmx.levels = {
        "sequence": np.zeros(512, dtype=np.uint8),
        "user": np.full(512, -1, dtype=np.int16),
    }
    app.backend = mock_backend

    # Set LED intensity via channel.set_level action -> must sync Virtual Dimmer!
    app.action_registry.execute("channel.set_level", 2, 204)
    assert led.intensity == pytest.approx(204 / 255.0, abs=0.01)

    # Set Moving Head intensity, Pan, Tilt, Zoom and LED Color
    app.action_registry.execute("channel.set_level", 1, 255)
    mh.set_pan_degrees(90.0)
    mh.set_tilt_degrees(-30.0)
    mh.set_zoom_degrees(25.0)
    led.set_color_srgb(0.0, 1.0, 0.0)

    # Record Cue 1.0 via playback.record_cue
    app.action_registry.execute("playback.record_cue")
    cue1 = app.lightshow.cues.get(1.0, 1)
    assert cue1 is not None
    assert cue1.channels[1] == 255
    assert cue1.channels[2] == 204
    assert cue1.device_values[1]["pan"] == pytest.approx(90.0, abs=0.5)
    assert cue1.device_values[1]["tilt"] == pytest.approx(-30.0, abs=0.5)
    assert cue1.device_values[1]["zoom"] == pytest.approx(25.0, abs=0.5)
    assert cue1.device_values[1]["intensity"] == pytest.approx(1.0, abs=0.01)
    assert cue1.device_values[2]["color"].lower() == "#00ff00"
    assert cue1.device_values[2]["intensity"] == pytest.approx(204 / 255.0, abs=0.01)

    # Modify Pan and Color on stage and update active step (Cue 1.0)
    mh.set_pan_degrees(180.0)
    led.set_color_srgb(0.0, 0.0, 1.0)
    app.action_registry.execute("channel.set_level", 2, 0)
    app.action_registry.execute("playback.update_active_step", 1.0)

    assert cue1.device_values[1]["pan"] == pytest.approx(180.0, abs=0.5)
    assert cue1.device_values[2]["color"].lower() == "#0000ff"
    assert cue1.device_values[2]["intensity"] == pytest.approx(0.0, abs=0.01)
    assert cue1.channels[2] == 0

    # Undo update_active_step -> restores Pan 90°, Green, and intensity 204/255
    app.history.undo()
    assert cue1.device_values[1]["pan"] == pytest.approx(90.0, abs=0.5)
    assert cue1.device_values[2]["color"].lower() == "#00ff00"
    assert cue1.device_values[2]["intensity"] == pytest.approx(204 / 255.0, abs=0.01)
    assert cue1.channels[2] == 204

    # Redo update_active_step -> re-applies Pan 180°, Blue, and intensity 0.0
    app.history.redo()
    assert cue1.device_values[1]["pan"] == pytest.approx(180.0, abs=0.5)
    assert cue1.device_values[2]["color"].lower() == "#0000ff"
    assert cue1.device_values[2]["intensity"] == pytest.approx(0.0, abs=0.01)
    assert cue1.channels[2] == 0
