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
"""GUI-specific tests for tab actions in Application and Bridge."""

from __future__ import annotations

import typing

import pytest
from gi.repository import Gtk
from olc.gtk3.application import Application

from test.gtk3.conftest import process_events  # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_app_callbacks_execute_switch_tab_action(app_gui: Application) -> None:
    """Test that menu callbacks trigger SwitchTabAction on the Core."""
    executed_actions = []
    original_execute = app_gui.core.action_registry.execute

    def mock_execute(
        name: str,
        *args: typing.Any,  # noqa: ANN401
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> typing.Any:  # noqa: ANN401
        executed_actions.append((name, args))
        return original_execute(name, *args, **kwargs)

    registry = typing.cast(typing.Any, app_gui.core.action_registry)
    registry.execute = mock_execute

    try:
        # Call independents callback
        app_gui.independents(None, None)
        process_events()
        assert ("gui.tab_open", ("indes",)) in executed_actions

        # Call curves callback
        app_gui.curves(None, None)
        process_events()
        assert ("gui.tab_open", ("curves",)) in executed_actions

        # Call faders callback
        app_gui.faders(None, None)
        process_events()
        assert ("gui.tab_open", ("faders",)) in executed_actions
    finally:
        registry.execute = original_execute


def test_manual_tab_switch_executes_action(app_gui: Application) -> None:
    """Test that manual notebook page switch triggers gui.tab_open action."""
    # Ensure window and tabs are open
    app_gui.faders(None, None)
    process_events()

    assert app_gui.tabs is not None
    tab = app_gui.tabs.tabs["faders"]
    assert tab is not None
    notebook = tab.get_parent()
    assert notebook is not None
    notebook_nb = typing.cast(Gtk.Notebook, notebook)

    executed_actions = []
    original_execute = app_gui.core.action_registry.execute

    def mock_execute(
        name: str,
        *args: typing.Any,  # noqa: ANN401
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> typing.Any:  # noqa: ANN401
        executed_actions.append((name, args))
        return original_execute(name, *args, **kwargs)

    registry = typing.cast(typing.Any, app_gui.core.action_registry)
    registry.execute = mock_execute

    try:
        # Switch physically to page 0 (playback)
        notebook_nb.set_current_page(0)
        process_events()

        assert ("gui.tab_open", ("playback", "playback")) in executed_actions
    finally:
        registry.execute = original_execute


def test_gui_tab_cross_notebook_move(app_gui: Application) -> None:
    """Test moving a tab between notebooks physically and checking its Undo/Redo."""
    app = app_gui
    # Open "indes" tab (starts in playback by default)
    app.independents(None, None)
    process_events()

    assert app.window is not None
    assert app.tabs is not None
    tab = app.tabs.tabs["indes"]
    assert tab is not None
    notebook = tab.get_parent()
    assert notebook is app.window.playback

    # Move "indes" to live notebook logically (simulating move_tab shortcut)
    app.core.action_registry.execute("gui.tab_move", "indes", "playback", "live", 0)
    process_events()

    # Verify physical parent is now live_view
    assert tab.get_parent() is app.window.live_view

    # Undo the move action
    app.core.history.undo()
    process_events()

    # Verify tab is back in playback notebook
    assert tab.get_parent() is app.window.playback

    # Redo the move action
    app.core.history.redo()
    process_events()

    # Verify tab is in live notebook again
    assert tab.get_parent() is app.window.live_view
