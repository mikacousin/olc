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
"""GUI behavior tests for the Groups tab."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import typing

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.group import Group  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.group import GroupTab  # noqa: E402
from olc.gtk3.widgets.group import GroupWidget  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


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
