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
"""GUI behavior tests for independent circuits."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import pytest
from olc.gtk3.application import Application  # noqa: E402

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
    assert inde_knob.level == 0
    assert inde_button.level == 0

    # 2. Execute set level to 50% on knob 1
    app_gui.core.action_registry.execute("independent.set_level", 1, 0.5)
    process_events()

    assert inde_knob.level == 128
    assert app_gui.virtual_console.independent1.value == 127.5

    # 3. Simulate knob movement on IHM to 100%
    app_gui.virtual_console.independent1.value = 255.0
    app_gui.virtual_console._inde_changed(app_gui.virtual_console.independent1)
    process_events()

    assert inde_knob.level == 255

    # 4. Execute set level to 100% on button 7
    app_gui.core.action_registry.execute("independent.set_level", 7, 1.0)
    process_events()

    assert inde_button.level == 255
    assert app_gui.virtual_console.independent7.get_active() is True

    # 5. Simulate button click on IHM to turn off
    app_gui.virtual_console.independent7.set_active(False)
    app_gui.virtual_console._inde_clicked(app_gui.virtual_console.independent7)
    process_events()

    assert inde_button.level == 0

    # Clean up
    app_gui.virtual_console.close()
    process_events()
