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
"""Tests for keyboard shortcuts and command line coexistence."""

# pylint: disable=protected-access

from __future__ import annotations

from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.widgets.channels_view import VIEW_MODES  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order


@pytest.mark.gui
def test_go_shortcuts_ctrl_g_and_space_hybrid(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Option 3 hybrid GO shortcuts: <Control>g everywhere, space if CLI empty."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller

    executed_actions: list[tuple[str, tuple[object, ...]]] = []
    orig_execute = app_gui.core.action_registry.execute

    def spy_execute(name: str, *args: object, **kwargs: object) -> object:
        executed_actions.append((name, args))
        return orig_execute(name, *args, **kwargs)

    monkeypatch.setattr(app_gui.core.action_registry, "execute", spy_execute)

    # 1. Space when command line is empty -> triggers playback.go
    app_gui.core.commandline.set_string("")
    handled = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert handled is True
    assert ("playback.go", ()) in executed_actions

    # 2. Space when command line is NOT empty -> appends " " to command line
    executed_actions.clear()
    app_gui.core.commandline.set_string("1")
    handled = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert handled is True
    assert ("commandline.append_char", (" ",)) in executed_actions
    assert ("playback.go", ()) not in executed_actions

    # 3. <Control>g when command line is NOT empty -> still triggers playback.go
    executed_actions.clear()
    handled = win._on_key_controller_pressed(
        controller, Gdk.KEY_g, 0, Gdk.ModifierType.CONTROL_MASK
    )
    assert handled is True
    assert ("playback.go", ()) in executed_actions

    # 4. When a Gtk.Entry has focus:
    #    - Space returns False (so user can type spaces in labels)
    #    - <Control>g STILL returns True and triggers playback.go!
    entry = Gtk.Entry()
    monkeypatch.setattr(win, "get_focus", lambda: entry)

    executed_actions.clear()
    handled_space = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert handled_space is False
    assert ("playback.go", ()) not in executed_actions

    handled_ctrl_g = win._on_key_controller_pressed(
        controller, Gdk.KEY_g, 0, Gdk.ModifierType.CONTROL_MASK
    )
    assert handled_ctrl_g is True
    assert ("playback.go", ()) in executed_actions

    app_gui.core.commandline.set_string("")


@pytest.mark.gui
def test_modifier_shortcuts_ctrl_f_ctrl_a_ctrl_up_down_alt_up_down(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test <Control>f, <Control>a, <Control>Up/Down, and <Alt>Up/Down."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    cv = win.live_view.channels_view

    # Ensure focus is on live_view
    monkeypatch.setattr(win, "get_active_tab", lambda: cv)

    # 1. <Control>f cycles view mode (All -> Patched -> Active)
    initial_mode = cv.view_mode
    handled = win._on_key_controller_pressed(
        controller, Gdk.KEY_f, 0, Gdk.ModifierType.CONTROL_MASK
    )
    assert handled is True
    assert cv.view_mode != initial_mode
    cv.view_mode = VIEW_MODES["All"]
    cv.update()

    # 2. <Control>a calls select_all on active ChannelsView
    select_all_mock = MagicMock()
    monkeypatch.setattr(cv, "select_all", select_all_mock)
    handled = win._on_key_controller_pressed(
        controller, Gdk.KEY_a, 0, Gdk.ModifierType.CONTROL_MASK
    )
    assert handled is True
    select_all_mock.assert_called_once()

    # 3. <Control>Up and <Control>Down call level_plus and level_minus
    level_plus_mock = MagicMock()
    level_minus_mock = MagicMock()
    monkeypatch.setattr(cv, "level_plus", level_plus_mock)
    monkeypatch.setattr(cv, "level_minus", level_minus_mock)

    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Up, 0, Gdk.ModifierType.CONTROL_MASK
        )
        is True
    )
    level_plus_mock.assert_called_once()

    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Down, 0, Gdk.ModifierType.CONTROL_MASK
        )
        is True
    )
    level_minus_mock.assert_called_once()

    # 4. <Alt>Up and <Alt>Down trigger playback.sequence_minus and sequence_plus
    executed: list[str] = []
    orig_execute = app_gui.core.action_registry.execute

    def spy_execute(name: str, *args: object, **kwargs: object) -> object:
        executed.append(name)
        return orig_execute(name, *args, **kwargs)

    monkeypatch.setattr(app_gui.core.action_registry, "execute", spy_execute)

    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Up, 0, Gdk.ModifierType.MOD1_MASK
        )
        is True
    )
    assert "playback.sequence_minus" in executed

    executed.clear()
    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Down, 0, Gdk.ModifierType.MOD1_MASK
        )
        is True
    )
    assert "playback.sequence_plus" in executed

    # 5. Verify app.faders accelerator was moved to <Shift><Control>f
    fader_accels = app_gui.get_accels_for_action("app.faders")
    assert any(a in fader_accels for a in ("<Shift><Control>f", "<Primary><Shift>f"))


@pytest.mark.gui
def test_editing_tab_navigation_and_f2_rename(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test F2 rename, <Alt>Up/Down, and arrow delegation when editing tab focused."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller

    app_gui.activate_action("sequences", None)
    process_events()
    assert app_gui.tabs is not None
    seq_tab = app_gui.tabs.tabs.get("sequences")
    assert seq_tab is not None

    # Focus the sequences tab
    monkeypatch.setattr(win, "get_active_tab", lambda: seq_tab)

    # 1. F2 calls rename_selected() on SequenceTab
    rename_mock = MagicMock()
    monkeypatch.setattr(seq_tab, "rename_selected", rename_mock)
    assert (
        win._on_key_controller_pressed(controller, Gdk.KEY_F2, 0, Gdk.ModifierType(0))
        is True
    )
    rename_mock.assert_called_once()

    # 2. <Alt>Up / <Alt>Down in SequenceTab calls _keypress_q / _keypress_w
    prev_mock = MagicMock()
    next_mock = MagicMock()
    monkeypatch.setattr(seq_tab, "_keypress_q", prev_mock)
    monkeypatch.setattr(seq_tab, "_keypress_w", next_mock)

    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Up, 0, Gdk.ModifierType.MOD1_MASK
        )
        is True
    )
    prev_mock.assert_called_once()

    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Down, 0, Gdk.ModifierType.MOD1_MASK
        )
        is True
    )
    next_mock.assert_called_once()

    # 3. Plain Up/Down in SequenceTab (which uses TreeViews) returns False so TreeView
    #    can navigate rows, while <Shift>Up / <Shift>Down triggers CLI history!
    assert (
        win._on_key_controller_pressed(controller, Gdk.KEY_Up, 0, Gdk.ModifierType(0))
        is False
    )
    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Up, 0, Gdk.ModifierType.SHIFT_MASK
        )
        is True
    )

    seq_tab.on_close_icon(seq_tab)
    process_events()
