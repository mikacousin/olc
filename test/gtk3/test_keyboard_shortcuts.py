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

import typing
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
def test_space_real_event_triggers_go_on_main_fader(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test real GDK space key event triggers playback.go when focus is on
    a view or notebook.
    """
    assert app_gui.window is not None
    win = app_gui.window
    process_events()

    executed_actions: list[str] = []
    orig_execute = app_gui.core.action_registry.execute

    def spy_execute(name: str, *args: object, **kwargs: object) -> object:
        executed_actions.append(name)
        return orig_execute(name, *args, **kwargs)

    monkeypatch.setattr(app_gui.core.action_registry, "execute", spy_execute)
    app_gui.core.commandline.set_string("")

    win.live_view.grab_focus()
    process_events()

    disp = Gdk.Display.get_default()
    assert disp is not None
    seat = disp.get_default_seat()
    assert seat is not None
    kbd = seat.get_keyboard()
    assert kbd is not None

    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.set_device(kbd)
    event_key = typing.cast("Gdk.EventKey", ev)
    event_key.keyval = Gdk.KEY_space
    gdk_win = win.get_window()
    assert gdk_win is not None
    event_key.window = gdk_win
    event_key.send_event = False
    event_key.time = 0
    event_key.state = Gdk.ModifierType(0)
    event_key.hardware_keycode = 65

    Gtk.main_do_event(ev)
    process_events()

    assert "playback.go" in executed_actions


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
    assert cv.view_mode == VIEW_MODES["Patched"]
    cv.combo.set_active(0)
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


@pytest.mark.gui
def test_shortcuts_window_and_menu_items(app_gui: Application) -> None:
    """Verify help-overlay.ui and app-menu.ui load all updated entries."""
    app_gui.open_shortcuts()
    process_events()
    assert app_gui.shortcuts is not None
    app_gui.shortcuts.hide()
    app_gui.shortcuts.destroy()
    app_gui.shortcuts = None

    menu = app_gui.setup_app_menu()
    labels: list[str] = []
    for i in range(menu.get_n_items()):
        val = menu.get_item_attribute_value(i, "label", None)
        if val is not None:
            labels.append(val.get_string())
    assert "Patch" in labels
    assert "DMX Outputs" in labels
    assert "Device Inspector" in labels

    # Verify updated accelerators for Patch and DMX Outputs
    patch_accels = app_gui.get_accels_for_action("app.patch_channels")
    assert any(a in patch_accels for a in ("<Control>p", "<Primary>p"))

    dmx_accels = app_gui.get_accels_for_action("app.dmx_outputs")
    assert any(a in dmx_accels for a in ("<Control>d", "<Primary>d"))


@pytest.mark.gui
def test_console_hotkeys_direct_letters(app_gui: Application) -> None:
    """Test single-key hotkeys (C=CHANNEL, Q=CUE, A=AT, T=THRU, F=FULL, Enter)."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    cmdline = app_gui.core.commandline

    cmdline.clear()
    assert cmdline.get_string() == ""

    # Press 'c' -> "CHANNEL "
    assert (
        win._on_key_controller_pressed(controller, Gdk.KEY_c, 0, Gdk.ModifierType(0))
        is True
    )
    assert cmdline.get_string() == "CHANNEL "

    # Press '1'
    assert (
        win._on_key_controller_pressed(controller, Gdk.KEY_1, 0, Gdk.ModifierType(0))
        is True
    )
    assert cmdline.get_string() == "CHANNEL 1"

    # Press 't' -> " THRU "
    assert (
        win._on_key_controller_pressed(controller, Gdk.KEY_t, 0, Gdk.ModifierType(0))
        is True
    )
    assert cmdline.get_string() == "CHANNEL 1 THRU "

    # Press '1', '0'
    win._on_key_controller_pressed(controller, Gdk.KEY_1, 0, Gdk.ModifierType(0))
    win._on_key_controller_pressed(controller, Gdk.KEY_0, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "CHANNEL 1 THRU 10"

    # Press 'a' -> " AT "
    win._on_key_controller_pressed(controller, Gdk.KEY_a, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "CHANNEL 1 THRU 10 AT "

    # Press 'f' -> "FULL"
    win._on_key_controller_pressed(controller, Gdk.KEY_f, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "CHANNEL 1 THRU 10 AT FULL"

    # Press Return -> executes command and clears command line
    win._on_key_controller_pressed(controller, Gdk.KEY_Return, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == ""

    # Test 'q' -> "CUE "
    win._on_key_controller_pressed(controller, Gdk.KEY_q, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "CUE "

    # Test 'n' -> "SNEAK "
    cmdline.clear()
    win._on_key_controller_pressed(controller, Gdk.KEY_n, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "SNEAK "

    # Test 'j' -> "ODD "
    cmdline.clear()
    win._on_key_controller_pressed(controller, Gdk.KEY_j, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "ODD "

    # Test 'y' -> "DELAY "
    cmdline.clear()
    win._on_key_controller_pressed(controller, Gdk.KEY_y, 0, Gdk.ModifierType(0))
    assert cmdline.get_string() == "DELAY "


@pytest.mark.gui
def test_console_hotkeys_shift_secondary_layer(app_gui: Application) -> None:
    """Test Shift combinations (Shift+Q -> GOTO CUE, Shift+C -> CLEAR, etc.)."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    cmdline = app_gui.core.commandline

    cmdline.clear()

    # Shift+Q -> "GOTO CUE "
    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_Q, 0, Gdk.ModifierType.SHIFT_MASK
        )
        is True
    )
    assert cmdline.get_string() == "GOTO CUE "

    # Shift+C -> Clear
    assert (
        win._on_key_controller_pressed(
            controller, Gdk.KEY_C, 0, Gdk.ModifierType.SHIFT_MASK
        )
        is True
    )
    assert cmdline.get_string() == ""

    # Shift+R -> "RECORD CUE "
    win._on_key_controller_pressed(
        controller, Gdk.KEY_R, 0, Gdk.ModifierType.SHIFT_MASK
    )
    assert cmdline.get_string() == "RECORD CUE "

    cmdline.clear()
    # Direct selection then Shift+A ("AT FULL")
    win._on_key_controller_pressed(controller, Gdk.KEY_1, 0, Gdk.ModifierType(0))
    win._on_key_controller_pressed(
        controller, Gdk.KEY_A, 0, Gdk.ModifierType.SHIFT_MASK
    )
    assert cmdline.get_string() == "1 AT FULL"


@pytest.mark.gui
def test_console_hotkeys_ctrl_alt_pos_keypad(app_gui: Application) -> None:
    """Test programmable keypad combinations with Ctrl+Alt modifiers."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    cmdline = app_gui.core.commandline

    ctrl_alt = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK

    cmdline.clear()
    # Ctrl+Alt+C -> "CHANNEL "
    assert win._on_key_controller_pressed(controller, Gdk.KEY_c, 0, ctrl_alt) is True
    assert cmdline.get_string() == "CHANNEL "

    # Ctrl+Alt+Q -> "CUE "
    cmdline.clear()
    assert win._on_key_controller_pressed(controller, Gdk.KEY_q, 0, ctrl_alt) is True
    assert cmdline.get_string() == "CUE "

    # Ctrl+Alt+N -> "SNEAK "
    cmdline.clear()
    assert win._on_key_controller_pressed(controller, Gdk.KEY_n, 0, ctrl_alt) is True
    assert cmdline.get_string() == "SNEAK "

    # Ctrl+Alt+J -> "ODD "
    cmdline.clear()
    assert win._on_key_controller_pressed(controller, Gdk.KEY_j, 0, ctrl_alt) is True
    assert cmdline.get_string() == "ODD "

    # Ctrl+Alt+Y -> "DELAY "
    cmdline.clear()
    assert win._on_key_controller_pressed(controller, Gdk.KEY_y, 0, ctrl_alt) is True
    assert cmdline.get_string() == "DELAY "

    # Ctrl+B -> Blackout toggle action
    executed: list[str] = []
    orig_exec = app_gui.core.action_registry.execute

    def spy_exec(name: str, *args: object, **kwargs: object) -> object:
        executed.append(name)
        return orig_exec(name, *args, **kwargs)

    app_gui.core.action_registry.execute = spy_exec  # type: ignore[assignment]
    try:
        assert (
            win._on_key_controller_pressed(
                controller, Gdk.KEY_b, 0, Gdk.ModifierType.CONTROL_MASK
            )
            is True
        )
        assert "dmx.blackout_all" in executed
    finally:
        app_gui.core.action_registry.execute = orig_exec  # type: ignore[assignment]


@pytest.mark.gui
def test_console_text_entry_focus_isolation(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure typing into a Gtk.Entry does not trigger console hotkeys."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    cmdline = app_gui.core.commandline

    cmdline.clear()
    entry = Gtk.Entry()
    win.add(entry)
    entry.show()
    entry.grab_focus()
    process_events()

    monkeypatch.setattr(win, "get_focus", lambda: entry)

    # In text entry, pressing 'c' should return False so the Entry receives the letter
    res = win._on_key_controller_pressed(controller, Gdk.KEY_c, 0, Gdk.ModifierType(0))
    assert res is False
    assert cmdline.get_string() == ""

    # Universal shortcut Ctrl+G still triggers GO even when text editing
    ctrl_g_res = win._on_key_controller_pressed(
        controller, Gdk.KEY_g, 0, Gdk.ModifierType.CONTROL_MASK
    )
    assert ctrl_g_res is True


@pytest.mark.gui
def test_cue_treeview_cell_editing_space(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure editing a cue text in CuesEditionTab does not trigger GO on space."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    cmdline = app_gui.core.commandline

    cmdline.clear()
    app_gui.open_memories()
    process_events()

    from olc.gtk3.cue import CuesEditionTab

    cues_tab = win.tabs_manager.tabs["memories"]
    assert isinstance(cues_tab, CuesEditionTab)
    if len(app_gui.core.lightshow.cues) == 0:
        from olc.cue import Cue

        app_gui.core.lightshow.cues.append(Cue(0, 1.0, text="Test Cue"))
        cues_tab.refresh()
        process_events()

    tree = cues_tab.treeview
    col = tree.get_column(1)  # Text column
    assert col is not None
    cells = col.get_cells()
    assert len(cells) > 0

    # Pre-select cue so cursor-changed doesn't re-trigger cue.select
    app_gui.core.action_registry.execute("cue.select", (1.0, 0))
    process_events()

    tree.grab_focus()
    tree.set_cursor_on_cell(Gtk.TreePath.new_first(), col, cells[0], True)
    process_events()

    executed_actions: list[str] = []
    orig_execute = app_gui.core.action_registry.execute

    def spy_execute(name: str, *args: object, **kwargs: object) -> object:
        executed_actions.append(name)
        return orig_execute(name, *args, **kwargs)

    monkeypatch.setattr(app_gui.core.action_registry, "execute", spy_execute)

    # 0. Global app accelerators do not include bare "space" for GO
    assert "space" not in app_gui.get_accels_for_action("app.go")

    # 1. Editing cell in CuesEditionTab: space returns False, playback.go is NOT called
    assert win.is_text_editing_active() is True
    res = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert res is False
    assert "playback.go" not in executed_actions

    # 2. Even if win.get_focus() temporarily returns the TreeView itself while editing:
    monkeypatch.setattr(win, "get_focus", lambda: tree)
    assert win.is_text_editing_active() is True
    res2 = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert res2 is False
    assert "playback.go" not in executed_actions


@pytest.mark.gui
def test_sequence_treeview_cell_editing_space(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure editing a cue text in SequenceTab does not trigger GO on space."""
    from olc.gtk3.sequence import SequenceTab

    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller

    # 1. Open the Sequences Tab
    app_gui.activate_action("sequences", None)
    process_events()

    seq_tab = win.tabs_manager.tabs["sequences"]
    assert isinstance(seq_tab, SequenceTab)

    # Select sequence 1 and insert a step
    path1 = Gtk.TreePath.new_first()
    seq_tab.treeview1.set_cursor(path1, None, False)
    seq_tab.on_sequence_changed()
    process_events()

    model2 = seq_tab.treeview2.get_model()
    if model2 is None or len(model2) == 0:
        seq_tab._keypress_r()
        process_events()

    tree2 = seq_tab.treeview2
    col_text = tree2.get_column(2)  # Column 2 is "Text"
    assert col_text is not None
    cells = col_text.get_cells()
    assert len(cells) > 0

    tree2.grab_focus()
    tree2.set_cursor_on_cell(Gtk.TreePath.new_first(), col_text, cells[0], True)
    process_events()

    executed_actions: list[str] = []
    orig_execute = app_gui.core.action_registry.execute

    def spy_execute(name: str, *args: object, **kwargs: object) -> object:
        executed_actions.append(name)
        return orig_execute(name, *args, **kwargs)

    monkeypatch.setattr(app_gui.core.action_registry, "execute", spy_execute)

    assert win.is_text_editing_active() is True
    res = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert res is False
    assert "playback.go" not in executed_actions

    res = win._on_key_controller_pressed(
        controller, Gdk.KEY_space, 0, Gdk.ModifierType(0)
    )
    assert res is False
    assert "playback.go" not in executed_actions
