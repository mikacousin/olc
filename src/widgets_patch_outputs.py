import cairo
import math
from gi.repository import Gtk, Gdk, Gio

class PatchWidget(Gtk.Widget):
    __gtype_name__ = "PatchWidget"

    def __init__(self, universe, output, patch):

        self.type = "Output"
        self.universe = universe
        self.output = output
        self.patch = patch

        self.app = Gio.Application.get_default()

        Gtk.Widget.__init__(self)
        self.scale = 1.0
        self.width = 60 * self.scale
        self.set_size_request(self.width,self.width)
        self.connect('button-press-event', self.on_click)
        self.connect('touch-event', self.on_click)

    def on_click(self, tgt, ev):
        # Deselect selected widgets
        self.app.window.flowbox.unselect_all()
        self.app.patch_outputs_tab.flowbox.unselect_all()
        # Select clicked widget
        child = self.app.patch_outputs_tab.flowbox.get_child_at_index(self.output-1)
        self.app.window.set_focus(child)
        self.app.patch_outputs_tab.flowbox.select_child(child)
        self.app.patch_outputs_tab.last_out_selected = str(self.output)

    def do_draw(self, cr):
        self.width = 60 * self.scale
        self.set_size_request(self.width,self.width)
        allocation = self.get_allocation()
        # paint background
        area = (0, allocation.width, 0, allocation.height)

        if self.patch.outputs[self.universe][self.output - 1] != 0:
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)

            self.draw_rounded_rectangle(cr, area, 10)
        else:
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
                self.draw_rounded_rectangle(cr, area, 10)

        # draw output number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12 * self.scale)
        text = str(self.output) + '.' + str(self.universe)
        (x, y, width, height, dx, dy) = cr.text_extents(text)
        cr.move_to(allocation.width / 2 - width / 2, allocation.height / 4 - (height - 20) / 4)
        cr.show_text(text)

        if self.patch.outputs[self.universe][self.output - 1] != 0:
            # draw channel number
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12 * self.scale)
            text = str(self.patch.outputs[self.universe][self.output - 1])
            (x, y, width, height, dx, dy) = cr.text_extents(text)
            cr.move_to(allocation.width / 2 - width / 2, 3 * (allocation.height / 4 - (height - 20) / 4))
            cr.show_text(text)

        # Draw Output level
        if self.app.dmx.frame[self.universe][self.output - 1]:
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12 * self.scale)
            text = str(self.app.dmx.frame[self.universe][self.output - 1])
            (x, y, width, height, dx, dy) = cr.text_extents(text)
            cr.move_to(allocation.width / 2 - width / 2, allocation.height / 2 - (height - 20) / 2)
            cr.show_text(text)

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.TOUCH_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)

    def draw_rounded_rectangle(self, cr, area, radius):
        a,b,c,d = area
        cr.arc(a + radius, c + radius, radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - radius, c + radius, radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - radius, d - radius, radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + radius, d - radius, radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.fill()
