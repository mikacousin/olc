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
"""Unit tests for Group actions (new, delete, update_channels, rename) and
HistoryManager.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from olc.core.app import CoreApplication
from olc.group import Group


def test_new_and_delete_group_actions_and_undo_redo() -> None:
    """Test group creation, deletion, undo, and redo."""
    # 1. Initialize core app
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clear groups list in lightshow
    app.lightshow.groups.clear()

    # 2. Track events
    created_events = []
    deleted_events = []
    app.subscribe("group.created", lambda group: created_events.append(group.index))
    app.subscribe("group.deleted", lambda group: deleted_events.append(group.index))

    # 3. Create Group 1.0
    app.action_registry.execute("group.new", 1.0)
    assert len(app.lightshow.groups) == 1
    assert app.lightshow.groups[0].index == 1.0
    assert created_events == [1.0]

    # 4. Create Group 3.0
    app.action_registry.execute("group.new", 3.0)
    assert len(app.lightshow.groups) == 2
    assert app.lightshow.groups[1].index == 3.0
    assert created_events == [1.0, 3.0]

    # 5. Create Group 2.0 (should insert in-between)
    app.action_registry.execute("group.new", 2.0)
    assert len(app.lightshow.groups) == 3
    assert app.lightshow.groups[0].index == 1.0
    assert app.lightshow.groups[1].index == 2.0
    assert app.lightshow.groups[2].index == 3.0
    assert created_events == [1.0, 3.0, 2.0]

    # 6. Undo Group 2.0 creation
    app.history.undo()
    assert len(app.lightshow.groups) == 2
    assert app.lightshow.groups[0].index == 1.0
    assert app.lightshow.groups[1].index == 3.0
    assert deleted_events == [2.0]

    # 7. Redo Group 2.0 creation
    app.history.redo()
    assert len(app.lightshow.groups) == 3
    assert app.lightshow.groups[1].index == 2.0
    assert created_events == [1.0, 3.0, 2.0, 2.0]

    # 8. Delete Group 2.0
    created_events.clear()
    deleted_events.clear()
    app.action_registry.execute("group.delete", 2.0)
    assert len(app.lightshow.groups) == 2
    assert app.lightshow.groups[0].index == 1.0
    assert app.lightshow.groups[1].index == 3.0
    assert deleted_events == [2.0]

    # 9. Undo deletion
    app.history.undo()
    assert len(app.lightshow.groups) == 3
    assert app.lightshow.groups[1].index == 2.0
    assert created_events == [2.0]


def test_group_actions_validation_errors() -> None:
    """Test group action error cases like duplicates or non-existent deletes."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.groups.clear()

    # Create Group 1.0
    app.action_registry.execute("group.new", 1.0)

    # Creating it again should raise ValueError
    with pytest.raises(ValueError, match="Group 1.0 already exists"):
        app.action_registry.execute("group.new", 1.0)

    # Deleting a non-existent group should raise ValueError
    with pytest.raises(ValueError, match="Group 9.0 does not exist"):
        app.action_registry.execute("group.delete", 9.0)


def test_group_new_action_auto_index() -> None:
    """Test NewGroupAction automatically assigns index when not provided."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.groups.clear()

    # First auto index should be 1.0 if empty
    app.action_registry.execute("group.new")
    assert len(app.lightshow.groups) == 1
    assert app.lightshow.groups[0].index == 1.0

    # Next auto index should be last_group.index + 1.0 -> 2.0
    app.action_registry.execute("group.new")
    assert len(app.lightshow.groups) == 2
    assert app.lightshow.groups[1].index == 2.0


def test_group_update_channels_action() -> None:
    """Test group update_channels action, including undo and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clean groups list
    app.lightshow.groups.clear()

    # Create initial group
    app.action_registry.execute("group.new", 1.0)
    group = app.lightshow.groups[0]
    assert group.index == 1.0
    assert group.channels == {}

    # Track updated events
    updated_events = []
    app.subscribe("group.updated", lambda g: updated_events.append(g.index))

    # Test group.update_channels
    app.action_registry.execute("group.update_channels", 1.0, {1: 255, 2: 128})
    assert group.channels == {1: 255, 2: 128}
    assert updated_events == [1.0]

    # Undo update_channels
    updated_events.clear()
    app.history.undo()
    assert group.channels == {}
    assert updated_events == [1.0]

    # Redo update_channels
    updated_events.clear()
    app.history.redo()
    assert group.channels == {1: 255, 2: 128}
    assert updated_events == [1.0]


