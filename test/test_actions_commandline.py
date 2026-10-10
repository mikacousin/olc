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
"""Unit tests for CommandLine actions (append_char, clear, set)."""
# pylint: disable=protected-access,import-outside-toplevel

from __future__ import annotations

from unittest.mock import MagicMock

from olc.actions.commandline import CommandLineAppendCharAction
from olc.core.app import CoreApplication


def test_commandline_append_char_execution_and_undo() -> None:
    """Test append_char appends character and supports undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    assert app.commandline.get_string() == ""

    app.action_registry.execute("commandline.append_char", "1")
    assert app.commandline.get_string() == "1"
    action = app.action_registry.get("commandline.append_char")
    assert action.get_feedback_state() == {"text": "1"}

    app.action_registry.execute("commandline.append_char", "2")
    assert app.commandline.get_string() == "12"

    app.action_registry.execute("commandline.append_char", ".")
    assert app.commandline.get_string() == "12."

    # Undo "."
    app.history.undo()
    assert app.commandline.get_string() == "12"

    # Undo "2"
    app.history.undo()
    assert app.commandline.get_string() == "1"

    # Redo "2"
    app.history.redo()
    assert app.commandline.get_string() == "12"


def test_commandline_clear_execution_and_undo() -> None:
    """Test clear resets commandline and supports undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.commandline.set_string("123")
    assert app.commandline.get_string() == "123"

    app.action_registry.execute("commandline.clear")
    assert app.commandline.get_string() == ""
    action = app.action_registry.get("commandline.clear")
    assert action.get_feedback_state() == {"text": ""}

    # Undo restores "123"
    app.history.undo()
    assert app.commandline.get_string() == "123"

    # Redo clears again
    app.history.redo()
    assert app.commandline.get_string() == ""


def test_commandline_set_execution_and_undo() -> None:
    """Test set replaces commandline string and supports undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.commandline.set_string("hello")

    app.action_registry.execute("commandline.set", "world")
    assert app.commandline.get_string() == "world"
    action = app.action_registry.get("commandline.set")
    assert action.get_feedback_state() == {"text": "world"}

    # Undo restores "hello"
    app.history.undo()
    assert app.commandline.get_string() == "hello"

    # Redo sets "world"
    app.history.redo()
    assert app.commandline.get_string() == "world"


def test_commandline_append_char_keyword_and_unchanged() -> None:
    """Test append_char with keyword parameter and unchanged edge cases."""
    settings = MagicMock()
    app = CoreApplication(settings)

    action = app.action_registry.get("commandline.append_char")
    assert isinstance(action, CommandLineAppendCharAction)
    action.configure(char="9")
    action.execute()
    assert app.commandline.get_string() == "9"

    # Setting identical text should not be undoable
    app.action_registry.execute("commandline.set", "9")
    set_action = app.action_registry.get("commandline.set")
    assert set_action.can_undo is False


def test_commandline_execute_backspace_and_history() -> None:
    """Test execute, backspace, and history navigation actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # 1. Backspace
    app.commandline.set_string("123")
    app.action_registry.execute("commandline.backspace")
    assert app.commandline.get_string() == "12"

    # 2. Execute command
    app.commandline.set_string("1 THRU 4")
    app.action_registry.execute("commandline.execute")
    # On success, buffer is cleared and selection is updated
    assert app.commandline.get_string() == ""
    assert app.selected_channels == [1, 2, 3, 4]

    # 3. History recall
    app.action_registry.execute("commandline.history_prev")
    assert app.commandline.get_string() == "1 THRU 4"

    app.action_registry.execute("commandline.history_next")
    assert app.commandline.get_string() == ""


def test_window_key_controller_handling() -> None:
    """Test Window._on_key_controller_pressed routes keys and handles shortcuts."""
    from gi.repository import Gdk

    from olc.gtk3.window import Window

    win = Window.__new__(Window)
    win.get_focus = MagicMock(return_value=None)
    mock_app = MagicMock()
    win.get_application = MagicMock(return_value=mock_app)
    win.live_view = MagicMock()

    # Digits from keypad
    no_mod = Gdk.ModifierType(0)
    ret = win._on_key_controller_pressed(MagicMock(), Gdk.KEY_KP_5, 0, no_mod)
    assert ret is True
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", "5"
    )

    # Enter
    ret = win._on_key_controller_pressed(MagicMock(), Gdk.KEY_Return, 0, no_mod)
    assert ret is True
    mock_app.core.action_registry.execute.assert_called_with("commandline.execute")

    # BackSpace
    ret = win._on_key_controller_pressed(MagicMock(), Gdk.KEY_BackSpace, 0, no_mod)
    assert ret is True
    mock_app.core.action_registry.execute.assert_called_with("commandline.backspace")


