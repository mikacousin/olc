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


def test_tracking_color_classification_mib_state() -> None:
    """Test TrackingDisplayState.MIB when a dark fixture pre-positions for next cue."""
    seq = Sequence(index=1, type_seq="Main")
    seq.tracking_mode = True
    seq.mib_enabled = True
    seq.steps.clear()
    seq.steps.append(Step(sequence=1))

    # Step 1 (Cue 1.0): Fixture 1 ON at Pan 0
    cue1 = Cue(sequence=1, number=1.0)
    cue1.set_device_parameter(1, "intensity", 1.0)
    cue1.set_device_parameter(1, "pan", 0.0)
    seq.steps.append(Step(sequence=1, cue=cue1))

    # Step 2 (Cue 2.0): Fixture 1 OFF (MIB pre-positions Pan to 90 for Cue 3.0)
    cue2 = Cue(sequence=1, number=2.0)
    cue2.set_device_parameter(1, "intensity", 0.0)
    seq.steps.append(Step(sequence=1, cue=cue2))

    # Step 3 (Cue 3.0): Fixture 1 ON at Pan 90
    cue3 = Cue(sequence=1, number=3.0)
    cue3.set_device_parameter(1, "intensity", 1.0)
    cue3.set_device_parameter(1, "pan", 90.0)
    seq.steps.append(Step(sequence=1, cue=cue3))

    state2, lvl2 = classify_channel_tracking_state(seq, 2, 1)
    assert state2 == TrackingDisplayState.MIB
    assert lvl2 == 0
    assert get_tracking_color(state2) == TRACKING_COLORS[TrackingDisplayState.MIB]

    # When MIB is disabled, Step 2 is an explicit move to 0 (INTENSITY_DOWN)
    seq.mib_enabled = False
    state2_off, lvl2_off = classify_channel_tracking_state(seq, 2, 1)
    assert state2_off == TrackingDisplayState.INTENSITY_DOWN
    assert lvl2_off == 0


@pytest.mark.gui
def test_sequence_tab_tracking_mode_toggle(app_gui: Application) -> None:
    """Test SequenceTab header toggle buttons for Tracking and MIB."""
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

    # Test MIB toggle button
    seq_tab.set_mib_enabled(True)
    assert app_gui.core.lightshow.main_playback.mib_enabled is True
    assert "MIB: ON" in seq_tab.mib_btn.get_label()

    mib_state = seq_tab.toggle_mib_mode()
    assert mib_state is False
    assert app_gui.core.lightshow.main_playback.mib_enabled is False
    assert "MIB: OFF" in seq_tab.mib_btn.get_label()

    seq_tab.set_mib_enabled(True)


@pytest.mark.gui
def test_sequence_tab_ifcb_columns_and_action(app_gui: Application) -> None:
    """Test Pos, Color, and Beam columns in SequenceTab and step.update_times."""
    app_gui.core.action_registry.execute("sequence.insert_step", 1.0, 1, 1.0, {1: 200})
    app_gui.activate_action("sequences", None)
    process_events()

    assert app_gui.tabs is not None
    seq_tab = app_gui.tabs.tabs.get("sequences")
    assert isinstance(seq_tab, SequenceTab)
    seq_tab.refresh()
    process_events()

    col_titles = [col.get_title() for col in seq_tab.treeview2.get_columns()]
    assert col_titles[8:12] == ["Pos", "Color", "Beam", "Channel Time"]

    app_gui.core.action_registry.execute(
        "step.update_times",
        1.0,
        1,
        time_position=4.0,
        time_color=1.5,
        time_beam=0.0,
    )
    process_events()

    step = app_gui.core.lightshow.main_playback.steps[1]
    assert step.time_position == pytest.approx(4.0)
    assert step.time_color == pytest.approx(1.5)
    assert step.time_beam == pytest.approx(0.0)
    assert seq_tab.liststore2[0][8] == "4"
    assert seq_tab.liststore2[0][9] == "1.5"
    assert seq_tab.liststore2[0][10] == "0"

    # Reset Pos to inherited (None) by passing -1.0
    app_gui.core.action_registry.execute(
        "step.update_times", 1.0, 1, time_position=-1.0
    )
    process_events()
    assert step.time_position is None
    assert seq_tab.liststore2[0][8] == ""


