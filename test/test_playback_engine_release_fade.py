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
"""Unit and concurrency tests for PlaybackEngine progressive release fades."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.core.playback_engine import RunnerState


def _make_app_with_chaser(
    seq_index: float = 2.0,
    channels: dict[int, int] | None = None,
) -> CoreApplication:
    """Create a CoreApplication with an active chaser loaded at step 1."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.backend = MagicMock()
    app.action_registry.execute("sequence.new", seq_index)
    app.action_registry.execute(
        "sequence.insert_step",
        seq_index,
        1,
        1.0,
        channels or {1: 255},
    )
    seq = app.lightshow.get_sequence(seq_index)
    assert seq is not None
    seq.load_step(1)
    return app


def test_deterministic_release_fade_progression() -> None:
    """Test deterministic tick(now=...) progression for a release fade."""
    app = _make_app_with_chaser(2.0, {1: 255})
    engine = app.playback_engine
    arb = app.playback_arbitrator

    released_events: list[float] = []
    app.subscribe("playback.sequence_released", released_events.append)

    try:
        assert app.action_registry.execute("sequence.release", 2.0, fade_time=2.0)
        # Stop background thread so we can drive tick(now=...) deterministically
        engine.stop_worker()

        fade = engine._release_fades.get(2.0)
        assert fade is not None
        start_time = fade.start_time

        # Reset to exact start_time before deterministic ticks
        assert engine.tick(now=start_time) is True
        runner = engine.get_runner(2.0)
        assert runner.state == RunnerState.RELEASING
        assert runner.fade_progress == pytest.approx(0.0)
        assert runner.fade_remaining == pytest.approx(2.0)

        # Midpoint: 1.0s / 2.0s = 50%
        has_work = engine.tick(now=start_time + 1.0)
        assert has_work is True
        state = arb.get_state(2.0)
        assert state is not None
        assert state.active is True
        assert state.fader_level == pytest.approx(0.5)
        assert runner.state == RunnerState.RELEASING
        assert runner.fade_progress == pytest.approx(0.5)
        assert runner.fade_remaining == pytest.approx(1.0)
        assert released_events == []

        # Completion: 2.0s / 2.0s = 100%
        has_work = engine.tick(now=start_time + 2.0)
        assert has_work is False
        state = arb.get_state(2.0)
        assert state is not None
        assert state.active is False
        assert state.fader_level == pytest.approx(1.0)
        assert runner.state == RunnerState.IDLE
        assert runner.fade_progress == pytest.approx(0.0)
        assert runner.fade_remaining == pytest.approx(0.0)
        assert released_events == [2.0]
    finally:
        engine.clear()


def test_refiring_sequence_cancels_active_release_fade() -> None:
    """Test that load_step/do_go/assert_playback cancel an active release fade."""
    app = _make_app_with_chaser(2.0, {1: 255})
    engine = app.playback_engine
    arb = app.playback_arbitrator
    seq = app.lightshow.get_sequence(2.0)
    assert seq is not None

    try:
        engine.release(2.0, fade_time=2.0)
        engine.stop_worker()

        fade = engine._release_fades.get(2.0)
        assert fade is not None
        start_time = fade.start_time

        engine.tick(now=start_time + 0.5)
        state = arb.get_state(2.0)
        assert state is not None
        assert state.fader_level == pytest.approx(0.75)

        # Re-fire step 1 -> cancels release fade and restores fader_level
        seq.load_step(1)
        assert 2.0 not in engine._release_fades
        assert state.active is True
        assert state.fader_level == pytest.approx(1.0)
        assert engine.get_runner(2.0).state == RunnerState.ACTIVE

        # Subsequent ticks past original duration do NOT release
        assert engine.tick(now=start_time + 3.0) is False
        assert state.active is True
    finally:
        engine.clear()


def test_concurrent_release_fades_real_40hz_worker() -> None:
    """Test 3 sequences releasing concurrently via the real 40Hz tick thread."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.backend = MagicMock()
    engine = app.playback_engine
    arb = app.playback_arbitrator

    indices = [2.0, 3.0, 4.0]
    try:
        for i, idx in enumerate(indices, start=1):
            app.action_registry.execute("sequence.new", idx)
            app.action_registry.execute("sequence.insert_step", idx, 1, 1.0, {i: 200})
            seq = app.lightshow.get_sequence(idx)
            assert seq is not None
            seq.load_step(1)

        for idx in indices:
            assert engine.release(idx, fade_time=0.15) is True

        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if all(engine.get_runner(idx).state == RunnerState.IDLE for idx in indices):
                break
            time.sleep(0.02)

        for idx in indices:
            assert engine.get_runner(idx).state == RunnerState.IDLE
            state = arb.get_state(idx)
            assert state is not None
            assert state.active is False
    finally:
        engine.clear()
        assert engine._tick_thread is None
