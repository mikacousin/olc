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
import typing

from gi.repository import Gio
from olc.files.ascii.writer import AsciiWriter
from olc.files.file_type import FileType
from olc.files.olc.writer import OlcWriter

if typing.TYPE_CHECKING:
    from olc.lightshow import LightShow


class ExportFile:
    """Export file"""

    file: Gio.File
    file_type: FileType
    writer: AsciiWriter | OlcWriter

    def __init__(
        self, file: Gio.File, file_type: FileType, lightshow: LightShow
    ) -> None:
        self.file = file
        self.file_type = file_type

        if self.file_type is FileType.ASCII:
            self.writer = AsciiWriter(self.file, lightshow)
        else:
            self.writer = OlcWriter(self.file, lightshow)

    def write(self) -> None:
        """Write file"""
        self.writer.write()

    def get_file_type(self) -> FileType:
        """Get file type

        Returns:
            "ascii" or "olc"
        """
        return self.file_type
