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
"""GUI behavior tests for the Patch tab."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.patch_channels import PatchChannelsTab  # noqa: E402
from olc.gtk3.patch_outputs import PatchOutputsTab  # noqa: E402
from olc.gtk3.widgets.patch_channels import PatchChannelWidget  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


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
