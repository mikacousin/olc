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
import zipfile

import pytest

from olc.actions.show import _detect_file_type
from olc.files.eos.personality import (
    EosParamDef,
    EosRangeBlock,
    EosSubRange,
    evaluate_eos_param_to_dmx,
)
from olc.files.eos.wire import decode_showdat, encode_showdat
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

    # Dimmer channel 1 with gel, beam_angle, and 3D transform
    dim1 = show.patch.devices[1]
    assert dim1.gel == "L201"
    assert dim1.beam_angle == pytest.approx(22.0)
    assert dim1.position == pytest.approx((1.0, 2.0, 5.0))
    assert dim1.orientation == pytest.approx((-90.0, 0.0, 0.0))

    # Moving head ch 5 on universe 2 (addr 525 -> univ 2, addr 13), floor orient
    spot5 = show.patch.devices[5]
    assert spot5.channels[0].universe == 2
    assert spot5.channels[0].address == 13
    assert spot5.beam_angle == pytest.approx(60.0)
    assert spot5.orientation == pytest.approx((-45.0, 180.0, 40.0))

    # Cue 1: Ch 1 cloned to Ch 2 (both at 80%), not blocked
    cue1 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 1.0
    )
    assert cue1.channels[1] == pytest.approx(0.8)
    assert cue1.channels[2] == pytest.approx(0.8)
    assert cue1.is_block is False

    # Cue 115: Gobo_Mode=191 tracked from Cue 110 -> -55=CCW (52155), +55=CW (46148)
    cue115 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 115.0
    )
    assert cue115.is_block is True
    assert cue115.is_assert is True
    assert cue115.notes == "Check smoke"
    assert cue115.palette_refs[4]["cyan"] == ("color", 1.0)
    val_ch4 = cue115.device_values[4]["gobo_index/speed"]
    val_ch5 = cue115.device_values[5]["gobo_index/speed"]
    assert round(val_ch4 * 65535) == 52155  # coarse 203 (CCW)
    assert round(val_ch5 * 65535) == 46148  # coarse 180 (CW)
    assert (round(val_ch4 * 65535) >> 8) == 203
    assert (round(val_ch5 * 65535) >> 8) == 180

    # Groups & Palettes (Focus + Color including cloned Ch 5)
    grp1 = show.groups.get(1.0)
    assert grp1 is not None
    assert grp1.channels == [4, 5]

    foc_pal = show.palettes.get(PaletteCategory.FOCUS, 1.0)
    assert foc_pal is not None
    assert foc_pal.text == "Stage Center"
    assert foc_pal.device_values[4]["pan"] == pytest.approx(15.0, abs=0.05)
    assert foc_pal.device_values[4]["tilt"] == pytest.approx(-10.0, abs=0.05)

    col_pal = show.palettes.get(PaletteCategory.COLOR, 1.0)
    assert col_pal is not None
    assert col_pal.device_values[4]["cyan"] == pytest.approx(1.0)
    assert col_pal.device_values[5]["cyan"] == pytest.approx(1.0)

    # Curve 901, Submaster 2 -> Preset 2 & Fader (1, 2), and Effect 1.0
    assert 901 in show.curves.curves
    assert show.curves.curves[901].name == "Anon Curve"
    sub_preset = show.palettes.get(PaletteCategory.PRESET, 2.0)
    assert sub_preset is not None
    assert sub_preset.text == "Anon Sub"
    assert sub_preset.channels[1] == pytest.approx(0.75)
    assert show.fader_bank.faders[1][2].contents.number == 2.0
    assert len(show.effects) == 1


def test_import_esf3d_routes_cuelists_without_duplication(
    tmp_path: pathlib.Path,
) -> None:
    """Cue Lists (len=27) and cue[20][3] route cues without duplicating."""
    with zipfile.ZipFile(DATA_DIR / "eos_sample_32.esf3d", "r") as zf:
        header, tree = decode_showdat(zf.read("showdat.dat"))

    # Add Cue List 1 & Cue List 2 ("Secondary List")
    cl1 = ["OBJ", 0, 1, None, 0] + [None] * 22
    cl2 = ["OBJ", 0, 2, None, "Secondary List"] + [None] * 22

    # Clone Cue 115 into Cue List 2 with its own label and intensity
    cue115_orig = next(
        it
        for it in tree[6:]
        if isinstance(it, list) and len(it) == 31 and it[2][2] == 1150000
    )
    cue115_cl2 = [list(x) if isinstance(x, list) else x for x in cue115_orig]
    cue115_cl2[2] = ["OBJ", 1, 1150000, "CL2 Cue 115", 0, 0.0, 0.0, 0]
    cue115_cl2[20] = ["OBJ", 0, None, 2, None]

    new_tree = tree[:6] + [cl1, cl2] + tree[6:] + [cue115_cl2]
    esf_path = tmp_path / "multi_cuelist.esf3d"
    with zipfile.ZipFile(esf_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("showdat.dat", encode_showdat(header, new_tree))

    show = LightShow()
    imp = ImportFile(show, esf_path, FileType.ESF3D)
    imp.parse_sync()

    # Main playback must have exactly one Cue 115 with Cue List 1's label
    main_115 = [
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 115.0
    ]
    assert len(main_115) == 1
    assert main_115[0].text == "Cue 115"

    # Secondary sequence #2 must be created with its own Cue 115
    seq2 = next((seq for seq in show.sequences if seq.index == 2), None)
    assert seq2 is not None
    assert seq2.text == "Secondary List"
    sec_115 = [s.cue for s in seq2.steps if s.cue is not None and s.cue.number == 115.0]
    assert len(sec_115) == 1
    assert sec_115[0].text == "CL2 Cue 115"


def test_evaluate_discrete_slots_and_point_ranges() -> None:
    """Discrete slots and point sub-ranges snap to home_dmx instead of midpoint."""
    prism = EosParamDef(
        param_id=201,
        name="Beam_Fx_Select",
        home_dmx=0,
        offset=10,
        num_bytes=1,
        range_blocks=[
            EosRangeBlock(
                None,
                0.0,
                0.0,
                [
                    EosSubRange("open", 0, 127, 0.5, 1.499999, 0),
                    EosSubRange("effect", 128, 255, 1.5, 2.4, 191),
                ],
            )
        ],
    )
    assert evaluate_eos_param_to_dmx(prism, 1.0, {}) == 0

    ct = EosParamDef(
        param_id=1719,
        name="Color_Temperature",
        home_dmx=0,
        offset=11,
        num_bytes=1,
        range_blocks=[
            EosRangeBlock(
                None,
                0.0,
                0.0,
                [
                    EosSubRange("Off", 0, 5, 1594.0, 1594.0, 0),
                    EosSubRange("1600-6500", 6, 255, 1600.0, 6500.0, 128),
                ],
            )
        ],
    )
    assert evaluate_eos_param_to_dmx(ct, 1594.0, {}) == 0
