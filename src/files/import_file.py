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

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.core.universe_config import Protocol  # noqa: E402
from olc.cue import Cue  # noqa: E402
from olc.files.ascii.parser import AsciiParser  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_dialog import Action, DialogData  # noqa: E402
from olc.files.olc.parser import OlcParser  # noqa: E402
from olc.files.parsed_data import ParsedData  # noqa: E402
from olc.independent import Independents  # noqa: E402
from olc.step import Step  # noqa: E402

if typing.TYPE_CHECKING:
    import olc.files.import_file
    from gi.repository import Gio
    from olc.core.engine import CoreEngine
    from olc.core.lightshow import LightShow
    from olc.midi import Midi
    from olc.tabs_manager import Tabs
    from olc.window import Window


def _import_single_universe(u: int, val: dict, engine: CoreEngine) -> None:
    """Helper to import configuration for a single universe."""
    config = engine.universe_map[u]
    protocols_set = set()
    for p_name in val.get("protocols", []):
        if p_name == "ARTNET":
            protocols_set.add(Protocol.ARTNET)
        elif p_name == "SACN" and u != 0:
            protocols_set.add(Protocol.SACN)
        elif p_name == "DMX_USB_PRO":
            protocols_set.add(Protocol.DMX_USB_PRO)
    config.set_protocols(protocols_set)

    if "artnet" in val:
        artnet_val = val["artnet"]
        config.artnet.net = artnet_val.get("net", 0)
        config.artnet.sub = artnet_val.get("sub", 0)
        config.artnet.sync_active = artnet_val.get("sync_active", False)

    if "sacn" in val:
        sacn_val = val["sacn"]
        config.sacn.priority = sacn_val.get("priority", 100)
        config.sacn.sync_address = sacn_val.get("sync_address", 0)

    if "dmx_usb_pro" in val:
        dmx_usb_pro_val = val["dmx_usb_pro"]
        config.dmx_usb_pro.port = dmx_usb_pro_val.get("port", "Auto-detect")
        config.dmx_usb_pro.port_index = dmx_usb_pro_val.get("port_index", 1)
        config.dmx_usb_pro.model = dmx_usb_pro_val.get("model", "Auto-detect")

    # Hot-reload sender registry for this universe
    engine.reload_universe(u)


# pylint: disable=too-many-instance-attributes
class ImportFile:
    """Import file"""

    file: Gio.File
    file_type: FileType
    data: ParsedData
    actions: dict
    parser: AsciiParser | OlcParser
    window: Window | None
    midi: Midi | None
    settings: Gio.Settings | None
    tabs: Tabs | None

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        lightshow: LightShow,
        file: Gio.File,
        file_type: FileType,
        window: Window | None = None,
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
                typing.cast("olc.files.import_file.ImportFile", self),
                default_time,
                importation=importation,
            )
        else:
            self.parser = OlcParser(
                typing.cast("olc.files.import_file.ImportFile", self),
                window=self.window,
                importation=importation,
            )

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
            self._do_import_universes()
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
            self.lightshow.groups.clear()
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
            self.lightshow.cues.clear()
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

    def _do_import_universes(self) -> None:
        universes_data = self.data.data.get("universes")
        if not universes_data:
            return

        if self.lightshow.app is None:
            return
        engine = self.lightshow.app.engine
        if engine is None:
            return

        for u_str, val in universes_data.items():
            try:
                u = int(u_str)
            except ValueError:
                continue
            if u not in engine.universe_map:
                continue

            _import_single_universe(u, val, engine)

    def _update_ui(self) -> None:
        if self.window is not None and self.window.live_view is not None:
            self.window.live_view.channels_view.update()
        if self.tabs:
            self.tabs.refresh_all()
        if self.window is not None and self.window.header is not None:
            cue = self.lightshow.main_playback.steps[1].cue
            number = cue.number if cue is not None else 0.0
            text = cue.text if cue is not None else ""
            subtitle = f"Mem. : 0.0 - Next Mem. : {number} {text}"
            self.window.header.set_subtitle(subtitle)
        if self.window is not None and self.window.playback is not None:
            self.window.playback.update_xfade_display(0)
            self.window.playback.update_sequence_display()
        # Redraw Mackie LCD
        if self.midi and self.midi.messages and self.midi.messages.lcd:
            self.midi.messages.lcd.show_faders()
