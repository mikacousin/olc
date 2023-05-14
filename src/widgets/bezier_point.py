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
import math
from gi.repository import Gdk, Gtk


class BezierPointWidget(Gtk.ToggleButton):
    """Bezier point widget"""

    __gtype_name__ = "BezierPointWidget"

    def __init__(self, *args, curve=None, **kwds):
        super().__init__(*args, **kwds)
        self.curve = curve
        evmask = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK
        self.set_events(evmask)
        self.connect("button_press_event", self.button_pressed)
        self.connect("motion_notify_event", self.motion_notify)
        self.offsetx = 0
        self.offsety = 0
        self.prev_x = 0
        self.prev_y = 0
        self.maxx = 0
        self.maxy = 0

    def button_pressed(self, widget, event):
        """Button pressed

        Args:
            widget: Widget pressed
            event: Event with coordinates
        """
        if event.button == 1:
            parent = widget.get_parent()
            window = parent.get_window()
            self.offsetx, self.offsety = window.get_root_origin()
            x, y = parent.translate_coordinates(self.get_toplevel(), 0, 0)
            self.offsetx += x
            self.offsety += y
            self.offsetx += event.x
            self.offsety += event.y
            self.maxx = parent.get_allocation().width - widget.get_allocation().width
            self.maxy = parent.get_allocation().height - widget.get_allocation().height

    def motion_notify(self, widget, event):
        """Button moved

        Args:
            widget: Widget moved
            event: Event with coordinates
        """
        x = event.x_root - self.offsetx
        y = event.y_root - self.offsety
        x = max(min(x, self.maxx), 0)
        y = max(min(y, self.maxy), 0)
        if x != self.prev_x or y != self.prev_y:
            print(self.curve.points)
            self.prev_x = x
            self.prev_y = y
            fixed = self.get_parent()
            fixed.move(widget, x, y)
            self.curve.points[1] = [x, y]
            self.curve.populate_values()

    def do_draw(self, cr):
        """Draw Bezier Point Widget

        Args:
            cr: Cairo context
        """
        self.set_size_request(8, 8)
        cr.set_line_width(1)
        if self.get_active():
            cr.set_source_rgba(0.7, 0.5, 0.2, 1.0)
        else:
            cr.set_source_rgba(0.5, 0.3, 0.0, 1.0)
        cr.arc(4, 4, 4, 0, 2 * math.pi)
        cr.fill()