@pytest.mark.gui
def test_live_view_tracking_and_manual_colors(app_gui: Application) -> None:
    """Test LiveView channel widgets tracking and manual Red/Coral colors."""
    main_pb = app_gui.core.lightshow.main_playback
    main_pb.tracking_mode = True
    main_pb.steps.clear()
    main_pb.steps.append(Step(sequence=1))
    main_pb.steps.append(Step(sequence=1, cue=Cue(1, 1.0, {1: 120, 2: 200})))
    main_pb.steps.append(Step(sequence=1, cue=Cue(1, 2.0, {2: 255, 3: 80})))
    main_pb.steps.append(Step(sequence=1, cue=Cue(1, 0, {})))
    main_pb.last = len(main_pb.steps)
    main_pb.position = 2
    main_pb.on_go = False

    assert app_gui.window is not None
    assert app_gui.core.backend is not None
    dmx = app_gui.core.backend.dmx
    dmx.levels["faders"].fill(0)
    app_gui.core.lightshow.independents.dmx.fill(0)
    dmx.levels["sequence"][0] = 120
    dmx.levels["sequence"][1] = 255
    dmx.levels["sequence"][2] = 80
    dmx.levels["user"].fill(-1)

    app_gui.window.update_channels_display(2)
    process_events()

    w1 = app_gui.window.live_view.channels_view.get_channel_widget(1)
    w2 = app_gui.window.live_view.channels_view.get_channel_widget(2)
    assert w1 is not None
    assert w2 is not None
    assert w1.level == 120
    assert w1.color_level == TRACKING_COLORS[TrackingDisplayState.TRACKED_VALUE]
    assert w2.level == 255
    assert w2.color_level == TRACKING_COLORS[TrackingDisplayState.INTENSITY_UP]

    # Set manual level on channel 1 -> Red/Coral
    dmx.levels["user"][0] = 180
    app_gui.window.live_view.update_channel_widget(1, 0)
    process_events()
    assert w1.level == 180
    assert w1.color_level == TRACKING_COLORS[TrackingDisplayState.MANUAL]
    assert w1.color_level == {"red": 0.95, "green": 0.35, "blue": 0.35}
    dmx.levels["user"].fill(-1)


@pytest.mark.gui
def test_track_channels_tab_tracking_and_device_values(app_gui: Application) -> None:
    """Test TrackChannelsTab resolves tracked levels, device_values, and colors."""
    from olc.gtk3.track_channels import (  # pylint: disable=import-outside-toplevel
        TrackChannelsTab,
    )
    from olc.gtk3.widgets.track_channels import (  # pylint: disable=import-outside-toplevel
        TrackChannelsWidget,
    )

    main_pb = app_gui.core.lightshow.main_playback
    main_pb.tracking_mode = True
    main_pb.steps.clear()
    main_pb.steps.append(Step(sequence=1))
    main_pb.steps.append(
        Step(
            sequence=1,
            cue=Cue(1, 1.0, {1: 150}, device_values={2: {"intensity": 0.5}}),
        )
    )
    main_pb.steps.append(
        Step(
            sequence=1,
            cue=Cue(1, 2.0, {}, device_values={2: {"intensity": 1.0}}),
        )
    )
    main_pb.steps.append(Step(sequence=1, cue=Cue(1, 0, {})))
    main_pb.last = len(main_pb.steps)

    # Ensure channels 1 and 2 are patched and selected in LiveView
    app_gui.core.lightshow.patch.patch_1on1()
    assert app_gui.window is not None
    flowbox = app_gui.window.live_view.channels_view.flowbox
    flowbox.unselect_all()
    c1 = flowbox.get_child_at_index(0)
    c2 = flowbox.get_child_at_index(1)
    assert c1 is not None and c2 is not None
    flowbox.select_child(c1)
    flowbox.select_child(c2)

    app_gui.activate_action("track_channels", None)
    process_events()

    assert app_gui.tabs is not None
    tc_tab = app_gui.tabs.tabs.get("track_channels")
    assert isinstance(tc_tab, TrackChannelsTab)
    tc_tab.refresh()
    process_events()

    step1_widget = tc_tab.steps[1]
    step2_widget = tc_tab.steps[2]
    assert isinstance(step1_widget, TrackChannelsWidget)
    assert isinstance(step2_widget, TrackChannelsWidget)

    # Step 1: Ch 1 = 150 (HARD_VALUE), Ch 2 = 128 from device_values 0.5 (HARD_VALUE)
    assert step1_widget.levels == [150, 128]
    assert step1_widget.colors == [
        TRACKING_COLORS[TrackingDisplayState.HARD_VALUE],
        TRACKING_COLORS[TrackingDisplayState.HARD_VALUE],
    ]

    # Step 2: Ch 1 = 150 (TRACKED_VALUE), Ch 2 = 255 (INTENSITY_UP)
    assert step2_widget.levels == [150, 255]
    assert step2_widget.colors == [
        TRACKING_COLORS[TrackingDisplayState.TRACKED_VALUE],
        TRACKING_COLORS[TrackingDisplayState.INTENSITY_UP],
    ]
