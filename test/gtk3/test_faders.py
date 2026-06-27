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
"""GUI behavior tests for the Faders tab and Virtual Console faders."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.fader_bank import FaderType  # noqa: E402
from olc.group import Group  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.fader import FaderEdit, FaderTab  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


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

    # Get first fader (widget and logical fader)
    gui_fader_widget = app_gui.virtual_console.faders[0]
    logical_fader = app_gui.core.lightshow.fader_bank.faders[1][1]

    # Verify initial levels
    assert logical_fader.level == 0.0
    assert gui_fader_widget.get_value() == 0.0

    # 2. Configure fader 1 contents as Group 1 (levels: {1: 255})
    app_gui.core.lightshow.groups.clear()
    app_gui.core.lightshow.groups.add(Group(1.0, {1: 255}, "Group A"))
    app_gui.core.lightshow.fader_bank.set_fader(1, 1, FaderType.GROUP, 1.0)
    process_events()

    # Re-evaluate logical_fader as it has been replaced with a FaderGroup instance
    logical_fader = app_gui.core.lightshow.fader_bank.faders[1][1]
    assert logical_fader.level == 0.0
    assert logical_fader.dmx[0] == 0

    # 3. Execute action: Set fader 1 (page 1, index 1) to 80% (0.8)
    app_gui.core.action_registry.execute("fader.set_level", 1, 1, 0.8)
    process_events()

    # 4. Assert passive updates
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
