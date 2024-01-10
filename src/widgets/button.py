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
import cairo
from gi.repository import Gdk, GObject, Gtk
from olc.define import App
from .common import rounded_rectangle, rounded_rectangle_fill


class ButtonWidget(Gtk.Widget):
    """Button widget"""

    __gtype_name__ = "ButtonWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_ACTION, None, ())}

    def __init__(self, label="", text="None"):
        Gtk.Widget.__init__(self)

        self.width = 50
        self.height = 50
        self.radius = 10
        self.font_size = 10

        self.pressed = False
        self.label = label
        self.text = text

        self.set_size_request(self.width, self.height)

        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)

        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)

    def on_press(self, _tgt, _ev):
        """Button pressed"""
        App().midi.messages.notes.send(self.text, 127)
        self.pressed = True
        self.queue_draw()
        self.emit("clicked")

    def on_release(self, _tgt, _ev):
        """Button released"""
        App().midi.messages.notes.send(self.text, 0)
        self.pressed = False
        self.queue_draw()

    def do_draw(self, cr):
        """Draw button

        Args:
            cr: Cairo context
        """
        # Draw rounded box
        if self.text == "None":
            cr.set_source_rgb(0.4, 0.4, 0.4)
        elif self.pressed:
            if App().midi.learning == self.text:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.3, 0.0)
        elif App().midi.learning == self.text:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        area = (1, self.width - 2, 1, self.height - 2)
        rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.radius)
        # Draw Text
        if self.text == "None":
            cr.set_source_rgb(0.5, 0.5, 0.5)
        else:
            cr.set_source_rgb(0.8, 0.8, 0.8)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(self.font_size)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(self.label)
        cr.move_to(
            self.width / 2 - w / 2, self.height / 2 - (h - (self.radius * 2)) / 2
        )
        cr.show_text(self.label)

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