def test_virtual_console_commandline_buttons() -> None:
    """Test VirtualConsoleWindow button handlers trigger commandline actions."""
    from olc.gtk3.virtual_console import VirtualConsoleWindow

    mock_app = MagicMock()
    mock_app.core.commandline = MagicMock()
    mock_app.core.action_registry = MagicMock()
    mock_app.midi = None

    vc = VirtualConsoleWindow.__new__(VirtualConsoleWindow)
    vc.app = mock_app
    vc.commandline = mock_app.core.commandline

    # Test enter
    vc._on_enter(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with("commandline.execute")

    # Test backspace
    vc._on_backspace(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with("commandline.backspace")

    # Test clear
    vc._on_clear(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with("commandline.clear")

    # Test syntax keywords
    vc._on_goto(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", "GOTO CUE "
    )

    vc._on_delete(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", "DELETE "
    )

    vc._on_full(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", " AT FULL"
    )

    vc._on_out(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", " AT OUT"
    )

    vc._on_odd(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", " ODD"
    )

    vc._on_even(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", " EVEN"
    )

    vc._on_block(MagicMock())
    mock_app.core.action_registry.execute.assert_called_with(
        "commandline.append_char", " BLOCK"
    )


def test_virtual_console_button_sensitivity() -> None:
    """Test VirtualConsoleWindow updates button sensitivity based on command text."""
    from olc.core.parser.tokens import TokenType
    from olc.gtk3.virtual_console import VirtualConsoleWindow
    from olc.gtk3.widgets.button import ButtonWidget

    mock_app = MagicMock()
    mock_app.midi = None

    vc = VirtualConsoleWindow.__new__(VirtualConsoleWindow)
    vc.app = mock_app

    # Create dummy buttons
    buttons = [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "dot",
        "enter",
        "thru",
        "plus",
        "minus",
        "all",
        "odd",
        "even",
        "at_level",
        "full",
        "out",
        "percent_plus",
        "percent_minus",
        "block",
        "delete",
        "goto",
    ]
    for b in buttons:
        setattr(vc, b, ButtonWidget(b))
    vc.queue_draw = MagicMock()

    # 1. Empty commandline
    vc.commandline = MagicMock()
    vc.commandline.get_string.return_value = ""
    vc.commandline.parser.get_expected_tokens.return_value = [
        TokenType.NUMBER,
        TokenType.GROUP,
        TokenType.ALL,
        TokenType.RECORD,
        TokenType.GOTO,
        TokenType.DELETE,
    ]
    vc.update_button_sensitivity()

    # Digits and All, Delete, Goto should be sensitive
    assert vc.one.get_sensitive() is True
    assert vc.all.get_sensitive() is True
    assert vc.delete.get_sensitive() is True
    # Enter and Thru should NOT be sensitive when empty
    assert vc.enter.get_sensitive() is False
    assert vc.thru.get_sensitive() is False
    assert vc.at_level.get_sensitive() is False

    # 2. After typing "1"
    vc.commandline.get_string.return_value = "1"
    vc.commandline.parser.get_expected_tokens.return_value = [
        TokenType.THRU,
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.AT,
        TokenType.NUMBER,
    ]
    vc.update_button_sensitivity()

    assert vc.one.get_sensitive() is True
    assert vc.two.get_sensitive() is True
    assert vc.enter.get_sensitive() is True
    assert vc.thru.get_sensitive() is True
    assert vc.at_level.get_sensitive() is True
    assert vc.delete.get_sensitive() is False

    # 3. Test ButtonWidget respects sensitive state on press and release
    btn = ButtonWidget("Test")
    btn.set_sensitive(False)
    clicked_mock = MagicMock()
    btn.connect("clicked", clicked_mock)
    btn.on_press(MagicMock(), MagicMock())
    btn.on_release(MagicMock(), MagicMock())
    clicked_mock.assert_not_called()
    assert btn.pressed is False

    # Test state-flags-changed resets pressed
    btn.set_sensitive(True)
    btn.on_press(MagicMock(), MagicMock())
    assert btn.pressed is True
    btn.set_sensitive(False)
    assert btn.pressed is False
