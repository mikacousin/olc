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
from __future__ import annotations

import gzip
import logging
import pathlib
import threading
import typing

from charset_normalizer import from_bytes

if typing.TYPE_CHECKING:
    from olc.files.import_file import ImportFile

LOGGER = logging.getLogger(__name__)


def _read_file_bytes(file: pathlib.Path | str | typing.Any) -> bytes:  # noqa: ANN401
    if isinstance(file, (pathlib.Path, str)):
        return pathlib.Path(file).read_bytes()
    if hasattr(file, "get_path"):
        path = file.get_path()
        if path:
            return pathlib.Path(path).read_bytes()
    if hasattr(file, "load_contents"):
        _success, data, _etag = file.load_contents(None)
        return bytes(data)
    raise TypeError(f"Unsupported file source: {file!r}")


class ReadFile:
    """Read file

    This class must be sub-classed and parse implemented
    """

    window: object | None
    imported: ImportFile
    compressed: bool
    contents: str

    def __init__(
        self,
        imported: ImportFile,
        window: object | None = None,
        compressed: bool = False,
        importation: bool = False,
        on_error: typing.Callable[[str], None] | None = None,
    ) -> None:
        self.imported = imported
        self.window = window
        self.compressed = compressed
        self.importation = importation
        self.on_error = on_error
        self.contents = ""

    def _process_data(self, data: bytes, auto_import: bool = True) -> None:
        if self.compressed:
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                self._error_dialog("Input file is not a valid file: BadGzipFile")
                return
        self.contents = str(from_bytes(data).best())
        self.parse()
        self.imported.data.clean()
        if not auto_import:
            return
        if self.importation:
            self.imported.select_data()
        else:
            self.imported.load_all()

    def read(self) -> None:
        """Read all file asynchronously."""

        def _worker() -> None:
            self.read_sync(auto_import=True)

        threading.Thread(target=_worker, daemon=True).start()

    def read_sync(self, auto_import: bool = True) -> None:
        """Read all file synchronously.

        Args:
            auto_import: If True, automatically import or prompt via dialog.
                If False, only parse and clean data.
        """
        try:
            data = _read_file_bytes(self.imported.file)
        except OSError as error:
            self._error_dialog(str(error))
            return
        self._process_data(data, auto_import=auto_import)

    def parse(self) -> None:
        """Parse file

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def _error_dialog(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)
        else:
            LOGGER.error("%s", message)
