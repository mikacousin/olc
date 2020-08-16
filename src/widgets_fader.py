"""Fader Widget for Virtual Console"""

from gi.repository import Gdk, GObject, Gtk
from olc.define import App
from olc.widgets import rounded_rectangle, rounded_rectangle_fill


class FaderWidget(Gtk.Scale):
    """Fader widget, inherits from Gtk.scale"""

    __gtype_name__ = "FaderWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_ACTION, None, ())}

    def __init__(self, *args, text="None", red=0.2, green=0.2, blue=0.2, **kwds):
        super().__init__(*args, **kwds)

        self.red = red
        self.green = green
        self.blue = blue

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
        """Draw Fader"""
        allocation = self.get_allocation()
        width = allocation.width
        height = allocation.height
        radius = 10

        layout = self.get_layout()
        layout_h = layout.get_pixel_size().height if layout else 0
        inverted = self.get_inverted()

        # Draw vertical box
        cr.set_source_rgb(self.red, self.green, self.blue)
        area = ((width / 2) - 3, (width / 2) + 3, layout_h + 10, height - 10)
        rounded_rectangle_fill(cr, area, radius / 2)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, radius / 2)

        value = self.get_value()

        # Draw Cursor
        if inverted:
            h = height - (((height - layout_h - 10 - (20 / 2)) / 255) * value)
        else:
            h = (
                layout_h
                + 10
                + (20 / 2)
                + (((height - layout_h - 10 - (20 / 2)) / 255) * value)
            )

        area = ((width / 2) - 19, (width / 2) + 19, h - 20, h)

        if App().midi.midi_learn == self.text:
            if self.pressed:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            if self.pressed:
                cr.set_source_rgb(0.1, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.2, 0.2, 0.2)
        rounded_rectangle_fill(cr, area, radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, radius)
