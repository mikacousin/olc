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
"""Comprehensive end-to-end headless integration tests for Open Lighting Console."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import numpy as np

from olc.core.app import CoreApplication
from olc.core.universe_config import Protocol, UniverseMap
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.fader import FaderType
from olc.group import Group


def _create_headless_app() -> tuple[CoreApplication, MagicMock]:
    """Helper to instantiate a fully decoupled CoreApplication for headless tests."""
    settings = MagicMock()
    settings.get_boolean.return_value = False
    settings.get_double.return_value = 0.0
    settings.get_string.return_value = ""
    settings.get_strv.return_value = []
    settings.get_int.return_value = 10

    core_app = CoreApplication(settings)

    # Attach mock backend
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {
        "user": np.full(MAX_CHANNELS, -1, dtype=np.int16),
        "sequence": np.full(MAX_CHANNELS, 0, dtype=np.int16),
        "faders": np.full(MAX_CHANNELS, 0, dtype=np.uint8),
    }
    mock_main_fader = MagicMock()
    mock_dmx.main_fader = mock_main_fader
    mock_backend.dmx = mock_dmx
    core_app.backend = mock_backend

    # Attach mock engine
    mock_engine = MagicMock()
    mock_engine.universe_map = UniverseMap(8)
    core_app.engine = mock_engine

    return core_app, mock_backend


def test_headless_commandline_and_channels_workflow() -> None:
    """Test command line editing and channel level manipulation without GUI."""
    app, backend = _create_headless_app()

    # 1. Command line text editing
    app.action_registry.execute("commandline.append_char", "1")
    app.action_registry.execute("commandline.append_char", "2")
    assert app.commandline.get_string() == "12"
    app.action_registry.execute("commandline.clear")
    assert app.commandline.get_string() == ""
    app.action_registry.execute("commandline.set", "5")
    assert app.commandline.get_string() == "5"

    # 2. Channel direct level
    app.action_registry.execute("channel.set_level", 5, 200)
    assert backend.dmx.levels["user"][4] == 200

    # 3. Multi-channel levels
    app.action_registry.execute("channel.set_multi_levels", {1: 150, 2: 150, 3: 150})
    assert backend.dmx.levels["user"][0] == 150
    assert backend.dmx.levels["user"][1] == 150
    assert backend.dmx.levels["user"][2] == 150

    # 4. Level adjustments (+, -, wheel) on selected channel
    app.selected_channels = [5]
    app.action_registry.execute("channel.level_plus")
    assert backend.dmx.levels["user"][4] == 210

    app.action_registry.execute("channel.level_minus")
    assert backend.dmx.levels["user"][4] == 200

    app.action_registry.execute("channel.wheel_adjust", 1, 1)
    assert backend.dmx.levels["user"][4] == 201

    # 5. Undo / Redo sequence
    app.history.undo()  # Undo wheel
    assert backend.dmx.levels["user"][4] == 200

    app.history.undo()  # Undo level_minus
    assert backend.dmx.levels["user"][4] == 210

    app.history.redo()  # Redo level_minus
    assert backend.dmx.levels["user"][4] == 200


def test_headless_cues_and_playback_workflow() -> None:
    """Test cue management, step insertion, and playback triggers in headless mode."""
    app, _ = _create_headless_app()

    # Set channel levels
    app.action_registry.execute("channel.set_level", 1, 255)
    app.action_registry.execute("channel.set_level", 2, 128)

    # 1. Record Cue
    app.action_registry.execute("playback.record_cue", 1.0, 1)
    assert len(app.lightshow.cues) >= 1

    # 2. Insert step in main playback
    app.action_registry.execute("sequence.insert_step", 1.0, 2, 2.0)
    main_seq = app.lightshow.main_playback
    assert len(main_seq.steps) >= 2

    # 3. Update step times and text
    app.action_registry.execute("step.update_times", 1.0, 2, time_in=4.0, time_out=4.0)
    assert main_seq.steps[2].time_in == 4.0
    assert main_seq.steps[2].time_out == 4.0

    app.action_registry.execute("step.update_text", 1.0, 2, "Intro Look")
    assert main_seq.steps[2].text == "Intro Look"

    # 4. Playback actions (mock playback thread/go)
    mock_playback = MagicMock()
    mock_playback.on_go = True
    mock_playback.position = 0
    mock_playback.steps = []
    mock_playback.last = 0
    app.lightshow.main_playback = mock_playback

    app.action_registry.execute("playback.go")
    mock_playback.do_go.assert_called_once_with(None)

    app.action_registry.execute("playback.pause")
    mock_playback.pause.assert_called_once_with(None, None)

    app.action_registry.execute("playback.go_back")
    mock_playback.go_back.assert_called_once_with(None, None)

    app.action_registry.execute("playback.sequence_plus")
    mock_playback.sequence_plus.assert_called_once()

    app.action_registry.execute("playback.sequence_minus")
    mock_playback.sequence_minus.assert_called_once()


def test_headless_groups_curves_independents_workflow() -> None:
    """Test Group, Curve, and Independent actions and Undo/Redo without GUI."""
    app, _ = _create_headless_app()

    # 1. Groups workflow
    app.action_registry.execute("group.new", 1.0)
    app.action_registry.execute("group.rename", 1.0, "Front")
    app.action_registry.execute("group.update_channels", 1.0, {1: 255, 2: 255})

    group = app.lightshow.groups.get(1.0)
    assert group is not None
    assert group.text == "Front"
    assert group.channels == {1: 255, 2: 255}

    app.action_registry.execute("group.rename", 1.0, "Front Stage")
    assert group.text == "Front Stage"

    app.action_registry.execute("group.delete", 1.0)
    assert app.lightshow.groups.get(1.0) is None

    app.history.undo()  # Restore deleted group
    restored_group = app.lightshow.groups.get(1.0)
    assert restored_group is not None
    assert restored_group.text == "Front Stage"

    # 2. Curves workflow
    app.action_registry.execute("curve.new", "limit", "Custom Limit")
    assert len(app.lightshow.curves.curves) >= 1

    curve_nb = max(app.lightshow.curves.curves.keys())
    app.action_registry.execute("curve.set_limit", curve_nb, 180)
    app.action_registry.execute("curve.delete", curve_nb)
    assert curve_nb not in app.lightshow.curves.curves

    app.history.undo()  # Restore curve
    assert curve_nb in app.lightshow.curves.curves

    # 3. Independents workflow
    app.action_registry.execute("independent.set_level", 1, 0.8)
    assert app.lightshow.independents.independents[0].level == 0.8

    app.action_registry.execute("independent.rename", 1, "House")
    assert app.lightshow.independents.independents[0].text == "House"

    app.action_registry.execute("independent.update_channels", 1, {5: 255})
    assert app.lightshow.independents.independents[0].levels == {5: 255}

    app.history.undo()  # Revert channels
    assert app.lightshow.independents.independents[0].levels != {5: 255}


def test_headless_faders_workflow() -> None:
    """Test Fader assignment, leveling, flashing, and paging without GUI."""
    app, backend = _create_headless_app()

    group = Group(1.0, {1: 200}, "Backlight")
    app.lightshow.groups.add(group)

    # 1. Assign group to fader 1 on page 1
    app.action_registry.execute("fader.assign", 1, 1, FaderType.GROUP, 1.0)
    fader_bank = app.lightshow.fader_bank
    fader = fader_bank.faders[1][1]
    assert fader.contents is group

    # 2. Adjust fader level
    app.action_registry.execute("fader.set_level", 1, 1, 0.7)
    assert fader.level == 0.7

    # 3. Flash fader
    app.action_registry.execute("fader.flash", 1, 1, True)
    assert backend.dmx.set_levels.called

    app.action_registry.execute("fader.flash", 1, 1, False)

    # 4. Set fader page
    app.action_registry.execute("fader.set_page", 2)
    assert fader_bank.active_page == 2

    # 5. Clear fader
    app.action_registry.execute("fader.clear", 1, 1)
    assert fader_bank.faders[1][1].contents is None

    # Undo clear restores fader assignment
    app.history.undo()
    assert fader_bank.faders[1][1].contents is group


def test_headless_show_lifecycle_workflow(tmp_path: pathlib.Path) -> None:
    """Test show creation, save, open, export, import, and Undo without GUI."""
    app, backend = _create_headless_app()

    # Populate show with data
    app.action_registry.execute("channel.set_level", 1, 255)
    cue = Cue(1, 1.0, {1: 255})
    app.lightshow.cues.add(cue)

    save_path = str(tmp_path / "test_show.olc")

    # 1. Save show
    app.action_registry.execute("show.save", save_path)
    assert pathlib.Path(save_path).exists()
    assert app.lightshow.modified is False

    # 2. Create new show
    app.action_registry.execute("show.new")
    assert len(app.lightshow.cues) == 0
    # Main fader must be 100% on new show
    backend.dmx.main_fader.set_level.assert_called_with(1.0)

    # 3. Open saved show
    app.action_registry.execute("show.open", save_path)
    assert len(app.lightshow.cues) >= 1

    # 4. Reset user levels
    app.action_registry.execute("show.reset_user_levels")
    assert np.all(backend.dmx.levels["user"] == -1)

    # 5. Export ASCII show file
    export_path = str(tmp_path / "test_show.asc")
    app.action_registry.execute("show.export_ascii", export_path)
    assert pathlib.Path(export_path).exists()

    # 6. Import show and undo import
    app.action_registry.execute("show.import", export_path)
    assert app.lightshow.modified is True

    # Undo import
    app.history.undo()
    assert len(app.history.redo_stack) >= 1


def test_headless_universes_preferences_and_gui_actions() -> None:
    """Test universe settings, preferences, and GUI actions without display server."""
    app, _ = _create_headless_app()
    assert app.engine is not None

    # 1. Universe configuration actions
    app.action_registry.execute("universe.set_protocol", 1, Protocol.ARTNET, True)
    assert Protocol.ARTNET in app.engine.universe_map[1].protocols

    app.action_registry.execute("universe.set_config", 1, artnet_net=3, artnet_sub=6)
    assert app.engine.universe_map[1].artnet.net == 3
    assert app.engine.universe_map[1].artnet.sub == 6

    # 2. Preferences actions
    app.action_registry.execute("gui.set_theme", dark_theme=False)
    assert app.dark_theme is False

    app.action_registry.execute("gui.set_percent_display", percent=True)
    app.action_registry.execute("gui.set_default_time", default_time=3.5)
    app.action_registry.execute("gui.zoom", target_zoom=1.2)
    assert app.zoom_level == 1.2

    # 3. Headless tab actions
    app.action_registry.execute("gui.tab_open", "curves")
    assert app.tabs.active_tabs["playback"] == "curves"

    app.action_registry.execute("gui.tab_close", "curves")
    assert app.tabs.get_notebook_of_tab("curves") is None

    # 4. Auxiliary window actions (all must emit without crash when headless)
    events: list[str] = []
    app.subscribe("gui.virtual_console_requested", lambda: events.append("vc"))
    app.subscribe("gui.fullscreen_toggle_requested", lambda: events.append("full"))
    app.subscribe("gui.shortcuts_requested", lambda: events.append("shortcuts"))
    app.subscribe("gui.about_requested", lambda: events.append("about"))

    app.action_registry.execute("gui.open_virtual_console")
    app.action_registry.execute("gui.toggle_fullscreen")
    app.action_registry.execute("gui.open_shortcuts")
    app.action_registry.execute("gui.open_about")

    assert events == ["vc", "full", "shortcuts", "about"]
