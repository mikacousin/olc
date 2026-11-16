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
