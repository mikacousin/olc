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
"""Unit tests for NewGroupAction, DeleteGroupAction, and HistoryManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from olc.core.app import CoreApplication


def test_new_and_delete_group_actions_and_undo_redo() -> None:
    """Test group creation, deletion, undo, and redo."""
    # 1. Initialize core app
    settings = MagicMock()
    app = CoreApplication(settings)

    # Mock the groups list in lightshow
    app.lightshow.groups = []

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
    app.lightshow.groups = []

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
    app.lightshow.groups = []

    # First auto index should be 1.0 if empty
    app.action_registry.execute("group.new")
    assert len(app.lightshow.groups) == 1
    assert app.lightshow.groups[0].index == 1.0

    # Next auto index should be last_group.index + 1.0 -> 2.0
    app.action_registry.execute("group.new")
    assert len(app.lightshow.groups) == 2
    assert app.lightshow.groups[1].index == 2.0
