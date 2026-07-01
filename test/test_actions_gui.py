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


def test_tab_actions() -> None:
    """Test tab management actions (open, close, move) and their undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    assert app.tabs.active_tabs["playback"] == "playback"
    assert app.tabs.notebooks["playback"] == ["playback"]

    # 1. Execute tab_open for "patch_outputs"
    app.action_registry.execute("gui.tab_open", "patch_outputs", "playback")
    assert app.tabs.active_tabs["playback"] == "patch_outputs"
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs"]

    # Undo open (should close it and revert active tab to "playback")
    app.history.undo()
    assert app.tabs.active_tabs["playback"] == "playback"
    assert app.tabs.notebooks["playback"] == ["playback"]

    # Redo open
    app.history.redo()
    assert app.tabs.active_tabs["playback"] == "patch_outputs"
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs"]

    # 2. Open another tab "memories"
    app.action_registry.execute("gui.tab_open", "memories", "playback")
    assert app.tabs.active_tabs["playback"] == "memories"
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs", "memories"]

    # 3. Move "memories" within same notebook to index 0
    app.action_registry.execute("gui.tab_move", "memories", "playback", "playback", 0)
    assert app.tabs.notebooks["playback"] == ["memories", "playback", "patch_outputs"]

    # Undo move
    app.history.undo()
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs", "memories"]

    # Redo move
    app.history.redo()
    assert app.tabs.notebooks["playback"] == ["memories", "playback", "patch_outputs"]

    # 4. Close "memories"
    app.action_registry.execute("gui.tab_close", "memories")
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs"]
    assert app.tabs.active_tabs["playback"] == "playback"

    # Undo close
    app.history.undo()
    assert app.tabs.notebooks["playback"] == ["memories", "playback", "patch_outputs"]
    assert app.tabs.active_tabs["playback"] == "memories"

    # 5. Move "memories" between notebooks (playback to live)
    assert app.tabs.notebooks["live"] == ["channels"]
    assert app.tabs.active_tabs["live"] == "channels"

    app.action_registry.execute("gui.tab_move", "memories", "playback", "live", 0)
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs"]
    assert app.tabs.active_tabs["playback"] == "playback"
    assert app.tabs.notebooks["live"] == ["memories", "channels"]
    assert app.tabs.active_tabs["live"] == "memories"

    # Undo move between notebooks
    app.history.undo()
    assert app.tabs.notebooks["playback"] == ["memories", "playback", "patch_outputs"]
    assert app.tabs.active_tabs["playback"] == "memories"
    assert app.tabs.notebooks["live"] == ["channels"]
    assert app.tabs.active_tabs["live"] == "channels"

    # Redo move between notebooks
    app.history.redo()
    assert app.tabs.notebooks["playback"] == ["playback", "patch_outputs"]
    assert app.tabs.active_tabs["playback"] == "playback"
    assert app.tabs.notebooks["live"] == ["memories", "channels"]
    assert app.tabs.active_tabs["live"] == "memories"


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
