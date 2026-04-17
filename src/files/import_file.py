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
import typing

from gi.repository import Gtk
from olc.cue import Cue
from olc.files.ascii.parser import AsciiParser
from olc.files.file_type import FileType
from olc.files.import_dialog import Action, DialogData
from olc.files.olc.parser import OlcParser
from olc.files.parsed_data import ParsedData
from olc.independent import Independents
from olc.step import Step

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.lightshow import LightShow
    from olc.midi import Midi
    from olc.tabs_manager import Tabs


# pylint: disable=too-many-instance-attributes
class ImportFile:
    """Import file"""

    file: Gio.File
    file_type: FileType
    data: ParsedData
    actions: dict
    parser: AsciiParser | OlcParser
    window: Gtk.Window | None
    midi: Midi | None
    settings: Gio.Settings | None
    tabs: Tabs | None

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        lightshow: LightShow,
        file: Gio.File,
        file_type: FileType,
        window: Gtk.Window | None = None,
        midi: Midi | None = None,
        settings: Gio.Settings | None = None,
        tabs: Tabs | None = None,
        importation: bool = False,
    ) -> None:
        self.lightshow = lightshow
        self.file = file
        self.file_type = file_type
        self.window = window
        self.midi = midi
        self.settings = settings
        self.tabs = tabs
        self.data = ParsedData(self.lightshow, self.midi)
        self.actions = {
            "curves": Action.REPLACE,
            "patch": Action.REPLACE,
            "sequences": {},
            "groups": Action.REPLACE,
            "independents": Action.REPLACE,
            "faders": Action.REPLACE,
            "midi": Action.REPLACE,
        }

        if self.file_type is FileType.ASCII:
            if self.settings:
                default_time = self.settings.get_double("default-time")
            else:
                default_time = 5.0
            self.parser = AsciiParser(
                self,
                self.lightshow,
                default_time,
                window=self.window,
                importation=importation,
            )
        else:
            self.parser = OlcParser(self, window=self.window, importation=importation)

    def parse(self) -> None:
        """Start reading file"""
        self.parser.read()
        self.lightshow.add_recent_file()

    def load_all(self) -> None:
        """Load all file"""
        for sequence in self.data.data["sequences"]:
            self.actions["sequences"][sequence] = Action.REPLACE
        self._do_import()
        self.lightshow.set_not_modified()

    def select_data(self) -> None:
        """Select data to import"""
        if self.window:
            dialog = DialogData(self.window, self.data.data, self.actions)
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.OK:
                self._do_import()
                self.lightshow.set_modified()

    def _do_import(self) -> None:
        self._do_import_curves()
        self._do_import_patch()
        self._do_import_sequences()
        self._do_import_groups()
        self._do_import_independents()
        self._do_import_presets()
        self._do_import_faders()
        if self.file_type is FileType.OLC:
            self._do_import_midi()
        self._update_ui()

    def _do_import_curves(self) -> None:
        if self.actions["curves"] is Action.IGNORE:
            return
        if self.actions["curves"] is Action.REPLACE:
            self.lightshow.curves.reset()
        self.data.import_curves()

    def _do_import_patch(self) -> None:
        if self.actions["patch"] is Action.IGNORE:
            return
        if self.actions["patch"] is Action.REPLACE:
            self.lightshow.patch.patch_empty()
        # Import patch
        self.data.import_patch()

    def _do_import_groups(self) -> None:
        if self.actions["groups"] is Action.IGNORE:
            return
        if self.actions["groups"] is Action.REPLACE:
            del self.lightshow.groups[:]
        self.data.import_groups()

    def _do_import_faders(self) -> None:
        if self.actions["faders"] is Action.IGNORE:
            return
        if self.actions["faders"] is Action.REPLACE:
            self.lightshow.fader_bank.reset_faders()
        self.data.import_faders(self.actions)

    def _do_import_independents(self) -> None:
        if self.actions["independents"] is Action.IGNORE:
            return
        if self.actions["independents"] is Action.REPLACE:
            self.lightshow.independents = Independents()
        self.data.import_independents()

    def _do_import_presets(self) -> None:
        # Presets (Cues not in a sequence) are attached to Main Playback
        if self.actions["sequences"].get(1) is Action.IGNORE:
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
                self.data.import_main_playback(
                    sequence, self.actions["sequences"][sequence]
                )
                # Add empty step at the end
                cue = Cue(0, 0.0)
                step = Step(sequence, cue=cue)
                self.lightshow.main_playback.add_step(step)
                # Main playback at start
                self.lightshow.main_playback.position = 0
            else:
                self.data.import_chaser(sequence, self.actions["sequences"][sequence])

    def _clear_sequence(self, sequence: int) -> None:
        if sequence == 1:
            del self.lightshow.cues[:]
            del self.lightshow.main_playback.steps[1:]
        else:
            chaser = None
            for chsr in self.lightshow.chasers:
                if chsr.index == sequence:
                    chaser = chsr
                    break
                if chaser:
                    self.lightshow.chasers.remove(chaser)

    def _do_import_midi(self) -> None:
        if self.actions["midi"] is Action.IGNORE:
            return
        if self.actions["midi"] is Action.REPLACE:
            if self.midi:
                self.midi.reset_messages()
        self.data.import_midi()

    def _update_ui(self) -> None:
        if self.window and self.window.live_view:
            self.window.live_view.channels_view.update()
        if self.tabs:
            self.tabs.refresh_all()
        if self.window and self.window.header:
            subtitle = (
                f"Mem. : 0.0 - "
                f"Next Mem. : {self.lightshow.main_playback.steps[1].cue.memory} "
                f"{self.lightshow.main_playback.steps[1].cue.text}"
            )
            self.window.header.set_subtitle(subtitle)
        if self.window and self.window.playback:
            self.window.playback.update_xfade_display(0)
            self.window.playback.update_sequence_display()
        # Redraw Mackie LCD
        if self.midi and self.midi.messages and self.midi.messages.lcd:
            self.midi.messages.lcd.show_faders()
