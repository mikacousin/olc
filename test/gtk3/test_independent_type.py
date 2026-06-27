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
"""GUI and Action behavior tests for independent circuit type changes."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import pytest
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.widgets.knob import KnobWidget
from olc.gtk3.widgets.toggle import ToggleWidget

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_action_change_type(app_gui: Application) -> None:
    """Test independent.change_type action and undo/redo."""
    inde = app_gui.core.lightshow.independents.independents[0]
    assert inde.inde_type == "knob"

    # 1. Execute type change to button
    app_gui.core.action_registry.execute("independent.change_type", 1, "button")
    process_events()
    assert inde.inde_type == "button"

    # 2. Undo
    app_gui.activate_action("undo", None)
    process_events()
    assert inde.inde_type == "knob"

    # 3. Redo
    app_gui.activate_action("redo", None)
    process_events()
    assert inde.inde_type == "button"

    # Reset
    app_gui.core.action_registry.execute("independent.change_type", 1, "knob")
    process_events()


def test_gui_change_type_rebuilds_virtual_console(app_gui: Application) -> None:
    """Test that changing independent type rebuilds Virtual Console."""
    # 1. Setup Virtual Console GUI
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # Verify initial widgets (1 is KnobWidget, 7 is ToggleWidget)
    assert isinstance(app_gui.virtual_console.independent1, KnobWidget)
    assert isinstance(app_gui.virtual_console.independent7, ToggleWidget)

    # 2. Change independent 1 to button
    app_gui.core.action_registry.execute("independent.change_type", 1, "button")
    process_events()

    # Verify widget 1 is now a ToggleWidget!
    assert isinstance(app_gui.virtual_console.independent1, ToggleWidget)

    # 3. Change independent 7 to knob
    app_gui.core.action_registry.execute("independent.change_type", 7, "knob")
    process_events()

    # Verify widget 7 is now a KnobWidget!
    assert isinstance(app_gui.virtual_console.independent7, KnobWidget)

    # Reset both to default configuration
    app_gui.core.action_registry.execute("independent.change_type", 1, "knob")
    app_gui.core.action_registry.execute("independent.change_type", 7, "button")
    process_events()

    # Clean up
    app_gui.virtual_console.close()
    process_events()
