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
"""Unit tests for show life cycle actions (show.new, show.reset_user_levels)."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.cue import Cue
from olc.fader import FaderType
from olc.group import Group


def test_show_new_resets_show_state() -> None:
    """Test show.new action completely resets state, patch, cues, and clears history."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Setup non-default state
    app.lightshow.cues.add(Cue(1, 3.0))
    app.lightshow.groups.add(Group(index=1.0, channels={1: 255}))
    app.lightshow.file_path = "/tmp/test.olc"
    app.lightshow.basename = "test.olc"
    app.lightshow.set_modified()
    assert app.lightshow.modified is True

    # Add output patch and push action to history
    app.action_registry.execute("patch.add_output", 5, 10, 1)
    assert len(app.history.undo_stack) > 0

    # Surcharge a manual user level
    if app.backend and app.backend.dmx:
        app.backend.dmx.levels["user"][4] = 200

    events: list[str] = []
    app.subscribe("show.new", lambda: events.append("show.new"))

    # Execute show.new
    app.action_registry.execute("show.new")

    # Assertions
    assert "show.new" in events
    assert len(app.lightshow.cues) == 0
    assert len(app.lightshow.groups) == 0
    assert len(app.lightshow.chasers) == 0
    assert app.lightshow.file is None
    assert app.lightshow.file_path is None
    assert app.lightshow.basename == ""
    assert app.lightshow.modified is False
    assert app.lightshow.main_playback.position == 0
    assert app.lightshow.patch.outputs[1][1] == [1, 0]  # Patch 1:1

    if app.backend and app.backend.dmx:
        assert (app.backend.dmx.levels["sequence"] == 0).all()
        assert (app.backend.dmx.levels["user"] == -1).all()

    # History must be cleared
    assert len(app.history.undo_stack) == 0
    assert len(app.history.redo_stack) == 0


def test_show_new_stops_running_chasers() -> None:
    """Test that show.new stops and joins any running chasers."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_chaser = MagicMock()
    mock_chaser.run = True
    mock_thread = MagicMock()
    mock_chaser.thread = mock_thread
    app.lightshow.chasers.append(mock_chaser)

    app.action_registry.execute("show.new")

    assert mock_chaser.run is False
    mock_thread.stop.assert_called_once()
    mock_thread.join.assert_called_once()
    assert len(app.lightshow.chasers) == 0


def test_show_reset_user_levels_and_undo_redo() -> None:
    """Test show.reset_user_levels clears manual channel overrides with Undo/Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    if app.backend and app.backend.dmx:
        app.backend.dmx.levels["user"][0] = 220
        app.backend.dmx.levels["user"][4] = 180

    reset_events: list[str] = []
    app.subscribe("show.user_levels_reset", lambda: reset_events.append("reset"))
    app.subscribe("show.user_levels_restored", lambda: reset_events.append("restored"))

    # Execute reset_user_levels
    app.action_registry.execute("show.reset_user_levels")

    assert "reset" in reset_events
    if app.backend and app.backend.dmx:
        assert app.backend.dmx.levels["user"][0] == -1
        assert app.backend.dmx.levels["user"][4] == -1
        assert (app.backend.dmx.levels["user"] == -1).all()

    # Undo
    app.history.undo()
    assert "restored" in reset_events
    if app.backend and app.backend.dmx:
        assert app.backend.dmx.levels["user"][0] == 220
        assert app.backend.dmx.levels["user"][4] == 180

    # Redo
    app.history.redo()
    if app.backend and app.backend.dmx:
        assert app.backend.dmx.levels["user"][0] == -1
        assert app.backend.dmx.levels["user"][4] == -1


def test_show_new_resets_main_fader_to_100_percent() -> None:
    """Test that show.new resets main_fader to 1.0 even if a FaderMain was assigned."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Assign a fader as MainFader and lower it
    app.action_registry.execute("fader.assign", 1, 1, FaderType.MAIN)
    if app.backend and app.backend.dmx:
        app.backend.dmx.main_fader.set_level(0.4)
        assert app.backend.dmx.main_fader.value == 0.4

    # Execute show.new
    app.action_registry.execute("show.new")

    # Main fader must be 1.0 (100%)
    if app.backend and app.backend.dmx:
        assert app.backend.dmx.main_fader.value == 1.0
