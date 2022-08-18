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
from gi.repository import Gtk


class MidiCheckButtonWidget(Gtk.CheckButton):
    """Check button widget for MIDI settings"""

    __gtype_name__ = "MIDICheckWidget"

    def __init__(self, midi_name="None"):
        Gtk.CheckButton.__init__(self)

        self.midi_name = midi_name

    def set_midi_name(self, midi_name="None"):
        """Set plain MIDI name

        Args:
            midi_name: plain MIDI name
        """
        self.midi_name = midi_name

    def get_midi_name(self):
        """Get plain MIDI name

        Returns:
            string: MIDI name (mido name)
        """
        return self.midi_name
