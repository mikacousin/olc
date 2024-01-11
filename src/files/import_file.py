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
from gi.repository import Gio, Gtk
from olc.cue import Cue
from olc.define import App
from olc.files.ascii.parser import AsciiParser
from olc.files.import_dialog import Action, DialogData
from olc.files.parsed_data import ParsedData
from olc.step import Step


class ImportFile:
    """Import file"""

    file: Gio.File
    file_type: str  # "ascii" or "olc"
    data = ParsedData
    actions: dict
    parser: AsciiParser

    def __init__(self, file: Gio.File, file_type: str):
        self.file = file
        self.file_type = file_type
        self.data = ParsedData()
        self.actions = {}

        if self.file_type == "ascii":
            self.parser = AsciiParser(self.file, self.data)

    def parse(self) -> None:
        """Start reading file"""
        self.parser.parse()

    def select_data(self) -> None:
        """Select data to import"""
        dialog = DialogData(App().window, self.data)
        response = dialog.run()
        self.actions["patch"] = dialog.action_patch
        self.actions["sequences"] = dialog.action_sequences
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self._do_import()

    def _do_import(self):
        self._do_import_patch()
        self._do_import_sequences()
        self._update_ui()

    def _do_import_patch(self) -> None:
        if self.actions["patch"] is Action.IGNORE:
            return
        if self.actions["patch"] is Action.REPLACE:
            App().backend.patch.patch_empty()
        # Import patch
        self.data.import_patch()

    def _do_import_sequences(self) -> None:
        for sequence in self.actions["sequences"]:
            if self.actions["sequences"][sequence] is Action.IGNORE:
                continue
            if self.actions["sequences"][sequence] is Action.REPLACE:
                self._clear_sequence(sequence)
            # Import sequence
            if sequence == 1:
                self.data.import_main_playback(sequence,
                                               self.actions["sequences"][sequence])
                # Add empty step at the end
                cue = Cue(0, 0.0)
                step = Step(sequence, cue=cue)
                App().sequence.add_step(step)
                # Main playback at start
                App().sequence.position = 0
            else:
                self.data.import_chaser(sequence, self.actions["sequences"][sequence])

    def _clear_sequence(self, sequence: int) -> None:
        if sequence == 1:
            del App().memories[:]
            del App().sequence.steps[1:]
        else:
            chaser = None
            for chsr in App().chasers:
                if chsr.index == sequence:
                    chaser = chsr
                    break
                if chaser:
                    App().chasers.remove(chaser)

    def _update_ui(self) -> None:
        App().window.live_view.channels_view.update()
        App().tabs.refresh_all()
        subtitle = (f"Mem. : 0.0 - Next Mem. : {App().sequence.steps[1].cue.memory} "
                    f"{App().sequence.steps[1].cue.text}")
        App().window.header.set_subtitle(subtitle)
        App().window.playback.update_xfade_display(0)
        App().window.playback.update_sequence_display()
