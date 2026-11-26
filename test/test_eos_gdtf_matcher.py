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
"""Tests for Eos ASCII personality to local GDTF fixture matching and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gio  # noqa: E402

from olc.core.app import CoreApplication  # noqa: E402
from olc.core.dmx_backend import DMXBackend  # noqa: E402
from olc.devices.channel import ChannelRange, ChannelType, FixtureType  # noqa: E402
from olc.devices.fixture import (  # noqa: E402
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
    save_user_fixture,
)
from olc.devices.gobo import GoboAsset, save_user_gobo  # noqa: E402
from olc.files.ascii.gdtf_matcher import (  # noqa: E402
    MatchStatus,
    match_eos_personalities,
)
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402


def _make_gdtf_spot(
    *,
    manufacturer: str = "Robe lighting",
    model: str = "ROBIN T1 Profile",
    gdtf_id: str = "gdtf-t1-uuid",
    pan_bounds: tuple[float, float] = (-270.0, 270.0),
    swap_tilt_intensity: bool = False,
    omit_pan_fine: bool = False,
) -> FixtureDefinition:
    """Build a non-builtin GDTF FixtureDefinition with 2 modes (9ch & 10ch)."""
    g1_ranges = [
        ChannelRange("Open", ChannelType.GOBO_WHEEL, 0, 127, gobo_id="builtin:open"),
        ChannelRange(
            "G1 Stars",
            ChannelType.GOBO_WHEEL,
            128,
            255,
            gobo_id=f"gdtf:{gdtf_id}:G1Slot1",
        ),
    ]
    g2_ranges = [
        ChannelRange("Open", ChannelType.GOBO_WHEEL, 0, 127, gobo_id="builtin:open"),
        ChannelRange(
            "G2 Bars",
            ChannelType.GOBO_WHEEL,
            128,
            255,
            gobo_id=f"gdtf:{gdtf_id}:G2Slot1",
        ),
    ]
    ch_defs = [
        ChannelDefinition(
            ChannelType.PAN,
            0,
            label="Pan",
            fine_offset=None if omit_pan_fine else 1,
            physical_min=pan_bounds[0],
            physical_max=pan_bounds[1],
            physical_unit="deg",
        ),
        ChannelDefinition(
            ChannelType.INTENSITY if swap_tilt_intensity else ChannelType.TILT,
            2,
            label="Tilt",
            fine_offset=3,
            physical_min=-135.0,
            physical_max=135.0,
            physical_unit="deg",
        ),
        ChannelDefinition(
            ChannelType.TILT if swap_tilt_intensity else ChannelType.INTENSITY,
            4,
            label="Dimmer",
        ),
        ChannelDefinition(ChannelType.RED, 5, label="Red"),
        ChannelDefinition(ChannelType.GREEN, 6, label="Green"),
        ChannelDefinition(ChannelType.BLUE, 7, label="Blue"),
        ChannelDefinition(ChannelType.GOBO_WHEEL, 8, label="Gobo1", ranges=g1_ranges),
        ChannelDefinition(ChannelType.GOBO_WHEEL, 9, label="Gobo1WheelSpin"),
        ChannelDefinition(ChannelType.GOBO_WHEEL, 10, label="Gobo2", ranges=g2_ranges),
    ]
    mode_11 = DmxModeDefinition(name="Mode 1 (11ch)", channel_defs=ch_defs)
    mode_5 = DmxModeDefinition(
        name="Compact (5ch)",
        channel_defs=[
            ChannelDefinition(ChannelType.INTENSITY, 0, label="Dimmer"),
            ChannelDefinition(ChannelType.RED, 1, label="Red"),
            ChannelDefinition(ChannelType.GREEN, 2, label="Green"),
            ChannelDefinition(ChannelType.BLUE, 3, label="Blue"),
            ChannelDefinition(
                ChannelType.GOBO_WHEEL, 4, label="Gobo1", ranges=g1_ranges
            ),
        ],
    )
    return FixtureDefinition(
        manufacturer=manufacturer,
        model=model,
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[mode_5, mode_11],
        gdtf_id=gdtf_id,
        is_builtin=False,
    )


def _make_eos_pers(
    *,
    manufacturer: str = "Robe",
    model: str = "T1 Profile",
    footprint: int = 11,
    pan_bounds: tuple[float, float] = (-270.0, 270.0),
    gobo2_as_generic: bool = True,
) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    param_types = {
        1: "Intens",
        2: "Pan",
        3: "Tilt",
        4: "Red",
        5: "Green",
        6: "Blue",
        7: "Gobo_Select",
        8: "Gobo_Index/Speed",
        9: "Gobo_Select_2" if gobo2_as_generic else "Gobo_Select",
    }
    pers: dict[int, dict[str, Any]] = {
        1: {
            "manufacturer": manufacturer,
            "model": model,
            "footprint": footprint,
            "channels": [
                {
                    "param_id": 2,
                    "bytes": 2,
                    "offset_coarse": 1,
                    "offset_fine": 2,
                    "default": 32768,
                    "phys_min": pan_bounds[0],
                    "phys_max": pan_bounds[1],
                    "slot_list": [],
                },
                {
                    "param_id": 3,
                    "bytes": 2,
                    "offset_coarse": 3,
                    "offset_fine": 4,
                    "default": 32768,
                    "phys_min": -135.0,
                    "phys_max": 135.0,
                    "slot_list": [],
                },
                {
                    "param_id": 1,
                    "bytes": 1,
                    "offset_coarse": 5,
                    "offset_fine": 0,
                    "default": 0,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
                {
                    "param_id": 4,
                    "bytes": 1,
                    "offset_coarse": 6,
                    "offset_fine": 0,
                    "default": 255,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
                {
                    "param_id": 5,
                    "bytes": 1,
                    "offset_coarse": 7,
                    "offset_fine": 0,
                    "default": 255,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
                {
                    "param_id": 6,
                    "bytes": 1,
                    "offset_coarse": 8,
                    "offset_fine": 0,
                    "default": 255,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
                {
                    "param_id": 7,
                    "bytes": 1,
                    "offset_coarse": 9,
                    "offset_fine": 0,
                    "default": 0,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
                {
                    "param_id": 8,
                    "bytes": 1,
                    "offset_coarse": 10,
                    "offset_fine": 0,
                    "default": 0,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
                {
                    "param_id": 9,
                    "bytes": 1,
                    "offset_coarse": 11,
                    "offset_fine": 0,
                    "default": 0,
                    "phys_min": 0.0,
                    "phys_max": 100.0,
                    "slot_list": [],
                },
            ],
        }
    }
    return pers, param_types


def test_matcher_normalized_name_and_mode_selection() -> None:
    """Normalized name matches 'Robe T1 Profile' to 'Robe lighting ROBIN T1 Profile'."""
    lib = FixtureLibrary()
    lib.register(_make_gdtf_spot())
    pers, ptypes = _make_eos_pers(manufacturer="Robe", model="T1 Profile", footprint=11)

    res = match_eos_personalities(pers, ptypes, lib)[1]
    assert res.status is MatchStatus.COMPATIBLE
    assert res.gdtf_mode is not None
    assert res.gdtf_mode.name == "Mode 1 (11ch)"
    assert res.gobo_count == 2
    assert res.score >= 0.95


def test_matcher_rejects_footprint_and_critical_mismatches() -> None:
    """Footprint, intensity/tilt swap, or 16-bit fine mismatch must be INCOMPATIBLE."""
    # 1. Footprint mismatch
    lib = FixtureLibrary()
    lib.register(_make_gdtf_spot())
    pers_fp, ptypes = _make_eos_pers(footprint=12)
    res_fp = match_eos_personalities(pers_fp, ptypes, lib)[1]
    assert res_fp.status is MatchStatus.INCOMPATIBLE

    # 2. Critical type swap (Intensity vs Tilt)
    lib2 = FixtureLibrary()
    lib2.register(_make_gdtf_spot(swap_tilt_intensity=True))
    pers_ok, ptypes = _make_eos_pers(footprint=11)
    res_swap = match_eos_personalities(pers_ok, ptypes, lib2)[1]
    assert res_swap.status is MatchStatus.INCOMPATIBLE
    assert any(i.severity == "error" for i in res_swap.issues)

    # 3. 16-bit fine_offset mismatch
    lib3 = FixtureLibrary()
    lib3.register(_make_gdtf_spot(omit_pan_fine=True))
    res_fine = match_eos_personalities(pers_ok, ptypes, lib3)[1]
    assert res_fine.status is MatchStatus.INCOMPATIBLE
    assert any("16-bit" in i.reason for i in res_fine.issues)


def test_matcher_warns_on_physical_bounds_difference() -> None:
    """Different Pan physical bounds produce WARNING without blocking."""
    lib = FixtureLibrary()
    lib.register(_make_gdtf_spot(pan_bounds=(-265.0, 265.0)))
    pers, ptypes = _make_eos_pers(pan_bounds=(-270.0, 270.0))

    res = match_eos_personalities(pers, ptypes, lib)[1]
    assert res.status is MatchStatus.WARNING
    assert any(
        i.severity == "warning" and "physical bounds" in i.reason for i in res.issues
    )


def test_ascii_import_auto_uses_local_gdtf_and_hydrates_gobos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full ASCII import substitutes local GDTF, hydrates PNG gobos, and maps cues."""
    monkeypatch.setenv("OLC_USER_FIXTURES_DIR", str(tmp_path / "fixtures"))
    monkeypatch.setenv("OLC_USER_GOBOS_DIR", str(tmp_path / "gobos"))

    gdtf_def = _make_gdtf_spot(pan_bounds=(-260.0, 260.0))
    save_user_fixture(gdtf_def)
    png_bytes = b"\x89PNG\r\n\x1a\nfake-gobo-png"
    save_user_gobo(
        GoboAsset(
            gobo_id="gdtf:gdtf-t1-uuid:G1Slot1",
            name="G1 Stars",
            data=png_bytes,
            ext="png",
        )
    )
    save_user_gobo(
        GoboAsset(
            gobo_id="gdtf:gdtf-t1-uuid:G2Slot1",
            name="G2 Bars",
            data=png_bytes,
            ext="png",
        )
    )

    asc = "\n".join(
        [
            "Ident 3:0",
            "Manufacturer ETC",
            "Console Eos",
            "$ParamType 1 1 Intens",
            "$ParamType 2 2 Pan",
            "$ParamType 3 2 Tilt",
            "$ParamType 4 3 Red",
            "$ParamType 5 3 Green",
            "$ParamType 6 3 Blue",
            "$ParamType 7 4 Gobo_Select",
            "$ParamType 8 4 Gobo_Index/Speed",
            "$ParamType 9 4 Gobo_Select_2",
            "$Personality 10",
            "   $$Manuf Robe",
            "   $$Model T1 Profile",
            "   $$Footprint 11",
            "   $$PersChan 2 2 1 2 32768 100 -270.0 270.0",
            "   $$PersChan 3 2 3 4 32768 100 -135.0 135.0",
            "   $$PersChan 1 1 5 0 0 100 0.0 100.0",
            "   $$PersChan 4 1 6 0 255 100 0.0 100.0",
            "   $$PersChan 5 1 7 0 255 100 0.0 100.0",
            "   $$PersChan 6 1 8 0 255 100 0.0 100.0",
            "   $$PersChan 7 1 9 0 0 100 0.0 100.0",
            "   $$PersChan 8 1 10 0 0 100 0.0 100.0",
            "   $$PersChan 9 1 11 0 0 100 0.0 100.0",
            "$Patch 1 10 1 1",
            "$CueList 1",
            "Cue 1 1",
            "   Chan 1@Hff",
            "   $$Param 1 1 255",
            "   $$Param 1 2 49151",
            "   $$Param 1 7 200",
            "   $$Param 1 9 180",
            "EndData",
        ]
    )
    asc_file = tmp_path / "show.asc"
    asc_file.write_text(asc, encoding="ascii")

    app = CoreApplication(MagicMock())
    app.backend = DMXBackend(app.lightshow)
    ls = app.lightshow
    imported = ImportFile(ls, Gio.File.new_for_path(str(asc_file)), FileType.ASCII)
    imported.parse_sync(auto_import=True)

    # Device should be instantiated from GDTF with PNG gobo_ids
    dev = ls.patch.get_device(1)
    assert dev is not None
    assert dev.gdtf_id == "gdtf-t1-uuid"
    assert dev.manufacturer == "Robe lighting"
    gobo_chs = [c for c in dev.channels if c.channel_type is ChannelType.GOBO_WHEEL]
    assert len(gobo_chs) == 3  # Gobo1, Gobo1WheelSpin, Gobo2
    assert gobo_chs[0].ranges[1].gobo_id == "gdtf:gdtf-t1-uuid:G1Slot1"
    assert gobo_chs[2].ranges[1].gobo_id == "gdtf:gdtf-t1-uuid:G2Slot1"

    # gobo_library must be hydrated from user cache
    assert ls.gobo_library.get("gdtf:gdtf-t1-uuid:G1Slot1") is not None
    assert ls.gobo_library.get("gdtf:gdtf-t1-uuid:G2Slot1") is not None

    # Cue playback must apply Pan using GDTF bounds and Gobo2 via GDTF label
    ls.main_playback.load_step(1)
    assert gobo_chs[0].value == 200
    assert gobo_chs[2].value == 180
    # Pan raw 49151/65535 -> 0.75 of [-260..260] -> +130° -> DMX 16-bit ~ 49151
    assert dev.pan_16bit == pytest.approx(49151, abs=2)

    # Verify disabling use_gdtf_matches falls back to Eos personality
    ls2 = LightShow()
    imp2 = ImportFile(ls2, Gio.File.new_for_path(str(asc_file)), FileType.ASCII)
    imp2.actions["use_gdtf_matches"] = False
    imp2.parse_sync(auto_import=True)
    dev2 = ls2.patch.get_device(1)
    assert dev2 is not None
    assert dev2.gdtf_id == ""
    assert dev2.manufacturer == "Robe"

    # Verify per-personality override in gdtf_overrides
    ls3 = LightShow()
    imp3 = ImportFile(ls3, Gio.File.new_for_path(str(asc_file)), FileType.ASCII)
    imp3.actions["gdtf_overrides"] = {10: "eos"}
    imp3.parse_sync(auto_import=True)
    dev3 = ls3.patch.get_device(1)
    assert dev3 is not None
    assert dev3.gdtf_id == ""
    assert dev3.manufacturer == "Robe"
