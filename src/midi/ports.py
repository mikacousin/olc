# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Any, List, Optional
import mido
from olc.define import App


class MidiIn:
    """A thin wrapper around mido input port"""

    name: Optional[str]  # The port name
    port: mido.ports.BaseInput  # The port itself

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name
        self.port = mido.open_input(self.name)
        self.port.callback = self.receive_callback

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

    inports: List[MidiIn]
    outports: List[Any]

    def __init__(self):
        self.inports = []
        self.outports = []

        # Open MIDI In ports
        ports = App().settings.get_strv("midi-in")
        self.open_input(ports)
        # Open MIDI Out ports
        ports = App().settings.get_strv("midi-out")
        self.open_output(ports)

    def open_input(self, ports: List[str]) -> None:
        """Open MIDI inputs

        Args:
            ports: MIDI ports to open
        """
        input_names = mido.get_input_names()
        for port in ports:
            if port in input_names:
                inport = MidiIn(port)
                self.inports.append(inport)
            else:
                inport = MidiIn()

    def open_output(self, ports: List[str]) -> None:
        """Open MIDI outputs

        Args:
            ports: MIDI ports to open
        """
        output_names = mido.get_output_names()
        for port in ports:
            if port in output_names:
                outport = mido.open_output(port)
                self.outports.append(outport)
            else:
                outport = mido.open_output()

    def close_input(self) -> None:
        """Close MIDI inputs"""
        for inport in self.inports:
            inport.close()
            self.inports.remove(inport)

    def close_output(self) -> None:
        """Close MIDI outputs"""
        for outport in self.outports:
            outport.close()
            self.outports.remove(outport)
