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
"""Unit tests for Stage 4: TrackingEngine, cues tracking, and fixture exchange."""
# pylint: disable=too-few-public-methods, missing-class-docstring, missing-function-docstring

import typing

import numpy as np
import pytest

from olc.core.tracking import TrackingEngine
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.devices.builtin import create_moving_head_definition, create_rgb_definition
from olc.patch import PatchCollisionError, PatchManager
from olc.sequence import Sequence
from olc.step import Step


def create_mock_sequence() -> Sequence:
    """Helper to create a Sequence with clean steps."""
    seq = Sequence(index=1, text="Test Sequence")
    seq.steps.clear()
    seq.last = 0
    return seq


def test_conventional_cue_only_vs_tracking() -> None:
    """Verify conventional channel tracking behavior in Cue-Only vs Tracking mode."""
    seq = create_mock_sequence()

    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 255, 2: 128}
    seq.add_step(Step(sequence=1, cue=cue1))

    cue2 = Cue(1, 2.0)
    cue2.channels = {2: 200, 3: 50}
    seq.add_step(Step(sequence=1, cue=cue2))

    # In Cue-Only mode (tracking_mode=False) at Step 1 (Cue 2):
    state_cue_only = TrackingEngine.resolve_step_state(
        seq, step_index=1, tracking_mode=False
    )
    assert state_cue_only.channels[0] == 0  # Channel 1 dropped to 0
    assert state_cue_only.channels[1] == 200  # Channel 2 explicit 200
    assert state_cue_only.channels[2] == 50  # Channel 3 explicit 50

    # In Tracking mode (tracking_mode=True) at Step 1 (Cue 2):
    state_tracking = TrackingEngine.resolve_step_state(
        seq, step_index=1, tracking_mode=True
    )
    assert state_tracking.channels[0] == 255  # Channel 1 tracked from Cue 1
    assert state_tracking.channels[1] == 200  # Channel 2 updated to 200
    assert state_tracking.channels[2] == 50  # Channel 3 explicit 50


def test_conventional_block_cue() -> None:
    """Verify that a Block Cue halts backward tracking of conventional channels."""
    seq = create_mock_sequence()

    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 255, 2: 180}
    seq.add_step(Step(sequence=1, cue=cue1))

    cue2 = Cue(1, 2.0, is_block=True)
    cue2.channels = {2: 90}
    seq.add_step(Step(sequence=1, cue=cue2))

    # At Step 1, even in Tracking mode, Channel 1 must NOT track through Block Cue
    state = TrackingEngine.resolve_step_state(seq, step_index=1, tracking_mode=True)
    assert state.channels[0] == 0  # Blocked by Cue 2
    assert state.channels[1] == 90  # Defined in Cue 2


def test_device_ltp_always_tracked() -> None:
    """Verify that LTP parameters (Pan, Tilt, Color, Zoom) are always tracked."""
    seq = create_mock_sequence()

    cue1 = Cue(1, 1.0)
    cue1.set_device_parameter(1, "pan", 45.0)
    cue1.set_device_parameter(1, "tilt", -20.0)
    cue1.set_device_parameter(1, "color", "#FF0000")
    cue1.set_device_parameter(1, "zoom", 18.0)
    cue1.set_device_parameter(1, "intensity", 1.0)
    seq.add_step(Step(sequence=1, cue=cue1))

    cue2 = Cue(1, 2.0)
    cue2.set_device_parameter(1, "tilt", 30.0)  # Move only tilt
    seq.add_step(Step(sequence=1, cue=cue2))

    # In Cue-Only mode: LTP parameters remain tracked, intensity drops to 0
    state_cue_only = TrackingEngine.resolve_step_state(
        seq, step_index=1, tracking_mode=False
    )
    dev1_co = state_cue_only.device_values[1]
    assert dev1_co["pan"] == 45.0  # LTP tracked
    assert dev1_co["tilt"] == 30.0  # Explicit move
    assert dev1_co["color"] == "#FF0000"  # LTP tracked
    assert dev1_co["zoom"] == 18.0  # LTP tracked
    assert dev1_co["intensity"] == 0.0  # Cue-only drops unassigned intensity to 0.0

    # In Tracking mode: LTP parameters remain tracked AND intensity is tracked
    state_tracking = TrackingEngine.resolve_step_state(
        seq, step_index=1, tracking_mode=True
    )
    dev1_tr = state_tracking.device_values[1]
    assert dev1_tr["pan"] == 45.0
    assert dev1_tr["tilt"] == 30.0
    assert dev1_tr["color"] == "#FF0000"
    assert dev1_tr["zoom"] == 18.0
    assert dev1_tr["intensity"] == 1.0  # Intensity tracked


