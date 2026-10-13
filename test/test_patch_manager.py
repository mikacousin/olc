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
"""Unit tests for the unified PatchManager, collision detection, and routing."""
# pylint: disable=import-outside-toplevel

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch as mock_patch

import pytest

from olc.core.app import CoreApplication
from olc.devices.builtin import (
    create_moving_head_definition,
)
from olc.dmx import Dmx
from olc.patch import PatchCollisionError, PatchManager


def test_patch_manager_initialization() -> None:
    """Test default initialization with empty patch and explicit 1:1 patch."""
    pm = PatchManager(universes=[1, 2])
    assert pm.universes == [1, 2]
    # Default patch is empty
    assert not pm.is_patched(1)
    assert pm.get_address_occupant(1, 1) is None
    assert pm.is_address_free(1, 1)
    assert len(pm.outputs) == 0
    assert len(pm.devices) == 0

    # Explicit 1:1 patch
    pm.patch_1on1()
    assert pm.is_patched(1)
    assert pm.get_address_occupant(1, 1) == 1
    assert pm.get_address_occupant(1, 512) == 512
    assert not pm.is_address_free(1, 1)
    assert pm.get_first_patched_channel() == 1
    assert pm.get_last_patched_channel() == 1024


def test_patch_dimmer_8bit_and_16bit() -> None:
    """Test patching standard and 16-bit dimmers."""
    pm = PatchManager(universes=[1])
    pm.patch_empty()
    assert len(pm.devices) == 0

    # 1. Patch 8-bit dimmer on channel 5, address 10, curve 3
    dev1 = pm.patch_dimmer(channel=5, universe=1, address=10, curve=3)
    assert dev1.fixture_id == 5
    assert pm.get_address_occupant(1, 10) == 5
    assert not pm.is_address_free(1, 10)
    assert pm.outputs[1][10] == [5, 3]
    assert pm.channels[5] == [[10, 1]]

    # 2. Patch 16-bit dimmer on channel 6, address 20
    dev2 = pm.patch_dimmer(channel=6, universe=1, address=20, fine=True)
    assert dev2.fixture_id == 6
    assert dev2.has_16bit_dimmer
    assert pm.get_address_occupant(1, 20) == 6
    assert pm.get_address_occupant(1, 21) == 6


def test_patch_device_moving_head() -> None:
    """Test patching a multi-parameter fixture."""
    pm = PatchManager(universes=[1, 2])
    pm.patch_empty()

    mh_def = create_moving_head_definition()
    dev = pm.patch_device(
        device_id=101,
        fixture_def=mh_def,
        universe=1,
        address=100,
        label="Spot 1",
    )
    assert dev.fixture_id == 101
    assert dev.channel_count() == 8
    # Addresses 100 to 107 should be occupied by 101
    for addr in range(100, 108):
        assert pm.get_address_occupant(1, addr) == 101
        assert not pm.is_address_free(1, addr)
    assert pm.is_address_free(1, 99)
    assert pm.is_address_free(1, 108)


def test_collision_detection_and_prevention() -> None:
    """Test collision detection and error raising."""
    pm = PatchManager(universes=[1])
    pm.patch_empty()

    mh_def = create_moving_head_definition()
    pm.patch_device(device_id=1, fixture_def=mh_def, universe=1, address=10)

    # Collision overlapping at start
    with pytest.raises(PatchCollisionError) as exc_info:
        pm.patch_device(device_id=2, fixture_def=mh_def, universe=1, address=15)
    assert exc_info.value.universe == 1
    assert exc_info.value.address == 15
    assert exc_info.value.colliding_device_id == 1
    assert exc_info.value.new_device_id == 2

    # Collision overlapping at boundary (address 17 is the last channel of device 1)
    with pytest.raises(PatchCollisionError):
        pm.patch_dimmer(channel=3, universe=1, address=17)

    # Free address right after (address 18)
    pm.patch_dimmer(channel=3, universe=1, address=18)
    assert pm.get_address_occupant(1, 18) == 3

    # Force patch should overwrite collision
    pm.patch_dimmer(channel=4, universe=1, address=12, force=True)
    assert pm.get_address_occupant(1, 12) == 4
    # The previous fixture 1 was unpatched due to the collision overwrite
    assert pm.get_device(1) is None


