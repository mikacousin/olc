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
from abc import ABC, abstractmethod
from gettext import gettext as _

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


_DEFAULT_HISTORY_LABELS: dict[str, str] = {
    "address.park": _("Park DMX address"),
    "address.unpark": _("Unpark DMX address"),
    "channel.level_minus": _("Decrease level (-%)"),
    "channel.level_plus": _("Increase level (+%)"),
    "channel.park": _("Park channel"),
    "channel.select_active": _("Select active channel"),
    "channel.select_add": _("Add channels to selection"),
    "channel.select_all": _("Select all channels"),
    "channel.select_channels": _("Select channels"),
    "channel.select_next": _("Select next channel"),
    "channel.select_none": _("Clear channel selection"),
    "channel.select_previous": _("Select previous channel"),
    "channel.select_remove": _("Remove channels from selection"),
    "channel.select_thru": _("Select channel range"),
    "channel.set_level": _("Set channel level"),
    "channel.set_level_from_cmd": _("Set level"),
    "channel.set_multi_levels": _("Set channels level"),
    "channel.unpark": _("Unpark channel"),
    "channel.wheel_adjust": _("Adjust channel level"),
    "cue.copy": _("Copy cue"),
    "cue.delete": _("Delete cue"),
    "cue.insert": _("Insert cue"),
    "cue.rename": _("Rename cue"),
    "cue.select": _("Select cue"),
    "cue.set_block": _("Toggle cue block"),
    "cue.set_channel_level": _("Edit cue channel level"),
    "cue.set_temp_channels": _("Edit cue channels"),
    "cue.update": _("Update cue"),
    "curve.delete": _("Delete curve"),
    "curve.new": _("Create curve"),
    "curve.rename": _("Rename curve"),
    "curve.set_limit": _("Set curve limit"),
    "curve.update_points": _("Edit curve points"),
    "device.adjust_pan_tilt": _("Adjust Pan/Tilt"),
    "device.adjust_parameter": _("Adjust fixture parameter"),
    "device.home": _("Home fixture"),
    "device.locate": _("Locate fixture"),
    "device.set_color": _("Set fixture color"),
    "device.set_pan_tilt": _("Set Pan/Tilt"),
    "device.set_parameter": _("Set fixture parameter"),
    "dmx.blackout_all": _("Toggle blackout all"),
    "dmx.clear_user_outputs": _("Clear user DMX outputs"),
    "dmx.test_output": _("Test DMX output"),
    "fader.assign": _("Assign fader"),
    "fader.clear": _("Clear fader"),
    "fixture.delete": _("Delete fixture profile"),
    "fixture.import_gdtf": _("Import GDTF fixture"),
    "fixture.upsert": _("Save fixture profile"),
    "group.delete": _("Delete group"),
    "group.new": _("Create group"),
    "group.rename": _("Rename group"),
    "group.select": _("Select group"),
    "group.update_channels": _("Update group channels"),
    "independent.change_type": _("Change independent type"),
    "independent.rename": _("Rename independent"),
    "independent.update_channels": _("Update independent channels"),
    "main_fader.set_level": _("Set Grand Master"),
    "midi.assign_mapping": _("Assign MIDI mapping"),
    "midi.clear_mappings": _("Clear MIDI mappings"),
    "midi.port_toggle": _("Toggle MIDI port"),
    "midi.set_port_mode": _("Set MIDI port mode"),
    "osc.set_config": _("Update OSC settings"),
    "osc.toggle": _("Toggle OSC"),
    "osc.toggle_static_client": _("Toggle OSC client"),
    "palette.apply": _("Apply palette"),
    "palette.delete": _("Delete palette"),
    "palette.record": _("Record palette"),
    "palette.rename": _("Rename palette"),
    "palette.update": _("Update palette"),
    "park.unpark_all": _("Unpark all"),
    "playback.record_cue": _("Record cue"),
    "playback.update_active_step": _("Update active cue"),
    "sequence.delete": _("Delete sequence"),
    "sequence.delete_step": _("Delete sequence step"),
    "sequence.insert_step": _("Insert sequence step"),
    "sequence.new": _("Create sequence"),
    "sequence.set_mib_enabled": _("Toggle MIB"),
    "sequence.set_tracking_mode": _("Change tracking mode"),
    "show.import": _("Import show"),
    "show.reset_user_levels": _("Reset user levels"),
    "show.set_home_preset": _("Set Home Preset"),
    "step.update_channel_time": _("Edit channel fade time"),
    "step.update_text": _("Edit step label"),
    "step.update_times": _("Edit step timing"),
    "universe.add": _("Add DMX universe"),
    "universe.blackout": _("Toggle universe blackout"),
    "universe.remove": _("Remove DMX universe"),
    "universe.set_config": _("Configure universe"),
    "universe.set_protocol": _("Change universe protocol"),
}


class Action(ABC):
    """Base class for all application actions (Command Pattern).

    Supports headless execution, Undo/Redo, and state feedback for physical
    controllers.
    """

    name: str = ""  # Unique action identifier (e.g., "group.new")
    history_label: str = ""  # Human-readable label for Undo History
    can_undo: bool = False  # Set to True if the action supports undo/redo

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        self.app = app
        self.command_line: str = ""

    @abstractmethod
    def execute(self) -> object:
        """Execute the action using its already-configured state.

        Must be implemented by all subclasses. Arguments are provided
        via configure() before this method is called.
        """

    def undo(self) -> None:
        """Revert the state changes made by execute().

        Must be overridden if can_undo is True.
        """
        if not self.can_undo:
            raise NotImplementedError(f"Action '{self.name}' does not support undo.")

    def redo(self) -> None:
        """Reapply the action. Defaults to calling execute() with saved state."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the current state of this action for MIDI/OSC feedback.

        Returns:
            A dictionary representing feedback parameters (e.g., {'active': True}).
        """
        return {}

    def get_history_label(self) -> str:
        """Return a human-readable label for the Undo History UI."""
        if self.history_label:
            return self.history_label
        if self.name in _DEFAULT_HISTORY_LABELS:
            return _DEFAULT_HISTORY_LABELS[self.name]
        if "." in self.name:
            domain, verb = self.name.split(".", 1)
            return f"{domain.capitalize()}: {verb.replace('_', ' ').title()}"
        return self.name.replace("_", " ").title()

    def get_history_details(self) -> str:
        """Return concise, user-friendly context details for the Undo History UI."""
        return ""
