# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Optional
import mido
from gi.repository import GLib
from olc.define import App
from olc.timer import RepeatedTimer


class MidiIO:
    """A thin wrapper around mido IO port"""

    name: Optional[str]  # The port name
    port: mido.ports.BaseInput  # The port itself

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name
        self.port = mido.open_ioport(name=self.name, callback=self.receive_callback)
        # self.port.callback = self.receive_callback

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
        if App().midi.midi_learn:
            App().midi.learn(msg)

        # Find action actived
        if msg.type in ("note_on", "note_off"):
            App().midi.notes.scan(msg)
        elif msg.type == "control_change":
            App().midi.control_change.scan(self.name, msg)
        elif msg.type == "pitchwheel":
            App().midi.pitchwheel.scan(msg)


class MidiPorts:
    """MIDI In and Out ports"""

    ports: list[MidiIO]

    def __init__(self):
        self.ports = []
        self.mido_ports = None

        ports = App().settings.get_strv("midi-ports")
        self.mido_ports = mido.get_ioport_names()
        self.open(ports)

        self.poll = RepeatedTimer(1, self.polling)

    def polling(self) -> None:
        """Poll MIDI ports"""
        port_names = mido.get_ioport_names()
        if port_names != self.mido_ports:
            self.mido_ports = port_names
            self.open(App().settings.get_strv("midi-ports"))
            App().midi.update_masters()
            App().midi.gm_init()
            if App().tabs.tabs["settings"]:
                GLib.idle_add(App().tabs.tabs["settings"].refresh)

    def open(self, ports: list[str]) -> None:
        """Open MIDI IO

        Args:
            ports: MIDI ports to open
        """
        for port in ports:
            if port in self.mido_ports:
                ioport = MidiIO(port)
                self.ports.append(ioport)
            else:
                ioport = MidiIO()

    def close(self) -> None:
        """Close MIDI inputs"""
        for port in self.ports:
            port.close()
            self.ports.remove(port)
