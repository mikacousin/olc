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

if typing.TYPE_CHECKING:
    from olc.lightshow import LightShow


class WriteFile:
    """Write file

    This class must be sub-classed and export implemented
    """

    file: Gio.File
    compressed: bool
    stream: Gio.FileOutputStream | Gio.ConverterOutputStream | None

    def __init__(
        self, file: Gio.File, lightshow: LightShow, compressed: bool = False
    ) -> None:
        self.file = file
        self.compressed = compressed
        self.stream = None
        self.lightshow = lightshow

    def write(self) -> None:
        """Write file"""
        output_stream = self.file.replace("", False, Gio.FileCreateFlags.NONE, None)
        if self.compressed:
            converter = Gio.ZlibCompressor.new(Gio.ZlibCompressorFormat.GZIP, -1)
            self.stream = Gio.ConverterOutputStream.new(output_stream, converter)
        else:
            self.stream = output_stream
        # Write data
        self.export()
        self.stream.close()
        self.lightshow.set_not_modified()
        self.lightshow.add_recent_file()

    def export(self) -> None:
        """Export file

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError
