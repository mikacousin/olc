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
    # 80% of 255 = 204
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 204

    # AT +10 (relative on active selection)
    cmd2 = parser.parse("AT + 10")
    res2 = executor.execute(cmd2)
    assert res2.success
    # 90% of 255 = 230
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 230

    # AT OUT
    cmd3 = parser.parse("AT OUT")
    res3 = executor.execute(cmd3)
    assert res3.success
    for ch in [1, 2, 3]:
        assert app.backend.dmx.levels["user"][ch - 1] == 0


def test_executor_record_and_goto_cue() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {"user": [0] * 512}
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
    assert cue.channels[1] == 255
    assert cue.channels[2] == 255

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
    mock_dmx.levels = {"user": [0] * 512, "sequence": [0] * 512}
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
    mock_dmx.levels = {"user": [0] * 512, "sequence": [0] * 512}
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

    from olc.cue import Cue
    from olc.devices.builtin import create_moving_head_definition
    from olc.sequence import _capture_device_states, _interpolate_device_states
    from olc.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_dmx.levels = {
        "user": np.full(512, -1, dtype=np.int16),
        "sequence": np.zeros(512, dtype=np.uint8),
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
    cue1 = Cue(0, 1.0, channels={1: 200}, device_values={1: {"pan": 0.0, "tilt": 0.0}})
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
    # Intensity 200 tracked from cue 1, pan=100 applied from cue 2
    assert mock_dmx.levels["sequence"][0] == 200
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
