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
"""Headless unit tests for Lot 4: Flexi state, GUI channel actions, MIDI & OSC."""

# pylint: disable=protected-access, missing-function-docstring

from __future__ import annotations

import typing
from types import SimpleNamespace
from unittest.mock import MagicMock

import mido
import pytest

from olc.actions import register_all_actions
from olc.controllers.midi import Midi
from olc.controllers.midi.notes import MidiNotes
from olc.controllers.osc.delegate import OSCDelegate
from olc.controllers.osc.oscquery import (
    ACCESS_WRITE_ONLY,
    build_oscquery_tree,
    find_node_by_path,
)
from olc.core.app import CoreApplication
from olc.core.live_state import LiveParameterState


def _make_app() -> CoreApplication:
    settings = MagicMock()
    settings.get_double.return_value = 2.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    register_all_actions(app.action_registry)
    return app


def test_live_parameter_state_is_channel_manual() -> None:
    """Verify LiveParameterState.is_channel_manual tracks params and palette refs."""
    state = LiveParameterState()
    assert state.is_channel_manual(1) is False

    state.mark_manual_params(1, ["pan"])
    assert state.is_channel_manual(1) is True
    assert state.is_channel_manual(2) is False

    state.clear_params(1, ["pan"])
    assert state.is_channel_manual(1) is False

    state.set_palette_ref(3, "color", ("color", 2.0), mark_manual=False)
    assert state.is_channel_manual(3) is True

    state.clear_channel(3)
    assert state.is_channel_manual(3) is False


@pytest.mark.parametrize(
    ("action_name", "event_name", "arg", "expected_payload"),
    [
        ("gui.channels_format", "gui.channels_format_requested", None, None),
        ("gui.channels_format", "gui.channels_format_requested", "table", "Table"),
        (
            "gui.channels_format",
            "gui.channels_format_requested",
            "summary+",
            "Summary+",
        ),
        ("gui.channels_data", "gui.channels_data_requested", None, None),
        ("gui.channels_data", "gui.channels_data_requested", "TOGGLE", "toggle"),
        ("gui.channels_data", "gui.channels_data_requested", "Cycle", "cycle"),
        ("gui.channels_data", "gui.channels_data_requested", "percent", "Percent"),
        ("gui.channels_data", "gui.channels_data_requested", "dmx", "DMX"),
        ("gui.channels_data", "gui.channels_data_requested", "label", "Label"),
        ("gui.channels_labels", "gui.channels_labels_requested", None, None),
        ("gui.channels_labels", "gui.channels_labels_requested", False, False),
        ("gui.channels_labels", "gui.channels_labels_requested", True, True),
        ("gui.channels_flexi", "gui.channels_flexi_requested", None, None),
        ("gui.channels_flexi", "gui.channels_flexi_requested", "devices", "Devices"),
        ("gui.channels_flexi", "gui.channels_flexi_requested", "SELECTED", "Selected"),
        ("gui.channels_flexi", "gui.channels_flexi_requested", "manual", "Manual"),
    ],
)
def test_gui_channels_actions_emit_normalized_events(
    action_name: str,
    event_name: str,
    arg: object,
    expected_payload: object,
) -> None:
    """Verify Format, Data, Labels, and Flexi core actions emit clean events."""
    app = _make_app()
    captured: list[object] = []
    app.subscribe(event_name, captured.append)

    if arg is None:
        app.action_registry.execute(action_name)
    else:
        app.action_registry.execute(action_name, arg)

    assert captured == [expected_payload]


def test_gui_channels_actions_ignore_invalid_arguments() -> None:
    """Unknown format/readout/flexi names should not emit invalid UI requests."""
    app = _make_app()
    captured: list[tuple[str, object]] = []
    for ev_name in (
        "gui.channels_format_requested",
        "gui.channels_data_requested",
        "gui.channels_flexi_requested",
    ):
        app.subscribe(
            ev_name, lambda payload, ev=ev_name: captured.append((ev, payload))
        )

    app.action_registry.execute("gui.channels_format", "bogus")
    app.action_registry.execute("gui.channels_data", "bogus")
    app.action_registry.execute("gui.channels_flexi", "bogus")

    assert captured == []


