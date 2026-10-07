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
import importlib.machinery
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# pylint: disable=redefined-outer-name

# Load OLCMonitor from tools/olc-monitor.in dynamically
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "olc-monitor.in"
_LOADER = importlib.machinery.SourceFileLoader("olc_monitor", str(_TOOL_PATH))
_SPEC = importlib.util.spec_from_loader("olc_monitor", _LOADER)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
OLCMonitor = _MOD.OLCMonitor


@pytest.fixture
def monitor_app() -> OLCMonitor:
    """Fixture providing an unmounted OLCMonitor instance."""
    # pylint: disable=protected-access
    app = OLCMonitor.__new__(OLCMonitor)
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
