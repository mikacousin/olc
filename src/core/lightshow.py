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

from olc.cue import Cues
from olc.curve import Curves
from olc.define import UNIVERSES
from olc.fader_bank import FaderBank
from olc.group import Groups
from olc.independent import Independents
from olc.patch import DMXPatch, PatchByOutputs
from olc.sequence import Sequence

if typing.TYPE_CHECKING:
    import olc.core.lightshow
    from olc.core.app import CoreApplication
    from olc.cue import Cue
    from olc.group import Group


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


# pylint: disable=too-many-instance-attributes
class LightShow(ShowFile):
    """Light show data"""

    app: CoreApplication | None
    curves: Curves
    main_playback: Sequence
    cues: Cues
    chasers: list
    groups: Groups
    fader_bank: FaderBank
    independents: Independents
    patch: DMXPatch
    patch_by_outputs: PatchByOutputs

    def __init__(self, app: CoreApplication | None = None) -> None:
        super().__init__(None)
        self.app = app
        lightshow_type = typing.cast("olc.core.lightshow.LightShow", self)
        # Curves
        self.curves = Curves(typing.cast(typing.Any, self))
        # Main Playback
        self.main_playback = Sequence(1, text="Main Playback", lightshow=lightshow_type)
        # List of global memories
        self.cues = Cues(self)
        # List of chasers
        self.chasers = []
        # List of groups
        self.groups = Groups(lightshow_type)
        # Faders
        self.fader_bank = FaderBank(lightshow_type)
        # Independents
        self.independents = Independents(lightshow_type)
        # Patch
        self.patch = DMXPatch(UNIVERSES)
        self.patch_by_outputs = PatchByOutputs(
            typing.cast(typing.Any, app or self.app), self.patch
        )

    def get_cue(self, number: float) -> None | Cue:
        """Get Cue with his number

        Args:
            number: Cue number

        Returns:
            Cue or None
        """
        return self.cues.get(number, 0)

    def get_group(self, number: float) -> None | Group:
        """Get Group with his number

        Args:
            number: Group number

        Returns:
            Group or None
        """
        return self.groups.get(number)

    def get_chaser(self, number: float) -> None | Sequence:
        """Get Chaser with his number

        Args:
            number: Chaser number

        Returns:
            Chaser or None
        """
        for chaser in self.chasers:
            if chaser.index == number:
                return chaser
        return None

    def reset(self) -> None:
        """Reset all"""
        lightshow_type = typing.cast("olc.core.lightshow.LightShow", self)
        del self.main_playback.steps[1:]
        self.cues.clear()
        for chaser in self.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        del self.chasers[:]
        self.groups.clear()
        self.fader_bank.reset_faders()
        self.independents = Independents(lightshow_type)
        self.patch.patch_empty()
