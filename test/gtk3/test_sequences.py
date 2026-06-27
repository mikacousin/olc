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
"""GUI behavior tests for the Sequences and Channel Time tabs."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import typing

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.channel_time import ChanneltimeTab  # noqa: E402
from olc.gtk3.sequence import SequenceTab  # noqa: E402

if typing.TYPE_CHECKING:
    from olc.gtk3.widgets.channel import ChannelWidget

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_sequence_and_channel_time_tab_behavior(app_gui: Application) -> None:
    """Test SequenceTab and ChanneltimeTab GUI interactions, including editing and
    undo/redo.
    """
    # 1. Clear sequences/chasers and cues
    app_gui.core.lightshow.chasers.clear()
    app_gui.core.lightshow.cues.clear()

    # 2. Open the Sequences Tab
    app_gui.activate_action("sequences", None)
    process_events()

    assert app_gui.tabs is not None
    seq_tab = app_gui.tabs.tabs.get("sequences")
    assert isinstance(seq_tab, SequenceTab)
    assert seq_tab.treeview1 is not None
    assert seq_tab.treeview2 is not None

    # 3. Create a new Sequence (Chaser 2.0)
    seq_tab._keypress_n()
    process_events()

    assert len(app_gui.core.lightshow.chasers) == 1
    assert app_gui.core.lightshow.chasers[0].index == 2.0

    # 4. Programmatically select row index 1 (Chaser 2.0)
    model1 = seq_tab.treeview1.get_model()
    assert model1 is not None
    assert len(model1) == 2  # Main Playback (index 1) and Chaser 2.0

    path1 = Gtk.TreePath.new_from_indices([1])
    seq_tab.treeview1.set_cursor(path1, None, False)
    seq_tab.on_sequence_changed()
    process_events()

    chaser = seq_tab.get_selected_sequence()
    assert chaser is not None
    assert chaser.index == 2.0

    # Set channel 5 level to create step with channels
    widget_ch = seq_tab.channels_view.get_channel_widget(5)
    assert widget_ch is not None
    widget_ch.level = 255
    widget_ch.next_level = 255

    # 5. Insert a step via _keypress_r (which inserts step 1 with cue 1.0)
    seq_tab._keypress_r()
    process_events()

    assert len(chaser.steps) == 2
    cue = chaser.steps[1].cue
    assert cue is not None
    assert cue.number == 1.0
    assert cue.channels == {5: 255}

    model2 = seq_tab.treeview2.get_model()
    assert model2 is not None
    assert len(model2) == 1
    assert model2[0][1] == "1.0"

    # Test Undo step insertion
    app_gui.activate_action("undo", None)
    process_events()
    assert len(chaser.steps) == 1
    assert len(model2) == 0

    # Test Redo step insertion
    app_gui.activate_action("redo", None)
    process_events()
    assert len(chaser.steps) == 2
    assert len(model2) == 1

    # 6. Open Channel Time Tab for step 1
    app_gui.channeltime(chaser, 1)
    process_events()

    ct_tab = app_gui.tabs.tabs.get("channel_time")
    assert isinstance(ct_tab, ChanneltimeTab)
    assert ct_tab.treeview is not None

    # Select channel 5 in channels view
    child_channel = ct_tab.channels_view.flowbox.get_child_at_index(4)  # Channel 5
    assert child_channel is not None
    ct_tab.channels_view.flowbox.select_child(child_channel)
    ct_tab.channels_view.flowbox.invalidate_filter()
    process_events()

    selected = ct_tab.channels_view.flowbox.get_selected_children()
    print("SELECTED CHANNELS WIDGETS:", selected)
    for flowboxchild in selected:
        child = flowboxchild.get_child()
        print("child:", child)
        if child is not None:
            channelwidget = typing.cast("ChannelWidget", child)
            print(
                "channelwidget.channel type:",
                type(channelwidget.channel),
                "val:",
                channelwidget.channel,
            )

    print("CT_TAB POSITION:", ct_tab.position, "TYPE:", type(ct_tab.position))
    print("CT_TAB SEQUENCE:", ct_tab.sequence)
    print("CT_TAB STEP:", ct_tab.step)
    print("CHASER STEPS[1]:", chaser.steps[1])
    print("CHASER STEPS:", chaser.steps)

    # Insert channel time
    ct_tab._keypress_insert()
    process_events()

    step_obj = chaser.steps[1]
    print("STEP_OBJ CHANNEL_TIME:", step_obj.channel_time)
    print("CT_TAB.STEP CHANNEL_TIME:", ct_tab.step.channel_time)
    assert 5 in step_obj.channel_time
    assert step_obj.channel_time[5].delay == 0.0
    assert step_obj.channel_time[5].time == 0.0

    # Edit delay to 1.5
    # Select the row in treeview first
    path_row = Gtk.TreePath.new_from_indices([0])
    ct_tab.treeview.set_cursor(path_row, None, False)
    process_events()

    ct_tab.delay_edited(typing.cast(Gtk.Widget, None), "0", "1.5")
    process_events()
    assert step_obj.channel_time[5].delay == 1.5
    assert ct_tab.liststore[0][1] == "1.5"

    # Test Undo delay edit
    app_gui.activate_action("undo", None)
    process_events()
    assert step_obj.channel_time[5].delay == 0.0
    assert ct_tab.liststore[0][1] == ""

    # Test Redo delay edit
    app_gui.activate_action("redo", None)
    process_events()
    assert step_obj.channel_time[5].delay == 1.5
    assert ct_tab.liststore[0][1] == "1.5"

    # Edit time to 2.0
    ct_tab.time_edited(typing.cast(Gtk.Widget, None), "0", "2.0")
    process_events()
    assert step_obj.channel_time[5].time == 2.0
    assert ct_tab.liststore[0][2] == "2"

    # Test Undo time edit
    app_gui.activate_action("undo", None)
    process_events()
    assert step_obj.channel_time[5].time == 0.0
    assert ct_tab.liststore[0][2] == ""
