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

import typing

from olc.dmx import Dmx

if typing.TYPE_CHECKING:
    from olc.lightshow import LightShow
    from olc.patch import DMXPatch


# pylint: disable=too-few-public-methods
class DMXBackend:
    """Create DMX Backend"""

    dmx: Dmx
    patch: DMXPatch

    def __init__(self, lightshow: LightShow) -> None:
        self.dmx = Dmx(typing.cast(typing.Any, self), lightshow)
        self.patch = lightshow.patch

    def stop(self) -> None:
        """Stop backend"""
        self.dmx.thread.stop()
