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
"""Unit tests for Sequence tracking display color classification and controls."""

# pylint: disable=redefined-outer-name, protected-access, too-many-locals

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")

from olc.cue import Cue  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.sequence import (  # noqa: E402
    TRACKING_COLORS,
    SequenceTab,
    TrackingDisplayState,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.sequence import Sequence  # noqa: E402
from olc.step import Step  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order


def test_tracking_color_classification_states() -> None:
    """Test HARD_VALUE, TRACKED_VALUE, INTENSITY_UP, INTENSITY_DOWN, and BLOCK."""
    seq = Sequence(index=1, type_seq="Main")
    seq.tracking_mode = True
    seq.steps.clear()

    # Step 0: initial empty step
    seq.steps.append(Step(sequence=1))

    # Step 1 (Cue 1.0): ch 1 = 128, ch 2 = 200 -> HARD_VALUE (White)
    cue1 = Cue(sequence=1, number=1.0, channels={1: 128, 2: 200})
    seq.steps.append(Step(sequence=1, cue=cue1))

    # Step 2 (Cue 2.0): ch 1 tracked, ch 2 = 255 (UP), ch 3 = 100 (UP from 0)
    cue2 = Cue(sequence=1, number=2.0, channels={2: 255, 3: 100})
    seq.steps.append(Step(sequence=1, cue=cue2))

    # Step 3 (Cue 3.0): ch 2 = 80 (DOWN from 255), ch 3 = 100 (HARD_VALUE)
    cue3 = Cue(sequence=1, number=3.0, channels={2: 80, 3: 100})
    seq.steps.append(Step(sequence=1, cue=cue3))

    # Step 4 (Cue 4.0): Block cue
    cue4 = Cue(sequence=1, number=4.0, channels={1: 128}, is_block=True)
    seq.steps.append(Step(sequence=1, cue=cue4))

    # Verify Step 1
    state1_ch1, lvl1_ch1 = classify_channel_tracking_state(seq, 1, 1)
    assert state1_ch1 == TrackingDisplayState.HARD_VALUE
    assert lvl1_ch1 == 128
    assert (
        get_tracking_color(state1_ch1)
        == TRACKING_COLORS[TrackingDisplayState.HARD_VALUE]
    )

    # Verify Step 2: ch 1 is TRACKED_VALUE (Cyan), ch 2 is INTENSITY_UP (Blue)
    state2_ch1, lvl2_ch1 = classify_channel_tracking_state(seq, 2, 1)
    assert state2_ch1 == TrackingDisplayState.TRACKED_VALUE
    assert lvl2_ch1 == 128
    assert (
        get_tracking_color(state2_ch1)
        == TRACKING_COLORS[TrackingDisplayState.TRACKED_VALUE]
    )

    state2_ch2, lvl2_ch2 = classify_channel_tracking_state(seq, 2, 2)
    assert state2_ch2 == TrackingDisplayState.INTENSITY_UP
    assert lvl2_ch2 == 255
    assert (
        get_tracking_color(state2_ch2)
        == TRACKING_COLORS[TrackingDisplayState.INTENSITY_UP]
    )

    # Verify Step 3: ch 2 is INTENSITY_DOWN (Green), ch 3 is HARD_VALUE (White)
    state3_ch2, lvl3_ch2 = classify_channel_tracking_state(seq, 3, 2)
    assert state3_ch2 == TrackingDisplayState.INTENSITY_DOWN
    assert lvl3_ch2 == 80
    assert (
        get_tracking_color(state3_ch2)
        == TRACKING_COLORS[TrackingDisplayState.INTENSITY_DOWN]
    )

    state3_ch3, lvl3_ch3 = classify_channel_tracking_state(seq, 3, 3)
    assert state3_ch3 == TrackingDisplayState.HARD_VALUE
    assert lvl3_ch3 == 100

    # Verify Step 4: Block Cue (Magenta)
    state4_ch1, lvl4_ch1 = classify_channel_tracking_state(seq, 4, 1)
    assert state4_ch1 == TrackingDisplayState.BLOCK
    assert lvl4_ch1 == 128
    assert get_tracking_color(state4_ch1) == TRACKING_COLORS[TrackingDisplayState.BLOCK]


@pytest.mark.gui
def test_sequence_tab_tracking_mode_toggle(app_gui: Application) -> None:
    """Test SequenceTab header toggle button switching between Cue-Only and Tracking."""
    app_gui.activate_action("sequences", None)
    process_events()

    assert app_gui.tabs is not None
    seq_tab = app_gui.tabs.tabs.get("sequences")
    assert isinstance(seq_tab, SequenceTab)

    seq_tab.set_tracking_mode(False)
    assert app_gui.core.lightshow.main_playback.tracking_mode is False
    assert "Cue-Only" in seq_tab.tracking_mode_btn.get_label()

    new_state = seq_tab.toggle_tracking_mode()
    assert new_state is True
    assert app_gui.core.lightshow.main_playback.tracking_mode is True
    assert "Tracking" in seq_tab.tracking_mode_btn.get_label()
