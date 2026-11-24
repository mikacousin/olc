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
"""Unit tests for multi-sequence Actions, CLI syntax, and Live ownership."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.core.channel_snapshot import build_live_channel_snapshot
from olc.core.dmx_backend import DMXBackend
from olc.core.parser.executor import CommandResult
from olc.core.playback_arbitrator import PlaybackPriority
from olc.devices.channel import Channel, ChannelType
from olc.devices.device import LightingDevice
from olc.devices.fixture import FixtureType
from olc.show.cue import Cue
from olc.show.sequence import Sequence
from olc.show.step import Step


def _make_app() -> CoreApplication:
    settings = MagicMock()
    settings.get_double.return_value = 5.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    app.backend = DMXBackend(app.lightshow)
    app.init_engine(monitor_port=5555, no_listen=True, no_transmit=True)
    return app


def _patch_rgb(app: CoreApplication, ch: int, addr: int) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=ch,
        label=f"LED {ch}",
        fixture_type=FixtureType.LED_PAR,
        channels=[
            Channel(ChannelType.INTENSITY, 1, addr),
            Channel(ChannelType.RED, 1, addr + 1),
            Channel(ChannelType.GREEN, 1, addr + 2),
            Channel(ChannelType.BLUE, 1, addr + 3),
        ],
    )
    app.lightshow.patch.devices[ch] = dev
    return dev


def _populate_seq(
    seq: Sequence,
    cues: list[tuple[float, dict[int, float], dict[int, dict[str, object]]]],
) -> None:
    for num, chans, devs in cues:
        cue = Cue(int(seq.index), num, channels=dict(chans), text=f"Q{num:g}")
        cue.device_values = {k: dict(v) for k, v in devs.items()}
        seq.cues.add(cue)
        step = Step(sequence=int(seq.index), cue=cue)
        seq.insert_step(len(seq.steps) - 1, step)


def _run_cli(app: CoreApplication, cmd: str) -> CommandResult:
    app.commandline.set_string(cmd)
    return app.commandline.execute()


def test_sequence_set_playback_options_undo_redo() -> None:
    """Verify sequence.set_playback_options updates options with Undo/Redo."""
    app = _make_app()
    try:
        seq2 = Sequence(2, text="FX Seq", lightshow=app.lightshow)
        app.lightshow.sequences.append(seq2)

        ok = app.action_registry.execute(
            "sequence.set_playback_options",
            2,
            priority=PlaybackPriority.HIGH,
            auto_start=True,
            wrap_around=True,
        )
        assert ok is True
        assert seq2.priority is PlaybackPriority.HIGH
        assert seq2.auto_start is True
        assert seq2.wrap_around is True

        app.action_registry.execute("edit.undo")
        assert seq2.priority is PlaybackPriority.NORMAL
        assert seq2.auto_start is False
        assert seq2.wrap_around is False

        app.action_registry.execute("edit.redo")
        assert seq2.priority is PlaybackPriority.HIGH
        assert seq2.auto_start is True
        assert seq2.wrap_around is True
    finally:
        app.stop()


def test_cli_multi_sequence_control_and_live_ownership() -> None:
    """Verify CLI GO/GOTO/PAUSE/ASSERT/RELEASE/RELEASE ALL and Live ownership."""
    app = _make_app()
    assert app.backend is not None
    try:
        dev1 = _patch_rgb(app, 1, 1)
        _patch_rgb(app, 2, 5)
        main_pb = app.lightshow.main_playback
        _populate_seq(
            main_pb,
            [(1.0, {1: 0.4}, {1: {"color": "#0000ff"}})],
        )

        seq2 = Sequence(2, text="Overlay", lightshow=app.lightshow)
        _populate_seq(
            seq2,
            [(10.0, {1: 0.9, 2: 0.7}, {1: {"color": "#ff0000"}})],
        )
        app.lightshow.sequences.append(seq2)

        # Load Seq 1 Cue 1
        main_pb.load_step(1)
        snap1 = build_live_channel_snapshot(app, 1)
        assert snap1.owner_sequence == 1.0
        assert snap1.owner_cue == 1.0

        # GOTO SEQ 2 CUE 10 TIME 0
        res_goto = _run_cli(app, "GOTO SEQ 2 CUE 10 TIME 0")
        assert res_goto.success is True
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.9)
        assert dev1.color_rgb == (255, 0, 0)

        snap1_after = build_live_channel_snapshot(app, 1)
        snap2_after = build_live_channel_snapshot(app, 2)
        assert snap1_after.owner_sequence == 2.0
        assert snap1_after.owner_cue == 10.0
        assert snap2_after.owner_sequence == 2.0
        assert snap2_after.owner_cue == 10.0

        # GO / PAUSE / ASSERT / RELEASE via CLI
        assert _run_cli(app, "PAUSE SEQ 2").success is True
        assert _run_cli(app, "ASSERT SEQ 1").success is True
        assert dev1.color_rgb == (0, 0, 255)

        assert _run_cli(app, "RELEASE SEQ 2").success is True
        assert 2.0 not in app.playback_arbitrator.active_sequences()
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.4)

        # Re-activate Seq 2, then RELEASE ALL
        assert _run_cli(app, "GOTO SEQ 2 CUE 10 TIME 0").success is True
        assert _run_cli(app, "GO SEQ 1").success is True
        res_rel_all = _run_cli(app, "RELEASE ALL")
        assert res_rel_all.success is True
        assert app.playback_arbitrator.active_sequences() == []
    finally:
        app.stop()
