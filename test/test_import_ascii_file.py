import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio  # noqa: E402

from files.import_file import ImportFile  # noqa: E402

FILE_PATH = "test/sample.asc"
gfile = Gio.File.new_for_path(FILE_PATH)


def test_import():
    imported = ImportFile(gfile, "ascii")
    imported.parse()
    assert imported.data.patch[7] == [(47, 1, 255)]
    assert imported.data.sequences[2]["text"] == "Chaser 1"