def test_auto_patch_sequential() -> None:
    """Test auto_patch across multiple devices and universe overflow."""
    pm = PatchManager(universes=[1, 2])
    pm.patch_empty()

    mh_def = create_moving_head_definition()
    # 3 moving heads (8 channels each) starting at universe 1 address 1
    patched = pm.auto_patch(
        device_ids=[1, 2, 3],
        fixture_def=mh_def,
        start_universe=1,
        start_address=1,
    )
    assert len(patched) == 3
    # Device 1: 1-8
    assert patched[0].footprint()[1] == (1, 8)
    # Device 2: 9-16
    assert patched[1].footprint()[1] == (9, 16)
    # Device 3: 17-24
    assert patched[2].footprint()[1] == (17, 24)

    # Overflow case: start at 508 (508 + 8 = 515 > 512)
    # Should wrap to universe 2 address 1
    patched_overflow = pm.auto_patch(
        device_ids=[4],
        fixture_def=mh_def,
        start_universe=1,
        start_address=508,
    )
    assert patched_overflow[0].footprint()[2] == (1, 8)


def test_unpatch_device_and_address() -> None:
    """Test unpatching devices and specific addresses."""
    pm = PatchManager(universes=[1])
    pm.patch_empty()

    mh_def = create_moving_head_definition()
    pm.patch_device(device_id=10, fixture_def=mh_def, universe=1, address=50)
    assert not pm.is_address_free(1, 50)

    # Unpatch device
    removed = pm.unpatch_device(10)
    assert removed is not None
    assert removed.fixture_id == 10
    assert pm.is_address_free(1, 50)
    assert pm.get_device(10) is None

    # Patch and unpatch by address
    pm.patch_device(device_id=20, fixture_def=mh_def, universe=1, address=50)
    unpatched_id = pm.unpatch_address(1, 55)
    assert unpatched_id == 20
    assert pm.is_address_free(1, 50)


def test_patch_actions_device_undo_redo() -> None:
    """Test patch.device and patch.unpatch_device actions with Undo/Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch
    patch.patch_empty()

    mh_def = create_moving_head_definition()

    # 1. Execute patch.device
    app.action_registry.execute(
        "patch.device",
        device_id=42,
        fixture_def=mh_def,
        universe=1,
        address=100,
        label="MySpot",
    )
    assert patch.has_device(42)
    assert patch.get_address_occupant(1, 100) == 42

    # 2. Undo
    app.history.undo()
    assert not patch.has_device(42)
    assert patch.is_address_free(1, 100)

    # 3. Redo
    app.history.redo()
    assert patch.has_device(42)
    assert patch.get_address_occupant(1, 100) == 42

    # 4. Unpatch device action
    app.action_registry.execute("patch.unpatch_device", device_id=42)
    assert not patch.has_device(42)

    # Undo unpatch
    app.history.undo()
    assert patch.has_device(42)
    assert patch.get_address_occupant(1, 100) == 42


def test_engine_vectorized_levels_with_devices() -> None:
    """Test fast vector distribution in Dmx engine with multi-parameter devices."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch
    patch.patch_empty()

    # 1. Patch a dimmer on ch 1, addr 1
    patch.patch_dimmer(channel=1, universe=1, address=1)
    # 2. Patch a moving head on id 2, addr 10 (8 channels)
    mh_def = create_moving_head_definition()
    spot = patch.patch_device(device_id=2, fixture_def=mh_def, universe=1, address=10)

    # Set pan to 16-bit value: 0x1234
    spot.set_pan_16bit(0x1234)

    with mock_patch("olc.dmx.RepeatedTimer"):
        dmx = Dmx(backend=None, lightshow=app.lightshow)
        # Set dimmer level for ch 1 to 200
        dmx.levels["sequence"][0] = 200

        # Call set_levels()
        dmx.set_levels()

        # Check universe 1 frame:
        # addr 1 (index 0) = dimmer = 200
        assert dmx.frame[0][0] == 200
        # addr 10 (index 9) = pan coarse = 0x12
        assert dmx.frame[0][9] == 0x12
        # addr 11 (index 10) = pan fine = 0x34
        assert dmx.frame[0][10] == 0x34


