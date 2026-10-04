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
"""Unit tests for MIDI actions (port_toggle, set_port_mode, learn_toggle,
assign_mapping, clear_mappings).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from gi.repository import Gtk
from olc.core.app import CoreApplication
from olc.gtk3.event_bridge import GuiEventBridge
from olc.settings import SettingsTab


def test_midi_port_toggle_action_and_undo_redo() -> None:
    """Test midi.port_toggle action execution, undo, and redo."""
    stored_settings: dict[str, list[str]] = {"midi-ports": ["existing_port"]}

    settings = MagicMock()
    settings.get_strv.side_effect = lambda k: list(stored_settings.get(k, []))

    def mock_set_strv(k: str, val: list[str]) -> None:
        stored_settings[k] = list(val)

    settings.set_strv.side_effect = mock_set_strv

    app = CoreApplication(settings)

    mock_midi = MagicMock()
    mock_ports = MagicMock()
    mock_midi.ports = mock_ports
    app.midi = mock_midi

    events: list[tuple[str, bool]] = []
    app.subscribe("midi.port_toggled", lambda p, en: events.append((p, en)))

    # 1. Enable new port
    app.action_registry.execute("midi.port_toggle", "new_port", True)
    assert "new_port" in stored_settings["midi-ports"]
    mock_ports.close.assert_called_once()
    mock_ports.open.assert_called_once()
    mock_midi.update_faders.assert_called_once()
    assert events == [("new_port", True)]

    # 2. Undo
    mock_ports.close.reset_mock()
    mock_ports.open.reset_mock()
    app.history.undo()
    assert "new_port" not in stored_settings["midi-ports"]
    assert "existing_port" in stored_settings["midi-ports"]
    mock_ports.close.assert_called_once()
    mock_ports.open.assert_called_once()

    # 3. Redo
    app.history.redo()
    assert "new_port" in stored_settings["midi-ports"]


def test_midi_set_port_mode_action_and_undo_redo() -> None:
    """Test midi.set_port_mode action execution, undo, and redo."""
    stored_settings: dict[str, list[str]] = {
        "relative1": [],
        "relative2": [],
        "makie": ["controller_1"],
        "absolute": [],
    }

    settings = MagicMock()
    settings.get_strv.side_effect = lambda k: list(stored_settings.get(k, []))

    def mock_set_strv(k: str, val: list[str]) -> None:
        stored_settings[k] = list(val)

    settings.set_strv.side_effect = mock_set_strv

    app = CoreApplication(settings)

    events: list[tuple[str, str]] = []
    app.subscribe("midi.port_mode_changed", lambda p, m: events.append((p, m)))

    # 1. Change mode from Mackie to Relative1
    app.action_registry.execute("midi.set_port_mode", "controller_1", "Relative1")
    assert "controller_1" not in stored_settings["makie"]
    assert "controller_1" in stored_settings["relative1"]
    assert events == [("controller_1", "Relative1")]

    # 2. Undo
    app.history.undo()
    assert "controller_1" in stored_settings["makie"]
    assert "controller_1" not in stored_settings["relative1"]

    # 3. Redo
    app.history.redo()
    assert "controller_1" not in stored_settings["makie"]
    assert "controller_1" in stored_settings["relative1"]


def test_midi_learn_toggle_action() -> None:
    """Test midi.learn_toggle action execution."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_midi = MagicMock()
    mock_midi.learning = ""
    app.midi = mock_midi

    events: list[str] = []
    app.subscribe("midi.learning_changed", events.append)

    app.action_registry.execute("midi.learn_toggle", "playback.go")
    assert mock_midi.learning == "playback.go"
    assert events == ["playback.go"]

    app.action_registry.execute("midi.learn_toggle", None)
    assert mock_midi.learning == ""
    assert events == ["playback.go", ""]


