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
"""Unit tests for GUI preference actions and Undo/Redo."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from olc.core.app import CoreApplication
from olc.gtk3.event_bridge import GuiEventBridge
from olc.settings import SettingsTab


def test_set_theme_action_and_undo_redo() -> None:
    """Test gui.set_theme action execution, Undo, and Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    events: list[bool] = []

    def on_theme_changed(dark_theme: bool) -> None:
        events.append(dark_theme)

    app.subscribe("gui.theme_changed", on_theme_changed)

    action = app.action_registry.get("gui.set_theme")
    assert action is not None
    assert action.can_undo is True

    # Initial default theme is True (dark)
    assert app.dark_theme is True

    # 1. Switch to light theme (False)
    app.action_registry.execute("gui.set_theme", dark_theme=False)
    assert app.dark_theme is False
    assert events == [False]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores dark theme (True)
    app.history.undo()
    assert app.dark_theme is True
    assert events == [False, True]

    # 3. Redo -> re-applies light theme (False)
    app.history.redo()
    assert app.dark_theme is False
    assert events == [False, True, False]


def test_set_percent_display_action_and_undo_redo() -> None:
    """Test gui.set_percent_display action execution, Undo, and Redo."""
    settings = MagicMock()
    settings.get_boolean.return_value = False

    app = CoreApplication(settings)

    events: list[bool] = []

    def on_percent_changed(percent: bool) -> None:
        events.append(percent)

    app.subscribe("gui.percent_display_changed", on_percent_changed)

    action = app.action_registry.get("gui.set_percent_display")
    assert action is not None
    assert action.can_undo is True

    # 1. Enable percentage display
    app.action_registry.execute("gui.set_percent_display", percent=True)
    settings.set_boolean.assert_called_with("percent", True)
    assert events == [True]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores False
    app.history.undo()
    settings.set_boolean.assert_called_with("percent", False)
    assert events == [True, False]

    # 3. Redo -> re-applies True
    app.history.redo()
    settings.set_boolean.assert_called_with("percent", True)
    assert events == [True, False, True]


def test_set_default_time_action_and_undo_redo() -> None:
    """Test gui.set_default_time action execution, Undo, and Redo."""
    settings = MagicMock()
    settings.get_double.return_value = 0.0

    app = CoreApplication(settings)

    events: list[float] = []

    def on_default_time_changed(time_val: float) -> None:
        events.append(time_val)

    app.subscribe("gui.default_time_changed", on_default_time_changed)

    action = app.action_registry.get("gui.set_default_time")
    assert action is not None
    assert action.can_undo is True

    # 1. Set default transfer time to 4.5 seconds
    app.action_registry.execute("gui.set_default_time", default_time=4.5)
    settings.set_double.assert_called_with("default-time", 4.5)
    assert events == [4.5]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores 0.0
    app.history.undo()
    settings.set_double.assert_called_with("default-time", 0.0)
    assert events == [4.5, 0.0]

    # 3. Redo -> re-applies 4.5
    app.history.redo()
    settings.set_double.assert_called_with("default-time", 4.5)
    assert events == [4.5, 0.0, 4.5]


def test_event_bridge_preferences_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GuiEventBridge routes preference events to UI components."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))

    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core
    mock_app.window = MagicMock()

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {
        "settings": mock_settings_tab,
        "sequences": MagicMock(),
        "groups": MagicMock(),
        "memories": MagicMock(),
    }

    _bridge = GuiEventBridge(mock_app)

    # 1. Percent display event
    core.emit("gui.percent_display_changed", True)
    mock_settings_tab.update_percent_ui.assert_called_once_with(True)
    mock_app.window.live_view.channels_view.update.assert_called_once()
    mock_app.tabs.tabs["sequences"].channels_view.update.assert_called_once()
    mock_app.tabs.tabs["groups"].channels_view.update.assert_called_once()
    mock_app.tabs.tabs["memories"].channels_view.update.assert_called_once()

    # 2. Default time event
    core.emit("gui.default_time_changed", 2.5)
    mock_settings_tab.update_default_time_ui.assert_called_once_with(2.5)


def test_settings_tab_update_percent_and_default_time() -> None:
    """Test SettingsTab programmatic updates for percentage switch and default time."""
    # pylint: disable=protected-access
    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    tab.switch_percent = MagicMock()
    tab.switch_percent.get_state.return_value = False
    tab.spin_default_time = MagicMock()
    tab.spin_default_time.get_value.return_value = 0.0

    # 1. Update percent switch
    tab.update_percent_ui(True)
    tab.switch_percent.set_state.assert_called_once_with(True)
    tab.switch_percent.set_active.assert_called_once_with(True)
    assert not tab._updating_settings

    # 2. Update default time
    tab.update_default_time_ui(3.0)
    tab.spin_default_time.set_value.assert_called_once_with(3.0)
    assert not tab._updating_settings
