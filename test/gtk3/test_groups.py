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

import types
import typing

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.group import GroupTab  # noqa: E402
from olc.gtk3.widgets.channels_table_view import COL_INTENSITY  # noqa: E402
from olc.gtk3.widgets.group import GroupWidget  # noqa: E402
from olc.show.group import Group  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_group_tab_behavior(app_gui: Application) -> None:
    """Test GroupTab navigation (non-undoable), in-place rename, and Undo/Redo."""
    # 1. Populate groups
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, [], "Group A"))
    app_gui.core.lightshow.groups.add(Group(2.0, [], "Group B"))

    # 2. Open groups tab
    app_gui.activate_action("groups", None)
    process_events()

    assert app_gui.tabs is not None
    group_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(group_tab, GroupTab)
    assert group_tab.flowbox is not None

    children = group_tab.flowbox.get_children()
    assert len(children) == 2, "Flowbox should render 2 groups."

    undo_len_before_nav = len(app_gui.core.history._undo_stack)

    # 3. Select Group A (index 0) -> must NOT push to Undo history
    child0 = children[0]
    assert isinstance(child0, Gtk.FlowBoxChild)
    group_tab.flowbox.select_child(child0)
    process_events()
    assert app_gui.core.selected_group == 1.0
    assert group_tab.selected_group_number == 1.0
    assert len(app_gui.core.history._undo_stack) == undo_len_before_nav

    # 4. Select Group B (index 1) -> must NOT push to Undo history
    child1 = children[1]
    assert isinstance(child1, Gtk.FlowBoxChild)
    group_tab.flowbox.select_child(child1)
    process_events()
    assert app_gui.core.selected_group == 2.0
    assert group_tab.selected_group_number == 2.0
    assert len(app_gui.core.history._undo_stack) == undo_len_before_nav

    # 5. Rename Group A via inline entry and verify in-place tile update (no rebuild)
    group_widget_to_rename = child0.get_child()
    assert isinstance(group_widget_to_rename, GroupWidget)
    mock_entry = Gtk.Entry()
    mock_entry.set_text("Group A Renamed")
    group_widget_to_rename.on_edit(mock_entry)
    process_events()

    assert app_gui.core.lightshow.groups[0].text == "Group A Renamed"
    same_children = group_tab.flowbox.get_children()
    first_child = typing.cast(Gtk.FlowBoxChild, same_children[0])
    assert first_child.get_child() is group_widget_to_rename
    assert group_widget_to_rename.name == "Group A Renamed"

    # 6. Single Undo restores Group A label cleanly without group.select clutter
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.groups[0].text == "Group A"
    assert group_widget_to_rename.name == "Group A"


def test_group_tab_channel_selection(app_gui: Application) -> None:
    """Test channel selection, membership order display (#1/#2), and Table view."""
    # 1. Set up a group and open the tab
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, [1, 2, 3], "G1"))

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

    # Ensure pure membership mode: no fake level=1.0 intensity on channels
    w1 = channels_view.get_channel_widget(1)
    w2 = channels_view.get_channel_widget(2)
    w3 = channels_view.get_channel_widget(3)
    assert w1 is not None and w2 is not None and w3 is not None
    assert w1.membership_mode is True
    assert w1.level == 0.0
    assert w1.membership_order == 1
    assert w2.level == 0.0
    assert w2.membership_order == 2
    assert w3.level == 0.0
    assert w3.membership_order == 3

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

    # 3. Add channel 3 via "3 +" (preserving selection order [1, 3])
    commandline.set_string("3")
    channels_view.select_plus()
    process_events()
    assert selection_manager.selected_channels == [1, 3]

    # 4. Deselect all via "0 C"
    commandline.set_string("0")
    channels_view.select_channel()
    process_events()
    assert selection_manager.selected_channels == []
    assert selection_manager.last_selected_channel is None
    assert channels_view.flowbox.get_selected_children() == []

    # 5. Undo: should restore [1, 3]
    app_gui.core.history.undo()
    process_events()
    assert selection_manager.selected_channels == [1, 3]

    # 6. Redo: should clear again
    app_gui.core.history.redo()
    process_events()
    assert selection_manager.selected_channels == []

    # 7. Select channels [1, 3] and update group via toolbar action
    commandline.set_string("1")
    channels_view.select_channel()
    commandline.set_string("3")
    channels_view.select_plus()
    process_events()
    group_tab.update_selected_channels()
    process_events()
    assert app_gui.core.lightshow.groups[0].channels == [1, 3]
    assert w1.membership_order == 1 and w1.level == 0.0
    assert w2.membership_order is None and w2.level == 0.0
    assert w3.membership_order == 2 and w3.level == 0.0

    # 8. Reverse group order -> ch 3 becomes #1, ch 1 becomes #2
    group_tab.reverse_selected_order()
    process_events()
    assert app_gui.core.lightshow.groups[0].channels == [3, 1]
    assert w3.membership_order == 1
    assert w1.membership_order == 2

    # 9. Table view shows "Order" column with #1 / #2 (never "F" or "255")
    channels_view.set_display_format("Table")
    process_events()
    titles = channels_view.table_view.get_column_titles()
    assert "Order" in titles
    assert "Int" not in titles
    iter_3 = channels_view.table_view._channel_iters[3]
    iter_1 = channels_view.table_view._channel_iters[1]
    iter_2 = channels_view.table_view._channel_iters[2]
    assert channels_view.table_view.store[iter_3][COL_INTENSITY] == "#1"
    assert channels_view.table_view.store[iter_1][COL_INTENSITY] == "#2"
    assert channels_view.table_view.store[iter_2][COL_INTENSITY] == ""