def test_group_rename_action() -> None:
    """Test group rename action, including undo and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clean groups list
    app.lightshow.groups.clear()

    # Create initial group
    app.action_registry.execute("group.new", 1.0)
    group = app.lightshow.groups[0]
    assert group.index == 1.0
    assert group.text == "1.0"

    # Track updated events
    updated_events = []
    app.subscribe("group.updated", lambda g: updated_events.append(g.index))

    # Test group.rename
    app.action_registry.execute("group.rename", 1.0, "New Group Name")
    assert group.text == "New Group Name"
    assert updated_events == [1.0]

    # Undo rename
    updated_events.clear()
    app.history.undo()
    assert group.text == "1.0"
    assert updated_events == [1.0]

    # Redo rename
    updated_events.clear()
    app.history.redo()
    assert group.text == "New Group Name"
    assert updated_events == [1.0]


def test_group_extended_actions_errors() -> None:
    """Test error validation for group extended actions."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.groups.clear()

    # Update non-existent group channels
    with pytest.raises(ValueError, match="Group 2.0 does not exist"):
        app.action_registry.execute("group.update_channels", 2.0, {1: 255})

    # Rename non-existent group
    with pytest.raises(ValueError, match="Group 2.0 does not exist"):
        app.action_registry.execute("group.rename", 2.0, "Nobody")


def test_groups_container_class() -> None:
    """Test Groups container class specific API."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Initialize groups
    groups = app.lightshow.groups
    groups.clear()

    # Test get_next_index on empty
    assert groups.get_next_index() == 1.0

    # Test add
    g1 = Group(index=1.0, channels={})
    groups.add(g1)
    assert len(groups) == 1
    assert groups[0] == g1
    assert groups.get(1.0) == g1
    assert groups.get_next_index() == 2.0

    # Test add duplicate raises ValueError
    with pytest.raises(ValueError, match="Group with index 1.0 already exists"):
        groups.add(Group(index=1.0, channels={}))

    # Test insert/append maintains sorted order
    g3 = Group(index=3.0, channels={})
    g2 = Group(index=2.0, channels={})
    groups.add(g3)
    groups.add(g2)

    assert len(groups) == 3
    assert groups[0] == g1
    assert groups[1] == g2
    assert groups[2] == g3

    # Test iteration
    items = list(groups)
    assert items == [g1, g2, g3]

    # Test pop and remove
    popped = groups.pop(1)
    assert popped == g2
    assert len(groups) == 2
    assert groups[0] == g1
    assert groups[1] == g3

    groups.remove(g3)
    assert len(groups) == 1
    assert groups[0] == g1


def test_group_select_action_undo_redo() -> None:
    """Test group select action, including undo and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clean groups list and set up group
    app.lightshow.groups.clear()
    app.action_registry.execute("group.new", 1.0)
    app.action_registry.execute("group.new", 2.0)

    # Track selection events
    received_selections: list[float | None] = []
    app.subscribe("group.selected_changed", received_selections.append)

    # 1. Test group.select with group 1.0
    app.action_registry.execute("group.select", 1.0)
    assert app.selected_group == 1.0
    assert received_selections == [1.0]

    # 2. Test group.select with group 2.0
    app.action_registry.execute("group.select", 2.0)
    assert app.selected_group == 2.0
    assert received_selections == [1.0, 2.0]

    # 3. Undo
    app.history.undo()
    assert app.selected_group == 1.0
    assert received_selections == [1.0, 2.0, 1.0]

    # 4. Undo again
    app.history.undo()
    assert app.selected_group is None
    assert received_selections == [1.0, 2.0, 1.0, None]

    # 5. Redo
    app.history.redo()
    assert app.selected_group == 1.0
    assert received_selections == [1.0, 2.0, 1.0, None, 1.0]

    # 6. Redo again
    app.history.redo()
    assert app.selected_group == 2.0
    assert received_selections == [1.0, 2.0, 1.0, None, 1.0, 2.0]

    # 7. Unselect group
    app.action_registry.execute("group.select", None)
    assert app.selected_group is None
    assert received_selections[-1] is None
