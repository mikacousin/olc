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
"""Unit tests for OSC control and feedback of Independents (1 to 9)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.core.backends.osc.delegate import OSCDelegate


def test_osc_independent_level_control_and_feedback() -> None:
    """Test controlling an independent level via OSC and receiving feedback."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    inde1 = app.lightshow.independents.independents[0]
    assert inde1.number == 1
    assert inde1.level == 0.0

    # Send OSC normalized level 0.65
    delegate._independent_level("/olc/independent/1/level", [0.65])
    assert inde1.level == 0.65
    mock_engine.publish_osc.assert_any_call(
        "independents", "/olc/independent/1/level", 0.65
    )


def test_osc_independent_button_press_and_release() -> None:
    """Test momentary button control on an independent via OSC."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    inde2 = app.lightshow.independents.independents[1]
    assert inde2.number == 2

    # Press button -> level 1.0
    delegate._independent_button("/olc/independent/2/button", [1])
    assert inde2.level == 1.0
    mock_engine.publish_osc.assert_any_call(
        "independents", "/olc/independent/2/level", 1.0
    )

    # Release button -> level 0.0
    delegate._independent_button("/olc/independent/2/button", [0])
    assert inde2.level == 0.0
    mock_engine.publish_osc.assert_any_call(
        "independents", "/olc/independent/2/level", 0.0
    )


def test_osc_independent_label_feedback() -> None:
    """Test that renaming an independent publishes OSC label feedback."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    _delegate = OSCDelegate(app)

    app.action_registry.execute("independent.rename", 1, "Haze Machine")
    mock_engine.publish_osc.assert_any_call(
        "independents", "/olc/independent/1/label", "Haze Machine"
    )


def test_osc_independent_dump_and_sync() -> None:
    """Test OSC independent dump and inclusion in full sync."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    sender = ("192.168.1.50", 9000)

    # 1. Dump query
    delegate._independent_dump("/olc/independent/dump", [], sender)
    # Check that send_direct was called with valid JSON data
    dump_calls = [
        c[0]
        for c in mock_engine.osc_subscriptions.send_direct.call_args_list
        if len(c[0]) >= 4 and c[0][2] == "/olc/independent/dump"
    ]
    assert len(dump_calls) == 1
    dump_data = json.loads(dump_calls[0][3])
    assert len(dump_data) == 9
    assert dump_data[0]["number"] == 1

    # 2. Full sync includes all 9 independents
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    delegate.send_full_sync(sender)
    direct_calls = mock_engine.osc_subscriptions.send_direct.call_args_list
    direct_addrs = [c[0][2] for c in direct_calls]
    for i in range(1, 10):
        assert f"/olc/independent/{i}/level" in direct_addrs
        assert f"/olc/independent/{i}/label" in direct_addrs
