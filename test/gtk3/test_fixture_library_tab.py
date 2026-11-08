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
"""Unit tests for FixtureLibraryTab GTK3 widget."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.fixture_library import (  # noqa: E402
    COL_CAT_MODEL,
    FixtureLibraryTab,
)

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip


def test_fixture_library_tab_opens_and_inspects_builtin(app_gui: Application) -> None:
    """Test opening Fixtures tab and verifying read-only state for built-ins."""
    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    # Catalog should contain the 6 built-in fixtures
    assert len(fixtures_tab.cat_store) >= 6

    # Select Generic:Dimmer
    lib = fixtures_tab.fixture_library
    dimmer_def = lib.get("Generic", "Dimmer")
    fixtures_tab.load_definition(dimmer_def)
    process_events()

    assert fixtures_tab.entry_mfg.get_text() == "Generic"
    assert fixtures_tab.entry_model.get_text() == "Dimmer"
    assert fixtures_tab.btn_apply.get_sensitive() is False
    assert fixtures_tab.btn_delete.get_sensitive() is False
    assert "Built-in profile (Read-Only)" in fixtures_tab.lbl_status.get_text()


def test_fixture_library_tab_duplicate_edit_and_apply(app_gui: Application) -> None:
    """Test duplicating a profile, modifying channels/home, and applying to the show."""
    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    # Select Generic:Moving Head Spot
    spot_def = fixtures_tab.fixture_library.get("Generic", "Moving Head Spot")
    fixtures_tab.load_definition(spot_def)
    process_events()

    # Click Duplicate
    fixtures_tab._on_duplicate_clicked(fixtures_tab.btn_duplicate)
    process_events()

    # Active definition should now be a Custom copy and editable
    active = fixtures_tab.active_definition
    assert active is not None
    assert active.manufacturer == "Custom"
    assert "Moving Head Spot" in active.model
    assert active.is_builtin is False
    assert fixtures_tab.btn_apply.get_sensitive() is True

    # Modify channel 1 (Pan) default Home value to 12345
    mode = active.default_mode()
    pan_def = mode.channel_defs[0]
    pan_def.default_value = 12345

    # Click Apply Changes
    fixtures_tab._on_apply_clicked(fixtures_tab.btn_apply)
    process_events()

    saved = fixtures_tab.fixture_library.get(active.manufacturer, active.model)
    assert saved is not None
    assert saved.default_mode().channel_defs[0].default_value == 12345

    # Delete custom copy
    fixtures_tab._on_delete_clicked(fixtures_tab.btn_delete)
    process_events()
    key = f"{active.manufacturer}:{active.model}"
    assert key not in fixtures_tab.fixture_library.keys()


def test_fixture_library_tab_new_and_filter(app_gui: Application) -> None:
    """Test creating a new profile and filtering in the catalog."""
    fixtures_tab = FixtureLibraryTab(app=app_gui)
    process_events()

    # Create new
    fixtures_tab._on_new_clicked(fixtures_tab.btn_new)
    process_events()

    assert fixtures_tab.active_definition is not None
    assert fixtures_tab.active_definition.manufacturer == "Custom"
    assert "New Fixture" in fixtures_tab.active_definition.model

    # Filter catalog
    fixtures_tab.search_entry.set_text("New Fixture")
    process_events()

    visible_models: list[str] = []
    tree_model = fixtures_tab.cat_tree.get_model()
    assert tree_model is not None
    for row in tree_model:
        visible_models.append(row[COL_CAT_MODEL])
    assert any("New Fixture" in m for m in visible_models)

    # Clear filter
    fixtures_tab.search_entry.set_text("")
    process_events()

    # Clean up created fixture
    fixtures_tab._on_delete_clicked(fixtures_tab.btn_delete)
    process_events()
    fixtures_tab.cleanup()
