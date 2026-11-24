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
"""GTK3 tests verifying full UI & control sync when switching MAIN Sequence."""

from __future__ import annotations

import pytest

from olc.gtk3.application import Application
from olc.show.cue import Cue
from olc.show.sequence import Sequence
from olc.show.step import Step
from test.gtk3.conftest import process_events


@pytest.mark.gui
def test_switch_main_sequence_updates_ui_and_controls(app_gui: Application) -> None:
    """Switching Seq 2 to MAIN updates MainPlaybackView, Header, Sequential, & nav."""
    ls = app_gui.core.lightshow
    seq1 = ls.main_playback
    orig_seq1_text = seq1.text
    seq1.text = ""

    # Populate Seq 1 with Cue 1.0 and 2.0
    for num in (1.0, 2.0):
        cue = Cue(1, num, channels={1: 255}, text=f"S1Q{num:g}")
        seq1.cues.add(cue)
        seq1.insert_step(len(seq1.steps) - 1, Step(sequence=1, cue=cue))

    # Create Seq 2 ("Overlay") with Cue 10.0 and 20.0 (custom time_in=3.5 on Cue 10)
    seq2 = Sequence(2, text="Overlay", lightshow=ls)
    c10 = Cue(2, 10.0, channels={2: 200}, text="Intro")
    seq2.cues.add(c10)
    s10 = Step(sequence=2, cue=c10, time_in=3.5, time_out=3.5)
    seq2.insert_step(len(seq2.steps) - 1, s10)

    c20 = Cue(2, 20.0, channels={3: 180}, text="Chorus")
    seq2.cues.add(c20)
    s20 = Step(sequence=2, cue=c20, time_in=7.0, time_out=7.0)
    seq2.insert_step(len(seq2.steps) - 1, s20)
    ls.sequences.append(seq2)

    assert app_gui.window is not None
    assert app_gui.window.playback is not None
    pb_view = app_gui.window.playback

    try:
        # Switch MAIN to Seq 2
        assert app_gui.core.action_registry.execute("playback.set_main_sequence", 2.0)
        process_events()

        # 1. Tab label reflects Seq 2 and its name
        assert pb_view._tab_label.get_text() == "Main · Seq 2 — Overlay"

        # 2. cues_liststore1 shows Seq 2's cues (10.0, 20.0), not Seq 1's (1.0, 2.0)
        cue_nums = [row[1] for row in pb_view.cues_liststore1 if row[1]]
        assert cue_nums == ["10.0", "20.0"]

        # 3. SequentialWidget shows Seq 2 next step timing (3.5s)
        assert pb_view.sequential.time_in == pytest.approx(3.5)

        # 4. HeaderBar subtitle shows Seq 2 prefix
        assert app_gui.window.header is not None
        assert (app_gui.window.header.get_subtitle() or "").startswith("Seq 2 — ")

        # 5. Seq+ / Seq- / Goto drive Seq 2 and leave Seq 1 untouched
        app_gui.core.action_registry.execute("playback.sequence_plus")
        process_events()
        assert seq2.position == 1
        assert seq1.position == 0

        app_gui.core.action_registry.execute("playback.sequence_plus")
        process_events()
        assert seq2.position == 2
        assert seq1.position == 0

        app_gui.core.action_registry.execute("playback.sequence_minus")
        process_events()
        assert seq2.position == 1
        assert seq1.position == 0

        # 6. Rename Seq 2 via sequence.rename -> MainPlaybackView tab title updates
        app_gui.core.action_registry.execute("sequence.rename", 2.0, "Renamed Overlay")
        process_events()
        assert pb_view._tab_label.get_text() == "Main · Seq 2 — Renamed Overlay"

        # 7. Switch back to Seq 1
        assert app_gui.core.action_registry.execute("playback.set_main_sequence", 1.0)
        process_events()
        assert pb_view._tab_label.get_text() == "Main · Seq 1"
        cue_nums_back = [row[1] for row in pb_view.cues_liststore1 if row[1]]
        assert cue_nums_back == ["1.0", "2.0"]
    finally:
        seq1.text = orig_seq1_text
        if seq2 in ls.sequences:
            ls.sequences.remove(seq2)
        app_gui.core.playback_engine.set_main_sequence(1.0)
