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
"""Headless integration tests for MIDI subsystem without GTK window."""
# pylint: disable=protected-access

from __future__ import annotations

from unittest.mock import MagicMock

import mido
import numpy as np
import pytest

from olc.core.app import CoreApplication
from olc.core.backends.midi import Midi
from olc.define import MAX_CHANNELS


def test_midi_headless_execution() -> None:
    """Verify that MIDI notes, CC and pitchwheel execute fully without GUI window."""
    settings = MagicMock()
    settings.get_strv.return_value = []

    core_app = CoreApplication(settings)

    # Set up mock backend for DMX levels
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {
        "user": np.full(MAX_CHANNELS, 50, dtype=np.int16),
        "sequence": np.full(MAX_CHANNELS, 0, dtype=np.int16),
    }
    mock_backend.dmx = mock_dmx
    core_app.backend = mock_backend

    # Mock delegate mimicking headless Application
    app_delegate = MagicMock()
    app_delegate.core = core_app
    app_delegate.settings = settings
    app_delegate.window = None
    app_delegate.virtual_console = None
    app_delegate.tabs = None
    app_delegate.crossfade = core_app.crossfade

    midi = Midi(app_delegate)
    core_app.midi = midi

    # 1. Test MIDI Notes in headless mode (e.g. commandline append '5')
    msg_num = mido.Message("note_on", channel=0, note=0, velocity=127)
    midi.messages.notes._execute_midi_action("number_5", msg_num)
    assert core_app.commandline.get_string() == "5"

    # 2. Test MIDI Jog wheel in headless mode
    core_app.selected_channels = [1]
    msg_wheel = mido.Message("control_change", channel=0, control=60, value=2)
    # relative1 mode for wheel
    settings.get_strv.side_effect = lambda k: ["mock_port"] if k == "relative1" else []
    midi.messages.control_change._function_wheel("mock_port", msg_wheel)
    assert core_app.backend.dmx.levels["user"][0] == 52

    # 3. Test MIDI Fader in headless mode
    fader_bank = core_app.lightshow.fader_bank
    msg_fader = mido.Message("control_change", channel=0, control=0, value=127)
    midi.messages.control_change._function_fader(msg_fader, 1)
    target_fader = fader_bank.get_fader(1)
    assert target_fader.level == 1.0

    # 4. Test Manual Crossfade in headless mode
    midi.xfade._xfade(midi.xfade.fader_out, 180)
    assert core_app.crossfade is not None
    assert core_app.crossfade.scale_a.value_255 == 180
    assert core_app.crossfade.scale_a.get_value() == pytest.approx(180 / 255.0)

    midi.stop()


def test_midi_package_has_no_gtk_dependency() -> None:
    """The MIDI backend must not import GTK/GLib/Gdk/Gio nor olc.gtk3."""
    import pathlib

    import olc.core.backends.midi as midi_pkg

    package_dir = pathlib.Path(midi_pkg.__file__).parent
    for path in package_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "gi.repository" not in text, path.name
        assert "olc.gtk3" not in text, path.name


def test_midi_headless_feedback_and_navigation() -> None:
    """Core events drive MIDI feedback and navigation keys run Core actions."""
    settings = MagicMock()
    settings.get_strv.return_value = []
    core_app = CoreApplication(settings)
    midi = core_app.init_midi()
    assert core_app.midi is midi

    # Feedback: fader level event updates MIDI fader anchor state
    core_app.emit("fader.level_changed", 1, 0.5)
    assert midi.faders.faders[0].value == 0.0

    # Navigation keys use Core actions (no window needed)
    msg = mido.Message("note_on", channel=0, note=0, velocity=127)
    core_app.selected_channels = [5]
    core_app.last_selected_channel = 5
    midi.messages.notes._execute_midi_action("right", msg)
    assert core_app.selected_channels == [6]
    midi.messages.notes._execute_midi_action("left", msg)
    assert core_app.selected_channels == [5]

    # Record/Time keys append to the command line
    midi.messages.notes._execute_midi_action("time", msg)
    assert "TIME" in core_app.commandline.get_string()

    midi.stop()


