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
"""Actions for show life cycle and file management."""

from __future__ import annotations

import copy
import os
import pathlib
import typing
from gettext import gettext as _

from olc.core.action import Action
from olc.define import MAX_FADER_PAGE, MAX_FADER_PER_PAGE
from olc.devices.builtin import populate_builtin_library
from olc.devices.device import LightingDevice
from olc.devices.fixture import FixtureDefinition
from olc.dmx_engine.universe_config import default_universe_map
from olc.files.export_file import ExportFile
from olc.files.file_type import FileType
from olc.files.import_file import ImportFile
from olc.files.import_types import Action as ImportAction
from olc.show.cue import Cue
from olc.show.fader import FaderType
from olc.show.group import Group
from olc.show.independent import Independents
from olc.show.lightshow import default_workspace
from olc.show.sequence import Sequence
from olc.show.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.lightshow import LightShow


class ShowNewAction(Action):
    """Action to reset and create a new blank show."""

    name = "show.new"
    can_undo = False

    def execute(self) -> None:
        """Reset all show data to default empty state and clear history."""
        lightshow = self.app.lightshow

        # Stop running effects and clear secondary sequences
        if hasattr(self.app, "effects_engine"):
            self.app.effects_engine.stop_all()
        if hasattr(lightshow, "effects"):
            lightshow.effects.clear()
        if hasattr(self.app, "playback_engine"):
            self.app.playback_engine.clear()
        if lightshow.main_playback is not None:
            lightshow.main_playback.stop()
        for seq in list(lightshow.sequences):
            seq.stop()
        del lightshow.sequences[:]

        # Reset groups and palettes
        lightshow.groups.clear()
        if hasattr(lightshow, "palettes"):
            lightshow.palettes.clear()

        # Reset user curves
        if hasattr(lightshow, "curves"):
            lightshow.curves.reset()

        # Reset fader bank
        if hasattr(lightshow, "fader_bank"):
            lightshow.fader_bank.reset_faders(reset_page_count=True)

        # Reset independents
        lightshow.independents = Independents(lightshow)

        # Reset fixture library, patch (empty), and universe configurations
        lightshow.fixture_library = populate_builtin_library()
        lightshow.patch.patch_empty()
        lightshow.universe_map = default_universe_map()
        if self.app.engine is not None:
            self.app.engine.sync_universe_map(lightshow.universe_map)

        # Reset park
        if hasattr(lightshow, "park"):
            lightshow.park.clear()
            self.app.emit("park.changed", 0)

        # Reset main playback
        lightshow.main_playback = Sequence(1, text="", lightshow=lightshow)
        lightshow.main_playback.position = 0
        lightshow.main_playback.update_channels()

        # Reset DMX levels and live parameter state
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            backend.dmx.reset_levels()
        if hasattr(self.app, "live_state"):
            self.app.live_state.clear_all()

        # Clear channel selection
        if hasattr(self.app, "live_selection"):
            self.app.live_selection.selected_channels = []
            self.app.live_selection.last_selected_channel = None

        # Reset file metadata
        lightshow.file = None
        lightshow.file_path = None
        lightshow.basename = ""
        lightshow.title = ""
        lightshow.home_preset = None
        lightshow.set_not_modified()

        # Reset workspace state to default
        lightshow.workspace = default_workspace()
        if hasattr(self.app, "tabs") and hasattr(self.app.tabs, "reset"):
            self.app.tabs.reset()

        # Clear undo/redo history
        self.app.history.clear()

        # Emit event
        self.app.emit("show.home_preset_changed", None)
        if hasattr(lightshow, "fader_bank"):
            self.app.emit(
                "fader.page_count_changed", lightshow.fader_bank.max_fader_page
            )
            self.app.emit("fader.skip_empty_pages_changed", False)
        self.app.emit("show.new")


