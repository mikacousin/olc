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
"""Unit & integration tests for PlaybackEngine and strict is_main isolation."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.core.dmx_backend import DMXBackend
from olc.core.playback_engine import RunnerState
from olc.show.cue import Cue
from olc.show.fader import FaderType
from olc.show.sequence import Sequence
from olc.show.step import Step


def _make_app() -> CoreApplication:
    settings = MagicMock()
    settings.get_double.return_value = 0.05
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    app.backend = DMXBackend(app.lightshow)
    app.init_engine(monitor_port=5555, no_listen=True, no_transmit=True)
    return app


def _add_cue(
    seq: Sequence, num: float, chans: dict[int, float], *, time_in: float = 0.0
) -> None:
    cue = Cue(int(seq.index), num, channels=dict(chans), text=f"Q{num:g}")
    seq.cues.add(cue)
    step = Step(
        sequence=int(seq.index),
        cue=cue,
        time_in=time_in,
        time_out=time_in,
    )
    seq.insert_step(len(seq.steps) - 1, step)


def test_secondary_sequence_does_not_touch_crossfade_or_main_events() -> None:
    """Verify secondary sequence fade never mutates CrossFade or main header events."""
    app = _make_app()
    assert app.crossfade is not None
    try:
        seq1 = app.lightshow.main_playback
        _add_cue(seq1, 1.0, {1: 0.5}, time_in=0.0)
        seq2 = Sequence(2, text="Overlay", lightshow=app.lightshow)
        _add_cue(seq2, 10.0, {2: 0.9}, time_in=0.15)
        app.lightshow.sequences.append(seq2)

        main_events: list[str] = []
        runner_events: list[float] = []
        for evt in (
            "playback.step_changed",
            "playback.transition_progress",
            "playback.transition_completed",
            "playback.go_started",
            "playback.go_triggered",
            "playback.stopped",
        ):
            app.subscribe(evt, lambda *_a, e=evt: main_events.append(e))
        app.subscribe("playback.runner_changed", lambda idx: runner_events.append(idx))

        # Sentinel values on CrossFade scales
        app.crossfade.scale_a.set_value(42)
        app.crossfade.scale_b.set_value(84)

        # Trigger Go on secondary Sequence 2
        assert app.playback_engine.go(2) is True
        deadline = time.time() + 1.5
        while seq2.on_go and time.time() < deadline:
            time.sleep(0.02)

        assert main_events == []
        assert 2.0 in runner_events
        assert app.crossfade.scale_a.get_value() == pytest.approx(42 / 255.0)
        assert app.crossfade.scale_b.get_value() == pytest.approx(84 / 255.0)
    finally:
        app.stop()


def test_set_main_sequence_switches_crossfade_and_supports_undo() -> None:
    """Verify playback.set_main_sequence switches main_sequence and CrossFade."""
    app = _make_app()
    assert app.crossfade is not None
    assert app.backend is not None
    try:
        seq1 = app.lightshow.main_playback
        _add_cue(seq1, 1.0, {1: 0.3})

        seq2 = Sequence(2, text="Alt Main", lightshow=app.lightshow)
        _add_cue(seq2, 20.0, {2: 0.8})
        app.lightshow.sequences.append(seq2)

        assert app.playback_engine.is_main_sequence(1) is True
        assert app.playback_engine.is_main_sequence(2) is False

        ok = app.action_registry.execute("playback.set_main_sequence", 2)
        assert ok is True
        assert app.playback_engine.main_sequence is seq2
        assert app.playback_engine.is_main_sequence(2) is True
        assert app.playback_engine.is_main_sequence(1) is False
        assert app.crossfade._get_main_sequence() is seq2

        # Manual crossfade now drives Seq 2 (ch 2), not Seq 1 (ch 1)
        app.crossfade.scale_a.set_value(0.5)
        app.crossfade.scale_moved(app.crossfade.scale_a)
        app.crossfade.scale_a.set_value(1.0)
        app.crossfade.scale_moved(app.crossfade.scale_a)
        app.crossfade.scale_b.set_value(1.0)
        app.crossfade.scale_moved(app.crossfade.scale_b)
        assert app.backend.dmx.levels["sequence"][1] == pytest.approx(0.8)

        # Undo restores Seq 1 as Main Sequence
        app.action_registry.execute("edit.undo")
        assert app.playback_engine.main_sequence is seq1
        assert app.playback_engine.is_main_sequence(1) is True
    finally:
        app.stop()


def test_playback_engine_snapshots_and_release_all() -> None:
    """Verify get_all_runner_snapshots telemetry and release_all()."""
    app = _make_app()
    try:
        seq1 = app.lightshow.main_playback
        _add_cue(seq1, 1.0, {1: 0.5})
        seq2 = Sequence(2, text="FX List", lightshow=app.lightshow)
        _add_cue(seq2, 10.0, {2: 0.9, 3: 0.7})
        app.lightshow.sequences.append(seq2)
        app.lightshow.fader_bank.set_fader(1, 5, FaderType.SEQUENCE, 2)

        seq1.load_step(1)
        seq2.load_step(1)

        snaps = app.playback_engine.get_all_runner_snapshots(active_only=True)
        assert len(snaps) == 2
        s1, s2 = snaps[0], snaps[1]
        assert s1.is_main is True
        assert s1.state is RunnerState.ACTIVE
        assert s1.active_cue == 1.0
        assert s1.owned_channels_count == 1

        assert s2.is_main is False
        assert s2.state is RunnerState.ACTIVE
        assert s2.active_cue == 10.0
        assert s2.assigned_fader == "P1-F5"
        assert s2.owned_channels_count == 2

        released = app.playback_engine.release_all()
        assert set(released) == {1.0, 2.0}
        assert app.playback_engine.get_all_runner_snapshots(active_only=True) == []
    finally:
        app.stop()
