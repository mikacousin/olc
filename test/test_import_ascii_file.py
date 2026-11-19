from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gtk", "3.0")
from charset_normalizer import from_bytes  # noqa: E402
from gi.repository import Gio  # noqa: E402

from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402

FILE_PATH = "test/sample.asc"
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
    asc_file = tmp_path / "eos_lot3.asc"
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
