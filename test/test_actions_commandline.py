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

from __future__ import annotations

from unittest.mock import MagicMock

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
