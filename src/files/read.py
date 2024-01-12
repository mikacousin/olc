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
from charset_normalizer import from_bytes
from gi.repository import Gio, GLib


class ReadFile:
    """Read file

    This class must be sub-classed and parse implemented
    """

    file: Gio.File

    def __init__(self, file: Gio.File):
        self.file = file

    def parse(self) -> None:
        """Read file line by line"""
        input_stream = self.file.read()
        data_stream = Gio.DataInputStream.new(input_stream)
        line = ""
        bytes_line = b""

        while True:
            try:
                byte = data_stream.read_byte()
            except GLib.Error:
                # EOF
                break

            if byte == 10 or byte == 13 and line:
                line = ""
                charset_match = from_bytes(bytes_line).best()
                if charset_match:
                    if charset_match.language == "Unknown":
                        line = bytes_line.decode("utf-8").strip()
                    else:
                        line = str(from_bytes(bytes_line).best()).strip()
                if line:
                    loop = self.do_parse(line)
                    if not loop:
                        break
                    line = ""
                    bytes_line = b""
            else:
                bytes_line += byte.to_bytes()

        data_stream.close()
        input_stream.close()

    def do_parse(self, line: str) -> bool:
        """Parse line

        Args:
            line: Line to parse

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError
