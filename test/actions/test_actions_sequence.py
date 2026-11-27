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
    """Test sequence creation, deletion, undo, and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clear sequences list
    app.lightshow.sequences.clear()

    created_events = []
    deleted_events = []
    app.subscribe("sequence.created", created_events.append)
    app.subscribe("sequence.deleted", deleted_events.append)

    # 1. Create a new sequence 2.0
    app.action_registry.execute("sequence.new", 2.0)
    assert len(app.lightshow.sequences) == 1
    assert app.lightshow.sequences[0].index == 2.0
    assert len(created_events) == 1
    assert created_events[0].index == 2.0

    # 2. Duplicate check
    with pytest.raises(ValueError, match="Sequence 2.0 already exists"):
        app.action_registry.execute("sequence.new", 2.0)

    # 3. Reserved index check
    with pytest.raises(ValueError, match="Secondary sequence cannot use index 1.0"):
        app.action_registry.execute("sequence.new", 1.0)

    # 4. Undo creation
    app.history.undo()
    assert len(app.lightshow.sequences) == 0
    assert len(deleted_events) == 1
    assert deleted_events[0].index == 2.0

    # 5. Redo creation
    app.history.redo()
    assert len(app.lightshow.sequences) == 1
    assert app.lightshow.sequences[0].index == 2.0

    # 6. Delete sequence
    created_events.clear()
    deleted_events.clear()
    app.action_registry.execute("sequence.delete", 2.0)
    assert len(app.lightshow.sequences) == 0
    assert len(deleted_events) == 1
    assert deleted_events[0].index == 2.0

    # 7. Undo delete
    app.history.undo()
    assert len(app.lightshow.sequences) == 1
    assert app.lightshow.sequences[0].index == 2.0
    assert len(created_events) == 1
    assert created_events[0].index == 2.0

    # 8. Redo delete
    app.history.redo()
    assert len(app.lightshow.sequences) == 0


# pylint: disable=too-many-statements
def test_sequence_insert_delete_step_actions_and_undo_redo() -> None:
    """Test inserting and deleting steps, including undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Set up a secondary sequence (index 2.0)
    app.lightshow.sequences.clear()
    app.action_registry.execute("sequence.new", 2.0)
    seq = app.lightshow.sequences[0]
    # A new sequence has exactly 1 step initially (step 0 at index 0)
    assert len(seq.steps) == 1
    assert seq.steps[0].cue.number == 0.0

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
    assert len(seq.steps) == 2
    assert seq.steps[0].cue.number == 0.0
    assert seq.steps[1].cue.number == 10.0
    assert seq.steps[1].cue.channels == {1: 255, 2: 128}
    assert inserted_steps == [(2.0, 1)]
    assert created_cues == [(2, 10.0)]

    # 2. Undo insert step
    app.history.undo()
    assert len(seq.steps) == 1
    assert seq.steps[0].cue.number == 0.0
    assert deleted_steps == [(2.0, 1)]
    assert deleted_cues == [(2, 10.0)]

    # 3. Redo insert step
    inserted_steps.clear()
    deleted_steps.clear()
    created_cues.clear()
    deleted_cues.clear()
    app.history.redo()
    assert len(seq.steps) == 2
    assert seq.steps[0].cue.number == 0.0
    assert seq.steps[1].cue.number == 10.0
    assert inserted_steps == [(2.0, 1)]
    assert created_cues == [(2, 10.0)]

    # 4. Insert step 2 with cue number 20.0
    app.action_registry.execute("sequence.insert_step", 2.0, 2, 20.0, {3: 200})
    assert len(seq.steps) == 3
    assert seq.steps[2].cue.number == 20.0

    # 5. Delete step 1
    inserted_steps.clear()
    deleted_steps.clear()
    app.action_registry.execute("sequence.delete_step", 2.0, 1)
    assert len(seq.steps) == 2
    assert seq.steps[0].cue.number == 0.0
    assert seq.steps[1].cue.number == 20.0
    assert deleted_steps == [(2.0, 1)]

    # 6. Undo delete step
    app.history.undo()
    assert len(seq.steps) == 3
    assert seq.steps[0].cue.number == 0.0
    assert seq.steps[1].cue.number == 10.0
    assert seq.steps[2].cue.number == 20.0
    assert inserted_steps == [(2.0, 1)]


