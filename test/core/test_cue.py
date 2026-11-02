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
"""Unit tests for Cue and CueChannels class."""

import numpy as np
import pytest

from olc.cue import Cue
from olc.files.parsed_data import ParsedData


def test_cue_channels_initialization() -> None:
    """Test that Cue initializes correctly with channels."""
    cue = Cue(sequence=1, number=1.0, channels={1: 100, 2: 200}, text="Test Cue")
    assert cue.sequence == 1
    assert cue.number == 1.0
    assert cue.text == "Test Cue"
    assert cue.channels[1] == 100
    assert cue.channels[2] == 200
    assert cue.channels_array[0] == 100
    assert cue.channels_array[1] == 200
    assert cue.channels_array[2] == 0


def test_cue_channels_setitem() -> None:
    """Test setting item in channels dictionary directly."""
    cue = Cue(sequence=1, number=1.0)
    # Trigger cached array creation
    assert cue.channels_array[4] == 0

    # Modify channel in-place
    cue.channels[5] = 150
    assert cue.channels[5] == 150
    assert cue.channels_array[4] == 150


def test_cue_channels_delitem() -> None:
    """Test deleting item from channels dictionary."""
    cue = Cue(sequence=1, number=1.0, channels={5: 150})
    # Trigger cached array creation
    assert cue.channels_array[4] == 150

    # Delete channel
    del cue.channels[5]
    assert 5 not in cue.channels
    assert cue.channels_array[4] == 0


def test_cue_channels_clear() -> None:
    """Test clearing the channels dictionary."""
    cue = Cue(sequence=1, number=1.0, channels={5: 150, 10: 200})
    assert cue.channels_array[4] == 150
    assert cue.channels_array[9] == 200

    cue.channels.clear()
    assert len(cue.channels) == 0
    assert cue.channels_array[4] == 0
    assert cue.channels_array[9] == 0


def test_cue_channels_update() -> None:
    """Test updating the channels dictionary."""
    cue = Cue(sequence=1, number=1.0, channels={5: 150})
    assert cue.channels_array[4] == 150

    cue.channels.update({5: 200, 10: 250})
    assert cue.channels[5] == 200
    assert cue.channels[10] == 250
    assert cue.channels_array[4] == 200
    assert cue.channels_array[9] == 250


def test_cue_channels_reassignment() -> None:
    """Test reassigning the channels dictionary entirely."""
    cue = Cue(sequence=1, number=1.0, channels={5: 150})
    assert cue.channels_array[4] == 150

    cue.channels = {10: 180}
    assert cue.channels[10] == 180
    assert 5 not in cue.channels
    assert cue.channels_array[4] == 0
    assert cue.channels_array[9] == 180


def test_cue_continuous_float_channels() -> None:
    """Verify that Cue and CueChannels preserve float64 sub-integer levels."""
    cue = Cue(sequence=1, number=1.0, channels={1: 127.5})
    assert isinstance(cue.channels[1], float)
    assert cue.channels[1] == 127.5
    assert cue.channels_array.dtype == np.float64
    assert cue.channels_array[0] == pytest.approx(127.5)

    # In-place float setting
    cue.channels[2] = 63.25
    assert cue.channels_array[1] == pytest.approx(63.25)

    # set_level with float
    cue.set_level(3, 204.8)
    assert cue.channels[3] == pytest.approx(204.8)
    assert cue.channels_array[2] == pytest.approx(204.8)


def test_cue_get_level_fallback_normalized_and_legacy() -> None:
    """Test get_level fallback to device_values intensity
    for normalized and legacy scales.
    """
    cue = Cue(sequence=1, number=1.0)

    # 1. Modern normalized intensity (<= 1.0) -> scaled to 0..255 float
    cue.set_device_parameter(1, "intensity", 0.5)
    assert cue.get_level(1) == pytest.approx(127.5)

    # 2. Legacy 0..255 integer intensity (> 1.0) -> preserved directly
    cue.set_device_parameter(2, "intensity", 200)
    assert cue.get_level(2) == 200

    # 3. Explicit channel overrides fallback
    cue.set_level(1, 100)
    assert cue.get_level(1) == 100


def test_cue_device_values_serialization_and_metadata_sync() -> None:
    """Verify device_values float parameters are preserved across serialization."""
    cue = Cue(sequence=1, number=2.0)
    cue.set_device_parameter(1, "intensity", 0.85)
    cue.set_device_parameter(1, "pan", 145.2)
    cue.set_device_parameter(1, "tilt", -42.8)
    cue.set_device_parameter(1, "color", "#112233")
    cue.is_block = True

    serialized = cue.to_dict()
    assert serialized["device_values"][1]["intensity"] == pytest.approx(0.85)
    assert serialized["device_values"][1]["pan"] == pytest.approx(145.2)
    assert serialized["device_values"][1]["tilt"] == pytest.approx(-42.8)
    assert serialized["device_values"][1]["color"] == "#112233"
    assert serialized["is_block"] is True

    # Deserialize back via ParsedData
    restored_cue = Cue(sequence=1, number=2.0)
    # pylint: disable=protected-access
    ParsedData._apply_cue_metadata(restored_cue, serialized)

    assert restored_cue.device_values[1]["intensity"] == pytest.approx(0.85)
    assert restored_cue.device_values[1]["pan"] == pytest.approx(145.2)
    assert restored_cue.device_values[1]["tilt"] == pytest.approx(-42.8)
    assert restored_cue.device_values[1]["color"] == "#112233"
    assert restored_cue.is_block is True
