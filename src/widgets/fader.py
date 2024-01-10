# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from gi.repository import Gdk, GObject, Gtk
from olc.define import App
from .common import rounded_rectangle, rounded_rectangle_fill


class FaderWidget(Gtk.Scale):
    """Fader widget, inherits from Gtk.scale"""

    __gtype_name__ = "FaderWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_ACTION, None, ())}

    def __init__(self, *args, text="None", red=0.2, green=0.2, blue=0.2, **kwds):
        super().__init__(*args, **kwds)

        self.red = red
        self.green = green
        self.blue = blue
        self.led = True
        self.pressed = False

        self.text = text

        self.connect("button-press-event", self.on_press)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-release-event", self.on_release)

    def on_press(self, _tgt, _ev):
        """Fader pressed"""
        self.pressed = True
        self.queue_draw()

        if self in (App().virtual_console.scale_a, App().virtual_console.scale_b):
            App().crossfade.manual = True

    def on_release(self, _tgt, _ev):
        """Fader released"""
        self.pressed = False
        self.queue_draw()
        self.emit("clicked")

    def do_draw(self, cr):
        """Draw Fader

        Args:
            cr: Cairo context
        """
        allocation = self.get_allocation()
        width = allocation.width
        height = allocation.height
        radius = 10

        layout = self.get_layout()
        layout_h = layout.get_pixel_size().height if layout else 0

        # Draw vertical box
        cr.set_source_rgb(self.red, self.green, self.blue)
        area = ((width / 2) - 3, (width / 2) + 3, layout_h + 10, height - 10)
        rounded_rectangle_fill(cr, area, radius / 2)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, radius / 2)

        # Cursor height
        value = self.get_value()

        if self.get_inverted():
            h = height - (((height - layout_h - 10 - (20 / 2)) / 255) * value)
        else:
            h = (layout_h + 10 + (20 / 2) + (((height - layout_h - 10 -
                                               (20 / 2)) / 255) * value))

        # Draw LED
        if self.led:
            cr.set_source_rgba(0.5, 0.3, 0.0, 1.0)
            area = ((width / 2) - 2, (width / 2) + 2, h - 10, height - 10)
            rounded_rectangle_fill(cr, area, radius / 2)

        # Draw Cursor
        area = ((width / 2) - 19, (width / 2) + 19, h - 20, h)

        if App().midi.learning == self.text:
            if self.pressed:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.2, 0.2)
        elif self.pressed:
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        rounded_rectangle_fill(cr, area, radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, radius)
