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
"""GTK3 tests for multi-sequence UI controls in FaderEdit, VC, and SequenceTab."""

from __future__ import annotations

import pytest

from olc.core.playback_arbitrator import PlaybackPriority
from olc.gtk3.application import Application
from olc.gtk3.fader import FaderTab
from olc.gtk3.sequence import SequenceTab
from olc.show.cue import Cue
from olc.show.fader import FaderSequence, FaderType
from olc.show.sequence import Sequence
from olc.show.step import Step
from test.gtk3.conftest import process_events

pytestmark = pytest.mark.gui


def test_gtk3_multi_sequence_fader_edit_vc_and_sequence_tab(
    app_gui: Application,
) -> None:
    """Verify FaderEdit seq options, VC active cue label, and SequenceTab buttons."""
    ls = app_gui.core.lightshow
    ls.fader_bank.reset_faders(reset_page_count=True)

    try:
        seq2 = Sequence(2, text="Overlay", lightshow=ls)
        cue10 = Cue(2, 10.0, channels={1: 0.75}, text="Q10")
        seq2.cues.add(cue10)
        seq2.insert_step(len(seq2.steps) - 1, Step(sequence=2, cue=cue10))
        ls.sequences.append(seq2)

        app_gui.core.action_registry.execute(
            "fader.assign", 1, 1, FaderType.SEQUENCE, 2
        )
        app_gui.activate_action("faders", None)
        app_gui.activate_action("virtual_console", None)
        app_gui.activate_action("sequences", None)
        process_events()

        assert app_gui.tabs is not None
        fader_tab = app_gui.tabs.tabs.get("faders")
        seq_tab = app_gui.tabs.tabs.get("sequences")
        assert isinstance(fader_tab, FaderTab)
        assert isinstance(seq_tab, SequenceTab)
        assert app_gui.virtual_console is not None
        vc = app_gui.virtual_console

        # 1. FaderEdit shows sequence options for FaderSequence & updates via action
        fader_edit = fader_tab.fader_widgets.get((1, 1))
        assert fader_edit is not None
        assert fader_edit.seq_options_box.get_visible() is True

        fader_edit.seq_option_checks["auto_start"].set_active(True)
        fader_edit.seq_priority_combo.set_active_id(str(int(PlaybackPriority.HIGH)))
        process_events()
        assert seq2.auto_start is True
        assert seq2.priority is PlaybackPriority.HIGH

        # Undo priority change -> back to NORMAL
        app_gui.core.history.undo()
        process_events()
        assert seq2.priority is PlaybackPriority.NORMAL

        # 2. Raising FaderSequence with auto_start activates Seq 2 -> VC label shows Q10
        fader = ls.fader_bank.faders[1][1]
        assert isinstance(fader, FaderSequence)
        fader.set_level(1.0)
        process_events()
        lbl = vc.format_fader_flash_label(fader)
        assert "Q10" in lbl

        # 3. SequenceTab priority combo & Release All button
        seq_tab.seq_priority_combo.set_active_id(str(int(PlaybackPriority.SUPER)))
        process_events()
        assert ls.main_playback.priority is PlaybackPriority.SUPER

        app_gui.core.history.undo()
        process_events()
        assert ls.main_playback.priority is PlaybackPriority.NORMAL

        seq_tab.seq_release_all_btn.emit("clicked")
        process_events()
        assert app_gui.core.playback_arbitrator.active_sequences() == []
    finally:
        app_gui.core.playback_arbitrator.clear()
        ls.main_playback.priority = PlaybackPriority.NORMAL
        ls.fader_bank.reset_faders(reset_page_count=True)
        ls.sequences.clear()
        app_gui.core.history.clear()
        process_events()
