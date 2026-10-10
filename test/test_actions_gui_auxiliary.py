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
"""Unit tests for auxiliary window GUI actions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.gtk3.event_bridge import GuiEventBridge


def test_open_virtual_console_action() -> None:
    """Test gui.open_virtual_console action execution and event emission."""
    settings = MagicMock()
    app = CoreApplication(settings)

    events: list[bool] = []

    def on_requested() -> None:
        events.append(True)

    app.subscribe("gui.virtual_console_requested", on_requested)

    action = app.action_registry.get("gui.open_virtual_console")
    assert action is not None
    assert action.can_undo is False

    app.action_registry.execute("gui.open_virtual_console")
    assert events == [True]
    # Non-undoable action does not add to undo history
    assert len(app.history.undo_stack) == 0


def test_toggle_fullscreen_action() -> None:
    """Test gui.toggle_fullscreen action execution and event emission."""
    settings = MagicMock()
    app = CoreApplication(settings)

    events: list[bool] = []

    def on_requested() -> None:
        events.append(True)

    app.subscribe("gui.fullscreen_toggle_requested", on_requested)

    action = app.action_registry.get("gui.toggle_fullscreen")
    assert action is not None
    assert action.can_undo is False

    app.action_registry.execute("gui.toggle_fullscreen")
    assert events == [True]
    assert len(app.history.undo_stack) == 0


def test_open_shortcuts_action() -> None:
    """Test gui.open_shortcuts action execution and event emission."""
    settings = MagicMock()
    app = CoreApplication(settings)

    events: list[bool] = []

    def on_requested() -> None:
        events.append(True)

    app.subscribe("gui.shortcuts_requested", on_requested)

    action = app.action_registry.get("gui.open_shortcuts")
    assert action is not None
    assert action.can_undo is False

    app.action_registry.execute("gui.open_shortcuts")
    assert events == [True]
    assert len(app.history.undo_stack) == 0


def test_open_about_action() -> None:
    """Test gui.open_about action execution and event emission."""
    settings = MagicMock()
    app = CoreApplication(settings)

    events: list[bool] = []

    def on_requested() -> None:
        events.append(True)

    app.subscribe("gui.about_requested", on_requested)

    action = app.action_registry.get("gui.open_about")
    assert action is not None
    assert action.can_undo is False

    app.action_registry.execute("gui.open_about")
    assert events == [True]
    assert len(app.history.undo_stack) == 0


def test_event_bridge_auxiliary_windows_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test GuiEventBridge correctly routes auxiliary window requests to app methods."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))

    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core
    mock_app.window = MagicMock()

    _bridge = GuiEventBridge(mock_app)

    # 1. Virtual Console
    core.emit("gui.virtual_console_requested")
    mock_app.open_virtual_console.assert_called_once()

    # 2. Full screen toggle
    core.emit("gui.fullscreen_toggle_requested")
    mock_app.window.fullscreen_toggle.assert_called_once_with()

    # 3. Shortcuts
    core.emit("gui.shortcuts_requested")
    mock_app.open_shortcuts.assert_called_once()

    # 4. About
    core.emit("gui.about_requested")
    mock_app.open_about.assert_called_once()
