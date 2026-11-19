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

import numpy as np

from olc.define import MAX_FADER_PAGE, MAX_FADER_PER_PAGE
from olc.show.fader import (
    Fader,
    FaderChannels,
    FaderMain,
    FaderPreset,
    FaderSequence,
    FaderType,
)
from olc.show.palette import PaletteCategory

if typing.TYPE_CHECKING:
    import olc.show.fader_bank
    from olc.core.app import CoreApplication
    from olc.show.cue import Cue
    from olc.show.lightshow import LightShow
    from olc.show.palette import Palette


class FaderBank:
    """Pages of faders"""

    active_page: int
    faders: dict
    channels: set
    active_faders: set
    max_fader_per_page: int
    lightshow: typing.Optional[LightShow]

    def __init__(self, lightshow: typing.Optional[LightShow] = None) -> None:
        self.lightshow = lightshow
        self.active_page = 1
        self.faders = {}
        self.max_fader_per_page = MAX_FADER_PER_PAGE
        for page in range(1, MAX_FADER_PAGE + 1):
            self.faders[page] = {}
            for index in range(1, MAX_FADER_PER_PAGE + 1):
                self.faders[page][index] = Fader(
                    index, typing.cast("olc.show.fader_bank.FaderBank", self)
                )
        self.channels = set()
        self.active_faders = set()
        self.update_active_faders()

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.lightshow.app if self.lightshow else None

    def get_fader(self, index: int) -> Fader:
        """Get fader on active page

        Args:
            index: Fader index

        Returns:
            Fader object
        """
        return self.faders[self.active_page][index]

    def reset_faders(self) -> None:
        """Reset all faders"""
        self.active_page = 1
        for page in range(1, MAX_FADER_PAGE + 1):
            for index in range(1, MAX_FADER_PER_PAGE + 1):
                self.set_fader(page, index, FaderType.NONE)
        self.channels = set()
        self.active_faders = set()
        self.update_active_faders()
        if (
            self.app
            and hasattr(self.app, "backend")
            and self.app.backend
            and hasattr(self.app.backend, "dmx")
            and getattr(self.app.backend.dmx, "main_fader", None)
        ):
            self.app.backend.dmx.main_fader.set_level(1.0)

    def get_fader_type(self, page: int, index: int) -> FaderType:
        """Get Fader type

        Args:
            page: Fader page
            index: Fader index

        Returns:
            Fader type
        """
        if isinstance(self.faders[page][index], FaderChannels):
            return FaderType.CHANNELS
        if isinstance(self.faders[page][index], FaderPreset):
            return FaderType.PRESET
        if isinstance(self.faders[page][index], FaderSequence):
            return FaderType.SEQUENCE
        if isinstance(self.faders[page][index], FaderMain):
            return FaderType.MAIN
        return FaderType.NONE

    def set_fader(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: dict[int, int] | float | None = None,
    ) -> None:
        """Assign a fader

        Args:
            page: Fader page
            index: Fader index
            fader_type: Fader type
            contents: Fader contents
        """
        if fader_type == self.get_fader_type(page, index):
            current_fader = self.faders[page][index]
            current_contents = getattr(current_fader, "contents", None)
            current_id = None
            if current_contents is not None:
                if hasattr(current_contents, "index"):
                    current_id = current_contents.index
                elif hasattr(current_contents, "number"):
                    current_id = current_contents.number

            if current_id != contents:
                current_fader.set_level(0)

            self._set_fader_contents(page, index, fader_type, contents)
        else:
            if not isinstance(self.faders[page][index], FaderMain):
                self.faders[page][index].set_level(0)
            self._set_fader_type(page, index, fader_type, contents)

    def _resolve_preset_contents(
        self, contents: dict[int, int] | float | None
    ) -> Palette | Cue | None:
        """Resolve Preset palette first, falling back to Cue."""
        if self.lightshow and isinstance(contents, (int, float)):
            target_num = float(contents)
            if hasattr(self.lightshow, "palettes"):
                preset = self.lightshow.palettes.get(PaletteCategory.PRESET, target_num)
                if preset is not None:
                    return preset
            return self.lightshow.get_cue(target_num)
        return None

    def _set_fader_type(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: dict[int, int] | float | None,
    ) -> None:
        fader_bank_type = typing.cast("olc.show.fader_bank.FaderBank", self)
        if fader_type == FaderType.NONE:
            self.faders[page][index] = Fader(index, fader_bank_type)
            self.faders[page][index].set_level(0)
        elif fader_type == FaderType.CHANNELS:
            channels = contents if isinstance(contents, dict) else None
            self.faders[page][index] = FaderChannels(index, fader_bank_type, channels)
            self.faders[page][index].set_level(0)
        elif fader_type == FaderType.MAIN:
            self.faders[page][index] = FaderMain(index, fader_bank_type)
        elif fader_type == FaderType.PRESET:
            preset_obj = self._resolve_preset_contents(contents)
            self.faders[page][index] = FaderPreset(index, fader_bank_type, preset_obj)
            self.faders[page][index].set_level(0)
        elif fader_type == FaderType.SEQUENCE:
            if (
                self.lightshow
                and isinstance(contents, (int, float))
                and (chaser := self.lightshow.get_chaser(contents))
            ):
                self.faders[page][index] = FaderSequence(index, fader_bank_type, chaser)
            else:
                self.faders[page][index] = FaderSequence(index, fader_bank_type)
            self.faders[page][index].set_level(0)
        self.update_active_faders()
        self.update_levels()

    def _set_fader_contents(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: dict[int, int] | float | None,
    ) -> None:
        if fader_type == FaderType.PRESET:
            preset_obj = self._resolve_preset_contents(contents)
            self.faders[page][index].set_contents(preset_obj)
        elif fader_type == FaderType.SEQUENCE:
            chaser = None
            if self.lightshow and isinstance(contents, (int, float)):
                chaser = self.lightshow.get_chaser(contents)
            self.faders[page][index].set_contents(chaser)

    def update_active_faders(self) -> None:
        """List faders with channels levels"""
        self.active_faders = set()
        for page in self.faders.values():
            for fader in page.values():
                if isinstance(fader, (FaderPreset, FaderChannels, FaderSequence)):
                    self.active_faders.add(fader)
                    self.channels = self.channels | fader.channels

    def update_levels(self) -> None:
        """Update faders levels for DMX"""
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            faders_levels = self.app.backend.dmx.levels["faders"]
            faders_levels.fill(0)
            for fader in self.active_faders:
                np.maximum(faders_levels, fader.dmx, out=faders_levels)
