# -*- coding: utf-8 -*-
"""Unit tests for ParkManager and DMX park processing."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.core.park import ParkManager
from olc.dmx import Dmx


def test_park_manager_channels() -> None:
    mgr = ParkManager()
    assert mgr.total_parked_count() == 0
    assert not mgr.is_channel_parked(1)

    mgr.park_channel(1, 200)
    mgr.park_channel(5, 300)  # Should clamp to 255
    mgr.park_channel(10, -50)  # Should clamp to 0

    assert mgr.is_channel_parked(1)
    assert mgr.get_channel_park_level(1) == 200
    assert mgr.get_channel_park_level(5) == 255
    assert mgr.get_channel_park_level(10) == 0
    assert mgr.total_parked_count() == 3

    old_val = mgr.unpark_channel(1)
    assert old_val == 200
    assert not mgr.is_channel_parked(1)
    assert mgr.total_parked_count() == 2


def test_park_manager_addresses() -> None:
    mgr = ParkManager()
    mgr.park_address(1, 12, 128)
    mgr.park_address(2, 512, 255)

    assert mgr.is_address_parked(1, 12)
    assert mgr.get_address_park_level(1, 12) == 128
    assert mgr.is_address_parked(2, 512)
    assert not mgr.is_address_parked(1, 13)
    assert mgr.total_parked_count() == 2

    old_val = mgr.unpark_address(1, 12)
    assert old_val == 128
    assert not mgr.is_address_parked(1, 12)


def test_park_manager_unpark_all_and_dict() -> None:
    mgr = ParkManager()
    mgr.park_channel(1, 255)
    mgr.park_channel(2, 100)
    mgr.park_address(1, 10, 50)

    data = mgr.to_dict()
    assert data["channels"] == {"1": 255, "2": 100}
    assert data["addresses"] == {"1/10": 50}

    old_chans, old_addrs = mgr.unpark_all()
    assert old_chans == {1: 255, 2: 100}
    assert old_addrs == {(1, 10): 50}
    assert mgr.total_parked_count() == 0

    # Restore from dict
    mgr.from_dict(data)
    assert mgr.get_channel_park_level(1) == 255
    assert mgr.get_channel_park_level(2) == 100
    assert mgr.get_address_park_level(1, 10) == 50
    assert mgr.total_parked_count() == 3


def test_dmx_composite_with_park() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    ls = app.lightshow
    dmx = Dmx(backend=None, lightshow=ls)

    # Initial levels
    comp = dmx.get_all_composite_levels()
    assert comp[0] == 0

    # Park channel 1 at 200
    ls.park.park_channel(1, 200)

    comp = dmx.get_all_composite_levels()
    assert comp[0] == 200

    level, color = dmx.get_composite_level(0)
    assert level == 200
    assert color == {"red": 1.0, "green": 0.7, "blue": 0.0}

    # Verify Blackout immunity
    dmx.blackout = True
    dmx.set_levels()

    # Channel 1 is mapped to universe 1 output 1 by default patch (if patched)
    if ls.patch.is_patched(1):
        # Even with blackout, parked channel frame output must remain 200
        assert dmx.frame[0][0] == 200

    # Test address park
    ls.park.park_address(1, 50, 175)
    dmx.set_levels()
    assert dmx.frame[0][49] == 175
