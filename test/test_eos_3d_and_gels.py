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
"""Tests for Eos ASCII 3D metadata (position/orientation/beam) and gel import."""

from __future__ import annotations

import json
from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gio  # noqa: E402

from olc.devices.channel import Channel, ChannelType, FixtureType  # noqa: E402
from olc.devices.color_pick.gels import lookup_gel, resolve_gel_hex  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.dmx_engine.patch_snapshot import build_snapshot  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402


def test_gel_lookup_and_hex_resolution() -> None:
    """lookup_gel and resolve_gel_hex handle Lee/Rosco variants and unknown codes."""
    assert lookup_gel("L203") is not None
    assert lookup_gel("Lee 203") == lookup_gel("L203")
    assert lookup_gel("L500") is not None
    assert lookup_gel("R119") is not None
    assert lookup_gel("L2") == lookup_gel("L002")
    assert lookup_gel("UNKNOWN999") is None

    hex_l203 = resolve_gel_hex("L203")
    assert hex_l203.startswith("#") and len(hex_l203) == 7
    assert resolve_gel_hex("UNKNOWN999") == ""


def test_lighting_device_gel_roundtrip_and_snapshot() -> None:
    """LightingDevice persists gel/gel_color and exposes them in patch snapshot."""
    dev = LightingDevice(
        fixture_id=1,
        label="PC 1",
        fixture_type=FixtureType.DIMMER,
        channels=[Channel(ChannelType.INTENSITY, 1, 1)],
        gel="L203",
    )
    assert dev.effective_gel_color == resolve_gel_hex("L203")

    restored = LightingDevice.from_dict(dev.to_dict())
    assert restored.gel == "L203"
    assert restored.effective_gel_color == dev.effective_gel_color

    snap = json.loads(build_snapshot([restored], version=1).decode("utf-8"))
    row = snap["devices"][0]
    assert row["gel"] == "L203"
    assert row["gel_color"] == dev.effective_gel_color


def test_eos_ascii_imports_3d_position_orientation_beam_and_gels(
    tmp_path: Path,
) -> None:
    """AsciiParser imports $$Position, $$Orientation, BeamAngle, and $$TextGel."""
    asc = "\n".join(
        [
            "Ident 3:0",
            "Manufacturer ETC",
            "Console Eos",
            "$ParamType 1 1 Intens",
            "$ParamType 2 2 Pan",
            "$ParamType 3 2 Tilt",
            "$Personality 10",
            "   $$Manuf Robe",
            "   $$Model Spot1",
            "   $$Footprint 3",
            "   $$PersChan 1 1 1 0 0 100 0.0 100.0",
            "   $$PersChan 2 1 2 0 128 100 -270.0 270.0",
            "   $$PersChan 3 1 3 0 128 100 -135.0 135.0",
            "$Patch 1 10 1 1",
            "   $$Position 2.5 -1.5 6.0",
            "   $$Orientation 0 0 -90",
            "   $$Data BeamAngle 18",
            "$Patch 2 0 10 1",
            "   Text Face PC",
            "   $$TextGel L203",
            "   $$Position -3.0 -5.0 8.0",
            "   $$Orientation -30 0 0",
            "   $$Data BeamAngle 40",
            "$Patch 3 0 11 1",
            "   $$Position 1.78 1.76 0.1",
            "   $$Orientation 40 180 -45.39",
            "$Patch 4 0 12 1",
            "   $$Position 1.5 0.0 6.75",
            "   $$Orientation -27 0 90",
            "EndData",
        ]
    )
    asc_file = tmp_path / "eos_3d.asc"
    asc_file.write_text(asc, encoding="ascii")

    ls = LightShow()
    imported = ImportFile(ls, Gio.File.new_for_path(str(asc_file)), FileType.ASCII)
    imported.parse_sync(auto_import=True)

    dev1 = ls.patch.get_device(1)
    assert dev1 is not None
    assert dev1.position == pytest.approx((2.5, -1.5, 6.0))
    # Eos (rx=0, ry=0, rz=-90) -> OLC (yaw=-90, pitch=0, roll=0)
    assert dev1.orientation == pytest.approx((-90.0, 0.0, 0.0))
    assert dev1.beam_angle == pytest.approx(18.0)

    dev2 = ls.patch.get_device(2)
    assert dev2 is not None
    assert dev2.label == "Face PC"
    assert dev2.position == pytest.approx((-3.0, -5.0, 8.0))
    assert dev2.orientation == pytest.approx((0.0, 0.0, 30.0))
    # Tilted forward (roll=30 deg around X) -> focus_point shifts along +Y on z=0
    assert dev2.focus_point[2] == pytest.approx(0.0)
    assert dev2.focus_point[1] > -5.0
    assert dev2.beam_angle == pytest.approx(40.0)
    assert dev2.gel == "L203"
    assert dev2.effective_gel_color == resolve_gel_hex("L203")

    # Floor fixture at (+1.78, +1.76, 0.1) aimed upward and inward toward (0, 0)
    dev3 = ls.patch.get_device(3)
    assert dev3 is not None
    assert dev3.orientation == pytest.approx((-45.39, 180.0, -40.0))
    assert dev3.focus_point[0] < 1.78
    assert dev3.focus_point[1] < 1.76
    assert dev3.focus_point[2] > 0.1

    # Overhead ring fixture at (+1.5, 0.0, 6.75) aimed downward and inward toward (0, 0)
    dev4 = ls.patch.get_device(4)
    assert dev4 is not None
    assert dev4.orientation == pytest.approx((90.0, 0.0, 27.0))
    assert dev4.focus_point[0] < 1.5
    assert dev4.focus_point[2] == pytest.approx(0.0)
