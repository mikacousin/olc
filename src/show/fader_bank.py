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
    FaderEffectMaster,
    FaderMain,
    FaderPreset,
    FaderSequence,
    FaderType,
)
from olc.show.palette import PaletteCategory

if typing.TYPE_CHECKING:
    import olc.show.fader_bank
    from olc.core.app import CoreApplication
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
    skip_empty_pages: bool
    fixed_faders: dict[int, int]
    lightshow: typing.Optional[LightShow]

    def __init__(self, lightshow: typing.Optional[LightShow] = None) -> None:
        self.lightshow = lightshow
        self.active_page = 1
        self.faders = {}
        self.max_fader_page = MAX_FADER_PAGE
        self.max_fader_per_page = MAX_FADER_PER_PAGE
        self.skip_empty_pages = False
        self.fixed_faders = {}
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

    def resolve_page(self, page: int, index: int) -> int:
        """Return fixed source page for *index* if fixed and valid, else *page*."""
        src_page = self.fixed_faders.get(index)
        if (
            src_page is not None
            and src_page in self.faders
            and self.get_fader_type(src_page, index) != FaderType.NONE
        ):
            return src_page
        return page

    def is_fader_fixed(self, page: int, index: int) -> bool:
        """Return True if fader *(page, index)* is fixed across all pages."""
        return self.fixed_faders.get(index) == page

    def get_fixed_source_page(self, index: int) -> int | None:
        """Return source page fixing column *index*, or None if not fixed."""
        src_page = self.fixed_faders.get(index)
        if (
            src_page is not None
            and src_page in self.faders
            and self.get_fader_type(src_page, index) != FaderType.NONE
        ):
            return src_page
        return None

    def set_fader_fixed(self, page: int, index: int, fixed: bool) -> None:
        """Fix or unfix fader at *(page, index)* across all pages."""
        if fixed:
            if (
                page in self.faders
                and index in self.faders[page]
                and self.get_fader_type(page, index) != FaderType.NONE
            ):
                self.fixed_faders[index] = page
        elif self.fixed_faders.get(index) == page:
            self.fixed_faders.pop(index, None)

    def get_fader(self, index: int, page: int | None = None) -> Fader:
        """Get effective fader on active (or specified) page, honoring fixed faders."""
        target_page = self.active_page if page is None else page
        effective_page = self.resolve_page(target_page, index)
        return self.faders[effective_page][index]

    def iter_page_faders(self, page: int | None = None) -> list[Fader]:
        """Return ordered list of effective faders for *page* (default active_page)."""
        return [
            self.get_fader(index, page)
            for index in range(1, self.max_fader_per_page + 1)
        ]

    def reset_faders(self, reset_page_count: bool = False) -> None:
        """Reset all faders"""
        self.active_page = 1
        self.fixed_faders = {}
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
            self.skip_empty_pages = False
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

    def is_page_populated(self, page: int) -> bool:
        """Return True if *page* has at least one configured (non-NONE) fader."""
        if page not in self.faders:
            return False
        return any(
            self.get_fader_type(page, idx) != FaderType.NONE
            for idx in self.faders[page]
        )

    def get_populated_pages(self) -> list[int]:
        """Return sorted list of page numbers (1..max_fader_page) with >= 1 fader."""
        return [
            p
            for p in sorted(self.faders.keys())
            if 1 <= p <= self.max_fader_page and self.is_page_populated(p)
        ]

    def get_next_page(self, step: int = 1, *, skip_empty: bool | None = None) -> int:
        """Compute next or previous playback page, optionally skipping empty pages."""
        max_p = max(1, int(self.max_fader_page))
        use_skip = self.skip_empty_pages if skip_empty is None else bool(skip_empty)
        direction = 1 if step >= 0 else -1

        if use_skip:
            populated = set(self.get_populated_pages())
            if populated:
                for offset in range(1, max_p + 1):
                    candidate = (
                        (self.active_page - 1 + direction * offset) % max_p
                    ) + 1
                    if candidate in populated:
                        return candidate

        return ((self.active_page - 1 + direction) % max_p) + 1

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

        for idx, src_p in list(self.fixed_faders.items()):
            if src_p > target:
                del self.fixed_faders[idx]

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
        if isinstance(self.faders[page][index], FaderEffectMaster):
            return FaderType.FX_MASTER
        if isinstance(self.faders[page][index], FaderMain):
            return FaderType.MAIN
        return FaderType.NONE

    def set_fader(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: dict[int, int]
        | dict[str, typing.Any]
        | tuple[str, int]
        | float
        | None = None,
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
            if fader_type == FaderType.NONE and self.fixed_faders.get(index) == page:
                self.fixed_faders.pop(index, None)
            if not isinstance(self.faders[page][index], FaderMain):
                self.faders[page][index].set_level(0)
            self._set_fader_type(page, index, fader_type, contents)

    def _resolve_preset_contents(
        self,
        contents: dict[int, int]
        | dict[str, typing.Any]
        | tuple[str, int]
        | float
        | None,
    ) -> Palette | None:
        """Resolve Preset palette from its number."""
        if (
            self.lightshow
            and isinstance(contents, (int, float))
            and hasattr(self.lightshow, "palettes")
        ):
            return self.lightshow.palettes.get(PaletteCategory.PRESET, float(contents))
        return None

    def _resolve_effect_contents(
        self,
        contents: dict[int, int]
        | dict[str, typing.Any]
        | tuple[str, int]
        | float
        | None,
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
        contents: dict[int, int]
        | dict[str, typing.Any]
        | tuple[str, int]
        | float
        | None,
    ) -> None:
        fader_bank_type = typing.cast("olc.show.fader_bank.FaderBank", self)
        if fader_type == FaderType.NONE:
            self.faders[page][index] = Fader(index, fader_bank_type)
            self.faders[page][index].set_level(0)
        elif fader_type == FaderType.CHANNELS:
            channels = (
                {int(k): int(v) for k, v in contents.items()}
                if isinstance(contents, dict)
                else None
            )
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
        elif fader_type == FaderType.FX_MASTER:
            m_kind = "speed"
            m_id = 1
            if isinstance(contents, dict):
                m_kind = str(contents.get("master_kind", "speed"))
                m_id = int(contents.get("master_id", 1))
            elif isinstance(contents, (tuple, list)) and len(contents) >= 2:
                m_kind = str(contents[0])
                m_id = int(contents[1])
            elif isinstance(contents, (int, float)):
                m_id = int(contents)
            self.faders[page][index] = FaderEffectMaster(
                index, fader_bank_type, master_kind=m_kind, master_id=m_id
            )
        self.update_active_faders()
        self.update_levels()

    def _set_fader_contents(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: dict[int, int]
        | dict[str, typing.Any]
        | tuple[str, int]
        | float
        | None,
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
        elif fader_type == FaderType.FX_MASTER:
            self.faders[page][index].set_contents(contents)

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
            dmx = self.app.backend.dmx
            levels = dmx.levels
            faders_levels = levels["faders"]
            faders_levels.fill(0)
            gm_exempt_levels = levels.get("faders_gm_exempt")
            if gm_exempt_levels is not None:
                gm_exempt_levels.fill(0)
            inhib_levels = levels.get("faders_inhibitive")
            if inhib_levels is not None:
                inhib_levels.fill(1.0)
            solo_levels = levels.get("faders_solo")
            if solo_levels is not None:
                solo_levels.fill(0.0)
            swop_prot_levels = levels.get("faders_swop_protect")
            if swop_prot_levels is not None:
                swop_prot_levels.fill(0.0)

            max_solo_level = 0.0
            for fader in self.active_faders:
                if getattr(fader, "inhibitive", False):
                    if inhib_levels is not None:
                        cap = max(0.0, min(1.0, float(fader.level)))
                        for ch in fader.channels:
                            if 1 <= ch <= len(inhib_levels):
                                inhib_levels[ch - 1] = min(inhib_levels[ch - 1], cap)
                    continue
                if getattr(fader, "solo_mode", False):
                    if fader.level > 0.0:
                        max_solo_level = max(
                            max_solo_level, min(1.0, float(fader.level))
                        )
                        if solo_levels is not None:
                            np.maximum(solo_levels, fader.dmx, out=solo_levels)
                    continue
                if gm_exempt_levels is not None and getattr(
                    fader, "exempt_grand_master", False
                ):
                    np.maximum(gm_exempt_levels, fader.dmx, out=gm_exempt_levels)
                elif swop_prot_levels is not None and getattr(
                    fader, "swop_protect", False
                ):
                    np.maximum(swop_prot_levels, fader.dmx, out=swop_prot_levels)
                else:
                    np.maximum(faders_levels, fader.dmx, out=faders_levels)
            dmx.solo_duck = max(0.0, 1.0 - max_solo_level)
