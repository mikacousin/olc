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
"""Unit tests for Cue actions (insert, delete, update, rename, copy, set_channel_level)
and Undo/Redo.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from olc.core.app import CoreApplication


def test_cue_insert_update_set_level() -> None:
    """Test cue insert, update, and set_channel_level actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clear cues list for testing
    app.lightshow.cues = []

    # Track events
    created_events = []
    updated_events = []

    app.subscribe("cue.created", lambda seq, mem: created_events.append((seq, mem)))
    app.subscribe("cue.updated", lambda seq, mem: updated_events.append((seq, mem)))

    # 1. Test cue.insert (empty cue)
    app.action_registry.execute("cue.insert", 1.0, 0)
    assert len(app.lightshow.cues) == 1
    assert app.lightshow.cues[0].memory == 1.0
    assert app.lightshow.cues[0].sequence == 0
    assert app.lightshow.cues[0].channels == {}
    assert created_events == [(0, 1.0)]

    # 2. Test undo cue.insert
    app.history.undo()
    assert len(app.lightshow.cues) == 0

    # 3. Test redo cue.insert
    app.history.redo()
    assert len(app.lightshow.cues) == 1
    assert app.lightshow.cues[0].memory == 1.0
    assert created_events == [(0, 1.0), (0, 1.0)]

    # 4. Test cue.update
    updated_events.clear()
    channels_to_set = {1: 255, 2: 128}
    app.action_registry.execute("cue.update", 1.0, 0, channels_to_set)
    assert app.lightshow.cues[0].channels == {1: 255, 2: 128}
    assert updated_events == [(0, 1.0)]

    # Undo cue.update
    app.history.undo()
    assert app.lightshow.cues[0].channels == {}

    # Redo cue.update
    app.history.redo()
    assert app.lightshow.cues[0].channels == {1: 255, 2: 128}

    # 5. Test cue.set_channel_level
    updated_events.clear()
    app.action_registry.execute("cue.set_channel_level", 1.0, 0, 1, 200)
    assert app.lightshow.cues[0].channels[1] == 200
    assert updated_events == [(0, 1.0)]

    # Undo set channel level
    app.history.undo()
    assert app.lightshow.cues[0].channels[1] == 255

    # Redo set channel level
    app.history.redo()
    assert app.lightshow.cues[0].channels[1] == 200


def test_cue_rename_and_copy() -> None:
    """Test cue rename and copy actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.cues = []
    created_events = []
    deleted_events = []
    updated_events = []

    app.subscribe("cue.created", lambda seq, mem: created_events.append((seq, mem)))
    app.subscribe("cue.deleted", lambda seq, mem: deleted_events.append((seq, mem)))
    app.subscribe("cue.updated", lambda seq, mem: updated_events.append((seq, mem)))

    # Insert baseline cue 1.0
    app.action_registry.execute("cue.insert", 1.0, 0)
    app.action_registry.execute("cue.update", 1.0, 0, {1: 200, 2: 128})

    # 1. Test cue.rename
    updated_events.clear()
    app.action_registry.execute("cue.rename", 1.0, 0, "Test Name")
    assert app.lightshow.cues[0].text == "Test Name"
    assert updated_events == [(0, 1.0)]

    # Undo rename
    app.history.undo()
    assert app.lightshow.cues[0].text == ""

    # Redo rename
    app.history.redo()
    assert app.lightshow.cues[0].text == "Test Name"

    # 2. Test cue.copy (creating a new destination cue)
    created_events.clear()
    updated_events.clear()
    app.action_registry.execute("cue.copy", 1.0, 2.0, 0)
    assert len(app.lightshow.cues) == 2
    assert app.lightshow.cues[1].memory == 2.0
    assert app.lightshow.cues[1].channels == {1: 200, 2: 128}
    assert created_events == [(0, 2.0)]
    assert updated_events == [(0, 2.0)]

    # Undo copy (should remove the destination cue)
    deleted_events.clear()
    app.history.undo()
    assert len(app.lightshow.cues) == 1
    assert deleted_events == [(0, 2.0)]

    # Redo copy
    created_events.clear()
    app.history.redo()
    assert len(app.lightshow.cues) == 2
    assert app.lightshow.cues[1].memory == 2.0
    assert app.lightshow.cues[1].channels == {1: 200, 2: 128}
    assert created_events == [(0, 2.0)]

    # 3. Test cue.copy (overwriting existing cue)
    # Update cue 1.0 first
    app.action_registry.execute("cue.update", 1.0, 0, {3: 50})
    # Copy 1.0 into 2.0
    created_events.clear()
    updated_events.clear()
    app.action_registry.execute("cue.copy", 1.0, 2.0, 0)
    assert len(app.lightshow.cues) == 2
    assert app.lightshow.cues[1].channels == {3: 50}
    assert not created_events  # Not created since it already existed
    assert updated_events == [(0, 2.0)]

    # Undo overwrite copy
    app.history.undo()
    assert app.lightshow.cues[1].channels == {1: 200, 2: 128}

    # Redo overwrite copy
    app.history.redo()
    assert app.lightshow.cues[1].channels == {3: 50}


def test_cue_delete() -> None:
    """Test cue delete action."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.cues = []
    created_events = []
    deleted_events = []

    app.subscribe("cue.created", lambda seq, mem: created_events.append((seq, mem)))
    app.subscribe("cue.deleted", lambda seq, mem: deleted_events.append((seq, mem)))

    # Insert baseline cue 2.0
    app.action_registry.execute("cue.insert", 2.0, 0)
    app.action_registry.execute("cue.update", 2.0, 0, {3: 50})

    # 1. Test cue.delete
    deleted_events.clear()
    app.action_registry.execute("cue.delete", 2.0, 0)
    assert len(app.lightshow.cues) == 0
    assert deleted_events == [(0, 2.0)]

    # Undo delete
    created_events.clear()
    app.history.undo()
    assert len(app.lightshow.cues) == 1
    assert app.lightshow.cues[0].memory == 2.0
    assert app.lightshow.cues[0].channels == {3: 50}
    assert created_events == [(0, 2.0)]

    # Redo delete
    deleted_events.clear()
    app.history.redo()
    assert len(app.lightshow.cues) == 0
    assert deleted_events == [(0, 2.0)]


def test_cue_actions_errors() -> None:
    """Test validation errors for cue actions."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.cues = []

    # Try update non-existent cue
    with pytest.raises(ValueError, match="Cue 1.0 \\(seq 0\\) does not exist"):
        app.action_registry.execute("cue.update", 1.0, 0, {})

    # Try delete non-existent cue
    with pytest.raises(ValueError, match="Cue 1.0 \\(seq 0\\) does not exist"):
        app.action_registry.execute("cue.delete", 1.0, 0)

    # Insert existing cue
    app.action_registry.execute("cue.insert", 1.0, 0)
    with pytest.raises(ValueError, match="Cue 1.0 \\(seq 0\\) already exists"):
        app.action_registry.execute("cue.insert", 1.0, 0)
