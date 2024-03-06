# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from __future__ import annotations

import gzip
import typing
from gettext import gettext as _

from charset_normalizer import from_bytes
from gi.repository import GLib, Gtk
from olc.define import App

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.files.import_file import ImportFile


class ReadFile:
    """Read file

    This class must be sub-classed and parse implemented
    """

    imported: ImportFile
    compressed: bool
    contents: str

    def __init__(self, imported: ImportFile, compressed=False, importation=False):
        self.imported = imported
        self.compressed = compressed
        self.importation = importation
        self.contents = ""

    def _load_cb(self, file: Gio.File, result: Gio.AsyncResult, user_data=None) -> None:
        try:
            _success, data, _etag = file.load_contents_finish(result)
        except GLib.GError as error:
            self._error_dialog(str(error))
            return
        if self.compressed:
            data = gzip.decompress(data)
        self.contents = str(from_bytes(data).best())
        self.parse()
        self.imported.data.clean()
        if self.importation:
            self.imported.select_data()
        else:
            self.imported.load_all()

    def read(self) -> None:
        """Read all file"""
        self.imported.file.load_contents_async(None, self._load_cb, None)

    def parse(self) -> None:
        """Parse file

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def _error_dialog(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            App().window, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, message)
        dialog.set_title(_("Error"))
        dialog.run()
        dialog.destroy()
