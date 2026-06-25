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
"""Unit tests for Sequence and Step actions and HistoryManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from olc.core.app import CoreApplication


def test_sequence_new_delete_actions_and_undo_redo() -> None:
    """Test sequence (chaser) creation, deletion, undo, and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clear chasers list
    app.lightshow.chasers.clear()

    created_events = []
    deleted_events = []
    app.subscribe("sequence.created", created_events.append)
    app.subscribe("sequence.deleted", deleted_events.append)

    # 1. Create a new sequence 2.0
    app.action_registry.execute("sequence.new", 2.0)
    assert len(app.lightshow.chasers) == 1
    assert app.lightshow.chasers[0].index == 2.0
    assert len(created_events) == 1
    assert created_events[0].index == 2.0

    # 2. Duplicate check
    with pytest.raises(ValueError, match="Chaser sequence 2.0 already exists"):
        app.action_registry.execute("sequence.new", 2.0)

    # 3. Reserved index check
    with pytest.raises(ValueError, match="Chaser sequence cannot use index 1.0"):
        app.action_registry.execute("sequence.new", 1.0)

    # 4. Undo creation
    app.history.undo()
    assert len(app.lightshow.chasers) == 0
    assert len(deleted_events) == 1
    assert deleted_events[0].index == 2.0

    # 5. Redo creation
    app.history.redo()
    assert len(app.lightshow.chasers) == 1
    assert app.lightshow.chasers[0].index == 2.0

    # 6. Delete sequence
    created_events.clear()
    deleted_events.clear()
    app.action_registry.execute("sequence.delete", 2.0)
    assert len(app.lightshow.chasers) == 0
    assert len(deleted_events) == 1
    assert deleted_events[0].index == 2.0

    # 7. Undo delete
    app.history.undo()
    assert len(app.lightshow.chasers) == 1
    assert app.lightshow.chasers[0].index == 2.0
    assert len(created_events) == 1
    assert created_events[0].index == 2.0

    # 8. Redo delete
    app.history.redo()
    assert len(app.lightshow.chasers) == 0


