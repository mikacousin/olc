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

from olc.define import MAX_ALLOWED_FADER_PAGES, MAX_FADER_PAGE, MAX_FADER_PER_PAGE
from olc.show.fader import (
    Fader,
    FaderChannels,
    FaderEffect,
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
    from olc.show.effect import EffectDefinition
    from olc.show.lightshow import LightShow
    from olc.show.palette import Palette


class FaderBank:
    """Pages of faders"""

    active_page: int
    faders: dict
    channels: set
    active_faders: set
    max_fader_page: int
    max_fader_per_page: int
    lightshow: typing.Optional[LightShow]

    def __init__(self, lightshow: typing.Optional[LightShow] = None) -> None:
        self.lightshow = lightshow
        self.active_page = 1
        self.faders = {}
        self.max_fader_page = MAX_FADER_PAGE
        self.max_fader_per_page = MAX_FADER_PER_PAGE
        for page in range(1, self.max_fader_page + 1):
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

    def reset_faders(self, reset_page_count: bool = False) -> None:
        """Reset all faders"""
        self.active_page = 1
        for page in sorted(list(self.faders.keys())):
            for index in range(1, MAX_FADER_PER_PAGE + 1):
                self.set_fader(page, index, FaderType.NONE)
        if reset_page_count:
            for page in [p for p in list(self.faders.keys()) if p > MAX_FADER_PAGE]:
                del self.faders[page]
            fader_bank_type = typing.cast("olc.show.fader_bank.FaderBank", self)
            for page in range(1, MAX_FADER_PAGE + 1):
                if page not in self.faders:
                    self.faders[page] = {
                        index: Fader(index, fader_bank_type)
                        for index in range(1, self.max_fader_per_page + 1)
                    }
            self.max_fader_page = MAX_FADER_PAGE
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

    def get_populated_faders_above_page(
        self, max_page: int
    ) -> list[tuple[int, int, FaderType, str]]:
        """Return non-empty faders configured on pages strictly above *max_page*."""
        populated: list[tuple[int, int, FaderType, str]] = []
        for page in sorted(self.faders.keys()):
            if page <= max_page:
                continue
            for index in sorted(self.faders[page].keys()):
                ftype = self.get_fader_type(page, index)
                if ftype != FaderType.NONE:
                    label = str(getattr(self.faders[page][index], "text", ""))
                    populated.append((page, index, ftype, label))
        return populated

    def set_max_pages(self, new_max_page: int) -> bool:
        """Resize available fader pages at runtime.

        Args:
            new_max_page: Target total number of fader pages (clamped 1..100).

        Returns:
            True if ``active_page`` had to be clamped down to fit, else False.
        """
        target = max(1, min(MAX_ALLOWED_FADER_PAGES, int(new_max_page)))
        if target == self.max_fader_page and len(self.faders) == target:
            return False

        fader_bank_type = typing.cast("olc.show.fader_bank.FaderBank", self)
        if target >= self.max_fader_page:
            for page in range(1, target + 1):
                if page not in self.faders:
                    self.faders[page] = {
                        index: Fader(index, fader_bank_type)
                        for index in range(1, self.max_fader_per_page + 1)
                    }
            self.max_fader_page = target
            midi = getattr(self.app, "midi", None) if self.app is not None else None
            if midi is not None and hasattr(midi, "ensure_fader_pages"):
                midi.ensure_fader_pages(target)
            return False

        for page in [p for p in sorted(self.faders.keys()) if p > target]:
            for fader in self.faders[page].values():
                if getattr(fader, "is_flashing", False):
                    fader.flash_off()
                if not isinstance(fader, FaderMain):
                    fader.set_level(0)
            del self.faders[page]

        self.max_fader_page = target
        page_clamped = False
        if self.active_page > target:
            self.active_page = target
            page_clamped = True

        self.update_active_faders()
        self.update_levels()
        if (
            self.app
            and hasattr(self.app, "backend")
            and self.app.backend
            and hasattr(self.app.backend, "dmx")
        ):
            self.app.backend.dmx.set_levels()
        return page_clamped

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
        if isinstance(self.faders[page][index], FaderEffect):
            return FaderType.EFFECT
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

    def _resolve_effect_contents(
        self, contents: dict[int, int] | float | None
    ) -> EffectDefinition | None:
        """Resolve an EffectDefinition from its effect number."""
        if (
            self.lightshow
            and isinstance(contents, (int, float))
            and hasattr(self.lightshow, "effects")
        ):
            return self.lightshow.effects.get(float(contents))
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
                and (seq_obj := self.lightshow.get_sequence(contents))
            ):
                self.faders[page][index] = FaderSequence(
                    index, fader_bank_type, seq_obj
                )
            else:
                self.faders[page][index] = FaderSequence(index, fader_bank_type)
            self.faders[page][index].set_level(0)
        elif fader_type == FaderType.EFFECT:
            eff_obj = self._resolve_effect_contents(contents)
            sel_chs = (
                list(getattr(self.app, "selected_channels", []))
                if self.app is not None
                else []
            )
            self.faders[page][index] = FaderEffect(
                index, fader_bank_type, eff_obj, effect_channels=sel_chs
            )
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
            seq_obj = None
            if self.lightshow and isinstance(contents, (int, float)):
                seq_obj = self.lightshow.get_sequence(contents)
            self.faders[page][index].set_contents(seq_obj)
        elif fader_type == FaderType.EFFECT:
            eff_obj = self._resolve_effect_contents(contents)
            self.faders[page][index].set_contents(eff_obj)

    def update_active_faders(self) -> None:
        """List faders with channels levels"""
        self.active_faders = set()
        for page in self.faders.values():
            for fader in page.values():
                if isinstance(
                    fader, (FaderPreset, FaderChannels, FaderSequence, FaderEffect)
                ):
                    self.active_faders.add(fader)
                    self.channels = self.channels | fader.channels

    def update_levels(self) -> None:
        """Update faders levels for DMX"""
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            levels = self.app.backend.dmx.levels
            faders_levels = levels["faders"]
            faders_levels.fill(0)
            gm_exempt_levels = levels.get("faders_gm_exempt")
            if gm_exempt_levels is not None:
                gm_exempt_levels.fill(0)
            for fader in self.active_faders:
                if gm_exempt_levels is not None and getattr(
                    fader, "exempt_grand_master", False
                ):
                    np.maximum(gm_exempt_levels, fader.dmx, out=gm_exempt_levels)
                else:
                    np.maximum(faders_levels, fader.dmx, out=faders_levels)
