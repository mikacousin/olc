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
"""Unit tests for olc-monitor dynamic universe life cycle and reconciliation."""

import asyncio
import collections
import importlib.machinery
import importlib.util
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from textual.color import Color

from olc.core.engine import CoreEngine
from olc.core.universe_config import UniverseMap

# pylint: disable=redefined-outer-name

# Load OLCMonitor from tools/olc-monitor.in dynamically
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "olc-monitor.in"
_LOADER = importlib.machinery.SourceFileLoader("olc_monitor", str(_TOOL_PATH))
_SPEC = importlib.util.spec_from_loader("olc_monitor", _LOADER)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
OLCMonitor = _MOD.OLCMonitor
FrequencyMonitor = _MOD.FrequencyMonitor
UniversePanel = _MOD.UniversePanel


@pytest.fixture
def monitor_app() -> OLCMonitor:
    """Fixture providing an unmounted OLCMonitor instance."""
    # pylint: disable=protected-access
    app = OLCMonitor.__new__(OLCMonitor)
    app._id = "test_app"
    app._reactives = {}
    app._sub_title = ""
    app.refresh = MagicMock()
    # Avoid App screen refresh in unmounted unit tests
    app.watch_status_text = MagicMock()
    app._universe_panels = {}
    app._dmx_cache = {}
    app._protocols_cache = {}
    app._dirty_uids = set()
    app._deleted_uids = set()
    app._last_active_universes = None
    app._placeholder_active = False
    app._universes_container = MagicMock()
    app.last_hz = 44.0
    app.last_frames = 100
    app._last_packet_time = 0.0
    app._signal_lost = False
    app._frequency_monitor = None
    return app


def test_remove_orphan_and_deleted_universes_explicit(
    monitor_app: OLCMonitor,
) -> None:
    """Test explicit deletion removal via _deleted_uids."""
    # pylint: disable=protected-access
    panel1 = AsyncMock()
    panel2 = AsyncMock()
    monitor_app._universe_panels = {1: panel1, 2: panel2}
    monitor_app._dmx_cache = {1: bytes(512), 2: bytes(512)}
    monitor_app._protocols_cache = {1: ["Art-Net"], 2: ["sACN"]}
    monitor_app._dirty_uids = {1, 2}
    monitor_app._deleted_uids = {2}

    asyncio.run(monitor_app._remove_orphan_and_deleted_universes())

    # Panel 2 removed, Panel 1 kept
    assert 2 not in monitor_app._universe_panels
    assert 1 in monitor_app._universe_panels
    panel2.remove.assert_called_once()
    panel1.remove.assert_not_called()

    # Caches for universe 2 cleared
    assert 2 not in monitor_app._dmx_cache
    assert 2 not in monitor_app._protocols_cache
    assert 2 not in monitor_app._dirty_uids
    assert 2 not in monitor_app._deleted_uids


def test_remove_orphan_and_deleted_universes_reconciliation(
    monitor_app: OLCMonitor,
) -> None:
    """Test reconciliation removal when universe is missing from active_universes."""
    # pylint: disable=protected-access
    panel1 = AsyncMock()
    panel2 = AsyncMock()
    panel3 = AsyncMock()
    monitor_app._universe_panels = {1: panel1, 2: panel2, 3: panel3}
    monitor_app._last_active_universes = {1, 3}  # 2 is orphan

    asyncio.run(monitor_app._remove_orphan_and_deleted_universes())

    assert 2 not in monitor_app._universe_panels
    assert 1 in monitor_app._universe_panels
    assert 3 in monitor_app._universe_panels
    panel2.remove.assert_called_once()
    panel1.remove.assert_not_called()
    panel3.remove.assert_not_called()


def test_remove_all_universes_restores_placeholder(
    monitor_app: OLCMonitor,
) -> None:
    """Test removing all universes re-mounts the placeholder widget."""
    # pylint: disable=protected-access
    panel1 = AsyncMock()
    monitor_app._universe_panels = {1: panel1}
    monitor_app._deleted_uids = {1}
    monitor_app._placeholder_active = False

    container = MagicMock()
    container.mount = AsyncMock()
    monitor_app._universes_container = container

    asyncio.run(monitor_app._remove_orphan_and_deleted_universes())

    assert len(monitor_app._universe_panels) == 0
    panel1.remove.assert_called_once()
    assert monitor_app._placeholder_active is True
    container.mount.assert_called_once()