class ShowResetUserLevelsAction(Action):
    """Action to clear manual user channel overrides with Undo/Redo."""

    name = "show.reset_user_levels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_levels: dict[int, float] = {}
        self._old_live_state: dict[int, typing.Any] = {}

    def execute(self) -> None:
        """Reset all manual user channel overrides to -1.0."""
        self.old_levels = {}
        if hasattr(self.app, "live_state"):
            self._old_live_state = self.app.live_state.snapshot_all()
            self.app.live_state.clear_all()
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels["user"]
            for idx, lvl in enumerate(user_levels):
                if lvl >= 0.0:
                    self.old_levels[idx + 1] = float(lvl)
            user_levels.fill(-1.0)
            engine = getattr(self.app, "playback_engine", None)
            main_pb = (
                engine.main_sequence
                if engine is not None and engine.main_sequence is not None
                else self.app.lightshow.main_playback
            )
            main_pb.update_channels()
            backend.dmx.set_levels()

        for ch in self.old_levels:
            self.app.emit("channel.level_changed", ch, -1.0)
        self.app.emit("show.user_levels_reset")

    def undo(self) -> None:
        """Restore previous manual user channel levels."""
        if hasattr(self.app, "live_state"):
            self.app.live_state.restore_all(self._old_live_state)
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels["user"]
            for ch, lvl in self.old_levels.items():
                if 1 <= ch <= len(user_levels):
                    user_levels[ch - 1] = lvl
            engine = getattr(self.app, "playback_engine", None)
            main_pb = (
                engine.main_sequence
                if engine is not None and engine.main_sequence is not None
                else self.app.lightshow.main_playback
            )
            main_pb.update_channels()
            backend.dmx.set_levels()

        for ch, lvl in self.old_levels.items():
            self.app.emit("channel.level_changed", ch, lvl)
        self.app.emit("show.user_levels_restored")

    def redo(self) -> None:
        """Re-apply user levels reset."""
        self.execute()


