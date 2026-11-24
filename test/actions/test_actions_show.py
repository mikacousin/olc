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
from olc.show.fader import FaderType
from olc.show.group import Group
from test.conftest import DATA_DIR


def test_show_new_resets_show_state() -> None:
    """Test show.new action completely resets state, patch, cues, and clears history."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Setup non-default state
    app.action_registry.execute("sequence.insert_step", 1.0, 1, 3.0)
    app.lightshow.groups.add(Group(index=1.0, channels=[1]))
    app.lightshow.file_path = "/tmp/test.olc"
    app.lightshow.basename = "test.olc"
    app.lightshow.set_modified()
    assert app.lightshow.modified is True

    # Add output patch and push action to history
    app.action_registry.execute("patch.add_outputs", [(5, 10, 1, 0)])
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
    assert app.lightshow.get_cue(3.0, 1) is None
    assert len(app.lightshow.groups) == 0
    assert len(app.lightshow.chasers) == 0
    assert app.lightshow.file is None
    assert app.lightshow.file_path is None
    assert app.lightshow.basename == ""
    assert app.lightshow.modified is False
    assert app.lightshow.main_playback.position == 0
    assert len(app.lightshow.patch.devices) == 0
    assert not app.lightshow.patch.is_patched(1)

    if app.backend and app.backend.dmx:
        assert (app.backend.dmx.levels["sequence"] == 0).all()
        assert (app.backend.dmx.levels["user"] == -1).all()

    # History must be cleared
    assert len(app.history.undo_stack) == 0
    assert len(app.history.redo_stack) == 0


def test_show_new_stops_running_chasers() -> None:
    """Test that show.new stops all secondary sequences and clears them."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_seq = MagicMock()
    app.lightshow.sequences.append(mock_seq)

    app.action_registry.execute("show.new")

    mock_seq.stop.assert_called_once_with()
    assert len(app.lightshow.sequences) == 0


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

    app.action_registry.execute("show.open", str(DATA_DIR / "sample.asc"))

    assert len(loaded_events) == 1
    assert app.lightshow.basename == "sample.asc"
    assert app.lightshow.modified is False
    assert app.lightshow.patch.get_output_info(1, 47) == (7, 0)
    assert len(app.history.undo_stack) == 0


def test_show_save_and_reopen_olc(tmp_path: pathlib.Path) -> None:
    """Test saving show to OLC format and reopening in a new session."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.action_registry.execute("sequence.insert_step", 1.0, 1, 2.5)
    app.lightshow.groups.add(Group(index=1.0, channels=[3, 1, 2]))
    app.action_registry.execute("patch.add_outputs", [(5, 20, 1, 0)])

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
    assert group.channels == [3, 1, 2]
    assert app2.lightshow.patch.get_output_info(1, 20) == (5, 0)


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
    app.lightshow.groups.add(Group(index=99.0, channels=[1], text="Initial Group"))
    app.action_registry.execute("sequence.insert_step", 1.0, 1, 99.0, {1: 50})
    app.lightshow.patch.add_output(1, 47, 1)
    app.lightshow.set_not_modified()

    imported_events: list[tuple[str, object]] = []
    app.subscribe(
        "show.imported",
        lambda path, opts: imported_events.append((path, opts)),
    )

    # Import sample file
    app.action_registry.execute("show.import", str(DATA_DIR / "sample.asc"))

    assert len(imported_events) == 1
    assert app.lightshow.modified is True
    # In sample file, output 47 is patched to channel 7
    assert app.lightshow.patch.get_output_info(1, 47) == (7, 0)

    # Verify cue from sample file was imported (as sequence cue or migrated preset)
    from olc.show.palette import PaletteCategory

    assert (
        app.lightshow.get_cue(1.0, 1) is not None
        or app.lightshow.palettes.get(PaletteCategory.PRESET, 1.0) is not None
    )

    # Undo
    app.history.undo()
    assert len(imported_events) == 2
    assert app.lightshow.patch.get_output_info(1, 47) == (1, 0)
    assert app.lightshow.groups.get(99.0) is not None
    assert app.lightshow.get_cue(99.0, 1) is not None
    assert app.lightshow.modified is False

    # Redo
    app.history.redo()
    assert len(imported_events) == 3
    assert app.lightshow.patch.get_output_info(1, 47) == (7, 0)
    assert app.lightshow.modified is True


def test_show_import_partial_options() -> None:
    """Test show.import with specific options (ignore patch, replace cues)."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Set initial patch
    app.lightshow.patch.add_output(42, 47, 1)

    # Import with patch ignored
    options = {
        "patch": "IGNORE",
        "curves": "IGNORE",
        "groups": "IGNORE",
        "independents": "IGNORE",
        "faders": "IGNORE",
        "midi": "IGNORE",
    }
    app.action_registry.execute("show.import", str(DATA_DIR / "sample.asc"), options)

    # Patch should NOT have changed because of IGNORE
    assert app.lightshow.patch.get_output_info(1, 47) == (42, 0)
    # Cues should have been imported (as sequence cues or migrated presets)
    from olc.show.palette import PaletteCategory

    assert (
        app.lightshow.get_cue(1.0, 1) is not None
        or app.lightshow.palettes.get(PaletteCategory.PRESET, 1.0) is not None
    )