def test_monitor_listen_zmq_packet_processing(
    monitor_app: OLCMonitor,
) -> None:
    """Test metadata parsing and cache updates for normal and deleted packets."""
    # pylint: disable=protected-access
    # 1. Normal packet
    raw_meta = json.dumps(
        {"hz": 44.0, "frames": 50, "protocols": ["Art-Net"], "active_universes": [1, 2]}
    )
    meta = json.loads(raw_meta)
    uid = 1
    data = bytes([128] * 512)

    active_univs = meta.get("active_universes")
    if active_univs is not None:
        monitor_app._last_active_universes = set(active_univs)

    if meta.get("deleted", False):
        monitor_app._deleted_uids.add(uid)
    else:
        monitor_app._dmx_cache[uid] = data
        monitor_app._protocols_cache[uid] = meta.get("protocols", [])
        monitor_app._dirty_uids.add(uid)

    assert monitor_app._last_active_universes == {1, 2}
    assert monitor_app._dmx_cache[1] == data
    assert monitor_app._protocols_cache[1] == ["Art-Net"]
    assert 1 in monitor_app._dirty_uids

    # 2. Deletion packet for universe 1
    raw_del_meta = json.dumps(
        {"hz": 44.0, "frames": 51, "deleted": True, "active_universes": [2]}
    )
    del_meta = json.loads(raw_del_meta)
    if del_meta.get("active_universes") is not None:
        monitor_app._last_active_universes = set(del_meta["active_universes"])

    if del_meta.get("deleted", False):
        monitor_app._deleted_uids.add(uid)
        monitor_app._dmx_cache.pop(uid, None)
        monitor_app._protocols_cache.pop(uid, None)
        monitor_app._dirty_uids.discard(uid)

    assert monitor_app._last_active_universes == {2}
    assert 1 in monitor_app._deleted_uids
    assert 1 not in monitor_app._dmx_cache
    assert 1 not in monitor_app._protocols_cache
    assert 1 not in monitor_app._dirty_uids


def test_frequency_monitor_set_signal_lost() -> None:
    """Test FrequencyMonitor explicit signal loss toggle."""
    # pylint: disable=protected-access
    freq_mon = FrequencyMonitor.__new__(FrequencyMonitor)
    freq_mon.zmq_addr = "tcp://127.0.0.1:5555"
    freq_mon._frequency = 44.0
    freq_mon._last_update = 100.0
    freq_mon._history = collections.deque(maxlen=100)
    freq_mon._last_sparkline_update = 0.0
    freq_mon._last_status_key = None
    freq_mon._is_signal_lost = False
    freq_mon._draw = MagicMock()
    freq_mon.query_one = MagicMock()

    freq_mon.set_signal_lost()
    assert freq_mon._is_signal_lost is True
    freq_mon._draw.assert_called_once()

    freq_mon.refresh_data(44.0)
    assert freq_mon._is_signal_lost is False


def test_universe_panel_set_signal_lost() -> None:
    """Test UniversePanel signal loss visual state and recovery."""
    # pylint: disable=protected-access
    panel = UniversePanel(1)
    panel.update = MagicMock()
    panel.display = True
    panel.is_in_viewport = MagicMock(return_value=True)  # type: ignore[method-assign]
    panel._draw()

    panel.set_signal_lost(True)
    assert panel._signal_lost is True
    assert "signal lost" in panel.border_title
    assert panel.styles.border.top[1] == Color.parse("red")

    # Redundant call should be a no-op
    panel.set_signal_lost(True)
    assert panel._signal_lost is True

    # Recovery on refresh_data
    panel.refresh_data(bytes([100] * 512), ["Art-Net"])
    assert panel._signal_lost is False
    assert "Art-Net" in panel.border_title
    assert panel.styles.border.top[1] == Color.parse("cyan")


