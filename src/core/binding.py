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
# pylint: disable=too-few-public-methods
from __future__ import annotations

import typing
from abc import ABC, abstractmethod

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class TriggerBinding(ABC):
    """Represents a connection between a physical trigger and a Core Action."""

    def __init__(self, action_name: str) -> None:
        """Initialize the TriggerBinding.

        Args:
            action_name: The name of the Action this is bound to.
        """
        self.action_name = action_name
        self.app: typing.Optional[CoreApplication] = None

    @abstractmethod
    def send_feedback(self, state: dict[str, typing.Any]) -> None:
        """Send state feedback back to the physical controller.

        Args:
            state: The current feedback state of the action.
        """


class KeyboardBinding(TriggerBinding):
    """Binds a keyboard key to a Core Action."""

    def __init__(self, action_name: str, key_name: str) -> None:
        """Initialize the KeyboardBinding.

        Args:
            action_name: The target action name.
            key_name: The key identifier (e.g. 'space', 'Delete').
        """
        super().__init__(action_name)
        self.key_name = key_name

    def send_feedback(self, state: dict[str, typing.Any]) -> None:
        # Keyboard inputs typically do not receive physical feedback,
        # but could trigger UI highlights if needed in the future.
        pass


class MidiBinding(TriggerBinding):
    """Binds a MIDI input note or CC to a Core Action and sends LED feedback."""

    def __init__(
        self,
        action_name: str,
        event_type: str,
        channel: int,
        number: int,
    ) -> None:
        """Initialize the MidiBinding.

        Args:
            action_name: The target action name.
            event_type: The MIDI event type ('note' or 'cc').
            channel: The MIDI channel (0-15).
            number: The MIDI note number or CC control number.
        """
        super().__init__(action_name)
        self.event_type = event_type
        self.channel = channel
        self.number = number

    def send_feedback(self, state: dict[str, typing.Any]) -> None:
        if not self.app or not self.app.midi:
            return

        active = state.get("active", False)
        timer = state.get("timer", 0)

        if self.event_type == "note":
            # Leverage existing Midi button-light interface
            if active or timer > 0:
                if timer > 0:
                    self.app.midi.button_on(self.action_name, timer)
                else:
                    self.app.midi.button_on(self.action_name)
            else:
                self.app.midi.button_off(self.action_name)
        elif self.event_type == "cc":
            value = state.get("level", 127 if active else 0)
            self.app.midi.send_cc(self.channel, self.number, value)


class OscBinding(TriggerBinding):
    """Binds an OSC address to a Core Action and sends status feedback."""

    def __init__(self, action_name: str, osc_address: str) -> None:
        """Initialize the OscBinding.

        Args:
            action_name: The target action name.
            osc_address: The target OSC address pattern (e.g. '/olc/playback/go').
        """
        super().__init__(action_name)
        self.osc_address = osc_address

    def send_feedback(self, state: dict[str, typing.Any]) -> None:
        if not self.app or not self.app.engine:
            return

        # TouchOSC style layout: send 1.0 (active/on) or 0.0 (inactive/off)
        active = state.get("active", False)
        val = 1.0 if active else 0.0
        self.app.engine.send_osc(self.osc_address, val)
