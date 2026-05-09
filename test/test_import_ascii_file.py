import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gio  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.lightshow import LightShow  # noqa: E402

FILE_PATH = "test/sample.asc"
gfile = Gio.File.new_for_path(FILE_PATH)


def test_import(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    mock_app = MagicMock()
    monkeypatch.setattr("olc.patch.App", lambda: mock_app)
    monkeypatch.setattr("olc.files.import_file.App", lambda: mock_app, raising=False)
    monkeypatch.setattr("olc.lightshow.App", lambda: mock_app, raising=False)

    lightshow = LightShow()
    imported = ImportFile(lightshow, gfile, FileType.ASCII)

    # Exécution synchrone du parsing
    _success, data, _etag = gfile.load_contents(None)
    from charset_normalizer import from_bytes

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
        7: 255,
        20: 255,
        31: 255,
    }
    assert imported.data.data["sequences"][2]["label"] == "Chaser 1"
