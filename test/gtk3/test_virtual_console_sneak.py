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
"""GUI behavior tests for Virtual Console Sneak button."""

from __future__ import annotations

import mido
import pytest

from olc.gtk3.application import Application
from olc.gtk3.widgets.button import ButtonWidget

from test.gtk3.conftest import process_events  # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_virtual_console_sneak_button_exists_and_sensitivity(
    app_gui: Application,
) -> None:
    """Test Virtual Console Sneak button existence and dynamic sensitivity."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    assert hasattr(vc, "sneak")
    assert isinstance(vc.sneak, ButtonWidget)
    assert vc.sneak.label == "Sneak"

    # Command line is empty -> sneak should be sensitive
    app_gui.core.commandline.set_string("")
    vc.update_button_sensitivity()
    assert vc.sneak.get_sensitive() is True

    # After channel selection -> sneak should be sensitive
    app_gui.core.commandline.set_string("1 THRU 5")
    vc.update_button_sensitivity()
    assert vc.sneak.get_sensitive() is True

    # In a context where SNEAK is not valid (e.g. after TIME)
    app_gui.core.commandline.set_string("TIME ")
    vc.update_button_sensitivity()
    assert vc.sneak.get_sensitive() is False

    # Cleanup
    app_gui.core.commandline.set_string("")
    vc.close()
    process_events()


def test_virtual_console_sneak_click_behavior(app_gui: Application) -> None:
    """Test clicking Sneak button in Virtual Console appends correctly."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    # 1. From empty command line
    app_gui.core.commandline.set_string("")
    vc.sneak.emit("clicked")
    process_events()
    assert app_gui.core.commandline.get_string() == "SNEAK "

    # 2. From channel selection
    app_gui.core.commandline.set_string("1 THRU 3")
    vc.sneak.emit("clicked")
    process_events()
    assert app_gui.core.commandline.get_string() == "1 THRU 3 SNEAK "

    # Cleanup
    app_gui.core.commandline.set_string("")
    vc.close()
    process_events()


def test_virtual_console_sneak_midi_learning_and_dispatch(
    app_gui: Application,
) -> None:
    """Test Sneak button MIDI learn and MIDI dispatch."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    # Activate MIDI learning
    app_gui.core.action_registry.execute("midi.learn_toggle", " ")
    process_events()
    assert vc.is_learning_midi is True

    # Click Sneak during MIDI learn mode
    vc.sneak.emit("clicked")
    process_events()

    assert app_gui.midi is not None
    assert app_gui.midi.learning == "sneak"

    # Disable MIDI learning
    app_gui.core.action_registry.execute("midi.learn_toggle", None)
    process_events()

    # Test MIDI message dispatch for sneak
    app_gui.core.commandline.set_string("")
    assert "sneak" in app_gui.midi.messages.notes.notes
    msg = mido.Message("note_on", note=60, velocity=127)
    app_gui.midi.messages.notes._dispatch("sneak", msg)
    assert app_gui.core.commandline.get_string().strip() == "SNEAK"

    # Cleanup
    app_gui.core.commandline.set_string("")
    vc.close()
    process_events()
