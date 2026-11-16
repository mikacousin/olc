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
# pylint: disable=protected-access, comparison-with-callable
from unittest.mock import MagicMock

import numpy as np

import olc.show.lightshow  # noqa: F401  # Pre-import to resolve circular import cycle
from olc.core.app import CoreApplication
from olc.core.dmx_backend import DMXBackend
from olc.define import MAX_CHANNELS, UNIVERSES
from olc.dmx import Dmx
from olc.dmx_engine.universe_config import Protocol


def test_dmx_send_emits_outputs_changed() -> None:
    """Test Dmx.send() pushes frames to CoreEngine and emits dmx.outputs_changed."""
    # Mock lightshow and app
    lightshow = MagicMock()
    lightshow.patch.universes = list(UNIVERSES)
    lightshow.patch.is_patched.return_value = False
    lightshow.patch.is_patched_mask = np.zeros(MAX_CHANNELS, dtype=bool)
    lightshow.independents.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
    app = MagicMock()
    engine = MagicMock()
    lightshow.app = app
    app.engine = engine

    universe_buffers = {u: np.zeros(512, dtype=np.uint8) for u in UNIVERSES}

    def apply_universe_frame(uid: int, arr: np.ndarray) -> None:
        np.copyto(universe_buffers[uid], arr)

    engine.apply_universe_frame.side_effect = apply_universe_frame

    dmx = Dmx(backend=None, lightshow=lightshow)
    assert not hasattr(dmx, "thread")

    # Simulate change on Universe 1 (index 0) at address 0 and 10
    dmx.frame[0][0] = 255
    dmx.frame[0][10] = 128

    # Trigger send
    dmx.send()

    # Verify dmx.outputs_changed event was emitted directly via CoreApplication
    outputs_events = [
        call.args
        for call in app.emit.call_args_list
        if call.args and call.args[0] == "dmx.outputs_changed"
    ]
    assert outputs_events == [("dmx.outputs_changed", UNIVERSES[0], [0, 10])]

    # Verify old_frame and engine buffer were updated
    assert dmx._old_frame[0][0] == 255
    assert dmx._old_frame[0][10] == 128
    assert np.array_equal(universe_buffers[UNIVERSES[0]], dmx.frame[0])


def test_dmx_notification_event_and_native_patch_callbacks() -> None:
    """Test notification event emission and native PatchManager callback wiring."""
    lightshow = MagicMock()
    lightshow.patch.universes = [1, 2]
    app = MagicMock()
    engine = MagicMock()
    lightshow.app = app
    app.engine = engine

    dmx = Dmx(backend=None, lightshow=lightshow)

    # Patch callbacks must be wired automatically in Dmx.__init__
    assert lightshow.patch.on_patch_empty_cb == dmx.all_outputs_at_zero
    assert lightshow.patch.on_unpatch_cb == dmx._on_unpatch_output

    dmx.frame[0][4] = 200
    dmx._on_unpatch_output(0, 4)
    assert dmx.frame[0][4] == 0

    dmx.all_outputs_at_zero()
    assert engine.blackout.call_count == 2

    dmx.trigger_notification("Alert", "Test body")
    app.emit.assert_called_with("backend.notification", "Alert", "Test body")


def test_dmx_facade_methods() -> None:
    """Test unified DMX facade helpers on Dmx."""
    lightshow = MagicMock()
    lightshow.patch.universes = [1]
    lightshow.patch.is_patched_mask = np.zeros(MAX_CHANNELS, dtype=bool)
    lightshow.patch.map_src_channels = np.array([], dtype=np.intp)
    lightshow.patch.map_dst_curves = np.array([], dtype=np.intp)
    lightshow.patch.map_dst_universes = np.array([], dtype=np.intp)
    lightshow.patch.map_dst_outputs = np.array([], dtype=np.intp)
    lightshow.patch.dynamic_intensity_devices = []
    lightshow.patch.device_channel_refs = []
    lightshow.independents.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
    lightshow.park = None

    app = MagicMock()
    engine = MagicMock()
    engine.snapshot_universe.return_value = np.full(512, 42, dtype=np.uint8)
    lightshow.app = app
    app.engine = engine

    dmx = Dmx(backend=None, lightshow=lightshow)

    dmx.set_universe_levels(1, {0: 255, 5: 128})
    assert dmx.get_output_level(1, 1) == 255
    assert dmx.get_output_level(1, 6) == 128
    engine.set_channels.assert_called_once_with(1, {0: 255, 5: 128})

    snap = dmx.snapshot_universe(1)
    assert np.all(snap == 42)

    dmx.blackout_universe(1)
    assert np.all(dmx.frame[0] == 0)
    engine.blackout.assert_called_once_with(1)

    dmx.apply_universe_frame(1, snap)
    assert np.all(dmx.frame[0] == 42)
    engine.apply_universe_frame.assert_called_once_with(1, snap)

    dmx.levels["sequence"][0] = 200.0
    dmx.levels["user"][1] = 150
    dmx.levels["faders"][2] = 100.0
    dmx.main_fader.set_level(0.5)
    dmx.reset_levels()
    assert np.all(dmx.levels["sequence"] == 0)
    assert np.all(dmx.levels["user"] == -1)
    assert np.all(dmx.levels["faders"] == 0)
    assert dmx.main_fader.value == 1.0


def test_dmx_add_remove_universe() -> None:
    """Test dynamic addition and removal of universes in Dmx."""
    lightshow = MagicMock()
    lightshow.patch.universes = [1, 2, 3, 4]
    dmx = Dmx(backend=None, lightshow=lightshow)

    assert len(dmx.frame) == 4
    assert len(dmx._old_frame) == 4

    # Add universe 5
    lightshow.patch.universes.append(5)
    dmx.add_universe(5)
    assert len(dmx.frame) == 5
    assert len(dmx._old_frame) == 5
    assert dmx.frame[4].shape == (512,)

    # Remove universe 2 (index 1)
    dmx.send_user_output(1, 2, 255)
    assert (1, 2) in dmx.user_outputs

    idx_2 = lightshow.patch.universes.index(2)
    lightshow.patch.universes.remove(2)
    dmx.remove_universe(2, index=idx_2)
    assert len(dmx.frame) == 4
    assert len(dmx._old_frame) == 4
    assert (1, 2) not in dmx.user_outputs


def test_dmx_get_composite_level_tracking_and_manual_colors() -> None:
    """Test Dmx.get_composite_level tracking, manual, fader, and indep colors."""
    from olc.core.tracking import (  # pylint: disable=import-outside-toplevel
        TRACKING_COLORS,
        TrackingDisplayState,
    )
    from olc.show.cue import Cue  # pylint: disable=import-outside-toplevel
    from olc.show.sequence import Sequence  # pylint: disable=import-outside-toplevel
    from olc.show.step import Step  # pylint: disable=import-outside-toplevel

    lightshow = MagicMock()
    lightshow.patch.universes = [1]
    lightshow.independents.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)

    seq = Sequence(index=1, type_seq="Main")
    seq.tracking_mode = True
    seq.steps.clear()
    seq.steps.append(Step(sequence=1))
    seq.steps.append(Step(sequence=1, cue=Cue(1, 1.0, {1: 120, 2: 200})))
    seq.steps.append(Step(sequence=1, cue=Cue(1, 2.0, {2: 255, 3: 80})))
    seq.position = 2
    seq.on_go = False
    lightshow.main_playback = seq

    dmx = Dmx(backend=None, lightshow=lightshow)

    dmx.levels["sequence"][:3] = [120, 255, 80]

    # Channel 1: tracked from Step 1 -> Cyan (TRACKED_VALUE)
    assert dmx.get_composite_level(0) == (
        120,
        TRACKING_COLORS[TrackingDisplayState.TRACKED_VALUE],
    )

    # Channel 2: increased from 200 to 255 -> Blue (INTENSITY_UP)
    assert dmx.get_composite_level(1) == (
        255,
        TRACKING_COLORS[TrackingDisplayState.INTENSITY_UP],
    )

    # Manual operator override on Channel 1 -> Red/Coral (MANUAL)
    dmx.levels["user"][0] = 180
    assert dmx.get_composite_level(0) == (
        180,
        {"red": 0.95, "green": 0.35, "blue": 0.35},
    )

    # Manual override takes priority over higher fader
    dmx.levels["faders"][0] = 210
    assert dmx.get_composite_level(0) == (
        180,
        {"red": 0.95, "green": 0.35, "blue": 0.35},
    )

    # When manual override is released, higher HTP fader takes over -> Green
    dmx.levels["user"][0] = -1
    assert dmx.get_composite_level(0) == (
        210,
        {"red": 0.4, "green": 0.7, "blue": 0.4},
    )

    # Higher HTP independent overrides fader -> Indigo Blue
    lightshow.independents.dmx[0] = 240
    assert dmx.get_composite_level(0) == (
        240,
        {"red": 0.4, "green": 0.4, "blue": 0.7},
    )


