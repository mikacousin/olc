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
"""Unit tests for independent actions."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication


def test_independent_rename_action() -> None:
    """Test renaming an independent circuit and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received_events = []
    app.subscribe(
        "independent.text_changed",
        lambda number, text: received_events.append((number, text)),
    )

    inde = app.lightshow.independents.independents[0]
    assert inde.number == 1
    assert inde.text == ""

    # Execute Rename
    app.action_registry.execute("independent.rename", 1, "Projecteur Service")
    assert inde.text == "Projecteur Service"
    assert app.lightshow.modified is True
    assert received_events == [(1, "Projecteur Service")]

    # Undo Rename
    app.history.undo()
    assert inde.text == ""

    # Redo Rename
    app.history.redo()
    assert inde.text == "Projecteur Service"


def test_independent_update_channels_action() -> None:
    """Test modifying channels associated with an independent and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received_events = []
    app.subscribe("independent.channels_changed", received_events.append)

    inde = app.lightshow.independents.independents[0]
    assert inde.levels == {}
    assert inde.channels == set()

    # Execute Update Channels
    channels_dict = {5: 255, 6: 128}
    app.action_registry.execute("independent.update_channels", 1, channels_dict)
    assert inde.levels == {5: 255, 6: 128}
    assert inde.channels == {5, 6}
    assert received_events == [1]

    # Undo Update Channels
    app.history.undo()
    assert inde.levels == {}
    assert inde.channels == set()

    # Redo Update Channels
    app.history.redo()
    assert inde.levels == {5: 255, 6: 128}
    assert inde.channels == {5, 6}


def test_independent_set_level_action() -> None:
    """Test setting independent level in real time and validation."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Mock backend
    mock_backend = MagicMock()
    app.backend = mock_backend

    received_events = []
    app.subscribe(
        "independent.level_changed",
        lambda number, level: received_events.append((number, level)),
    )

    inde = app.lightshow.independents.independents[0]
    inde.set_levels({1: 255})
    assert inde.level == 0
    assert inde.dmx[0] == 0

    # Execute set level to 50%
    app.action_registry.execute("independent.set_level", 1, 0.5)
    assert inde.level == 128
    assert inde.dmx[0] == 128
    assert received_events == [(1, 0.5)]

    # Undo should do nothing (can_undo = False)
    app.history.undo()
    assert inde.level == 128
