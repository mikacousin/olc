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
"""Unit tests for SelectionManager and selection actions."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.core.selection import (
    SelectActiveAction,
    SelectAddAction,
    SelectAllAction,
    SelectionManager,
    SelectRemoveAction,
    SelectThruAction,
)


def test_selection_manager_basic_operations() -> None:
    """Test standard logical SelectionManager operations."""
    settings = MagicMock()
    app = CoreApplication(settings)

    changed_selections: list[list[int]] = []

    def on_changed(sel: list[int]) -> None:
        changed_selections.append(sel)

    manager = SelectionManager(
        commandline=app.commandline,
        on_changed_callback=on_changed,
        history_manager=app.history,
        get_level_callback=lambda ch: 100 if ch in (2, 4) else 0,
    )

    # 1. Select active channel 5
    manager.execute_action(SelectActiveAction, channel=5)
    assert manager.selected_channels == [5]
    assert manager.last_selected_channel == 5
    assert changed_selections[-1] == [5]

    # 2. Add channel 10
    manager.execute_action(SelectAddAction, channel=10)
    assert manager.selected_channels == [5, 10]
    assert manager.last_selected_channel == 10
    assert changed_selections[-1] == [5, 10]

    # 3. Add channel 10 again (should not duplicate)
    manager.execute_action(SelectAddAction, channel=10)
    assert manager.selected_channels == [5, 10]

    # 4. Remove channel 5
    manager.execute_action(SelectRemoveAction, channel=5)
    assert manager.selected_channels == [10]
    assert manager.last_selected_channel == 5
    assert changed_selections[-1] == [10]

    # 5. Thru from last_selected (5) to 8
    manager.execute_action(SelectThruAction, to_channel=8)
    # Range is 5 to 8, meaning: 5, 6, 7, 8. And 10 was already there.
    # Order is preserve of original selection and then range added.
    assert set(manager.selected_channels) == {5, 6, 7, 8, 10}
    assert manager.last_selected_channel == 8

    # 6. Select all (active levels are 2 and 4)
    manager.execute_action(SelectAllAction)
    assert manager.selected_channels == [2, 4]


def test_selection_manager_undo_redo() -> None:
    """Test undo/redo on SelectionManager actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    manager = SelectionManager(
        commandline=app.commandline,
        history_manager=app.history,
    )

    # Execute some actions
    manager.execute_action(SelectActiveAction, channel=3)
    manager.execute_action(SelectAddAction, channel=6)

    assert manager.selected_channels == [3, 6]
    assert manager.last_selected_channel == 6

    # Undo add 6
    app.history.undo()
    assert manager.selected_channels == [3]
    assert manager.last_selected_channel == 3

    # Undo active 3
    app.history.undo()
    assert manager.selected_channels == []
    assert manager.last_selected_channel is None

    # Redo active 3
    app.history.redo()
    assert manager.selected_channels == [3]
    assert manager.last_selected_channel == 3

    # Redo add 6
    app.history.redo()
    assert manager.selected_channels == [3, 6]
    assert manager.last_selected_channel == 6
