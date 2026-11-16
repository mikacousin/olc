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
import pathlib
import typing

if typing.TYPE_CHECKING:
    from olc.show.lightshow import LightShow


def _resolve_path(file: pathlib.Path | str | typing.Any) -> pathlib.Path:  # noqa: ANN401
    if isinstance(file, (pathlib.Path, str)):
        return pathlib.Path(file)
    if hasattr(file, "get_path"):
        path = file.get_path()
        if path:
            return pathlib.Path(path)
    raise TypeError(f"Unsupported file target: {file!r}")


class WriteFile:
    """Write file

    This class must be sub-classed and export implemented
    """

    file: pathlib.Path | str | typing.Any
    compressed: bool
    stream: typing.IO[bytes] | gzip.GzipFile | None

    def __init__(
        self,
        file: pathlib.Path | str | typing.Any,  # noqa: ANN401
        lightshow: LightShow,
        compressed: bool = False,
    ) -> None:
        self.file = file
        self.compressed = compressed
        self.stream = None
        self.lightshow = lightshow

    def write(self) -> None:
        """Write file"""
        path = _resolve_path(self.file)
        if self.compressed:
            with gzip.open(path, "wb") as stream:
                self.stream = stream
                self.export()
        else:
            with open(path, "wb") as stream:
                self.stream = stream
                self.export()
        self.stream = None
        self.lightshow.set_not_modified()
        self.lightshow.add_recent_file()

    def export(self) -> None:
        """Export file

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError
