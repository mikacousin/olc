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
"""Unit tests for manual value persistence, SneakController, and SNEAK execution."""
# pylint: disable=protected-access, missing-function-docstring

from __future__ import annotations

import typing
from unittest.mock import MagicMock, patch

import pytest

from olc.actions import register_all_actions
from olc.core.app import CoreApplication
from olc.core.parser.executor import CommandExecutor
from olc.core.parser.parser import CommandParser
from olc.cue import Cue
from olc.dmx import Dmx
from olc.step import Step


def _create_test_app(sneak_time: float = 5.0) -> tuple[CoreApplication, Dmx]:
    """Helper to initialize CoreApplication with mock settings and actions."""
    settings = MagicMock()
    settings.get_double.return_value = sneak_time
    app = CoreApplication(settings)
    register_all_actions(app.action_registry)

    # Initialize backend with real Dmx
    mock_backend = MagicMock()
    real_dmx = Dmx(backend=None, lightshow=typing.cast(typing.Any, app.lightshow))
    mock_backend.dmx = real_dmx
    app.backend = mock_backend

    return app, real_dmx


def test_manual_values_persist_across_go_and_sequence_steps() -> None:
    """Ensure manual values (levels['user'] != -1) persist across GO, sequence+,
    and goto without being cleared."""
    app, dmx = _create_test_app()
    seq = app.lightshow.main_playback

    # Set up cues
    cue1 = Cue(1, 1.0)
    cue1.channels = {1: 100}
    cue2 = Cue(1, 2.0)
    cue2.channels = {1: 150}
    seq.insert_step(1, Step(sequence=1, cue=cue1))
    seq.insert_step(2, Step(sequence=1, cue=cue2))
    seq.load_step(1)

    # Set manual value for channel 1 and channel 2
    dmx.levels["user"][0] = 220
    dmx.levels["user"][1] = 180

    # Execute sequence_plus
    seq.sequence_plus()
    assert dmx.levels["user"][0] == 220
    assert dmx.levels["user"][1] == 180

    # Execute sequence_minus
    seq.sequence_minus()
    assert dmx.levels["user"][0] == 220
    assert dmx.levels["user"][1] == 180

    # Execute goto
    seq.goto("2")
    assert dmx.levels["user"][0] == 220
    assert dmx.levels["user"][1] == 180


def test_channel_sneak_immediate() -> None:
    """Test sneaking a channel immediately (duration=0)."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    dmx.levels["user"][0] = 240
    assert dmx.levels["user"][0] == 240

    # 1 SNEAK TIME 0
    cmd = parser.parse("1 SNEAK TIME 0")
    res = executor.execute(cmd)
    assert res.success is True
    assert dmx.levels["user"][0] == -1


def test_channel_sneak_to_sequence_background() -> None:
    """Test that channel sneak targets sequence background level."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    dmx.levels["sequence"][0] = 135.0
    dmx.levels["user"][0] = 255

    # Composite level should be 255 while manual is active
    comp_lvl, comp_col = dmx.get_composite_level(0)
    assert comp_lvl == 255
    assert comp_col == {"red": 0.95, "green": 0.35, "blue": 0.35}

    # Sneak channel 1
    res = executor.execute(parser.parse("1 SNEAK TIME 0"))
    assert res.success is True
    assert dmx.levels["user"][0] == -1

    # Composite level should now revert to sequence background level (135)
    # and color must NOT remain red
    comp_lvl_after, comp_col_after = dmx.get_composite_level(0)
    assert comp_lvl_after == 135
    assert comp_col_after != {"red": 0.95, "green": 0.35, "blue": 0.35}


