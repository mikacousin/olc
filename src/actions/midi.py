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
"""Actions for MIDI configuration, port toggling, modes, learning, and mappings."""

from __future__ import annotations

import typing

import mido
from olc.core.action import Action

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class MidiPortToggleAction(Action):
    """Action to toggle a physical MIDI port enabled or disabled."""

    name = "midi.port_toggle"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.port_name: str = ""
        self.enable: bool = False
        self.old_enabled: bool = False

    def configure(self, port_name: str, enable: bool) -> None:
        """Configure the port name and desired state.

        Args:
            port_name: MIDI port identifier string.
            enable: True to enable, False to disable.
        """
        self.port_name = port_name
        self.enable = enable

    def execute(self) -> None:
        """Execute the port toggle action."""
        settings = getattr(self.app, "settings", None)
        if settings is None or not hasattr(settings, "get_strv"):
            self.can_undo = False
            return

        current_ports = list(settings.get_strv("midi-ports"))
        self.old_enabled = self.port_name in current_ports

        if self.enable == self.old_enabled:
            self.can_undo = False
            return

        self._apply_state(self.enable)

    def _apply_state(self, enable: bool) -> None:
        settings = getattr(self.app, "settings", None)
        if settings is None:
            return

        ports = list(settings.get_strv("midi-ports"))
        if enable:
            if self.port_name not in ports:
                ports.append(self.port_name)
        else:
            if self.port_name in ports:
                ports.remove(self.port_name)

        ports = list(set(ports))
        settings.set_strv("midi-ports", ports)

        midi = getattr(self.app, "midi", None)
        if midi is not None and hasattr(midi, "ports") and midi.ports is not None:
            midi.ports.close()
            midi.ports.open(ports)
            midi.update_faders()

        self.app.emit("midi.port_toggled", self.port_name, enable)

    def undo(self) -> None:
        """Revert the port toggle."""
        self._apply_state(self.old_enabled)

    def redo(self) -> None:
        """Reapply the port toggle."""
        self._apply_state(self.enable)


class MidiSetPortModeAction(Action):
    """Action to set the encoding mode of a MIDI port."""

    name = "midi.set_port_mode"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.port_name: str = ""
        self.mode: str = ""
        self.old_mode: str = ""

    def configure(self, port_name: str, mode: str) -> None:
        """Configure the port and encoding mode.

        Args:
            port_name: MIDI port name.
            mode: Mode ('Relative1', 'Relative2', 'Mackie', 'Absolute').
        """
        self.port_name = port_name
        self.mode = mode

    def execute(self) -> None:
        """Execute the port mode change."""
        settings = getattr(self.app, "settings", None)
        if settings is None or not hasattr(settings, "get_strv"):
            self.can_undo = False
            return

        rel1 = list(settings.get_strv("relative1"))
        rel2 = list(settings.get_strv("relative2"))
        makie = list(settings.get_strv("makie"))
        absolute = list(settings.get_strv("absolute"))

        if self.port_name in rel1:
            self.old_mode = "Relative1"
        elif self.port_name in rel2:
            self.old_mode = "Relative2"
        elif self.port_name in makie:
            self.old_mode = "Mackie"
        elif self.port_name in absolute:
            self.old_mode = "Absolute"
        else:
            self.old_mode = ""

        if self.old_mode == self.mode:
            self.can_undo = False
            return

        self._apply_mode(self.mode)

    def _apply_mode(self, mode: str) -> None:
        settings = getattr(self.app, "settings", None)
        if settings is None:
            return

        rel1 = list(settings.get_strv("relative1"))
        rel2 = list(settings.get_strv("relative2"))
        makie = list(settings.get_strv("makie"))
        absolute = list(settings.get_strv("absolute"))

        for lst in (rel1, rel2, makie, absolute):
            if self.port_name in lst:
                lst.remove(self.port_name)

        normalized = mode.lower()
        if "relative1" in normalized:
            rel1.append(self.port_name)
        elif "relative2" in normalized:
            rel2.append(self.port_name)
        elif (
            "makie" in normalized or "mackie" in normalized or "relative3" in normalized
        ):
            makie.append(self.port_name)
        elif "absolute" in normalized:
            absolute.append(self.port_name)

        settings.set_strv("relative1", list(set(rel1)))
        settings.set_strv("relative2", list(set(rel2)))
        settings.set_strv("makie", list(set(makie)))
        settings.set_strv("absolute", list(set(absolute)))

        self.app.emit("midi.port_mode_changed", self.port_name, mode)

    def undo(self) -> None:
        """Revert the port mode change."""
        self._apply_mode(self.old_mode)

    def redo(self) -> None:
        """Reapply the port mode change."""
        self._apply_mode(self.mode)


class MidiLearnToggleAction(Action):
    """Action to toggle MIDI learn mode for a given action."""

    name = "midi.learn_toggle"
    can_undo = False  # Real-time state toggle

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.action_name: str | None = None

    def configure(self, action_name: str | None = None) -> None:
        """Configure the action to learn.

        Args:
            action_name: Name of action to learn, or None to cancel learning.
        """
        self.action_name = action_name

    def execute(self) -> None:
        """Execute the learn toggle."""
        midi = getattr(self.app, "midi", None)
        learning = self.action_name or ""
        if midi is not None:
            midi.learning = learning

        self.app.emit("midi.learning_changed", learning)


