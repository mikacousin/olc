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
"""Unit tests for CommandExecutor."""
# pylint: disable=import-outside-toplevel, protected-access, too-many-locals, missing-function-docstring

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.core.parser.ast_nodes import SelectOnlyCommandNode
from olc.core.parser.executor import CommandExecutor
from olc.core.parser.parser import CommandParser


def test_executor_resolve_selection() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    executor = CommandExecutor(app)
    parser = CommandParser()

    node1 = parser.parse("1 THRU 5")
    assert isinstance(node1, SelectOnlyCommandNode)
    assert executor.resolve_selection(node1.selection) == [1, 2, 3, 4, 5]

    node2 = parser.parse("1 THRU 10 - 4 - 6")
    assert isinstance(node2, SelectOnlyCommandNode)
    assert executor.resolve_selection(node2.selection) == [1, 2, 3, 5, 7, 8, 9, 10]

    node3 = parser.parse("1 THRU 10 ODD")
    assert isinstance(node3, SelectOnlyCommandNode)
    assert executor.resolve_selection(node3.selection) == [1, 3, 5, 7, 9]

    node4 = parser.parse("1 THRU 10 EVEN")
    assert isinstance(node4, SelectOnlyCommandNode)
    assert executor.resolve_selection(node4.selection) == [2, 4, 6, 8, 10]


def test_executor_select_only() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    executor = CommandExecutor(app)
    parser = CommandParser()

    cmd = parser.parse("1 THRU 4")
    res = executor.execute(cmd)

    assert res.success
    assert app.selected_channels == [1, 2, 3, 4]
    assert app.last_selected_channel == 4


def test_executor_intensity_absolute_and_relative() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    executor = CommandExecutor(app)
    parser = CommandParser()

    # 1 THRU 3 AT 80
    cmd1 = parser.parse("1 THRU 3 AT 80")
    res1 = executor.execute(cmd1)
    assert res1.success
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 0.8

    # AT +10 (relative on active selection)
    cmd2 = parser.parse("AT + 10")
    res2 = executor.execute(cmd2)
    assert res2.success
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 0.9

    # AT OUT
    cmd3 = parser.parse("AT OUT")
    res3 = executor.execute(cmd3)
    assert res3.success
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 0.0


def test_executor_record_and_goto_cue() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    executor = CommandExecutor(app)
    parser = CommandParser()

    # Turn on channels 1 and 2
    executor.execute(parser.parse("1 + 2 AT FULL"))

    # RECORD CUE 1 TIME 3 / 2
    cmd_rec = parser.parse("RECORD CUE 1 TIME 3 / 2 BLOCK")
    res_rec = executor.execute(cmd_rec)
    assert res_rec.success

    cue = app.lightshow.cues.get(1.0, 1)
    assert cue is not None
    assert cue.is_block is True
    assert cue.channels[1] == 1.0
    assert cue.channels[2] == 1.0

    step = next(
        (s for s in app.lightshow.main_playback.steps if s.cue and s.cue.number == 1.0),
        None,
    )
    assert step is not None
    assert step.time_in == 3.0
    assert step.time_out == 2.0

    # GOTO CUE 1
    cmd_goto = parser.parse("GOTO CUE 1")
    res_goto = executor.execute(cmd_goto)
    assert res_goto.success


