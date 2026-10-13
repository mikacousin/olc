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
"""Unit tests for manual CrossFade with TrackingEngine and multi-parameter devices."""
# pylint: disable=too-few-public-methods, missing-class-docstring, missing-function-docstring

from __future__ import annotations

import typing

import numpy as np
import pytest

from olc.core.crossfade import CrossFade
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.devices.builtin import create_moving_head_definition, create_rgb_definition
from olc.patch import PatchManager
from olc.sequence import Sequence
from olc.step import Step


class _MockDMX:
    def __init__(self) -> None:
        self.levels = {
            "sequence": np.zeros(MAX_CHANNELS, dtype=np.uint8),
            "user": np.full(MAX_CHANNELS, -1, dtype=np.int16),
        }
        self.set_levels_calls = 0

    def set_levels(self) -> None:
        self.set_levels_calls += 1


class _MockBackend:
    def __init__(self) -> None:
        self.dmx = _MockDMX()


class _MockAction:
    def get_feedback_state(self) -> dict[str, typing.Any]:
        return {"active": False}


class _MockRegistry:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[typing.Any, ...]]] = []

    def execute(self, name: str, *args: typing.Any) -> None:  # noqa: ANN401
        self.executed.append((name, args))

    def trigger_feedback(self, _name: str) -> None:
        pass

    def get(self, _name: str) -> _MockAction:
        return _MockAction()


class _MockLightShow:
    def __init__(self, patch: PatchManager) -> None:
        self.patch = patch
        self.main_playback: Sequence = typing.cast(typing.Any, None)
        self.app: _MockApp = typing.cast(typing.Any, None)


class _MockSettings:
    def get_double(self, _key: str) -> float:
        return 5.0


class _MockApp:
    def __init__(self, patch: PatchManager) -> None:
        self.backend = _MockBackend()
        self.lightshow = _MockLightShow(patch)
        self.lightshow.app = self
        self.action_registry = _MockRegistry()
        self.events: list[tuple[str, tuple[typing.Any, ...]]] = []
        self.midi = None
        self.crossfade: CrossFade | None = None
        self.settings = _MockSettings()

    @property
    def core(self) -> _MockApp:
        return self

    def emit(self, event_name: str, *args: typing.Any) -> None:  # noqa: ANN401
        self.events.append((event_name, args))


def _build_crossfade_env(
    tracking_mode: bool = True,
) -> tuple[_MockApp, Sequence, PatchManager, CrossFade]:
    patch = PatchManager()
    patch.patch_empty()
    app = _MockApp(patch)
    seq = Sequence(
        index=1, text="Main", lightshow=typing.cast(typing.Any, app.lightshow)
    )
    seq.tracking_mode = tracking_mode
    seq.steps.clear()
    seq.last = 0
    app.lightshow.main_playback = seq
    xfade = CrossFade(app)
    app.crossfade = xfade
    return app, seq, patch, xfade


def test_manual_crossfade_preserves_tracked_channels_and_separates_scales() -> None:
    """Verify scale_a fades decays, scale_b fades attacks, and tracked stay intact."""
    app, seq, _patch, xfade = _build_crossfade_env(tracking_mode=True)

    # Step 0: Cue 0
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    # Step 1 (Cue 1): Ch 1 @ 200 (tracks), Ch 2 @ 200 (decays), Ch 3 @ 0 (attacks)
    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 200, 2: 200}
    seq.add_step(Step(sequence=1, cue=cue1, time_in=2.0, time_out=2.0))

    # Step 2 (Cue 2): Ch 1 tracked @ 200, Ch 2 @ 100 (decay), Ch 3 @ 100 (attack)
    cue2 = Cue(1, 2.0)
    cue2.channels = {2: 100, 3: 100}
    seq.add_step(Step(sequence=1, cue=cue2, time_in=2.0, time_out=2.0))

    # Sentinel last step
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    seq.load_step(1)
    dmx_seq = app.backend.dmx.levels["sequence"]
    assert dmx_seq[0] == 200
    assert dmx_seq[1] == 200
    assert dmx_seq[2] == 0

    # Move scale_a (Out/Decays) to 50% (~128/255)
    xfade.manual = True
    xfade.scale_a.set_value(128)
    xfade.scale_moved(xfade.scale_a)

    # Ch 1 (tracked) must remain 200!
    assert dmx_seq[0] == 200
    # Ch 2 (decay 200 -> 100) is around ~150
    assert 148 <= int(dmx_seq[1]) <= 152
    # Ch 3 (attack 0 -> 100) must still be 0 because scale_b has not moved
    assert dmx_seq[2] == 0

    # Now move scale_b (In/Attacks) to 50% (~128/255)
    xfade.scale_b.set_value(128)
    xfade.scale_moved(xfade.scale_b)

    # Ch 1 still 200, Ch 2 (decay) still ~150, Ch 3 (attack) ~50
    assert dmx_seq[0] == 200
    assert 148 <= int(dmx_seq[1]) <= 152
    assert 48 <= int(dmx_seq[2]) <= 52

    # Bring both sliders to 255 -> at_full()
    xfade.scale_a.set_value(255)
    xfade.scale_moved(xfade.scale_a)
    xfade.scale_b.set_value(255)
    xfade.scale_moved(xfade.scale_b)

    assert seq.position == 2
    assert dmx_seq[0] == 200  # Tracked channel preserved at full
    assert dmx_seq[1] == 100
    assert dmx_seq[2] == 100


