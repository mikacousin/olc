"""Unit and integration tests for ASCII / EOS show file importation."""

from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gtk", "3.0")
from charset_normalizer import from_bytes  # noqa: E402
from gi.repository import Gio  # noqa: E402

from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402

FILE_PATH = "test/fixtures/sample.asc"
gfile = Gio.File.new_for_path(FILE_PATH)


def test_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test ASCII file importation"""

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(lightshow, gfile, FileType.ASCII)

    # Synchronous parsing execution
    _success, data, _etag = gfile.load_contents(None)

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

    # Secondary sequence imported as Normal (not forced to Chaser)
    assert len(lightshow.chasers) == 1
    assert lightshow.chasers[0].index == 2
    assert lightshow.chasers[0].type_seq == "Normal"


def test_import_eos_base_nocturne_cuelists_and_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify doc/00  Base  Nocturne.asc splits 3 CueLists without cue collisions."""
    import pathlib

    asc_path = pathlib.Path("doc/00  Base  Nocturne.asc")
    if not asc_path.exists():
        pytest.skip("doc/00  Base  Nocturne.asc not present")

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=False)

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

    from olc.devices.channel import ChannelType, FixtureType

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


def test_import_eos_base_nocturne_devices_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify doc/00  Base  Nocturne.asc imports all moving/LED devices and $$Param."""
    import pathlib

    asc_path = pathlib.Path("doc/00  Base  Nocturne.asc")
    if not asc_path.exists():
        pytest.skip("doc/00  Base  Nocturne.asc not present")

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

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
$Patch 1 51365 1 901 1
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

    # Curve 901 imported as InterpolateCurve and linked to channel 1
    curve_901 = lightshow.curves.get_curve(901)
    assert isinstance(curve_901, InterpolateCurve)
    assert curve_901.name == "IES Square"
    dev1 = lightshow.patch.get_device(1)
    assert dev1 is not None and dev1.curve_id == 901

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

    # Unused Sub 99 must not pollute groups or palettes
    assert lightshow.groups.get(99.0) is None
    assert lightshow.palettes.get(PaletteCategory.PRESET, 99.0) is None

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


def test_import_eos_base_nocturne_groups_curves_and_faders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify doc/00  Base  Nocturne.asc imports $Group, $Curve, and $FaderDef."""
    import pathlib

    from olc.show.fader import FaderType
    from olc.show.palette import PaletteCategory

    asc_path = pathlib.Path("doc/00  Base  Nocturne.asc")
    if not asc_path.exists():
        pytest.skip("doc/00  Base  Nocturne.asc not present")

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

    # $Curve 901 imported
    c901 = lightshow.curves.get_curve(901)
    assert c901 is not None and c901.name == "IES Square"

    # $FaderDef 1 -> Sub 6 imported as Preset 6 with FaderType.PRESET
    assert lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    preset6 = lightshow.palettes.get(PaletteCategory.PRESET, 6.0)
    assert preset6 is not None
    assert lightshow.fader_bank.faders[1][1].contents is preset6


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
    assert eos_param_id_to_olc_key(57675, ptypes) == "frost"
    assert eos_param_id_to_olc_key(9999, ptypes) is None


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
    cue1 = lightshow.cues.get(1.0, 0)
    cue2 = lightshow.cues.get(2.0, 0)
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


def test_import_eos_base_nocturne_palettes_and_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Base Nocturne imports palettes and resolves Cue/Preset refs."""
    import pathlib

    from olc.show.fader import FaderType
    from olc.show.palette import PaletteCategory

    asc_path = pathlib.Path("doc/00  Base  Nocturne.asc")
    if not asc_path.exists():
        pytest.skip("doc/00  Base  Nocturne.asc not present")

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    # Palette counts
    assert len(lightshow.palettes.list_by_category(PaletteCategory.COLOR)) == 26
    assert len(lightshow.palettes.list_by_category(PaletteCategory.BEAM)) == 64
    assert len(lightshow.palettes.list_by_category(PaletteCategory.FOCUS)) == 8
    assert len(lightshow.groups) == 7
    assert not any(g.index >= 500 for g in lightshow.groups)
    assert lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET

    # CP106 (L106)
    cp106 = lightshow.palettes.get(PaletteCategory.COLOR, 106.0)
    assert cp106 is not None and cp106.text == "L106"
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
    cue99 = lightshow.cues.get(99.0, 0)
    assert cue99 is not None
    assert cue99.device_values[41]["color"] == "#ff0700"
    assert cue99.palette_refs[41]["color"] == ("color", 106.0)

    cue100 = lightshow.cues.get(100.0, 0)
    assert cue100 is not None
    assert cue100.device_values[1]["color"] == "#ff0000"
    assert cue100.palette_refs[1]["color"] == ("color", 106.0)
    assert cue100.palette_refs[1]["pan"] == ("preset", 100.0)

    cue106 = lightshow.cues.get(106.0, 0)
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

    # Mode collision merged under BrandA:DuoSpot, CMY keeps color_profile=None
    duospot = lightshow.fixture_library.get("BrandA", "DuoSpot")
    assert duospot.mode_names() == ["7ch", "4ch"]
    assert duospot.color_profile is None
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


def test_import_eos_base_nocturne_fixture_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Base Nocturne populates fixture_library cleanly (Scenario B)."""
    import pathlib

    from olc.devices.channel import ChannelType

    asc_path = pathlib.Path("doc/00  Base  Nocturne.asc")
    if not asc_path.exists():
        pytest.skip("doc/00  Base  Nocturne.asc not present")

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

    # Moving heads (CMY -> no additive color_profile)
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
    assert ghibli.color_profile is None
    assert (
        lightshow.patch.count_devices_using_definition("Ayrton", "Ghibli_Extended") == 3
    )

    diablo = lightshow.fixture_library.get("Ayrton", "Diablo_S_Extended_Pan_540")
    diablo_mode = diablo.default_mode()
    assert len(diablo_mode.channel_defs) == 33
    assert diablo_mode.footprint() == 56
    assert diablo.color_profile is None
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


def test_import_eos_base_nocturne_slots_units_notes_and_inversions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify doc/00  Base  Nocturne.asc preserves case, slots, units, notes."""
    import itertools
    import pathlib

    asc_path = pathlib.Path("doc/00  Base  Nocturne.asc")
    if not asc_path.exists():
        pytest.skip("doc/00  Base  Nocturne.asc not present")

    mock_app = MagicMock()
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.show.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_path)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

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
