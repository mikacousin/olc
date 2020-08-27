"""Controller Widget for Virtual Console"""

import math

from gi.repository import GObject, Gtk, Gdk
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

        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self.on_scroll)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-release-event", self.on_release)

    def on_release(self, _tgt, _ev):
        """Emit 'clicked' when released"""
        self.emit("clicked")

    def on_scroll(self, _widget, event):
        """On scroll wheel event"""
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        step = 10
        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            step = 1
        (scroll, direction) = event.get_scroll_direction()
        if scroll and direction == Gdk.ScrollDirection.UP:
            self.emit("moved", Gdk.ScrollDirection.UP, step)
        elif scroll and direction == Gdk.ScrollDirection.DOWN:
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
        """Draw Controller"""
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
