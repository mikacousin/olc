"""Knob Widget for Virtual Console"""

import math

from gi.repository import GObject, Gtk, Gdk
from olc.define import App


class KnobWidget(Gtk.DrawingArea):
    """Knob widget, inherits from Gtk.DrawingArea"""

    __gtype_name__ = "KnobWidget"

    __gsignals__ = {
        "clicked": (GObject.SignalFlags.ACTION, None, ()),
        "changed": (GObject.SignalFlags.ACTION, None, ()),
    }

    def __init__(self, text="None"):
        Gtk.DrawingArea.__init__(self)

        self.value = 0
        self.text = text

        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect("scroll-event", self.on_scroll)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-release-event", self.on_release)

    def on_release(self, _tgt, _ev):
        """Emit 'clicked' when released"""
        self.emit("clicked")

    def get_value(self):
        """Return value (0-255)"""
        return self.value

    def on_scroll(self, _widget, event):
        """On mouse wheel event"""
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        step = 10
        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            step = 1
        (scroll, direction) = event.get_scroll_direction()
        if scroll and direction == Gdk.ScrollDirection.UP:
            self.value += step
        if scroll and direction == Gdk.ScrollDirection.DOWN:
            self.value -= step
        if self.value < 0:
            self.value = 0
        elif self.value > 255:
            self.value = 255
        self.emit("changed")
        self.queue_draw()

    def do_draw(self, cr):
        """Draw Knob"""
        scale = 1.5
        self.set_size_request(34 * scale, 34 * scale)
        width = self.get_allocation().width
        height = self.get_allocation().height

        # move to the center of the drawing area
        # (translate from the top left corner to w/2, h/2)
        cr.translate(width / 2, height / 2)
        cr.rotate(math.radians(-220))
        cr.scale(scale, scale)
        cr.set_line_width(2)
        cr.set_source_rgba(0.1, 0.1, 0.1, 1.0)
        cr.arc(0, 0, 10, 0, math.radians(360))
        cr.stroke()
        if App().midi.midi_learn == self.text:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
        cr.arc(0, 0, 10, 0, math.radians(360))
        cr.fill()

        angle = (self.get_value() / 255) * 260
        # LED
        cr.set_line_width(3)
        cr.set_source_rgba(0.5, 0.3, 0.0, 1.0)
        cr.arc(0, 0, 15, math.radians(0), math.radians(angle))
        cr.stroke()
        # Knob
        cr.set_line_width(2)
        cr.set_source_rgba(0.1, 0.1, 0.1, 1.0)
        x1 = 2 * math.cos(math.radians(angle))
        y1 = 2 * math.sin(math.radians(angle))
        x2 = 8 * math.cos(math.radians(angle))
        y2 = 8 * math.sin(math.radians(angle))
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.stroke()
