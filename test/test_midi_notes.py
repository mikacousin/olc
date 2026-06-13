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
"""Unit tests for MidiNotes CC integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import mido
from olc.files.olc.writer import OlcWriter
from olc.files.parsed_data import ParsedData
from olc.midi.notes import MidiNotes


def test_midi_notes_cc_init() -> None:
    """Test that cc_notes is initialized properly."""
    midi = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi, app)
    # Check that cc_notes is initialized with the same keys as notes, all [0, -1]
    assert "playback.go" in notes.cc_notes
    assert notes.cc_notes["playback.go"] == [0, -1]
    assert notes.notes["playback.go"] == [0, 94]


def test_midi_notes_learn_cc_and_note_mutual_exclusion() -> None:
    """Test learn_cc and learn mutual exclusion behavior."""
    midi = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi, app)

    # 1. Learn CC mapping for playback.go
    msg_cc = mido.Message("control_change", channel=1, control=50, value=127)
    notes.learn_cc(msg_cc, "playback.go")
    assert notes.cc_notes["playback.go"] == [1, 50]
    assert notes.notes["playback.go"] == [0, -1]  # Note mapping cleared

    # 2. Learn Note mapping for playback.go (should clear CC mapping)
    msg_note = mido.Message("note_on", channel=1, note=60, velocity=127)
    notes.learn(msg_note, "playback.go")
    assert notes.notes["playback.go"] == [1, 60]
    assert notes.cc_notes["playback.go"] == [0, -1]  # CC mapping cleared


def test_midi_notes_scan_cc() -> None:
    """Test scan_cc routes CC inputs correctly to simulated note dispatching."""
    midi = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi, app)

    # Map playback.go to CC channel 1, control 50
    msg_learn = mido.Message("control_change", channel=1, control=50, value=127)
    notes.learn_cc(msg_learn, "playback.go")

    # Scan a CC message
    msg_scan = mido.Message("control_change", channel=1, control=50, value=127)
    with patch.object(notes, "_dispatch") as mock_dispatch:
        notes.scan_cc(msg_scan)

        # _dispatch should be called with the action name and a simulated note message
        mock_dispatch.assert_called_once()
        key, simulated_msg = mock_dispatch.call_args[0]
        assert key == "playback.go"
        assert simulated_msg.type == "note_on"
        assert simulated_msg.velocity == 127
        assert simulated_msg.channel == 1


def test_midi_notes_send_cc() -> None:
    """Test that send method sends CC messages when mapped to CC."""
    midi = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi, app)

    # Map playback.go to CC channel 1, control 50
    msg_learn = mido.Message("control_change", channel=1, control=50, value=127)
    notes.learn_cc(msg_learn, "playback.go")

    # Send physical feedback for playback.go (value 127)
    notes.send("playback.go", 127)

    # midi.enqueue should be called with a control_change message
    midi.enqueue.assert_called_once()
    sent_msg = midi.enqueue.call_args[0][0]
    assert sent_msg.type == "control_change"
    assert sent_msg.channel == 1
    assert sent_msg.control == 50
    assert sent_msg.value == 127


def test_midi_notes_writer_and_parsed_data() -> None:
    """Test serialization and deserialization of note_cc mappings."""
    midi = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi, app)

    # Set some CC mapping
    notes.cc_notes["playback.go"] = [1, 55]

    # Mock midi hierarchy for writer
    midi.messages = MagicMock()
    midi.messages.notes = notes
    midi.messages.control_change.control_change = {}
    midi.messages.pitchwheel.pitchwheel = {}

    # Write using OlcWriter
    writer = OlcWriter(MagicMock(), MagicMock(), midi=midi)
    # pylint: disable=protected-access
    writer._midi()

    # Verify note_cc key is written
    assert "note_cc" in writer.data["midi_mapping"]
    assert writer.data["midi_mapping"]["note_cc"]["playback.go"] == [1, 55]

    # Mock load using ParsedData
    parsed = ParsedData(MagicMock(), midi=midi)
    parsed.data["midi"] = {
        "note": {},
        "note_cc": {"playback.go": [1, 55]},
        "control_change": {},
        "pitchwheel": {},
    }

    # Clear target cc_notes first to verify import
    notes.cc_notes["playback.go"] = [0, -1]
    parsed.import_midi()

    assert notes.cc_notes["playback.go"] == [1, 55]


def test_midi_notes_send_cc_prioritized() -> None:
    """Test that CC mappings are prioritized over default Note mappings in send()."""
    midi = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi, app)

    # Set both note and CC mappings active
    notes.notes["playback.go"] = [0, 94]  # Default Note mapping
    notes.cc_notes["playback.go"] = [1, 50]  # Custom CC mapping

    notes.send("playback.go", 127)

    # Assert control_change was queued, not note_on
    midi.enqueue.assert_called_once()
    sent_msg = midi.enqueue.call_args[0][0]
    assert sent_msg.type == "control_change"
    assert sent_msg.channel == 1
    assert sent_msg.control == 50
    assert sent_msg.value == 127