def test_midi_assign_mapping_action_and_undo_redo() -> None:
    """Test midi.assign_mapping action execution, collision handling, and undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_midi = MagicMock()
    mock_notes = MagicMock()
    mock_notes.notes = {"playback.go": [0, 94], "other.action": [0, 60]}
    mock_notes.cc_notes = {"playback.go": [0, -1], "other.action": [0, -1]}

    mock_cc = MagicMock()
    mock_cc.control_change = {"wheel": [0, 16]}

    mock_pitch = MagicMock()
    mock_pitch.pitchwheel = {"crossfade_in": -1}

    mock_midi.messages.notes = mock_notes
    mock_midi.messages.control_change = mock_cc
    mock_midi.messages.pitchwheel = mock_pitch
    mock_midi.learning = ""

    mock_notes.learn.side_effect = lambda msg, act: mock_notes.notes.update(
        {act: [msg.channel, msg.note]}
    )
    mock_cc.learn.side_effect = lambda msg, act: mock_cc.control_change.update(
        {act: [msg.channel, msg.control]}
    )
    mock_pitch.learn.side_effect = lambda msg, act: mock_pitch.pitchwheel.update(
        {act: msg.pitch}
    )
    app.midi = mock_midi

    events: list[tuple[str, str, int, int]] = []
    app.subscribe(
        "midi.mapping_assigned",
        lambda evt, act, ch, num: events.append((evt, act, ch, num)),
    )

    # 1. Assign note 60 to playback.go
    app.action_registry.execute("midi.assign_mapping", "note", "playback.go", 0, 60)
    assert mock_notes.notes["playback.go"] == [0, 60]
    assert events == [("note", "playback.go", 0, 60)]

    # 2. Undo
    app.history.undo()
    assert mock_notes.notes["playback.go"] == [0, 94]

    # 3. Redo
    app.history.redo()
    assert mock_notes.notes["playback.go"] == [0, 60]


def test_midi_clear_mappings_action_and_undo_redo() -> None:
    """Test midi.clear_mappings action execution, undo, and redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_midi = MagicMock()
    mock_notes = MagicMock()
    mock_notes.notes = {"playback.go": [0, 94], "clear": [0, 50]}
    mock_notes.cc_notes = {"playback.go": [0, -1], "clear": [0, -1]}

    mock_cc = MagicMock()
    mock_cc.control_change = {"wheel": [0, 16]}

    mock_pitch = MagicMock()
    mock_pitch.pitchwheel = {"fader_1": 0}

    mock_midi.messages.notes = mock_notes
    mock_midi.messages.control_change = mock_cc
    mock_midi.messages.pitchwheel = mock_pitch

    def mock_reset_messages() -> None:
        mock_notes.notes = {k: [0, -1] for k in mock_notes.notes}
        mock_notes.cc_notes = {k: [0, -1] for k in mock_notes.cc_notes}
        mock_cc.control_change = {k: [0, -1] for k in mock_cc.control_change}
        mock_pitch.pitchwheel = {k: -1 for k in mock_pitch.pitchwheel}

    mock_midi.reset_messages.side_effect = mock_reset_messages
    app.midi = mock_midi

    # 1. Clear single action mapping
    app.action_registry.execute("midi.clear_mappings", "playback.go")
    assert mock_notes.notes["playback.go"] == [0, -1]
    assert mock_notes.notes["clear"] == [0, 50]

    # Undo single clear
    app.history.undo()
    assert mock_notes.notes["playback.go"] == [0, 94]

    # 2. Clear all mappings
    app.action_registry.execute("midi.clear_mappings", None)
    assert mock_notes.notes["playback.go"] == [0, -1]
    assert mock_notes.notes["clear"] == [0, -1]
    assert mock_cc.control_change["wheel"] == [0, -1]
    assert mock_pitch.pitchwheel["fader_1"] == -1

    # Undo clear all
    app.history.undo()
    assert mock_notes.notes["playback.go"] == [0, 94]
    assert mock_notes.notes["clear"] == [0, 50]
    assert mock_cc.control_change["wheel"] == [0, 16]
    assert mock_pitch.pitchwheel["fader_1"] == 0


def test_event_bridge_midi_settings_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GuiEventBridge routes midi.port_toggled and midi.port_mode_changed
    to SettingsTab."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))
    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {"settings": mock_settings_tab}

    _bridge = GuiEventBridge(mock_app)

    # 1. Trigger midi.port_toggled via action undo
    core.emit("midi.port_toggled", "BCF2000", True)
    mock_settings_tab.update_midi_port_toggle.assert_called_once_with("BCF2000", True)

    # 2. Trigger midi.port_mode_changed via action undo
    core.emit("midi.port_mode_changed", "BCF2000", "Absolute")
    mock_settings_tab.update_midi_port_mode.assert_called_once_with(
        "BCF2000", "Absolute"
    )


def test_settings_tab_update_midi() -> None:
    """Test SettingsTab updates liststore_midi on port toggle and mode change."""
    # pylint: disable=protected-access
    tab = SettingsTab.__new__(SettingsTab)
    tab.settings = MagicMock()
    tab.settings.get_strv.side_effect = lambda k: ["BCF2000"] if k == "makie" else []

    tab.liststore_midi = Gtk.ListStore(str, bool, str, str)
    tab.liststore_midi.append(["BCF2000", False, "", "BCF2000"])
    tab.liststore_midi.append(["nanoKONTROL", True, "Absolute", "nanoKONTROL"])

    # 1. Test update_midi_port_toggle enabling a port
    tab.update_midi_port_toggle("BCF2000", True)
    assert tab.liststore_midi[0][1] is True
    assert tab.liststore_midi[0][2] == "Relative3 (Makie)"

    # 2. Test update_midi_port_toggle disabling a port
    tab.update_midi_port_toggle("BCF2000", False)
    assert tab.liststore_midi[0][1] is False
    assert tab.liststore_midi[0][2] == ""

    # 3. Test update_midi_port_mode with various mode strings
    tab.update_midi_port_mode("nanoKONTROL", "Relative1")
    assert tab.liststore_midi[1][2] == "Relative1"

    tab.update_midi_port_mode("nanoKONTROL", "mackie")
    assert tab.liststore_midi[1][2] == "Relative3 (Makie)"

    tab.update_midi_port_mode("nanoKONTROL", "relative2")
    assert tab.liststore_midi[1][2] == "Relative2"

    tab.update_midi_port_mode("nanoKONTROL", "absolute")
    assert tab.liststore_midi[1][2] == "Absolute"
