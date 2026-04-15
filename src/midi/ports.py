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
from typing import Callable, Optional

import mido
from gi.repository import GLib
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.midi import Midi


class MidiIO:
    """A thin wrapper around mido IO port"""

    name: Optional[str]  # The port name
    port: mido.ports.BaseInput  # The port itself

    def __init__(self, midi: Midi, name: Optional[str] = None) -> None:
        self.midi = midi
        self.name = name
        self.port = mido.open_ioport(name=self.name, callback=self.receive_callback)

    def __del__(self) -> None:
        self.port.callback = None
        self.port.close()

    def close(self) -> None:
        """Close open MIDI port and delete Callback"""
        self.port.callback = None
        self.port.close()

    def receive_callback(self, msg: mido.Message) -> None:
        """Scan MIDI messages.
        Executed with mido callback, in another thread

        Args:
            msg: MIDI message
        """
        # print(self.name, msg)
        if self.midi.learning:
            self.midi.learn(msg)

        # Find action
        if msg.type in ("note_on", "note_off"):
            self.midi.messages.notes.scan(msg)
        elif msg.type == "control_change":
            self.midi.messages.control_change.scan(self.name, msg)
        elif msg.type == "pitchwheel":
            self.midi.messages.pitchwheel.scan(msg)


class MidiPorts:
    """MIDI In and Out ports"""

    ports: list[MidiIO]

    def __init__(
        self,
        midi: Midi,
        settings: Gio.Settings,
        on_ports_changed: Callable[[], None] | None = None,
    ) -> None:
        self.midi = midi
        self.settings = settings
        self.on_ports_changed = on_ports_changed

        self.ports = []
        self.mido_ports = None

        ports = self.settings.get_strv("midi-ports")
        self.mido_ports = mido.get_ioport_names()
        self.open(ports)

        self.poll = RepeatedTimer(1, self.polling)

    def polling(self) -> None:
        """Poll MIDI ports"""
        port_names = mido.get_ioport_names()
        if port_names != self.mido_ports:
            self.mido_ports = port_names
            self.open(self.settings.get_strv("midi-ports"))
            self.midi.update_faders()
            if self.on_ports_changed:
                GLib.idle_add(self.on_ports_changed)

    def open(self, ports: list[str]) -> None:
        """Open MIDI IO

        Args:
            ports: MIDI ports to open
        """
        for port in ports:
            if self.mido_ports and port in self.mido_ports:
                ioport = MidiIO(self.midi, port)
                self.ports.append(ioport)

    def close(self) -> None:
        """Close MIDI inputs"""
        for port in self.ports:
            self.ports.remove(port)
            port.close()