def test_patch_clear_and_set_1on1_undo_preserves_multi_param_devices() -> None:
    """Test undo of patch.clear and patch.set_1on1 restores multi-param devices."""
    from olc.devices.builtin import create_rgbw_definition

    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch
    patch.patch_empty()

    mh_def = create_moving_head_definition()
    rgbw_def = create_rgbw_definition()

    patch.patch_device(
        device_id=42, fixture_def=mh_def, universe=1, address=100, label="Spot 42"
    )
    patch.patch_device(
        device_id=10, fixture_def=rgbw_def, universe=1, address=20, label="Wash 10"
    )

    # 1. patch.clear and undo
    app.action_registry.execute("patch.clear")
    assert not patch.has_device(42)
    assert not patch.has_device(10)

    app.history.undo()
    assert patch.has_device(42)
    assert patch.has_device(10)
    dev42 = patch.get_device(42)
    assert dev42 is not None
    assert dev42.label == "Spot 42"
    assert dev42.channel_count() == 8

    # 2. patch.set_1on1 and undo
    app.action_registry.execute("patch.set_1on1")
    app.history.undo()
    dev42_after = patch.get_device(42)
    dev10_after = patch.get_device(10)
    assert dev42_after is not None
    assert dev42_after.label == "Spot 42"
    assert dev42_after.channel_count() == 8
    assert dev10_after is not None
    assert dev10_after.label == "Wash 10"
    assert dev10_after.uses_virtual_dimmer is True


# pylint: disable=too-many-locals
def test_fixture_exchange_clamping_warning() -> None:
    """Test detection of clamped cue parameters when exchanging fixture profiles."""
    from olc.cue import Cue
    from olc.devices.device import ChannelType, FixtureType
    from olc.devices.fixture import (
        ChannelDefinition,
        DmxModeDefinition,
        FixtureDefinition,
    )
    from olc.patch import FixtureExchangeWarning
    from olc.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch
    patch.patch_empty()

    # Original moving head has Pan [-270°..270°], Tilt [-135°..135°]
    orig_mh_def = create_moving_head_definition()
    patch.patch_device(
        device_id=1,
        fixture_def=orig_mh_def,
        universe=1,
        address=1,
        label="Main Spot",
    )

    # Cue 1.0 has Pan = 250.0°, Tilt = 45.0°, Zoom = 20.0°
    cue1 = Cue(1, 1.0, channels={1: 255})
    cue1.set_device_parameter(1, "pan", 250.0)
    cue1.set_device_parameter(1, "tilt", 45.0)
    cue1.set_device_parameter(1, "zoom", 20.0)
    step1 = Step(1, cue=cue1)
    app.lightshow.cues.add(cue1)
    app.lightshow.main_playback.insert_step(1, step1)

    # Compact moving head profile with Pan [-180°..180°] and Zoom [15°..25°]
    compact_mode = DmxModeDefinition(
        name="Compact 4ch",
        channel_defs=[
            ChannelDefinition(
                ChannelType.PAN,
                offset=0,
                physical_min=-180.0,
                physical_max=180.0,
                physical_unit="deg",
            ),
            ChannelDefinition(
                ChannelType.TILT,
                offset=1,
                physical_min=-135.0,
                physical_max=135.0,
                physical_unit="deg",
            ),
            ChannelDefinition(
                ChannelType.ZOOM,
                offset=2,
                physical_min=15.0,
                physical_max=25.0,
                physical_unit="deg",
            ),
            ChannelDefinition(
                ChannelType.INTENSITY,
                offset=3,
                physical_min=0.0,
                physical_max=1.0,
            ),
        ],
    )
    compact_fdef = FixtureDefinition(
        manufacturer="Generic",
        model="Compact Spot",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[compact_mode],
    )

    # 1. Preview check
    warnings = patch.check_clamped_cue_parameters(1, compact_fdef, "Compact 4ch")
    assert len(warnings) == 1
    w = warnings[0]
    assert isinstance(w, FixtureExchangeWarning)
    assert w.device_id == 1
    assert w.cue_number == 1.0
    assert w.parameter == "pan"
    assert w.original_value == pytest.approx(250.0)
    assert w.clamped_value == pytest.approx(180.0)
    assert w.physical_min == pytest.approx(-180.0)
    assert w.physical_max == pytest.approx(180.0)
    assert "écrêté à 180" in w.format_message()

    # 2. Exchange fixture and event emission
    received_events: list[tuple[object, list[FixtureExchangeWarning]]] = []
    app.subscribe(
        "patch.fixture_exchanged",
        lambda dev, warns: received_events.append((dev, warns)),
    )

    new_dev = patch.exchange_fixture(1, compact_fdef, force=True)
    assert len(patch.last_exchange_warnings) == 1
    assert len(received_events) == 1
    event_dev, event_warns = received_events[0]
    assert event_dev is new_dev
    assert len(event_warns) == 1

    # 3. Verify non-destructive cue preservation: cue still holds 250.0°
    assert cue1.device_values[1]["pan"] == pytest.approx(250.0)

    # 4. Applying to new device clamps to 180.0°
    new_dev.apply_device_values(cue1.device_values[1])
    assert new_dev.pan_degrees == pytest.approx(180.0)
