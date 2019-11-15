import cairo
import math
from gi.repository import Gtk, Gdk, Gio, GObject

class FaderWidget(Gtk.Widget):
    __gtype_name__ = "FaderWidget"

    __gsignals__ = {
            "clicked" : (GObject.SIGNAL_ACTION, None, ())
            }

    def __init__(self, text='None', red=0.2, green=0.2, blue=0.2):
        Gtk.Widget.__init__(self)

        self.app = Gio.Application.get_default()

        self.width = 60
        self.height = 360
        self.radius = 10

        self.red = red
        self.green = green
        self.blue = blue

        self.pressed = False
        self.value = 0
        self.inverted = False
        self.on_fader = False

        self.text = text

        self.set_size_request(self.width + 1, self.height + 1)

        self.connect('button-press-event', self.on_press)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect('button-release-event', self.on_release)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect('motion-notify-event', self.on_motion)

    def on_press(self, tgt, ev):
        self.pressed = True
        self.queue_draw()

        if self.inverted:
            h = (((self.height - 20) / 255) * self.value)
        else:
            h = self.height - 20 - (((self.height - 20) / 255) * self.value)

        if ev.y > h  and ev.y < h + 20:
            self.on_fader = True

    def on_release(self, tgt, ev):
        self.pressed = False
        self.queue_draw()
        self.emit('clicked')

    def on_motion(self, tgt, ev):
        if self.pressed and self.on_fader and not self.app.midi.midi_learn:
            if self.inverted:
                val = ((self.height - 20) / 360) * ev.y
            else:
                val = self.height - 20 - (((self.height - 20) / 360) * ev.y)
            if val < 0:
                val = 0
            elif val > 255:
                val = 255
            self.value = val
            self.queue_draw()

    def do_draw(self, cr):
        # Draw vertical box
        cr.set_source_rgb(self.red, self.green, self.blue)
        area = ((self.width / 2) - 3, (self.width / 2) + 3, 1, self.height - 2)
        self.rounded_rectangle_fill(cr, area, self.radius / 2)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        self.rounded_rectangle(cr, area, self.radius / 2)
        # Draw Cursor
        if self.inverted:
            h = (((self.height - 20) / 255) * self.value)
        else:
            h = self.height - 20 - (((self.height - 20) / 255) * self.value)
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
        area = (1, self.width - 2, h, h + 20)
        self.rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        self.rounded_rectangle(cr, area, self.radius)

    def rounded_rectangle_fill(self, cr, area, radius):
        a,b,c,d = area
        cr.arc(a + radius, c + radius, radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - radius, c + radius, radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - radius, d - radius, radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + radius, d - radius, radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.fill()

    def rounded_rectangle(self, cr, area, radius):
        a,b,c,d = area
        cr.arc(a + radius, c + radius, radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - radius, c + radius, radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - radius, d - radius, radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + radius, d - radius, radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.stroke()

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = (self.get_events() | Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                | Gdk.EventMask.TOUCH_MASK)
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)

    def get_value(self):
        return self.value

    def set_value(self, value):
        if value >= 0 and value < 256:
            self.value = value
            self.queue_draw()

    def get_inverted(self):
        return self.inverted

    def set_inverted(self, inv):
        if inv == False or inv == True:
            self.inverted = inv
            self.queue_draw()