def test_manual_crossfade_interpolates_devices_and_ifcb_times() -> None:
    """Verify manual crossfade interpolates LTP, Virtual Dimmer, and IFCB timings."""
    _app, seq, patch, xfade = _build_crossfade_env(tracking_mode=True)
    mh = patch.patch_device(1, create_moving_head_definition(), 1, 1)
    led = patch.patch_device(2, create_rgb_definition(), 1, 20)

    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    # Step 1 (Cue 1): MH at Pan 0°, Color Black, Int 1.0; LED Virtual Dimmer at 1.0, Red
    cue1 = Cue(1, 1.0)
    cue1.set_device_parameter(1, "intensity", 1.0)
    cue1.set_device_parameter(1, "pan", 0.0)
    cue1.set_device_parameter(1, "zoom", 10.0)
    cue1.set_device_parameter(2, "intensity", 1.0)
    cue1.set_device_parameter(2, "color", "#ff0000")
    seq.add_step(Step(sequence=1, cue=cue1, time_in=2.0, time_out=2.0))

    # Step 2 (Cue 2):
    # - MH Pan -> 100° with explicit time_position = 4.0s, Zoom -> 30° (time_in = 2.0s)
    # - LED intensity -> 0.0 (decay over time_out = 2.0s), Color -> Blue (#0000ff)
    cue2 = Cue(1, 2.0)
    cue2.set_device_parameter(1, "pan", 100.0)
    cue2.set_device_parameter(1, "zoom", 30.0)
    cue2.set_device_parameter(2, "intensity", 0.0)
    cue2.set_device_parameter(2, "color", "#0000ff")
    step2 = Step(
        sequence=1,
        cue=cue2,
        time_in=2.0,
        time_out=2.0,
        time_position=4.0,
    )
    seq.add_step(step2)
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    seq.load_step(1)
    assert mh.pan_degrees == pytest.approx(0.0, abs=0.1)
    assert mh.zoom_degrees == pytest.approx(10.0, abs=0.2)
    assert led.intensity == pytest.approx(1.0, abs=0.01)

    # Total time of step2 is 4.0s (4000ms) due to time_position=4.0s.
    # Move scale_a to 25% of 4000ms = 1000ms (which is 50% of time_out=2.0s)
    xfade.manual = True
    xfade.scale_a.set_value(round(255 * 0.25))
    xfade.scale_moved(xfade.scale_a)

    # LED intensity is decaying on scale_a (time_out=2s): at 1000ms it should be ~0.5
    assert led.intensity == pytest.approx(0.5, abs=0.03)
    # MH Pan hasn't moved because scale_b is still 0
    assert mh.pan_degrees == pytest.approx(0.0, abs=0.5)

    # Move scale_b to 25% of 4000ms = 1000ms:
    # - Zoom uses time_in=2.0s -> 50% progress -> 10 + 0.5 * 20 = 20°
    # - Pan uses time_position=4.0s -> 25% progress -> 25°
    xfade.scale_b.set_value(round(255 * 0.25))
    xfade.scale_moved(xfade.scale_b)

    assert mh.zoom_degrees == pytest.approx(20.0, abs=1.0)
    assert mh.pan_degrees == pytest.approx(25.0, abs=1.0)

    # Complete crossfade (both at 255)
    xfade.scale_a.set_value(255)
    xfade.scale_moved(xfade.scale_a)
    xfade.scale_b.set_value(255)
    xfade.scale_moved(xfade.scale_b)

    assert seq.position == 2
    assert mh.pan_degrees == pytest.approx(100.0, abs=0.5)
    assert mh.zoom_degrees == pytest.approx(30.0, abs=0.5)
    assert mh.intensity == pytest.approx(1.0, abs=0.01)  # Tracked from Cue 1!
    assert led.intensity == pytest.approx(0.0, abs=0.01)
    assert led.color_srgb.b == pytest.approx(1.0, abs=0.02)