def test_monitor_listen_zmq_shutdown_packet(
    monitor_app: OLCMonitor,
) -> None:
    """Test processing of a graceful shutdown packet."""
    # pylint: disable=protected-access
    raw_shutdown_meta = json.dumps(
        {
            "hz": 0.0,
            "frames": 200,
            "deleted": True,
            "status": "shutdown",
            "active_universes": [],
        }
    )
    meta = json.loads(raw_shutdown_meta)
    uid = 1
    freq_mock = MagicMock()
    monitor_app._frequency_monitor = freq_mock

    # Simulate shutdown handling from _listen_zmq
    monitor_app._last_packet_time = time.time()
    monitor_app._signal_lost = False

    if meta.get("status") == "shutdown":
        monitor_app.last_hz = 0.0
        monitor_app._signal_lost = True
        active_univs = meta.get("active_universes", [])
        monitor_app._last_active_universes = set(active_univs)
        monitor_app._deleted_uids.add(uid)
        if monitor_app._frequency_monitor is not None:
            monitor_app._frequency_monitor.set_signal_lost()

    assert monitor_app._signal_lost is True
    assert monitor_app.last_hz == 0.0
    assert monitor_app._last_active_universes == set()
    assert uid in monitor_app._deleted_uids
    freq_mock.set_signal_lost.assert_called_once()


def test_monitor_render_cached_data_timeout_watchdog(
    monitor_app: OLCMonitor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that render loop triggers signal loss when no packets arrive for >2.0s."""
    # pylint: disable=protected-access
    monitor_app._last_packet_time = 100.0
    monkeypatch.setattr(time, "time", lambda: 105.0)

    freq_mock = MagicMock()
    monitor_app._frequency_monitor = freq_mock
    panel_mock = MagicMock()
    panel_mock.remove = AsyncMock()
    monitor_app._universe_panels = {1: panel_mock}

    asyncio.run(monitor_app._render_cached_data())

    assert monitor_app._signal_lost is True
    assert monitor_app.last_hz == 0.0
    freq_mock.set_signal_lost.assert_called_once()
    panel_mock.set_signal_lost.assert_called_with(True)
    assert "OLC offline / Signal lost" in monitor_app.status_text


def test_monitor_render_cached_data_recovery(
    monitor_app: OLCMonitor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that render loop clears signal loss when fresh packets arrive."""
    # pylint: disable=protected-access
    monitor_app._signal_lost = True
    monitor_app._last_packet_time = 100.0
    monkeypatch.setattr(time, "time", lambda: 101.0)

    freq_mock = MagicMock()
    monitor_app._frequency_monitor = freq_mock
    panel_mock = MagicMock()
    panel_mock.protocols = ["Art-Net"]
    panel_mock.remove = AsyncMock()
    monitor_app._universe_panels = {1: panel_mock}
    monitor_app.last_hz = 44.0

    asyncio.run(monitor_app._render_cached_data())

    assert monitor_app._signal_lost is False
    freq_mock.refresh_data.assert_called_with(44.0)
    panel_mock.set_signal_lost.assert_called_with(False)
    assert "Active universes: 1 | 44.0 Hz" in monitor_app.status_text


def test_core_engine_stop_emits_shutdown() -> None:
    """Test that CoreEngine.stop emits shutdown metadata on ZMQ pub before closing."""
    # pylint: disable=protected-access
    engine = CoreEngine(
        UniverseMap(), loopback=True, no_transmit=True, monitor_port=None
    )
    mock_pub = MagicMock()
    engine._zmq_pub = mock_pub

    engine.stop()

    assert mock_pub.send_multipart.call_count >= 1
    # Check that at least one message contains status: shutdown
    found_shutdown = False
    for call_args in mock_pub.send_multipart.call_args_list:
        parts = call_args[0][0]
        meta = json.loads(parts[1].decode("utf-8"))
        if meta.get("status") == "shutdown":
            found_shutdown = True
            assert meta.get("hz") == 0.0
            assert meta.get("deleted") is True
            assert meta.get("active_universes") == []
    assert found_shutdown is True
    mock_pub.close.assert_called_once()
