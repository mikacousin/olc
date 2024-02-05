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
from olc.independent import Independents
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
        self.actions = {
            "patch": Action.REPLACE,
            "sequences": {},
            "groups": Action.REPLACE,
            "independents": Action.REPLACE,
            "faders": Action.REPLACE
        }

        if self.file_type == "ascii":
            if App():
                default_time = App().settings.get_double("default-time")
            else:
                default_time = 5.0
            self.parser = AsciiParser(self.file, self.data, default_time)

    def parse(self) -> None:
        """Start reading file"""
        self.parser.read()
        App().lightshow.add_recent_file()
        self.data.clean()

    def select_data(self) -> None:
        """Select data to import"""
        dialog = DialogData(App().window, self.data, self.actions)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self._do_import()
            App().lightshow.set_modified()

    def _do_import(self):
        self._do_import_patch()
        self._do_import_sequences()
        self._do_import_groups()
        self._do_import_independents()
        self._do_import_presets()
        self._do_import_faders()
        self._update_ui()

    def _do_import_patch(self) -> None:
        if self.actions["patch"] is Action.IGNORE:
            return
        if self.actions["patch"] is Action.REPLACE:
            App().lightshow.patch.patch_empty()
        # Import patch
        self.data.import_patch()

    def _do_import_groups(self) -> None:
        if self.actions["groups"] is Action.IGNORE:
            return
        if self.actions["groups"] is Action.REPLACE:
            del App().lightshow.groups[:]
        self.data.import_groups()

    def _do_import_faders(self) -> None:
        if self.actions["faders"] is Action.IGNORE:
            return
        if self.actions["faders"] is Action.REPLACE:
            App().lightshow.fader_bank.reset_faders()
        self.data.import_faders()

    def _do_import_independents(self) -> None:
        if self.actions["independents"] is Action.IGNORE:
            return
        if self.actions["independents"] is Action.REPLACE:
            App().lightshow.independents = Independents()
        self.data.import_independents()

    def _do_import_presets(self) -> None:
        # Presets (Cues not in a sequence) are attached to Main Playback
        if self.actions["sequences"][1] is Action.IGNORE:
            return
        self.data.import_presets()

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
                App().lightshow.main_playback.add_step(step)
                # Main playback at start
                App().lightshow.main_playback.position = 0
            else:
                self.data.import_chaser(sequence, self.actions["sequences"][sequence])

    def _clear_sequence(self, sequence: int) -> None:
        if sequence == 1:
            del App().lightshow.cues[:]
            del App().lightshow.main_playback.steps[1:]
        else:
            chaser = None
            for chsr in App().lightshow.chasers:
                if chsr.index == sequence:
                    chaser = chsr
                    break
                if chaser:
                    App().lightshow.chasers.remove(chaser)

    def _update_ui(self) -> None:
        App().window.live_view.channels_view.update()
        App().tabs.refresh_all()
        subtitle = (f"Mem. : 0.0 - "
                    f"Next Mem. : {App().lightshow.main_playback.steps[1].cue.memory} "
                    f"{App().lightshow.main_playback.steps[1].cue.text}")
        App().window.header.set_subtitle(subtitle)
        App().window.playback.update_xfade_display(0)
        App().window.playback.update_sequence_display()
        # Redraw Mackie LCD
        App().midi.messages.lcd.show_faders()
