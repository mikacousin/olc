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
"""Unit tests for KeyboardBinding, MidiBinding, and OscBinding."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.binding import KeyboardBinding, MidiBinding, OscBinding


def test_keyboard_binding() -> None:
    """Test KeyboardBinding properties and send_feedback (no-op)."""
    binding = KeyboardBinding("channel.set_level", "space")
    assert binding.action_name == "channel.set_level"
    assert binding.key_name == "space"
    # Should not raise exception
    binding.send_feedback({"active": True})


def test_midi_binding_note() -> None:
    """Test MidiBinding note-type feedback triggers correct app.midi calls."""
    binding = MidiBinding("playback.go", "note", 1, 60)
    assert binding.action_name == "playback.go"
    assert binding.event_type == "note"
    assert binding.channel == 1
    assert binding.number == 60

    # No app set -> should return early without crash
    binding.send_feedback({"active": True})

    # Set mock app and midi
    mock_app = MagicMock()
    mock_midi = MagicMock()
    mock_app.midi = mock_midi
    binding.app = mock_app

    binding.send_feedback({"active": True})
    mock_midi.button_on.assert_called_once_with("playback.go")
    mock_midi.button_off.assert_not_called()

    mock_midi.reset_mock()
    binding.send_feedback({"active": False})
    mock_midi.button_off.assert_called_once_with("playback.go")
    mock_midi.button_on.assert_not_called()


def test_midi_binding_cc() -> None:
    """Test MidiBinding CC-type feedback triggers correct app.midi calls."""
    binding = MidiBinding("channel.set_level", "cc", 2, 7)
    mock_app = MagicMock()
    mock_midi = MagicMock()
    mock_app.midi = mock_midi
    binding.app = mock_app

    # CC event type with active state
    binding.send_feedback({"active": True, "level": 100})
    mock_midi.send_cc.assert_called_once_with(2, 7, 100)

    # CC event type with inactive state (default to 0)
    mock_midi.reset_mock()
    binding.send_feedback({"active": False})
    mock_midi.send_cc.assert_called_once_with(2, 7, 0)


def test_osc_binding() -> None:
    """Test OscBinding feedback triggers correct engine OSC sends."""
    binding = OscBinding("playback.pause", "/olc/playback/pause")
    assert binding.action_name == "playback.pause"
    assert binding.osc_address == "/olc/playback/pause"

    # No app/engine set -> should return early
    binding.send_feedback({"active": True})

    mock_app = MagicMock()
    mock_engine = MagicMock()
    mock_app.engine = mock_engine
    binding.app = mock_app

    binding.send_feedback({"active": True})
    mock_engine.send_osc.assert_called_once_with("/olc/playback/pause", 1.0)

    mock_engine.reset_mock()
    binding.send_feedback({"active": False})
    mock_engine.send_osc.assert_called_once_with("/olc/playback/pause", 0.0)