# pylint: disable=too-many-statements
def test_sequence_insert_delete_step_actions_and_undo_redo() -> None:
    """Test inserting and deleting steps, including undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Set up a chaser sequence (index 2.0)
    app.lightshow.chasers.clear()
    app.action_registry.execute("sequence.new", 2.0)
    chaser = app.lightshow.chasers[0]
    # A new chaser has exactly 1 step initially (step 0 at index 0)
    assert len(chaser.steps) == 1
    assert chaser.steps[0].cue.number == 0.0

    inserted_steps = []
    deleted_steps = []
    created_cues = []
    deleted_cues = []

    app.subscribe("step.inserted", lambda seq, step: inserted_steps.append((seq, step)))
    app.subscribe("step.deleted", lambda seq, step: deleted_steps.append((seq, step)))
    app.subscribe("cue.created", lambda seq, num: created_cues.append((seq, num)))
    app.subscribe("cue.deleted", lambda seq, num: deleted_cues.append((seq, num)))

    # 1. Insert step 1 with cue number 10.0 and some channels
    app.action_registry.execute("sequence.insert_step", 2.0, 1, 10.0, {1: 255, 2: 128})
    assert len(chaser.steps) == 2
    assert chaser.steps[0].cue.number == 0.0
    assert chaser.steps[1].cue.number == 10.0
    assert chaser.steps[1].cue.channels == {1: 255, 2: 128}
    assert inserted_steps == [(2.0, 1)]
    assert created_cues == [(2, 10.0)]

    # 2. Undo insert step
    app.history.undo()
    assert len(chaser.steps) == 1
    assert chaser.steps[0].cue.number == 0.0
    assert deleted_steps == [(2.0, 1)]
    assert deleted_cues == [(2, 10.0)]

    # 3. Redo insert step
    inserted_steps.clear()
    deleted_steps.clear()
    created_cues.clear()
    deleted_cues.clear()
    app.history.redo()
    assert len(chaser.steps) == 2
    assert chaser.steps[0].cue.number == 0.0
    assert chaser.steps[1].cue.number == 10.0
    assert inserted_steps == [(2.0, 1)]
    assert created_cues == [(2, 10.0)]

    # 4. Insert step 2 with cue number 20.0
    app.action_registry.execute("sequence.insert_step", 2.0, 2, 20.0, {3: 200})
    assert len(chaser.steps) == 3
    assert chaser.steps[2].cue.number == 20.0

    # 5. Delete step 1
    inserted_steps.clear()
    deleted_steps.clear()
    app.action_registry.execute("sequence.delete_step", 2.0, 1)
    assert len(chaser.steps) == 2
    assert chaser.steps[0].cue.number == 0.0
    assert chaser.steps[1].cue.number == 20.0
    assert deleted_steps == [(2.0, 1)]

    # 6. Undo delete step
    app.history.undo()
    assert len(chaser.steps) == 3
    assert chaser.steps[0].cue.number == 0.0
    assert chaser.steps[1].cue.number == 10.0
    assert chaser.steps[2].cue.number == 20.0
    assert inserted_steps == [(2.0, 1)]


def test_step_update_times_and_text_actions_and_undo_redo() -> None:
    """Test updating step times and text, including undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.chasers.clear()
    app.action_registry.execute("sequence.new", 2.0)
    chaser = app.lightshow.chasers[0]

    app.action_registry.execute("sequence.insert_step", 2.0, 1, 10.0)
    step = chaser.steps[1]

    # Verify initial default times and text
    assert step.wait == 0.0
    assert step.time_in == 5.0
    assert step.text == ""

    updated_events = []
    app.subscribe(
        "step.updated", lambda seq, step_idx: updated_events.append((seq, step_idx))
    )

    # 1. Update times
    app.action_registry.execute("step.update_times", 2.0, 1, time_in=2.5, wait=1.0)
    assert step.time_in == 2.5
    assert step.wait == 1.0
    assert updated_events == [(2.0, 1)]

    # Undo
    app.history.undo()
    assert step.time_in == 5.0
    assert step.wait == 0.0

    # Redo
    app.history.redo()
    assert step.time_in == 2.5
    assert step.wait == 1.0

    # 2. Update text
    updated_events.clear()
    app.action_registry.execute("step.update_text", 2.0, 1, "My Cool Step")
    assert step.text == "My Cool Step"
    assert updated_events == [(2.0, 1)]

    # Undo
    app.history.undo()
    assert step.text == ""

    # Redo
    app.history.redo()
    assert step.text == "My Cool Step"


def test_step_update_channel_time_action_and_undo_redo() -> None:
    """Test updating channel-specific times within a step, including undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.chasers.clear()
    app.action_registry.execute("sequence.new", 2.0)
    chaser = app.lightshow.chasers[0]

    app.action_registry.execute("sequence.insert_step", 2.0, 1, 10.0)
    step = chaser.steps[1]
    assert step.channel_time == {}

    # 1. Set channel 5 time to delay=1.0, time=3.0
    app.action_registry.execute(
        "step.update_channel_time", 2.0, 1, 5, delay=1.0, time=3.0
    )
    assert 5 in step.channel_time
    assert step.channel_time[5].delay == 1.0
    assert step.channel_time[5].time == 3.0

    # 2. Undo
    app.history.undo()
    assert 5 not in step.channel_time

    # 3. Redo
    app.history.redo()
    assert 5 in step.channel_time
    assert step.channel_time[5].delay == 1.0
    assert step.channel_time[5].time == 3.0

    # 4. Modify only delay
    app.action_registry.execute("step.update_channel_time", 2.0, 1, 5, delay=2.5)
    assert step.channel_time[5].delay == 2.5
    assert step.channel_time[5].time == 3.0

    # Undo
    app.history.undo()
    assert step.channel_time[5].delay == 1.0
    assert step.channel_time[5].time == 3.0

    # 5. Delete by setting both to 0.0
    app.action_registry.execute(
        "step.update_channel_time", 2.0, 1, 5, delay=0.0, time=0.0
    )
    assert 5 not in step.channel_time

    # Undo deletion
    app.history.undo()
    assert 5 in step.channel_time
    assert step.channel_time[5].delay == 1.0
    assert step.channel_time[5].time == 3.0
