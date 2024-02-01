import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio  # noqa: E402

from files.import_file import ImportFile  # noqa: E402

FILE_PATH = "test/sample.asc"
gfile = Gio.File.new_for_path(FILE_PATH)


def test_import():
    imported = ImportFile(gfile, "ascii")
    imported.parse()
    assert imported.data.console["console"] == "olc"
    assert imported.data.console["manufacturer"] == "mika"
    assert imported.data.patch[7] == [(47, 1, 255)]
    assert imported.data.sequences[1]["steps"][0] == 1.0
    assert imported.data.sequences[1]["steps"][1] == 2.0
    assert imported.data.sequences[1]["steps"][2] == 1.0
    assert imported.data.sequences[1]["steps"][3] == 4.0
    assert imported.data.sequences[1]["cues"][2.0]["text"] == "Entrée Public"
    assert imported.data.sequences[1]["cues"][1.0]["channels"] == {
        7: 255,
        20: 255,
        31: 255
    }
    assert imported.data.sequences[2]["text"] == "Chaser 1"
