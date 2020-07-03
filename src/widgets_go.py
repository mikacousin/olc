import cairo
from gi.repository import Gtk, Gdk, GObject

from olc.define import App
from olc.widgets import rounded_rectangle_fill, rounded_rectangle


class GoWidget(Gtk.Widget):
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

    def on_press(self, tgt, ev):
        self.pressed = True
        self.queue_draw()

    def on_release(self, tgt, ev):
        self.pressed = False
        self.queue_draw()
        self.emit("clicked")

    def do_draw(self, cr):
        # Draw rounded box
        if self.pressed:
            if App().midi.midi_learn == "Go":
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.1, 0.1, 0.1)
        else:
            if App().midi.midi_learn == "Go":
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
        (x, y, w, h, dx, dy) = cr.text_extents("Go")
        cr.move_to(
            self.width / 2 - w / 2, self.height / 2 - (h - (self.radius * 2)) / 2
        )
        cr.show_text("Go")

    def do_realize(self):
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
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
