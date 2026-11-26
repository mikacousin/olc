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
"""Tests for GoboLibrary, Eos ASCII gobo import, .olc, and inspector tiles."""

from __future__ import annotations

import pathlib
import struct
import zlib
from unittest.mock import MagicMock

import pytest
from gi.repository import Gio

from olc.core.app import CoreApplication
from olc.devices.channel import Channel, ChannelRange, ChannelType, FixtureType
from olc.devices.device import LightingDevice
from olc.devices.gobo import (
    BUILTIN_GOBO_IDS,
    GoboAsset,
    decode_eos_resource_hex,
    resolve_builtin_gobo,
)
from olc.files.file_type import FileType
from olc.files.import_file import ImportFile


def test_resolve_builtin_gobo_keywords_and_fallback() -> None:
    """Keyword matching maps common gobo names; unknown names fall back by slot."""
    assert resolve_builtin_gobo("Open", 0) == "builtin:open"
    assert resolve_builtin_gobo("Star Field", 3) == "builtin:stars"
    assert resolve_builtin_gobo("Leaf Breakup", 2) == "builtin:breakup"
    assert resolve_builtin_gobo("Unknown Custom", 0) == "builtin:open"
    assert resolve_builtin_gobo("Unknown Custom", 1) in BUILTIN_GOBO_IDS[1:]


def test_decode_eos_resource_hex_qt_qcompress() -> None:
    """decode_eos_resource_hex strips 4-byte BE size header and decompresses zlib."""
    payload = b"\x89PNG\r\n\x1a\nfake-png-body"
    header = struct.pack(">I", len(payload))
    hex_str = (header + zlib.compress(payload)).hex().upper()
    assert decode_eos_resource_hex(hex_str) == payload
    assert decode_eos_resource_hex("not-hex") is None


def test_eos_show_asc_extracts_gobos_and_populates_default_gobo_slots() -> None:
    """Importing eos_show.asc extracts $Resource gobos and builds Gobo_Select ranges."""
    asc_path = pathlib.Path(__file__).parent / "data" / "eos_show.asc"
    app = CoreApplication(MagicMock())
    imp = ImportFile(
        app.lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imp.parse_sync(auto_import=True)

    assert len(app.lightshow.gobo_library) >= 1
    first_asset = app.lightshow.gobo_library.all()[0]
    assert first_asset.ext == "png"
    assert first_asset.data.startswith(b"\x89PNG")

    gobo_devs = [
        d
        for d in app.lightshow.patch.devices.values()
        if d.get_channel(ChannelType.GOBO_WHEEL) is not None
    ]
    assert len(gobo_devs) >= 1
    gobo_ch = gobo_devs[0].get_channel(ChannelType.GOBO_WHEEL)
    assert gobo_ch is not None
    assert len(gobo_ch.ranges) >= 2
    assert gobo_ch.ranges[0].label == "Open"


def test_olc_persistence_gobo_library_and_static_gobo(tmp_path: pathlib.Path) -> None:
    """Verify .olc round-trip for GoboLibrary, ChannelRange.gobo_id, and device.gobo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    asset = GoboAsset(
        gobo_id="cid-123", name="Custom Star", data=b"\x89PNG\r\n\x1a\ntest", ext="png"
    )
    app.lightshow.gobo_library.add(asset)

    mover = LightingDevice(
        fixture_id=1,
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
                        "Star", ChannelType.GOBO_WHEEL, 128, 255, gobo_id="cid-123"
                    ),
                ],
            )
        ],
    )
    fixed = LightingDevice(
        fixture_id=2,
        label="Decoupe",
        fixture_type=FixtureType.DIMMER,
        channels=[Channel(ChannelType.INTENSITY, 1, 2)],
        static_gobo="builtin:breakup",
    )
    app.lightshow.patch.devices[1] = mover
    app.lightshow.patch.devices[2] = fixed

    save_path = tmp_path / "gobos.olc"
    app.action_registry.execute("show.save", str(save_path))

    app2 = CoreApplication(settings)
    app2.action_registry.execute("show.open", str(save_path))
    re_asset = app2.lightshow.gobo_library.get("cid-123")
    assert re_asset is not None
    assert re_asset.data == asset.data

    re_mover = app2.lightshow.patch.get_device(1)
    assert re_mover is not None
    ch = re_mover.get_channel(ChannelType.GOBO_WHEEL)
    assert ch is not None
    assert ch.ranges[1].gobo_id == "cid-123"

    re_fixed = app2.lightshow.patch.get_device(2)
    assert re_fixed is not None
    assert re_fixed.static_gobo == "builtin:breakup"


@pytest.mark.gui
def test_device_inspector_displays_and_applies_gobo_tiles() -> None:
    """DeviceInspectorWidget renders gobo tiles and clicking applies the gobo slot."""
    from gi.repository import Gtk

    from olc.gtk3.device_inspector import DeviceInspectorWidget

    core = CoreApplication(MagicMock())
    dev = LightingDevice(
        fixture_id=10,
        label="Spot 10",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 1),
            Channel(
                ChannelType.GOBO_WHEEL,
                1,
                2,
                ranges=[
                    ChannelRange(
                        "Open", ChannelType.GOBO_WHEEL, 0, 84, gobo_id="builtin:open"
                    ),
                    ChannelRange(
                        "Stars",
                        ChannelType.GOBO_WHEEL,
                        85,
                        170,
                        gobo_id="builtin:stars",
                    ),
                    ChannelRange(
                        "Bars", ChannelType.GOBO_WHEEL, 171, 255, gobo_id="builtin:bars"
                    ),
                ],
            ),
        ],
    )
    core.lightshow.patch.devices[10] = dev

    mock_gtk_app = MagicMock()
    mock_gtk_app.core = core
    inspector = DeviceInspectorWidget(app=mock_gtk_app)
    win = Gtk.Window()
    win.add(inspector)
    win.show_all()

    inspector.set_selected_channels([10])
    while Gtk.events_pending():
        Gtk.main_iteration()

    children = inspector.gobo_flowbox.get_children()
    assert len(children) == 3
    # Click "Stars" tile (index 1)
    flow_child = children[1]
    assert isinstance(flow_child, Gtk.FlowBoxChild)
    btn = flow_child.get_child()
    assert isinstance(btn, Gtk.Button)
    btn.clicked()
    while Gtk.events_pending():
        Gtk.main_iteration()

    gobo_ch = dev.get_channel(ChannelType.GOBO_WHEEL)
    assert gobo_ch is not None
    assert gobo_ch.value == 127  # midpoint of [85, 170]
    win.destroy()