def test_device_hard_zero_intensity() -> None:
    """Verify that an explicit 0% intensity (Hard Zero) stops intensity tracking."""
    seq = create_mock_sequence()

    cue1 = Cue(1, 1.0)
    cue1.set_device_parameter(1, "intensity", 0.8)
    cue1.set_device_parameter(1, "pan", 90.0)
    seq.add_step(Step(sequence=1, cue=cue1))

    cue2 = Cue(1, 2.0)
    cue2.set_device_parameter(1, "intensity", 0.0)  # Hard zero
    seq.add_step(Step(sequence=1, cue=cue2))

    cue3 = Cue(1, 3.0)
    cue3.set_device_parameter(1, "pan", 120.0)  # Pan move, no intensity specified
    seq.add_step(Step(sequence=1, cue=cue3))

    state = TrackingEngine.resolve_step_state(seq, step_index=2, tracking_mode=True)
    dev1 = state.device_values[1]
    assert dev1["pan"] == 120.0
    assert dev1["intensity"] == 0.0  # Preserves Hard Zero from Cue 2


def test_device_block_cue_halts_ltp() -> None:
    """Verify that Block Cues prevent earlier LTP attributes from tracking through."""
    seq = create_mock_sequence()

    cue1 = Cue(1, 1.0)
    cue1.set_device_parameter(1, "pan", 55.0)
    cue1.set_device_parameter(1, "tilt", 25.0)
    seq.add_step(Step(sequence=1, cue=cue1))

    cue2 = Cue(1, 2.0, is_block=True)
    # dev 1 defines tilt only; pan is omitted
    cue2.set_device_parameter(1, "tilt", -10.0)
    seq.add_step(Step(sequence=1, cue=cue2))

    state = TrackingEngine.resolve_step_state(seq, step_index=1, tracking_mode=False)
    dev1 = state.device_values[1]
    assert dev1["tilt"] == -10.0
    assert dev1["pan"] == 0.0  # Halted by block cue, returns default 0.0


def test_patch_manager_exchange_fixture_preserves_cues() -> None:
    """Verify fixture exchange preserves cues and recalculates native DMX channels."""
    pm = PatchManager(universes=[1, 2])
    pm.patch_empty()
    mh_def = create_moving_head_definition()
    dev1 = pm.patch_device(
        device_id=1,
        fixture_def=mh_def,
        universe=1,
        address=1,
        label="Spot 1",
    )

    # Cue stores physical degree values
    cue1 = Cue(1, 1.0)
    cue1.set_device_parameter(1, "pan", 135.0)  # 135° on [-270..270] -> norm 0.75
    cue1.set_device_parameter(1, "tilt", 45.0)  # 45° on [-135..135]  -> norm ~0.6667
    cue1.set_device_parameter(1, "intensity", 1.0)

    # Apply to device 1
    dev1.apply_device_values(cue1.device_values[1])
    assert dev1.intensity == 1.0
    assert pytest.approx(dev1.pan_degrees, abs=0.1) == 135.0
    assert pytest.approx(dev1.tilt_degrees, abs=0.1) == 45.0

    # Exchange fixture with RGB PAR (different footprint and parameters)
    rgb_def = create_rgb_definition()
    new_dev = pm.exchange_fixture(
        device_id=1,
        new_fixture_def=rgb_def,
        force=True,
    )

    assert pm.get_device(1) is new_dev
    assert new_dev.fixture_id == 1

    # Apply the same cue to the new fixture without any cue modification
    new_dev.apply_device_values(cue1.device_values[1])
    assert new_dev.intensity == 1.0