class MidiAssignMappingAction(Action):
    """Action to assign a MIDI message to an application action."""

    name = "midi.assign_mapping"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.event_type: str = ""
        self.action: str = ""
        self.channel: int = 0
        self.number: int = 0
        self.old_snapshot: dict[str, typing.Any] = {}

    def configure(
        self, event_type: str, action: str, channel: int, number: int
    ) -> None:
        """Configure the mapping assignment.

        Args:
            event_type: 'note', 'control_change', or 'pitchwheel'.
            action: Action string identifier.
            channel: MIDI channel (0-15).
            number: Note number, control change number, or pitch.
        """
        self.event_type = event_type
        self.action = action
        self.channel = channel
        self.number = number

    def execute(self) -> None:
        """Execute the mapping assignment."""
        midi = getattr(self.app, "midi", None)
        if midi is None or not hasattr(midi, "messages"):
            self.can_undo = False
            return

        self.old_snapshot = {
            "notes": {k: list(v) for k, v in midi.messages.notes.notes.items()},
            "cc_notes": {k: list(v) for k, v in midi.messages.notes.cc_notes.items()},
            "control_change": {
                k: list(v)
                for k, v in midi.messages.control_change.control_change.items()
            },
            "pitchwheel": dict(midi.messages.pitchwheel.pitchwheel),
        }

        if self.event_type == "note":
            msg = mido.Message("note_on", channel=self.channel, note=self.number)
            midi.messages.notes.learn(msg, self.action)
        elif self.event_type == "control_change":
            msg = mido.Message(
                "control_change", channel=self.channel, control=self.number
            )
            midi.messages.control_change.learn(msg, self.action)
            midi.messages.notes.learn_cc(msg, self.action)
        elif self.event_type == "pitchwheel":
            msg = mido.Message("pitchwheel", channel=self.channel, pitch=self.number)
            midi.messages.pitchwheel.learn(msg, self.action)

        # Check if anything changed
        if (
            self.old_snapshot["notes"] == midi.messages.notes.notes
            and self.old_snapshot["cc_notes"] == midi.messages.notes.cc_notes
            and self.old_snapshot["control_change"]
            == midi.messages.control_change.control_change
            and self.old_snapshot["pitchwheel"] == midi.messages.pitchwheel.pitchwheel
        ):
            self.can_undo = False
            return

        self.app.lightshow.set_modified()
        self.app.emit(
            "midi.mapping_assigned",
            self.event_type,
            self.action,
            self.channel,
            self.number,
        )

    def undo(self) -> None:
        """Revert the mapping assignment."""
        midi = getattr(self.app, "midi", None)
        if midi is None or not hasattr(midi, "messages") or not self.old_snapshot:
            return

        midi.messages.notes.notes = {
            k: list(v) for k, v in self.old_snapshot["notes"].items()
        }
        midi.messages.notes.cc_notes = {
            k: list(v) for k, v in self.old_snapshot["cc_notes"].items()
        }
        midi.messages.control_change.control_change = {
            k: list(v) for k, v in self.old_snapshot["control_change"].items()
        }
        midi.messages.pitchwheel.pitchwheel = dict(self.old_snapshot["pitchwheel"])

        self.app.lightshow.set_modified()
        self.app.emit("midi.mapping_reverted", self.action)

    def redo(self) -> None:
        """Reapply the mapping assignment."""
        self.execute()


class MidiClearMappingsAction(Action):
    """Action to clear a specific mapping or all MIDI mappings."""

    name = "midi.clear_mappings"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.action: str | None = None
        self.old_snapshot: dict[str, typing.Any] = {}

    def configure(self, action: str | None = None) -> None:
        """Configure which action to clear, or None for all.

        Args:
            action: Action string to clear, or None to clear all.
        """
        self.action = action

    def execute(self) -> None:
        """Execute the clear mappings action."""
        midi = getattr(self.app, "midi", None)
        if midi is None or not hasattr(midi, "messages"):
            self.can_undo = False
            return

        self.old_snapshot = {
            "notes": {k: list(v) for k, v in midi.messages.notes.notes.items()},
            "cc_notes": {k: list(v) for k, v in midi.messages.notes.cc_notes.items()},
            "control_change": {
                k: list(v)
                for k, v in midi.messages.control_change.control_change.items()
            },
            "pitchwheel": dict(midi.messages.pitchwheel.pitchwheel),
        }

        if self.action:
            if self.action in midi.messages.notes.notes:
                midi.messages.notes.notes[self.action] = [0, -1]
            if self.action in midi.messages.notes.cc_notes:
                midi.messages.notes.cc_notes[self.action] = [0, -1]
            if self.action in midi.messages.control_change.control_change:
                midi.messages.control_change.control_change[self.action] = [0, -1]
            if self.action in midi.messages.pitchwheel.pitchwheel:
                midi.messages.pitchwheel.pitchwheel[self.action] = -1
        else:
            midi.reset_messages()

        self.app.lightshow.set_modified()
        self.app.emit("midi.mappings_cleared", self.action)

    def undo(self) -> None:
        """Revert the clearing of mappings."""
        midi = getattr(self.app, "midi", None)
        if midi is None or not hasattr(midi, "messages") or not self.old_snapshot:
            return

        midi.messages.notes.notes = {
            k: list(v) for k, v in self.old_snapshot["notes"].items()
        }
        midi.messages.notes.cc_notes = {
            k: list(v) for k, v in self.old_snapshot["cc_notes"].items()
        }
        midi.messages.control_change.control_change = {
            k: list(v) for k, v in self.old_snapshot["control_change"].items()
        }
        midi.messages.pitchwheel.pitchwheel = dict(self.old_snapshot["pitchwheel"])

        self.app.lightshow.set_modified()
        self.app.emit("midi.mappings_reverted", self.action)

    def redo(self) -> None:
        """Reapply the clear mappings."""
        self.execute()
