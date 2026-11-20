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
"""GUI and action behavior tests for independent circuits and type changes."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import pytest

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.widgets.knob import KnobWidget
from olc.gtk3.widgets.toggle import ToggleWidget
from olc.show.independent import IndependentType

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_gui_independent_set_level_action(app_gui: Application) -> None:
    """Test that independent.set_level action works and updates Virtual Console."""
    # 1. Setup Virtual Console GUI
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # Get independent 1 (knob) and 7 (button)
    inde_knob = app_gui.core.lightshow.independents.independents[0]
    inde_button = app_gui.core.lightshow.independents.independents[6]

    # Verify initial levels
    assert inde_knob.level == 0.0
    assert inde_button.level == 0.0

    # 2. Execute set level to 50% on knob 1
    app_gui.core.action_registry.execute("independent.set_level", 1, 0.5)
    process_events()

    assert inde_knob.level == 0.5
    assert app_gui.virtual_console.independent1.value == 127.5

    # 3. Simulate knob movement on IHM to 100%
    app_gui.virtual_console.independent1.value = 255.0
    app_gui.virtual_console._inde_changed(app_gui.virtual_console.independent1)
    process_events()

    assert inde_knob.level == 1.0

    # 4. Execute set level to 100% on button 7
    app_gui.core.action_registry.execute("independent.set_level", 7, 1.0)
    process_events()

    assert inde_button.level == 1.0
    assert app_gui.virtual_console.independent7.get_active() is True

    # 5. Simulate button click on IHM to turn off
    app_gui.virtual_console.independent7.set_active(False)
    app_gui.virtual_console._inde_clicked(app_gui.virtual_console.independent7)
    process_events()

    assert inde_button.level == 0.0

    # Clean up
    app_gui.virtual_console.close()
    process_events()


def test_action_change_type(app_gui: Application) -> None:
    """Test independent.change_type action and undo/redo."""
    inde = app_gui.core.lightshow.independents.independents[0]
    assert inde.inde_type == IndependentType.KNOB

    # 1. Execute type change to button
    app_gui.core.action_registry.execute(
        "independent.change_type", 1, IndependentType.BUTTON
    )
    process_events()
    assert inde.inde_type == IndependentType.BUTTON

    # 2. Undo
    app_gui.activate_action("undo", None)
    process_events()
    assert inde.inde_type == IndependentType.KNOB

    # 3. Redo
    app_gui.activate_action("redo", None)
    process_events()
    assert inde.inde_type == IndependentType.BUTTON

    # Reset
    app_gui.core.action_registry.execute(
        "independent.change_type", 1, IndependentType.KNOB
    )
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
    app_gui.core.action_registry.execute(
        "independent.change_type", 1, IndependentType.BUTTON
    )
    process_events()

    # Verify widget 1 is now a ToggleWidget!
    assert isinstance(app_gui.virtual_console.independent1, ToggleWidget)

    # 3. Change independent 7 to knob
    app_gui.core.action_registry.execute(
        "independent.change_type", 7, IndependentType.KNOB
    )
    process_events()

    # Verify widget 7 is now a KnobWidget!
    assert isinstance(app_gui.virtual_console.independent7, KnobWidget)

    # Reset both to default configuration
    app_gui.core.action_registry.execute(
        "independent.change_type", 1, IndependentType.KNOB
    )
    app_gui.core.action_registry.execute(
        "independent.change_type", 7, IndependentType.BUTTON
    )
    process_events()

    # Clean up
    app_gui.virtual_console.close()
    process_events()