def test_midi_learn_dispatch_and_persistence_for_lot4_actions() -> None:
    """Verify MIDI notes, CC, learn, and dict serialization for channel controls."""
    midi_stub = MagicMock()
    app = MagicMock()
    notes = MidiNotes(midi_stub, app)

    action_widgets = {
        "gui.channels_format": ("channels_format", 70),
        "gui.channels_data": ("channels_data", 71),
        "gui.channels_labels": ("channels_labels", 72),
        "gui.channels_flexi": ("channels_flexi", 73),
    }

    for action_name, (vc_widget, note_num) in action_widgets.items():
        assert notes.notes[action_name] == [0, -1]
        assert notes.cc_notes[action_name] == [0, -1]

        # Note learn + scan note_on / note_off
        learn_msg = mido.Message("note_on", channel=2, note=note_num, velocity=127)
        notes.learn(learn_msg, action_name)
        assert notes.notes[action_name] == [2, note_num]

        app.action_registry.execute.reset_mock()
        app.emit.reset_mock()
        notes.scan(mido.Message("note_on", channel=2, note=note_num, velocity=127))
        app.emit.assert_any_call("button.pressed", vc_widget, True)
        app.action_registry.execute.assert_called_once_with(action_name)

        app.action_registry.execute.reset_mock()
        notes.scan(mido.Message("note_on", channel=2, note=note_num, velocity=0))
        app.emit.assert_any_call("button.pressed", vc_widget, False)
        app.action_registry.execute.assert_not_called()

    # Verify CC learn + dispatch + round-trip serialization on Flexi
    cc_msg = mido.Message("control_change", channel=3, control=41, value=127)
    notes.learn_cc(cc_msg, "gui.channels_flexi")
    assert notes.cc_notes["gui.channels_flexi"] == [3, 41]
    assert notes.notes["gui.channels_flexi"] == [0, -1]

    app.action_registry.execute.reset_mock()
    notes.scan_cc(mido.Message("control_change", channel=3, control=41, value=127))
    app.action_registry.execute.assert_called_once_with("gui.channels_flexi")

    # Test Midi.to_dict / Midi.from_dict serialization round-trip
    facade_a = SimpleNamespace(
        messages=SimpleNamespace(
            notes=notes,
            control_change=SimpleNamespace(control_change={}),
            pitchwheel=SimpleNamespace(pitchwheel={}),
        )
    )
    saved = Midi.to_dict(typing.cast(Midi, facade_a))

    restored_notes = MidiNotes(midi_stub, app)
    facade_b = SimpleNamespace(
        messages=SimpleNamespace(
            notes=restored_notes,
            control_change=SimpleNamespace(control_change={}),
            pitchwheel=SimpleNamespace(pitchwheel={}),
        )
    )
    Midi.from_dict(typing.cast(Midi, facade_b), saved)

    assert restored_notes.notes["gui.channels_format"] == [2, 70]
    assert restored_notes.notes["gui.channels_data"] == [2, 71]
    assert restored_notes.notes["gui.channels_labels"] == [2, 72]
    assert restored_notes.cc_notes["gui.channels_flexi"] == [3, 41]


def test_osc_routes_and_oscquery_for_lot4_controls() -> None:
    """Verify OSC routes and OSCQuery nodes for Format, Data, Labels, and Flexi."""
    app = _make_app()
    mock_exec = MagicMock()
    app.action_registry.execute = mock_exec  # type: ignore[method-assign]
    delegate = OSCDelegate(app)

    # /olc/channels/format
    delegate._channels_format("/olc/channels/format", [])
    mock_exec.assert_called_with("gui.channels_format")
    mock_exec.reset_mock()
    delegate._channels_format("/olc/channels/format", [0])  # release ignored
    mock_exec.assert_not_called()
    delegate._channels_format("/olc/channels/format", ["Table"])
    mock_exec.assert_called_with("gui.channels_format", "Table")

    # /olc/channels/data & /olc/channels/readout
    mock_exec.reset_mock()
    delegate._channels_data("/olc/channels/data", [1])
    mock_exec.assert_called_with("gui.channels_data")
    mock_exec.reset_mock()
    delegate._channels_data("/olc/channels/readout", ["Percent"])
    mock_exec.assert_called_with("gui.channels_data", "Percent")
    mock_exec.reset_mock()
    delegate._channels_data("/olc/channels/data", ["cycle"])
    mock_exec.assert_called_with("gui.channels_data", "cycle")

    # /olc/channels/labels & /olc/channels/labels/toggle
    mock_exec.reset_mock()
    delegate._channels_labels("/olc/channels/labels", [])
    mock_exec.assert_called_with("gui.channels_labels")
    mock_exec.reset_mock()
    delegate._channels_labels("/olc/channels/labels", ["toggle"])
    mock_exec.assert_called_with("gui.channels_labels")
    mock_exec.reset_mock()
    delegate._channels_labels("/olc/channels/labels", [0])
    mock_exec.assert_called_with("gui.channels_labels", False)
    mock_exec.reset_mock()
    delegate._channels_labels("/olc/channels/labels", [1])
    mock_exec.assert_called_with("gui.channels_labels", True)
    mock_exec.reset_mock()
    delegate._channels_labels_toggle("/olc/channels/labels/toggle", [1])
    mock_exec.assert_called_with("gui.channels_labels")

    # /olc/channels/flexi
    mock_exec.reset_mock()
    delegate._channels_flexi("/olc/channels/flexi", [1])
    mock_exec.assert_called_with("gui.channels_flexi")
    mock_exec.reset_mock()
    delegate._channels_flexi("/olc/channels/flexi", [0])
    mock_exec.assert_not_called()
    delegate._channels_flexi("/olc/channels/flexi", ["Devices"])
    mock_exec.assert_called_with("gui.channels_flexi", "Devices")

    # OSCQuery introspection tree
    tree = build_oscquery_tree(osc_port=9000)
    for path in (
        "/olc/channels/format",
        "/olc/channels/data",
        "/olc/channels/labels",
        "/olc/channels/flexi",
    ):
        node = find_node_by_path(tree, path)
        assert node is not None
        assert node["ACCESS"] == ACCESS_WRITE_ONLY
