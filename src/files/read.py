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
from gi.repository import Gio


class ReadFile:
    """Read file

    This class must be sub-classed and parse implemented
    """

    file: Gio.File
    contents: str

    def __init__(self, file: Gio.File):
        self.file = file
        self.contents = ""

    def read(self) -> None:
        """Read all file"""
        input_stream = self.file.read()
        file_size = input_stream.query_info(Gio.FILE_ATTRIBUTE_STANDARD_SIZE).get_size()
        data = input_stream.read_bytes(file_size, None)
        self.contents = str(from_bytes(data.get_data()).best())
        input_stream.close()
        self.parse()

    def parse(self) -> None:
        """Parse file

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError
