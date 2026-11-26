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
"""Tests for the patch snapshot served to external viewers (olc-viz)."""

import json
import socket
import time
from types import SimpleNamespace

import pytest
import zmq

from olc.dmx_engine.engine import CoreEngine
from olc.dmx_engine.patch_snapshot import (
    SNAPSHOT_REQUEST,
    PatchSnapshotServer,
    build_snapshot,
)
from olc.dmx_engine.universe_config import UniverseMap


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _device(
    fixture_id: int, universe: int, address: int, footprint: int, **kw: str
) -> SimpleNamespace:
    channels = [
        SimpleNamespace(universe=universe, address=address + i)
        for i in range(footprint)
    ]
    return SimpleNamespace(
        fixture_id=fixture_id,
        label=kw.get("label", f"Dev {fixture_id}"),
        manufacturer=kw.get("manufacturer", "Robe"),
        model=kw.get("model", "Robin 600"),
        mode_name=kw.get("mode_name", "Mode 1"),
        gdtf_id=kw.get("gdtf_id", ""),
        universe=universe,
        address=address,
        channels=channels,
    )


def _request_snapshot(port: int) -> dict:
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.connect(f"tcp://127.0.0.1:{port}")
    try:
        sock.send(SNAPSHOT_REQUEST)
        return json.loads(sock.recv())
    finally:
        sock.close()
        ctx.term()


def test_build_snapshot_describes_devices_sorted_by_id() -> None:
    """Rows carry the fields olc-viz needs and are sorted by fixture id."""
    devices = [
        _device(101, 2, 17, 24, gdtf_id="Robe@Robin600"),
        _device(5, 1, 5, 1, manufacturer="Generic", model="Dimmer"),
    ]
    snap = json.loads(build_snapshot(devices, version=7))
    assert snap["version"] == 7
    assert [d["id"] for d in snap["devices"]] == [5, 101]
    robin = snap["devices"][1]
    assert robin["universe"] == 2
    assert robin["address"] == 17
    assert robin["footprint"] == 24
    assert robin["gdtf"] == "Robe@Robin600"
    assert robin["mode"] == "Mode 1"


def test_footprint_counts_primary_universe_only() -> None:
    """A dimmer patched on several outputs reports its primary universe span."""
    dev = _device(3, 1, 10, 1)
    dev.channels.append(SimpleNamespace(universe=2, address=400))
    row = json.loads(build_snapshot([dev], 1))["devices"][0]
    assert (row["universe"], row["address"], row["footprint"]) == (1, 10, 1)


def test_update_bumps_version() -> None:
    """Each update publishes a strictly newer version."""
    server = PatchSnapshotServer(_free_port())
    assert server.version == 0
    first = server.update([])
    second = server.update([_device(1, 1, 1, 1)])
    assert 0 < first < second == server.version


def test_server_answers_snapshot_requests() -> None:
    """A REQ client receives the latest snapshot; unknown requests get {}."""
    port = _free_port()
    server = PatchSnapshotServer(port)
    server.start()
    try:
        assert _request_snapshot(port)["devices"] == []
        version = server.update([_device(101, 2, 17, 24)])
        snap = _request_snapshot(port)
        assert snap["version"] == version
        assert snap["devices"][0]["id"] == 101
    finally:
        server.stop()


def test_server_start_fails_when_port_is_taken() -> None:
    """A port conflict is reported instead of being silently ignored."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        server = PatchSnapshotServer(int(s.getsockname()[1]))
        with pytest.raises(zmq.ZMQError):
            server.start()


def test_engine_announces_patch_version_in_monitor_metadata() -> None:
    """Monitor frames carry patch_version, and it changes with publish_patch."""
    port = _free_port() - 1  # the snapshot server uses monitor_port + 1
    engine = CoreEngine(
        UniverseMap(1), loopback=True, no_listen=True, monitor_port=port
    )
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.LINGER, 0)
    sub.setsockopt(zmq.SUBSCRIBE, b"universe:")
    sub.setsockopt(zmq.RCVTIMEO, 3000)
    sub.connect(f"tcp://127.0.0.1:{port}")

    def next_patch_version() -> int:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            _topic, meta, _data = sub.recv_multipart()
            version = json.loads(meta).get("patch_version")
            if version is not None:
                return int(version)
        raise AssertionError("no patch_version received")

    try:
        engine.start()
        first = next_patch_version()
        engine.publish_patch([_device(1, 1, 1, 1)])
        deadline = time.monotonic() + 5.0
        latest = first
        while latest == first and time.monotonic() < deadline:
            latest = next_patch_version()
        assert latest > first
        assert _request_snapshot(port + 1)["version"] == latest
    finally:
        sub.close()
        ctx.term()
        engine.stop()


def test_build_snapshot_includes_stage_3d_and_optical_channels() -> None:
    """Snapshot exposes stage floor/fog, device 3D coords, and full DMX channel map."""
    from olc.devices.channel import Channel, ChannelType, FixtureType
    from olc.devices.device import LightingDevice
    from olc.show.lightshow import StageConfig

    stage = StageConfig(
        width=16.0, depth=12.0, color="#1a1a1f", grid_spacing=0.5, fog_density=0.6
    )
    spot = LightingDevice(
        fixture_id=101,
        label="Face 1",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 1),
            Channel(
                ChannelType.PAN,
                1,
                2,
                physical_min=-270.0,
                physical_max=270.0,
            ),
            Channel(ChannelType.PAN, 1, 3, fine=True),
            Channel(ChannelType.ZOOM, 1, 4, physical_min=10.0, physical_max=50.0),
        ],
        position=(-2.5, -4.0, 6.0),
        focus_point=(0.0, 1.0, 1.5),
        orientation=(0.0, 0.0, 180.0),
        beam_angle=20.0,
    )
    multi_dimmer = LightingDevice(
        fixture_id=5,
        label="Duo Dim",
        fixture_type=FixtureType.DIMMER,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 20),
            Channel(ChannelType.INTENSITY, 2, 100),
        ],
    )

    snap = json.loads(build_snapshot([spot, multi_dimmer], version=3, stage=stage))
    assert snap["stage"] == {
        "width": 16.0,
        "depth": 12.0,
        "color": "#1a1a1f",
        "grid_spacing": 0.5,
        "fog_density": 0.6,
    }

    d5, d101 = snap["devices"]
    assert d5["id"] == 5
    assert d5["fixture_type"] == "dimmer"
    assert [(c["universe"], c["address"]) for c in d5["channels"]] == [
        (1, 20),
        (2, 100),
    ]

    assert d101["id"] == 101
    assert d101["fixture_type"] == "moving_head"
    assert d101["position"] == [-2.5, -4.0, 6.0]
    assert d101["focus_point"] == [0.0, 1.0, 1.5]
    assert d101["orientation"] == [0.0, 0.0, 180.0]
    assert d101["beam_angle"] == 20.0
    assert d101["channels"] == [
        {"type": "intensity", "universe": 1, "address": 1, "label": "intensity"},
        {
            "type": "pan",
            "universe": 1,
            "address": 2,
            "label": "pan",
            "physical_min": -270.0,
            "physical_max": 270.0,
        },
        {"type": "pan", "universe": 1, "address": 3, "label": "pan", "fine": True},
        {
            "type": "zoom",
            "universe": 1,
            "address": 4,
            "label": "zoom",
            "physical_min": 10.0,
            "physical_max": 50.0,
        },
    ]


def test_set_focus_and_set_stage_commands_over_zmq_and_undo() -> None:
    """REQ commands set_focus (fixed + moving head IK) & set_stage update CoreApp."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication
    from olc.devices.channel import Channel, ChannelType, FixtureType
    from olc.devices.device import LightingDevice

    port = _free_port() - 1
    app = CoreApplication(MagicMock())

    fixed = LightingDevice(
        fixture_id=10,
        label="Face",
        fixture_type=FixtureType.DIMMER,
        channels=[Channel(ChannelType.INTENSITY, 1, 1)],
        position=(0.0, -4.0, 4.0),
    )
    mover = LightingDevice(
        fixture_id=20,
        label="Spot",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 2),
            Channel(ChannelType.PAN, 1, 3, physical_min=-270.0, physical_max=270.0),
            Channel(ChannelType.TILT, 1, 4, physical_min=-135.0, physical_max=135.0),
        ],
        position=(0.0, 0.0, 4.0),
    )
    app.lightshow.patch.devices[10] = fixed
    app.lightshow.patch.devices[20] = mover

    engine = app.init_engine(monitor_port=port, no_listen=True, no_transmit=True)
    engine.start()

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.connect(f"tcp://127.0.0.1:{port + 1}")
    try:
        # 1. Fixed fixture preview (commit=False -> not added to undo stack)
        sock.send_json(
            {
                "cmd": "set_focus",
                "device_id": 10,
                "target": [1.0, 2.0, 0.0],
                "commit": False,
            }
        )
        rep = json.loads(sock.recv())
        assert rep["ok"] is True
        assert fixed.focus_point == pytest.approx((1.0, 2.0, 0.0))
        assert len(app.history.undo_stack) == 0

        # 2. Moving head commit=True -> updates focus_point, pan/tilt, and undo stack
        sock.send_json(
            {
                "cmd": "set_focus",
                "device_id": 20,
                "target": [0.0, 4.0, 0.0],
                "commit": True,
            }
        )
        rep = json.loads(sock.recv())
        assert rep["ok"] is True
        assert mover.focus_point == pytest.approx((0.0, 4.0, 0.0))
        assert mover.pan_degrees == pytest.approx(0.0, abs=1.5)
        assert mover.tilt_degrees == pytest.approx(45.0, abs=1.5)
        assert len(app.history.undo_stack) == 1

        app.history.undo()
        assert mover.focus_point == pytest.approx((0.0, 0.0, 0.0))
        app.history.redo()
        assert mover.focus_point == pytest.approx((0.0, 4.0, 0.0))

        # 3. Stage fog update
        sock.send_json({"cmd": "set_stage", "fog_density": 0.8, "commit": True})
        rep = json.loads(sock.recv())
        assert rep["ok"] is True
        assert app.lightshow.stage.fog_density == pytest.approx(0.8)
    finally:
        sock.close()
        ctx.term()
        engine.stop()


