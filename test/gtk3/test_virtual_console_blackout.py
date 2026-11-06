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
"""GUI behavior tests for Virtual Console Blackout toggle button."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel

from __future__ import annotations

import mido
import pytest
from gi.repository import Gtk

from olc.gtk3.application import Application

from test.gtk3.conftest import process_events  # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_virtual_console_blackout_initial_state(app_gui: Application) -> None:
    """Test Virtual Console Blackout initial state reflects Core."""
    # Ensure blackout is off initially
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    process_events()

    # 1. Open virtual console when blackout is False
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    assert isinstance(vc.blackout, Gtk.ToggleButton)
    assert vc.blackout.get_active() is False
    assert vc.blackout.get_style_context().has_class("olc-blackout-toggle")

    # Close virtual console
    vc.close()
    process_events()

    # 2. Activate blackout, then open virtual console
    app_gui.core.action_registry.execute("dmx.blackout_all", True)
    process_events()
    assert app_gui.core.blackout_active is True

    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console
    assert vc.blackout.get_active() is True

    # Cleanup
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    process_events()
    vc.close()
    process_events()


def test_virtual_console_blackout_click_toggles(app_gui: Application) -> None:
    """Test clicking Blackout in Virtual Console toggles blackout state."""
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    process_events()

    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    assert vc.blackout.get_active() is False
    assert app_gui.core.blackout_active is False

    # Simulate user toggling button to active
    vc.blackout.set_active(True)
    process_events()

    assert app_gui.core.blackout_active is True
    if app_gui.core.backend and hasattr(app_gui.core.backend, "dmx"):
        assert app_gui.core.backend.dmx.blackout is True

    # Simulate user toggling button back to inactive
    vc.blackout.set_active(False)
    process_events()

    assert app_gui.core.blackout_active is False
    if app_gui.core.backend and hasattr(app_gui.core.backend, "dmx"):
        assert app_gui.core.backend.dmx.blackout is False

    vc.close()
    process_events()


def test_virtual_console_blackout_external_sync(app_gui: Application) -> None:
    """Test that external blackout changes sync to the Virtual Console button."""
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    process_events()

    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    assert vc.blackout.get_active() is False

    # External toggle ON via action
    app_gui.core.action_registry.execute("dmx.blackout_all", True)
    process_events()
    assert vc.blackout.get_active() is True

    # External toggle OFF via action
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    process_events()
    assert vc.blackout.get_active() is False

    vc.close()
    process_events()


def test_virtual_console_blackout_midi_learning(app_gui: Application) -> None:
    """Test clicking Blackout button during MIDI learn mode sets learning target."""
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    process_events()

    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    # Activate MIDI learning
    app_gui.core.action_registry.execute("midi.learn_toggle", " ")
    process_events()
    assert vc.is_learning_midi is True

    # Click blackout during learn mode
    vc.blackout.set_active(True)
    process_events()

    assert app_gui.midi is not None
    assert app_gui.midi.learning == "dmx.blackout_all"
    # Blackout state should not have toggled in core during learn mode
    assert app_gui.core.blackout_active is False

    # Disable MIDI learning
    app_gui.core.action_registry.execute("midi.learn_toggle", None)
    process_events()
    vc.close()
    process_events()


def test_midi_notes_blackout_all(app_gui: Application) -> None:
    """Test MIDI notes handler dispatches dmx.blackout_all on note velocity 127."""
    assert app_gui.midi is not None
    notes = app_gui.midi.messages.notes

    assert "dmx.blackout_all" in notes.notes

    app_gui.core.action_registry.execute("dmx.blackout_all", False)
    assert app_gui.core.blackout_active is False

    # Trigger with velocity 127
    msg_on = mido.Message("note_on", note=60, velocity=127)
    notes.blackout_all(msg_on)
    assert app_gui.core.blackout_active is True

    # Velocity 0 should not trigger
    msg_off = mido.Message("note_off", note=60, velocity=0)
    notes.blackout_all(msg_off)
    assert app_gui.core.blackout_active is True

    # Reset
    app_gui.core.action_registry.execute("dmx.blackout_all", False)
