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

    # Track events
    created_events = []
    updated_events = []

    app.subscribe(
        "cue.created", lambda seq, cue_num: created_events.append((seq, cue_num))
    )
    app.subscribe(
        "cue.updated", lambda seq, cue_num: updated_events.append((seq, cue_num))
    )

    # 1. Test cue.insert (empty cue)
    app.action_registry.execute("cue.insert", 1.0, 1)
    cue1 = app.lightshow.get_cue(1.0, 1)
    assert cue1 is not None
    assert cue1.number == 1.0
    assert cue1.sequence == 1
    assert cue1.channels == {}
    assert created_events == [(1, 1.0)]

    # 2. Test undo cue.insert
    app.history.undo()
    assert app.lightshow.get_cue(1.0, 1) is None

    # 3. Test redo cue.insert
    app.history.redo()
    cue1 = app.lightshow.get_cue(1.0, 1)
    assert cue1 is not None
    assert cue1.number == 1.0
    assert created_events == [(1, 1.0), (1, 1.0)]

    # 4. Test cue.update
    updated_events.clear()
    channels_to_set = {1: 1.0, 2: 0.5}
    app.action_registry.execute("cue.update", 1.0, 1, channels_to_set)
    assert cue1.channels == {1: 1.0, 2: 0.5}
    assert updated_events == [(1, 1.0)]

    # Undo cue.update
    app.history.undo()
    assert cue1.channels == {}

    # Redo cue.update
    app.history.redo()
    assert cue1.channels == {1: 1.0, 2: 0.5}

    # 5. Test cue.set_channel_level
    updated_events.clear()
    app.action_registry.execute("cue.set_channel_level", 1.0, 1, 1, 0.8)
    assert cue1.channels[1] == 0.8
    assert updated_events == [(1, 1.0)]

    # Undo set channel level
    app.history.undo()
    assert cue1.channels[1] == 1.0

    # Redo set channel level
    app.history.redo()
    assert cue1.channels[1] == 0.8


def test_cue_rename_and_copy() -> None:
    """Test cue rename and copy actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    created_events = []
    deleted_events = []
    updated_events = []

    app.subscribe(
        "cue.created", lambda seq, cue_num: created_events.append((seq, cue_num))
    )
    app.subscribe(
        "cue.deleted", lambda seq, cue_num: deleted_events.append((seq, cue_num))
    )
    app.subscribe(
        "cue.updated", lambda seq, cue_num: updated_events.append((seq, cue_num))
    )

    # Insert baseline cue 1.0
    app.action_registry.execute("cue.insert", 1.0, 1)
    app.action_registry.execute("cue.update", 1.0, 1, {1: 200, 2: 128})
    cue1 = app.lightshow.get_cue(1.0, 1)
    assert cue1 is not None

    # 1. Test cue.rename
    updated_events.clear()
    app.action_registry.execute("cue.rename", 1.0, 1, "Test Name")
    assert cue1.text == "Test Name"
    assert updated_events == [(1, 1.0)]

    # Undo rename
    app.history.undo()
    assert cue1.text == ""

    # Redo rename
    app.history.redo()
    assert cue1.text == "Test Name"

    # 2. Test cue.copy (creating a new destination cue)
    created_events.clear()
    updated_events.clear()
    app.action_registry.execute("cue.copy", 1.0, 2.0, 1)
    cue2 = app.lightshow.get_cue(2.0, 1)
    assert cue2 is not None
    assert cue2.number == 2.0
    assert cue2.channels == {1: 200, 2: 128}
    assert created_events == [(1, 2.0)]
    assert updated_events == [(1, 2.0)]

    # Undo copy (should remove the destination cue)
    deleted_events.clear()
    app.history.undo()
    assert app.lightshow.get_cue(2.0, 1) is None
    assert deleted_events == [(1, 2.0)]

    # Redo copy
    created_events.clear()
    app.history.redo()
    cue2 = app.lightshow.get_cue(2.0, 1)
    assert cue2 is not None
    assert cue2.number == 2.0
    assert cue2.channels == {1: 200, 2: 128}
    assert created_events == [(1, 2.0)]

    # 3. Test cue.copy (overwriting existing cue)
    # Update cue 1.0 first
    app.action_registry.execute("cue.update", 1.0, 1, {3: 50})
    # Copy 1.0 into 2.0
    created_events.clear()
    updated_events.clear()
    app.action_registry.execute("cue.copy", 1.0, 2.0, 1)
    cue2 = app.lightshow.get_cue(2.0, 1)
    assert cue2 is not None
    assert cue2.channels == {3: 50}
    assert not created_events  # Not created since it already existed
    assert updated_events == [(1, 2.0)]

    # Undo overwrite copy
    app.history.undo()
    cue2 = app.lightshow.get_cue(2.0, 1)
    assert cue2 is not None
    assert cue2.channels == {1: 200, 2: 128}

    # Redo overwrite copy
    app.history.redo()
    cue2 = app.lightshow.get_cue(2.0, 1)
    assert cue2 is not None
    assert cue2.channels == {3: 50}


def test_cue_delete() -> None:
    """Test cue delete action."""
    settings = MagicMock()
    app = CoreApplication(settings)

    created_events = []
    deleted_events = []

    app.subscribe(
        "cue.created", lambda seq, cue_num: created_events.append((seq, cue_num))
    )
    app.subscribe(
        "cue.deleted", lambda seq, cue_num: deleted_events.append((seq, cue_num))
    )

    # Insert baseline cue 2.0
    app.action_registry.execute("cue.insert", 2.0, 1)
    app.action_registry.execute("cue.update", 2.0, 1, {3: 50})

    # 1. Test cue.delete
    deleted_events.clear()
    app.action_registry.execute("cue.delete", 2.0, 1)
    assert app.lightshow.get_cue(2.0, 1) is None
    assert deleted_events == [(1, 2.0)]

    # Undo delete
    created_events.clear()
    app.history.undo()
    cue2 = app.lightshow.get_cue(2.0, 1)
    assert cue2 is not None
    assert cue2.number == 2.0
    assert cue2.channels == {3: 50}
    assert created_events == [(1, 2.0)]

    # Redo delete
    deleted_events.clear()
    app.history.redo()
    assert app.lightshow.get_cue(2.0, 1) is None
    assert deleted_events == [(1, 2.0)]


def test_cue_actions_errors() -> None:
    """Test validation errors for cue actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Try update non-existent cue
    with pytest.raises(ValueError, match="Cue 1.0 \\(seq 1\\) does not exist"):
        app.action_registry.execute("cue.update", 1.0, 1, {})

    # Try delete non-existent cue
    with pytest.raises(ValueError, match="Cue 1.0 \\(seq 1\\) does not exist"):
        app.action_registry.execute("cue.delete", 1.0, 1)

    # Insert existing cue
    app.action_registry.execute("cue.insert", 1.0, 1)
    with pytest.raises(ValueError, match="Cue 1.0 \\(seq 1\\) already exists"):
        app.action_registry.execute("cue.insert", 1.0, 1)