class ShowOpenAction(Action):
    """Action to open and load a show file."""

    name = "show.open"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.file_path: str = ""

    def configure(self, file_path: str) -> None:
        """Configure the action with target file path.

        Args:
            file_path: Absolute or relative path to the show file.
        """
        self.file_path = file_path

    def execute(self) -> None:
        """Load show from file and clear history."""
        if not self.file_path:
            raise ValueError("No file path specified for show.open")

        path = os.path.abspath(self.file_path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        ext = "".join([s for s in pathlib.Path(path).suffixes if " " not in s]).lower()
        file_type = FileType.ASCII if ext == ".asc" else FileType.OLC

        file_path_obj = pathlib.Path(path)
        lightshow = self.app.lightshow
        lightshow.file = file_path_obj
        lightshow.file_path = path
        lightshow.basename = os.path.basename(path)
        lightshow.title = ""
        lightshow.home_preset = None

        imported = ImportFile(
            lightshow,
            file_path_obj,
            file_type,
            midi=getattr(self.app, "midi", None),
            settings=getattr(self.app, "settings", None),
        )
        imported.parse_sync()

        # Reset DMX levels and live parameter state
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            backend.dmx.reset_levels()
        if hasattr(self.app, "live_state"):
            self.app.live_state.clear_all()

        # Clear channel selection
        if hasattr(self.app, "live_selection"):
            self.app.live_selection.selected_channels = []
            self.app.live_selection.last_selected_channel = None

        # Clear history
        self.app.history.clear()

        # Emit event
        self.app.emit("show.loaded", path)


class ShowSaveAction(Action):
    """Action to save current show to an OLC file."""

    name = "show.save"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.file_path: str | None = None

    def configure(self, file_path: str | None = None) -> None:
        """Configure the action with target file path.

        Args:
            file_path: Optional path to save to. Defaults to current show file path.
        """
        self.file_path = file_path

    def execute(self) -> None:
        """Save show to OLC file."""
        target_path = self.file_path or self.app.lightshow.file_path
        if not target_path:
            raise ValueError("No file path specified for show.save")

        path = os.path.abspath(target_path)
        file_path_obj = pathlib.Path(path)
        lightshow = self.app.lightshow
        lightshow.file = file_path_obj
        lightshow.file_path = path
        lightshow.basename = os.path.basename(path)

        # Request workspace state synchronization before export
        self.app.emit("show.before_save")

        exported = ExportFile(
            file_path_obj,
            FileType.OLC,
            lightshow,
            midi=getattr(self.app, "midi", None),
        )
        exported.write()
        lightshow.set_not_modified()
        lightshow.add_recent_file()

        self.app.emit("show.saved", path)


class ShowExportAsciiAction(Action):
    """Action to export current show to USITT ASCII format."""

    name = "show.export_ascii"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.file_path: str = ""

    def configure(self, file_path: str) -> None:
        """Configure the action with target file path.

        Args:
            file_path: Path to export the ASCII file to.
        """
        self.file_path = file_path

    def execute(self) -> None:
        """Export show to USITT ASCII file."""
        if not self.file_path:
            raise ValueError("No file path specified for show.export_ascii")

        path = os.path.abspath(self.file_path)
        exported = ExportFile(
            pathlib.Path(path),
            FileType.ASCII,
            self.app.lightshow,
        )
        exported.write()

        self.app.emit("show.exported", path, "ascii")


def _copy_cue(cue: Cue | None) -> Cue | None:
    """Create a copy of a Cue object.

    Args:
        cue: Source Cue to copy.

    Returns:
        Copied Cue or None.
    """
    if cue is None:
        return None
    copied = Cue(
        sequence=cue.sequence,
        number=cue.number,
        channels=dict(cue.channels),
        text=cue.text,
    )
    copied.device_values = copy.deepcopy(cue.device_values)
    copied.palette_refs = copy.deepcopy(cue.palette_refs)
    copied.effect_refs = copy.deepcopy(getattr(cue, "effect_refs", {}))
    copied.is_block = bool(cue.is_block)
    return copied


def _copy_step(step: Step) -> Step:
    """Create a deep copy of a Step object.

    Args:
        step: Source Step to copy.

    Returns:
        Copied Step object.
    """
    channel_time = copy.deepcopy(step.channel_time)
    return Step(
        sequence=step.sequence,
        cue=_copy_cue(step.cue),
        time_in=step.time_in,
        time_out=step.time_out,
        delay_in=step.delay_in,
        delay_out=step.delay_out,
        wait=step.wait,
        channel_time=channel_time,
        text=step.text,
        time_position=step.time_position,
        delay_position=step.delay_position,
        time_color=step.time_color,
        delay_color=step.delay_color,
        time_beam=step.time_beam,
        delay_beam=step.delay_beam,
    )


def _copy_sequence(seq: Sequence, lightshow: LightShow) -> Sequence:
    """Create a copy of a Sequence object for snapshot.

    Args:
        seq: Source sequence.
        lightshow: Parent LightShow reference.

    Returns:
        Copied Sequence.
    """
    copied = Sequence(
        seq.index,
        type_seq=seq.type_seq,
        text=seq.text,
        lightshow=lightshow,
    )
    copied.steps = [_copy_step(s) for s in seq.steps]
    copied.position = seq.position
    copied.last = seq.last
    copied.channels = set(seq.channels)
    copied.tracking_mode = bool(getattr(seq, "tracking_mode", False))
    copied.mib_enabled = bool(getattr(seq, "mib_enabled", True))
    copied.mib_fade_time = float(getattr(seq, "mib_fade_time", 2.0))
    return copied


def _normalize_action(act: ImportAction | str | object) -> ImportAction:
    """Convert string or action to an ImportAction.

    Args:
        act: String name or action value.

    Returns:
        Corresponding ImportAction member.
    """
    if isinstance(act, ImportAction):
        return act
    if isinstance(act, str):
        act_upper = act.upper()
        if act_upper == "MERGE":
            return ImportAction.MERGE
        if act_upper == "IGNORE":
            return ImportAction.IGNORE
        if act_upper == "REPLACE":
            return ImportAction.REPLACE
    return ImportAction.REPLACE


def _apply_import_options(
    imported: ImportFile, options: dict[str, typing.Any] | None
) -> None:
    """Apply user import options to the ImportFile actions mapping.

    Args:
        imported: Target ImportFile instance.
        options: Dictionary specifying import actions for sections.
    """
    for key in (
        "curves",
        "patch",
        "groups",
        "palettes",
        "effects",
        "independents",
        "faders",
        "midi",
    ):
        if options and key in options:
            imported.actions[key] = _normalize_action(options[key])
        else:
            imported.actions[key] = ImportAction.REPLACE

    imported.actions["sequences"] = {}
    sequences_data = imported.data.data.get("sequences", {})
    seq_options = options.get("sequences") if options else None
    for seq in sequences_data:
        if isinstance(seq_options, dict) and seq in seq_options:
            imported.actions["sequences"][seq] = _normalize_action(seq_options[seq])
        elif seq_options is not None and not isinstance(seq_options, dict):
            imported.actions["sequences"][seq] = _normalize_action(seq_options)
        else:
            imported.actions["sequences"][seq] = ImportAction.REPLACE


class ShowImportAction(Action):
    """Action to import data from a file into current show with Undo/Redo."""

    name = "show.import"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.file_path: str = ""
        self.options: dict[str, typing.Any] | None = None
        self._snapshot: dict[str, typing.Any] | None = None

    def configure(
        self,
        file_path: str,
        options: dict[str, typing.Any] | None = None,
    ) -> None:
        """Configure the action with target file path and import options.

        Args:
            file_path: Path to the file to import.
            options: Dictionary specifying import actions for sections.
        """
        self.file_path = file_path
        self.options = options

    def execute(self) -> None:
        """Execute the import operation."""
        if not self.file_path:
            raise ValueError("No file path specified for show.import")

        path = os.path.abspath(self.file_path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        # Take snapshot before modifying lightshow if not already taken
        if self._snapshot is None:
            self._snapshot = self._take_snapshot()

        ext = "".join([s for s in pathlib.Path(path).suffixes if " " not in s]).lower()
        file_type = FileType.ASCII if ext == ".asc" else FileType.OLC

        file_path_obj = pathlib.Path(path)
        lightshow = self.app.lightshow

        imported = ImportFile(
            lightshow,
            file_path_obj,
            file_type,
            midi=getattr(self.app, "midi", None),
            settings=getattr(self.app, "settings", None),
            importation=True,
        )
        imported.parse_sync(auto_import=False)
        _apply_import_options(imported, self.options)

        # Execute import
        imported.do_import()
        lightshow.set_modified()

        # Update backend DMX
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            backend.dmx.set_levels()

        self.app.emit("show.imported", path, self.options)

    def undo(self) -> None:
        """Undo the import operation."""
        self._restore_snapshot()

    def redo(self) -> None:
        """Redo the import operation."""
        self.execute()

    def _take_snapshot(self) -> dict[str, typing.Any]:
        """Capture the current state of all importable structures."""
        lightshow = self.app.lightshow
        snapshot: dict[str, typing.Any] = {}

        # 1. Curves
        if hasattr(lightshow, "curves"):
            snapshot["curves"] = dict(lightshow.curves.curves)

        # 2. Fixture library & Patch
        if hasattr(lightshow, "fixture_library"):
            snapshot["fixture_definitions"] = [
                fdef.to_dict() for fdef in lightshow.fixture_library.all()
            ]
        snapshot["patch_devices"] = {
            dev_id: dev.to_dict() for dev_id, dev in lightshow.patch.devices.items()
        }
        if hasattr(lightshow, "universe_map"):
            snapshot["universe_map"] = copy.deepcopy(lightshow.universe_map)

        # 3. Groups and Palettes
        snapshot["groups"] = [
            Group(g.index, channels=list(g.channels), text=g.text)
            for g in lightshow.groups
        ]
        if hasattr(lightshow, "palettes"):
            snapshot["palettes"] = lightshow.palettes.to_dict()

        # 4. Main playback
        mp = lightshow.main_playback
        snapshot["main_playback_steps"] = [_copy_step(s) for s in mp.steps]
        snapshot["main_playback_position"] = mp.position
        snapshot["main_playback_last"] = mp.last
        snapshot["main_playback_tracking_mode"] = bool(
            getattr(mp, "tracking_mode", False)
        )

        # 6. Secondary sequences and effects
        snapshot["sequences"] = [
            _copy_sequence(s, lightshow) for s in lightshow.sequences
        ]
        if hasattr(lightshow, "effects"):
            snapshot["effects"] = lightshow.effects.to_list()

        # 7. Independents
        snapshot["independents"] = [
            (inde.number, inde.text, dict(inde.levels), inde.inde_type, inde.level)
            for inde in lightshow.independents.independents
        ]

        # 8. Faders
        faders_data: dict[tuple[int, int], tuple[FaderType, typing.Any, float]] = {}
        if hasattr(lightshow, "fader_bank"):
            fb = lightshow.fader_bank
            snapshot["fader_max_page"] = fb.max_fader_page
            snapshot["fader_skip_empty_pages"] = bool(
                getattr(fb, "skip_empty_pages", False)
            )
            snapshot["fixed_faders"] = dict(getattr(fb, "fixed_faders", {}))
            for page in range(1, fb.max_fader_page + 1):
                for idx in range(1, MAX_FADER_PER_PAGE + 1):
                    fader = fb.faders[page][idx]
                    ftype = fb.get_fader_type(page, idx)
                    contents = getattr(fader, "contents", None)
                    contents_id = None
                    if contents is not None:
                        if hasattr(contents, "index"):
                            contents_id = contents.index
                        elif hasattr(contents, "number"):
                            contents_id = contents.number
                        elif isinstance(contents, dict):
                            contents_id = dict(contents)
                    faders_data[(page, idx)] = (ftype, contents_id, fader.level)
        snapshot["faders"] = faders_data

        # 9. Show metadata and modified state
        snapshot["title"] = getattr(lightshow, "title", "")
        snapshot["home_preset"] = getattr(lightshow, "home_preset", None)
        snapshot["modified"] = bool(lightshow.modified)

        return snapshot

    def _restore_curves_and_patch(
        self, snapshot: dict[str, typing.Any], lightshow: LightShow
    ) -> None:
        """Restore curves, fixture definitions, and patch from snapshot."""
        if "curves" in snapshot and hasattr(lightshow, "curves"):
            lightshow.curves.curves = dict(snapshot["curves"])

        if "fixture_definitions" in snapshot and hasattr(lightshow, "fixture_library"):
            lightshow.fixture_library = populate_builtin_library()
            for fd in snapshot["fixture_definitions"]:
                lightshow.fixture_library.register(FixtureDefinition.from_dict(fd))

        lightshow.patch.patch_empty()
        for dev_dict in snapshot.get("patch_devices", {}).values():
            dev = LightingDevice.from_dict(dev_dict)
            lightshow.patch.restore_device(dev)

        lightshow.patch.invalidate_cache()
        if "universe_map" in snapshot:
            lightshow.universe_map = copy.deepcopy(snapshot["universe_map"])
            if self.app.engine is not None:
                self.app.engine.sync_universe_map(lightshow.universe_map)

    def _restore_groups_and_palettes(
        self, snapshot: dict[str, typing.Any], lightshow: LightShow
    ) -> None:
        """Restore groups and palettes from snapshot."""
        lightshow.groups.clear()
        for g in snapshot["groups"]:
            lightshow.groups.add(Group(g.index, channels=list(g.channels), text=g.text))

        if "palettes" in snapshot and hasattr(lightshow, "palettes"):
            lightshow.palettes.from_dict(snapshot["palettes"])

    def _restore_playbacks(
        self,
        snapshot: dict[str, typing.Any],
        lightshow: LightShow,
    ) -> None:
        """Restore main playback and chasers from snapshot."""
        mp = lightshow.main_playback
        mp.steps = [_copy_step(s) for s in snapshot["main_playback_steps"]]
        mp.position = snapshot["main_playback_position"]
        mp.last = snapshot["main_playback_last"]
        mp.tracking_mode = bool(snapshot.get("main_playback_tracking_mode", False))
        mp.update_channels()

        if hasattr(self.app, "playback_engine"):
            self.app.playback_engine.clear()
        for seq in list(lightshow.sequences):
            seq.stop()
        del lightshow.sequences[:]
        for seq in snapshot["sequences"]:
            lightshow.sequences.append(_copy_sequence(seq, lightshow))
        if "effects" in snapshot and hasattr(lightshow, "effects"):
            lightshow.effects.from_list(snapshot["effects"])

    def _restore_independents_and_faders(
        self, snapshot: dict[str, typing.Any], lightshow: LightShow
    ) -> None:
        """Restore independents and faders from snapshot."""
        for num, text, levels, inde_type, level in snapshot["independents"]:
            if 1 <= num <= len(lightshow.independents.independents):
                inde = lightshow.independents.independents[num - 1]
                inde.text = text
                inde.inde_type = inde_type
                inde.set_levels(dict(levels))
                inde.set_level(level)
        lightshow.independents.update_channels()
        lightshow.independents.update_dmx()

        if hasattr(lightshow, "fader_bank"):
            fb = lightshow.fader_bank
            fb.reset_faders()
            target_pages = snapshot.get("fader_max_page", MAX_FADER_PAGE)
            fb.set_max_pages(target_pages)
            fb.skip_empty_pages = bool(snapshot.get("fader_skip_empty_pages", False))
            for (page, idx), (ftype, contents_id, level) in snapshot["faders"].items():
                if page > fb.max_fader_page:
                    fb.set_max_pages(page)
                if ftype != FaderType.NONE:
                    fb.set_fader(page, idx, ftype, contents_id)
                    fb.faders[page][idx].set_level(level)
            fb.update_active_faders()
            fb.fixed_faders = {
                int(k): int(v)
                for k, v in snapshot.get("fixed_faders", {}).items()
                if 1 <= int(v) <= fb.max_fader_page
            }
            fb.update_levels()

    def _restore_snapshot(self) -> None:
        """Restore all importable structures from snapshot."""
        if self._snapshot is None:
            return

        lightshow = self.app.lightshow
        self._restore_curves_and_patch(self._snapshot, lightshow)
        self._restore_groups_and_palettes(self._snapshot, lightshow)
        self._restore_playbacks(self._snapshot, lightshow)
        self._restore_independents_and_faders(self._snapshot, lightshow)
        lightshow.title = self._snapshot.get("title", "")
        lightshow.home_preset = self._snapshot.get("home_preset", None)

        # Restore modified state
        if self._snapshot["modified"]:
            lightshow.set_modified()
        else:
            lightshow.set_not_modified()

        # Update backend DMX
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            backend.dmx.set_levels()

        # Emit imported event to trigger GUI refresh
        self.app.emit("show.imported", self.file_path, self.options)


class ShowSetHomePresetAction(Action):
    """Action to configure the show's Home Preset number with Undo/Redo."""

    name = "show.set_home_preset"
    history_label = _("Set Home Preset")
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.preset_number: float | None = None
        self.old_home_preset: float | None = None
        self.old_modified: bool = False

    def configure(self, preset_number: float | None = None) -> None:
        """Configure target Home Preset number, or None / <= 0 to clear."""
        if preset_number is None or float(preset_number) <= 0.0:
            self.preset_number = None
        else:
            self.preset_number = round(float(preset_number), 4)

    def get_history_details(self) -> str:
        """Return formatted Home Preset number or None label for history."""
        if self.preset_number is None:
            return _("None")
        if self.preset_number.is_integer():
            return str(int(self.preset_number))
        return str(self.preset_number)

    def execute(self) -> None:
        """Update lightshow.home_preset and notify listeners."""
        lightshow = self.app.lightshow
        self.old_home_preset = getattr(lightshow, "home_preset", None)
        self.old_modified = bool(getattr(lightshow, "modified", False))
        if self.old_home_preset == self.preset_number:
            self.can_undo = False
            return
        lightshow.home_preset = self.preset_number
        lightshow.set_modified()
        self.app.emit("show.home_preset_changed", self.preset_number)

    def undo(self) -> None:
        """Restore previous Home Preset number."""
        lightshow = self.app.lightshow
        lightshow.home_preset = self.old_home_preset
        if self.old_modified:
            lightshow.set_modified()
        else:
            lightshow.set_not_modified()
        self.app.emit("show.home_preset_changed", self.old_home_preset)

    def redo(self) -> None:
        """Re-apply new Home Preset number."""
        lightshow = self.app.lightshow
        lightshow.home_preset = self.preset_number
        lightshow.set_modified()
        self.app.emit("show.home_preset_changed", self.preset_number)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return Home Preset state metadata."""
        return {"home_preset": self.preset_number}
