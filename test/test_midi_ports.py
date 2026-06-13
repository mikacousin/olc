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
"""Unit tests for MidiIO receive_callback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import mido
from olc.midi.ports import MidiIO


@patch("olc.midi.ports.mido.open_ioport")
def test_midi_io_receive_callback_learning(_mock_open_ioport: MagicMock) -> None:
    """Test that receive_callback schedules learning.

    Also checks it does not scan actions if learning is active.
    """
    mock_midi = MagicMock()
    mock_midi.learning = "playback.go"

    # Instantiate MidiIO with patched open_ioport
    midi_io = MidiIO(mock_midi, name="TestPort")

    # Create a dummy MIDI message
    msg = mido.Message("control_change", channel=0, control=50, value=127)

    with patch("olc.midi.ports.GLib.idle_add") as mock_idle_add:
        midi_io.receive_callback(msg)

        # Should schedule learning on GLib main loop
        mock_idle_add.assert_called_once_with(mock_midi.learn, msg)

    # Verify that no action scan was performed
    mock_midi.messages.notes.scan.assert_not_called()
    mock_midi.messages.notes.scan_cc.assert_not_called()
    mock_midi.messages.control_change.scan.assert_not_called()


@patch("olc.midi.ports.mido.open_ioport")
def test_midi_io_receive_callback_normal(_mock_open_ioport: MagicMock) -> None:
    """Test that receive_callback scans actions and does not learn if learning is
    inactive."""
    mock_midi = MagicMock()
    mock_midi.learning = ""

    # Instantiate MidiIO with patched open_ioport
    midi_io = MidiIO(mock_midi, name="TestPort")

    # Create a dummy MIDI CC message
    msg = mido.Message("control_change", channel=0, control=50, value=127)

    with patch("olc.midi.ports.GLib.idle_add") as mock_idle_add:
        midi_io.receive_callback(msg)

        # Should not schedule learning
        mock_idle_add.assert_not_called()

    # Verify that action scan was performed
    mock_midi.messages.notes.scan_cc.assert_called_once_with(msg)
    mock_midi.messages.control_change.scan.assert_called_once_with("TestPort", msg)
