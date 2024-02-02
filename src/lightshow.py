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
from gi.repository import GLib, Gtk

from olc.curve import Curves
from olc.define import MAX_FADER_PAGE, UNIVERSES, App
from olc.independent import Independents
from olc.master import Master
from olc.patch import DMXPatch
from olc.sequence import Sequence


class ShowFile:
    """Opened file"""

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
        # pages of 10 faders
        self.faders = []
        for page in range(MAX_FADER_PAGE):
            self.faders.extend(Master(page + 1, i + 1, 0, 0) for i in range(10))
        # Independents
        self.independents = Independents()
        # Patch
        self.patch = DMXPatch(UNIVERSES)

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
        del self.faders[:]
        App().fader_page = 1
        for page in range(MAX_FADER_PAGE):
            self.faders.extend(Master(page + 1, i + 1, 0, 0) for i in range(10))
        self.independents = Independents()
        self.patch.patch_empty()
