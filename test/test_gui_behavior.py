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

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel

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
from olc.group import Group  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.cue import CuesEditionTab  # noqa: E402
from olc.gtk3.curve import CurveButton, CurvesTab  # noqa: E402
from olc.gtk3.group import GroupTab  # noqa: E402
from olc.gtk3.patch_channels import PatchChannelsTab  # noqa: E402
from olc.gtk3.patch_outputs import PatchOutputsTab  # noqa: E402
from olc.gtk3.widgets.group import GroupWidget  # noqa: E402
from olc.gtk3.widgets.patch_channels import PatchChannelWidget  # noqa: E402

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
    gresource_path = "/usr/local/share/olc/olc.gresource"
    if os.path.exists(gresource_path):
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
