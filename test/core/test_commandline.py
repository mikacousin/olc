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
"""Unit tests for CoreCommandLine."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication


def test_commandline_operations() -> None:
    """Test standard logical command line operations."""
    settings = MagicMock()
    app = CoreApplication(settings)
    commandline = app.commandline

    # Verify default state
    assert commandline.get_string() == ""

    # Test set_string
    commandline.set_string("1 THRU 10")
    assert commandline.get_string() == "1 THRU 10"

    # Test add_string
    commandline.add_string(" @ 80")
    assert commandline.get_string() == "1 THRU 10 @ 80"


def test_commandline_changed_event() -> None:
    """Test commandline.changed event emission on state updates."""
    settings = MagicMock()
    app = CoreApplication(settings)
    commandline = app.commandline

    events_received: list[str] = []

    def on_commandline_changed(keystring: str) -> None:
        events_received.append(keystring)

    app.subscribe("commandline.changed", on_commandline_changed)

    # Trigger set_string
    commandline.set_string("Group 2")
    assert events_received == ["Group 2"]

    # Trigger add_string
    commandline.add_string(" @ 100")
    assert events_received == ["Group 2", "Group 2 @ 100"]


def test_commandline_backspace_hybrid_token() -> None:
    """Test hybrid token-based backspace operations."""
    settings = MagicMock()
    app = CoreApplication(settings)
    commandline = app.commandline

    # 1. Step-by-step complete command line unwinding
    commandline.set_string("CHANNEL 10 THRU 20 AT 80")
    expected_steps = [
        "CHANNEL 10 THRU 20 AT 8",
        "CHANNEL 10 THRU 20 AT ",
        "CHANNEL 10 THRU 20 ",
        "CHANNEL 10 THRU ",
        "CHANNEL 10 ",
        "CHANNEL ",
        "",
    ]
    for step in expected_steps:
        commandline.backspace()
        assert commandline.get_string() == step

    # 2. Backspace on empty and whitespace-only buffers
    commandline.set_string("")
    commandline.backspace()
    assert commandline.get_string() == ""

    commandline.set_string("   ")
    commandline.backspace()
    assert commandline.get_string() == ""

    # 3. Compound keywords
    commandline.set_string("RECORD CUE ")
    commandline.backspace()
    assert commandline.get_string() == "RECORD "
    commandline.backspace()
    assert commandline.get_string() == ""

    commandline.set_string("AT FULL")
    commandline.backspace()
    assert commandline.get_string() == "AT "

    # 4. Operators and decimal numbers
    commandline.set_string("GROUP 3 + 4")
    commandline.backspace()
    assert commandline.get_string() == "GROUP 3 + "
    commandline.backspace()
    assert commandline.get_string() == "GROUP 3 "

    commandline.set_string("CUE 1.5")
    commandline.backspace()
    assert commandline.get_string() == "CUE 1."
    commandline.backspace()
    assert commandline.get_string() == "CUE 1"
    commandline.backspace()
    assert commandline.get_string() == "CUE "