def test_device_set_3d_action_and_undo_redo() -> None:
    """Verify device.set_3d updates 3D geometry and supports Undo/Redo."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication
    from olc.devices.channel import Channel, ChannelType, FixtureType
    from olc.devices.device import LightingDevice

    app = CoreApplication(MagicMock())
    dev = LightingDevice(
        fixture_id=7,
        label="Wash",
        fixture_type=FixtureType.LED_PAR,
        channels=[Channel(ChannelType.INTENSITY, 1, 1)],
    )
    app.lightshow.patch.devices[7] = dev

    app.action_registry.execute(
        "device.set_3d",
        7,
        position=(1.5, -2.0, 5.0),
        focus_point=(0.0, 1.0, 0.5),
        orientation=(0.0, 10.0, 0.0),
        beam_angle=40.0,
    )
    assert dev.position == pytest.approx((1.5, -2.0, 5.0))
    assert dev.focus_point == pytest.approx((0.0, 1.0, 0.5))
    assert dev.orientation == pytest.approx((0.0, 10.0, 0.0))
    assert dev.beam_angle == pytest.approx(40.0)

    app.history.undo()
    assert dev.position == pytest.approx((0.0, 0.0, 4.0))
    assert dev.beam_angle == pytest.approx(25.0)

    app.history.redo()
    assert dev.position == pytest.approx((1.5, -2.0, 5.0))
    assert dev.beam_angle == pytest.approx(40.0)


def test_snapshot_gobo_ranges_static_gobo_and_get_gobo_command() -> None:
    """Snapshot exports gobo ranges/static_gobo and get_gobo returns raw PNG bytes."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication
    from olc.devices.channel import Channel, ChannelRange, ChannelType, FixtureType
    from olc.devices.device import LightingDevice
    from olc.devices.gobo import GoboAsset

    port = _free_port() - 1
    app = CoreApplication(MagicMock())
    png_bytes = b"\x89PNG\r\n\x1a\nfake-gobo-png"
    app.lightshow.gobo_library.add(
        GoboAsset(gobo_id="cid-g1", name="Star", data=png_bytes, ext="png")
    )
    mover = LightingDevice(
        fixture_id=10,
        label="Spot",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(
                ChannelType.GOBO_WHEEL,
                1,
                1,
                ranges=[
                    ChannelRange(
                        "Open", ChannelType.GOBO_WHEEL, 0, 127, gobo_id="builtin:open"
                    ),
                    ChannelRange(
                        "Star", ChannelType.GOBO_WHEEL, 128, 255, gobo_id="cid-g1"
                    ),
                ],
            )
        ],
    )
    fixed = LightingDevice(
        fixture_id=11,
        label="Decoupe",
        fixture_type=FixtureType.DIMMER,
        channels=[Channel(ChannelType.INTENSITY, 1, 2)],
        static_gobo="builtin:breakup",
    )
    app.lightshow.patch.devices[10] = mover
    app.lightshow.patch.devices[11] = fixed

    engine = app.init_engine(monitor_port=port, no_listen=True, no_transmit=True)
    engine.start()
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.connect(f"tcp://127.0.0.1:{port + 1}")
    try:
        sock.send(SNAPSHOT_REQUEST)
        snap = json.loads(sock.recv())
        d10, d11 = snap["devices"]
        assert d10["channels"][0]["ranges"] == [
            {"label": "Open", "min": 0, "max": 127, "gobo_id": "builtin:open"},
            {"label": "Star", "min": 128, "max": 255, "gobo_id": "cid-g1"},
        ]
        assert d11["static_gobo"] == "builtin:breakup"

        sock.send_json({"cmd": "get_gobo", "id": "cid-g1"})
        assert sock.recv() == png_bytes
    finally:
        sock.close()
        ctx.term()
        engine.stop()