def test_group_tab_toolbar_direct_select_and_order_tools(
    app_gui: Application,
) -> None:
    """Test Direct Select, double-click, Record/Update/Reverse/Sort/Clear/Delete."""
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, [5, 2, 8], "Spot Ring"))
    app_gui.core.selected_channels = []

    app_gui.activate_action("groups", None)
    process_events()
    assert app_gui.tabs is not None
    group_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(group_tab, GroupTab)

    children = group_tab.flowbox.get_children()
    assert len(children) == 1
    tile = typing.cast(Gtk.FlowBoxChild, children[0]).get_child()
    assert isinstance(tile, GroupWidget)

    # 1. Direct Select OFF: single click inspects tile without touching Live selection
    assert group_tab.direct_select_toggle.get_active() is False
    tile.on_click(
        tile,
        typing.cast(Gdk.Event, types.SimpleNamespace(type=Gdk.EventType.BUTTON_PRESS)),
    )
    process_events()
    assert app_gui.core.selected_channels == []

    # Double-click when Direct Select is OFF recalls ordered channels into Live
    tile.on_click(
        tile,
        typing.cast(Gdk.Event, types.SimpleNamespace(type=Gdk.EventType(5))),
    )
    process_events()
    assert app_gui.core.selected_channels == [5, 2, 8]

    # 2. Direct Select ON: single click immediately recalls ordered channels into Live
    app_gui.core.selected_channels = []
    group_tab.direct_select_toggle.set_active(True)
    tile.on_click(
        tile,
        typing.cast(Gdk.Event, types.SimpleNamespace(type=Gdk.EventType.BUTTON_PRESS)),
    )
    process_events()
    assert app_gui.core.selected_channels == [5, 2, 8]
    group_tab.direct_select_toggle.set_active(False)

    # 3. Ctrl+A (select_all) in GroupChannelsView selects members in exact group order
    group_tab.channels_view.select_all()
    process_events()
    assert group_tab.channels_view.get_selected_channels() == [5, 2, 8]

    # 4. Sort -> Reverse -> Clear (+ Undo)
    g1 = app_gui.core.lightshow.groups.get(1.0)
    assert g1 is not None
    group_tab.btn_sort.clicked()
    process_events()
    assert g1.channels == [2, 5, 8]

    group_tab.btn_reverse.clicked()
    process_events()
    assert g1.channels == [8, 5, 2]

    group_tab.btn_clear.clicked()
    process_events()
    assert g1.channels == []

    app_gui.core.history.undo()
    process_events()
    assert g1.channels == [8, 5, 2]

    # 5. Record Group 2.5 from Live selection via Record button + CommandLine
    app_gui.core.selected_channels = [10, 6, 4]
    group_tab.channels_view.selection_manager.selected_channels = []
    app_gui.core.commandline.set_string("2.5")
    group_tab.btn_record.clicked()
    process_events()
    grp25 = app_gui.core.lightshow.groups.get(2.5)
    assert grp25 is not None
    assert grp25.channels == [10, 6, 4]
    assert app_gui.core.commandline.get_string() == ""
    assert group_tab.selected_group_number == 2.5

    # 6. Select Live button recalls Group 2.5's ordered channels
    app_gui.core.selected_channels = []
    group_tab.btn_select_live.clicked()
    process_events()
    assert app_gui.core.selected_channels == [10, 6, 4]

    # 7. Delete button deletes Group 2.5 cleanly
    group_tab.btn_delete.clicked()
    process_events()
    assert app_gui.core.lightshow.groups.get(2.5) is None
