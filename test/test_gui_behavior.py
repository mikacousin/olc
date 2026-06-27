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
"""Automated behavioral tests for the GTK3 GUI (Phases 1 & 2)."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import os
import typing
from collections.abc import Generator

import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk  # noqa: E402
from olc.cue import Cue  # noqa: E402
from olc.fader_bank import FaderType  # noqa: E402
from olc.group import Group  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.channel_time import ChanneltimeTab  # noqa: E402
from olc.gtk3.cue import CuesEditionTab  # noqa: E402
from olc.gtk3.curve import CurveButton, CurvesTab  # noqa: E402
from olc.gtk3.fader import FaderEdit, FaderTab  # noqa: E402
from olc.gtk3.group import GroupTab  # noqa: E402
from olc.gtk3.patch_channels import PatchChannelsTab  # noqa: E402
from olc.gtk3.patch_outputs import PatchOutputsTab  # noqa: E402
from olc.gtk3.sequence import SequenceTab  # noqa: E402
from olc.gtk3.widgets.group import GroupWidget  # noqa: E402
from olc.gtk3.widgets.patch_channels import PatchChannelWidget  # noqa: E402

if typing.TYPE_CHECKING:
    from olc.gtk3.widgets.channel import ChannelWidget

pytestmark = pytest.mark.gui


# Helper to process the GTK event loop and flush idle callbacks
def process_events() -> None:
    """Process GTK events to flush the main loop."""
    for _ in range(15):
        while Gtk.events_pending():
            Gtk.main_iteration()


@pytest.fixture(scope="module")
def app_gui_instance() -> Generator[Application, None, None]:
    """Fixture to launch the complete GTK Application instance once for the module."""
    # Register resources
    gresource_path = None
    candidates = [
        os.path.join(
            os.path.dirname(__file__), "..", "builddir", "data", "olc.gresource"
        ),
        "/usr/local/share/olc/olc.gresource",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            gresource_path = candidate
            break

    if gresource_path is not None:
        resource = Gio.resource_load(gresource_path)
        Gio.Resource._register(resource)  # type: ignore

    # Disable DBus unique registration
    original_init = Gtk.Application.__init__

    def patched_init(
        self: Gtk.Application,
        *args: typing.Any,  # noqa: ANN401
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> None:
        kwargs["application_id"] = None
        kwargs["flags"] = Gio.ApplicationFlags.NON_UNIQUE
        original_init(self, *args, **kwargs)

    Gtk.Application.__init__ = patched_init  # type: ignore

    app = Application("test-version")
    app.register(None)

    # Initialize Engine and Backend (normally done in do_command_line)
    from olc.backends import DMXBackend
    from olc.core.engine import CoreEngine
    from olc.core.universe_config import Protocol, UniverseMap
    from olc.define import UNIVERSES

    universe_map = UniverseMap(max(UNIVERSES) + 1)
    for u in range(1, 5):
        universe_map.enable_protocol(u, Protocol.ARTNET)
        universe_map.enable_protocol(u, Protocol.SACN)

    app.engine = CoreEngine(universe_map, monitor_port=5555, no_listen=True)
    app.core.engine = app.engine

    app.backend = DMXBackend(app.core.lightshow)
    app.core.backend = app.backend

    app.engine.start()

    def on_patch_empty_cb() -> None:
        if app.backend:
            app.backend.dmx.all_outputs_at_zero()

    def on_unpatch_cb(index: int, output: int) -> None:
        if app.backend:
            app.backend.dmx.frame[index][output] = 0

    app.core.lightshow.patch.on_patch_empty_cb = on_patch_empty_cb
    app.core.lightshow.patch.on_unpatch_cb = on_unpatch_cb
    app.backend.dmx.add_notification_callback(app.on_backend_notification)

    # Activate
    app.activate()
    process_events()

    yield app

    # Cleanup application window and stop engines
    if app.engine:
        app.engine.stop()
    if app.backend:
        app.backend.stop()
    if app.window:
        app.window.destroy()
    app.quit()
    process_events()


@pytest.fixture(scope="function")
def app_gui(app_gui_instance: Application) -> Generator[Application, None, None]:
    """Fixture to reset state and open/close tabs for each test function."""
    app = app_gui_instance

    # 1. Clear any logical data
    app.core.lightshow.groups.clear()
    app.core.lightshow.cues.clear()
    app.core.lightshow.patch.patch_empty()

    # 2. Close any open tabs
    if app.tabs:
        for tab_name in list(app.tabs.tabs.keys()):
            app.tabs.close(tab_name)

    process_events()

    yield app

    process_events()


# ==============================================================================
# Phase 1: Patch DMX & Curves Tests
# ==============================================================================


def test_patch_outputs_tab_behavior(app_gui: Application) -> None:
    """Test PatchOutputsTab GUI interactions and undo/redo."""
    # 1. Open the patch outputs tab
    app_gui.activate_action("patch_outputs", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("patch_outputs")
    assert isinstance(patch_tab, PatchOutputsTab)
    assert patch_tab.flowbox is not None

    # 2. Test initial state / select output 10 (index 9)
    children = patch_tab.flowbox.get_children()
    assert len(children) == 2048, (
        "Flowbox should contain 2048 outputs for all Universes."
    )

    # 3. Trigger "Patch 1:1" button
    app_gui.core.action_registry.execute("patch.clear")
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) == 0

    patch_tab.on_button_clicked(Gtk.Button(label="Patch 1:1"))
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) > 0, (
        "1:1 Patch should populate outputs."
    )

    # 4. Trigger "Unpatch all" button
    patch_tab.on_button_clicked(Gtk.Button(label="Unpatch all"))
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) == 0, (
        "Unpatch all should clear outputs."
    )

    # 5. Undo unpatch all
    app_gui.activate_action("undo", None)
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) > 0, (
        "Undo should restore 1:1 patch."
    )


def test_patch_channels_tab_behavior(app_gui: Application) -> None:
    """Test PatchChannelsTab selection and data updating."""
    # 1. Open the patch channels tab
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_chan_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_chan_tab, PatchChannelsTab)
    assert patch_chan_tab.flowbox is not None

    # 2. Select channel 5 (index 4)
    children = patch_chan_tab.flowbox.get_children()
    patch_chan_tab.flowbox.unselect_all()
    assert len(children) > 4
    child_widget = children[4]
    assert isinstance(child_widget, Gtk.FlowBoxChild)
    patch_chan_tab.flowbox.select_child(child_widget)
    process_events()

    selected = patch_chan_tab.flowbox.get_selected_children()
    assert len(selected) == 1
    widget = selected[0].get_child()
    assert isinstance(widget, PatchChannelWidget)
    assert widget.channel == 5, "Widget channel number should be 5."

    # 3. Modify patch via core and check reflection in patch data
    app_gui.core.action_registry.execute("patch.clear")
    process_events()
    app_gui.core.action_registry.execute("patch.add_output", 5, 10, 1)
    process_events()

    assert app_gui.core.lightshow.patch.channels[5] == [[10, 1]]


def test_curves_tab_behavior(app_gui: Application) -> None:
    """Test CurvesTab creation, modification, deletion, and undo."""
    # 1. Open curves tab
    app_gui.activate_action("curves", None)
    process_events()

    assert app_gui.tabs is not None
    curves_tab = app_gui.tabs.tabs.get("curves")
    assert isinstance(curves_tab, CurvesTab)
    assert curves_tab.flowbox is not None

    # 2. Create new Limit curve
    initial_curve_count = len(app_gui.core.lightshow.curves.curves)
    curves_tab.on_new_curve(curves_tab.buttons["limit"])
    process_events()

    assert len(app_gui.core.lightshow.curves.curves) == initial_curve_count + 1, (
        "A new curve should be created."
    )

    # Get the created curve number (usually the last index)
    new_curve_number = list(app_gui.core.lightshow.curves.curves.keys())[-1]

    # 3. Verify it is visible in the flowbox
    children = curves_tab.flowbox.get_children()
    flowbox_children = [c for c in children if isinstance(c, Gtk.FlowBoxChild)]

    def get_curve_button(c: Gtk.FlowBoxChild) -> CurveButton:
        btn = c.get_child()
        assert isinstance(btn, CurveButton)
        return btn

    assert any(
        get_curve_button(c).curve_nb == new_curve_number for c in flowbox_children
    ), "Curve widget should be rendered."

    # 4. Select the new curve
    target_child = None
    for child in flowbox_children:
        if get_curve_button(child).curve_nb == new_curve_number:
            target_child = child
            break
    assert target_child is not None
    curves_tab.flowbox.select_child(target_child)
    process_events()

    # 5. Delete curve
    assert curves_tab.curve_edition is not None
    curves_tab.curve_edition.on_del_curve(Gtk.Button())
    process_events()
    assert new_curve_number not in app_gui.core.lightshow.curves.curves, (
        "Curve should be deleted."
    )

    # 6. Undo deletion
    app_gui.activate_action("undo", None)
    process_events()
    assert new_curve_number in app_gui.core.lightshow.curves.curves, (
        "Undo should restore the deleted curve."
    )


# ==============================================================================
# Phase 2: Cues & Groups Tests
# ==============================================================================


def test_group_tab_behavior(app_gui: Application) -> None:
    """Test GroupTab selection, rename, and undo/redo."""
    # 1. Populate groups
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, {}, "Group A"))
    app_gui.core.lightshow.groups.add(Group(2.0, {}, "Group B"))

    # 2. Open groups tab
    app_gui.activate_action("groups", None)
    process_events()

    assert app_gui.tabs is not None
    group_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(group_tab, GroupTab)
    assert group_tab.flowbox is not None

    children = group_tab.flowbox.get_children()
    assert len(children) == 2, "Flowbox should render 2 groups."

    # 3. Select Group A (index 0)
    child0 = children[0]
    assert isinstance(child0, Gtk.FlowBoxChild)
    group_tab.flowbox.select_child(child0)
    process_events()
    assert app_gui.core.selected_group == 1.0
    assert group_tab.selected_group_number == 1.0

    # 4. Select Group B (index 1)
    child1 = children[1]
    assert isinstance(child1, Gtk.FlowBoxChild)
    group_tab.flowbox.select_child(child1)
    process_events()
    assert app_gui.core.selected_group == 2.0
    assert group_tab.selected_group_number == 2.0

    # 5. Undo group selection
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.selected_group == 1.0
    assert group_tab.selected_group_number == 1.0
    selected_children = group_tab.flowbox.get_selected_children()
    assert len(selected_children) == 1
    sel_child = selected_children[0]
    assert isinstance(sel_child, Gtk.FlowBoxChild)
    group_widget = sel_child.get_child()
    assert isinstance(group_widget, GroupWidget)
    assert group_widget.number == 1.0

    # 6. Rename Group A via the callback
    group_widget_to_rename = child0.get_child()
    assert isinstance(group_widget_to_rename, GroupWidget)
    mock_entry = Gtk.Entry()
    mock_entry.set_text("Group A Renamed")
    group_widget_to_rename.on_edit(mock_entry)
    process_events()

    assert app_gui.core.lightshow.groups[0].text == "Group A Renamed"

    # Query fresh widget since refresh() destroys and recreates the flowbox
    new_children = group_tab.flowbox.get_children()
    new_child = new_children[0]
    assert isinstance(new_child, Gtk.FlowBoxChild)
    new_widget = new_child.get_child()
    assert isinstance(new_widget, GroupWidget)
    assert new_widget.name == "Group A Renamed"

    # Undo rename
    # If duplicate selection event was pushed during UI refresh, undo it first
    if (
        app_gui.core.history._undo_stack
        and app_gui.core.history._undo_stack[-1].name == "group.select"
    ):
        app_gui.activate_action("undo", None)
        process_events()

    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.groups[0].text == "Group A"

    new_children = group_tab.flowbox.get_children()
    new_child0 = new_children[0]
    assert isinstance(new_child0, Gtk.FlowBoxChild)
    new_widget0 = new_child0.get_child()
    assert isinstance(new_widget0, GroupWidget)
    assert new_widget0.name == "Group A"


def test_cues_edition_tab_behavior(app_gui: Application) -> None:
    """Test CuesEditionTab insertion, rename, delete, and undo/redo."""
    # 1. Clear cues and add one
    app_gui.core.lightshow.cues.clear()
    app_gui.core.lightshow.cues.append(Cue(0, 1.0, {}, "Cue 1"))

    # 2. Open memories/cues tab
    app_gui.activate_action("memories", None)
    process_events()

    assert app_gui.tabs is not None
    cues_tab = app_gui.tabs.tabs.get("memories")
    assert isinstance(cues_tab, CuesEditionTab)
    assert cues_tab.treeview is not None

    # Verify initial treeview row
    model = cues_tab.treeview.get_model()
    assert model is not None
    assert len(model) == 1, "TreeView should have 1 row initially."

    # 3. Insert a new cue (cue 2.0)
    cues_tab._insert_cue_on_next_free_number()
    process_events()
    assert len(app_gui.core.lightshow.cues) == 2, "There should be 2 cues now."
    assert len(model) == 2, "TreeView should render 2 rows."

    # 4. Rename the first cue
    cues_tab._text_edited(Gtk.CellRendererText(), "0", "Cue 1 Renamed")
    process_events()
    assert app_gui.core.lightshow.cues[0].text == "Cue 1 Renamed"

    # Undo rename
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.cues[0].text == "Cue 1"

    # 5. Delete selected cue (cue 2.0)
    # Execute delete action directly (to avoid GUI confirmation dialog popup blocker)
    # Note: We do not set the treeview cursor here to avoid queuing asynchronous
    # cursor-changed events that inject cue.select into the undo history.
    cue_to_del = app_gui.core.lightshow.cues[1]
    app_gui.core.action_registry.execute(
        "cue.delete", cue_to_del.number, cue_to_del.sequence
    )
    process_events()

    assert len(app_gui.core.lightshow.cues) == 1, "Cue should be deleted."
    assert len(model) == 1, "TreeView should render 1 row."

    # 6. Undo delete
    app_gui.activate_action("undo", None)
    process_events()
    assert len(app_gui.core.lightshow.cues) == 2, "Undo should restore the deleted cue."
    assert len(model) == 2, "TreeView should render 2 rows."


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


# ==============================================================================
# Phase 3: Channel Selection Behaviour Tests
# ==============================================================================


def test_live_view_channel_selection(app_gui: Application) -> None:
    """Test channel selection/deselection via keyboard in the live view.

    Covers:
    - C key selects the channel entered in the commandline
    - 0 C deselects all channels
    - C alone (empty commandline) deselects all channels
    - Undo/redo of both operations
    """
    assert app_gui.window is not None
    channels_view = app_gui.window.live_view.channels_view
    commandline = app_gui.core.commandline

    # Reset selection state
    app_gui.core.live_selection.selected_channels = []
    app_gui.core.live_selection.last_selected_channel = None

    # 1. Select channel 3 via "3 C"
    commandline.set_string("3")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == [3]
    assert app_gui.core.last_selected_channel == 3

    # 2. Add channel 7 via "7 +"
    commandline.set_string("7")
    channels_view.select_plus()
    process_events()
    assert set(app_gui.core.selected_channels) == {3, 7}

    # 3. Deselect all via "0 C"
    commandline.set_string("0")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == []
    assert app_gui.core.last_selected_channel is None

    # 4. Undo: should restore {3, 7}
    app_gui.activate_action("undo", None)
    process_events()
    assert set(app_gui.core.selected_channels) == {3, 7}

    # 5. Redo: should clear again
    app_gui.activate_action("redo", None)
    process_events()
    assert app_gui.core.selected_channels == []

    # 6. Re-select channel 5, then deselect via bare C (empty commandline)
    commandline.set_string("5")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == [5]

    commandline.set_string("")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == []
    assert app_gui.core.last_selected_channel is None


def test_group_tab_channel_selection(app_gui: Application) -> None:
    """Test channel selection/deselection via keyboard in the Groups tab channels view.

    Covers:
    - C key selects the channel entered in the commandline (local SelectionManager)
    - 0 C deselects all channels in the group channels view
    - C alone (empty commandline) deselects all channels
    - Undo/redo via the shared history
    - GUI flowbox highlights match the logical selection state
    """
    # 1. Set up a group and open the tab
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, {1: 200, 2: 150, 3: 100}, "G1"))

    app_gui.activate_action("groups", None)
    process_events()

    assert app_gui.tabs is not None
    group_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(group_tab, GroupTab)

    channels_view = group_tab.channels_view
    commandline = app_gui.core.commandline
    selection_manager = channels_view.selection_manager

    # Select the group so the channels view is populated
    children = group_tab.flowbox.get_children()
    assert len(children) >= 1
    group_tab.flowbox.select_child(typing.cast(Gtk.FlowBoxChild, children[0]))
    process_events()

    # 2. Select channel 1 via "1 C"
    commandline.set_string("1")
    channels_view.select_channel()
    process_events()
    assert selection_manager.selected_channels == [1]
    assert selection_manager.last_selected_channel == 1

    # Verify flowbox highlight
    selected_fb = channels_view.flowbox.get_selected_children()
    assert any(c.get_index() == 0 for c in selected_fb), (
        "Channel 1 flowbox child should be highlighted."
    )

    # 3. Add channel 2 via "2 +"
    commandline.set_string("2")
    channels_view.select_plus()
    process_events()
    assert set(selection_manager.selected_channels) == {1, 2}

    # 4. Deselect all via "0 C"
    commandline.set_string("0")
    channels_view.select_channel()
    process_events()
    assert selection_manager.selected_channels == []
    assert selection_manager.last_selected_channel is None

    # Flowbox should show no selection
    assert channels_view.flowbox.get_selected_children() == []

    # 5. Undo: should restore {1, 2}
    app_gui.core.history.undo()
    process_events()
    assert set(selection_manager.selected_channels) == {1, 2}

    # 6. Redo: should clear again
    app_gui.core.history.redo()
    process_events()
    assert selection_manager.selected_channels == []

    # 7. Re-select channel 3, then deselect via bare C (empty commandline)
    commandline.set_string("3")
    channels_view.select_channel()
    process_events()
    assert selection_manager.selected_channels == [3]

    commandline.set_string("")
    channels_view.select_channel()
    process_events()
    assert selection_manager.selected_channels == []
    assert selection_manager.last_selected_channel is None


def test_fader_tab_behavior(app_gui: Application) -> None:
    """Test FaderTab configuration and undo/redo."""
    # 1. Open faders tab
    app_gui.activate_action("faders", None)
    process_events()

    assert app_gui.tabs is not None
    fader_tab = app_gui.tabs.tabs.get("faders")
    assert isinstance(fader_tab, FaderTab)

    # 2. Get first fader (page 1, index 1)
    fader_edit = None
    for child in fader_tab.stack.get_children():
        if not isinstance(child, Gtk.Container):
            continue
        for hbox in child.get_children():
            if not isinstance(hbox, Gtk.Container):
                continue
            for widget in hbox.get_children():
                if (
                    isinstance(widget, FaderEdit)
                    and widget.page == 1
                    and widget.index == 1
                ):
                    fader_edit = widget
                    break
            if fader_edit:
                break
        if fader_edit:
            break

    assert fader_edit is not None, "FaderEdit for page 1, index 1 not found"
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # 3. Configure fader 1 as GROUP fader
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, {}, "Group A"))
    process_events()

    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )

    # Setting type to GROUP
    fader_edit._on_type_changed(Gtk.ModelButton(), FaderType.GROUP)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )

    # Setting contents to Group 1.0
    mock_button = Gtk.ModelButton()
    mock_button.set_label("1.0 : Group A")
    fader_edit._on_contents_changed(mock_button, FaderType.GROUP, 1.0)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is not None
    )

    # Simulate raising the fader to 50%
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.5

    # 4. Change contents to Group B (2.0)
    app_gui.core.lightshow.groups.add(Group(2.0, {}, "Group B"))
    process_events()
    mock_button2 = Gtk.ModelButton()
    mock_button2.set_label("2.0 : Group B")
    fader_edit._on_contents_changed(mock_button2, FaderType.GROUP, 2.0)
    process_events()

    # The fader level is reset to 0 upon content change
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    contents_b = getattr(
        app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None
    )
    assert contents_b is not None
    assert contents_b.index == 2.0

    # Raise the fader again to 50%
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)

    # 5. First Ctrl+Z (reverts contents to Group A)
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    # The level must be reset to 0 because content changed back to Group A (1.0)
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    contents_a = getattr(
        app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None
    )
    assert contents_a is not None
    assert contents_a.index == 1.0

    # Raise the fader again to 50%
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)

    # 6. Second Ctrl+Z (reverts contents to None)
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )

    # Raise the fader again to 50% (should be inert on a type with None contents,
    # but let's test the type change level reset)
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)

    # 7. Third Ctrl+Z (reverts type to NONE)
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )


def test_fader_set_level_action(app_gui: Application) -> None:
    """Test that fader.set_level action works and correctly updates Virtual Console."""
    # 1. Setup Virtual Console GUI
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # 2. Configure fader 1 as GROUP fader with Group A (channels {1: 255})
    app_gui.core.lightshow.groups.clear()
    group_a = Group(1.0, {1: 255}, "Group A")
    app_gui.core.lightshow.groups.add(group_a)
    process_events()

    # Setup fader 1
    app_gui.core.lightshow.fader_bank.set_fader(1, 1, FaderType.GROUP, 1.0)
    process_events()

    # Verify fader is GROUP and level is 0
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0

    # Verify GUI fader widget value is 0
    gui_fader_widget = app_gui.virtual_console.faders[0]
    assert gui_fader_widget.get_value() == 0.0

    # 3. Execute fader.set_level action via registry
    app_gui.core.action_registry.execute("fader.set_level", 1, 1, 0.8)  # 80%
    process_events()

    # 4. Asserts:
    # A. Model level updated to 0.8
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.8
    # B. DMX output reflects change (channel 1 is at 80% * 255 = 204)
    assert app_gui.core.lightshow.fader_bank.faders[1][1].dmx[0] == 204
    # C. GUI fader widget value updated to 0.8 * 255 = 204
    assert gui_fader_widget.get_value() == 204.0

    # 5. Move GUI fader slider directly to 50%
    gui_fader_widget.set_value(127.5)  # 50%
    # Trigger value-changed callback
    app_gui.virtual_console.fader_moved(gui_fader_widget)
    process_events()

    # Model and DMX must reflect 50%
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.5
    assert (
        app_gui.core.lightshow.fader_bank.faders[1][1].dmx[0] == 128
    )  # 0.5 * 255 rounded

    # Close Virtual Console window
    app_gui.virtual_console.close()
    process_events()


def test_virtual_console_present_if_already_open(app_gui: Application) -> None:
    """Test that virtual_console action calls present() if already open."""
    # 1. Open the virtual console
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # 2. Patch present() method
    from unittest.mock import patch

    with patch.object(app_gui.virtual_console, "present") as mock_present:
        # 3. Activate action again
        app_gui.activate_action("virtual_console", None)
        process_events()

        # 4. Check that present was called
        mock_present.assert_called_once()

    # Clean up
    app_gui.virtual_console.close()
    process_events()


def test_fader_set_page_action(app_gui: Application) -> None:
    """Test that fader.set_page action works and correctly updates Virtual Console."""
    # 1. Setup Virtual Console GUI
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # Verify initial page is 1
    assert app_gui.core.lightshow.fader_bank.active_page == 1
    assert app_gui.virtual_console.page_number.get_label() == "1"

    # 2. Execute fader.set_page action to switch to page 2
    app_gui.core.action_registry.execute("fader.set_page", 2)
    process_events()

    # Verify page is 2 in model and GUI
    assert app_gui.core.lightshow.fader_bank.active_page == 2
    assert app_gui.virtual_console.page_number.get_label() == "2"

    # 3. Click Page+ button on Virtual Console (should transition to page 3)
    app_gui.virtual_console._on_fader_page(app_gui.virtual_console.fader_page_plus)
    process_events()

    assert app_gui.core.lightshow.fader_bank.active_page == 3
    assert app_gui.virtual_console.page_number.get_label() == "3"

    # 4. Click Page- button on Virtual Console (should transition back to page 2)
    app_gui.virtual_console._on_fader_page(app_gui.virtual_console.fader_page_minus)
    process_events()

    assert app_gui.core.lightshow.fader_bank.active_page == 2
    assert app_gui.virtual_console.page_number.get_label() == "2"

    # Clean up
    app_gui.virtual_console.close()
    process_events()
