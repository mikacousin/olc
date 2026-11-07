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
"""Paged channels matrix manager for OSC tablet controllers."""

from __future__ import annotations

import json
import typing

from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class ChannelsGridManager:
    """Manages a paged virtual grid of channels for OSC tablet remotes."""

    def __init__(
        self,
        app: CoreApplication,
        grid_size: int = 24,
        start_channel: int = 1,
    ) -> None:
        self.app = app
        self._grid_size: int = max(1, min(96, int(grid_size)))
        self._start_channel: int = max(1, min(MAX_CHANNELS, int(start_channel)))

    @property
    def grid_size(self) -> int:
        """Number of cells per page on the OSC remote."""
        return self._grid_size

    @grid_size.setter
    def grid_size(self, size: int) -> None:
        self._grid_size = max(1, min(96, int(size)))

    @property
    def start_channel(self) -> int:
        """First channel ID of the current page (1-based)."""
        return self._start_channel

    @start_channel.setter
    def start_channel(self, channel: int) -> None:
        self._start_channel = max(1, min(MAX_CHANNELS, int(channel)))

    @property
    def current_page(self) -> int:
        """1-based current page index."""
        return (self._start_channel - 1) // self._grid_size + 1

    @property
    def total_pages(self) -> int:
        """Total number of pages based on MAX_CHANNELS and grid_size."""
        return max(1, (MAX_CHANNELS + self._grid_size - 1) // self._grid_size)

    @property
    def end_channel(self) -> int:
        """Last channel ID on the current page."""
        return min(MAX_CHANNELS, self._start_channel + self._grid_size - 1)

    @property
    def page_info(self) -> tuple[int, int, int, int]:
        """Return tuple of (current_page, total_pages, start_channel, end_channel)."""
        return (
            self.current_page,
            self.total_pages,
            self.start_channel,
            self.end_channel,
        )

    def next_page(self) -> None:
        """Advance to the next page of channels."""
        target = self._start_channel + self._grid_size
        if target <= MAX_CHANNELS:
            self.start_channel = target

    def prev_page(self) -> None:
        """Go back to the previous page of channels."""
        self.start_channel = max(1, self._start_channel - self._grid_size)

    def get_cell_for_channel(self, channel: int) -> int | None:
        """Return the 1-based cell index for a channel if currently visible."""
        if self._start_channel <= channel <= self.end_channel:
            return channel - self._start_channel + 1
        return None

    def get_channel_for_cell(self, cell_index: int) -> int | None:
        """Return the 1-based channel ID for a 1-based cell index."""
        if 1 <= cell_index <= self._grid_size:
            ch = self._start_channel + cell_index - 1
            if ch <= MAX_CHANNELS:
                return ch
        return None

    def get_cell_info(self, cell_index: int) -> dict[str, typing.Any]:
        """Compute the full telemetry payload for a 1-based cell."""
        ch = self.get_channel_for_cell(cell_index)
        if ch is None:
            return {
                "cell": cell_index,
                "channel": 0,
                "level": 0.0,
                "label": "",
                "selected": 0,
                "color": "zero",
            }

        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

        raw_level = 0
        color_state = "zero"

        if backend_dmx is not None:
            comp_level, _ = backend_dmx.get_composite_level(ch - 1)
            intensity_mult = float(
                getattr(backend_dmx, "effective_intensity_mult", 1.0)
            )
            scaled_level = round(comp_level * intensity_mult)
            raw_level = scaled_level

            if scaled_level == 0:
                color_state = "zero"
            elif backend_dmx.levels["user"][ch - 1] != -1:
                color_state = "manual"
            elif backend_dmx.levels["faders"][ch - 1] > 0:
                color_state = "fader"
            elif self.app.lightshow.independents.dmx[ch - 1] > 0:
                color_state = "independent"
            else:
                color_state = "cue"

        level_norm = round(raw_level / 255.0, 3)

        label = f"Ch {ch}"
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is not None:
            dev = patch.devices.get(ch)
            if dev is not None and getattr(dev, "label", None):
                label = str(dev.label)

        selected_channels = getattr(self.app, "selected_channels", [])
        is_selected = 1 if ch in selected_channels else 0

        return {
            "cell": cell_index,
            "channel": ch,
            "level": level_norm,
            "label": label,
            "selected": is_selected,
            "color": color_state,
        }

    def get_page_snapshot(self) -> list[dict[str, typing.Any]]:
        """Return full list of cell states for the active page."""
        return [self.get_cell_info(i) for i in range(1, self._grid_size + 1)]

    def get_page_snapshot_json(self) -> str:
        """Serialize current page cells to JSON."""
        return json.dumps(self.get_page_snapshot())
