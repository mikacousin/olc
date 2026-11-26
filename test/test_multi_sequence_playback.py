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
"""Integration tests for concurrent multi-sequence playback and Eos CL faders."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gio  # noqa: E402

from olc.core.app import CoreApplication  # noqa: E402
from olc.core.dmx_backend import DMXBackend  # noqa: E402
from olc.devices.channel import Channel, ChannelType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.devices.fixture import FixtureType  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.cue import Cue  # noqa: E402
from olc.show.fader import FaderSequence, FaderType  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402
from olc.show.sequence import Sequence  # noqa: E402
from olc.show.step import Step  # noqa: E402


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


def test_concurrent_main_playback_and_fader_sequence_htp_ltp_assert_release() -> None:
    """Verify Seq 1 and Seq 2 on FaderSequence run concurrently with HTP/LTP."""
    app = _make_app()
    assert app.backend is not None
    try:
        dev1 = _patch_rgb(app, 1, 1)
        main_pb = app.lightshow.main_playback
        _populate_seq(
            main_pb,
            [(1.0, {1: 0.5}, {1: {"color": "#0000ff"}})],
        )

        seq2 = Sequence(2, text="Overlay", lightshow=app.lightshow)
        _populate_seq(
            seq2,
            [(10.0, {1: 0.8}, {1: {"color": "#ff0000"}})],
        )
        app.lightshow.sequences.append(seq2)

        app.lightshow.fader_bank.set_fader(1, 5, FaderType.SEQUENCE, seq2.index)
        fader = app.lightshow.fader_bank.faders[1][5]
        assert isinstance(fader, FaderSequence)

        # 1. Load Seq 1 Cue 1
        main_pb.load_step(1)
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.5)
        assert dev1.color_rgb == (0, 0, 255)

        # 2. Bring Fader 5 up to 100% -> Seq 2 HTP (0.8) & LTP (#ff0000) win
        fader.set_level(1.0)
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.8)
        assert dev1.color_rgb == (255, 0, 0)

        # 3. Assert Seq 1 reclaims color ownership without dropping Seq 2 HTP
        main_pb.assert_playback()
        assert dev1.color_rgb == (0, 0, 255)
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.8)

        # 4. Release Seq 2 -> intensity falls back to Seq 1 (0.5)
        fader.release()
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.5)
        assert dev1.color_rgb == (0, 0, 255)
    finally:
        app.stop()


def test_fader_sequence_auto_start_auto_stop_and_release_on_end() -> None:
    """Verify auto_start, auto_stop, and release_on_end on FaderSequence."""
    app = _make_app()
    assert app.backend is not None
    try:
        seq2 = Sequence(2, text="SubSeq", lightshow=app.lightshow)
        seq2.auto_start = True
        seq2.auto_stop = True
        seq2.release_on_end = True
        _populate_seq(seq2, [(1.0, {1: 0.9}, {}), (2.0, {1: 0.4}, {})])
        app.lightshow.sequences.append(seq2)

        app.lightshow.fader_bank.set_fader(1, 1, FaderType.SEQUENCE, seq2.index)
        fader = app.lightshow.fader_bank.faders[1][1]
        assert isinstance(fader, FaderSequence)

        # Raise from 0 -> auto_start activates step 1
        fader.set_level(0.5)
        assert 2.0 in app.playback_arbitrator.active_sequences()
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.45)

        # Drop to 0 -> auto_stop releases Seq 2
        fader.set_level(0.0)
        assert 2.0 not in app.playback_arbitrator.active_sequences()
        assert app.backend.dmx.levels["sequence"][0] == pytest.approx(0.0)

        # Raise again, advance to end, then Go at last cue -> release_on_end releases
        fader.set_level(1.0)
        seq2.position = 2
        seq2.do_go(None)
        assert 2.0 not in app.playback_arbitrator.active_sequences()
    finally:
        app.stop()


def test_eos_ascii_cuelist_on_fader_import(tmp_path: Path) -> None:
    """Verify Eos $CueList 2 + $FaderDef $$Target CL 2 + $$GoFromLast 3."""
    asc = "\n".join(
        [
            "Ident 3:0",
            "Manufacturer ETC",
            "Console Eos",
            "$CueList 1",
            "   Text Main",
            "Cue 1 1",
            "   Chan 1@Hff",
            "$CueList 2",
            "   Text dbut seq",
            "   $$Exclude 1",
            "Cue 699 2",
            "   Chan 2@H80",
            "$FaderDef 5",
            "   $$Target CL 2",
            "   $$GoFromLast 3 ! Restore",
            "EndData",
        ]
    )
    asc_file = tmp_path / "eos_cl_fader.asc"
    asc_file.write_text(asc, encoding="ascii")

    ls = LightShow()
    imported = ImportFile(ls, Gio.File.new_for_path(str(asc_file)), FileType.ASCII)
    imported.parse_sync(auto_import=True)

    assert len(ls.sequences) == 1
    seq2 = ls.sequences[0]
    assert seq2.index == 2
    assert seq2.release_on_end is True

    fader5 = ls.fader_bank.faders[1][5]
    assert isinstance(fader5, FaderSequence)
    assert fader5.contents is seq2
    assert fader5.exclude_record is True


def test_real_eos_file_cuelist_on_fader() -> None:
    """Verify $CueList 2 on $FaderDef 5 in real Eos show file if present."""
    asc_path = Path("doc/Conduites Eos/EDF- AGEN DUCOURNEAU - 17 NOVEMBRE 2026.asc")
    if not asc_path.exists():
        pytest.skip("Real Eos ASCII file not available in workspace")

    ls = LightShow()
    imported = ImportFile(ls, Gio.File.new_for_path(str(asc_path)), FileType.ASCII)
    imported.parse_sync(auto_import=True)

    seq2 = next((s for s in ls.sequences if s.index == 2), None)
    assert seq2 is not None
    assert seq2.release_on_end is True

    fader5 = ls.fader_bank.faders[1][5]
    assert isinstance(fader5, FaderSequence)
    assert fader5.contents is seq2
    assert fader5.exclude_record is True


def test_sequence_backward_to_blackout_resets_device_intensity() -> None:
    """Verify stepping back to blackout/Cue 0 resets physical and virtual dimmers."""
    from olc.devices.builtin import (  # pylint: disable=import-outside-toplevel
        create_moving_head_definition,
        create_rgb_definition,
    )

    app = _make_app()
    assert app.backend is not None
    try:
        dev10 = app.lightshow.patch.patch_device(
            10, create_moving_head_definition(), universe=1, address=1
        )
        dev11 = app.lightshow.patch.patch_device(
            11, create_rgb_definition(), universe=1, address=30
        )
        app.lightshow.patch.update_numpy_cache_if_dirty()

        main_pb = app.lightshow.main_playback
        _populate_seq(
            main_pb,
            [
                (1.0, {}, {}),
                (
                    2.0,
                    {10: 1.0, 11: 1.0},
                    {
                        10: {"intensity": 1.0, "pan": 45.0},
                        11: {"intensity": 1.0, "color": "#ff0000"},
                    },
                ),
            ],
        )

        # Load Cue 2 (lit)
        main_pb.load_step(2)
        assert dev10.intensity == pytest.approx(1.0)
        assert dev11.intensity == pytest.approx(1.0)
        assert app.backend.dmx.frame[0][4] == 255  # MH dimmer (addr 5 -> idx 4)
        assert app.backend.dmx.frame[0][29] == 255  # RGB red (addr 30 -> idx 29)

        # Step back to Cue 1 (blackout) via sequence_minus
        main_pb.sequence_minus()
        assert dev10.intensity == pytest.approx(0.0)
        assert dev11.intensity == pytest.approx(0.0)
        assert app.backend.dmx.frame[0][4] == 0
        assert app.backend.dmx.frame[0][29] == 0

        # Reload Cue 2, then jump directly to Cue 0
        main_pb.load_step(2)
        assert dev10.intensity == pytest.approx(1.0)
        assert dev11.intensity == pytest.approx(1.0)
        main_pb.load_step(0)
        assert dev10.intensity == pytest.approx(0.0)
        assert dev11.intensity == pytest.approx(0.0)
        assert app.backend.dmx.frame[0][4] == 0
        assert app.backend.dmx.frame[0][29] == 0
    finally:
        app.stop()


@pytest.mark.parametrize("mib_enabled", [False, True])
def test_thread_goback_fades_device_intensity_to_zero_and_finalizes(
    mib_enabled: bool,
) -> None:
    """Verify ThreadGoBack fades device intensities to 0.0 and finalizes cleanly."""
    from olc.devices.builtin import (  # pylint: disable=import-outside-toplevel
        create_moving_head_definition,
        create_rgb_definition,
    )
    from olc.show.sequence_threads import (  # pylint: disable=import-outside-toplevel
        ThreadGoBack,
    )

    app = _make_app()
    assert app.backend is not None
    try:
        dev10 = app.lightshow.patch.patch_device(
            10, create_moving_head_definition(), universe=1, address=1
        )
        dev11 = app.lightshow.patch.patch_device(
            11, create_rgb_definition(), universe=1, address=30
        )
        app.lightshow.patch.update_numpy_cache_if_dirty()

        main_pb = app.lightshow.main_playback
        main_pb.mib_enabled = mib_enabled
        _populate_seq(
            main_pb,
            [
                (1.0, {}, {}),
                (
                    2.0,
                    {10: 1.0, 11: 1.0},
                    {
                        10: {"intensity": 1.0, "pan": 45.0},
                        11: {"intensity": 1.0, "color": "#ff0000"},
                    },
                ),
            ],
        )

        # GoBack from Cue 2 to Cue 1 (blackout)
        main_pb.load_step(2)
        tgb = ThreadGoBack(main_pb)
        tgb._capture_start_levels()
        tgb.update_levels(go_back_time=2000.0, i=1000.0, position=2)
        assert dev10.intensity == pytest.approx(0.5, abs=0.05)
        assert dev11.intensity == pytest.approx(0.5, abs=0.05)

        tgb._finalize_goback(1)
        assert dev10.intensity == pytest.approx(0.0)
        assert dev11.intensity == pytest.approx(0.0)
        assert app.backend.dmx.frame[0][4] == 0
        assert app.backend.dmx.frame[0][29] == 0

        # GoBack from Cue 1 (or Cue 2) to Cue 0
        main_pb.load_step(2)
        tgb0 = ThreadGoBack(main_pb)
        tgb0._capture_start_levels()
        tgb0.update_levels(go_back_time=2000.0, i=1000.0, position=1)
        assert dev10.intensity == pytest.approx(0.5, abs=0.05)
        assert dev11.intensity == pytest.approx(0.5, abs=0.05)

        tgb0._finalize_goback(0)
        assert dev10.intensity == pytest.approx(0.0)
        assert dev11.intensity == pytest.approx(0.0)
        assert app.backend.dmx.frame[0][4] == 0
        assert app.backend.dmx.frame[0][29] == 0
    finally:
        app.stop()


def test_sequence_backward_with_intensity_only_in_device_values() -> None:
    """Verify stepping back updates device intensity even if cue.channels is empty."""
    from olc.devices.builtin import (  # pylint: disable=import-outside-toplevel
        create_moving_head_definition,
        create_rgb_definition,
    )

    app = _make_app()
    assert app.backend is not None
    try:
        dev10 = app.lightshow.patch.patch_device(
            10, create_moving_head_definition(), universe=1, address=1
        )
        dev11 = app.lightshow.patch.patch_device(
            11, create_rgb_definition(), universe=1, address=30
        )
        app.lightshow.patch.update_numpy_cache_if_dirty()

        main_pb = app.lightshow.main_playback
        _populate_seq(
            main_pb,
            [
                (1.0, {}, {10: {"intensity": 0.25}, 11: {"intensity": 0.5}}),
                (2.0, {}, {10: {"intensity": 1.0}, 11: {"intensity": 1.0}}),
            ],
        )

        main_pb.load_step(2)
        assert dev10.intensity == pytest.approx(1.0)
        assert dev11.intensity == pytest.approx(1.0)

        main_pb.sequence_minus()
        assert dev10.intensity == pytest.approx(0.25)
        assert dev11.intensity == pytest.approx(0.5)

        main_pb.sequence_minus()
        assert dev10.intensity == pytest.approx(0.0)
        assert dev11.intensity == pytest.approx(0.0)
        assert app.backend.dmx.frame[0][4] == 0
        assert app.backend.dmx.frame[0][29] == 0
    finally:
        app.stop()
