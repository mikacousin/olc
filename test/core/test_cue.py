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

from olc.cue import Cue


def test_cue_channels_initialization() -> None:
    """Test that Cue initializes correctly with channels."""
    cue = Cue(sequence=1, memory=1.0, channels={1: 100, 2: 200}, text="Test Cue")
    assert cue.sequence == 1
    assert cue.memory == 1.0
    assert cue.text == "Test Cue"
    assert cue.channels[1] == 100
    assert cue.channels[2] == 200
    assert cue.channels_array[0] == 100
    assert cue.channels_array[1] == 200
    assert cue.channels_array[2] == 0


def test_cue_channels_setitem() -> None:
    """Test setting item in channels dictionary directly."""
    cue = Cue(sequence=1, memory=1.0)
    # Trigger cached array creation
    assert cue.channels_array[4] == 0

    # Modify channel in-place
    cue.channels[5] = 150
    assert cue.channels[5] == 150
    assert cue.channels_array[4] == 150


def test_cue_channels_delitem() -> None:
    """Test deleting item from channels dictionary."""
    cue = Cue(sequence=1, memory=1.0, channels={5: 150})
    # Trigger cached array creation
    assert cue.channels_array[4] == 150

    # Delete channel
    del cue.channels[5]
    assert 5 not in cue.channels
    assert cue.channels_array[4] == 0


def test_cue_channels_clear() -> None:
    """Test clearing the channels dictionary."""
    cue = Cue(sequence=1, memory=1.0, channels={5: 150, 10: 200})
    assert cue.channels_array[4] == 150
    assert cue.channels_array[9] == 200

    cue.channels.clear()
    assert len(cue.channels) == 0
    assert cue.channels_array[4] == 0
    assert cue.channels_array[9] == 0


def test_cue_channels_update() -> None:
    """Test updating the channels dictionary."""
    cue = Cue(sequence=1, memory=1.0, channels={5: 150})
    assert cue.channels_array[4] == 150

    cue.channels.update({5: 200, 10: 250})
    assert cue.channels[5] == 200
    assert cue.channels[10] == 250
    assert cue.channels_array[4] == 200
    assert cue.channels_array[9] == 250


def test_cue_channels_reassignment() -> None:
    """Test reassigning the channels dictionary entirely."""
    cue = Cue(sequence=1, memory=1.0, channels={5: 150})
    assert cue.channels_array[4] == 150

    cue.channels = {10: 180}
    assert cue.channels[10] == 180
    assert 5 not in cue.channels
    assert cue.channels_array[4] == 0
    assert cue.channels_array[9] == 180
