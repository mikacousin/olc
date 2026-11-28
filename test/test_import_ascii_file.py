"""Unit and integration tests for ASCII / EOS show file importation."""

from pathlib import Path
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gtk", "3.0")
from charset_normalizer import from_bytes  # noqa: E402
from gi.repository import Gio  # noqa: E402

from olc.files.ascii.parser import AsciiParser  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402
from test.conftest import DATA_DIR  # noqa: E402

FILE_PATH = str(DATA_DIR / "sample.asc")
gfile = Gio.File.new_for_path(FILE_PATH)


@pytest.fixture(scope="module", name="_eos_show_imported")
def eos_show_imported_fixture() -> tuple[LightShow, ImportFile]:
    """Import test/data/eos_show.asc once for read-only verification tests."""
    asc_path = DATA_DIR / "eos_show.asc"

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)
    return lightshow, imported


def test_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test ASCII file importation"""

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(lightshow, gfile, FileType.ASCII)

    # Synchronous parsing execution
    _success, data, _etag = gfile.load_contents(None)

    assert isinstance(imported.parser, AsciiParser)
    imported.parser.contents = str(from_bytes(data).best())
    imported.parser.parse()
    imported.data.clean()

    # Assertions
    assert imported.data.data["console"]["console"] == "olc"
    assert imported.data.data["console"]["manufacturer"] == "mika"
    assert imported.data.data["patch"][7] == [{"output": 47, "universe": 1, "curve": 0}]
    assert imported.data.data["sequences"][1]["steps"][1]["cue"] == 1.0
    assert imported.data.data["sequences"][1]["steps"][2]["cue"] == 2.0
    assert imported.data.data["sequences"][1]["steps"][3]["cue"] == 1.0
    assert imported.data.data["sequences"][1]["steps"][4]["cue"] == 4.0
    assert imported.data.data["sequences"][1]["cues"][2.0]["label"] == "Entrée Public"
    assert imported.data.data["sequences"][1]["cues"][1.0]["channels"] == {
        7: 1.0,
        20: 1.0,
        31: 1.0,
    }
    assert imported.data.data["sequences"][2]["label"] == "Chaser 1"


def test_import_eos_cuelists_timings_utext_and_wait_shift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Test Eos multi-CueList, IFCB times, $$Block, $$UText, and 1-cue wait shift."""
    import pathlib

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$CueList 1
   Text Main List
