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
from olc.devices.channel import ChannelRange, ChannelType
from olc.devices.device import FixtureType
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
)
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
    assert show.main_playback.tracking_mode is True

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

    # Cue 110 starts Effect 1.0 on Ch 4, 5 with size_scale=2.01, rate_scale=0.79
    cue110 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 110.0
    )
    assert cue110.effect_refs[4] == {
        "effect": 1.0,
        "order_index": 0,
        "channels": [4, 5],
        "rate_scale": 0.79,
        "size_scale": 2.01,
    }
    assert cue110.effect_refs[5]["order_index"] == 1

    # Cue 115: Gobo_Mode=191 tracked from Cue 110 -> -55=CCW (52155), +55=CW (46148)
    cue115 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 115.0
    )
    assert cue115.effect_refs[4] == {"stop": True}
    assert cue115.effect_refs[5] == {"stop": True}
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
    assert seq2.tracking_mode is True
    assert seq2.text == "Secondary List"
    sec_115 = [s.cue for s in seq2.steps if s.cue is not None and s.cue.number == 115.0]
    assert len(sec_115) == 1
    assert sec_115[0].text == "CL2 Cue 115"


def test_import_esf3d_routes_none_cuelist_via_start_and_nearest_anchor(
    tmp_path: pathlib.Path,
) -> None:
    """Cues with cue[20][3] == None route via start-cue (len=8) or nearest anchor."""
    with zipfile.ZipFile(DATA_DIR / "eos_sample_32.esf3d", "r") as zf:
        header, tree = decode_showdat(zf.read("showdat.dat"))

    cl3 = ["OBJ", 0, 3, None, "Third List"] + [None] * 22
    start_cl3 = ["OBJ", 0, ["OBJ", 0, 100000, 3, None], ["OBJ", 0, -4, 3, None]] + [
        None
    ] * 4
    cue115_orig = next(
        it
        for it in tree[6:]
        if isinstance(it, list) and len(it) == 31 and it[2][2] == 1150000
    )
    cue10_none = [list(x) if isinstance(x, list) else x for x in cue115_orig]
    cue10_none[2] = ["OBJ", 1, 100000, "CL3 Start 10", 0, 0.0, 0.0, 0]
    cue10_none[20] = ["OBJ", 0, None, None, None]

    cue25_none = [list(x) if isinstance(x, list) else x for x in cue115_orig]
    cue25_none[2] = ["OBJ", 1, 250000, "CL3 Near 25", 0, 0.0, 0.0, 0]
    cue25_none[20] = ["OBJ", 0, None, None, None]

    cue29_cl3 = [list(x) if isinstance(x, list) else x for x in cue115_orig]
    cue29_cl3[2] = ["OBJ", 1, 290000, "CL3 Anchor 29", 0, 0.0, 0.0, 0]
    cue29_cl3[20] = ["OBJ", 0, None, 3, None]

    new_tree = tree[:6] + [cl3, start_cl3, cue10_none, cue25_none, cue29_cl3] + tree[6:]
    esf_path = tmp_path / "none_cuelist.esf3d"
    with zipfile.ZipFile(esf_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("showdat.dat", encode_showdat(header, new_tree))

    show = LightShow()
    ImportFile(show, esf_path, FileType.ESF3D).parse_sync()

    seq3 = next((seq for seq in show.sequences if seq.index == 3), None)
    assert seq3 is not None
    seq3_nums = [s.cue.number for s in seq3.steps if s.cue and s.cue.number > 0]
    assert seq3_nums == [10.0, 25.0, 29.0]


def test_import_esf3d_tracks_cue26_effect_modifier_updates(
    tmp_path: pathlib.Path,
) -> None:
    """A cue with empty cue[23] and cue[26] scales updates active effect_refs."""
    with zipfile.ZipFile(DATA_DIR / "eos_sample_32.esf3d", "r") as zf:
        header, tree = decode_showdat(zf.read("showdat.dat"))

    cue110_orig = next(
        it
        for it in tree[6:]
        if isinstance(it, list) and len(it) == 31 and it[2][2] == 1100000
    )
    cue112 = [list(x) if isinstance(x, list) else x for x in cue110_orig]
    cue112[2] = ["OBJ", 1, 1120000, "Cue 112 Scale", 0, 0.0, 0.0, 0]
    cue112[23] = ["OBJ", 0, 0, ["OBJ", 0, 0]]
    cue112[26] = ["OBJ", 0, 1, 10000, ["OBJ", 0, 77, 7, 100, 100, 180]]

    new_tree = tree + [cue112]
    esf_path = tmp_path / "eff_scale.esf3d"
    with zipfile.ZipFile(esf_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("showdat.dat", encode_showdat(header, new_tree))

    show = LightShow()
    ImportFile(show, esf_path, FileType.ESF3D).parse_sync()

    c112 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 112.0
    )
    assert c112.effect_refs[4] == {
        "effect": 1.0,
        "order_index": 0,
        "channels": [4, 5],
        "rate_scale": 0.07,
        "size_scale": 0.77,
    }


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


def _make_anon_spot_gdtf() -> FixtureDefinition:
    """Build a synthetic local GDTF matching AnonLights Spot_16bit_Anon (12ch)."""
    mode = DmxModeDefinition(
        name="12ch Standard",
        channel_defs=[
            ChannelDefinition(ChannelType.PAN, offset=0, fine_offset=1, label="Pan"),
            ChannelDefinition(ChannelType.TILT, offset=2, fine_offset=3, label="Tilt"),
            ChannelDefinition(
                ChannelType.INTENSITY,
                offset=4,
                fine_offset=5,
                label="Dimmer",
                highlight_value=65535,
            ),
            ChannelDefinition(ChannelType.CYAN, offset=6, label="Cyan"),
            ChannelDefinition(ChannelType.MAGENTA, offset=7, label="Magenta"),
            ChannelDefinition(ChannelType.YELLOW, offset=8, label="Yellow"),
            ChannelDefinition(
                ChannelType.GOBO_WHEEL,
                offset=9,
                label="Gobo1",
                ranges=[
                    ChannelRange("Open", ChannelType.GOBO_WHEEL, 0, 9),
                    ChannelRange(
                        "Star",
                        ChannelType.GOBO_WHEEL,
                        10,
                        77,
                        snap_value=40,
                        description="Star gobo",
                        gobo_id="gdtf:star",
                    ),
                ],
            ),
            ChannelDefinition(
                ChannelType.GENERIC,
                offset=10,
                fine_offset=11,
                label="GoboRot",
            ),
        ],
    )
    return FixtureDefinition(
        manufacturer="AnonLights",
        model="Spot_16bit_Anon",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[mode],
        gdtf_id="gdtf-anon-spot-12ch",
        is_builtin=False,
    )


def test_import_esf3d_gdtf_enrichment_enabled() -> None:
    """Local GDTF enriches gobos/gdtf_id while preserving Eos DMX and Cue values."""
    show = LightShow()
    show.fixture_library.register(_make_anon_spot_gdtf())

    imp = ImportFile(show, DATA_DIR / "eos_sample_32.esf3d", FileType.ESF3D)
    imp.parse_sync()

    matches = imp.data.data["gdtf_matches"]
    assert matches[1]["status"] == "compatible"
    assert matches[1]["gobo_count"] == 1

    dev4 = show.patch.devices[4]
    assert dev4.gdtf_id == "gdtf-anon-spot-12ch"
    gobo_ch = next(c for c in dev4.channels if c.channel_type is ChannelType.GOBO_WHEEL)
    assert any(r.gobo_id == "gdtf:star" for r in gobo_ch.ranges)
    star_r = next(r for r in gobo_ch.ranges if r.gobo_id == "gdtf:star")
    assert star_r.description == "Star gobo"

    # Eos Cue 115 Gobo_Index/Speed (52155 / 46148) and DMX offsets remain intact
    cue115 = next(
        s.cue
        for s in show.main_playback.steps
        if s.cue is not None and s.cue.number == 115.0
    )
    assert round(cue115.device_values[4]["gobo_index/speed"] * 65535) == 52155
    assert round(cue115.device_values[5]["gobo_index/speed"] * 65535) == 46148


@pytest.mark.parametrize(
    "actions",
    [
        {"use_gdtf_matches": False},
        {"use_gdtf_matches": True, "gdtf_overrides": {1: "eos"}},
    ],
)
def test_import_esf3d_gdtf_enrichment_disabled_or_overridden(
    actions: dict[str, object],
) -> None:
    """use_gdtf_matches=False or gdtf_overrides={1: 'eos'} skips GDTF enrichment."""
    show = LightShow()
    show.fixture_library.register(_make_anon_spot_gdtf())

    imp = ImportFile(show, DATA_DIR / "eos_sample_32.esf3d", FileType.ESF3D)
    imp.actions.update(actions)
    imp.parse_sync()

    # Match summary is still recorded for the import dialog
    assert imp.data.data["gdtf_matches"][1]["status"] == "compatible"

    dev4 = show.patch.devices[4]
    assert dev4.gdtf_id == ""
    gobo_ch = next(c for c in dev4.channels if c.channel_type is ChannelType.GOBO_WHEEL)
    assert all(r.gobo_id == "" for r in gobo_ch.ranges)


def test_eos_zoom_effects_stepbased_palette_and_engine() -> None:
    """StepBased Zoom, palette-based Absolute Zoom, ESF3D ref, and engine."""
    from olc.core.effects_engine import EffectsEngine
    from olc.files.ascii.eos_effects import (
        EOS_TYPE_ABSOLUTE,
        EOS_TYPE_STEPBASED,
        convert_eos_effect,
        new_eos_effect,
    )
    from olc.files.eos.parser import _extract_effect_step_token
    from olc.show.effect import EffectLayer, EffectMode, WaveformType
    from olc.show.palette import Palette

    param_types = {79: "Zoom"}

    # 1. StepBased effect with param_id 79 -> parameter == "zoom"
    raw_step = new_eos_effect(1.0)
    raw_step["label"] = "Zoom"
    raw_step["eos_type"] = EOS_TYPE_STEPBASED
    raw_step["param_ids"] = [79]
    raw_step["steps"] = [[1.0, 0.0, 0.0, 0.0, 100.0, 0.0]] * 2
    eff1 = convert_eos_effect(raw_step, param_types)
    assert eff1["groups"] == 2
    assert eff1["layers"][0]["parameter"] == "zoom"

    # 2. ESF3D step token extraction for BP 1 (ref_kind=3, cat_id=4, num=10000)
    st_bp1: list[object] = [
        "OBJ",
        0,
        3,
        0,
        0,
        0,
        2000,
        3,
        0,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        ["OBJ", 0, 10000, 4, None],
        None,
    ]
    assert _extract_effect_step_token(st_bp1) == "BP 1"

    # 3. Absolute effect with BP 1 / BP 2 and empty param_ids infers "zoom"
    raw_abs = new_eos_effect(2.0)
    raw_abs["label"] = "Zoom2"
    raw_abs["eos_type"] = EOS_TYPE_ABSOLUTE
    raw_abs["actions"] = [(2.0, 0.0, "BP 1"), (2.0, 0.0, "BP 2")]
    palettes = {
        "beam": {
            1.0: {"device_values": {1: {"zoom": 60.0}}},
            2.0: {"device_values": {1: {"zoom": 10.0}}},
        }
    }
    eff2 = convert_eos_effect(raw_abs, param_types, palettes=palettes)
    assert eff2["layers"][0]["parameter"] == "zoom"
    assert eff2["layers"][0]["low_palette"] == ["beam", 1.0]
    assert eff2["layers"][0]["high_palette"] == ["beam", 2.0]

    # 4. EffectsEngine resolves low_palette / high_palette for zoom in ABSOLUTE mode
    show = LightShow()
    fdef = FixtureDefinition(
        manufacturer="Test",
        model="ZoomSpot",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_modes=[
            DmxModeDefinition(
                name="1ch",
                channel_defs=[
                    ChannelDefinition(
                        ChannelType.ZOOM,
                        offset=0,
                        label="Zoom",
                        physical_min=10.0,
                        physical_max=60.0,
                    )
                ],
            )
        ],
    )
    dev = fdef.instantiate(fixture_id=1, label="Spot 1", universe=1, address=1)
    show.patch.devices[1] = dev
    show.palettes.add(
        Palette(
            category=PaletteCategory.BEAM,
            number=1.0,
            text="Narrow",
            device_values={1: {"zoom": 60.0}},
        )
    )
    show.palettes.add(
        Palette(
            category=PaletteCategory.BEAM,
            number=2.0,
            text="Wide",
            device_values={1: {"zoom": 10.0}},
        )
    )
    engine = EffectsEngine(None, lightshow=show)
    layer = EffectLayer(
        parameter="zoom",
        waveform=WaveformType.PULSE,
        mode=EffectMode.ABSOLUTE,
        low_palette=("beam", 1.0),
        high_palette=("beam", 2.0),
    )
    ch_base: dict[str, object] = {"zoom": 20.0}
    ch_last: dict[str, object] = {}
    assert engine._apply_scalar_device_layer_locked(
        dev, 1, layer, 0.0, 1.0, ch_base, ch_last
    )
    assert dev.zoom_degrees == pytest.approx(60.0, abs=0.5)
    assert engine._apply_scalar_device_layer_locked(
        dev, 1, layer, 1.0, 1.0, ch_base, ch_last
    )
    assert dev.zoom_degrees == pytest.approx(10.0, abs=0.5)
