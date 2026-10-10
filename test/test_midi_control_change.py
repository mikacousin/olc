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
"""Unit tests for MidiControlChanges and MidiXFade decoupling."""
# pylint: disable=protected-access

from __future__ import annotations

from unittest.mock import MagicMock

import mido

from olc.midi.control_change import MidiControlChanges
from olc.midi.xfade import MidiXFade


def test_control_change_wheel_executes_action() -> None:
    """Test that wheel CC dispatches channel.wheel_adjust action."""
    mock_midi = MagicMock()
    mock_app = MagicMock()
    mock_app.window = None
    mock_app.virtual_console = None

    # Settings returns empty mode lists -> relative1 or mackie
    mock_app.settings.get_strv.return_value = ["test_port"]

    cc = MidiControlChanges(mock_midi, mock_app)

    # Relative1: value 1 -> UP, step 1
    msg = mido.Message("control_change", channel=0, control=60, value=1)
    cc._function_wheel("test_port", msg)

    mock_app.core.action_registry.execute.assert_called_once_with(
        "channel.wheel_adjust", 1, 1
    )


def test_control_change_fader_executes_action() -> None:
    """Test that fader CC dispatches fader.set_level action."""
    mock_midi = MagicMock()
    mock_fader = MagicMock()
    mock_fader.is_valid.return_value = True
    mock_midi.faders.faders = [mock_fader]

    mock_app = MagicMock()
    mock_app.window = None
    mock_app.virtual_console = None
    mock_fader_bank = MagicMock()
    mock_fader_bank.active_page = 1
    mock_target_fader = MagicMock()
    mock_target_fader.level = 0.0
    mock_fader_bank.get_fader.return_value = mock_target_fader
    mock_app.core.lightshow.fader_bank = mock_fader_bank

    cc = MidiControlChanges(mock_midi, mock_app)

    msg = mido.Message("control_change", channel=0, control=0, value=127)
    cc._function_fader(msg, 1)

    mock_app.core.action_registry.execute.assert_called_once_with(
        "fader.set_level", 1, 1, 1.0
    )


def test_midi_xfade_executes_action() -> None:
    """Test that manual crossfade dispatches playback.manual_xfade action."""
    mock_midi = MagicMock()
    mock_app = MagicMock()
    mock_app.window = None
    mock_app.virtual_console = None
    mock_crossfade = MagicMock()
    mock_app.crossfade = mock_crossfade

    xfade = MidiXFade(mock_midi, mock_app)

    xfade._xfade(xfade.fader_out, 200)

    mock_app.core.action_registry.execute.assert_called_once_with(
        "playback.manual_xfade", "a", 200
    )
