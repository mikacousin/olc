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
