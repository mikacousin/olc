import math
from gi.repository import Gtk, Gdk, Gio, GObject


class FaderWidget(Gtk.Scale):
    __gtype_name__ = "FaderWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_ACTION, None, ())}

    def __init__(self, text="None", red=0.2, green=0.2, blue=0.2, *args, **kwds):
        super().__init__(*args, **kwds)

        self.app = Gio.Application.get_default()

        self.red = red
        self.green = green
        self.blue = blue

        self.pressed = False

        self.text = text

        self.connect("button-press-event", self.on_press)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-release-event", self.on_release)

    def on_press(self, tgt, ev):
        self.pressed = True
        self.queue_draw()

        if self in (self.app.virtual_console.scaleA, self.app.virtual_console.scaleB):
            self.app.crossfade.manual = True

    def on_release(self, tgt, ev):
        self.pressed = False
        self.queue_draw()
        self.emit("clicked")

    def do_draw(self, cr):
        allocation = self.get_allocation()
        width = allocation.width
        height = allocation.height
        radius = 10

        layout = self.get_layout()
        if layout:
            layout_h = layout.get_pixel_size().height
        else:
            layout_h = 0

        inverted = self.get_inverted()

        # Draw vertical box
        cr.set_source_rgb(self.red, self.green, self.blue)
        area = ((width / 2) - 3, (width / 2) + 3, layout_h + 10, height - 10)
        self.rounded_rectangle_fill(cr, area, radius / 2)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        self.rounded_rectangle(cr, area, radius / 2)

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

        if self.app.midi.midi_learn == self.text:
            if self.pressed:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            if self.pressed:
                cr.set_source_rgb(0.1, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.2, 0.2, 0.2)
        self.rounded_rectangle_fill(cr, area, radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        self.rounded_rectangle(cr, area, radius)

    def rounded_rectangle_fill(self, cr, area, radius):
        a, b, c, d = area
        cr.arc(a + radius, c + radius, radius, 2 * (math.pi / 2), 3 * (math.pi / 2))
        cr.arc(b - radius, c + radius, radius, 3 * (math.pi / 2), 4 * (math.pi / 2))
        cr.arc(b - radius, d - radius, radius, 0 * (math.pi / 2), 1 * (math.pi / 2))
        cr.arc(a + radius, d - radius, radius, 1 * (math.pi / 2), 2 * (math.pi / 2))
        cr.close_path()
        cr.fill()

    def rounded_rectangle(self, cr, area, radius):
        a, b, c, d = area
        cr.arc(a + radius, c + radius, radius, 2 * (math.pi / 2), 3 * (math.pi / 2))
        cr.arc(b - radius, c + radius, radius, 3 * (math.pi / 2), 4 * (math.pi / 2))
        cr.arc(b - radius, d - radius, radius, 0 * (math.pi / 2), 1 * (math.pi / 2))
        cr.arc(a + radius, d - radius, radius, 1 * (math.pi / 2), 2 * (math.pi / 2))
        cr.close_path()
        cr.stroke()
