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

import os
import typing

from olc.define import DEFAULT_UNIVERSES
from olc.devices.builtin import populate_builtin_library
from olc.dmx_engine.universe_config import UniverseMap, default_universe_map
from olc.show.cue import CueEditor
from olc.show.curve import Curves
from olc.show.effect import EffectDefinition, EffectManager
from olc.show.fader_bank import FaderBank
from olc.show.group import Groups
from olc.show.independent import Independents
from olc.show.palette import Palette, PaletteCategory, PaletteManager
from olc.show.park import ParkManager
from olc.show.patch import PatchManager
from olc.show.sequence import Sequence

if typing.TYPE_CHECKING:
    import olc.show.lightshow
    from olc.core.app import CoreApplication
    from olc.devices.fixture import FixtureLibrary
    from olc.show.cue import Cue
    from olc.show.group import Group


class ShowFile:
    """Opened file (Agnostic version, no Gio/Gtk dependency)"""

    file_path: str | None
    basename: str
    modified: bool
    file: typing.Any

    def __init__(self, file_path: str | None) -> None:
        self.file_path = file_path
        self.basename = os.path.basename(file_path) if file_path else ""
        self.modified = False
        self.file = None
        self.on_modified_changed: typing.Callable[[str], None] | None = None

    def add_recent_file(self) -> None:
        """Add to Recent files (no-op in base class)"""

    def set_modified(self) -> None:
        """Set file as modified"""
        self.modified = True
        self.basename = os.path.basename(self.file_path) if self.file_path else ""
        if self.on_modified_changed:
            self.on_modified_changed(f"{self.basename}*")

    def set_not_modified(self) -> None:
        """Set file as not modified"""
        self.modified = False
        self.basename = os.path.basename(self.file_path) if self.file_path else ""
        if self.on_modified_changed:
            self.on_modified_changed(self.basename)


def default_workspace() -> dict[str, typing.Any]:
    """Return default workspace configuration dictionary."""
    return {
        "version": 1,
        "active_pane": "playback",
        "panes": {
            "live": {"tabs": ["channels"], "active_tab": "channels"},
            "playback": {"tabs": ["playback"], "active_tab": "playback"},
        },
        "tab_settings": {"channels": {"view_mode": "All"}},
        "virtual_console": {"open": False},
    }


# pylint: disable=too-many-instance-attributes
class LightShow(ShowFile):
    """Light show data"""

    app: CoreApplication | None
    fixture_library: FixtureLibrary
    curves: Curves
    main_playback: Sequence
    cue_editor: CueEditor
    sequences: list
    effects: EffectManager
    groups: Groups
    palettes: PaletteManager
    fader_bank: FaderBank
    independents: Independents
    patch: PatchManager
    park: ParkManager
    universe_map: UniverseMap
    workspace: dict[str, typing.Any]
    title: str
    home_preset: float | None

    def __init__(self, app: CoreApplication | None = None) -> None:
        super().__init__(None)
        self.app = app
        self.workspace = default_workspace()
        self.title = ""
        self.home_preset = None
        lightshow_type = typing.cast("olc.show.lightshow.LightShow", self)
        # Fixture Library
        self.fixture_library = populate_builtin_library()
        # Curves
        self.curves = Curves(typing.cast(typing.Any, self))
        # Main Playback
        self.main_playback = Sequence(1, text="Main Playback", lightshow=lightshow_type)
        # Blind cue level editor
        self.cue_editor = CueEditor(lightshow_type)
        # Secondary sequences (2..N) and parametric Effects Manager
        self.sequences = []
        self.effects = EffectManager(lightshow_type)
        # List of groups
        self.groups = Groups(lightshow_type)
        # Palettes & Presets
        self.palettes = PaletteManager()
        # Faders
        self.fader_bank = FaderBank(lightshow_type)
        # Independents
        self.independents = Independents(lightshow_type)
        # Patch
        self.patch = PatchManager(list(DEFAULT_UNIVERSES), lightshow=lightshow_type)
        # Park
        self.park = ParkManager()
        # Universe configurations
        self.universe_map = default_universe_map()

    @property
    def chasers(self) -> list:
        """Compatibility alias for secondary sequences list."""
        return self.sequences

    @chasers.setter
    def chasers(self, value: list) -> None:
        self.sequences = value

    def get_cue(self, number: float, sequence: int = 1) -> None | Cue:
        """Get Cue by number and sequence index.

        Args:
            number: Cue number
            sequence: Sequence index (default 1 for Main Playback)

        Returns:
            Cue or None
        """
        seq = (
            self.main_playback
            if sequence in (0, 1)
            else self.get_sequence(float(sequence))
        )
        if seq is not None:
            for step in seq.steps:
                if step.cue is not None and step.cue.number == number:
                    return step.cue
        return None

    def iter_all_cues(self) -> typing.Iterator[Cue]:
        """Yield all unique Cue objects across Main Playback and secondary sequences."""
        seen: set[int] = set()
        for seq in (self.main_playback, *self.sequences):
            for step in seq.steps:
                cue = getattr(step, "cue", None)
                if cue is not None and id(cue) not in seen:
                    seen.add(id(cue))
                    yield cue

    def get_group(self, number: float) -> None | Group:
        """Get Group with his number

        Args:
            number: Group number

        Returns:
            Group or None
        """
        return self.groups.get(number)

    def get_palette(
        self, category: PaletteCategory | str, number: float
    ) -> None | Palette:
        """Get Palette or Preset by category and number."""
        return self.palettes.get(category, number)

    def get_effect(self, number: float) -> None | EffectDefinition:
        """Get EffectDefinition by number, or None."""
        return self.effects.get(number)

    def get_sequence(self, number: float) -> None | Sequence:
        """Get secondary Sequence by its index number."""
        for seq in self.sequences:
            if seq.index == number:
                return seq
        return None

    def get_chaser(self, number: float) -> None | Sequence:
        """Compatibility alias for get_sequence."""
        return self.get_sequence(number)

    def reset(self) -> None:
        """Reset all"""
        lightshow_type = typing.cast("olc.show.lightshow.LightShow", self)
        if self.app is not None and hasattr(self.app, "effects_engine"):
            self.app.effects_engine.stop_all()
        self.title = ""
        self.home_preset = None
        self.fixture_library = populate_builtin_library()
        del self.main_playback.steps[1:]
        for seq in self.sequences:
            if seq.run and seq.thread:
                seq.run = False
                seq.thread.stop()
                seq.thread.join()
        del self.sequences[:]
        self.effects.clear()
        self.groups.clear()
        self.palettes.clear()
        self.fader_bank.reset_faders(reset_page_count=True)
        self.independents = Independents(lightshow_type)
        self.patch.patch_empty()
        self.universe_map = default_universe_map()
