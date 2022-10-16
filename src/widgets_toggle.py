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
import mido
from gi.repository import GLib, Gtk
from olc.define import App
from olc.widgets import rounded_rectangle, rounded_rectangle_fill


class ToggleWidget(Gtk.ToggleButton):
    """Toggle button widget"""

    __gtype_name__ = "ToggleWidget"

    def __init__(self, text="None"):
        Gtk.ToggleButton.__init__(self)

        self.width = 50
        self.height = 50
        self.radius = 5
        self.text = text

    def do_draw(self, cr):
        """Draw Toggle button

        Args:
            cr: Cairo context
        """
        self.set_size_request(self.width, self.height)
        # Button
        area = (10, self.width - 10, 10, self.height - 10)
        if App().midi.midi_learn == self.text:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        elif self.get_active():
            cr.set_source_rgb(0.5, 0.3, 0.0)
            for outport in App().midi.ports.outports:
                item = App().midi.notes.notes[self.text]
                if item[1] != -1:
                    msg = mido.Message(
                        "note_on", channel=item[0], note=item[1], velocity=127, time=0
                    )
                    GLib.idle_add(outport.send, msg)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
            for outport in App().midi.ports.outports:
                item = App().midi.notes.notes[self.text]
                if item[1] != -1:
                    msg = mido.Message(
                        "note_on", channel=item[0], note=item[1], velocity=0, time=0
                    )
                    GLib.idle_add(outport.send, msg)
        rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.radius)
