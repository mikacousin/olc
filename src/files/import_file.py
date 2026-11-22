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

import pathlib
import typing

from olc.dmx_engine.universe_config import Protocol
from olc.files.ascii.parser import AsciiParser
from olc.files.file_type import FileType
from olc.files.import_types import Action
from olc.files.olc.parser import OlcParser
from olc.files.parsed_data import ParsedData
from olc.show.cue import Cue
from olc.show.independent import Independents
from olc.show.lightshow import default_workspace
from olc.show.step import Step

if typing.TYPE_CHECKING:
    import olc.files.import_file
    from olc.controllers.midi import Midi
    from olc.dmx_engine.universe_config import UniverseMap
    from olc.show.lightshow import LightShow


def _import_single_universe(u: int, val: dict, universe_map: UniverseMap) -> None:
    """Helper to import configuration for a single universe."""
    config = universe_map[u]
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


# pylint: disable=too-many-instance-attributes
class ImportFile:
    """Import file"""

    file: pathlib.Path | str | typing.Any
    file_type: FileType
    data: ParsedData
    actions: dict
    parser: AsciiParser | OlcParser
    window: typing.Any | None
    midi: Midi | None
    settings: typing.Any | None
    tabs: typing.Any | None

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        lightshow: LightShow,
        file: pathlib.Path | str | typing.Any,  # noqa: ANN401
        file_type: FileType,
        window: typing.Any | None = None,  # noqa: ANN401
        midi: Midi | None = None,
        settings: typing.Any | None = None,  # noqa: ANN401
        tabs: typing.Any | None = None,  # noqa: ANN401
        importation: bool = False,
        on_select_data: typing.Callable[[], None] | None = None,
    ) -> None:
        self.lightshow = lightshow
        self.file = file
        self.file_type = file_type
        self.window = window
        self.midi = midi
        self.settings = settings
        self.tabs = tabs
        self.on_select_data = on_select_data
        self.data = ParsedData(self.lightshow, self.midi)
        self.actions = {
            "curves": Action.REPLACE,
            "patch": Action.REPLACE,
            "sequences": {},
            "groups": Action.REPLACE,
            "palettes": Action.REPLACE,
            "effects": Action.REPLACE,
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

    def parse_sync(self, auto_import: bool = True) -> None:
        """Start reading file synchronously.

        Args:
            auto_import: If True, automatically import or prompt via dialog.
                If False, only parse and clean data.
        """
        self.parser.read_sync(auto_import=auto_import)
        self.lightshow.add_recent_file()

    def load_all(self) -> None:
        """Load all file"""
        self.lightshow.title = ""
        self.lightshow.home_preset = None
        if hasattr(self.lightshow, "fader_bank"):
            self.lightshow.fader_bank.reset_faders(reset_page_count=True)
        for sequence in self.data.data["sequences"]:
            self.actions["sequences"][sequence] = Action.REPLACE
        self._do_import()
        self.lightshow.set_not_modified()

    def select_data(self) -> None:
        """Select data to import via UI callback if provided."""
        if self.on_select_data is not None:
            self.on_select_data()
        else:
            self._do_import()
            self.lightshow.set_modified()

    def do_import(self) -> None:
        """Execute the import process."""
        self._do_import()

    def _do_import(self) -> None:
        self.data.import_show_metadata()
        self._do_import_curves()
        if self.file_type is FileType.OLC:
            self._do_import_universes()
        self._do_import_patch()
        self._do_import_palettes()
        self._do_import_effects()
        self._do_import_sequences()
        self._do_import_groups()
        self._do_import_independents()
        self._do_import_presets()
        self._do_import_faders()
        if self.file_type is FileType.OLC:
            self._do_import_midi()
            self._do_import_workspace()
            self._do_import_park()
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
            from olc.devices.builtin import (  # pylint: disable=import-outside-toplevel
                populate_builtin_library,
            )

            self.lightshow.fixture_library = populate_builtin_library()
            self.lightshow.patch.patch_empty()
        # Import patch
        self.data.import_patch()
        app = getattr(self.lightshow, "app", None)
        if app is not None and hasattr(app, "emit"):
            app.emit("fixture_library.changed")
            app.emit("patch.changed")

    def _do_import_groups(self) -> None:
        if self.actions["groups"] is Action.IGNORE:
            return
        if self.actions["groups"] is Action.REPLACE:
            self.lightshow.groups.clear()
        self.data.import_groups()

    def _do_import_palettes(self) -> None:
        palettes_action = self.actions.get("palettes", Action.REPLACE)
        if palettes_action is Action.IGNORE:
            return
        if palettes_action is Action.REPLACE and hasattr(self.lightshow, "palettes"):
            self.lightshow.palettes.clear()
        self.data.import_palettes()

    def _do_import_effects(self) -> None:
        effects_action = self.actions.get("effects", Action.REPLACE)
        if effects_action is Action.IGNORE:
            return
        if effects_action is Action.REPLACE and hasattr(self.lightshow, "effects"):
            self.lightshow.effects.clear()
        self.data.import_effects()

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
            target_seq = None
            for seq_obj in self.lightshow.sequences:
                if seq_obj.index == sequence:
                    target_seq = seq_obj
                    break
            if target_seq:
                self.lightshow.sequences.remove(target_seq)

    def _do_import_midi(self) -> None:
        if self.actions["midi"] is Action.IGNORE:
            return
        if self.actions["midi"] is Action.REPLACE:
            if self.midi:
                self.midi.reset_messages()
        self.data.import_midi()

    def _do_import_workspace(self) -> None:
        workspace = self.data.data.get("workspace")
        self.lightshow.workspace = workspace if workspace else default_workspace()

    def _do_import_universes(self) -> None:
        universes_data = self.data.data.get("universes")
        if not universes_data:
            return

        universe_map = getattr(self.lightshow, "universe_map", None)
        app = self.lightshow.app
        engine = getattr(app, "engine", None) if app is not None else None
        backend = getattr(app, "backend", None) if app is not None else None

        for u_str, val in universes_data.items():
            try:
                u = int(u_str)
            except ValueError:
                continue

            if universe_map is not None:
                if u not in universe_map:
                    universe_map.add_universe(u)
                _import_single_universe(u, val, universe_map)

            if u not in self.lightshow.patch.universes:
                self.lightshow.patch.add_universe(u)

            if backend is not None and getattr(backend, "dmx", None) is not None:
                if u not in backend.dmx.patch.universes:
                    backend.dmx.patch.add_universe(u)
                backend.dmx.add_universe(u)

        if engine is not None and universe_map is not None:
            engine.sync_universe_map(universe_map)

    def _do_import_park(self) -> None:
        park_data = self.data.data.get("park")
        if hasattr(self.lightshow, "park"):
            if park_data:
                is_norm = bool(self.data.data.get("normalized_levels", True))
                self.lightshow.park.from_dict(park_data, normalized=is_norm)
            else:
                self.lightshow.park.clear()
            app = self.lightshow.app
            if app is not None and hasattr(app, "emit"):
                app.emit("park.changed", self.lightshow.park.total_parked_count())

    def _update_ui(self) -> None:
        if self.window is not None and self.window.live_view is not None:
            self.window.live_view.channels_view.update()
        if self.tabs and hasattr(self.tabs, "refresh_all"):
            self.tabs.refresh_all()
        if self.window is not None and self.window.header is not None:
            cue = self.lightshow.main_playback.steps[1].cue
            number = cue.number if cue is not None else 0.0
            text = cue.text if cue is not None else ""
            subtitle = f"Cue : 0.0 - Next Cue : {number} {text}"
            self.window.header.set_subtitle(subtitle)
        if self.window is not None and self.window.playback is not None:
            self.window.playback.update_xfade_display(0)
            self.window.playback.update_sequence_display()
