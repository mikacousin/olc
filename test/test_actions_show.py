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
"""Unit tests for show life cycle actions (show.new, show.open, show.save, etc.)."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import pytest

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


def test_show_open_ascii() -> None:
    """Test show.open with sample ASCII file."""
    settings = MagicMock()
    app = CoreApplication(settings)

    loaded_events: list[str] = []
    app.subscribe("show.loaded", loaded_events.append)

    app.action_registry.execute("show.open", "test/sample.asc")

    assert len(loaded_events) == 1
    assert app.lightshow.basename == "sample.asc"
    assert app.lightshow.modified is False
    assert app.lightshow.patch.outputs[1][47] == [7, 0]
    assert len(app.history.undo_stack) == 0


def test_show_save_and_reopen_olc(tmp_path: pathlib.Path) -> None:
    """Test saving show to OLC format and reopening in a new session."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.lightshow.cues.add(Cue(1, 2.5))
    app.lightshow.groups.add(Group(index=1.0, channels={1: 255, 2: 128}))
    app.action_registry.execute("patch.add_output", 5, 20, 1)

    save_path = str(tmp_path / "test_show.olc")
    saved_events: list[str] = []
    app.subscribe("show.saved", saved_events.append)

    app.action_registry.execute("show.save", save_path)

    assert len(saved_events) == 1
    assert pathlib.Path(save_path).exists()
    assert app.lightshow.modified is False
    assert app.lightshow.basename == "test_show.olc"

    # Re-open in a fresh application instance
    app2 = CoreApplication(settings)
    app2.action_registry.execute("show.open", save_path)

    assert app2.lightshow.basename == "test_show.olc"
    assert app2.lightshow.modified is False
    group = app2.lightshow.groups.get(1.0)
    assert group is not None
    assert group.channels == {1: 255, 2: 128}
    assert app2.lightshow.patch.outputs[1][20] == [5, 0]


def test_show_save_without_path(tmp_path: pathlib.Path) -> None:
    """Test show.save without argument uses existing lightshow.file_path."""
    settings = MagicMock()
    app = CoreApplication(settings)
    save_path = str(tmp_path / "existing.olc")

    # First save with path
    app.action_registry.execute("show.save", save_path)
    assert app.lightshow.file_path == save_path

    # Mark modified
    app.lightshow.set_modified()
    assert app.lightshow.modified is True

    # Save again without arguments
    app.action_registry.execute("show.save")
    assert app.lightshow.modified is False


def test_show_export_ascii(tmp_path: pathlib.Path) -> None:
    """Test exporting show to USITT ASCII format."""
    settings = MagicMock()
    app = CoreApplication(settings)

    export_path = str(tmp_path / "exported.asc")
    exported_events: list[tuple[str, str]] = []
    app.subscribe("show.exported", lambda p, fmt: exported_events.append((p, fmt)))

    app.action_registry.execute("show.export_ascii", export_path)

    assert len(exported_events) == 1
    assert exported_events[0] == (export_path, "ascii")
    assert pathlib.Path(export_path).exists()


def test_show_actions_error_handling() -> None:
    """Test error handling for show persistence actions."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Missing file for show.open
    with pytest.raises(FileNotFoundError):
        app.action_registry.execute("show.open", "/nonexistent/path/file.olc")

    # Empty path for show.open
    with pytest.raises(ValueError):
        app.action_registry.execute("show.open", "")

    # show.save with no path configured
    app.lightshow.file_path = None
    with pytest.raises(ValueError):
        app.action_registry.execute("show.save")

    # show.export_ascii with empty path
    with pytest.raises(ValueError):
        app.action_registry.execute("show.export_ascii", "")

    # show.import with empty path
    with pytest.raises(ValueError):
        app.action_registry.execute("show.import", "")

    # show.import with nonexistent file
    with pytest.raises(FileNotFoundError):
        app.action_registry.execute("show.import", "/nonexistent/path/file.asc")


def test_show_import_ascii_and_undo_redo() -> None:
    """Test show.import action with ASCII file and verify full Undo/Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Initial state
    app.lightshow.groups.add(Group(index=99.0, channels={1: 100}, text="Initial Group"))
    app.lightshow.cues.add(Cue(1, 99.0, channels={1: 50}, text="Initial Cue"))
    app.lightshow.patch.outputs[1][47] = [1, 0]
    app.lightshow.patch.invalidate_cache()
    app.lightshow.set_not_modified()

    imported_events: list[tuple[str, object]] = []
    app.subscribe(
        "show.imported",
        lambda path, opts: imported_events.append((path, opts)),
    )

    # Import sample file
    app.action_registry.execute("show.import", "test/sample.asc")

    assert len(imported_events) == 1
    assert app.lightshow.modified is True
    # In sample file, output 47 is patched to channel 7
    assert app.lightshow.patch.outputs[1][47] == [7, 0]

    # Verify cue from sample file was imported
    assert app.lightshow.cues.get(1.0, 0) is not None

    # Undo
    app.history.undo()
    assert len(imported_events) == 2
    assert app.lightshow.patch.outputs[1][47] == [1, 0]
    assert app.lightshow.groups.get(99.0) is not None
    assert app.lightshow.cues.get(99.0, 1) is not None
    assert app.lightshow.modified is False

    # Redo
    app.history.redo()
    assert len(imported_events) == 3
    assert app.lightshow.patch.outputs[1][47] == [7, 0]
    assert app.lightshow.modified is True


def test_show_import_partial_options() -> None:
    """Test show.import with specific options (ignore patch, replace cues)."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Set initial patch
    app.lightshow.patch.outputs[1][47] = [42, 0]
    app.lightshow.patch.invalidate_cache()

    # Import with patch ignored
    options = {
        "patch": "IGNORE",
        "curves": "IGNORE",
        "groups": "IGNORE",
        "independents": "IGNORE",
        "faders": "IGNORE",
        "midi": "IGNORE",
    }
    app.action_registry.execute("show.import", "test/sample.asc", options)

    # Patch should NOT have changed because of IGNORE
    assert app.lightshow.patch.outputs[1][47] == [42, 0]
    # Cues should have been imported
    assert app.lightshow.cues.get(1.0, 0) is not None