def test_midi_headless_core_init_and_ports_close() -> None:
    """Verify CoreApplication.init_midi() works headless and closes all ports."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication

    core_app = CoreApplication(None)
    midi = core_app.init_midi()
    assert midi is not None
    assert core_app.midi is midi
    assert midi.ports.settings is None

    # Replace any discovered ports with mocks to verify safe iteration in close()
    port_a = MagicMock()
    port_a.name = "Mock In/Out A"
    port_b = MagicMock()
    port_b.name = "Mock In/Out B"
    if isinstance(midi.ports.ports, list):
        midi.ports.ports = [port_a, port_b]
    else:
        midi.ports.ports = {"Mock A": port_a, "Mock B": port_b}

    midi.ports.close()
    assert len(midi.ports.ports) == 0
    midi.stop()


def test_midi_headless_event_feedback_and_serialization() -> None:
    """Verify Core event feedback to MIDI and to_dict()/from_dict() roundtrip."""
    from unittest.mock import patch

    from olc.core.app import CoreApplication

    core_app = CoreApplication(None)
    midi = core_app.init_midi()
    assert midi is not None

    with (
        patch.object(midi, "button_on") as mock_on,
        patch.object(midi, "button_off") as mock_off,
        patch.object(midi.messages.control_change, "send") as mock_cc_send,
        patch.object(midi.messages.pitchwheel, "send") as mock_pw_send,
        patch.object(midi.xfade.fader_out, "set_state") as mock_out_state,
        patch.object(midi.xfade.fader_in, "set_state") as mock_in_state,
    ):
        core_app.emit("playback.go_started")
        mock_on.assert_called_with("playback.go")

        core_app.emit("playback.transition_completed")
        mock_off.assert_called_with("playback.go")

        mock_on.reset_mock()
        mock_off.reset_mock()
        core_app.emit("playback.pause_triggered", {"active": True})
        mock_on.assert_called_with("playback.pause")
        core_app.emit("playback.pause_triggered", {"active": False})
        mock_off.assert_called_with("playback.pause")

        mock_off.reset_mock()
        core_app.emit("playback.stopped")
        mock_off.assert_any_call("playback.go")
        mock_off.assert_any_call("playback.pause")

        core_app.emit("fader.level_changed", 1, 0.5)
        mock_cc_send.assert_called_with("fader_1", 64)
        mock_pw_send.assert_called_with("fader_1", 0)

        mock_cc_send.reset_mock()
        mock_pw_send.reset_mock()
        core_app.lightshow.fader_bank.get_fader(1).level = 1.0
        core_app.emit("fader.flash_changed", 1, True)
        mock_cc_send.assert_called_with("fader_1", 127)
        mock_pw_send.assert_called_with("fader_1", 8191)

        core_app.emit("playback.xfade_moved", "a", 128)
        mock_out_state.assert_called_with(128)
        core_app.emit("playback.xfade_moved", "b", 64)
        mock_in_state.assert_called_with(64)

    # Serialization roundtrip + legacy key mapping
    midi.messages.notes.notes["time"] = [1, 42]
    midi.messages.notes.cc_notes["playback.go"] = [2, 10]
    midi.messages.control_change.control_change["fader_1"] = [1, 7]
    midi.messages.pitchwheel.pitchwheel["fader_1"] = 0
    exported = midi.to_dict()

    core_app2 = CoreApplication(None)
    midi2 = core_app2.init_midi()
    assert midi2 is not None
    exported["note"]["go"] = [3, 12]
    midi2.from_dict(exported)

    assert midi2.messages.notes.notes["time"] == [1, 42]
    assert midi2.messages.notes.notes["playback.go"] == [3, 12]
    assert midi2.messages.notes.cc_notes["playback.go"] == [2, 10]
    assert midi2.messages.control_change.control_change["fader_1"] == [1, 7]
    assert midi2.messages.pitchwheel.pitchwheel["fader_1"] == 0

    midi.stop()
    midi2.stop()