def test_show_workspace_persistence_headless(tmp_path: pathlib.Path) -> None:
    """Test show workspace persistence across show.save and show.open (headless)."""
    settings = MagicMock()
    app = CoreApplication(settings)

    custom_ws = {
        "version": 1,
        "active_pane": "live",
        "panes": {
            "live": {"tabs": ["channels", "groups"], "active_tab": "groups"},
            "playback": {"tabs": ["playback", "cues"], "active_tab": "cues"},
        },
        "tab_settings": {
            "channels": {"view_mode": "Patched"},
            "groups": {"view_mode": "Patched"},
            "cues": {"view_mode": "Active"},
        },
        "virtual_console": {"open": True},
    }
    app.lightshow.workspace = dict(custom_ws)

    # Save to .olc file
    target_file = tmp_path / "custom_workspace.olc"
    app.action_registry.execute("show.save", str(target_file))
    assert target_file.exists()

    # Create new show and verify workspace reset
    app.action_registry.execute("show.new")
    assert app.lightshow.workspace["active_pane"] == "playback"
    assert app.lightshow.workspace["panes"]["live"]["tabs"] == ["channels"]

    # Reopen saved file and verify workspace restored
    app.action_registry.execute("show.open", str(target_file))
    assert app.lightshow.workspace == custom_ws


def test_show_open_legacy_olc_without_workspace(tmp_path: pathlib.Path) -> None:
    """Test opening a legacy OLC file that contains no workspace section."""
    import gzip
    import json

    legacy_data = {
        "application": "olc",
        "version": "0.8.5.beta",
        "patch": {},
        "sequences": {},
        "cues": {},
    }
    target_file = tmp_path / "legacy.olc"
    with gzip.open(str(target_file), "wb") as f:
        f.write(json.dumps(legacy_data).encode("utf-8"))

    settings = MagicMock()
    app = CoreApplication(settings)
    app.action_registry.execute("show.open", str(target_file))

    # Should open without error and maintain valid workspace
    assert isinstance(app.lightshow.workspace, dict)
    assert "version" in app.lightshow.workspace or app.lightshow.workspace == {}


def test_show_set_home_preset_and_undo_redo() -> None:
    """Test show.set_home_preset execution, clearing with 0/None, and Undo/Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    assert app.lightshow.home_preset is None
    assert app.lightshow.modified is False

    events: list[float | None] = []
    app.subscribe("show.home_preset_changed", events.append)

    # Set integer Home Preset 999
    app.action_registry.execute("show.set_home_preset", preset_number=999.0)
    assert app.lightshow.home_preset == pytest.approx(999.0)
    assert app.lightshow.modified is True
    assert events == [999.0]
    assert app.history.undo_stack[-1].get_history_details() == "999"
    assert app.history.undo_stack[-1].get_feedback_state() == {"home_preset": 999.0}

    # Update to decimal preset 999.5
    app.action_registry.execute("show.set_home_preset", preset_number=999.5)
    assert app.lightshow.home_preset == pytest.approx(999.5)
    assert app.history.undo_stack[-1].get_history_details() == "999.5"

    # Clear with 0 -> normalized to None
    app.action_registry.execute("show.set_home_preset", preset_number=0.0)
    assert app.lightshow.home_preset is None
    assert events[-1] is None

    # No-op when setting same value should not pollute undo stack
    stack_len = len(app.history.undo_stack)
    app.action_registry.execute("show.set_home_preset", preset_number=None)
    assert len(app.history.undo_stack) == stack_len

    # Undo back through 999.5 -> 999.0 -> None (also restores unmodified flag)
    app.history.undo()
    assert app.lightshow.home_preset == pytest.approx(999.5)
    app.history.undo()
    assert app.lightshow.home_preset == pytest.approx(999.0)
    app.history.undo()
    assert app.lightshow.home_preset is None
    assert app.lightshow.modified is False

    # Redo back to 999.0
    app.history.redo()
    assert app.lightshow.home_preset == pytest.approx(999.0)
    assert app.lightshow.modified is True


def test_show_new_and_open_reset_home_preset_and_title(tmp_path: pathlib.Path) -> None:
    """Test show.new, show.open, and show.import snapshot reset/preserve metadata."""
    settings = MagicMock()
    app = CoreApplication(settings)

    hp_events: list[float | None] = []
    app.subscribe("show.home_preset_changed", hp_events.append)

    app.lightshow.title = "Existing Title"
    app.lightshow.home_preset = 999.0
    app.action_registry.execute("show.new")

    assert app.lightshow.title == ""
    assert app.lightshow.home_preset is None
    assert hp_events == [None]

    # Opening an ASCII file without $$HOMEPRESET resets prior home_preset and title
    app.lightshow.title = "Previous Show"
    app.lightshow.home_preset = 888.0
    app.action_registry.execute("show.open", str(DATA_DIR / "sample.asc"))
    assert app.lightshow.title == ""
    assert app.lightshow.home_preset is None

    # Import snapshot preserves title/home_preset across Undo
    app.lightshow.title = "Saved Title"
    app.lightshow.home_preset = 777.0
    asc_file = tmp_path / "override.asc"
    asc_file.write_text("IDENT 3:0\n$$TITLE Imported\n$$HOMEPRESET 123\nENDDATA\n")

    app.action_registry.execute("show.import", str(asc_file))
    assert app.lightshow.title == "Imported"
    assert app.lightshow.home_preset == pytest.approx(123.0)

    app.history.undo()
    assert app.lightshow.title == "Saved Title"
    assert app.lightshow.home_preset == pytest.approx(777.0)
