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
"""Unit tests for CueEditor and CueSetTempChannelsAction."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
from olc.core.app import CoreApplication
from olc.cue import CueEditor
from olc.define import MAX_CHANNELS


def test_cue_editor_initialization() -> None:
    """Test that CueEditor initializes with empty overrides."""
    lightshow = MagicMock()
    editor = CueEditor(lightshow)
    assert not editor.has_overrides(1.0, 0)
    levels = editor.get_levels(1.0, 0)
    assert isinstance(levels, np.ndarray)
    assert len(levels) == MAX_CHANNELS
    assert np.all(levels == -1)


def test_cue_editor_set_and_clear() -> None:
    """Test setting temporary level overrides and clearing them."""
    app = MagicMock()
    app.core = app
    lightshow = MagicMock()
    lightshow.app = app
    editor = CueEditor(lightshow)

    editor.set_level(1.5, 0, channel=5, level=150)
    assert editor.has_overrides(1.5, 0)
    assert editor.get_levels(1.5, 0)[4] == 150
    app.emit.assert_called_once_with("cue_editor.changed", 0, 1.5)

    app.emit.reset_mock()
    editor.clear(1.5, 0)
    assert not editor.has_overrides(1.5, 0)
    assert editor.get_levels(1.5, 0)[4] == -1
    app.emit.assert_called_once_with("cue_editor.changed", 0, 1.5)


def test_cue_set_temp_channels_action() -> None:
    """Test CueSetTempChannelsAction and its Undo/Redo integration."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Clean app cues and ensure editor exists
    app.lightshow.cues.clear()

    # Trigger events tracing
    changed_events = []
    app.subscribe(
        "cue_editor.changed", lambda seq, mem: changed_events.append((seq, mem))
    )

    # Execute temp levels set action
    app.action_registry.execute("cue.set_temp_channels", 2.0, 0, {10: 200, 20: 100})
    editor = app.lightshow.cues.cue_editor
    assert editor.has_overrides(2.0, 0)
    assert editor.get_levels(2.0, 0)[9] == 200
    assert editor.get_levels(2.0, 0)[19] == 100
    assert (0, 2.0) in changed_events

    # Undo action
    changed_events.clear()
    app.history.undo()
    assert not editor.has_overrides(2.0, 0)
    assert editor.get_levels(2.0, 0)[9] == -1
    assert editor.get_levels(2.0, 0)[19] == -1
    assert (0, 2.0) in changed_events

    # Redo action
    changed_events.clear()
    app.history.redo()
    assert editor.has_overrides(2.0, 0)
    assert editor.get_levels(2.0, 0)[9] == 200
    assert editor.get_levels(2.0, 0)[19] == 100
    assert (0, 2.0) in changed_events