def test_step_update_times_and_text_actions_and_undo_redo() -> None:
    """Test updating step times and text, including undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.sequences.clear()
    app.action_registry.execute("sequence.new", 2.0)
    seq = app.lightshow.sequences[0]

    app.action_registry.execute("sequence.insert_step", 2.0, 1, 10.0)
    step = seq.steps[1]

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

    app.lightshow.sequences.clear()
    app.action_registry.execute("sequence.new", 2.0)
    seq = app.lightshow.sequences[0]

    app.action_registry.execute("sequence.insert_step", 2.0, 1, 10.0)
    step = seq.steps[1]
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


def test_step_link_loop_and_curve_actions_and_engine() -> None:
    """Test step.set_link, step.set_curve, _next_step loops, and _apply_step_curve."""
    import pytest

    from olc.show.cue import Cue
    from olc.show.curve import SegmentsCurve
    from olc.show.sequence_threads import ThreadGo, _apply_step_curve
    from olc.show.step import Step

    app = CoreApplication(MagicMock())
    seq = app.lightshow.main_playback
    for num in (1.0, 2.0, 3.0, 4.0):
        cue = Cue(1, num, {1: num * 0.2})
        seq.insert_step(seq.last - 1, Step(1, cue, time_in=1.0, time_out=1.0))

    step_updated_events: list[tuple[float, int]] = []
    app.subscribe(
        "step.updated",
        lambda seq_idx, step_idx: step_updated_events.append((seq_idx, step_idx)),
    )

    # 1. step.set_link + Undo/Redo + step.updated emission
    app.action_registry.execute("step.set_link", 1.0, 3, 1.0, 2)
    assert seq.steps[3].link_cue == 1.0
    assert seq.steps[3].loop_count == 2
    assert (1.0, 3) in step_updated_events

    app.history.undo()
    assert seq.steps[3].link_cue is None
    assert seq.steps[3].loop_count == 0

    app.history.redo()
    assert seq.steps[3].link_cue == 1.0
    assert seq.steps[3].loop_count == 2

    # Go from step 3 twice -> lands on step 1 (Q1); 3rd Go -> step 4 (Q4)
    seq.position = 3
    t1 = ThreadGo(False, seq)
    assert t1.target_step == 1
    t1._finalize_go()  # pylint: disable=protected-access
    assert seq.position == 1

    seq.position = 3
    t2 = ThreadGo(False, seq)
    assert t2.target_step == 1
    t2._finalize_go()  # pylint: disable=protected-access
    assert seq.position == 1

    seq.position = 3
    t3 = ThreadGo(False, seq)
    assert t3.target_step == 4
    t3._finalize_go()  # pylint: disable=protected-access
    assert seq.position == 4

    # Link on the last cue (step 4 -> Q1) is honored instead of wrapping/releasing
    app.action_registry.execute("step.set_link", 1.0, 4, 1.0, 0)
    t4 = ThreadGo(False, seq)
    assert t4.target_step == 1
    t4._finalize_go()  # pylint: disable=protected-access
    assert seq.position == 1

    # 2. step.set_curve + Undo/Redo + _apply_step_curve
    curve = SegmentsCurve()
    curve.set_points([(0, 0), (128, 200), (255, 255)])
    app.lightshow.curves.curves[10] = curve

    app.action_registry.execute("step.set_curve", 1.0, 2, 10)
    assert seq.steps[2].curve_id == 10
    assert _apply_step_curve(app.lightshow, 10, 0.5) == pytest.approx(
        curve.evaluate_normalized(0.5)
    )

    app.history.undo()
    assert seq.steps[2].curve_id == 0
    assert _apply_step_curve(app.lightshow, 0, 0.5) == pytest.approx(0.5)


def test_playback_seq_plus_minus_emit_next_curve_id() -> None:
    """Seq+ and Seq- feedback must include next_curve_id for the upcoming cue."""
    from olc.show.cue import Cue
    from olc.show.step import Step

    app = CoreApplication(MagicMock())
    seq = app.lightshow.main_playback
    for num, cid in ((1.0, 0), (2.0, 10), (3.0, 0)):
        cue = Cue(1, num, {1: 0.5})
        seq.insert_step(
            seq.last - 1, Step(1, cue, time_in=1.0, time_out=1.0, curve_id=cid)
        )

    plus_events: list[dict[str, object]] = []
    minus_events: list[dict[str, object]] = []
    app.subscribe("playback.sequence_plus_triggered", plus_events.append)
    app.subscribe("playback.sequence_minus_triggered", minus_events.append)

    seq.position = 0
    app.action_registry.execute("playback.sequence_plus")
    assert seq.position == 1
    assert plus_events[-1]["next_curve_id"] == 10

    app.action_registry.execute("playback.sequence_plus")
    assert seq.position == 2
    assert plus_events[-1]["next_curve_id"] == 0

    app.action_registry.execute("playback.sequence_minus")
    assert seq.position == 1
    assert minus_events[-1]["next_curve_id"] == 10