Cue 1 1
   Text Noir  ( vrif)
   $$UText Noir  ( vérif B
   $$UText ackup &#33;&#33;&#33;)
   $$TimeUp 4 1
   $$TimeDown 6 2
   $$TimePosition 15 0 1 1
   $$TimeColor 12 1 1 1
   $$TimeGraphic 8 0.5 1 1
   $$Block
   $$Dwell 3
   Chan 1@Hff
Cue 2 1
   $$UText Top &#8594; Musique
   Chan 1@H80
$CueList 2
   Text Secondary List
Cue 1 2
   Text Cue One List Two
   Chan 2@Hff
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_sample.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    seqs = imported.data.data["sequences"]
    assert set(seqs.keys()) == {1, 2}
    assert seqs[1]["mode"] == "normal"
    assert seqs[2]["mode"] == "normal"
    assert seqs[1]["label"] == "Main List"
    assert seqs[2]["label"] == "Secondary List"

    # Cue 1 in list 1 and Cue 1 in list 2 must not overwrite each other
    assert seqs[1]["cues"][1.0]["label"] == "Noir  ( vérif Backup !!!)"
    assert seqs[2]["cues"][1.0]["label"] == "Cue One List Two"
    assert seqs[1]["cues"][1.0]["is_block"] is True
    assert seqs[1]["cues"][2.0]["label"] == "Top → Musique"

    # Timings & 1-cue wait shift (Eos $$Dwell 3 on Cue 1 -> OLC wait 3.0 on Cue 2)
    s1 = seqs[1]["steps"][1]
    s2 = seqs[1]["steps"][2]
    assert s1["time_in"] == 4.0 and s1["delay_in"] == 1.0
    assert s1["time_out"] == 6.0 and s1["delay_out"] == 2.0
    assert s1["time_position"] == 15.0 and s1["delay_position"] == 0.0
    assert s1["time_color"] == 12.0 and s1["delay_color"] == 1.0
    assert s1["time_beam"] == 8.0 and s1["delay_beam"] == 0.5
    assert s1["wait"] == 0.0
    assert s2["wait"] == 3.0

    # Secondary sequence imported cleanly
    assert len(lightshow.sequences) == 1
    assert lightshow.sequences[0].index == 2


def test_import_eos_show_cuelists_and_labels(
    _eos_show_imported: tuple[LightShow, ImportFile],
) -> None:
    """Verify eos_show.asc splits 3 CueLists without cue collisions."""
    _lightshow, imported = _eos_show_imported

    seqs = imported.data.data["sequences"]
    assert set(seqs.keys()) == {1, 2, 3}
    total_steps = sum(len(s["steps"]) for s in seqs.values())
    assert total_steps == 122
    assert seqs[1]["mode"] == "normal"
    assert seqs[2]["mode"] == "normal"
    assert seqs[3]["mode"] == "normal"
    assert "!!!" in seqs[1]["cues"][99.0]["label"]
    assert "→" in seqs[1]["cues"][106.0]["label"]


def test_import_eos_personalities_patch_and_cue_params(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Test $ParamType, $Personality, $Patch (16-bit & virtual dimmer), and $$Param."""
    import pathlib

    from olc.devices.channel import ChannelType
    from olc.devices.device import FixtureType

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 3 2 Tilt
$ParamType 12 3 Red
$ParamType 13 3 Green
$ParamType 14 3 Blue
$ParamType 79 5 Zoom
$Personality 100
   $$Manuf Ayrton
   $$Model Spot_Test
   $$Footprint 6
   $$PersChan 1 1 1 0 0
   $$PersSlot 0 255 0 0.0 100.0 %
   $$PersChan 2 2 2 3 32768
   $$PersSlot 0 65535 32768 -270.0 270.0 D
   $$PersChan 3 2 4 5 32768
   $$PersSlot 0 65535 32768 -130.0 130.0 D
   $$PersChan 79 1 6 0 128
   $$PersSlot 0 255 128 10.0 50.0 D
$Personality 200
   $$Manuf Cameo
   $$Model RGB_Test
   $$Footprint 3
   $$VirtualInt
   $$PersChan 12 1 1 0 255
   $$PersChan 13 1 2 0 255
   $$PersChan 14 1 3 0 255
Patch 1 21<31@Hff
$Patch 1 100 513 0 1
   $$Pers Spot_Test
$Patch 2 200 10 0 1
   $$Pers RGB_Test
$CueList 1
Cue 1 1
   Chan 1@Hff 2@H80 21@Hff
   $$Param 1 1@255 2@32768 3@65535 79@128
   $$Param 2 12@255 13@0
   $$Param 2 14@128
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_devices.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    # Patch has Moving Head (ch 1), Virtual Dimmer LED (ch 2), and Dimmer (ch 21)
    dev1 = lightshow.patch.get_device(1)
    dev2 = lightshow.patch.get_device(2)
    dev21 = lightshow.patch.get_device(21)
    assert dev1 is not None
    assert dev1.fixture_type is FixtureType.MOVING_HEAD
    pan_ch = dev1.get_channel(ChannelType.PAN)
    assert pan_ch is not None
    assert pan_ch.universe == 2 and pan_ch.address == 2
    pan_channels = [c for c in dev1.channels if c.channel_type is ChannelType.PAN]
    assert len(pan_channels) == 2 and pan_channels[1].fine is True

    assert dev2 is not None
    assert dev2.fixture_type is FixtureType.LED_PAR
    assert dev2.uses_virtual_dimmer is True

    assert dev21 is not None
    assert dev21.fixture_type is FixtureType.DIMMER

    # Cue 1 device_values decoded properly
    cue1 = lightshow.main_playback.steps[1].cue
    assert cue1 is not None
    assert abs(cue1.device_values[1]["pan"] - 0.0) < 0.1
    assert abs(cue1.device_values[1]["tilt"] - 130.0) < 0.1
    assert abs(cue1.device_values[1]["zoom"] - 30.0) < 0.2
    assert cue1.device_values[2]["color"] == "#ff0080"


def test_import_eos_show_devices_and_params(
    _eos_show_imported: tuple[LightShow, ImportFile],
) -> None:
    """Verify eos_show.asc imports all moving/LED devices and $$Param."""
    lightshow, _imported = _eos_show_imported

    # Moving heads 1..5 (Ghibli / Diablo), LEDs 41.., conventionals (21.., 31.., 60)
    for ch in (1, 2, 3, 4, 5, 21, 31, 41, 60):
        assert lightshow.patch.get_device(ch) is not None
    assert any(
        step.cue is not None and bool(step.cue.device_values)
        for step in lightshow.main_playback.steps
    )


def test_import_eos_groups_curves_subs_and_faders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Test $Group/$$ChanList, $Curve, Sub, and $FaderDef ($$Target S / CL)."""
    import pathlib

    from olc.show.curve import InterpolateCurve
    from olc.show.fader import FaderPreset, FaderType
    from olc.show.palette import PaletteCategory

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$Curve 901
   Text IES Square
   $$Interpolated
   $$CurveData 0@0 128@130 255@255
$Curve 902
   Text Stepped Full
   $$CurveData 0@255 255@255
$Patch 1 51365 1 1 1
   $$Curve 901 1
   $$Curve 902 2
$Patch 2 51365 2 1 1
$Group 2
   Text Ghibli
   $$ChanList 3 1 2
Sub 6 1
   Text PAR Anneau
   Chan 21@Hff 22@H80
Sub 99 1
   Text Unused Sub
   Chan 30@Hff
$FaderDef 1
   $$Target S 6
$FaderDef 2
   $$Target CL 1
$CueList 1
Cue 1 1
   Chan 1@Hff
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_curves_faders.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    # Curve 901 linked via $$Curve 901 1; $$Curve 902 2 does not override intensity;
    # dimmer with address_mode=1 and no $$Curve keeps LinearCurve (0).
    curve_901 = lightshow.curves.get_curve(901)
    assert isinstance(curve_901, InterpolateCurve)
    assert curve_901.name == "IES Square"
    dev1 = lightshow.patch.get_device(1)
    assert dev1 is not None and dev1.curve_id == 901
    dev2 = lightshow.patch.get_device(2)
    assert dev2 is not None and dev2.curve_id == 0

    # $Group 2 imported as ordered pure channel list [3, 1, 2]
    grp2 = lightshow.groups.get(2.0)
    assert grp2 is not None
    assert grp2.text == "Ghibli"
    assert grp2.channels == [3, 1, 2]
    assert not any(g.index >= 500 for g in lightshow.groups)

    # Fader 1 -> Sub 6 imported as Preset 6 with FaderType.PRESET (no 500+ groups)
    assert lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    fader1 = lightshow.fader_bank.faders[1][1]
    assert isinstance(fader1, FaderPreset)
    preset6 = lightshow.palettes.get(PaletteCategory.PRESET, 6.0)
    assert preset6 is not None
    assert fader1.contents is preset6
    assert preset6.text == "PAR Anneau"
    assert preset6.channels[21] == 1.0
    assert abs(preset6.channels[22] - (128 / 255.0)) < 0.01

    # Unused Sub 99 is promoted as a Preset (Option A) without creating a Group
    assert lightshow.groups.get(99.0) is None
    preset99 = lightshow.palettes.get(PaletteCategory.PRESET, 99.0)
    assert preset99 is not None
    assert preset99.text == "Unused Sub"
    assert preset99.channels[30] == pytest.approx(1.0)

    # Fader 2 -> CueList 1 (Main Playback)
    assert lightshow.fader_bank.get_fader_type(1, 2) == FaderType.SEQUENCE


def test_import_legacy_ascii_groups_and_faders_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify sample.asc groups/faders migrate to list[int] + Presets."""
    from olc.show.fader import FaderPreset, FaderType
    from olc.show.palette import PaletteCategory

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(lightshow, gfile, FileType.ASCII)
    imported.parse_sync(auto_import=True)

    # Legacy groups retain ordered channel lists without levels
    grp1 = lightshow.groups.get(1.0)
    assert grp1 is not None and grp1.channels == [1, 2]
    grp3 = lightshow.groups.get(3.0)
    assert grp3 is not None and grp3.channels == [13, 17, 36, 40]
    assert not any(g.index >= 500 for g in lightshow.groups)

    # Migrated presets keep levels and bind to FaderType.PRESET
    preset3 = lightshow.palettes.get(PaletteCategory.PRESET, 3.0)
    preset5 = lightshow.palettes.get(PaletteCategory.PRESET, 5.0)
    preset101 = lightshow.palettes.get(PaletteCategory.PRESET, 101.0)
    preset104 = lightshow.palettes.get(PaletteCategory.PRESET, 104.0)
    assert preset3 is not None and preset5 is not None
    assert preset101 is not None and preset104 is not None

    assert lightshow.fader_bank.get_fader_type(1, 4) == FaderType.PRESET
    assert lightshow.fader_bank.faders[1][4].contents is preset3

    # Group 5 and Cue 5 both exist in sample.asc -> Fader 6 must resolve Preset 5
    assert lightshow.fader_bank.get_fader_type(1, 6) == FaderType.PRESET
    fader6 = lightshow.fader_bank.faders[1][6]
    assert isinstance(fader6, FaderPreset)
    assert fader6.contents is preset5

    assert lightshow.fader_bank.get_fader_type(1, 10) == FaderType.PRESET
    assert lightshow.fader_bank.faders[1][10].contents is preset101
    assert lightshow.fader_bank.get_fader_type(2, 10) == FaderType.PRESET
    assert lightshow.fader_bank.faders[2][10].contents is preset104


def test_import_eos_show_groups_curves_and_faders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify eos_show.asc imports $Group, $Curve, and $FaderDef."""
    from olc.show.fader import FaderType
    from olc.show.palette import PaletteCategory

    asc_path = DATA_DIR / "eos_show.asc"

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    # 7 $Group entries populated via $$ChanList preserving order
    assert len(lightshow.groups) == 7
    grp1 = lightshow.groups.get(1.0)
    assert grp1 is not None and grp1.text == "All Moving"
    assert len(grp1.channels) == 22
    grp2 = lightshow.groups.get(2.0)
    assert grp2 is not None and grp2.channels == [3, 1, 2]
    assert not any(g.index >= 500 for g in lightshow.groups)

    # $Curve 901 imported and cp1252 curve names decoded properly (not cp1250 'ŕ')
    c901 = lightshow.curves.get_curve(901)
    assert c901 is not None and c901.name == "IES Square"
    for cid, expected_name in (
        (905, "Full à 1%"),
        (906, "Out à 100%"),
        (907, "Préchauffe à 5%"),
        (909, "Tjrs à 100%"),
    ):
        curve = lightshow.curves.get_curve(cid)
        assert curve is not None and curve.name == expected_name

    # Eos address_mode=1 must NOT assign curve_id=1 (SquareRootCurve)
    for ch in (1, 41, 52, 100):
        dev = lightshow.patch.get_device(ch)
        assert dev is not None and dev.curve_id == 0

    # $FaderDef 1 -> Sub 6 imported as Preset 6 with FaderType.PRESET
    assert lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    preset6 = lightshow.palettes.get(PaletteCategory.PRESET, 6.0)
    assert preset6 is not None
    assert lightshow.fader_bank.faders[1][1].contents is preset6

    from olc.devices.device import ChannelType
    from olc.show.curve import SteppedCurve
    from olc.show.fader import FaderEffect

    # Cue 19 Seq 3: Part 1 global fade (5s) + Part 2 channel_time on ch 41..44 (3s)
    seq3 = next(s for s in lightshow.sequences if s.index == 3)
    step19 = next(s for s in seq3.steps if s.cue is not None and s.cue.number == 19.0)
    assert step19.text == "41Jusqu'à44"
    assert step19.time_in == pytest.approx(5.0)
    assert step19.time_out == pytest.approx(5.0)
    for ch in (41, 42, 43, 44):
        assert ch in step19.channel_time
        assert step19.channel_time[ch].delay == pytest.approx(0.0)
        assert step19.channel_time[ch].time == pytest.approx(3.0)

    # $Patch dimmer labels (Text) & $$Options P (flip Pan on Diablo ch 4)
    for ch in range(21, 27):
        dev = lightshow.patch.get_device(ch)
        assert dev is not None and dev.label == f"Patch {ch}"
    dev4 = lightshow.patch.get_device(4)
    assert dev4 is not None
    pan4 = dev4.get_channel(ChannelType.PAN)
    assert pan4 is not None
    assert pan4.physical_min == pytest.approx(270.0)
    assert pan4.physical_max == pytest.approx(-270.0)
    dev5 = lightshow.patch.get_device(5)
    assert dev5 is not None
    pan5 = dev5.get_channel(ChannelType.PAN)
    assert pan5 is not None
    assert pan5.physical_min == pytest.approx(-270.0)
    assert pan5.physical_max == pytest.approx(270.0)

    # SteppedCurve (905, 906) & non-0/non-255 endpoint preservation (907, 909, 910)
    c905 = lightshow.curves.get_curve(905)
    assert isinstance(c905, SteppedCurve)
    assert c905.get_level(0) == 0
    assert c905.get_level(2) == 0
    assert c905.get_level(3) == 255
    assert c905.get_level(255) == 255

    c906 = lightshow.curves.get_curve(906)
    assert isinstance(c906, SteppedCurve)
    assert c906.get_level(0) == 255
    assert c906.get_level(252) == 255
    assert c906.get_level(255) == 0

    c907 = lightshow.curves.get_curve(907)
    assert c907 is not None
    assert c907.get_level(0) == 13
    assert c907.get_level(255) == 255

    c909 = lightshow.curves.get_curve(909)
    assert c909 is not None
    assert c909.get_level(0) == 255
    assert c909.get_level(255) == 255

    c910 = lightshow.curves.get_curve(910)
    assert c910 is not None
    assert c910.get_level(0) == 255
    assert c910.get_level(255) == 0

    # Mixed effect Sub 20 mounted on fader (3, 4) keeps base_channels & text
    fader34 = lightshow.fader_bank.faders[3][4]
    assert isinstance(fader34, FaderEffect)
    assert fader34.text == "Sub 20"
    assert fader34.base_channels == {ch: pytest.approx(1.0) for ch in range(21, 27)}

    # Unmounted static Subs promoted to Presets (Option A); pure-effect Sub 200 skipped
    for pnum, label in (
        (1.0, "Sub 1"),
        (2.0, "Sub 2"),
        (3.0, "Sub 3"),
        (50.0, "Sub 50"),
        (901.0, "Sub 901"),
    ):
        preset = lightshow.palettes.get(PaletteCategory.PRESET, pnum)
        assert preset is not None and preset.text == label
    assert lightshow.palettes.get(PaletteCategory.PRESET, 200.0) is None

    # Section 6.3 metadata, cue flags/notes/actions, effect envelopes, and sub flags
    from olc.show.effect import EffectEnvelopeMode
    from olc.show.fader import FaderPreset

    assert lightshow.title == "OLC Anonymized Eos Show"
    assert lightshow.home_preset == pytest.approx(999.0)
    assert lightshow.main_playback.mib_enabled is True
    all_seqs = [lightshow.main_playback, *lightshow.sequences]
    assert all(s.mib_enabled is True for s in all_seqs)

    assert_cues = [
        (s.index, step.cue.number)
        for s in all_seqs
        for step in s.steps
        if step.cue is not None and step.cue.is_assert
    ]
    assert len(assert_cues) == 9

    assert step19.cue is not None
    assert step19.cue.is_int_block is True
    assert step19.cue.is_assert is True
    assert step19.cue.notes == "zoom 9 edge 3"

    seq2 = next(s for s in lightshow.sequences if s.index == 2)
    step522 = next(s for s in seq2.steps if s.cue is not None and s.cue.number == 522.0)
    assert step522.cue is not None and step522.cue.is_int_block is True
    step498 = next(s for s in seq2.steps if s.cue is not None and s.cue.number == 498.0)
    assert step498.cue is not None and step498.cue.execute_preset == pytest.approx(1.0)

    fx1 = lightshow.effects.get(1.0)
    fx100 = lightshow.effects.get(100.0)
    fx11 = lightshow.effects.get(11.0)
    assert fx1 is not None and fx1.entry_mode == EffectEnvelopeMode.FADE_BY_SIZE
    assert fx1.cascade is True
    assert fx100 is not None and fx100.cascade is True
    assert fx11 is not None and fx11.layers[0].duty_cycle == pytest.approx(1.0)

    fader_sub900 = lightshow.fader_bank.faders[1][6]
    assert isinstance(fader_sub900, FaderPreset)
    assert fader_sub900.text == "Sub 900"
    assert fader_sub900.exempt_grand_master is True
    fader_sub6 = lightshow.fader_bank.faders[1][1]
    assert isinstance(fader_sub6, FaderPreset)
    assert fader_sub6.intensity_master is True

    # Section 6.4 (Base Nocturne audit): $$StepTimes, signed offsets, waveforms
    from olc.show.effect import EffectMode, WaveformType

    fx5 = lightshow.effects.get(5.0)
    fx7 = lightshow.effects.get(7.0)
    fx103 = lightshow.effects.get(103.0)
    assert fx5 is not None and fx5.cycle_time == pytest.approx(5.0, abs=0.01)
    assert fx7 is not None and fx7.cycle_time == pytest.approx(4.998, abs=0.01)
    assert fx11.cycle_time == pytest.approx(10.002, abs=0.01)
    assert fx103 is not None and fx103.cycle_time == pytest.approx(25.0, abs=0.05)

    fx2 = lightshow.effects.get(2.0)
    fx6 = lightshow.effects.get(6.0)
    fx909 = lightshow.effects.get(909.0)
    fx915 = lightshow.effects.get(915.0)
    fx916 = lightshow.effects.get(916.0)
    assert fx2 is not None
    assert fx2.layers[0].mode == EffectMode.RELATIVE
    assert fx2.layers[0].waveform == WaveformType.PULSE
    assert fx2.layers[0].size == pytest.approx(-25.0)
    assert fx6 is not None
    assert fx6.cycle_time == pytest.approx(10.0)
    assert fx6.layers[0].mode == EffectMode.RELATIVE
    assert fx6.layers[0].waveform == WaveformType.PULSE
    assert fx6.layers[0].size == pytest.approx(-5.0)
    assert fx909 is not None and fx909.layers[0].waveform == WaveformType.RANDOM
    assert fx915 is not None and fx915.layers[0].waveform == WaveformType.SAW_UP
    assert fx916 is not None and fx916.layers[0].waveform == WaveformType.SAW_DOWN

    # Generic optical/framing $$Param support: BP 8..10/30 & Preset 10..12 populated
    for bp_num in (8.0, 9.0, 10.0):
        bp = lightshow.palettes.get(PaletteCategory.BEAM, bp_num)
        assert bp is not None
        assert "frame_a_1" in bp.device_values.get(1, {})
        assert "frame_assembly" in bp.device_values.get(1, {})
    bp30 = lightshow.palettes.get(PaletteCategory.BEAM, 30.0)
    assert bp30 is not None
    assert bp30.device_values[1]["gobo_index/speed"] == pytest.approx(0.75, abs=1e-3)

    pr10 = lightshow.palettes.get(PaletteCategory.PRESET, 10.0)
    pr11 = lightshow.palettes.get(PaletteCategory.PRESET, 11.0)
    pr12 = lightshow.palettes.get(PaletteCategory.PRESET, 12.0)
    assert pr10 is not None
    assert pr10.device_values[4]["gobo_index/speed"] == pytest.approx(0.5, abs=1e-3)
    assert pr10.device_values[5]["gobo_index/speed"] == pytest.approx(1.0, abs=1e-3)
    assert pr11 is not None and pr11.device_values[1][
        "gobo_index/speed"
    ] == pytest.approx(1.0)
    assert pr12 is not None and pr12.device_values[1][
        "gobo_index/speed"
    ] == pytest.approx(0.0)

    # 16-bit generic channel application on Ghibli ch 1
    dev1 = lightshow.patch.get_device(1)
    assert dev1 is not None
    home_gobo_rot = dev1.get_channel_normalized_by_label("Gobo_Index/Speed")
    assert home_gobo_rot == pytest.approx(16383 / 65535.0, abs=1e-4)
    dev1.apply_device_parameter("gobo_index/speed", 0.5)
    assert dev1.get_channel_normalized_by_label("gobo_index/speed") == pytest.approx(
        0.5, abs=1e-4
    )
    dev1.apply_device_parameter("gobo_index/speed", 16383 / 65535.0)

    # FaderPreset proportional LTP blending & release on Sub 11, 12, 13, and Sub 6 guard
    fader_sub11 = lightshow.fader_bank.faders[2][2]
    fader_sub12 = lightshow.fader_bank.faders[2][3]
    fader_sub13 = lightshow.fader_bank.faders[2][4]
    assert isinstance(fader_sub11, FaderPreset)
    assert isinstance(fader_sub12, FaderPreset)
    assert isinstance(fader_sub13, FaderPreset)

    # Sub 11 raises Gobo_Index/Speed from Home (~0.25) -> 0.625 -> 1.0 -> restores ~0.25
    fader_sub11.set_level(0.5)
    assert dev1.get_channel_normalized_by_label("Gobo_Index/Speed") == pytest.approx(
        0.5 * (16383 / 65535.0 + 1.0), abs=1e-3
    )
    fader_sub11.set_level(1.0)
    assert dev1.get_channel_normalized_by_label("Gobo_Index/Speed") == pytest.approx(
        1.0, abs=1e-4
    )
    fader_sub11.set_level(0.0)
    assert dev1.get_channel_normalized_by_label("Gobo_Index/Speed") == pytest.approx(
        16383 / 65535.0, abs=1e-4
    )

    # Sub 12 lowers Gobo_Index/Speed toward 0.0 -> restores ~0.25
    fader_sub12.set_level(0.5)
    assert dev1.get_channel_normalized_by_label("Gobo_Index/Speed") == pytest.approx(
        0.5 * (16383 / 65535.0), abs=1e-3
    )
    fader_sub12.set_level(1.0)
    assert dev1.get_channel_normalized_by_label("Gobo_Index/Speed") == pytest.approx(
        0.0, abs=1e-4
    )
    fader_sub12.set_level(0.0)
    assert dev1.get_channel_normalized_by_label("Gobo_Index/Speed") == pytest.approx(
        16383 / 65535.0, abs=1e-4
    )

    # Sub 13 (intensity_master=True, channels={}) drives strobe 1.0 -> 25/255 -> 1.0
    assert dev1.strobe_hz == pytest.approx(1.0, abs=1e-3)
    fader_sub13.set_level(1.0)
    assert dev1.strobe_hz == pytest.approx(25 / 255.0, abs=1e-3)
    fader_sub13.set_level(0.0)
    assert dev1.strobe_hz == pytest.approx(1.0, abs=1e-3)

    # Sub 6 (intensity_master=True, channels={1,2,3}) must NOT overwrite pan/tilt
    dev1.set_pan_degrees(90.0)
    fader_sub6.set_level(1.0)
    assert dev1.pan_degrees == pytest.approx(90.0, abs=0.5)
    fader_sub6.set_level(0.0)
    assert dev1.pan_degrees == pytest.approx(90.0, abs=0.5)


def test_eos_param_token_parsing() -> None:
    """Unit-test parse_eos_param_token and eos_param_id_to_olc_key."""
    from olc.files.ascii.eos_devices import (
        eos_param_id_to_olc_key,
        parse_eos_param_token,
    )

    assert parse_eos_param_token("GL106#65535") == (65535.0, None)
    assert parse_eos_param_token("GL106#0") == (0.0, None)
    assert parse_eos_param_token("t255") == (255.0, None)
    assert parse_eos_param_token("u0") == (0.0, None)
    assert parse_eos_param_token("CP106") == (None, ("color", 106.0))
    assert parse_eos_param_token("FP12.5") == (None, ("focus", 12.5))
    assert parse_eos_param_token("BP2") == (None, ("beam", 2.0))
    assert parse_eos_param_token("IP3") == (None, ("intensity", 3.0))
    assert parse_eos_param_token("PR100") == (None, ("preset", 100.0))
    assert parse_eos_param_token("32768") == (32768.0, None)
    assert parse_eos_param_token("not_a_token") == (None, None)
    assert parse_eos_param_token("") == (None, None)

    ptypes = {
        1: "Intens",
        2: "Pan",
        12: "Red",
        76: "Diffusion",
        78: "Edge",
        57675: "Medium_Diffusion",
        9999: "UnknownParam",
    }
    assert eos_param_id_to_olc_key(1, ptypes) == "intensity"
    assert eos_param_id_to_olc_key(1, {}) == "intensity"
    assert eos_param_id_to_olc_key(2, ptypes) == "pan"
    assert eos_param_id_to_olc_key(12, ptypes) == "color"
    assert eos_param_id_to_olc_key(76, ptypes) == "frost"
    assert eos_param_id_to_olc_key(78, ptypes) == "focus"
    assert eos_param_id_to_olc_key(57675, ptypes) == "medium_diffusion"
    assert eos_param_id_to_olc_key(9999, ptypes) is None

    ptypes_ext = {
        **ptypes,
        206: "Gobo_Index/Speed",
        211: "Gobo_Select_2",
        240: "Frame_a_1",
        9998: "Custom_Blade",
    }
    assert eos_param_id_to_olc_key(206, ptypes_ext) == "gobo_index/speed"
    assert eos_param_id_to_olc_key(211, ptypes_ext) == "gobo_select_2"
    assert eos_param_id_to_olc_key(240, ptypes_ext) == "frame_a_1"
    assert eos_param_id_to_olc_key(9998, ptypes_ext) is None
    assert (
        eos_param_id_to_olc_key(
            9998, ptypes_ext, pers={"channels": [{"param_id": 9998}]}
        )
        == "custom_blade"
    )


def test_import_eos_palettes_special_formats_and_two_pass_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Test two-pass resolution when Cues/Preset/Sub appear before Eos palettes."""
    import pathlib

    from olc.show.palette import PaletteCategory

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 3 2 Tilt
$ParamType 12 3 Red
$ParamType 13 3 Green
$ParamType 14 3 Blue
$ParamType 76 5 Diffusion
$ParamType 57675 5 Medium_Diffusion
$Personality 100
   $$Manuf TestBrand
   $$Model Spot_RGB
   $$Footprint 7
   $$PersChan 1 1 1 0 0
   $$PersChan 2 2 2 3 32768
   $$PersSlot 0 65535 32768 -270.0 270.0 D
   $$PersChan 3 2 4 5 32768
   $$PersSlot 0 65535 32768 -135.0 135.0 D
   $$PersChan 76 1 6 0 0
   $$PersChan 57675 1 7 0 0
$Personality 200
   $$Manuf TestBrand
   $$Model RGB_Fixture
   $$Footprint 3
   $$VirtualInt
   $$PersChan 12 2 1 2 65535
   $$PersChan 13 2 3 4 65535
   $$PersChan 14 2 5 6 65535
$Patch 1 100 1 0 1
$Patch 3 100 10 0 1
$Patch 41 200 20 0 1
$CueList 1
Cue 1 1
   $$Param 1 1@IP3 2@FP12 3@FP12 76@BP2
   $$Param 41 12@CP106 13@CP106 14@CP106
Cue 2 1
   $$Param 1 2@PR100 3@PR100 76@PR100
Sub 6 1
   Text Color Sub
   Chan 41@Hff
   $$Param 41 12@CP106 13@CP106 14@CP106
$FaderDef 1
   $$Target S 6
Group 100
   Text Preset 100
   $$Param 1 2@FP12 3@FP12 76@BP2
$IntensityPalette 3
   Text IP 75
   Chan 1@75
$FocusPalette 12
   Text Center Spot
   $$Param 1 2@32768 3@65535
$ColorPalette 106
   Text L106
   $$Param 41 12@GL106#65535 13@GL106#1712 14@GL106#0
$BeamPalette 2
   Text FROST
   $$Param 1 76@t255 57675@t0
   $$Param 3 76@u255 57675@u0
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_two_pass.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    # 1. Base palettes decoded properly
    ip3 = lightshow.palettes.get(PaletteCategory.INTENSITY, 3.0)
    fp12 = lightshow.palettes.get(PaletteCategory.FOCUS, 12.0)
    cp106 = lightshow.palettes.get(PaletteCategory.COLOR, 106.0)
    bp2 = lightshow.palettes.get(PaletteCategory.BEAM, 2.0)
    assert ip3 is not None and ip3.channels[1] == pytest.approx(0.75)
    assert fp12 is not None and fp12.device_values[1]["pan"] == pytest.approx(
        0.0, abs=0.1
    )
    assert fp12.device_values[1]["tilt"] == pytest.approx(135.0, abs=0.1)
    assert cp106 is not None and cp106.device_values[41]["color"] == "#ff0700"
    assert bp2 is not None
    assert bp2.device_values[1]["frost"] == pytest.approx(1.0)
    assert bp2.device_values[3]["frost"] == pytest.approx(1.0)

    # 2. Eos Preset 100 resolved against FP12 & BP2
    pr100 = lightshow.palettes.get(PaletteCategory.PRESET, 100.0)
    assert pr100 is not None
    assert pr100.device_values[1]["pan"] == pytest.approx(0.0, abs=0.1)
    assert pr100.device_values[1]["tilt"] == pytest.approx(135.0, abs=0.1)
    assert pr100.device_values[1]["frost"] == pytest.approx(1.0)
    assert pr100.palette_refs[1]["pan"] == ("focus", 12.0)
    assert pr100.palette_refs[1]["frost"] == ("beam", 2.0)

    # 3. Cues defined before palettes resolved all refs + cascade from PR100
    cue1 = lightshow.get_cue(1.0, 1)
    cue2 = lightshow.get_cue(2.0, 1)
    assert cue1 is not None
    assert cue1.channels[1] == pytest.approx(0.75)
    assert cue1.device_values[1]["intensity"] == pytest.approx(0.75)
    assert cue1.device_values[1]["tilt"] == pytest.approx(135.0, abs=0.1)
    assert cue1.device_values[1]["frost"] == pytest.approx(1.0)
    assert cue1.device_values[41]["color"] == "#ff0700"
    assert cue1.palette_refs[1]["intensity"] == ("intensity", 3.0)
    assert cue1.palette_refs[41]["color"] == ("color", 106.0)

    assert cue2 is not None
    assert cue2.device_values[1]["frost"] == pytest.approx(1.0)
    assert cue2.palette_refs[1]["frost"] == ("preset", 100.0)

    # 4. Mounted Sub 6 (Preset 6) resolved CP106
    sub6 = lightshow.palettes.get(PaletteCategory.PRESET, 6.0)
    assert sub6 is not None
    assert sub6.channels[41] == pytest.approx(1.0)
    assert sub6.device_values[41]["color"] == "#ff0700"
    assert sub6.palette_refs[41]["color"] == ("color", 106.0)

    # 5. Live cascade propagation after import: editing BP2 updates Preset 100 & Cue 2
    bp2.device_values[1]["frost"] = 0.25
    res = lightshow.palettes.propagate_update(lightshow, PaletteCategory.BEAM, 2.0)
    assert res["presets"] >= 1
    assert res["cues"] >= 2
    assert pr100.device_values[1]["frost"] == pytest.approx(0.25)
    assert cue2.device_values[1]["frost"] == pytest.approx(0.25)


def test_import_eos_show_palettes_and_refs(
    _eos_show_imported: tuple[LightShow, ImportFile],
) -> None:
    """Verify eos_show.asc imports palettes and resolves Cue/Preset refs."""
    from olc.show.fader import FaderType
    from olc.show.palette import PaletteCategory

    lightshow, _imported = _eos_show_imported

    # Palette counts
    assert len(lightshow.palettes.list_by_category(PaletteCategory.COLOR)) == 26
    assert len(lightshow.palettes.list_by_category(PaletteCategory.BEAM)) == 64
    assert len(lightshow.palettes.list_by_category(PaletteCategory.FOCUS)) == 8
    assert len(lightshow.groups) == 7
    assert not any(g.index >= 500 for g in lightshow.groups)
    assert lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET

    # CP106 (L106)
    cp106 = lightshow.palettes.get(PaletteCategory.COLOR, 106.0)
    assert cp106 is not None and cp106.text == "ColorPalette 106"
    assert cp106.device_values[1]["color"] == "#ff0000"
    assert cp106.device_values[41]["color"] == "#ff0700"

    # BP1 (NO FROST) and BP2 (FROST)
    bp1 = lightshow.palettes.get(PaletteCategory.BEAM, 1.0)
    bp2 = lightshow.palettes.get(PaletteCategory.BEAM, 2.0)
    assert bp1 is not None and bp2 is not None
    for ch in range(1, 6):
        assert bp1.device_values[ch]["frost"] == pytest.approx(0.0)
        assert bp2.device_values[ch]["frost"] == pytest.approx(1.0)

    # FP10 pan/tilt on ch 4 & 5
    fp10 = lightshow.palettes.get(PaletteCategory.FOCUS, 10.0)
    assert fp10 is not None
    assert fp10.device_values[4]["pan"] == pytest.approx(-55.3, abs=0.2)
    assert fp10.device_values[5]["tilt"] == pytest.approx(-6.9, abs=0.2)

    # Eos Preset 110 references BP2 on channel 1
    pr110 = lightshow.palettes.get(PaletteCategory.PRESET, 110.0)
    assert pr110 is not None
    assert pr110.device_values[1]["frost"] == pytest.approx(1.0)
    assert pr110.palette_refs[1]["frost"] == ("beam", 2.0)

    # Cues with CP106, PR100, BP2 references resolved cleanly
    cue99 = lightshow.get_cue(99.0, 1)
    assert cue99 is not None
    assert cue99.device_values[41]["color"] == "#ff0700"
    assert cue99.palette_refs[41]["color"] == ("color", 106.0)

    cue100 = lightshow.get_cue(100.0, 1)
    assert cue100 is not None
    assert cue100.device_values[1]["color"] == "#ff0000"
    assert cue100.palette_refs[1]["color"] == ("color", 106.0)
    assert cue100.palette_refs[1]["pan"] == ("preset", 100.0)

    cue106 = lightshow.get_cue(106.0, 1)
    assert cue106 is not None
    assert cue106.device_values[1]["frost"] == pytest.approx(1.0)
    assert cue106.palette_refs[1]["frost"] == ("beam", 2.0)


def test_import_eos_fixture_library_definitions_modes_and_color_profiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Verify FixtureDefinition import (0-based, 16-bit, modes, $$Pers)."""
    import pathlib

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 3 2 Tilt
$ParamType 9 3 Cyan
$ParamType 10 3 Magenta
$ParamType 11 3 Yellow
$ParamType 12 3 Red
$ParamType 13 3 Green
$ParamType 14 3 Blue
$ParamType 51 3 White
$Personality 10
   $$Manuf BrandA
   $$Model DuoSpot
   $$Footprint 7
   $$PersChan 1 1 1 0 0
   $$PersChan 2 2 2 3 32768
   $$PersSlot 0 65535 32768 -270.0 270.0 D
   $$PersChan 9 1 4 0 0
   $$PersChan 10 1 5 0 0
   $$PersChan 11 1 6 0 0
   $$PersChan 3 1 7 0 128
$Personality 11
   $$Manuf BrandA
   $$Model DuoSpot
   $$Footprint 4
   $$PersChan 1 2 1 2 65535
   $$PersChan 2 2 3 4 32768
$Personality 20
   $$Manuf BrandB
   $$Model LedRGBW
   $$Footprint 9
   $$PersChan 1 1 1 0 0
   $$PersChan 12 2 2 3 65535
   $$PersChan 13 2 4 5 65535
   $$PersChan 14 2 6 7 65535
   $$PersChan 51 2 8 9 65535
$Personality 30
   $$Manuf BrandC
   $$Model UnpatchedWash
   $$Footprint 4
   $$PersChan 12 1 1 0 255
   $$PersChan 13 1 2 0 255
   $$PersChan 14 1 3 0 255
   $$PersChan 48 1 4 0 255
$Personality 40
   $$Manuf Generic
   $$Model Dimmer
   $$Footprint 1
   $$PersChan 1 1 1 0 0
$Patch 1 10 500 0 1
   $$Pers AliasNameThatDiffers
$Patch 2 11 100 0 1
$Patch 3 20 200 0 1
$Patch 4 40 1 0 1
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_fixture_lib.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    # All non-dimmer personalities imported (patched + unpatched)
    non_builtin = [f for f in lightshow.fixture_library.all() if not f.is_builtin]
    assert len(non_builtin) == 3

    # Mode collision merged under BrandA:DuoSpot, CMY gets subtractive color_profile
    duospot = lightshow.fixture_library.get("BrandA", "DuoSpot")
    assert duospot.mode_names() == ["7ch", "4ch"]
    assert duospot.color_profile is not None
    assert duospot.color_profile.mixing_mode == "subtractive"
    mode7 = duospot.get_mode("7ch")
    assert mode7.footprint() == 7
    assert len(mode7.channel_defs) == 6
    assert mode7.channel_defs[0].offset == 0
    assert mode7.channel_defs[1].offset == 1
    assert mode7.channel_defs[1].fine_offset == 2
    assert mode7.channel_defs[1].default_value == 32768
    mode4 = duospot.get_mode("4ch")
    assert mode4.footprint() == 4
    assert mode4.channel_defs[0].offset == 0
    assert mode4.channel_defs[0].fine_offset == 1
    assert mode4.channel_defs[0].default_value == 65535

    # $$Pers alias does not break count_devices_using_definition or sync
    assert lightshow.patch.count_devices_using_definition("BrandA", "DuoSpot") == 2
    dev1 = lightshow.patch.get_device(1)
    assert dev1 is not None and dev1.mode_name == "7ch"
    addrs_before = [(c.universe, c.address, c.channel_type) for c in dev1.channels]
    synced = lightshow.patch.sync_devices_with_definition(duospot)
    assert set(synced) == {1, 2}
    dev1_after = lightshow.patch.get_device(1)
    assert dev1_after is not None
    dev1_after_addrs = [
        (c.universe, c.address, c.channel_type) for c in dev1_after.channels
    ]
    assert dev1_after_addrs == addrs_before

    # LED RGBW gets generic RGBW color profile and 16-bit default 65535
    led = lightshow.fixture_library.get("BrandB", "LedRGBW")
    assert led.color_profile is not None
    assert [e.name for e in led.color_profile.emitters] == [
        "Red",
        "Green",
        "Blue",
        "White",
    ]
    led_mode = led.default_mode()
    assert led_mode.footprint() == 9
    assert led_mode.channel_defs[1].default_value == 65535

    # Unpatched non-dimmer personality is imported with used == 0
    unpatched = lightshow.fixture_library.get("BrandC", "UnpatchedWash")
    assert (
        lightshow.patch.count_devices_using_definition("BrandC", "UnpatchedWash") == 0
    )
    assert unpatched.default_mode().footprint() == 4
    assert unpatched.default_mode().channel_defs[3].label == "param_48"


def test_import_eos_show_fixture_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify eos_show.asc populates fixture_library cleanly (Scenario B)."""
    from olc.devices.channel import ChannelType

    asc_path = DATA_DIR / "eos_show.asc"

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    non_builtin = [f for f in lightshow.fixture_library.all() if not f.is_builtin]
    assert len(non_builtin) == 9

    # Moving heads (CMY -> subtractive color_profile)
    ghibli = lightshow.fixture_library.get("Ayrton", "Ghibli_Extended")
    ghibli_mode = ghibli.default_mode()
    assert len(ghibli_mode.channel_defs) == 35
    assert ghibli_mode.footprint() == 58
    assert ghibli_mode.channel_defs[0].offset == 0
    assert ghibli_mode.channel_defs[0].fine_offset == 1
    assert ghibli_mode.channel_defs[0].default_value == 32768
    beam_fx = next(cd for cd in ghibli_mode.channel_defs if cd.offset == 35)
    assert beam_fx.fine_offset == 36
    assert beam_fx.default_value == 16383
    assert ghibli.color_profile is not None
    assert ghibli.color_profile.mixing_mode == "subtractive"
    assert (
        lightshow.patch.count_devices_using_definition("Ayrton", "Ghibli_Extended") == 3
    )

    diablo = lightshow.fixture_library.get("Ayrton", "Diablo_S_Extended_Pan_540")
    diablo_mode = diablo.default_mode()
    assert len(diablo_mode.channel_defs) == 33
    assert diablo_mode.footprint() == 56
    assert diablo.color_profile is not None
    assert diablo.color_profile.mixing_mode == "subtractive"
    assert (
        lightshow.patch.count_devices_using_definition(
            "Ayrton", "Diablo_S_Extended_Pan_540"
        )
        == 2
    )

    # Cameo F1 FC (RGBW additive -> RGBW color_profile, 16-bit defaults intact)
    cameo_fc = lightshow.fixture_library.get("Cameo", "F1_FC_16_CH_Direct_CCT")
    cameo_mode = cameo_fc.default_mode()
    assert len(cameo_mode.channel_defs) == 11
    assert cameo_mode.footprint() == 16
    for ct in (ChannelType.RED, ChannelType.GREEN, ChannelType.BLUE, ChannelType.WHITE):
        cd = next(c for c in cameo_mode.channel_defs if c.channel_type is ct)
        assert cd.default_value == 65535
    assert cameo_fc.color_profile is not None
    assert [e.name for e in cameo_fc.color_profile.emitters] == [
        "Red",
        "Green",
        "Blue",
        "White",
    ]
    assert (
        lightshow.patch.count_devices_using_definition(
            "Cameo", "F1_FC_16_CH_Direct_CCT"
        )
        == 4
    )

    # Unpatched non-dimmer personalities (used == 0)
    expected_unpatched: list[tuple[str, str, int, list[str] | None]] = [
        ("Cameo", "F1_T_5ch", 5, None),
        ("Cameo", "Zenit_W_600_2ch", 2, None),
        ("Coemar", "ParLite_LED_RGBW", 4, ["Red", "Green", "Blue", "White"]),
        ("Custom", "ParLite_LED_RGBA", 4, ["Red", "Green", "Blue", "Amber"]),
        ("GLP", "Fusion_XPAR_12Z_M3_Adv", 16, ["Red", "Green", "Blue", "Lime"]),
        (
            "OXO_Show_Solutions",
            "Multibeam_LED_FCW_M4",
            5,
            ["Red", "Green", "Blue", "White"],
        ),
    ]
    for mfg, mod, exp_fp, exp_emitters in expected_unpatched:
        fdef = lightshow.fixture_library.get(mfg, mod)
        assert fdef.default_mode().footprint() == exp_fp
        assert len(fdef.default_mode().channel_defs) > 0
        assert lightshow.patch.count_devices_using_definition(mfg, mod) == 0
        if exp_emitters is None:
            assert fdef.color_profile is None
        else:
            assert fdef.color_profile is not None
            assert [e.name for e in fdef.color_profile.emitters] == exp_emitters

    # Apply to Show round-trip preserves channel count and exact DMX addresses
    dev1 = lightshow.patch.get_device(1)
    dev41 = lightshow.patch.get_device(41)
    assert dev1 is not None and dev41 is not None
    dev1_addrs = [(c.universe, c.address, c.channel_type) for c in dev1.channels]
    dev41_addrs = [(c.universe, c.address, c.channel_type) for c in dev41.channels]
    assert len(dev1_addrs) == 58 and len(dev41_addrs) == 16

    lightshow.patch.sync_devices_with_definition(ghibli)
    lightshow.patch.sync_devices_with_definition(cameo_fc)
    dev1_after = lightshow.patch.get_device(1)
    dev41_after = lightshow.patch.get_device(41)
    assert dev1_after is not None and dev41_after is not None
    assert [
        (c.universe, c.address, c.channel_type) for c in dev1_after.channels
    ] == dev1_addrs
    assert [
        (c.universe, c.address, c.channel_type) for c in dev41_after.channels
    ] == dev41_addrs

    # Scenario B: setting pure red on RGBW zeroes out White channel via NNLS
    dev41_after.set_color_hex("#ff0000")
    red_ch = dev41_after.get_channel(ChannelType.RED)
    white_ch = dev41_after.get_channel(ChannelType.WHITE)
    assert red_ch is not None and red_ch.value == 255
    assert white_ch is not None and white_ch.value == 0


def test_import_eos_case_slots_units_notes_and_inversions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Verify synthetic Eos case, slash params, slots, units, notes, inversions."""
    import pathlib

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 79 5 Zoom
$ParamType 206 4 Gobo_Index/Speed
$ParamType 1719 3 Color_Temperature
$Personality 500
   $$Manuf MixedBrand
   $$Model Test_Fixture_X
   $$Footprint 6
   $$PersChan 1 1 1 0 0
   $$PersSlot 0 255 0 0.0 100.0 %
   $$PersChan 2 2 2 3 32768
   $$PersSlot 0 65535 32768 -270.0 270.0 -270 to 270 D
   $$PersChan 206 1 4 0 0
   $$PersSlot 0 9 0 0.0 0.0 Stop
   $$PersSlot 10 255 128 1.0 100.0
   $$PersSlText Indexed / Rotate
   $$PersChan 1719 1 5 0 0
   $$PersSlot 255 0 0 3200.0 8500.0 Temp +
   $$PersChan 79 1 6 0 128
   $$PersSlot 0 0 0 0.0 0.0 Off
   $$PersSlot 255 1 128 10.0 50.0 10 to 50 D
   $$Notes First part&#10;Second li
   $$Notes ne!
$Patch 10 500 1 0 1
$CueList 1
Cue 1 1
   $$Param 10 1719@255
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_personalities.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    fdef = lightshow.fixture_library.get("MixedBrand", "Test_Fixture_X")
    assert fdef.manufacturer == "MixedBrand"
    assert fdef.model == "Test_Fixture_X"
    assert fdef.notes == "First part\nSecond line!"

    chans = {cd.offset + 1: cd for cd in fdef.default_mode().channel_defs}
    assert chans[1].label == "Intens"
    assert chans[1].physical_unit == "%"
    assert chans[1].ranges == []

    assert chans[2].label == "Pan"
    assert chans[2].physical_unit == "deg"
    assert chans[2].ranges == []

    # Slash parameter and $$PersSlText preserved
    assert chans[4].label == "Gobo_Index/Speed"
    assert [r.label for r in chans[4].ranges] == ["Stop", "Indexed / Rotate"]
    assert chans[4].ranges[1].value_min == 10
    assert chans[4].ranges[1].value_max == 255

    # Single-slot inverted channel: 255..0 maps 3200..8500 => 8500 -> 3200 K
    assert chans[5].label == "Color_Temperature"
    assert chans[5].physical_unit == "K"
    assert chans[5].physical_min == 8500.0
    assert chans[5].physical_max == 3200.0
    assert chans[5].ranges == []

    # Multi-slot with reversed DMX slot normalized + physical inverted on that slot
    assert chans[6].label == "Zoom"
    assert chans[6].physical_unit == "deg"
    assert [(r.value_min, r.value_max) for r in chans[6].ranges] == [(0, 0), (1, 255)]
    assert chans[6].ranges[1].physical_min == 50.0
    assert chans[6].ranges[1].physical_max == 10.0


def test_import_eos_show_slots_units_notes_and_inversions(
    _eos_show_imported: tuple[LightShow, ImportFile],
) -> None:
    """Verify eos_show.asc preserves case, slots, units, notes."""
    import itertools

    lightshow, _imported = _eos_show_imported

    # Exact case preserved
    ghibli = lightshow.fixture_library.get("Ayrton", "Ghibli_Extended")
    assert ghibli.manufacturer == "Ayrton"
    assert ghibli.model == "Ghibli_Extended"
    diablo = lightshow.fixture_library.get("Ayrton", "Diablo_S_Extended_Pan_540")
    assert diablo.manufacturer == "Ayrton"
    assert diablo.model == "Diablo_S_Extended_Pan_540"
    cameo_fc = lightshow.fixture_library.get("Cameo", "F1_FC_16_CH_Direct_CCT")
    assert cameo_fc.manufacturer == "Cameo"
    assert cameo_fc.model == "F1_FC_16_CH_Direct_CCT"
    oxo = lightshow.fixture_library.get("OXO_Show_Solutions", "Multibeam_LED_FCW_M4")
    assert oxo.manufacturer == "OXO_Show_Solutions"
    assert oxo.model == "Multibeam_LED_FCW_M4"

    # Slash parameter names intact + physical units + single-slot no redundant ranges
    ghibli_chs = ghibli.default_mode().channel_defs
    ghibli_by_off = {cd.offset: cd for cd in ghibli_chs}
    assert ghibli_by_off[0].label == "Pan"
    assert ghibli_by_off[0].physical_unit == "deg"
    assert ghibli_by_off[0].ranges == []
    assert ghibli_by_off[2].label == "Tilt"
    assert ghibli_by_off[2].physical_unit == "deg"
    assert ghibli_by_off[6].label == "Intens"
    assert ghibli_by_off[6].physical_unit == "%"
    assert ghibli_by_off[6].ranges == []
    assert ghibli_by_off[11].label == "Zoom"
    assert ghibli_by_off[11].physical_unit == "deg"
    assert ghibli_by_off[28].label == "Gobo_Index/Speed"
    assert ghibli_by_off[35].label == "Beam_Fx_Index/Speed"
    # Continuous inverted channel on Ghibli: Frame_Assembly (65535..0 -> -100..100%)
    assert ghibli_by_off[55].label == "Frame_Assembly"
    assert ghibli_by_off[55].physical_unit == "%"
    assert ghibli_by_off[55].physical_min == 100.0
    assert ghibli_by_off[55].physical_max == -100.0

    # Diablo: slash params, 16-bit Edge_Mode converted cleanly, Frame_Assembly deg
    diablo_by_off = {cd.offset: cd for cd in diablo.default_mode().channel_defs}
    assert diablo_by_off[28].label == "Gobo_Index/Speed"
    assert diablo_by_off[34].label == "Beam_Fx_Index/Speed"
    assert diablo_by_off[53].label == "Frame_Assembly"
    assert diablo_by_off[53].physical_unit == "deg"
    assert diablo_by_off[53].physical_min == 45.0
    assert diablo_by_off[53].physical_max == -45.0
    edge_mode = diablo_by_off[15]
    assert edge_mode.label == "Edge_Mode"
    assert [r.label for r in edge_mode.ranges] == [
        "Continuous",
        "5m Auto Focus",
        "7.5m Auto Focus",
        "10m Auto Focus",
        "15m Auto Focus",
    ]
    for prev, nxt in itertools.pairwise(edge_mode.ranges):
        assert prev.value_max < nxt.value_min

    # Cameo F1_FC: Red %, Color_Temperature K + 7 slots, Tint inverted, Color_Mix LEE
    cameo_by_off = {cd.offset: cd for cd in cameo_fc.default_mode().channel_defs}
    assert cameo_by_off[3].label == "Red"
    assert cameo_by_off[3].physical_unit == "%"
    cct = cameo_by_off[11]
    assert cct.label == "Color_Temperature"
    assert cct.physical_unit == "K"
    assert len(cct.ranges) == 7
    assert cct.ranges[0].label == "Off"
    assert cct.ranges[1].label == "2700"
    assert cct.ranges[-1].label == "Temp +"

    tint = cameo_by_off[12]
    assert tint.label == "Tint"
    assert tint.physical_unit == "%"
    assert [(r.value_min, r.value_max) for r in tint.ranges] == [(0, 0), (1, 255)]
    assert tint.ranges[1].physical_min == 100.0
    assert tint.ranges[1].physical_max == -100.0

    cmix = cameo_by_off[13]
    assert cmix.label == "Color_Mix"
    assert len(cmix.ranges) > 50
    cmix_labels = {r.label for r in cmix.ranges}
    assert "135 - Deep Golden Amber" in cmix_labels
    assert "778 - Millennium Gold" in cmix_labels
    for prev, nxt in itertools.pairwise(cmix.ranges):
        assert prev.value_max < nxt.value_min

    # Zenit_W_600_2ch: single-slot inverted CTO
    zenit = lightshow.fixture_library.get("Cameo", "Zenit_W_600_2ch")
    zenit_cct = zenit.default_mode().channel_defs[1]
    assert zenit_cct.label == "Color_Temperature"
    assert zenit_cct.physical_unit == "K"
    assert zenit_cct.physical_min == 8500.0
    assert zenit_cct.physical_max == 3200.0

    # GLP Fusion: Color_Mix includes $$PersSlText labels
    glp = lightshow.fixture_library.get("GLP", "Fusion_XPAR_12Z_M3_Adv")
    glp_cmix = next(
        cd for cd in glp.default_mode().channel_defs if cd.label == "Color_Mix"
    )
    assert any(r.label == "Stop At Current color" for r in glp_cmix.ranges)

    # Custom ParLite_LED_RGBA: $$Notes decoded and unwrapped
    rgba = lightshow.fixture_library.get("Custom", "ParLite_LED_RGBA")
    assert "flash in this range" in rgba.notes
    assert "DMX Status: Tested\nRDM Status: Not Supported" in rgba.notes


_EOS_EFFECTS_ASC = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 3 2 Tilt
$ParamType 12 3 Red
$ParamType 13 3 Green
$ParamType 14 3 Blue
$ParamType 79 5 Zoom
$Effect 3
   Text strob|| Abs
   $$Type 4 ! Absolute
   $$Grouping 1
   $$Action   1  0.02 0 0
   $$Action   2  0.01 0 Bkgrd
$Effect 7
   Text sin
   $$Type 1 ! Linear
   $$Scale 50
   $$Data   1 0
$Effect 5
   Text zoom -> mini||Sin
   $$Type 1 ! Linear
   $$Scale 15
   $$ParamList  79
   $$Data   1 0
$Effect 901
   Text Figure 8
   $$Type 2 ! Focus
   $$Scale 27
   $$ParamList  2 3
   $$Dimensions 2
   $$Data   1 0 1
$Effect 917
   Text Rainbow RGB
   $$Type 1 ! Linear
   $$ParamList  12 13 14
   $$Data   1 0 0 0
$Effect 100
   Text CHENILLARD
   $$Type 5 ! StepBased
   $$Step   1  1 1 0 1 100 0
   $$ChanList      3
   $$Step   2  1 1 0 1 100 0
   $$ChanList      1
$CueList 1
Cue 1 1
   Chan 1@Hff
   $$EffectChan  7  21  1
   $$EffectChan  7  22  1
   $$EffectChan  7  23  1
   $$EffectData  7  Rate 79
   $$EffectData  7  Size 50
Cue 2 1
   Chan 1@Hff
   $$EffectData  7  Rate 30
Cue 3 1
   Chan 1@Hff
   $$EffectChan  0  22  1
EndData
"""


def _parse_asc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object, content: str
) -> ImportFile:
    import pathlib

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_effects.asc"
    asc_file.write_text(content, encoding="utf-8")
    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)
    return imported


def test_import_eos_effect_definitions_and_cue_refs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Eos $Effect blocks and $$EffectChan/$$EffectData are imported."""
    imported = _parse_asc(monkeypatch, tmp_path, _EOS_EFFECTS_ASC)
    effects = imported.lightshow.effects

    assert len(effects) == 6

    strobe = effects.get(3.0)
    assert strobe is not None
    assert strobe.groups == 1
    assert strobe.layers[0].parameter == "intensity"
    assert strobe.layers[0].low_value == 0.0
    assert strobe.layers[0].mode.value == "absolute"

    sine = effects.get(7.0)
    assert sine is not None
    assert sine.layers[0].size == 50.0

    zoom = effects.get(5.0)
    assert zoom is not None
    assert zoom.layers[0].parameter == "zoom"
    assert zoom.layers[0].size == 15.0

    fig8 = effects.get(901.0)
    assert fig8 is not None
    assert [layer.parameter for layer in fig8.layers] == ["pan", "tilt"]
    assert fig8.layers[1].freq_mult == 2.0
    assert fig8.layers[0].size == 27.0

    rainbow = effects.get(917.0)
    assert rainbow is not None
    assert rainbow.layers[0].parameter == "color"
    assert rainbow.layers[0].waveform.value == "rainbow"

    chase = effects.get(100.0)
    assert chase is not None
    assert chase.groups == 2

    cues = [s.cue for s in imported.lightshow.main_playback.steps if s.cue]
    cue1 = next(c for c in cues if c.number == 1.0)
    cue2 = next(c for c in cues if c.number == 2.0)
    cue3 = next(c for c in cues if c.number == 3.0)

    assert sorted(cue1.effect_refs) == [21, 22, 23]
    assert cue1.effect_refs[21]["order_index"] == 0
    assert cue1.effect_refs[23]["order_index"] == 2
    assert cue1.effect_refs[22]["channels"] == [21, 22, 23]
    assert cue1.effect_refs[21]["rate_scale"] == pytest.approx(0.79)
    assert cue1.effect_refs[21]["size_scale"] == pytest.approx(0.5)

    # Data-only cue updates the tracked effect on the same ordered channels
    assert cue2.effect_refs[21]["effect"] == 7.0
    assert cue2.effect_refs[21]["rate_scale"] == pytest.approx(0.30)

    # EffectChan 0 is a Stop Effect marker
    assert cue3.effect_refs[22] == {"stop": True}


def test_import_eos_effects_action_merge_and_ignore(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Import actions Replace / Merge / Ignore apply to effects."""
    from olc.files.import_types import Action
    from olc.show.effect import EffectDefinition

    imported = _parse_asc(monkeypatch, tmp_path, _EOS_EFFECTS_ASC)
    show = imported.lightshow

    # Merge keeps an unrelated pre-existing effect
    show.effects.add(EffectDefinition(number=500.0, label="Keep me"))
    imported.actions["effects"] = Action.MERGE
    imported.do_import()
    assert show.effects.get(500.0) is not None
    assert show.effects.get(3.0) is not None

    # Replace clears it
    imported.actions["effects"] = Action.REPLACE
    imported.do_import()
    assert show.effects.get(500.0) is None
    assert show.effects.get(3.0) is not None

    # Ignore leaves the pool untouched
    show.effects.add(EffectDefinition(number=501.0, label="Stay"))
    imported.actions["effects"] = Action.IGNORE
    imported.do_import()
    assert show.effects.get(501.0) is not None


def test_import_eos_sub_effect_mounted_on_effect_fader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """A Sub carrying $$EffectChan mounted on a fader becomes an Effect fader."""
    from olc.show.fader import FaderEffect, FaderType

    content = _EOS_EFFECTS_ASC.replace(
        "$CueList 1",
        """Sub 20 1
   Text chaser horaire
   Chan 21@Hff 22@Hff
   $$EffectChan  7  22  1
   $$EffectChan  7  21  1
$FaderDef 1
   $$Target S 20
$CueList 1""",
    )
    imported = _parse_asc(monkeypatch, tmp_path, content)
    show = imported.lightshow

    assert show.fader_bank.get_fader_type(1, 1) == FaderType.EFFECT
    fader = show.fader_bank.faders[1][1]
    assert isinstance(fader, FaderEffect)
    assert fader.contents is show.effects.get(7.0)
    assert fader.effect_channels == [22, 21]


def test_import_eos_show_effects(
    _eos_show_imported: tuple[LightShow, ImportFile],
) -> None:
    """Verify eos_show.asc imports its 34 effects and cue refs."""
    lightshow, _imported = _eos_show_imported

    assert len(lightshow.effects) == 34
    circle = lightshow.effects.get(901.0)
    assert circle is not None
    assert [layer.parameter for layer in circle.layers] == ["pan", "tilt"]
    rainbow = lightshow.effects.get(917.0)
    assert rainbow is not None
    assert rainbow.layers[0].waveform.value == "rainbow"

    cue106 = lightshow.get_cue(106.0, 1)
    assert cue106 is not None
    assert cue106.effect_refs[21]["effect"] == 7.0
    assert cue106.effect_refs[21]["channels"] == [21, 22, 23, 24, 25, 26]
    assert cue106.effect_refs[21]["rate_scale"] == pytest.approx(0.79)

    cue107 = lightshow.get_cue(107.0, 1)
    assert cue107 is not None
    assert cue107.effect_refs[1] == {"stop": True}

    # Eos CueLists use Tracking mode so effects and $$ChanMove blackouts propagate
    from olc.core.tracking import TrackingEngine

    assert lightshow.main_playback.tracking_mode is True
    assert all(seq.tracking_mode is True for seq in lightshow.sequences)

    step_by_cue = {
        step.cue.number: idx
        for idx, step in enumerate(lightshow.main_playback.steps)
        if step.cue is not None and step.cue.number != 0
    }

    res103 = TrackingEngine.resolve_step_state(
        lightshow.main_playback,
        step_by_cue[103.0],
        tracking_mode=True,
        patch=lightshow.patch,
    )
    for ch in range(21, 41):
        assert res103.channels[ch - 1] == pytest.approx(0.0)

    res106 = TrackingEngine.resolve_step_state(
        lightshow.main_playback,
        step_by_cue[106.0],
        tracking_mode=True,
        patch=lightshow.patch,
    )
    assert {spec["effect"] for spec in res106.effect_refs.values()} == {7.0, 11.0}

    # Cue 107 stops ch 1..3 (FX 11) while FX 7 on ch 21..26 keeps tracking
    res107 = TrackingEngine.resolve_step_state(
        lightshow.main_playback,
        step_by_cue[107.0],
        tracking_mode=True,
        patch=lightshow.patch,
    )
    assert {spec["effect"] for spec in res107.effect_refs.values()} == {7.0}
    assert sorted(res107.effect_refs.keys()) == [21, 22, 23, 24, 25, 26]

    # Cue 110 stops FX 7 on ch 21..26
    res110 = TrackingEngine.resolve_step_state(
        lightshow.main_playback,
        step_by_cue[110.0],
        tracking_mode=True,
        patch=lightshow.patch,
    )
    assert res110.effect_refs == {}

    # Cue 165 blacks out both moving heads (1..5) and LEDs (41..44) via $$ChanMove
    res165 = TrackingEngine.resolve_step_state(
        lightshow.main_playback,
        step_by_cue[165.0],
        tracking_mode=True,
        patch=lightshow.patch,
    )
    for ch in (1, 2, 3, 4, 5, 41, 42, 43, 44):
        assert res165.channels[ch - 1] == pytest.approx(0.0)
        assert res165.device_values.get(ch, {}).get("intensity", 0.0) == pytest.approx(
            0.0
        )


def test_ascii_export_import_effects_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """AsciiWriter round-trips effects, cue effect_refs, and Effect faders."""
    import pathlib

    from olc.files.ascii.writer import AsciiWriter
    from olc.show.cue import Cue
    from olc.show.effect import DistributeDirection
    from olc.show.fader import FaderEffect, FaderType
    from olc.show.palette import Palette, PaletteCategory
    from olc.show.sequence import Sequence
    from olc.show.step import Step

    assert isinstance(tmp_path, pathlib.Path)
    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    show = LightShow()
    show.palettes.add(
        Palette(
            category=PaletteCategory.COLOR,
            number=1.0,
            text="Red",
            device_values={1: {"color": "#ff0000"}},
        )
    )
    show.palettes.add(
        Palette(
            category=PaletteCategory.COLOR,
            number=2.0,
            text="Blue",
            device_values={1: {"color": "#0000ff"}},
        )
    )

    eff1 = show.effects.create_from_template("sine_dimmer", 1.0, label="Warm Sine")
    eff1.groups = 2
    show.effects.create_from_template("circle", 2.0, label="Circle")
    eff3 = show.effects.create_from_template("rainbow", 3.0, label="Rainbow")
    eff3.direction = DistributeDirection.RANDOM
    eff4 = show.effects.create_from_template(
        "two_color_chase", 4.0, label="Color Bounce"
    )
    eff4.layers[0].softness = 0.0

    # Main playback cues: Cue 1 starts Effect 1 on [3, 1, 2]; Cue 2 stops ch 1
    cue1 = Cue(
        1,
        1.0,
        {1: 1.0, 2: 0.8, 3: 0.6},
        text="FX Start",
        effect_refs={
            ch: {
                "effect": 1.0,
                "order_index": idx,
                "channels": [3, 1, 2],
                "rate_scale": 0.8,
                "size_scale": 0.6,
            }
            for idx, ch in enumerate([3, 1, 2])
        },
    )
    cue2 = Cue(1, 2.0, {}, text="FX Stop ch1", effect_refs={1: {"stop": True}})
    show.main_playback.insert_step(1, Step(1, cue=cue1, text="FX Start"))
    show.main_playback.insert_step(2, Step(1, cue=cue2, text="FX Stop ch1"))

    # Secondary Sequence 2 Cue 1 starts Effect 2 on [10, 11]
    seq2 = Sequence(2, text="FX Seq", lightshow=show)
    seq2_cue1 = Cue(
        2,
        1.0,
        {10: 1.0, 11: 1.0},
        text="Sec FX",
        effect_refs={
            10: {"effect": 2.0, "order_index": 0, "channels": [10, 11]},
            11: {"effect": 2.0, "order_index": 1, "channels": [10, 11]},
        },
    )
    seq2.cues.add(seq2_cue1)
    seq2.insert_step(1, Step(2, cue=seq2_cue1, text="Sec FX"))
    show.sequences.append(seq2)

    # Effect Fader on page 1, index 1 with control_mode='both' & channels [3, 1, 2]
    show.fader_bank.set_fader(1, 1, FaderType.EFFECT, 1.0)
    fader1 = show.fader_bank.faders[1][1]
    assert isinstance(fader1, FaderEffect)
    fader1.set_control_mode("both")
    fader1.set_effect_channels([3, 1, 2])

    asc_path = tmp_path / "effects_roundtrip.asc"
    AsciiWriter(asc_path, show).write()
    assert asc_path.exists()

    # Re-import into a fresh LightShow
    reimported = LightShow()
    importer = ImportFile(
        reimported, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    importer.parse_sync(auto_import=True)

    assert len(reimported.effects) == 4
    re_eff1 = reimported.effects.get(1.0)
    assert re_eff1 is not None
    assert re_eff1.label == "Warm Sine"
    assert re_eff1.groups == 2
    assert re_eff1.layers[0].waveform.value == "sine"

    re_eff2 = reimported.effects.get(2.0)
    assert re_eff2 is not None
    assert [layer.parameter for layer in re_eff2.layers] == ["pan", "tilt"]
    assert re_eff2.layers[0].size == pytest.approx(15.0)

    re_eff3 = reimported.effects.get(3.0)
    assert re_eff3 is not None
    assert re_eff3.direction == DistributeDirection.RANDOM
    assert re_eff3.layers[0].waveform.value == "rainbow"

    re_eff4 = reimported.effects.get(4.0)
    assert re_eff4 is not None
    assert re_eff4.layers[0].parameter == "color"
    assert re_eff4.layers[0].low_palette == ("color", 1.0)
    assert re_eff4.layers[0].high_palette == ("color", 2.0)
    assert re_eff4.layers[0].softness == pytest.approx(0.0)

    # Verify main playback cue effect_refs round-trip
    re_cues = [s.cue for s in reimported.main_playback.steps if s.cue]
    re_cue1 = next(c for c in re_cues if c.number == 1.0)
    re_cue2 = next(c for c in re_cues if c.number == 2.0)
    assert re_cue1.effect_refs[3]["effect"] == 1.0
    assert re_cue1.effect_refs[3]["order_index"] == 0
    assert re_cue1.effect_refs[1]["order_index"] == 1
    assert re_cue1.effect_refs[2]["order_index"] == 2
    assert re_cue1.effect_refs[3]["channels"] == [3, 1, 2]
    assert re_cue1.effect_refs[3]["rate_scale"] == pytest.approx(0.8)
    assert re_cue1.effect_refs[3]["size_scale"] == pytest.approx(0.6)
    assert re_cue2.effect_refs[1] == {"stop": True}

    # Verify secondary sequence cue effect_refs
    re_seq2 = reimported.get_sequence(2)
    assert re_seq2 is not None
    re_seq2_cue1 = next(c for c in re_seq2.cues if c.number == 1.0)
    assert re_seq2_cue1.effect_refs[10]["effect"] == 2.0
    assert re_seq2_cue1.effect_refs[10]["channels"] == [10, 11]

    # Verify FaderEffect round-trip
    assert reimported.fader_bank.get_fader_type(1, 1) == FaderType.EFFECT
    re_fader1 = reimported.fader_bank.faders[1][1]
    assert isinstance(re_fader1, FaderEffect)
    assert re_fader1.contents is re_eff1
    assert re_fader1.control_mode == "both"
    assert re_fader1.effect_channels == [3, 1, 2]


def test_import_eos_chanmove_tracking_blackouts_and_cp1252_decoding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Test $$ChanMove 8/16-bit tracking blackouts, $$Block, effects, and cp1252."""
    import pathlib

    from olc.core.tracking import TrackingEngine
    from olc.files.read import decode_file_bytes

    # 1. decode_file_bytes prefers UTF-8 cleanly and resolves cp1252 vs cp1250 ties
    cp1252_text = (
        "Ident 3:0\n"
        "$Curve 905\n   Text Full à 1%\n"
        "$Curve 907\n   Text Préchauffe à 5%\n"
        "$CueList 1\nCue 1 1\n   Text Entrée Public\nEndData\n"
    )
    decoded_cp1252 = decode_file_bytes(cp1252_text.encode("cp1252"))
    assert "Full à 1%" in decoded_cp1252
    assert "Préchauffe à 5%" in decoded_cp1252
    assert "Entrée Public" in decoded_cp1252
    assert "ŕ" not in decoded_cp1252

    utf8_bytes = "Ident 3:0\n$$UText Top → Musique à vue\nEndData\n".encode("utf-8")
    assert "Top → Musique à vue" in decode_file_bytes(utf8_bytes)

    # 2. $$ChanMove 8/16-bit + blackouts + $$Block + tracked effect continuity
    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$Personality 100
   $$Manuf Generic
   $$Model Spot_Test
   $$Footprint 3
   $$PersChan 1 1 1 0 0
   $$PersChan 2 2 2 3 32768
$Patch 1 100 1 1 1
$Patch 21 51365 10 1 1
$Effect 7
   Text Dim Sin
   $$Type 1 ! Linear
   $$Scale 50
$CueList 1
Cue 1 1
   $$ChanMove 1@Hffff 21@Hff
   Chan 1@Hff 21@Hff
   $$Param 1 1@255
   $$EffectChan 7 21 1
Cue 2 1
   $$ChanMove 1@H0000 21@H33
   Chan 21@H33
Cue 3 1
   $$ChanMove 21@H00
   Chan
Cue 4 1
   $$Block
   $$ChanMove 1@H8000
   Chan 1@H80 21@H00
   $$EffectChan 0 21 1
EndData
"""
    assert isinstance(tmp_path, pathlib.Path)
    asc_file = tmp_path / "eos_tracking.asc"
    asc_file.write_bytes(asc_content.encode("cp1252"))

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    dev1 = lightshow.patch.get_device(1)
    assert dev1 is not None and dev1.curve_id == 0
    assert lightshow.main_playback.tracking_mode is True

    # Step 1 (Cue 1): moving head 1 @100%, dimmer 21 @100%, Effect 7 active
    res1 = TrackingEngine.resolve_step_state(
        lightshow.main_playback, 1, tracking_mode=True, patch=lightshow.patch
    )
    assert res1.device_values[1]["intensity"] == pytest.approx(1.0)
    assert res1.channels[20] == pytest.approx(1.0)
    assert 21 in res1.effect_refs and res1.effect_refs[21]["effect"] == 7.0

    # Step 2 (Cue 2): ch 1 blacks out via $$ChanMove 1@H0000 even without $$Param 1@0
    # and Effect 7 continues tracking on dimmer 21 (moved to 0x33/255 via $$ChanMove)
    res2 = TrackingEngine.resolve_step_state(
        lightshow.main_playback, 2, tracking_mode=True, patch=lightshow.patch
    )
    assert res2.device_values[1]["intensity"] == pytest.approx(0.0)
    assert res2.channels[20] == pytest.approx(0x33 / 255.0)
    assert 21 in res2.effect_refs and res2.effect_refs[21]["effect"] == 7.0

    # Step 3 (Cue 3): blackout cue with ONLY $$ChanMove 21@H00 and empty Chan line
    res3 = TrackingEngine.resolve_step_state(
        lightshow.main_playback, 3, tracking_mode=True, patch=lightshow.patch
    )
    assert res3.channels[20] == pytest.approx(0.0)
    assert res3.device_values[1]["intensity"] == pytest.approx(0.0)
    assert 21 in res3.effect_refs

    # Step 4 (Cue 4): $$Block keeps explicit 50% (0x8000/65535) and stops Effect 7
    res4 = TrackingEngine.resolve_step_state(
        lightshow.main_playback, 4, tracking_mode=True, patch=lightshow.patch
    )
    assert res4.device_values[1]["intensity"] == pytest.approx(0x8000 / 65535.0)
    assert res4.channels[20] == pytest.approx(0.0)
    assert res4.effect_refs == {}


def test_import_eos_parts_patch_options_labels_stepped_and_mixed_subs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify Cue Part timing, $Patch options/labels, SteppedCurve, and Subs."""
    import logging

    from olc.devices.device import ChannelType
    from olc.show.curve import InterpolateCurve, SteppedCurve
    from olc.show.fader import FaderEffect, FaderType
    from olc.show.palette import PaletteCategory

    asc_content = """Ident 3:0
Manufacturer ETC
Console Eos
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 3 2 Tilt
$Personality 100
   $$Manuf TestBrand
   $$Model Spot_PT
   $$Footprint 5
   $$PersChan 2 2 1 2 32768
   $$PersSlot 0 65535 32768 -270.0 270.0 D
   $$PersChan 3 2 3 4 32768
   $$PersSlot 0 65535 32768 -135.0 135.0 D
   $$PersChan 1 1 5 0 0
$Personality 40
   $$Manuf Generic
   $$Model Dimmer
   $$Footprint 1
   $$PersChan 1 1 1 0 0
$Patch 21 40 50 0 1
   Text Front PAR
$Patch 1 100 1 0 1
   Text Spot FlipP
   $$Options P
$Patch 2 100 10 0 1
   Text Spot FlipT
   $$Options T
$Patch 3 100 20 0 1
   Text Spot SwapPT
   $$Options S
$Curve 905
   Text Step Hold
   $$Stepped
   $$CurveData 0 0 10 0 11 255 255 255
$Curve 910
   Text Inverse Fade
   $$Interpolated
   $$CurveData 0 255 255 0
$Effect 10
   Text Dimmer FX
   $$Type 1
   $$ParamList 1
$CueList 1
Cue 1 1
   Part 1
   Text Main Cue
   Up 5
   Down 4
   $$TimeColor 6
   Chan 21@Hff
   Part 2
   Text Part Two
   Up 2 1
   Down 3 0.5
   $$TimeColor 9
   Chan 1@H80 2@H00
Sub 20 1
   Text Mixed FX
   Chan 21@Hff
   $$EffectChan 10 21 1
Sub 50 1
   Text Spare Look
   Chan 21@H80
Sub 60 1
   Text Spare FX
   $$EffectChan 10 21 1
$FaderDef 1
   $$Target S 20
$FaderDef 300
   $$Target S 50
$FaderDef 1300
   $$Target S 50
EndData
"""
    with caplog.at_level(logging.DEBUG, logger="olc.files.ascii.parser"):
        imported = _parse_asc(monkeypatch, tmp_path, asc_content)
    show = imported.lightshow

    assert "Ignoring Eos $FaderDef 1300" in caplog.text
    assert show.fader_bank.max_fader_page == 30
    assert show.fader_bank.get_fader_type(30, 10) == FaderType.PRESET

    # Patch labels and $$Options P / T / S
    dev21 = show.patch.get_device(21)
    assert dev21 is not None and dev21.label == "Front PAR"

    dev1 = show.patch.get_device(1)
    assert dev1 is not None and dev1.label == "Spot FlipP"
    pan1 = dev1.get_channel(ChannelType.PAN)
    assert pan1 is not None
    assert pan1.physical_min == pytest.approx(270.0)
    assert pan1.physical_max == pytest.approx(-270.0)

    dev2 = show.patch.get_device(2)
    assert dev2 is not None and dev2.label == "Spot FlipT"
    tilt2 = dev2.get_channel(ChannelType.TILT)
    assert tilt2 is not None
    assert tilt2.physical_min == pytest.approx(135.0)
    assert tilt2.physical_max == pytest.approx(-135.0)

    dev3 = show.patch.get_device(3)
    assert dev3 is not None and dev3.label == "Spot SwapPT"
    pan3_chs = dev3.get_channels(ChannelType.PAN)
    tilt3_chs = dev3.get_channels(ChannelType.TILT)
    pan3_coarse = next(c for c in pan3_chs if not c.fine)
    pan3_fine = next(c for c in pan3_chs if c.fine)
    tilt3_coarse = next(c for c in tilt3_chs if not c.fine)
    tilt3_fine = next(c for c in tilt3_chs if c.fine)
    assert (pan3_coarse.address, pan3_fine.address) == (22, 23)
    assert (tilt3_coarse.address, tilt3_fine.address) == (20, 21)

    # SteppedCurve and custom endpoints
    c905 = show.curves.get_curve(905)
    assert isinstance(c905, SteppedCurve)
    assert c905.get_level(0) == 0
    assert c905.get_level(10) == 0
    assert c905.get_level(11) == 255
    assert c905.get_level(255) == 255

    c910 = show.curves.get_curve(910)
    assert isinstance(c910, InterpolateCurve)
    assert c910.get_level(0) == 255
    assert c910.get_level(255) == 0

    # Cue Part 1 / Part 2 preservation & channel_time
    step1 = next(
        s for s in show.main_playback.steps if s.cue is not None and s.cue.number == 1.0
    )
    assert step1.text == "Main Cue"
    assert step1.time_in == pytest.approx(5.0)
    assert step1.time_out == pytest.approx(4.0)
    assert step1.time_color == pytest.approx(6.0)
    assert 21 not in step1.channel_time
    assert step1.channel_time[1].delay == pytest.approx(1.0)
    assert step1.channel_time[1].time == pytest.approx(2.0)
    assert step1.channel_time[2].delay == pytest.approx(0.5)
    assert step1.channel_time[2].time == pytest.approx(3.0)

    # Mixed effect fader + base_channels proportional scaling + clearing
    assert show.fader_bank.get_fader_type(1, 1) == FaderType.EFFECT
    fader = show.fader_bank.faders[1][1]
    assert isinstance(fader, FaderEffect)
    assert fader.text == "Mixed FX"
    assert fader.base_channels == {21: pytest.approx(1.0)}
    fader.set_level(0.5)
    assert fader.dmx[20] == pytest.approx(0.5)
    fader.set_base_channels({})
    assert fader.dmx[20] == pytest.approx(0.0)

    # Unmounted Subs: static Sub 50 promoted to Preset 50; pure-effect Sub 60 skipped
    preset50 = show.palettes.get(PaletteCategory.PRESET, 50.0)
    assert preset50 is not None
    assert preset50.text == "Spare Look"
    assert preset50.channels[21] == pytest.approx(128 / 255.0)
    assert show.palettes.get(PaletteCategory.PRESET, 60.0) is None


def test_import_eos_6_3_assert_intblock_envelopes_gm_exempt_and_home_preset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """Verify 6.3 metadata, assert/intblock, envelopes, GM-exempt, and Execute S."""
    import pathlib

    from olc.core.app import CoreApplication
    from olc.files.ascii.writer import AsciiWriter
    from olc.show.effect import EffectEnvelopeMode
    from olc.show.fader import FaderPreset
    from olc.show.sequence import ThreadGo

    # 1. File without $$AutoMark -> mib_enabled is False
    assert isinstance(tmp_path, pathlib.Path)
    no_mark_asc = """Ident 3:0
Manufacturer ETC
Console Eos
$CueList 1
Cue 1 1
   Chan 1@Hff
EndData
"""
    show_no_mark = _parse_asc(monkeypatch, tmp_path, no_mark_asc).lightshow
    assert show_no_mark.main_playback.mib_enabled is False

    # 2. Full synthetic Section 6.3 show loaded into CoreApplication
    full_asc = """Ident 3:0
Manufacturer ETC
Console Eos
$$Title My  Live  Show
$$AutoMark
$$HomePreset 999
$ParamType 1 1 Intens
$ParamType 2 2 Pan
$ParamType 3 2 Tilt
$Personality 100
   $$Manuf TestBrand
   $$Model Spot_PT
   $$Footprint 5
   $$PersChan 2 2 1 2 32768
   $$PersSlot 0 65535 32768 -270.0 270.0 D
   $$PersChan 3 2 3 4 32768
   $$PersSlot 0 65535 32768 -135.0 135.0 D
   $$PersChan 1 1 5 0 0
$Personality 40
   $$Manuf Generic
   $$Model Dimmer
   $$Footprint 1
   $$PersChan 1 1 1 0 0
$Patch 1 100 1 0 1
$Patch 21 40 21 0 1
$Patch 22 40 22 0 1
$Effect 10
   Text Pulse FX
   $$Type 1
   $$ParamList 1
   $$Entry 0
   $$Exit 2
   $$Cascade
   $$Trail 40
$CueList 1
Cue 1 1
   Up 2
   $$ChanMove 1@Hff
   $$Param 1 1@65535 2@49152 3@32768
Cue 2 1
   $$IntBlock
   $$Assert
   $$CueNotes Hold spotlight
   $$Action Execute S 10
   Chan 1@H00
Group 999
   Text Home Look
   $$Param 1 2@40000 3@20000
Sub 10 1
   Text Spare Move
   Chan 25@H80
   $$Param 1 3@45000
Sub 900 1
   Text Gradin
   $$Exclude 9 ! Record, GM
   Chan 21@Hff
Sub 5 1
   Text Front Normal
   $$IntensityMaster
   Chan 22@Hff
$FaderDef 1
   $$Target S 900
$FaderDef 2
   $$Target S 5
EndData
"""
    settings = MagicMock()
    app = CoreApplication(settings)
    from olc.core.dmx_backend import DMXBackend

    app.backend = DMXBackend(app.lightshow)

    asc_path = tmp_path / "show_6_3.asc"
    asc_path.write_text(full_asc, encoding="utf-8")
    imported = ImportFile(
        app.lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    ls = app.lightshow
    assert ls.title == "My  Live  Show"
    assert ls.home_preset == pytest.approx(999.0)
    assert ls.main_playback.mib_enabled is True

    # Effect envelopes + trail + AsciiWriter round-trip
    fx10 = ls.effects.get(10.0)
    assert fx10 is not None
    assert fx10.entry_mode == EffectEnvelopeMode.IMMEDIATE
    assert fx10.exit_mode == EffectEnvelopeMode.FADE_BY_RATE
    assert fx10.cascade is True
    assert fx10.layers[0].duty_cycle == pytest.approx(0.4)

    export_path = tmp_path / "export_6_3.asc"
    AsciiWriter(export_path, ls).write()
    exported_txt = export_path.read_text(encoding="utf-8")
    assert "$$ENTRY 0" in exported_txt
    assert "$$EXIT 2" in exported_txt
    assert "$$CASCADE" in exported_txt

    # Cue flags, notes, Execute S 10 -> ThreadGo._finalize_go()
    step2 = ls.main_playback.steps[2]
    assert step2.cue is not None
    assert step2.cue.is_int_block is True
    assert step2.cue.is_assert is True
    assert step2.cue.notes == "Hold spotlight"
    assert step2.cue.execute_preset == pytest.approx(10.0)

    ls.main_playback.position = 1
    thread_go = ThreadGo(False, ls.main_playback)
    thread_go._finalize_go()
    assert app.backend.dmx.levels["sequence"][24] == pytest.approx(128 / 255.0)
    dev1 = ls.patch.get_device(1)
    assert dev1 is not None
    assert dev1.tilt_degrees < 0.0 or dev1.tilt_degrees > 0.0

    # $$HomePreset 999 applied on device.home & undone cleanly
    tilt_before_home = dev1.tilt_degrees
    app.action_registry.execute("device.home", channels=[1])
    assert dev1.pan_degrees == pytest.approx((40000 / 65535.0) * 540.0 - 270.0, abs=0.5)
    assert dev1.tilt_degrees == pytest.approx(
        (20000 / 65535.0) * 270.0 - 135.0, abs=0.5
    )
    app.history.undo()
    assert dev1.tilt_degrees == pytest.approx(tilt_before_home, abs=0.1)

    # $$Exclude 9 (GM-exempt) keeps house lights at 255 through Main Fader=0 & Blackout
    fader_gm_exempt = ls.fader_bank.faders[1][1]
    fader_normal = ls.fader_bank.faders[1][2]
    assert isinstance(fader_gm_exempt, FaderPreset)
    assert isinstance(fader_normal, FaderPreset)
    assert fader_gm_exempt.exempt_grand_master is True
    assert fader_normal.intensity_master is True

    fader_gm_exempt.set_level(1.0)
    fader_normal.set_level(1.0)
    assert app.backend.dmx.frame[0][20] == 255
    assert app.backend.dmx.frame[0][21] == 255

    app.backend.dmx.main_fader.set_level(0.0)
    app.backend.dmx.set_levels()
    assert app.backend.dmx.frame[0][20] == 255
    assert app.backend.dmx.frame[0][21] == 0

    app.backend.dmx.blackout = True
    app.backend.dmx.set_levels()
    assert app.backend.dmx.frame[0][20] == 255
    assert app.backend.dmx.frame[0][21] == 0


def test_ascii_writer_section_6_3_and_6_4_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """AsciiWriter symmetrically round-trips 6.3/6.4 metadata, faders, and effects."""
    import pathlib

    from olc.files.ascii.writer import AsciiWriter
    from olc.show.cue import Cue
    from olc.show.effect import EffectDefinition, EffectLayer, EffectMode, WaveformType
    from olc.show.fader import FaderPreset, FaderType
    from olc.show.palette import Palette, PaletteCategory
    from olc.show.sequence import Sequence
    from olc.show.step import Step

    assert isinstance(tmp_path, pathlib.Path)
    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    show = LightShow()
    show.title = "Gala  Nocturne"
    show.home_preset = 999.0
    show.main_playback.mib_enabled = False

    c1 = Cue(
        sequence=1,
        number=1.0,
        channels={1: 1.0},
        is_block=True,
        is_int_block=True,
        is_assert=True,
        notes="Line one\nLine two",
        execute_preset=5.0,
    )
    show.main_playback.cues.add(c1)
    show.main_playback.insert_step(1, Step(sequence=1.0, cue=c1, text="Intro"))

    seq2 = Sequence(index=2, text="Side List")
    c2 = Cue(
        sequence=2,
        number=10.0,
        channels={2: 0.5},
        is_int_block=True,
        is_assert=True,
        notes="Side note",
        execute_preset=7.0,
    )
    seq2.cues.add(c2)
    seq2.insert_step(1, Step(sequence=2.0, cue=c2, text="Flash"))
    show.sequences.append(seq2)

    p5 = Palette(category=PaletteCategory.PRESET, number=5.0, text="P5")
    p6 = Palette(category=PaletteCategory.PRESET, number=6.0, text="P6")
    show.palettes.add(p5)
    show.palettes.add(p6)

    show.fader_bank.set_fader(1, 1, FaderType.PRESET, 5.0)
    show.fader_bank.set_fader(1, 2, FaderType.PRESET, 6.0)
    show.fader_bank.set_fader_fixed(1, 1, True)
    f1 = show.fader_bank.faders[1][1]
    f2 = show.fader_bank.faders[1][2]
    assert isinstance(f1, FaderPreset) and isinstance(f2, FaderPreset)
    f1.exempt_grand_master = True
    f2.intensity_master = True

    show.effects.add(
        EffectDefinition(
            number=11.0,
            label="Long Sine",
            cycle_time=25.0,
            layers=[
                EffectLayer(
                    parameter="intensity",
                    waveform=WaveformType.SINE,
                    mode=EffectMode.RELATIVE,
                    size=30.0,
                    duty_cycle=0.75,
                )
            ],
        )
    )
    show.effects.add(
        EffectDefinition(
            number=6.0,
            label="Zoom Dip",
            cycle_time=10.0,
            layers=[
                EffectLayer(
                    parameter="zoom",
                    waveform=WaveformType.PULSE,
                    mode=EffectMode.RELATIVE,
                    size=-5.0,
                    duty_cycle=0.5,
                )
            ],
        )
    )

    out_path = tmp_path / "roundtrip_6_4.asc"
    AsciiWriter(out_path, show).write()

    reloaded = LightShow()
    imp = ImportFile(reloaded, Gio.File.new_for_path(str(out_path)), FileType.ASCII)
    imp.parse_sync(auto_import=True)

    assert reloaded.title == "Gala  Nocturne"
    assert reloaded.home_preset == pytest.approx(999.0)
    assert reloaded.main_playback.mib_enabled is False

    rc1 = reloaded.main_playback.steps[1].cue
    assert rc1 is not None
    assert rc1.is_block is True
    assert rc1.is_int_block is True
    assert rc1.is_assert is True
    assert rc1.notes == "Line one\nLine two"
    assert rc1.execute_preset == pytest.approx(5.0)

    rseq2 = next(s for s in reloaded.sequences if s.index == 2)
    assert rseq2.mib_enabled is False
    rc2 = rseq2.steps[1].cue
    assert rc2 is not None
    assert rc2.is_int_block is True
    assert rc2.is_assert is True
    assert rc2.notes == "Side note"
    assert rc2.execute_preset == pytest.approx(7.0)

    rf1 = reloaded.fader_bank.faders[1][1]
    rf2 = reloaded.fader_bank.faders[1][2]
    assert isinstance(rf1, FaderPreset) and rf1.exempt_grand_master is True
    assert reloaded.fader_bank.is_fader_fixed(1, 1) is True
    assert isinstance(rf2, FaderPreset) and rf2.intensity_master is True
    assert reloaded.fader_bank.is_fader_fixed(1, 2) is False

    rfx11 = reloaded.effects.get(11.0)
    assert rfx11 is not None
    assert rfx11.cycle_time == pytest.approx(25.0)
    assert rfx11.layers[0].duty_cycle == pytest.approx(0.75)

    rfx6 = reloaded.effects.get(6.0)
    assert rfx6 is not None
    assert rfx6.cycle_time == pytest.approx(10.0)
    assert rfx6.layers[0].mode == EffectMode.RELATIVE
    assert rfx6.layers[0].waveform == WaveformType.PULSE
    assert rfx6.layers[0].size == pytest.approx(-5.0)


def test_eos_show_dmx_fidelity_and_bkgrd_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """Verify 0 DMX mismatch across eos_show.asc and Bkgrd ceiling on Abs effects."""
    import pathlib
    import typing
    from types import SimpleNamespace

    import numpy as np

    from olc.core.app import CoreApplication
    from olc.core.effects_engine import EffectsEngine
    from olc.devices.channel import ChannelType
    from olc.files.ascii.parser import AsciiParser
    from olc.files.ascii.writer import AsciiWriter
    from olc.show.palette import PaletteCategory

    asc_path = DATA_DIR / "eos_show.asc"
    assert isinstance(tmp_path, pathlib.Path)

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    ls = LightShow()
    imported = ImportFile(ls, Gio.File.new_for_path(str(asc_path)), FileType.ASCII)
    imported.parse_sync(auto_import=True)
    parser = imported.parser
    assert isinstance(parser, AsciiParser)

    def _u16(dev: object, label: str) -> int:
        chs = getattr(dev, "channels", [])
        coarse = next(
            c for c in chs if not c.fine and not c.ultra_fine and c.label == label
        )
        fine = next((c for c in chs if c.fine and c.label == f"{label}_fine"), None)
        return ((coarse.value << 8) | fine.value) if fine is not None else coarse.value

    # 1. Gobos & dual Gobo wheels
    dev1 = ls.patch.get_device(1)
    dev4 = ls.patch.get_device(4)
    dev41 = ls.patch.get_device(41)
    assert dev1 is not None and dev4 is not None and dev41 is not None

    bp22 = ls.palettes.get(PaletteCategory.BEAM, 22.0)
    bp123 = ls.palettes.get(PaletteCategory.BEAM, 123.0)
    pr110 = ls.palettes.get(PaletteCategory.PRESET, 110.0)
    assert bp22 is not None and bp123 is not None and pr110 is not None

    dev4.apply_device_values(bp22.device_values[4])
    assert _u16(dev4, "Gobo_Select") == 15

    dev1.apply_device_values(bp123.device_values[1])
    assert _u16(dev1, "Gobo_Select") == 45

    dev1.apply_device_values(pr110.device_values[1])
    assert _u16(dev1, "Gobo_Select") == 0
    assert _u16(dev1, "Gobo_Select_2") == 27

    # 2. Dual Frost (Diffusion vs Medium_Diffusion)
    bp2 = ls.palettes.get(PaletteCategory.BEAM, 2.0)
    bp3 = ls.palettes.get(PaletteCategory.BEAM, 3.0)
    assert bp2 is not None and bp3 is not None

    dev1.apply_device_values(bp2.device_values[1])
    assert _u16(dev1, "Diffusion") == 255
    assert _u16(dev1, "Medium_Diffusion") == 0

    dev1.apply_device_values(bp3.device_values[1])
    assert _u16(dev1, "Diffusion") == 0
    assert _u16(dev1, "Medium_Diffusion") == 255

    # 3. 16-bit RGBW emitter fidelity on ColorPalette 1 (LED F1 ch 41)
    cp1 = ls.palettes.get(PaletteCategory.COLOR, 1.0)
    assert cp1 is not None
    assert cp1.device_values[41]["color"] == "#61fcff"
    dev41.apply_device_values(cp1.device_values[41])
    assert abs(_u16(dev41, "Red") - 24854) <= 2
    assert abs(_u16(dev41, "Green") - 64827) <= 2
    assert abs(_u16(dev41, "Blue") - 65535) <= 2
    assert abs(_u16(dev41, "White") - 65535) <= 2

    # 4. Global byte-for-byte guard across ALL palettes, presets, and cues
    mismatches: list[tuple[str, int, str, int, int]] = []
    checked_params: set[str] = set()

    def _audit_container(
        label: str,
        raw_by_ch: dict[int, dict[int, float]],
        olc_dev_vals: dict[int, dict[str, object]],
    ) -> None:
        for ch, pmap in raw_by_ch.items():
            dev = ls.patch.get_device(ch)
            if dev is None:
                continue
            pers_id = parser.channel_personality.get(ch)
            pers = parser.personalities.get(pers_id) if pers_id is not None else None
            if pers is None:
                continue
            pers_by_pid = {int(pc["param_id"]): pc for pc in pers["channels"]}
            saved = [c.value for c in dev.channels]
            dev.apply_device_values(olc_dev_vals.get(ch, {}))
            for pid, raw_val in pmap.items():
                pc = pers_by_pid.get(pid)
                if pc is None:
                    continue
                pname = parser.param_types.get(pid, f"pid_{pid}")
                checked_params.add(pname)
                coarse = next(
                    c
                    for c in dev.channels
                    if not c.fine and not c.ultra_fine and c.label == pname
                )
                fine = next(
                    (c for c in dev.channels if c.fine and c.label == f"{pname}_fine"),
                    None,
                )
                slots = pc.get("slot_list", [])
                slot_inverted = len(slots) == 1 and int(slots[0]["dmx_min"]) > int(
                    slots[0]["dmx_max"]
                )
                is_flipped = (
                    coarse.channel_type != ChannelType.GENERIC
                    and coarse.physical_max < coarse.physical_min
                    and not slot_inverted
                )
                if int(pc.get("bytes", 1)) == 2 and fine is not None:
                    actual = (coarse.value << 8) | fine.value
                    expected = (
                        65535 - int(round(raw_val))
                        if is_flipped
                        else int(round(raw_val))
                    )
                    tol = 300
                else:
                    actual = coarse.value
                    exp_8 = (
                        int(round(raw_val)) >> 8
                        if raw_val > 255
                        else int(round(raw_val))
                    )
                    expected = 255 - exp_8 if is_flipped else exp_8
                    tol = 2
                if abs(actual - expected) > tol:
                    mismatches.append((label, ch, pname, expected, actual))
            for c, val_saved in zip(dev.channels, saved, strict=False):
                c.value = val_saved

    for (cat_val, num), raw_by_ch in parser._palette_raw_params.items():
        pal = ls.palettes.get(PaletteCategory(cat_val), num)
        if pal is not None:
            _audit_container(f"{cat_val} {num:g}", raw_by_ch, pal.device_values)

    for (seq_num, cue_num), raw_by_ch in parser._cue_raw_params.items():
        seq = (
            ls.main_playback
            if seq_num == 1
            else next((s for s in ls.sequences if s.index == seq_num), None)
        )
        if seq is None:
            continue
        st = next((s for s in seq.steps if s.cue and s.cue.number == cue_num), None)
        if st is not None and st.cue is not None:
            _audit_container(
                f"Seq{seq_num} Cue{cue_num:g}", raw_by_ch, st.cue.device_values
            )

    assert len(checked_params) >= 40
    assert mismatches == []

    # 5. Absolute 0 -> Bkgrd effects stay bounded by base cue intensity + round-trip
    fx4 = ls.effects.get(4.0)
    assert fx4 is not None
    assert fx4.layers[0].low_value == 0.0
    assert fx4.layers[0].high_value == "bkgrd"

    app_stub = typing.cast(
        "CoreApplication",
        SimpleNamespace(lightshow=ls, backend=None, emit=lambda *_a, **_k: None),
    )
    base = np.zeros(512, dtype=np.float64)

    for eff_num, times in (
        (4.0, [0.0, 1.25, 2.5, 3.75, 5.0, 7.5]),
        (3.0, [0.0, 0.005, 0.01, 0.015, 0.025]),
    ):
        for base_lvl in (0.0, 0.10, 0.50):
            base[20] = base_lvl
            eng = EffectsEngine(app_stub)
            eng.start_effect(eff_num, [21], now=0.0)
            samples = [
                float(eng.apply_intensity_modulation(base, now=t)[20]) for t in times
            ]
            assert max(samples) == pytest.approx(base_lvl, abs=1e-4)
            assert min(samples) == pytest.approx(0.0, abs=1e-4)

    rt_path = tmp_path / "bkgrd_roundtrip.asc"
    AsciiWriter(rt_path, ls).write()
    ls_rt = LightShow()
    ImportFile(ls_rt, Gio.File.new_for_path(str(rt_path)), FileType.ASCII).parse_sync(
        auto_import=True
    )
    rt_fx4 = ls_rt.effects.get(4.0)
    assert rt_fx4 is not None
    assert rt_fx4.layers[0].low_value == pytest.approx(0.0)
    assert rt_fx4.layers[0].high_value == "bkgrd"


def test_import_eos_nocturne_page3_and_page4_three_fader_effect_controllers() -> None:
    """Verify Eos $$Control 3-fader effect wings (Master, Rate, Size) import & run."""
    from olc.core.app import CoreApplication
    from olc.show.fader import FaderEffect

    asc_path = str(
        Path(__file__).resolve().parent.parent
        / "doc"
        / "Conduites Eos"
        / "00  Base  Nocturne.asc"
    )
    app = CoreApplication(MagicMock())
    ImportFile(
        app.lightshow, Gio.File.new_for_path(asc_path), FileType.ASCII
    ).parse_sync(auto_import=True)

    fb = app.lightshow.fader_bank
    # Page 3: faders 1..3 -> Sub 21 (ch 15,16,11,12,13,14)
    f_master = fb.faders[3][1]
    f_rate = fb.faders[3][2]
    f_size = fb.faders[3][3]
    assert isinstance(f_master, FaderEffect)
    assert isinstance(f_rate, FaderEffect)
    assert isinstance(f_size, FaderEffect)

    assert f_master.modifier_only is False
    assert f_master.level == pytest.approx(0.0)
    assert f_master.effect_channels == [15, 16, 11, 12, 13, 14]

    assert f_rate.modifier_only is True
    assert f_rate.control_mode == "rate"
    assert f_rate.level == pytest.approx(0.5)
    assert f_rate.max_scale == pytest.approx(10.0)

    assert f_size.modifier_only is True
    assert f_size.control_mode == "size"
    assert f_size.level == pytest.approx(0.5)
    assert f_size.max_scale == pytest.approx(10.0)

    # Page 3 also has Sub 20 (4..6) and Sub 22 (7..9); Page 4 has Sub 24/25/23
    assert isinstance(fb.faders[3][4], FaderEffect)
    assert isinstance(fb.faders[3][5], FaderEffect) and fb.faders[3][5].modifier_only
    assert isinstance(fb.faders[3][7], FaderEffect)
    assert isinstance(fb.faders[4][1], FaderEffect)
    assert isinstance(fb.faders[4][2], FaderEffect) and fb.faders[4][2].modifier_only

    # Moving Rate modifier alone must NOT start Effect 7
    f_rate.set_level(0.75)
    assert app.effects_engine.get_active_instances() == []
    f_rate.flash_on()
    assert f_rate.level == pytest.approx(0.5)

    # Raising Master starts Effect 7 on [15..14] at nominal 1.0x rate and 0.8 size
    f_master.set_level(0.8)
    active = app.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].channels == [15, 16, 11, 12, 13, 14]
    assert active[0].rate_scale == pytest.approx(1.0)
    assert active[0].size_scale == pytest.approx(0.8)

    # Rate modifier varies bidirectionally (< 0.5 slows, > 0.5 speeds up)
    f_rate.set_level(0.25)
    assert active[0].rate_scale == pytest.approx(0.5)
    f_rate.set_level(0.75)
    assert active[0].rate_scale == pytest.approx(5.5)
    f_rate.flash_on()
    assert active[0].rate_scale == pytest.approx(1.0)

    # Starting Sub 20 (fader 4) runs independently; stopping Sub 21 leaves Sub 20 active
    f_master_2 = fb.faders[3][4]
    assert isinstance(f_master_2, FaderEffect)
    f_master_2.set_level(1.0)
    assert len(app.effects_engine.get_active_instances()) == 2
    f_master.set_level(0.0)
    remaining = app.effects_engine.get_active_instances()
    assert len(remaining) == 1
    assert remaining[0].channels == [21, 22, 23, 24, 25, 26]


def test_import_eos_fader_exclusion_solo_inhibitive_and_roundtrip(
    tmp_path: object,
) -> None:
    """Verify Eos $$Exclude/$$Exclusive/$$SoloMode/$$Locked/$$Master 2 & round-trip."""
    from pathlib import Path

    from olc.files.ascii.writer import AsciiWriter

    assert isinstance(tmp_path, Path)

    asc_path = str(
        Path(__file__).resolve().parent.parent
        / "doc"
        / "Conduites Eos"
        / "00  Base  Nocturne.asc"
    )
    ls = LightShow()
    ImportFile(ls, Gio.File.new_for_path(asc_path), FileType.ASCII).parse_sync(
        auto_import=True
    )

    # Fader 1 -> Sub 6 ($$Exclude 1, $$IntensityMaster, $$Exclusive)
    f1 = ls.fader_bank.faders[1][1]
    assert f1.exclude_record is True
    assert f1.swop_protect is True
    assert getattr(f1, "intensity_master", False) is True
    assert f1.exempt_grand_master is False

    # Fader 6 -> Sub 900 ($$Exclude 9, $$Exclusive)
    f6 = ls.fader_bank.faders[1][6]
    assert f6.exempt_grand_master is True
    assert f6.exclude_record is True
    assert f6.swop_protect is True

    # Synthetic Eos ASCII with SoloMode, Locked, Inhibitive ($$Master 2) + round-trip
    syn_path = tmp_path / "fader_flags_eos.asc"
    syn_path.write_text(
        "\n".join(
            [
                "IDENT 3:0",
                "MANUFACTURER ETC",
                "CONSOLE Eos",
                "PATCH 1 1 1 100",
                "PATCH 1 2 2 100",
                "SUB 1 1",
                "TEXT SoloFader",
                "$$SOLOMODE",
                "$$EXCLUDE 1",
                "CHAN 1@HFF",
                "SUB 2 1",
                "TEXT InhibFader",
                "$$MASTER 2",
                "$$LOCKED",
                "CHAN 2@HFF",
                "$FaderDef 1",
                "$$TARGET S 1",
                "$FaderDef 2",
                "$$TARGET S 2",
                "ENDDATA",
            ]
        ),
        encoding="ascii",
    )
    ls2 = LightShow()
    ImportFile(ls2, Gio.File.new_for_path(str(syn_path)), FileType.ASCII).parse_sync(
        auto_import=True
    )
    sf1 = ls2.fader_bank.faders[1][1]
    assert sf1.solo_mode is True
    assert sf1.exclude_record is True
    sf2 = ls2.fader_bank.faders[1][2]
    assert sf2.inhibitive is True
    assert sf2.locked is True

    rt_path = tmp_path / "fader_flags_rt.asc"
    AsciiWriter(rt_path, ls2).write()
    ls3 = LightShow()
    ImportFile(ls3, Gio.File.new_for_path(str(rt_path)), FileType.ASCII).parse_sync(
        auto_import=True
    )
    rt1 = ls3.fader_bank.faders[1][1]
    assert rt1.solo_mode is True
    assert rt1.exclude_record is True
    rt2 = ls3.fader_bank.faders[1][2]
    assert rt2.inhibitive is True
    assert rt2.locked is True


def test_sequence_1_default_empty_and_ascii_label_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sequence 1 must default to empty text and preserve labels on ASCII I/O."""
    from olc.core.app import CoreApplication
    from olc.files.ascii.writer import AsciiWriter

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    app = CoreApplication(MagicMock())
    assert app.lightshow.main_playback.text == ""
    app.lightshow.main_playback.text = "Temp"
    app.action_registry.execute("show.new")
    assert app.lightshow.main_playback.text == ""

    # 1. Eos $CueList 1 with Text Strip -> main_playback.text == "Strip"
    asc_named = tmp_path / "eos_named.asc"
    asc_named.write_text(
        "\n".join(
            [
                "IDENT 3:0",
                "MANUFACTURER ETC",
                "CONSOLE Eos",
                "$CueList 1",
                "   Text Strip",
                "Cue 1 1",
                "   Up 2",
                "   Chan 1 @ 50",
                "ENDDATA",
            ]
        ),
        encoding="ascii",
    )
    ls_named = LightShow()
    ImportFile(
        ls_named, Gio.File.new_for_path(str(asc_named)), FileType.ASCII
    ).parse_sync(auto_import=True)
    assert ls_named.main_playback.text == "Strip"

    # 2. Round-trip via AsciiWriter preserves "Strip"
    rt_path = tmp_path / "eos_named_rt.asc"
    AsciiWriter(rt_path, ls_named).write()
    rt_text = rt_path.read_text(encoding="utf-8")
    assert "TEXT Strip\n" in rt_text
    assert "$$TEXT Strip\n" in rt_text

    ls_rt = LightShow()
    ImportFile(ls_rt, Gio.File.new_for_path(str(rt_path)), FileType.ASCII).parse_sync(
        auto_import=True
    )
    assert ls_rt.main_playback.text == "Strip"

    # 3. Eos $CueList 1 without Text -> main_playback.text == ""
    asc_unnamed = tmp_path / "eos_unnamed.asc"
    asc_unnamed.write_text(
        "\n".join(
            [
                "IDENT 3:0",
                "MANUFACTURER ETC",
                "CONSOLE Eos",
                "$CueList 1",
                "Cue 1 1",
                "   Up 2",
                "   Chan 1 @ 50",
                "ENDDATA",
            ]
        ),
        encoding="ascii",
    )
    ls_unnamed = LightShow()
    ImportFile(
        ls_unnamed, Gio.File.new_for_path(str(asc_unnamed)), FileType.ASCII
    ).parse_sync(auto_import=True)
    assert ls_unnamed.main_playback.text == ""

    rt_empty = tmp_path / "eos_unnamed_rt.asc"
    AsciiWriter(rt_empty, ls_unnamed).write()
    assert "$SEQUENCE 1 0\n\n" in rt_empty.read_text(encoding="utf-8")


def test_eos_ascii_proportion_and_preheat_curves(tmp_path: object) -> None:
    """Eos $$Proportion and $$Preheat convert into deduplicated transfer curves."""
    import pathlib

    from olc.show.curve import SegmentsCurve

    assert isinstance(tmp_path, pathlib.Path)

    asc = tmp_path / "eos_prop_preheat.asc"
    asc.write_text(
        "\n".join(
            [
                "IDENT 3:0",
                "MANUFACTURER ETC",
                "CONSOLE Eos",
                "$Patch 1 1 1 100",
                "   $$Proportion 80",
                "   $$Preheat 10",
                "$Patch 2 1 2 100",
                "   $$Proportion 80",
                "   $$Preheat 10",
                "ENDDATA",
            ]
        ),
        encoding="ascii",
    )
    show = LightShow()
    ImportFile(show, Gio.File.new_for_path(str(asc)), FileType.ASCII).parse_sync(
        auto_import=True
    )
    d1 = show.patch.get_device(1)
    d2 = show.patch.get_device(2)
    assert d1 is not None and d2 is not None
    assert d1.curve_id >= 1000
    assert d1.curve_id == d2.curve_id
    curve = show.curves.get_curve(d1.curve_id)
    assert isinstance(curve, SegmentsCurve)
    assert curve.evaluate_normalized(0.0) == pytest.approx(0.10, abs=0.02)
    assert curve.evaluate_normalized(0.5) == pytest.approx(0.40, abs=0.02)
    assert curve.evaluate_normalized(1.0) == pytest.approx(0.80, abs=0.02)


def test_ascii_round_trip_cue_link_loop_and_curve(tmp_path: object) -> None:
    """Verify ASCII import/export round-trip for LINK, $$LOOP, and $$CURVE."""
    import pathlib

    from olc.files.ascii.writer import AsciiWriter

    assert isinstance(tmp_path, pathlib.Path)
    asc = tmp_path / "cue_link_curve.asc"
    asc.write_text(
        "\n".join(
            [
                "IDENT 3:0",
                "MANUFACTURER ETC",
                "CONSOLE Eos",
                "$Curve 7",
                "   $$CurvePoint 0 0",
                "   $$CurvePoint 50 90",
                "   $$CurvePoint 100 100",
                "$CueList 1",
                "Cue 1 1",
                "   Up 2",
                "   Chan 1 @ 50",
                "Cue 2 1",
                "   Up 3",
                "   Link 1",
                "   $$Loop 4",
                "   $$Curve 7",
                "   Chan 1 @ 0",
                "ENDDATA",
            ]
        ),
        encoding="ascii",
    )
    ls = LightShow()
    ImportFile(ls, Gio.File.new_for_path(str(asc)), FileType.ASCII).parse_sync(
        auto_import=True
    )
    step2 = ls.main_playback.steps[2]
    assert step2.link_cue == pytest.approx(1.0)
    assert step2.loop_count == 4
    assert step2.curve_id == 7

    rt_path = tmp_path / "cue_link_curve_rt.asc"
    AsciiWriter(rt_path, ls).write()
    rt_text = rt_path.read_text(encoding="utf-8")
    assert "LINK 1\n" in rt_text
    assert "$$LOOP 4\n" in rt_text
    assert "$$CURVE 7\n" in rt_text


def test_ascii_import_multipart_fixture_and_patch_notes(tmp_path: Path) -> None:
    """Multi-part fixtures merge channels and $$Notes/$$Text1..10 populate dev.notes."""
    from olc.devices.channel import ChannelType
    from olc.files.ascii.writer import AsciiWriter

    asc = tmp_path / "multipart_notes.asc"
    asc.write_text(
        "\n".join(
            [
                "Ident 3:0",
                "Manufacturer ETC",
                "Console Eos",
                "$ParamType 1 1 Intens",
                "$ParamType 2 2 Pan",
                "$Personality 10",
                "   $$Manuf TourBrand",
                "   $$Model SpotDual",
                "   $$Footprint 2",
                "   $$PersChan 1 1 1 0 0 100 0.0 100.0",
                "   $$PersChan 2 2 2 0 32768 100 -270.0 270.0",
                "$Patch 30 10 100 1",
                "   $$Text Dual Spot",
                "   $$Notes Bridge 1",
                "$Patch 30 10 120 1",
                "$Patch 31 0 150 1",
                "   $$Text Dimmer 31",
                "   $$Text1 FOH Left",
                "$Patch 32 0 0 1",
                "   $$Text Spare 32",
                "   $$Notes Rack B",
                "ENDDATA",
            ]
        ),
        encoding="ascii",
    )

    ls = LightShow()
    ImportFile(ls, Gio.File.new_for_path(str(asc)), FileType.ASCII).parse_sync(
        auto_import=True
    )

    d30 = ls.patch.get_device(30)
    assert d30 is not None
    assert d30.label == "Dual Spot"
    assert "Bridge 1" in d30.notes
    int_chs = [c for c in d30.channels if c.channel_type is ChannelType.INTENSITY]
    assert [(c.universe, c.address) for c in int_chs] == [(1, 100), (1, 120)]
    d30.set_intensity(0.5)
    assert all(c.value in (127, 128) for c in int_chs)

    d31 = ls.patch.get_device(31)
    assert d31 is not None
    assert d31.label == "Dimmer 31"
    assert d31.notes == "FOH Left"

    d32 = ls.patch.get_device(32)
    assert d32 is not None
    assert d32.label == "Spare 32"
    assert d32.notes == "Rack B"
    assert d32.channels == []

    rt_path = tmp_path / "multipart_notes_rt.asc"
    AsciiWriter(rt_path, ls).write()
    assert "   $$Notes Rack B\n" in rt_path.read_text(encoding="utf-8")
