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

from gi.repository import Gdk, GObject, Gtk
from olc.define import App


class ControllerWidget(Gtk.DrawingArea):
    """Controller widget, inherits from Gtk.DrawingArea

    Attributes:
        angle (int): Controller angle (from -360 to 360)
        led (bool): Display LED
    """

    __gtype_name__ = "ControllerWidget"

    __gsignals__ = {
        "moved": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (
                Gdk.ScrollDirection,
                int,
            ),
        ),
        "clicked": (GObject.SignalFlags.ACTION, None, ()),
    }

    def __init__(self, text="None"):
        Gtk.DrawingArea.__init__(self)

        self.angle = 0
        self.led = False
        self.text = text

        # Mouse position when button clicked
        self.x1 = 0
        self.y1 = 0
        self.old_angle = 0

        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self.on_scroll)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_press)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-release-event", self.on_release)
        self.add_events(Gdk.EventMask.BUTTON1_MOTION_MASK)
        self.connect("motion-notify-event", self.on_motion)

    def on_press(self, _tgt, event):
        """Mouse button pressed

        Args:
            event: Gdk.Event
        """
        self.x1 = event.x
        self.y1 = event.y
        self.old_angle = math.radians(self.angle)

    def on_release(self, _tgt, _ev):
        """Mouse button released"""
        self.old_angle = 0
        self.emit("clicked")

    def on_motion(self, _tgt, event):
        """Track mouse to rotate controller

        Args:
            event: Gdk.Event
        """
        # Center
        x0 = self.get_allocation().width / 2
        y0 = self.get_allocation().height / 2
        # Actual position
        x2 = event.x
        y2 = event.y
        # Angle of movement
        y = (self.x1 - x0) * (y2 - y0) - (self.y1 - y0) * (x2 - x0)
        x = (self.x1 - x0) * (x2 - x0) + (self.y1 - y0) * (y2 - y0)
        angle = math.atan2(y, x)
        if angle > math.pi / 2:
            self.old_angle = self.old_angle + math.pi / 2
            angle = angle - math.pi / 2
            self.x1 = x2
            self.y1 = y2
        elif angle < -math.pi / 2:
            self.old_angle = self.old_angle - math.pi / 2
            angle = angle + math.pi / 2
            self.x1 = x2
            self.y1 = y2
        self.angle = math.degrees(self.old_angle + angle)
        step = math.degrees(abs(angle)) * (100 / 360)
        if angle > 0:
            self.emit("moved", Gdk.ScrollDirection.UP, step)
        else:
            self.emit("moved", Gdk.ScrollDirection.DOWN, step)

    def on_scroll(self, _widget, event):
        """On scroll wheel event

        Args:
            event: Gdk.Event
        """
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        step = 1 if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK else 10
        (scroll, direction) = event.get_scroll_direction()
        if scroll:
            if direction == Gdk.ScrollDirection.UP:
                self.emit("moved", Gdk.ScrollDirection.UP, step)
            elif direction == Gdk.ScrollDirection.DOWN:
                self.emit("moved", Gdk.ScrollDirection.DOWN, step)

    def do_moved(self, direction, step):
        """On 'moved' signal

        Args:
            direction (Gdk.ScrollDirection): UP or DOWN
            step (int): increment or decrement step size
        """
        if direction == Gdk.ScrollDirection.UP:
            self.angle += step
        elif direction == Gdk.ScrollDirection.DOWN:
            self.angle -= step
        if self.angle > 360:
            self.angle -= 360
        elif self.angle < -360:
            self.angle += 360
        self.queue_draw()

    def do_draw(self, cr):
        """Draw Controller

        Args:
            cr: Cairo context
        """
        scale = 2
        self.set_size_request(60 * scale, 60 * scale)
        width = self.get_allocation().width
        height = self.get_allocation().height
        # move to the center of the drawing area
        # (translate from the top left corner to w/2, h/2)
        cr.translate(width / 2, height / 2)
        cr.scale(scale, scale)
        # Circle
        cr.set_line_width(1)
        cr.set_source_rgba(0.1, 0.1, 0.1, 1.0)
        cr.arc(0, 0, 20, 0, math.radians(360))
        cr.stroke()
        if App().midi.midi_learn == self.text:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
        cr.arc(0, 0, 19, 0, math.radians(360))
        cr.fill()
        # LED
        if self.led:
            cr.set_line_width(1)
            cr.set_source_rgba(0.8, 0.4, 0.4, 1.0)
            x1 = 27 * math.cos(math.radians(self.angle))
            y1 = 27 * math.sin(math.radians(self.angle))
            cr.arc(x1, y1, 3, math.radians(0), math.radians(360))
            cr.fill()
        # Knob
        cr.set_line_width(2)
        cr.set_source_rgba(0.1, 0.1, 0.1, 1.0)
        x1 = 10 * math.cos(math.radians(self.angle))
        y1 = 10 * math.sin(math.radians(self.angle))
        x2 = 16 * math.cos(math.radians(self.angle))
        y2 = 16 * math.sin(math.radians(self.angle))
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.stroke()
