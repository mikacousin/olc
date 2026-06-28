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
"""Unit tests for GUI actions."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from olc.core.app import CoreApplication


def test_zoom_action() -> None:
    """Test ZoomAction and its undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received_events = []
    app.subscribe("gui.zoom_changed", received_events.append)

    assert app.zoom_level == 1.0

    # Execute Zoom
    app.action_registry.execute("gui.zoom", 1.5)
    assert app.zoom_level == 1.5
    assert received_events == [1.5]

    # Undo
    app.history.undo()
    assert app.zoom_level == 1.0
    assert received_events == [1.5, 1.0]

    # Redo
    app.history.redo()
    assert app.zoom_level == 1.5
    assert received_events == [1.5, 1.0, 1.5]


def test_switch_tab_action() -> None:
    """Test SwitchTabAction and its undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received_events = []
    app.subscribe("gui.active_tab_changed", received_events.append)

    assert app.active_tab == "channels"

    # Execute switch
    app.action_registry.execute("gui.switch_tab", "patch_outputs")
    assert app.active_tab == "patch_outputs"
    assert received_events == ["patch_outputs"]

    # Undo
    app.history.undo()
    assert app.active_tab == "channels"
    assert received_events == ["patch_outputs", "channels"]

    # Redo
    app.history.redo()
    assert app.active_tab == "patch_outputs"
    assert received_events == ["patch_outputs", "channels", "patch_outputs"]


def test_zoom_debouncing() -> None:
    """Test zoom debouncing mechanism."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Trigger zoom twice quickly
    app.zoom("in")
    app.zoom("in")

    assert app.zoom_level == 1.1

    # Wait for timer to expire (0.6s + safety margin)
    time.sleep(0.8)

    # Should have committed a single action in the history
    assert app.zoom_level == 1.1

    # Test Undo of the debounced zoom action
    app.history.undo()
    assert app.zoom_level == 1.0
