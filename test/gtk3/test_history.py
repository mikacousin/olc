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
"""GUI behavior tests for the History tab."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.history import HistoryTab  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_history_tab_behavior(app_gui: Application) -> None:
    """Test HistoryTab creation, update, undo/redo button actions, row activation,
    and clearing."""
    # 1. Clear any initial history
    app_gui.core.history.clear()
    process_events()

    # 2. Open history tab
    app_gui.history_cb(None, None)
    process_events()

    assert app_gui.tabs is not None
    history_tab = app_gui.tabs.tabs.get("history")
    assert isinstance(history_tab, HistoryTab)
    # The action of opening the tab itself is in the undo stack
    assert len(history_tab.liststore) == 1
    assert history_tab.liststore[0][1] == "gui.tab_open"

    # Buttons should reflect the 1 active action
    assert history_tab.btn_undo.get_sensitive()
    assert not history_tab.btn_redo.get_sensitive()
    assert history_tab.btn_clear.get_sensitive()

    # 3. Perform some actions to populate history
    app_gui.core.action_registry.execute("channel.set_level", 1, 200)
    process_events()
    app_gui.core.action_registry.execute("channel.set_level", 2, 100)
    process_events()

    # Verify history manager has the actions (tab_open + 2 channel actions)
    assert len(app_gui.core.history.undo_stack) == 3
    assert len(app_gui.core.history.redo_stack) == 0

    # Verify history tab liststore is updated (3 rows)
    assert len(history_tab.liststore) == 3
    # Row 0: gui.tab_open (active)
    # Row 1: channel 1 action (active)
    # Row 2: channel 2 action (active)
    assert history_tab.liststore[0][0] == "✔"
    assert history_tab.liststore[0][1] == "gui.tab_open"

    assert history_tab.liststore[1][0] == "✔"
    assert history_tab.liststore[1][1] == "channel.set_level"
    assert "channel: 1" in history_tab.liststore[1][2]
    assert history_tab.liststore[1][3] is True

    assert history_tab.liststore[2][0] == "✔"
    assert history_tab.liststore[2][1] == "channel.set_level"
    assert "channel: 2" in history_tab.liststore[2][2]
    assert history_tab.liststore[2][3] is True

    # Buttons should be active/sensitive
    assert history_tab.btn_undo.get_sensitive()
    assert not history_tab.btn_redo.get_sensitive()
    assert history_tab.btn_clear.get_sensitive()

    # 4. Test Undo / Redo buttons
    history_tab.on_undo_clicked(history_tab.btn_undo)
    process_events()
    assert len(app_gui.core.history.undo_stack) == 2
    assert len(app_gui.core.history.redo_stack) == 1
    assert len(history_tab.liststore) == 3
    # Third row status should be empty and is_active (col 3) should be False
    # (insensitive)
    assert history_tab.liststore[2][0] == ""
    assert history_tab.liststore[2][3] is False

    history_tab.on_redo_clicked(history_tab.btn_redo)
    process_events()
    assert len(app_gui.core.history.undo_stack) == 3
    assert len(app_gui.core.history.redo_stack) == 0

    # 5. Test Row Activation (double-click to jump to state)
    # Jump back to state after first channel action (idx=1)
    # Double-clicking index 1 should undo 1 step (to reach state after index 1).
    path = Gtk.TreePath.new_from_string("1")
    history_tab.on_row_activated(history_tab.treeview, path, Gtk.TreeViewColumn(""))
    process_events()

    assert len(app_gui.core.history.undo_stack) == 2
    assert len(app_gui.core.history.redo_stack) == 1
    # Check level of channel 2 is restored/undone to -1 (released), channel 1 is still
    # 200
    assert app_gui.backend.dmx.levels["user"][1] == -1
    assert app_gui.backend.dmx.levels["user"][0] == 200

    # Jump forward to second channel action (idx=2)
    path = Gtk.TreePath.new_from_string("2")
    history_tab.on_row_activated(history_tab.treeview, path, Gtk.TreeViewColumn(""))
    process_events()

    assert len(app_gui.core.history.undo_stack) == 3
    assert len(app_gui.core.history.redo_stack) == 0
    assert app_gui.backend.dmx.levels["user"][1] == 100

    # 6. Test Clear History
    history_tab.on_clear_clicked(history_tab.btn_clear)
    process_events()
    assert len(app_gui.core.history.undo_stack) == 0
    assert len(app_gui.core.history.redo_stack) == 0
    assert len(history_tab.liststore) == 0