def test_manual_crossfade_cue_only_mode_and_return_to_zero() -> None:
    """Verify Cue-Only mode drops untracked channels on scale_a and resets at (0, 0)."""
    app, seq, _patch, xfade = _build_crossfade_env(tracking_mode=False)

    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 200}
    seq.add_step(Step(sequence=1, cue=cue1, time_in=2.0, time_out=2.0))

    cue2 = Cue(1, 2.0)
    cue2.channels = {2: 100}
    seq.add_step(Step(sequence=1, cue=cue2, time_in=2.0, time_out=2.0))
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    seq.load_step(1)
    dmx_seq = app.backend.dmx.levels["sequence"]
    assert dmx_seq[0] == 200

    # Move scale_a to 50%: in Cue-Only mode, Ch 1 decays from 200 toward 0 (~100)
    xfade.manual = True
    xfade.scale_a.set_value(128)
    xfade.scale_moved(xfade.scale_a)
    assert 98 <= int(dmx_seq[0]) <= 102
    assert seq.on_go is True

    # Return scale_a to 0 -> cancels crossfade and restores baseline 200
    xfade.scale_a.set_value(0)
    xfade.scale_moved(xfade.scale_a)
    assert int(dmx_seq[0]) == 200
    assert seq.on_go is False
    assert xfade.manual is False


def test_takeover_manual_crossfade_while_go_paused_does_not_deadlock() -> None:
    """Verify taking over manual crossfade while Go is paused halts cleanly."""
    app, seq, _patch, xfade = _build_crossfade_env(tracking_mode=True)

    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 100}
    seq.add_step(Step(sequence=1, cue=cue1, time_in=10.0, time_out=10.0))

    cue2 = Cue(1, 2.0)
    cue2.channels = {1: 200}
    seq.add_step(Step(sequence=1, cue=cue2, time_in=10.0, time_out=10.0))
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    seq.load_step(1)

    # 1. Trigger Go transition (starts ThreadGo with total_time=10000ms)
    seq.do_go(None)
    assert seq.on_go is True
    assert seq.thread is not None
    assert seq.thread.is_alive()

    # 2. Pause the transition
    seq.pause(None, None)
    assert seq.thread.pause.is_set() is False

    # 3. Take over manually with crossfade
    xfade.manual = True
    xfade.scale_a.set_value(50)
    xfade.scale_moved(xfade.scale_a)

    # Verify:
    # - Background thread was stopped and joined cleanly without deadlock
    assert seq.thread is None
    # - Manual crossfade is now in control
    assert seq.on_go is True
    assert xfade.manual is True
    # - Pause was reset
    pause_events = [ev for ev in app.events if ev[0] == "playback.pause_triggered"]
    assert len(pause_events) >= 1
    assert pause_events[-1][1][0]["active"] is False


def test_takeover_manual_crossfade_while_goback_paused_does_not_deadlock() -> None:
    """Verify taking over manual crossfade while GoBack is paused halts cleanly."""
    app, seq, _patch, xfade = _build_crossfade_env(tracking_mode=True)

    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 100}
    seq.add_step(Step(sequence=1, cue=cue1, time_in=2.0, time_out=2.0))

    cue2 = Cue(1, 2.0)
    cue2.channels = {1: 200}
    seq.add_step(Step(sequence=1, cue=cue2, time_in=2.0, time_out=2.0))
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    # Start at step 2, so go_back can step to 1
    seq.load_step(2)

    seq.go_back(None, None)
    assert seq.on_go is True
    assert seq.thread is not None
    assert seq.thread.is_alive()

    # Pause the go_back
    seq.pause(None, None)
    assert seq.thread.pause.is_set() is False

    # Take over manually with crossfade
    xfade.manual = True
    xfade.scale_b.set_value(60)
    xfade.scale_moved(xfade.scale_b)

    # Verify: thread stopped cleanly and manual crossfade in control
    assert seq.thread is None
    assert seq.on_go is True
    assert xfade.manual is True


def test_sequence_stop_while_paused_without_midi_does_not_deadlock() -> None:
    """Verify Sequence.stop() properly halts a paused transition without MIDI."""
    _app, seq, _patch, _xfade = _build_crossfade_env(tracking_mode=True)

    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))
    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 100}
    seq.add_step(Step(sequence=1, cue=cue1, time_in=10.0, time_out=10.0))
    cue2 = Cue(1, 2.0)
    cue2.channels = {1: 200}
    seq.add_step(Step(sequence=1, cue=cue2, time_in=10.0, time_out=10.0))
    seq.add_step(Step(sequence=1, cue=Cue(0, 0.0)))

    seq.load_step(1)
    seq.do_go(None)
    assert seq.on_go is True
    assert seq.thread is not None

    seq.pause(None, None)
    assert seq.thread.pause.is_set() is False

    # Calling seq.stop() must cleanly stop and join without deadlocking
    stopped = seq.stop()
    assert stopped is True
    assert seq.on_go is False
    assert seq.thread is None
