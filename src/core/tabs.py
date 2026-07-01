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
"""Agnostic tabs model and manager for Open Lighting Console."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


# pylint: disable=too-few-public-methods
class CoreTabs:
    """Agnostic logical manager for interface tab containers and layout."""

    def __init__(self, app: CoreApplication) -> None:
        self.app = app
        # Ordered lists of open tab names for each notebook container
        self.notebooks: dict[str, list[str]] = {
            "live": ["channels"],
            "playback": ["playback"],
        }
        # Currently active/selected tab name for each notebook container
        self.active_tabs: dict[str, str] = {
            "live": "channels",
            "playback": "playback",
        }

    def get_notebook_of_tab(self, tab_name: str) -> typing.Optional[str]:
        """Find which notebook container holds the given tab name."""
        for nbid, tab_list in self.notebooks.items():
            if tab_name in tab_list:
                return nbid
        return None
