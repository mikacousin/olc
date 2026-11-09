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
"""GUI behavior tests for real-time DMX outputs updates and park status."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import pytest
from gi.repository import Gtk

from olc.gtk3.application import Application
from olc.gtk3.dmx_outputs import DMXOutputsTab

from test.gtk3.conftest import process_events  # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_dmx_outputs_tab_realtime_park_unpatched_address(
    app_gui: Application,
) -> None:
    """Test that DMX visualizer updates in real time when parking an address."""
    app = app_gui
    assert app.backend is not None and app.backend.dmx is not None

    # Open dmx_outputs tab
    app.activate_action("dmx_outputs", None)
    process_events()

    assert app.tabs is not None
    assert "dmx_outputs" in app.tabs.tabs
    tab = app.tabs.tabs["dmx_outputs"]
    assert isinstance(tab, DMXOutputsTab)

    w0 = tab.outputs[0]
    w0.queue_draw = MagicMock()

    # Address 1/1 is unpatched
    assert app.core.lightshow.patch.get_address_occupant(1, 1) is None
    assert app.backend.dmx.frame[0][0] == 0

    # 1. Park unpatched address 1/1 at 200
    app.core.action_registry.execute("address.park", (1, 1), 200)
    process_events()

    assert app.backend.dmx.frame[0][0] == 200
    assert w0._is_parked() is True
    assert w0.queue_draw.called

    # 2. Unpark address 1/1
    w0.queue_draw.reset_mock()
    app.core.action_registry.execute("address.unpark", (1, 1))
    process_events()

    assert app.backend.dmx.frame[0][0] == 0
    assert w0._is_parked() is False
    assert w0.queue_draw.called


def test_dmx_outputs_tab_park_badge_and_color(app_gui: Application) -> None:
    """Test DMXOutputWidget _is_parked reflects both address and channel park."""
    app = app_gui
    # Patch channel 5 to universe 1 address 10
    app.core.lightshow.patch.patch_dimmer(channel=5, universe=1, address=10)

    app.activate_action("dmx_outputs", None)
    process_events()

    assert app.tabs is not None
    tab = app.tabs.tabs["dmx_outputs"]
    assert isinstance(tab, DMXOutputsTab)

    widget_idx = 9  # address 10 (1-based) is index 9
    w = tab.outputs[widget_idx]
    assert w._is_parked() is False

    # Park channel 5
    app.core.action_registry.execute("channel.park", 5, 80)
    process_events()
    assert w._is_parked() is True

    # Unpark channel 5
    app.core.action_registry.execute("channel.unpark", 5)
    process_events()
    assert w._is_parked() is False

    # Park physical address directly
    app.core.action_registry.execute("address.park", (1, 10), 128)
    process_events()
    assert w._is_parked() is True

    # Unpark physical address
    app.core.action_registry.execute("address.unpark", (1, 10))
    process_events()
    assert w._is_parked() is False


def test_shortcuts_window_contains_park_unpark_address() -> None:
    """Test that help-overlay.ui defines ADDRESS, PARK, and UNPARK shortcuts."""
    overlay_path = (
        pathlib.Path(__file__).resolve().parents[2] / "data" / "help-overlay.ui"
    )
    builder = Gtk.Builder()
    builder.add_from_file(str(overlay_path))

    window = builder.get_object("help_overlay")
    assert window is not None

    shift_d = builder.get_object("shift_syntax_d")
    assert shift_d is not None
    assert shift_d.get_property("title") == "ADDRESS"
    assert shift_d.get_property("accelerator") == "<shift>D"

    shift_p = builder.get_object("shift_syntax_p")
    assert shift_p is not None
    assert shift_p.get_property("title") == "PARK"
    assert shift_p.get_property("accelerator") == "<shift>P"

    alt_p = builder.get_object("alt_syntax_p")
    assert alt_p is not None
    assert alt_p.get_property("title") == "UNPARK"
    assert alt_p.get_property("accelerator") == "<alt>P"