def test_dmx_set_levels_pushes_synchronously_without_timer_thread() -> None:
    """Verify Dmx pushes updated frames and events synchronously in set_levels()."""
    app = CoreApplication(MagicMock())
    app.lightshow.patch.patch_empty()
    app.lightshow.patch.add_output(1, 1, 1)
    app.backend = DMXBackend(app.lightshow)
    app.init_engine(no_listen=True, no_transmit=True)
    assert app.engine is not None

    output_events: list[tuple[int, list[int]]] = []
    channel_events: list[list[int]] = []
    app.subscribe("dmx.outputs_changed", lambda u, o: output_events.append((u, o)))
    app.subscribe("channels.updated", channel_events.append)

    try:
        assert not hasattr(app.backend.dmx, "thread")
        app.backend.dmx.levels["user"][0] = 180.0 / 255.0
        app.backend.dmx.set_levels()

        assert app.engine.universe(1)[0] == 180
        assert (1, [0]) in output_events
        assert [1] in channel_events
    finally:
        app.engine.stop()


def test_dmx_in_htp_merge_and_non_overwrite_on_set_levels() -> None:
    """Verify Art-Net/sACN DMX-In HTP merges with console without overwriting."""
    app = CoreApplication(MagicMock())
    app.lightshow.patch.patch_empty()
    app.lightshow.patch.add_output(1, 1, 1)
    app.lightshow.patch.add_output(2, 2, 1)
    app.lightshow.universe_map.enable_protocol(1, Protocol.ARTNET)
    app.lightshow.universe_map.enable_protocol(1, Protocol.SACN)

    app.backend = DMXBackend(app.lightshow)
    app.init_engine(no_listen=False, no_transmit=True)
    assert app.engine is not None

    input_events: list[tuple[int, int, int, int]] = []
    app.subscribe(
        "dmx.input_received",
        lambda u, arr: input_events.append((u, int(arr[0]), int(arr[1]), int(arr[2]))),
    )

    try:
        dmx = app.backend.dmx
        dmx.levels["user"][0] = 100.0 / 255.0
        dmx.levels["user"][1] = 200.0 / 255.0
        dmx.set_levels()

        # Receive Art-Net frame on universe 1: ch1=220 (>100), ch2=120 (<200), ch3=90
        app.engine._on_artnet_dmx_received(1, [220, 120, 90])
        assert input_events[-1] == (1, 220, 120, 90)
        assert list(app.engine.universe(1).array[:3]) == [220, 200, 90]

        # Receive sACN frame on universe 1: HTP across Art-Net Rx, sACN Rx, and console
        app.engine._on_sacn_dmx_received(1, [150, 240, 0])
        assert input_events[-1] == (1, 220, 240, 90)
        assert list(app.engine.universe(1).array[:3]) == [220, 240, 90]

        # Subsequent console recalculation must preserve DMX-In HTP contribution
        dmx.set_levels()
        assert list(app.engine.universe(1).array[:3]) == [220, 240, 90]

        # Parked address must override both console and DMX-In
        app.lightshow.park.park_address(1, 1, 50)
        dmx.set_levels()
        assert list(app.engine.universe(1).array[:3]) == [50, 240, 90]

        # Dropping DMX-In back to 0 restores console level immediately
        app.engine._on_artnet_dmx_received(1, [0, 0, 0])
        app.engine._on_sacn_dmx_received(1, [0, 0, 0])
        assert list(app.engine.universe(1).array[:3]) == [50, 200, 0]
    finally:
        app.engine.stop()


def test_sub_8bit_precision_cli_to_16bit_dimmer() -> None:
    """Verify 0.1% CLI input preserves sub-8-bit precision on a 16-bit dimmer."""
    from olc.core.parser.executor import CommandExecutor
    from olc.core.parser.parser import CommandParser

    app = CoreApplication(MagicMock())
    patch = app.lightshow.patch
    patch.patch_empty()
    dev = patch.patch_dimmer(channel=1, universe=1, address=1, fine=True)
    assert dev.has_16bit_dimmer

    app.backend = DMXBackend(app.lightshow)
    dmx = app.backend.dmx
    parser = CommandParser()
    executor = CommandExecutor(app)

    res = executor.execute(parser.parse("1 AT 0.1"))
    assert res.success
    assert dmx.levels["user"][0] == 0.001
    # 0.001 * 65535 = 65.535 -> round = 66 -> coarse=0, fine=66
    assert dmx.frame[0][0] == 0
    assert dmx.frame[0][1] == 66
