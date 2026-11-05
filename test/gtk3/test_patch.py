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

from __future__ import annotations

from unittest.mock import MagicMock

import cairo
import gi
import pytest

gi.require_version("Gtk", "3.0")

from olc.devices.builtin import create_rgb_definition  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.dmx_outputs import DMXOutputsTab  # noqa: E402
from olc.gtk3.patch_channels import PatchChannelsTab  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_dmx_outputs_tab_behavior(app_gui: Application) -> None:
    """Test DMXOutputsTab GUI interactions."""
    # 1. Open the DMX outputs tab
    app_gui.activate_action("dmx_outputs", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("dmx_outputs")
    assert isinstance(patch_tab, DMXOutputsTab)
    assert patch_tab.flowbox is not None

    # 2. Test initial state / select output 10 (index 9)
    children = patch_tab.flowbox.get_children()
    assert len(children) == 2048, (
        "Flowbox should contain 2048 outputs for all Universes."
    )

    # 3. Test patch changes reflection
    app_gui.core.action_registry.execute("patch.clear")
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) == 0

    app_gui.core.action_registry.execute("patch.set_1on1")
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) > 0, (
        "1:1 Patch should populate outputs."
    )

    app_gui.core.action_registry.execute("patch.clear")
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) == 0, (
        "Unpatch should empty outputs."
    )

    # 5. Undo unpatch all
    app_gui.activate_action("undo", None)
    process_events()
    assert len(app_gui.core.lightshow.patch.outputs) > 0, (
        "Undo should restore 1:1 patch."
    )


def test_patch_channels_tab_behavior(app_gui: Application) -> None:
    """Test PatchChannelsTab device selection and data updating."""
    # 1. Open the patch channels tab
    app_gui.activate_action("patch_channels", None)
    process_events()

    assert app_gui.tabs is not None
    patch_chan_tab = app_gui.tabs.tabs.get("patch_channels")
    assert isinstance(patch_chan_tab, PatchChannelsTab)
    assert patch_chan_tab.devices_treeview is not None
    assert patch_chan_tab.devices_store is not None

    # 2. Patch a device and verify reflection in device table
    app_gui.core.action_registry.execute("patch.clear")
    process_events()

    dev = patch_chan_tab.add_patched_device(
        device_id=5,
        fixture_key="Generic:Dimmer",
        universe=1,
        address=10,
        label="Front Dimmer",
    )
    process_events()

    assert dev.device_id == 5
    assert len(patch_chan_tab.devices_store) == 1
    row = patch_chan_tab.devices_store[0]
    assert row[0] == 5  # COL_ID
    assert row[1] == "Front Dimmer"  # COL_NAME

    # 3. Select device in TreeView
    selection = patch_chan_tab.devices_treeview.get_selection()
    first_iter = patch_chan_tab.devices_store.get_iter_first()
    assert first_iter is not None
    selection.select_iter(first_iter)
    assert patch_chan_tab.get_selected_device_id() == 5

    # 4. Remove device and verify removal
    removed = patch_chan_tab.remove_patched_device(5)
    process_events()
    assert removed is True
    assert len(patch_chan_tab.devices_store) == 0


def test_dmx_output_widget_draw_dimmer_and_device(app_gui: Application) -> None:
    """Test DMXOutputWidget drawing for simple dimmer and multi-parameter device."""
    app_gui.activate_action("dmx_outputs", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("dmx_outputs")
    assert isinstance(patch_tab, DMXOutputsTab)

    # 1. Clear patch and patch a simple dimmer on 1.1 and an RGB LED on 1.10
    app_gui.core.action_registry.execute("patch.clear")
    process_events()

    app_gui.core.lightshow.patch.patch_dimmer(channel=1, universe=1, address=1)
    rgb_def = create_rgb_definition()
    app_gui.core.lightshow.patch.patch_device(
        device_id=12, fixture_def=rgb_def, universe=1, address=10
    )
    # Patch a 4-digit device to test font scaling
    app_gui.core.lightshow.patch.patch_device(
        device_id=1001, fixture_def=rgb_def, universe=1, address=20
    )
    process_events()

    # 2. Render dimmer widget (output 1)
    w_dim = patch_tab.outputs[0]
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 70, 70)
    cr = cairo.Context(surface)
    w_dim.do_draw(cr)

    # 3. Render device widget (output 10, Red param)
    w_rgb = patch_tab.outputs[9]
    w_rgb.do_draw(cr)

    # 4. Render 4-digit device widget (output 20)
    w_large = patch_tab.outputs[19]
    w_large.do_draw(cr)


def test_dmx_outputs_network_dmx_refresh_devices(app_gui: Application) -> None:
    """Test that network DMX updates trigger queue_draw on device widgets."""
    app_gui.activate_action("dmx_outputs", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("dmx_outputs")
    assert isinstance(patch_tab, DMXOutputsTab)

    app_gui.core.action_registry.execute("patch.clear")
    process_events()

    rgb_def = create_rgb_definition()
    app_gui.core.lightshow.patch.patch_device(
        device_id=5, fixture_def=rgb_def, universe=1, address=1
    )
    process_events()

    # Mock queue_draw on the first 3 output widgets
    w1 = patch_tab.outputs[0]
    w2 = patch_tab.outputs[1]
    w3 = patch_tab.outputs[2]

    w1.queue_draw = MagicMock()
    w2.queue_draw = MagicMock()
    w3.queue_draw = MagicMock()

    # Simulate network DMX changed on outputs 0, 1, 2
    patch_tab.on_network_dmx_changed(1, [0, 1, 2])

    assert w1.queue_draw.called
    assert w2.queue_draw.called
    assert w3.queue_draw.called


def test_dmx_output_widget_draw_passive_curve(app_gui: Application) -> None:
    """Test passive curve drawing on a DMXOutputWidget with a non-linear curve."""
    app_gui.activate_action("dmx_outputs", None)
    process_events()

    assert app_gui.tabs is not None
    patch_tab = app_gui.tabs.tabs.get("dmx_outputs")
    assert isinstance(patch_tab, DMXOutputsTab)

    # Patch a dimmer with curve 1 (Square Root)
    app_gui.core.action_registry.execute("patch.clear")
    app_gui.core.lightshow.patch.patch_dimmer(channel=1, universe=1, address=1, curve=1)
    process_events()

    w_dim = patch_tab.outputs[0]
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 70, 70)
    cr = cairo.Context(surface)
    # Verify do_draw runs smoothly with passive curve drawing
    assert w_dim.do_draw(cr) is False