def test_executor_all_selection_includes_virtual_dimmer_devices() -> None:
    """Test ALL selection includes both dimmer channels and virtual-dimmer devices."""
    import pytest

    from olc.devices.builtin import create_rgbw_definition

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [-1.0] * 512, "sequence": [0.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    patch = app.lightshow.patch
    patch.patch_empty()
    patch.patch_dimmer(channel=1, universe=1, address=1)
    rgbw_dev = patch.patch_device(
        device_id=20,
        fixture_def=create_rgbw_definition(),
        universe=1,
        address=10,
    )

    executor = CommandExecutor(app)
    parser = CommandParser()

    res = executor.execute(parser.parse("ALL AT 50"))
    assert res.success is True
    assert res.affected_channels == [1, 20]
    assert rgbw_dev.intensity_percent == pytest.approx(50.0, abs=0.5)


def test_executor_gobo_iris_and_update_cue() -> None:
    """Test GOBO, IRIS, and all physical attributes in RECORD CUE and UPDATE CUE."""
    import pytest

    from olc.devices.device import ChannelRange, ChannelType, FixtureType
    from olc.devices.fixture import (
        ChannelDefinition,
        DmxModeDefinition,
        FixtureDefinition,
    )

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [-1.0] * 512, "sequence": [0.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    mode = DmxModeDefinition(
        name="Full",
        channel_defs=[
            ChannelDefinition(ChannelType.INTENSITY, offset=0),
            ChannelDefinition(
                ChannelType.PAN,
                offset=1,
                fine_offset=2,
                physical_min=-270.0,
                physical_max=270.0,
            ),
            ChannelDefinition(
                ChannelType.TILT,
                offset=3,
                fine_offset=4,
                physical_min=-135.0,
                physical_max=135.0,
            ),
            ChannelDefinition(
                ChannelType.ZOOM, offset=5, physical_min=5.0, physical_max=50.0
            ),
            ChannelDefinition(
                ChannelType.FOCUS, offset=6, physical_min=1.0, physical_max=20.0
            ),
            ChannelDefinition(
                ChannelType.STROBE, offset=7, physical_min=0.0, physical_max=25.0
            ),
            ChannelDefinition(
                ChannelType.COLOR_TEMP,
                offset=8,
                physical_min=2700.0,
                physical_max=6500.0,
            ),
            ChannelDefinition(
                ChannelType.IRIS, offset=9, physical_min=0.0, physical_max=100.0
            ),
            ChannelDefinition(
                ChannelType.GOBO_WHEEL,
                offset=10,
                ranges=[
                    ChannelRange("Open", ChannelType.GOBO_WHEEL, 0, 15),
                    ChannelRange("Dots", ChannelType.GOBO_WHEEL, 16, 50),
                    ChannelRange("Stars", ChannelType.GOBO_WHEEL, 51, 100),
                ],
            ),
            ChannelDefinition(ChannelType.RED, offset=11),
            ChannelDefinition(ChannelType.GREEN, offset=12),
            ChannelDefinition(ChannelType.BLUE, offset=13),
        ],
    )
    fdef = FixtureDefinition(
        manufacturer="Test",
        model="FullSpot",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[mode],
    )

    patch = app.lightshow.patch
    patch.patch_empty()
    dev = patch.patch_device(device_id=1, fixture_def=fdef, universe=1, address=1)

    executor = CommandExecutor(app)
    parser = CommandParser()

    cmd = (
        "1 AT 80 PAN 45 TILT -30 ZOOM 25 FOCUS 10 "
        "STROBE 12 CCT 4600 IRIS 60 GOBO 2 COLOR #00FF80"
    )
    res = executor.execute(parser.parse(cmd))
    assert res.success is True
    assert dev.gobo == "Dots"
    assert dev.iris == pytest.approx(60.0, abs=0.5)

    # Record Cue 1
    res_rec = executor.execute(parser.parse("RECORD CUE 1"))
    assert res_rec.success is True
    cue1 = app.lightshow.cues.get(1.0, 1)
    assert cue1 is not None
    dvals = cue1.device_values[1]
    assert dvals["pan"] == pytest.approx(45.0, abs=0.1)
    assert dvals["tilt"] == pytest.approx(-30.0, abs=0.1)
    assert dvals["zoom"] == pytest.approx(25.0, abs=0.5)
    assert dvals["focus"] == pytest.approx(10.0, abs=0.2)
    assert dvals["strobe"] == pytest.approx(12.0, abs=0.2)
    assert dvals["cct"] == pytest.approx(4600.0, abs=20.0)
    assert dvals["iris"] == pytest.approx(60.0, abs=0.5)
    assert dvals["gobo"] == "Dots"
    assert dvals["color"] == "#00FF80"

    # Modify Pan and Gobo by name and UPDATE CUE 1
    executor.execute(parser.parse('1 PAN 90 GOBO "Stars"'))
    res_upd = executor.execute(parser.parse("UPDATE CUE 1"))
    assert res_upd.success is True
    assert cue1.device_values[1]["pan"] == pytest.approx(90.0, abs=0.1)
    assert cue1.device_values[1]["gobo"] == "Stars"


def test_sequence_plus_minus_and_ltp_interpolation() -> None:
    """Test sequence_plus/minus tracking resolution and continuous LTP interpolation."""
    import numpy as np
    import pytest

    from olc.devices.builtin import create_moving_head_definition
    from olc.show.cue import Cue
    from olc.show.sequence import _capture_device_states, _interpolate_device_states
    from olc.show.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {
        "user": np.full(512, -1.0, dtype=np.float64),
        "sequence": np.zeros(512, dtype=np.float64),
    }
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    patch = app.lightshow.patch
    patch.patch_empty()
    spot = patch.patch_device(
        device_id=1,
        fixture_def=create_moving_head_definition(),
        universe=1,
        address=1,
    )

    seq = app.lightshow.main_playback
    seq.tracking_mode = True
    cue1 = Cue(0, 1.0, channels={1: 0.8}, device_values={1: {"pan": 0.0, "tilt": 0.0}})
    cue2 = Cue(0, 2.0, channels={}, device_values={1: {"pan": 100.0, "tilt": -50.0}})
    app.lightshow.cues.add(cue1)
    app.lightshow.cues.add(cue2)
    seq.insert_step(1, Step(1, cue=cue1))
    seq.insert_step(2, Step(1, cue=cue2))

    # Step+ to cue 1, then Step+ to cue 2
    seq.sequence_plus()
    assert seq.position == 1
    assert spot.pan_degrees == pytest.approx(0.0, abs=0.1)

    seq.sequence_plus()
    assert seq.position == 2
    # Intensity 0.8 tracked from cue 1, pan=100 applied from cue 2
    assert mock_dmx.levels["sequence"][0] == 0.8
    assert spot.pan_degrees == pytest.approx(100.0, abs=0.1)
    assert spot.tilt_degrees == pytest.approx(-50.0, abs=0.1)

    # Step- back to cue 1
    seq.sequence_minus()
    assert seq.position == 1
    assert spot.pan_degrees == pytest.approx(0.0, abs=0.1)

    # Continuous LTP interpolation at 50% progress between Cue 1 and Cue 2
    start_states = _capture_device_states(patch)
    _interpolate_device_states(
        patch,
        start_states,
        {1: {"pan": 100.0, "tilt": -50.0}},
        0.5,
    )
    assert spot.pan_degrees == pytest.approx(50.0, abs=0.1)
    assert spot.tilt_degrees == pytest.approx(-25.0, abs=0.1)


def test_executor_record_cue_preserves_sentinel_and_sorted_order() -> None:
    """Verify RECORD CUE inserts steps before the sentinel step in sorted order."""
    import pytest

    from olc.devices.builtin import create_rgb_definition

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [-1.0] * 512, "sequence": [0.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    patch = app.lightshow.patch
    patch.patch_empty()
    led = patch.patch_device(1, create_rgb_definition(), 1, 1)

    seq = app.lightshow.main_playback
    # Fresh sequence has [Step(Cue 0), Step(Cue 0)]
    assert len(seq.steps) == 2
    assert seq.steps[0].cue is not None and seq.steps[0].cue.number == 0.0
    assert seq.steps[-1].cue is not None and seq.steps[-1].cue.number == 0.0

    inserted_events: list[tuple[float, int]] = []
    updated_events: list[tuple[float, int]] = []
    app.subscribe("step.inserted", lambda s, idx: inserted_events.append((s, idx)))
    app.subscribe("step.updated", lambda s, idx: updated_events.append((s, idx)))

    executor = CommandExecutor(app)
    parser = CommandParser()

    # Set LED (Virtual Dimmer) to 100% Red and record Cue 5
    executor.execute(parser.parse("1 AT 100 COLOR RED"))
    assert led.intensity == pytest.approx(1.0)
    executor.execute(parser.parse("RECORD CUE 5 TIME 3"))

    # Cue 5 must be at steps[1], and sentinel Cue 0 must remain at steps[-1] (steps[2])
    assert len(seq.steps) == 3
    assert seq.steps[0].cue is not None and seq.steps[0].cue.number == 0.0
    assert seq.steps[1].cue is not None and seq.steps[1].cue.number == 5.0
    assert seq.steps[2].cue is not None and seq.steps[2].cue.number == 0.0
    assert inserted_events == [(1.0, 1)]
    assert seq.steps[1].cue.device_values[1]["intensity"] == pytest.approx(1.0)
    assert seq.steps[1].cue.channels[1] == 1.0

    # Record Cue 2 -> inserted at steps[1] before Cue 5 (moves to steps[2])
    executor.execute(parser.parse("1 AT 50 COLOR BLUE"))
    executor.execute(parser.parse("RECORD CUE 2 TIME 2"))

    assert len(seq.steps) == 4
    assert [s.cue.number for s in seq.steps if s.cue is not None] == [
        0.0,
        2.0,
        5.0,
        0.0,
    ]
    assert inserted_events == [(1.0, 1), (1.0, 1)]

    # Re-record Cue 5 with new time -> updates existing step at index 2
    executor.execute(parser.parse("RECORD CUE 5 TIME 4"))
    assert len(seq.steps) == 4
    assert seq.steps[2].time_in == 4.0
    assert updated_events == [(1.0, 2)]


def test_executor_noun_first_ifcb_and_goto_time_override() -> None:
    """Noun-first CUE commands, IFCB family timings, and GOTO TIME 0."""
    import numpy as np
    import pytest

    from olc.devices.builtin import create_rgb_definition

    app = CoreApplication(MagicMock())
    mock_backend = MagicMock()
    mock_backend.dmx.levels = {
        "user": np.full(512, -1.0, dtype=np.float64),
        "sequence": np.zeros(512, dtype=np.float64),
    }
    app.backend = mock_backend

    patch = app.lightshow.patch
    patch.patch_empty()
    led = patch.patch_device(1, create_rgb_definition(), 1, 1)

    seq = app.lightshow.main_playback
    executor = CommandExecutor(app)
    parser = CommandParser()

    # Record Cue 1 with IFCB timings using noun-first syntax
    executor.execute(parser.parse("1 AT 100 COLOR RED"))
    executor.execute(
        parser.parse("CUE 1 RECORD TIME 3 POSITION 1.5 DELAY 0.5 COLOR 4 BEAM 2")
    )

    step1 = seq.steps[1]
    assert step1.time_in == pytest.approx(3.0)
    assert step1.time_position == pytest.approx(1.5)
    assert step1.delay_position == pytest.approx(0.5)
    assert step1.time_color == pytest.approx(4.0)
    assert step1.time_beam == pytest.approx(2.0)
    assert step1.total_time == pytest.approx(4.0)

    # Record Cue 2 with 50% Green
    executor.execute(parser.parse("1 AT 50 COLOR GREEN"))
    executor.execute(parser.parse("CUE 2 RECORD TIME 5"))

    # Block / Unblock via noun-first syntax
    executor.execute(parser.parse("CUE 2 BLOCK"))
    assert step1.cue is not None
    cue2 = seq.steps[2].cue
    assert cue2 is not None and cue2.is_block is True
    executor.execute(parser.parse("CUE 2 UNBLOCK"))
    assert cue2.is_block is False

    # GOTO CUE 1 TIME 0 -> instant load without waiting 4s
    executor.execute(parser.parse("GOTO CUE 1 TIME 0"))
    assert seq.position == 1
    assert not seq.on_go
    assert float(mock_backend.dmx.levels["sequence"][0]) == pytest.approx(1.0)
    assert led.intensity == pytest.approx(1.0)
    assert led.color_srgb.to_hex().upper() == "#FF0000"

    # CUE 2 GOTO TIME 0 -> instant load of Cue 2
    executor.execute(parser.parse("CUE 2 GOTO TIME 0"))
    assert seq.position == 2
    assert not seq.on_go
    assert float(mock_backend.dmx.levels["sequence"][0]) == pytest.approx(0.5)
    assert led.intensity == pytest.approx(0.5)
    assert led.color_srgb.to_hex().upper() == "#00FF00"


def test_command_executor_home_and_locate() -> None:
    from olc.actions import register_all_actions
    from olc.devices import create_moving_head_definition

    app = CoreApplication(MagicMock())
    register_all_actions(app.action_registry)
    mock_backend = MagicMock()
    mock_backend.dmx = MagicMock()
    app.backend = mock_backend

    fix_def = create_moving_head_definition()
    app.lightshow.patch.patch_device(1, fix_def, 1, 1)
    dev = app.lightshow.patch.devices[1]

    dev.set_intensity(0.5)
    dev.set_position_degrees(50.0, 50.0)

    parser = CommandParser()
    executor = CommandExecutor(app)

    # Execute 1 HOME
    res = executor.execute(parser.parse("1 HOME"))
    assert res.success is True
    assert dev.intensity == 0.5
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)

    # Execute 1 LOCATE
    res_loc = executor.execute(parser.parse("1 LOCATE"))
    assert res_loc.success is True
    assert dev.intensity == 1.0


def test_executor_relative_selection() -> None:
    """Test relative selection (+, -, THRU, ODD/EVEN) modifying active selection."""
    settings = MagicMock()
    app = CoreApplication(settings)
    executor = CommandExecutor(app)
    parser = CommandParser()

    # Initial selection: 1 THRU 3
    executor.execute(parser.parse("1 THRU 3"))
    assert app.selected_channels == [1, 2, 3]
    assert app.last_selected_channel == 3

    # Relative add: + 5
    res1 = executor.execute(parser.parse("+ 5"))
    assert res1.success is True
    assert app.selected_channels == [1, 2, 3, 5]
    assert app.last_selected_channel == 5

    # Relative THRU: THRU 8 (from last 5 to 8)
    res2 = executor.execute(parser.parse("THRU 8"))
    assert res2.success is True
    assert app.selected_channels == [1, 2, 3, 5, 6, 7, 8]
    assert app.last_selected_channel == 8

    # Relative exclude: - 2 - 6
    res3 = executor.execute(parser.parse("- 2 - 6"))
    assert res3.success is True
    assert app.selected_channels == [1, 3, 5, 7, 8]

    # Direct ODD filter
    res4 = executor.execute(parser.parse("ODD"))
    assert res4.success is True
    assert app.selected_channels == [1, 3, 5, 7]

    # Direct EVEN filter on [1, 3, 5, 7] -> empty
    res5 = executor.execute(parser.parse("EVEN"))
    assert res5.success is True
    assert app.selected_channels == []


def test_executor_relative_selection_with_intensity() -> None:
    """Test relative selection combined with action clause (e.g. + 4 AT 50)."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    executor = CommandExecutor(app)
    parser = CommandParser()

    # Initial selection: 1 and 2
    executor.execute(parser.parse("1 + 2"))
    assert app.selected_channels == [1, 2]

    # + 4 AT 50 -> selection becomes [1, 2, 4] and all set to 50% (0.5)
    res = executor.execute(parser.parse("+ 4 AT 50"))
    assert res.success is True
    assert app.selected_channels == [1, 2, 4]
    for ch in [1, 2, 4]:
        assert app.backend.dmx.levels["user"][ch - 1] == 0.5


def test_commandline_selection_and_intensity_undo_redo() -> None:
    """Test full user workflow: 1 THRU 20 ENTER AT 30 ENTER followed by Undo/Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [-1.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # 1. Type 1 THRU 20 into command line
    app.action_registry.execute("commandline.append_char", "1")
    app.action_registry.execute("commandline.append_char", " THRU ")
    app.action_registry.execute("commandline.append_char", "20")
    assert app.commandline.get_string() == "1 THRU 20"
    # Keystrokes must NOT be in undo stack
    assert len(app.history.undo_stack) == 0

    # 2. Press ENTER (execute commandline)
    app.action_registry.execute("commandline.execute")
    assert app.commandline.get_string() == ""
    assert app.selected_channels == list(range(1, 21))
    assert app.last_selected_channel == 20
    # Exactly 1 action in undo stack: channel.select_channels
    assert len(app.history.undo_stack) == 1
    assert app.history.undo_stack[-1].name == "channel.select_channels"

    # 3. Type AT 30 into command line
    app.action_registry.execute("commandline.append_char", "AT ")
    app.action_registry.execute("commandline.append_char", "30")
    assert app.commandline.get_string() == "AT 30"
    assert len(app.history.undo_stack) == 1

    # 4. Press ENTER (execute commandline)
    app.action_registry.execute("commandline.execute")
    assert app.commandline.get_string() == ""
    for ch in range(1, 21):
        assert app.backend.dmx.levels["user"][ch - 1] == 0.3
    # Exactly 2 actions in undo stack: select_channels, set_multi_levels
    assert len(app.history.undo_stack) == 2
    assert app.history.undo_stack[-1].name == "channel.set_multi_levels"

    # 5. First UNDO -> cancels AT 30
    app.action_registry.execute("edit.undo")
    for ch in range(1, 21):
        assert app.backend.dmx.levels["user"][ch - 1] == -1.0
    # Channels 1..20 are still selected
    assert app.selected_channels == list(range(1, 21))
    assert len(app.history.undo_stack) == 1
    assert len(app.history.redo_stack) == 1

    # 6. Second UNDO -> cancels 1 THRU 20 selection
    app.action_registry.execute("edit.undo")
    assert app.selected_channels == []
    assert app.last_selected_channel is None
    assert len(app.history.undo_stack) == 0
    assert len(app.history.redo_stack) == 2

    # 7. First REDO -> restores 1 THRU 20 selection
    app.action_registry.execute("edit.redo")
    assert app.selected_channels == list(range(1, 21))
    assert app.last_selected_channel == 20
    assert len(app.history.undo_stack) == 1

    # 8. Second REDO -> restores AT 30 intensity
    app.action_registry.execute("edit.redo")
    for ch in range(1, 21):
        assert app.backend.dmx.levels["user"][ch - 1] == 0.3
    assert len(app.history.undo_stack) == 2
    assert len(app.history.redo_stack) == 0


def test_executor_patch_command_and_atomic_undo_redo() -> None:
    """Verify PATCH command with THRU/+/-, atomic Undo/Redo, and collisions."""
    from olc.devices.builtin import create_rgb_definition

    app = CoreApplication(MagicMock())
    patch = app.lightshow.patch
    patch.patch_empty()

    executor = CommandExecutor(app)
    parser = CommandParser()

    # 1. Single channel patched to multiple non-consecutive addresses
    res = executor.execute(parser.parse("1 PATCH AT 10 THRU 13 + 2/5 - 11"))
    assert res.success is True
    for univ, addr in ((1, 10), (1, 12), (1, 13), (2, 5)):
        assert patch.get_address_occupant(univ, addr) == 1
    assert patch.get_address_occupant(1, 11) is None

    # Single Undo reverts the ENTIRE command
    assert len(app.history.undo_stack) == 1
    app.action_registry.execute("edit.undo")
    for univ, addr in ((1, 10), (1, 12), (1, 13), (2, 5)):
        assert patch.get_address_occupant(univ, addr) is None

    # Single Redo restores the ENTIRE command
    app.action_registry.execute("edit.redo")
    for univ, addr in ((1, 10), (1, 12), (1, 13), (2, 5)):
        assert patch.get_address_occupant(univ, addr) == 1

    # 2. Collision triggers confirmation request and refuses without confirmation
    confirm_calls: list[str] = []
    app.subscribe(
        "commandline.confirm_required",
        lambda msg, _cb: confirm_calls.append(msg),
    )
    res_coll = executor.execute(parser.parse("2 PATCH AT 10"))
    assert res_coll.success is False
    assert len(confirm_calls) == 1
    assert "1/10" in confirm_calls[0]
    assert patch.get_address_occupant(1, 10) == 1  # unchanged

    # 3. Confirmation callback overwrites and is undoable in one step
    callbacks: list[object] = []
    app2 = CoreApplication(MagicMock())
    app2.lightshow.patch.patch_empty()
    exec2 = CommandExecutor(app2)
    exec2.execute(parser.parse("1 PATCH AT 10 THRU 11"))
    app2.subscribe(
        "commandline.confirm_required",
        lambda _msg, cb: callbacks.append(cb),
    )
    res_need_confirm = exec2.execute(parser.parse("2 PATCH AT 10 THRU 11"))
    assert res_need_confirm.success is False
    assert len(callbacks) == 1
    cb_fn = callbacks[0]
    assert callable(cb_fn)
    cb_fn()
    assert app2.lightshow.patch.get_address_occupant(1, 10) == 2
    assert app2.lightshow.patch.get_address_occupant(1, 11) == 2

    # Undo restores channel 1 on both 10 and 11
    app2.action_registry.execute("edit.undo")
    assert app2.lightshow.patch.get_address_occupant(1, 10) == 1
    assert app2.lightshow.patch.get_address_occupant(1, 11) == 1

    # 4. Reject patching onto non-dimmer fixture channel
    app2.lightshow.patch.patch_device(50, create_rgb_definition(), 1, 100)
    res_non_dim = exec2.execute(parser.parse("50 PATCH AT 200"))
    assert res_non_dim.success is False
    assert "non-dimmer" in res_non_dim.message


def test_executor_unpatch_command_and_atomic_undo_redo() -> None:
    """Verify UNPATCH variants and single-step atomic Undo/Redo."""
    app = CoreApplication(MagicMock())
    patch = app.lightshow.patch
    patch.patch_empty()

    executor = CommandExecutor(app)
    parser = CommandParser()

    # Patch channel 1 to 10..13 and channel 2 to 20..21
    executor.execute(parser.parse("1 PATCH AT 10 THRU 13"))
    executor.execute(parser.parse("2 PATCH AT 20 THRU 21"))

    # 1. Unpatch specific addresses on channel 1: 1 UNPATCH AT 11 THRU 12
    res1 = executor.execute(parser.parse("1 UNPATCH AT 11 THRU 12"))
    assert res1.success is True
    assert patch.get_address_occupant(1, 10) == 1
    assert patch.get_address_occupant(1, 11) is None
    assert patch.get_address_occupant(1, 12) is None
    assert patch.get_address_occupant(1, 13) == 1

    # Single Undo restores both 11 and 12
    app.action_registry.execute("edit.undo")
    assert patch.get_address_occupant(1, 11) == 1
    assert patch.get_address_occupant(1, 12) == 1

    # 2. Unpatch full channels: 1 THRU 2 UNPATCH
    res2 = executor.execute(parser.parse("1 THRU 2 UNPATCH"))
    assert res2.success is True
    assert patch.get_device(1) is None
    assert patch.get_device(2) is None

    # Single Undo restores both channels and all their addresses
    app.action_registry.execute("edit.undo")
    assert patch.get_address_occupant(1, 10) == 1
    assert patch.get_address_occupant(1, 13) == 1
    assert patch.get_address_occupant(1, 20) == 2
    assert patch.get_address_occupant(1, 21) == 2

    # 3. Unpatch by address: ADDRESS 20 THRU 21 UNPATCH
    res3 = executor.execute(parser.parse("ADDRESS 20 THRU 21 UNPATCH"))
    assert res3.success is True
    assert patch.get_address_occupant(1, 20) is None
    assert patch.get_address_occupant(1, 21) is None


def test_executor_address_at_level_and_next_last_stepping() -> None:
    """Test ADDRESS ... AT <level>, Undo/Redo, and Eos-style Next/Last stepping."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication
    from olc.dmx import Dmx

    settings = MagicMock()
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    dmx = Dmx(None, app.lightshow)
    app.backend = MagicMock()
    app.backend.dmx = dmx
    parser = CommandParser()
    executor = CommandExecutor(app)

    # 1. ADDRESS 10 AT 50 -> sets user_outputs[(10, 1)] = 128 and Address Check
    app.commandline.set_string("ADDRESS 10 AT 50")
    res = app.commandline.execute()
    assert res.success is True
    assert dmx.user_outputs[(10, 1)] == 128
    assert app.address_check == (1, 10, 128)
    assert app.commandline.get_string() == "ADDRESS 1/10 AT 50"

    # 2. Next (+1) -> releases 10, tests 11 at 128, updates command line
    assert app.step_address_check(1) is True
    assert (10, 1) not in dmx.user_outputs
    assert dmx.user_outputs[(11, 1)] == 128
    assert app.address_check == (1, 11, 128)
    assert app.commandline.get_string() == "ADDRESS 1/11 AT 50"

    # 3. Undo Next -> restores 10 at 128 and releases 11
    app.action_registry.execute("edit.undo")
    assert dmx.user_outputs[(10, 1)] == 128
    assert (11, 1) not in dmx.user_outputs

    # 4. Redo Next -> releases 10 and restores 11 at 128
    app.action_registry.execute("edit.redo")
    assert (10, 1) not in dmx.user_outputs
    assert dmx.user_outputs[(11, 1)] == 128

    # 5. Last (-1) -> releases 11 and returns to 10
    assert app.step_address_check(-1) is True
    assert (11, 1) not in dmx.user_outputs
    assert dmx.user_outputs[(10, 1)] == 128
    assert app.commandline.get_string() == "ADDRESS 1/10 AT 50"

    # 6. ADDRESS 10 AT OUT -> releases 10 and exits Address Check
    res_out = executor.execute(parser.parse("ADDRESS 10 AT OUT"))
    assert res_out.success is True
    assert (10, 1) not in dmx.user_outputs
    assert app.address_check is None
    assert app.step_address_check(1) is False

    # 7. Exiting Address Check restores underlying channel/cue/fader DMX level
    app.lightshow.patch.patch_dimmer(channel=1, universe=1, address=10)
    dmx.levels["user"][0] = 102.0 / 255.0
    dmx.set_levels()
    assert dmx.get_output_level(1, 10) == 102

    executor.execute(parser.parse("ADDRESS 10 AT FULL"))
    assert dmx.get_output_level(1, 10) == 255
    assert app.address_check == (1, 10, 255)

    app.clear_address_check()
    assert app.address_check is None
    assert (10, 1) not in dmx.user_outputs
    assert dmx.get_output_level(1, 10) == 102

    # 8. Selecting a channel (e.g. clicking in ChannelsView) exits Address Check
    executor.execute(parser.parse("ADDRESS 10 AT FULL"))
    assert dmx.get_output_level(1, 10) == 255
    assert app.address_check == (1, 10, 255)

    app.action_registry.execute("channel.select_channels", [1])
    assert app.address_check is None
    assert (10, 1) not in dmx.user_outputs
    assert dmx.get_output_level(1, 10) == 102

    # 9. Pressing BackSpace during Address Check exits Address Check & clears cmdline
    app.commandline.set_string("ADDRESS 10 AT FULL")
    app.commandline.execute()
    assert dmx.get_output_level(1, 10) == 255
    assert app.address_check == (1, 10, 255)
    assert app.commandline.get_string() == "ADDRESS 1/10 AT FULL"

    app.action_registry.execute("commandline.backspace")
    assert app.address_check is None
    assert (10, 1) not in dmx.user_outputs
    assert dmx.get_output_level(1, 10) == 102
    assert app.commandline.get_string() == ""


def test_executor_channel_check_and_next_last_stepping() -> None:
    """Test Eos-style CHECK, default 80%, Next/Last stepping, and restore."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication
    from olc.dmx import Dmx

    settings = MagicMock()
    settings.get_boolean.return_value = True
    settings.get_double.return_value = 80.0
    app = CoreApplication(settings)
    dmx = Dmx(None, app.lightshow)
    app.backend = MagicMock()
    app.backend.dmx = dmx
    app.lightshow.patch.patch_dimmer(channel=1, universe=1, address=1)
    app.lightshow.patch.patch_dimmer(channel=3, universe=1, address=3)
    app.lightshow.patch.patch_dimmer(channel=5, universe=1, address=5)

    # Existing user level on ch 3 before check
    dmx.levels["user"][2] = 0.25

    parser = CommandParser()
    executor = CommandExecutor(app)

    # 1. `1 CHECK` uses default channel-check-level (80.0%)
    app.commandline.set_string("1 CHECK")
    app.commandline.execute()
    assert app.channel_check == (1, 0.8, -1.0)
    assert abs(dmx.levels["user"][0] - 0.8) < 1e-6
    assert app.commandline.get_string() == "CHANNEL 1 CHECK AT 80"

    # 2. Step Next (+1) -> channel 3 (next patched channel), restores ch 1 to -1.0
    app.step_channel_check(1)
    assert app.channel_check == (3, 0.8, 0.25)
    assert dmx.levels["user"][0] == -1.0
    assert abs(dmx.levels["user"][2] - 0.8) < 1e-6
    assert app.commandline.get_string() == "CHANNEL 3 CHECK AT 80"

    # 3. Step Next (+1) -> channel 5, restores ch 3 to its previous 0.25
    app.step_channel_check(1)
    assert app.channel_check == (5, 0.8, -1.0)
    assert abs(dmx.levels["user"][2] - 0.25) < 1e-6
    assert abs(dmx.levels["user"][4] - 0.8) < 1e-6

    # 4. Step Last (-1) -> back to channel 3
    app.step_channel_check(-1)
    assert app.channel_check == (3, 0.8, 0.25)
    assert dmx.levels["user"][4] == -1.0
    assert abs(dmx.levels["user"][2] - 0.8) < 1e-6

    # 5. BackSpace exits Channel Check and restores ch 3 to 0.25
    app.action_registry.execute("commandline.backspace")
    assert app.channel_check is None
    assert abs(dmx.levels["user"][2] - 0.25) < 1e-6
    assert app.commandline.get_string() == ""

    # 6. `1 AT 50 CHECK` & selecting another channel exits Channel Check
    executor.execute(parser.parse("1 AT 50 CHECK"))
    assert app.channel_check == (1, 0.5, -1.0)
    assert abs(dmx.levels["user"][0] - 0.5) < 1e-6

    app.action_registry.execute("channel.select_channels", [3])
    assert app.channel_check is None
    assert dmx.levels["user"][0] == -1.0

    # 7. `1 CHECK AT OUT` releases immediately without entering channel_check
    dmx.levels["user"][0] = 0.6
    executor.execute(parser.parse("1 CHECK AT OUT"))
    assert app.channel_check is None
    assert dmx.levels["user"][0] == -1.0


def test_executor_group_selection_real_lightshow() -> None:
    """Test GROUP <n> selection resolves against real LightShow.groups."""
    from olc.core.app import CoreApplication
    from olc.show.group import Group

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    app.lightshow.groups.add(Group(2.0, [3, 1, 5], "Movers"))

    parser = CommandParser()
    executor = CommandExecutor(app)
    res = executor.execute(parser.parse("GROUP 2 AT 80"))

    assert res.success is True
    assert app.selected_channels == [1, 3, 5]
    for ch in (1, 3, 5):
        assert app.backend.dmx.levels["user"][ch - 1] == pytest.approx(0.8)


def test_executor_palette_record_apply_update_cascade_and_undo_redo() -> None:
    """Test end-to-end RECORD/APPLY/UPDATE/DELETE Palette & Preset + cascade."""
    from olc.core.app import CoreApplication
    from olc.devices.builtin import create_moving_head_definition, create_rgb_definition
    from olc.devices.channel import ChannelType
    from olc.dmx import Dmx
    from olc.show.cue import Cue
    from olc.show.fader import FaderPreset
    from olc.show.palette import Palette, PaletteCategory
    from olc.show.step import Step

    settings = MagicMock()
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    dmx = Dmx(None, app.lightshow)
    app.backend = MagicMock()
    app.backend.dmx = dmx

    # Ch 1: Dimmer, Ch 2: LED RGB, Ch 3: Moving Head Spot
    app.lightshow.patch.patch_dimmer(channel=1, universe=1, address=1)
    app.lightshow.patch.patch_device(2, create_rgb_definition(), 1, 10)
    app.lightshow.patch.patch_device(3, create_moving_head_definition(), 1, 20)

    rgb_dev = app.lightshow.patch.devices[2]
    spot_dev = app.lightshow.patch.devices[3]

    parser = CommandParser()
    executor = CommandExecutor(app)

    # 1. Record Intensity Palette 1 (ch 1 @ 80%), Color Palette 2 (ch 2 Red),
    #    Focus Palette 10 (ch 3 Pan 45 Tilt -20), Beam Palette 1 (ch 3 Zoom 25)
    executor.execute(parser.parse("1 AT 80"))
    res_rec_ip = executor.execute(parser.parse("RECORD INTENSITY PALETTE 1"))
    assert res_rec_ip.success is True
    ip1 = app.lightshow.palettes.get(PaletteCategory.INTENSITY, 1.0)
    assert ip1 is not None and ip1.channels[1] == pytest.approx(0.8)

    executor.execute(parser.parse("2 COLOR #FF0000"))
    res_rec_cp = executor.execute(parser.parse("RECORD COLOR PALETTE 2"))
    assert res_rec_cp.success is True
    cp2 = app.lightshow.palettes.get(PaletteCategory.COLOR, 2.0)
    assert cp2 is not None
    assert cp2.device_values[2]["color"].upper() == "#FF0000"

    executor.execute(parser.parse("3 PAN 45 TILT -20"))
    res_rec_fp = executor.execute(parser.parse("RECORD FOCUS PALETTE 10"))
    assert res_rec_fp.success is True
    fp10 = app.lightshow.palettes.get(PaletteCategory.FOCUS, 10.0)
    assert fp10 is not None
    assert fp10.device_values[3]["pan"] == pytest.approx(45.0, abs=1.5)
    assert fp10.device_values[3]["tilt"] == pytest.approx(-20.0, abs=1.5)

    executor.execute(parser.parse("3 ZOOM 25"))
    res_rec_bp = executor.execute(parser.parse("RECORD BEAM PALETTE 1"))
    assert res_rec_bp.success is True
    bp1 = app.lightshow.palettes.get(PaletteCategory.BEAM, 1.0)
    assert bp1 is not None
    assert bp1.device_values[3]["zoom"] == pytest.approx(25.0, abs=1.0)

    # 2. Record Preset 1 from live stage (ch 1, 2, 3) then clear live state
    app.selected_channels = []
    res_rec_pr = executor.execute(parser.parse("RECORD PRESET 1"))
    assert res_rec_pr.success is True
    pr1 = app.lightshow.palettes.get(PaletteCategory.PRESET, 1.0)
    assert pr1 is not None and pr1.channels[1] == pytest.approx(0.8)

    # Reset devices and user levels, then recall via CP 2 / FP 10 / BP 1 / PRESET 1
    dmx.levels["user"][0] = 0.0
    rgb_dev.set_color_hex("#000000")
    spot_dev.home()

    assert executor.execute(parser.parse("2 CP 2")).success is True
    assert rgb_dev.color_srgb.r == pytest.approx(1.0, abs=0.05)
    assert rgb_dev.color_srgb.g == pytest.approx(0.0, abs=0.05)

    # Undo CP 2 recall reverts LED back to black
    app.action_registry.execute("edit.undo")
    assert rgb_dev.color_srgb.r == pytest.approx(0.0, abs=0.05)
    app.action_registry.execute("edit.redo")
    assert rgb_dev.color_srgb.r == pytest.approx(1.0, abs=0.05)

    assert executor.execute(parser.parse("1 INTENSITY PALETTE 1")).success is True
    assert dmx.levels["user"][0] == pytest.approx(0.8)

    assert executor.execute(parser.parse("3 FOCUS PALETTE 10")).success is True
    assert spot_dev.pan_degrees == pytest.approx(45.0, abs=1.5)

    assert executor.execute(parser.parse("3 BEAM PALETTE 1")).success is True
    assert spot_dev.zoom_degrees == pytest.approx(25.0, abs=1.0)

    # Recall full Preset 1
    dmx.levels["user"][0] = 0.0
    rgb_dev.set_color_hex("#000000")
    spot_dev.home()
    assert executor.execute(parser.parse("1 THRU 3 PRESET 1")).success is True
    assert dmx.levels["user"][0] == pytest.approx(0.8)
    assert rgb_dev.color_srgb.r == pytest.approx(1.0, abs=0.05)
    assert spot_dev.pan_degrees == pytest.approx(45.0, abs=1.5)

    # 3. Cascade propagation via UPDATE COLOR PALETTE 2 (+ Undo/Redo rollback!)
    pr5 = Palette(
        category=PaletteCategory.PRESET,
        number=5.0,
        text="Linked Preset",
        channels={2: 1.0},
        device_values={2: {"color": "#FF0000"}},
        palette_refs={2: {"color": ("color", 2.0)}},
    )
    app.lightshow.palettes.add(pr5)
    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={2: 1.0},
        device_values={2: {"color": "#FF0000"}},
        palette_refs={2: {"color": ("color", 2.0)}},
    )
    app.lightshow.cues.add(cue1)
    app.lightshow.main_playback.add_step(Step(1, cue=cue1))
    fader = FaderPreset(1, app.lightshow.fader_bank, pr5)
    app.lightshow.fader_bank.faders[1][1] = fader

    # Edit ch 2 color live to green (#00FF00) and run UPDATE COLOR PALETTE 2
    executor.execute(parser.parse("2 COLOR #00FF00"))
    res_upd = executor.execute(parser.parse("UPDATE COLOR PALETTE 2"))
    assert res_upd.success is True
    assert "propagated to 1 preset(s), 1 cue(s)" in res_upd.message
    assert cp2.device_values[2]["color"].upper() == "#00FF00"
    assert pr5.device_values[2]["color"].upper() == "#00FF00"
    assert cue1.device_values[2]["color"].upper() == "#00FF00"

    # Undo UPDATE cascades rollback back to #FF0000
    app.action_registry.execute("edit.undo")
    cp2_undone = app.lightshow.palettes.get(PaletteCategory.COLOR, 2.0)
    assert cp2_undone is not None
    assert cp2_undone.device_values[2]["color"].upper() == "#FF0000"
    assert pr5.device_values[2]["color"].upper() == "#FF0000"
    assert cue1.device_values[2]["color"].upper() == "#FF0000"

    # Redo UPDATE cascades #00FF00 again
    app.action_registry.execute("edit.redo")
    assert pr5.device_values[2]["color"].upper() == "#00FF00"
    assert cue1.device_values[2]["color"].upper() == "#00FF00"

    # 4. Delete Beam Palette 1 + Undo/Redo
    assert executor.execute(parser.parse("DELETE BEAM PALETTE 1")).success is True
    assert app.lightshow.palettes.get(PaletteCategory.BEAM, 1.0) is None
    app.action_registry.execute("edit.undo")
    assert app.lightshow.palettes.get(PaletteCategory.BEAM, 1.0) is not None
    assert spot_dev.get_channel(ChannelType.ZOOM) is not None


def test_executor_group_commands_float_order_and_undo_redo() -> None:
    """Verify RECORD/UPDATE/DELETE/LABEL GROUP, float IDs, order preservation, Undo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.lightshow.groups.clear()

    parser = CommandParser()
    executor = CommandExecutor(app)

    # 1. Explicit descending selection preserves reverse order
    res_sel = executor.execute(parser.parse("4 THRU 1"))
    assert res_sel.success is True
    assert app.selected_channels == [4, 3, 2, 1]

    # 2. Record float Group 2.5 with ordered selection + label
    res_rec = executor.execute(
        parser.parse('10 THRU 8 + 2 RECORD GROUP 2.5 LABEL "Contres"')
    )
    assert res_rec.success is True
    grp = app.lightshow.groups.get(2.5)
    assert grp is not None
    assert grp.channels == [10, 9, 8, 2]
    assert grp.text == "Contres"

    # Undo -> removes Group 2.5; Redo -> restores
    app.action_registry.execute("edit.undo")
    assert app.lightshow.groups.get(2.5) is None
    app.action_registry.execute("edit.redo")
    assert app.lightshow.groups.get(2.5) is not None

    # 3. Recall GROUP 2.5 preserves ordered selection
    app.selected_channels = []
    res_g = executor.execute(parser.parse("GROUP 2.5"))
    assert res_g.success is True
    assert app.selected_channels == [10, 9, 8, 2]

    # 4. Update Group 2.5 with new ordered selection (+ Undo/Redo)
    res_upd = executor.execute(parser.parse("1 + 5 + 3 UPDATE GROUP 2.5"))
    assert res_upd.success is True
    grp25 = app.lightshow.groups.get(2.5)
    assert grp25 is not None
    assert grp25.channels == [1, 5, 3]
    app.action_registry.execute("edit.undo")
    assert grp25.channels == [10, 9, 8, 2]
    app.action_registry.execute("edit.redo")
    assert grp25.channels == [1, 5, 3]

    # 5. Label Group via both syntaxes (+ Undo/Redo)
    assert executor.execute(parser.parse('LABEL GROUP 2.5 "Wash"')).success is True
    assert grp25.text == "Wash"
    assert executor.execute(parser.parse('GROUP 2.5 LABEL "Front"')).success is True
    assert grp25.text == "Front"
    app.action_registry.execute("edit.undo")
    assert grp25.text == "Wash"

    # 6. Auto-numbered RECORD GROUP from current Live selection
    app.selected_channels = [7, 4]
    res_auto = executor.execute(parser.parse("RECORD GROUP"))
    assert res_auto.success is True
    auto_grp = app.lightshow.groups.get(3.5)
    assert auto_grp is not None
    assert auto_grp.channels == [7, 4]

    # 7. Delete Group 2.5 (+ Undo)
    assert executor.execute(parser.parse("DELETE GROUP 2.5")).success is True
    assert app.lightshow.groups.get(2.5) is None
    app.action_registry.execute("edit.undo")
    assert app.lightshow.groups.get(2.5) is not None


def test_multi_sequence_cue_commands_without_collision() -> None:
    """Verify RECORD/UPDATE/BLOCK/DELETE SEQ <n> CUE <m> isolate same cue numbers."""
    app = CoreApplication(MagicMock())
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0.0] * 512}
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend
    parser = CommandParser()
    executor = CommandExecutor(app)

    app.action_registry.execute("sequence.new", 2.0)

    # Record Cue 1 in Main Playback (Seq 1) with Ch 1 @ 50%
    executor.execute(parser.parse("1 @ 50"))
    res1 = executor.execute(parser.parse("RECORD CUE 1"))
    assert res1.success is True
    assert "Cue 1.0" in res1.message

    # Record Cue 1 in Seq 2 with Ch 2 @ 80% (same cue number, different sequence)
    mock_dmx.levels["user"][0] = 0.0
    executor.execute(parser.parse("2 @ 80"))
    res2 = executor.execute(parser.parse("RECORD SEQ 2 CUE 1"))
    assert res2.success is True
    assert "Seq 2 Cue 1.0" in res2.message

    cue_seq1 = app.lightshow.get_cue(1.0, 1)
    cue_seq2 = app.lightshow.get_cue(1.0, 2)
    assert cue_seq1 is not None and cue_seq2 is not None
    assert cue_seq1 is not cue_seq2
    assert 1 in cue_seq1.channels and 2 not in cue_seq1.channels
    assert 2 in cue_seq2.channels and 1 not in cue_seq2.channels

    # Block Seq 2 Cue 1 only (noun-first syntax)
    res_blk = executor.execute(parser.parse("SEQ 2 CUE 1 BLOCK"))
    assert res_blk.success is True
    assert "Seq 2 Cue 1.0" in res_blk.message
    assert cue_seq2.is_block is True
    assert cue_seq1.is_block is False

    # Delete Seq 2 Cue 1 leaves Seq 1 Cue 1 intact
    res_del = executor.execute(parser.parse("DELETE SEQ 2 CUE 1"))
    assert res_del.success is True
    assert app.lightshow.get_cue(1.0, 2) is None
    assert app.lightshow.get_cue(1.0, 1) is cue_seq1