def test_patch_manager_exchange_collision_detection() -> None:
    """Verify collision handling during fixture exchange."""
    pm = PatchManager(universes=[1])
    pm.patch_empty()
    rgb_def = create_rgb_definition()  # Footprint 3

    # Patch dev 1 at 1..3, dev 2 at 4..6
    pm.patch_device(1, rgb_def, 1, 1)
    pm.patch_device(2, rgb_def, 1, 4)

    # Moving head footprint is 16 channels. Exchanging at 1 collides with dev 2 at 4
    mh_def = create_moving_head_definition()
    with pytest.raises(PatchCollisionError) as exc_info:
        pm.exchange_fixture(1, mh_def, force=False)
    assert exc_info.value.colliding_device_id == 2

    # With force=True, dev 2 is unpatched and exchange succeeds
    new_dev = pm.exchange_fixture(1, mh_def, force=True)
    assert pm.get_device(1) is new_dev
    assert pm.get_device(2) is None


def test_sequence_load_step_integration() -> None:
    """Verify Sequence.load_step resolves and applies state to patched devices."""

    class MockDmx:
        def __init__(self) -> None:
            self.levels = {
                "sequence": np.zeros(MAX_CHANNELS, dtype=np.uint8),
                "user": np.full(MAX_CHANNELS, -1, dtype=np.int32),
            }
            self.set_levels_called = False

        def set_levels(self) -> None:
            self.set_levels_called = True

    class MockBackend:
        def __init__(self) -> None:
            self.dmx = MockDmx()

    class MockApp:
        def __init__(self, backend: MockBackend) -> None:
            self.backend = backend

    class MockLightShow:
        def __init__(self, patch: PatchManager, backend: MockBackend) -> None:
            self.patch = patch
            self.app = MockApp(backend)

    pm = PatchManager(universes=[1])
    pm.patch_empty()
    mh_def = create_moving_head_definition()
    dev = pm.patch_device(1, mh_def, 1, 1)

    backend = MockBackend()
    lightshow: typing.Any = MockLightShow(pm, backend)
    seq = Sequence(index=1, text="Playback", lightshow=lightshow)
    seq.steps.clear()

    # Step 0: Base position
    cue0 = Cue(1, 1.0)
    cue0.channels = {10: 100}
    cue0.set_device_parameter(1, "pan", 45.0)
    cue0.set_device_parameter(1, "intensity", 0.5)
    seq.add_step(Step(sequence=1, cue=cue0))

    # Step 1: Pan moves, intensity omitted
    cue1 = Cue(1, 2.0)
    cue1.channels = {20: 200}
    cue1.set_device_parameter(1, "pan", 90.0)
    seq.add_step(Step(sequence=1, cue=cue1))

    # Load Step 1 in Cue-Only mode
    seq.tracking_mode = False
    seq.load_step(1)

    assert seq.backend.dmx.levels["sequence"][9] == 0  # Channel 10 dropped in Cue-Only
    assert seq.backend.dmx.levels["sequence"][19] == 200  # Channel 20 loaded
    assert pytest.approx(dev.pan_degrees, abs=0.5) == 90.0
    assert dev.intensity == 0.0  # Intensity dropped in Cue-Only

    # Load Step 1 in Tracking mode
    seq.tracking_mode = True
    seq.load_step(1)

    assert seq.backend.dmx.levels["sequence"][9] == 100  # Channel 10 tracked
    assert seq.backend.dmx.levels["sequence"][19] == 200  # Channel 20 loaded
    assert pytest.approx(dev.pan_degrees, abs=0.5) == 90.0
    assert dev.intensity == 0.5  # Intensity tracked
