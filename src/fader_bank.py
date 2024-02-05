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
# from olc.define import MAX_FADER_PAGE
from typing import Any

from olc.define import App
from olc.fader import (Fader, FaderChannels, FaderGM, FaderGroup, FaderPreset,
                       FaderSequence, FaderType)

MAX_FADER_PAGE = 10
MAX_FADER_PER_PAGE = 10


class FaderBank:
    """Pages of faders"""

    active_page: int
    faders: dict
    channels: set
    active_faders: set

    def __init__(self):
        self.active_page = 1
        self.faders = {}
        for page in range(1, MAX_FADER_PAGE + 1):
            self.faders[page] = {}
            for index in range(1, MAX_FADER_PER_PAGE + 1):
                self.faders[page][index] = Fader(index, self)
        self.channels = set()
        self.active_faders = set()
        self.update_active_faders()

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

    def set_fader(self,
                  page: int,
                  index: int,
                  fader_type: FaderType,
                  contents: Any = None) -> None:
        """Assign a fader

        Args:
            page: Fader page
            index: Fader index
            fader_type: Fader type
            contents: Fader contents
        """
        self.faders[page][index].set_level(0)
        if fader_type == FaderType.NONE:
            self.faders[page][index] = Fader(index, self)
        elif fader_type == FaderType.CHANNELS:
            self.faders[page][index] = FaderChannels(index, self, contents)
        elif fader_type == FaderType.GROUP:
            if group := App().lightshow.get_group(contents):
                self.faders[page][index] = FaderGroup(index, self, group)
        elif fader_type == FaderType.GM:
            self.faders[page][index] = FaderGM(index, self)
        elif fader_type == FaderType.PRESET:
            if cue := App().lightshow.get_cue(contents):
                self.faders[page][index] = FaderPreset(index, self, cue)
        elif fader_type == FaderType.SEQUENCE:
            if chaser := App().lightshow.get_chaser(contents):
                self.faders[page][index] = FaderSequence(index, self, chaser)
        if page == self.active_page:
            # Refresh MIDI LCD
            App().midi.update_fader(self.faders[page][index])
            # Refresh Virtual Console
            if App().virtual_console:
                widget = App().virtual_console.faders[self.faders[page][index].index -
                                                      1]
                widget.set_value(0)
                App().virtual_console.fader_moved(widget)
                App().virtual_console.flashes[self.faders[page][index].index -
                                              1].label = self.faders[page][index].text
                App().virtual_console.flashes[self.faders[page][index].index -
                                              1].queue_draw()
        # TODO: Update FaderTab

    def update_active_faders(self) -> None:
        """List faders with channels levels"""
        self.active_faders = set()
        for page in self.faders.values():
            for fader in page.values():
                if isinstance(fader,
                              (FaderGroup, FaderPreset, FaderChannels, FaderSequence)):
                    self.active_faders.add(fader)
                    self.channels = self.channels | fader.channels

    def update_levels(self) -> None:
        """Update faders levels for DMX"""
        for channel in self.channels:
            if not App().lightshow.patch.is_patched(channel):
                continue
            level_fader = -1
            for fader in self.active_faders:
                if fader.dmx[channel - 1] > level_fader:
                    level_fader = fader.dmx[channel - 1]
                if level_fader != -1:
                    App().backend.dmx.levels["faders"][channel - 1] = level_fader
