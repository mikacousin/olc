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
import cairo
import mido
from gi.repository import Gdk, GLib, GObject, Gtk
from olc.define import App
from olc.widgets import rounded_rectangle, rounded_rectangle_fill


class GoWidget(Gtk.Widget):
    """Go button widget"""

    __gtype_name__ = "GoWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)

        self.width = 100
        self.height = 50
        self.radius = 10

        self.pressed = False

        self.set_size_request(self.width, self.height)

        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)

        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)

    def on_press(self, _tgt, _ev):
        """Go pressed"""
        for outport in App().midi.outports:
            item = App().midi.notes.notes["go"]
            msg = mido.Message(
                "note_on", channel=item[0], note=item[1], velocity=127, time=0
            )
            GLib.idle_add(outport.send, msg)
        self.pressed = True
        self.queue_draw()

    def on_release(self, _tgt, _ev):
        """Go released"""
        for outport in App().midi.outports:
            item = App().midi.notes.notes["go"]
            msg = mido.Message(
                "note_on", channel=item[0], note=item[1], velocity=0, time=0
            )
            GLib.idle_add(outport.send, msg)
        self.pressed = False
        self.queue_draw()
        self.emit("clicked")

    def do_draw(self, cr):
        """Draw Go button

        Args:
            cr: Cairo context
        """
        # Draw rounded box
        if self.pressed:
            if App().midi.midi_learn == "go":
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.3, 0.0)
        elif App().midi.midi_learn == "go":
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        area = (1, self.width - 2, 1, self.height - 2)
        rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.radius)
        # Draw Go
        cr.set_source_rgb(0.8, 0.8, 0.8)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(10)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents("Go")
        cr.move_to(
            self.width / 2 - w / 2, self.height / 2 - (h - (self.radius * 2)) / 2
        )
        cr.show_text("Go")

    def do_realize(self):
        """Realize widget"""
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = (
            self.get_events()
            | Gdk.EventMask.EXPOSURE_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.TOUCH_MASK
        )
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