def test_channel_sneak_to_independent_background() -> None:
    """Test that channel sneak respects active Independent background level."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    # Set up Independent 1 with Channel 1 at level 190
    inde = app.lightshow.independents.independents[0]
    inde.set_levels({1: 190})
    inde.set_level(1.0)
    app.lightshow.independents.update_dmx()
    assert app.lightshow.independents.dmx[0] == 190

    # User overrides channel 1 to FULL (255)
    dmx.levels["user"][0] = 255
    comp_lvl, _ = dmx.get_composite_level(0)
    assert comp_lvl == 255

    # Sneak channel 1
    res = executor.execute(parser.parse("1 SNEAK TIME 0"))
    assert res.success is True
    assert dmx.levels["user"][0] == -1

    # Channel returns to independent level (190)
    comp_lvl_after, _ = dmx.get_composite_level(0)
    assert comp_lvl_after == 190


def test_channel_sneak_fade_interpolation() -> None:
    """Test step-by-step interpolation of SneakController for channels."""
    app, dmx = _create_test_app()
    dmx.levels["user"][0] = 200

    app.sneak_controller.sneak_channels([1], duration=1.0)
    fade = app.sneak_controller._channel_fades[1]
    fade.start_time = 0.0

    # 50% progressed (0.5s)
    with patch("time.monotonic", return_value=0.5):
        cont = app.sneak_controller._on_tick()
        assert cont is True
        assert dmx.levels["user"][0] == pytest.approx(100, abs=1)

    # 100% progressed (1.0s)
    with patch("time.monotonic", return_value=1.0):
        cont = app.sneak_controller._on_tick()
        assert cont is False
        assert dmx.levels["user"][0] == -1


def test_independent_sneak_immediate() -> None:
    """Test sneaking an independent master down to 0 immediately."""
    app, _dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    inde = app.lightshow.independents.independents[1]  # Independent 2
    inde.set_levels({5: 255})
    inde.set_level(0.75)
    app.lightshow.independents.update_dmx()
    assert inde.level == 0.75

    res = executor.execute(parser.parse("INDEPENDENT 2 SNEAK TIME 0"))
    assert res.success is True
    assert inde.level == 0.0


def test_independent_sneak_fade_interpolation() -> None:
    """Test step-by-step interpolation of SneakController for independents."""
    app, _dmx = _create_test_app()
    inde = app.lightshow.independents.independents[2]  # Independent 3
    inde.set_level(1.0)

    app.sneak_controller.sneak_independents([3], duration=2.0)
    fade = app.sneak_controller._inde_fades[3]
    fade.start_time = 0.0

    # 50% progressed (1.0s)
    with patch("time.monotonic", return_value=1.0):
        cont = app.sneak_controller._on_tick()
        assert cont is True
        assert inde.level == pytest.approx(0.5, abs=0.05)

    # 100% progressed (2.0s)
    with patch("time.monotonic", return_value=2.0):
        cont = app.sneak_controller._on_tick()
        assert cont is False
        assert inde.level == 0.0


def test_sneak_all_manual_channels_when_no_selection() -> None:
    """Test that bare 'SNEAK TIME 0' sneaks all currently manual channels."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    dmx.levels["user"][0] = 100
    dmx.levels["user"][1] = 150
    dmx.levels["user"][2] = 200

    res = executor.execute(parser.parse("SNEAK TIME 0"))
    assert res.success is True
    assert dmx.levels["user"][0] == -1
    assert dmx.levels["user"][1] == -1
    assert dmx.levels["user"][2] == -1


def test_sneak_only_selected_channels_when_selection_active() -> None:
    """Test that bare 'SNEAK TIME 0' prioritizes currently active channel selection."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    dmx.levels["user"][0] = 100
    dmx.levels["user"][1] = 150
    dmx.levels["user"][2] = 200

    # Active selection is channels 1 and 2
    app.selected_channels = [1, 2]

    res = executor.execute(parser.parse("SNEAK TIME 0"))
    assert res.success is True
    # Channels 1 and 2 are released
    assert dmx.levels["user"][0] == -1
    assert dmx.levels["user"][1] == -1
    # Channel 3 was NOT selected, so its manual override persists
    assert dmx.levels["user"][2] == 200


def test_default_sneak_time_from_settings() -> None:
    """Verify that SneakController uses sneak-time from GSettings by default."""
    app, dmx = _create_test_app(sneak_time=3.5)
    assert app.sneak_controller.get_default_sneak_time() == 3.5

    dmx.levels["user"][0] = 255
    affected = app.sneak_controller.sneak_channels([1], duration=None)
    assert affected == [1]
    fade = app.sneak_controller._channel_fades[1]
    assert fade.duration == 3.5


def test_record_cue_releases_manual_override_for_current_cue() -> None:
    """Recording or updating the current active cue releases manual values."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)
    seq = app.lightshow.main_playback

    # Set up cue 1 in global cues and active step
    cue1 = Cue(1, 1.0)
    app.lightshow.cues.add(cue1)
    seq.insert_step(1, Step(sequence=1, cue=cue1))
    seq.load_step(1)
    assert seq.position == 1

    # Channel 1 is manual at 210
    dmx.levels["user"][0] = 210

    # UPDATE CUE 1
    res = executor.execute(parser.parse("UPDATE CUE 1"))
    assert res.success is True
    assert dmx.levels["user"][0] == -1
    assert cue1.channels.get(1) == 210


def test_channel_sneak_emits_channels_updated() -> None:
    """Ensure channels.updated is emitted when a channel is sneaked."""
    app, dmx = _create_test_app()
    parser = CommandParser()
    executor = CommandExecutor(app)

    dmx.levels["user"][0] = 150
    events: list[list[int]] = []
    app.subscribe("channels.updated", lambda chs: events.append(list(chs)))

    executor.execute(parser.parse("1 SNEAK TIME 0"))
    assert [1] in events
