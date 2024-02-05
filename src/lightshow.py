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
from __future__ import annotations

import typing

from gi.repository import GLib, Gtk
from olc.curve import Curves
from olc.define import UNIVERSES, App
from olc.fader_bank import FaderBank
from olc.independent import Independents
from olc.patch import DMXPatch
from olc.sequence import Sequence

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.cue import Cue
    from olc.group import Group


class ShowFile:
    """Opened file"""

    file: Gio.File
    basename: str
    modified: bool
    recent_manager: Gtk.RecentManager

    def __init__(self, file):
        self.file = file
        self.basename = self.file.get_basename() if file else ""
        self.modified = False
        self.recent_manager = Gtk.RecentManager.get_default()

    def add_recent_file(self) -> None:
        """Add to Recent files

        Raises:
            e: not documented
        """
        if not self.file:
            return
        uri = self.file.get_uri()
        if uri:
            # We remove the project from recent projects list
            # and then re-add it to this list to make sure it
            # gets positioned at the top of the recent projects list.
            try:
                self.recent_manager.remove_item(uri)
            except GLib.Error as e:
                if e.domain != "gtk-recent-manager-error-quark":
                    raise e
            self.recent_manager.add_item(uri)

    def set_modified(self) -> None:
        """Set file as modified"""
        self.modified = True
        self.basename = self.file.get_basename() if self.file else ""
        App().window.header.set_title(f"{self.basename}*")

    def set_not_modified(self) -> None:
        """Set file as not modified"""
        self.modified = False
        self.basename = self.file.get_basename() if self.file else ""
        App().window.header.set_title(self.basename)


class LightShow(ShowFile):
    """Light show data"""

    curves: Curves
    main_playback: Sequence
    cues: list
    chasers: list
    groups: list
    fader_bank: FaderBank
    independents: Independents
    patch: DMXPatch

    def __init__(self):
        super().__init__(None)
        # Curves
        self.curves = Curves()
        # Main Playback
        self.main_playback = Sequence(1, text="Main Playback")
        # List of global memories
        self.cues = []
        # List of chasers
        self.chasers = []
        # List of groups
        self.groups = []
        # Faders
        self.fader_bank = FaderBank()
        # Independents
        self.independents = Independents()
        # Patch
        self.patch = DMXPatch(UNIVERSES)

    def get_cue(self, number: float) -> None | Cue:
        """Get Cue with his number

        Args:
            number: Cue number

        Returns:
            Cue or None
        """
        for cue in self.cues:
            if cue.memory == number:
                return cue
        return None

    def get_group(self, number: float) -> None | Group:
        """Get Group with his number

        Args:
            number: Group number

        Returns:
            Group or None
        """
        for group in self.groups:
            if group.index == number:
                return group
        return None

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
        del self.main_playback.steps[1:]
        del self.cues[:]
        for chaser in self.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        del self.chasers[:]
        del self.groups[:]
        self.fader_bank.reset_faders()
        self.independents = Independents()
        self.patch.patch_empty()
