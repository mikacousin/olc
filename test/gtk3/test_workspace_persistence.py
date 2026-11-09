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
"""GUI-specific tests for workspace and tab settings persistence."""

from __future__ import annotations

import gzip
import json
import pathlib

import pytest

from olc.gtk3.application import Application
from olc.gtk3.cue import CuesEditionTab
from olc.gtk3.group import GroupTab
from test.gtk3.conftest import process_events  # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_tab_settings_retention_across_close_and_reopen(
    app_gui: Application,
) -> None:
    """Test that configuring an open tab, closing it, and reopening retains settings."""
    assert app_gui.tabs is not None

    # 1. Open groups tab
    app_gui.open_groups()
    process_events()

    groups_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(groups_tab, GroupTab)
    assert groups_tab.channels_view is not None

    # 2. Configure view mode to Patched
    groups_tab.channels_view.set_view_mode_by_name("Patched")
    process_events()
    assert groups_tab.channels_view.view_mode == 1
    assert groups_tab.channels_view.get_view_mode_name() == "Patched"

    # 3. Physically close the groups tab
    app_gui.tabs.close_physically("groups")
    process_events()
    assert app_gui.tabs.tabs.get("groups") is None

    # 4. Reopen the groups tab and verify retained setting
    app_gui.open_groups()
    process_events()

    new_groups_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(new_groups_tab, GroupTab)
    assert new_groups_tab is not groups_tab  # New widget instance
    assert new_groups_tab.channels_view.view_mode == 1
    assert new_groups_tab.channels_view.get_view_mode_name() == "Patched"


def test_full_workspace_persistence_on_save_and_open(
    app_gui: Application,
    tmp_path: pathlib.Path,
) -> None:
    """Test saving a show with open tabs and custom view modes and restoring on open."""
    assert app_gui.tabs is not None
    assert app_gui.window is not None

    # 1. Open and configure memories tab
    app_gui.open_memories()
    process_events()
    mem_tab = app_gui.tabs.tabs.get("memories")
    assert isinstance(mem_tab, CuesEditionTab)
    mem_tab.channels_view.set_view_mode_by_name("Active")
    process_events()

    # 2. Open and configure groups tab
    app_gui.open_groups()
    process_events()
    grp_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(grp_tab, GroupTab)
    grp_tab.channels_view.set_view_mode_by_name("Patched")
    process_events()

    # 3. Configure paned position
    assert app_gui.window.paned is not None
    app_gui.window.paned.set_position(500)
    process_events()
    expected_pos = app_gui.window.paned.get_position()

    # 4. Save show to temporary file
    save_path = str(tmp_path / "workspace_show.olc")
    app_gui.core.action_registry.execute("show.save", save_path)
    process_events()
    assert pathlib.Path(save_path).exists()

    # 5. Reset via show.new
    app_gui.core.action_registry.execute("show.new")
    process_events()
    assert app_gui.tabs.tabs.get("memories") is None
    assert app_gui.tabs.tabs.get("groups") is None

    # 6. Reopen saved show via show.open
    app_gui.core.action_registry.execute("show.open", save_path)
    process_events()

    # 7. Verify tabs are restored
    restored_mem = app_gui.tabs.tabs.get("memories")
    restored_grp = app_gui.tabs.tabs.get("groups")
    assert isinstance(restored_mem, CuesEditionTab)
    assert isinstance(restored_grp, GroupTab)

    # 8. Verify display parameters
    assert restored_mem.channels_view.get_view_mode_name() == "Active"
    assert restored_grp.channels_view.get_view_mode_name() == "Patched"

    # 9. Verify paned position
    assert app_gui.window.paned.get_position() == expected_pos


def test_legacy_show_open_in_gui_applies_default_workspace(
    app_gui: Application,
    tmp_path: pathlib.Path,
) -> None:
    """Test opening a legacy show in GUI cleanly falls back to default workspace."""
    legacy_file = tmp_path / "legacy_gui.olc"
    data = {
        "application": "olc",
        "version": "0.8.5.beta",
        "patch": {},
        "sequences": {},
        "cues": {},
    }
    with gzip.open(str(legacy_file), "wb") as f:
        f.write(json.dumps(data).encode("utf-8"))

    # Open memories first to have an extra tab
    app_gui.open_memories()
    process_events()
    assert app_gui.tabs is not None
    assert app_gui.tabs.tabs.get("memories") is not None

    # Open legacy file
    app_gui.core.action_registry.execute("show.open", str(legacy_file))
    process_events()

    # Extra tab should have closed, leaving default layout
    assert app_gui.tabs.tabs.get("memories") is None
