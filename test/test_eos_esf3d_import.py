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
"""Integration tests for native ETC Eos ``.esf3d`` import."""

from __future__ import annotations

import pathlib

import pytest

from olc.actions.show import _detect_file_type
from olc.files.file_type import FileType
from olc.files.import_file import ImportFile
from olc.show.lightshow import LightShow
from olc.show.palette import PaletteCategory

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"


def test_detect_file_type_esf3d() -> None:
    """File type detection maps .esf3d and .esf2 to FileType.ESF3D."""
    assert _detect_file_type("show.esf3d") is FileType.ESF3D
    assert _detect_file_type("SHOW.ESF2") is FileType.ESF3D
    assert _detect_file_type("show.asc") is FileType.ASCII
    assert _detect_file_type("show.olc") is FileType.OLC


@pytest.mark.parametrize(
    ("filename", "expected_title"),
    [
        ("eos_sample_32.esf3d", "Anon Show 32"),
        ("eos_sample_33.esf3d", "Anon Show 33"),
    ],
)
def test_import_esf3d_autonomous_fixtures_and_show(
    filename: str, expected_title: str
) -> None:
    """Import anonymized Eos 3.2 and 3.3 .esf3d files without GDTF switching."""
    show = LightShow()
    imp = ImportFile(show, DATA_DIR / filename, FileType.ESF3D)
    imp.parse_sync()

    assert show.title == expected_title

    # Autonomous fixture definition built directly from tree[2]
    fdef = show.fixture_library.get("AnonLights", "Spot_16bit_Anon")
    assert fdef is not None
    assert fdef.dmx_modes[0].channel_count() == 12

    # Dimmer channel 1 with gel and 3D transform
    dim1 = show.patch.devices[1]
    assert dim1.gel == "L201"
    assert dim1.position == pytest.approx((1.0, 2.0, 5.0))
    assert dim1.orientation == pytest.approx((-90.0, 0.0, 0.0))

    # Moving head ch 5 on universe 2 (addr 525 -> univ 2, addr 13), floor orient
    spot5 = show.patch.devices[5]
    assert spot5.channels[0].universe == 2
    assert spot5.channels[0].address == 13
    assert spot5.orientation == pytest.approx((-45.0, 180.0, -40.0))

    # Cue 115: Gobo_Index/Speed in Rot mode (279=191): -55 -> CCW, +55 -> CW
    cue115 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 115.0
    )
    val_ch4 = cue115.device_values[4]["gobo_index/speed"]
    val_ch5 = cue115.device_values[5]["gobo_index/speed"]
    assert round(val_ch4 * 65535) == 52155  # coarse 203 (CCW)
    assert round(val_ch5 * 65535) == 46148  # coarse 180 (CW)
    assert (round(val_ch4 * 65535) >> 8) == 203
    assert (round(val_ch5 * 65535) >> 8) == 180

    # Groups & Palettes
    grp1 = show.groups.get(1.0)
    assert grp1 is not None
    assert grp1.channels == [4, 5]

    col_pal = show.palettes.get(PaletteCategory.COLOR, 1.0)
    assert col_pal is not None
    assert col_pal.device_values[4]["cyan"] == pytest.approx(1.0)
