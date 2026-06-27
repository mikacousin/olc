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
"""GUI behavior tests for live view channel selection."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import pytest
from olc.gtk3.application import Application  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_live_view_channel_selection(app_gui: Application) -> None:
    """Test channel selection/deselection via keyboard in the live view.

    Covers:
    - C key selects the channel entered in the commandline
    - 0 C deselects all channels
    - C alone (empty commandline) deselects all channels
    - Undo/redo of both operations
    """
    assert app_gui.window is not None
    channels_view = app_gui.window.live_view.channels_view
    commandline = app_gui.core.commandline

    # Reset selection state
    app_gui.core.live_selection.selected_channels = []
    app_gui.core.live_selection.last_selected_channel = None

    # 1. Select channel 3 via "3 C"
    commandline.set_string("3")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == [3]
    assert app_gui.core.last_selected_channel == 3

    # 2. Add channel 7 via "7 +"
    commandline.set_string("7")
    channels_view.select_plus()
    process_events()
    assert set(app_gui.core.selected_channels) == {3, 7}

    # 3. Deselect all via "0 C"
    commandline.set_string("0")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == []
    assert app_gui.core.last_selected_channel is None

    # 4. Undo: should restore {3, 7}
    app_gui.activate_action("undo", None)
    process_events()
    assert set(app_gui.core.selected_channels) == {3, 7}

    # 5. Redo: should clear again
    app_gui.activate_action("redo", None)
    process_events()
    assert app_gui.core.selected_channels == []

    # 6. Re-select channel 5, then deselect via bare C (empty commandline)
    commandline.set_string("5")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == [5]

    commandline.set_string("")
    channels_view.select_channel()
    process_events()
    assert app_gui.core.selected_channels == []
    assert app_gui.core.last_selected_channel is None