def test_cue_select_action_undo_redo() -> None:
    """Test cue select action, including undo and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Set up cues
    app.action_registry.execute("cue.insert", 1.0, 0)
    app.action_registry.execute("cue.insert", 2.0, 0)

    # Track selection events
    received_selections: list[tuple[float, int] | None] = []
    app.subscribe("cue.selected_changed", received_selections.append)

    # 1. Test cue.select with cue (1.0, 0)
    app.action_registry.execute("cue.select", (1.0, 0))
    assert app.selected_cue == (1.0, 0)
    assert received_selections == [(1.0, 0)]

    # 2. Test cue.select with cue (2.0, 0)
    app.action_registry.execute("cue.select", (2.0, 0))
    assert app.selected_cue == (2.0, 0)
    assert received_selections == [(1.0, 0), (2.0, 0)]

    # 3. Undo
    app.history.undo()
    assert app.selected_cue == (1.0, 0)
    assert received_selections == [(1.0, 0), (2.0, 0), (1.0, 0)]

    # 4. Undo again
    app.history.undo()
    assert app.selected_cue is None
    assert received_selections == [(1.0, 0), (2.0, 0), (1.0, 0), None]

    # 5. Redo
    app.history.redo()
    assert app.selected_cue == (1.0, 0)
    assert received_selections == [(1.0, 0), (2.0, 0), (1.0, 0), None, (1.0, 0)]

    # 6. Redo again
    app.history.redo()
    assert app.selected_cue == (2.0, 0)
    assert received_selections == [
        (1.0, 0),
        (2.0, 0),
        (1.0, 0),
        None,
        (1.0, 0),
        (2.0, 0),
    ]

    # 7. Unselect cue
    app.action_registry.execute("cue.select", None)
    assert app.selected_cue is None
    assert received_selections[-1] is None


def test_cue_flags_and_notes_actions_with_undo_redo() -> None:
    """Test cue.set_block, cue.set_int_block, cue.set_assert, and cue.set_notes."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.action_registry.execute("sequence.new", 2.0)
    app.action_registry.execute("sequence.insert_step", 2.0, 1, 10.0, {1: 200})

    seq = app.lightshow.get_sequence(2.0)
    assert seq is not None
    cue = seq.steps[1].cue
    assert cue is not None

    app.action_registry.execute("cue.set_block", 10.0, True, 2)
    assert cue.is_block is True
    app.history.undo()
    assert cue.is_block is False
    app.history.redo()
    assert cue.is_block is True

    app.action_registry.execute("cue.set_int_block", 10.0, True, 2)
    assert cue.is_int_block is True
    app.history.undo()
    assert cue.is_int_block is False

    app.action_registry.execute("cue.set_assert", 10.0, True, 2)
    assert cue.is_assert is True
    app.history.undo()
    assert cue.is_assert is False

    app.action_registry.execute("cue.set_notes", 10.0, "Spot cue note", 2)
    assert cue.notes == "Spot cue note"
    app.history.undo()
    assert cue.notes == ""
    app.history.redo()
    assert cue.notes == "Spot cue note"
