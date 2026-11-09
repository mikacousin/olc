# -*- coding: utf-8 -*-
"""Unit tests for park state persistence and OSC integration."""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.core.backends.osc.delegate import OSCDelegate


def test_park_show_persistence() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)

    # 1. Park channels and addresses
    app.action_registry.execute("channel.park", [1, 5], 200)
    app.action_registry.execute("address.park", (1, 15), 180)
    assert app.lightshow.park.total_parked_count() == 3

    # 2. Save show to temporary file
    with tempfile.NamedTemporaryFile(suffix=".olc") as tmp:
        app.action_registry.execute("show.save", tmp.name)

        # 3. Create fresh app and load show
        app2 = CoreApplication(settings)
        assert app2.lightshow.park.total_parked_count() == 0

        app2.action_registry.execute("show.open", tmp.name)
        assert app2.lightshow.park.total_parked_count() == 3
        assert app2.lightshow.park.get_channel_park_level(1) == 200
        assert app2.lightshow.park.get_channel_park_level(5) == 200
        assert app2.lightshow.park.get_address_park_level(1, 15) == 180

        # 4. show.new resets park
        app2.action_registry.execute("show.new")
        assert app2.lightshow.park.total_parked_count() == 0


def test_osc_delegate_park_endpoints() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    app.engine = MagicMock()

    delegate = OSCDelegate(app)

    # Call /olc/channel/7/park with level 0.8
    delegate._channel_park("/olc/channel/7/park", [0.8])
    assert app.lightshow.park.is_channel_parked(7)
    assert app.lightshow.park.get_channel_park_level(7) == 204

    # Call /olc/address/1/20/park with level 0.5
    delegate._address_park("/olc/address/1/20/park", [0.5])
    assert app.lightshow.park.is_address_parked(1, 20)
    assert app.lightshow.park.get_address_park_level(1, 20) == 128

    # Call /olc/channel/7/unpark
    delegate._channel_unpark("/olc/channel/7/unpark", [])
    assert not app.lightshow.park.is_channel_parked(7)

    # Call /olc/park/unpark_all
    delegate._park_unpark_all("/olc/park/unpark_all", [])
    assert app.lightshow.park.total_parked_count() == 0
