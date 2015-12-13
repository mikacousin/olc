from gi.repository import Gtk, Gdk
import cairo
import math

class ChanelWidget(Gtk.Widget):
    __gtype_name__ = 'ChanelWidget'

    def __init__(self, chanel, level, next_level):
        Gtk.Widget.__init__(self)

        self.chanel = str(chanel)
        self.level = level
        self.next_level = next_level
        self.clicked = False

        self.connect("button-press-event", self.on_click)
        self.set_size_request(80, 80)

    def on_click(self, tgt, ev):
        if self.clicked:
            self.clicked = False
        else:
            self.clicked = True
        self.queue_draw()

    def do_draw(self, cr):
        # paint background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        allocation = self.get_allocation()

        # dessine un cadre
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()
        # dessine fond pour le numéro de cicuit
        if self.clicked:
            cr.set_source_rgb(0.4, 0.4, 0.4)
            cr.rectangle(1, 1, allocation.width-2, 18)
            cr.fill()
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
            cr.rectangle(1, 1, allocation.width-2, 18)
            cr.fill()
        # draw chanel number
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.move_to(50,15)
        cr.show_text(self.chanel)
        # draw level
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        cr.move_to(6,48)
        cr.show_text(str(self.level))
        # draw level bar
        cr.rectangle(allocation.width-9, allocation.height-2, 6, -(50/255)*self.level)
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()
        # draw down icon
        if self.next_level < self.level:
            offset_x = 6
            offset_y = -6
            cr.move_to(offset_x + 11, offset_y + allocation.height-6)
            cr.line_to(offset_x + 6, offset_y + allocation.height-16)
            cr.line_to(offset_x + 16, offset_y + allocation.height-16)
            cr.close_path()
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.fill()
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            cr.move_to(offset_x + 24, offset_y + allocation.height-6)
            cr.show_text(str(self.next_level))
        # draw up icon
        if self.next_level > self.level:
            offset_x = 6
            offset_y = 15
            cr.move_to(offset_x + 11, offset_y + 6)
            cr.line_to(offset_x + 6, offset_y + 16)
            cr.line_to(offset_x + 16, offset_y + 16)
            cr.close_path()
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.fill()
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            cr.move_to(offset_x + 24, offset_y + 16)
            cr.show_text(str(self.next_level))

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

class SequentialWidget(Gtk.Widget):
    __gtype_name__ = 'SequentialWidget'

    def __init__(self, time_in, time_out):

        self.time_in = time_in
        self.time_out = time_out

        Gtk.Widget.__init__(self)
        self.set_size_request(1000, 300)

        # Change to dark theme
        settings = Gtk.Settings.get_default()
        settings.set_property('gtk-application-prefer-dark-theme', True)

    def do_draw(self, cr):
        if self.time_in > self.time_out:
            self.time_max = self.time_in
            self.time_min = self.time_out
        else:
            self.time_max = self.time_out
            self.time_min = self.time_in

        # paint background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        allocation = self.get_allocation()

        # dessine un cadre
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        # draw time line
        fg_color = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(fg_color));
        cr.set_line_width(1)
        cr.move_to(16, 24)
        cr.line_to(allocation.width-16, 24)
        cr.line_to(allocation.width-16, 18)
        cr.move_to(16, 24)
        cr.line_to(16, 18)
        inter = (allocation.width-32)/self.time_max
        for i in range(self.time_max-1):
            cr.move_to(16+(inter*(i+1)), 24)
            cr.line_to(16+(inter*(i+1)), 18)
        cr.stroke()

        # draw Out line
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.move_to(16, 40)
        cr.line_to(16+(inter*self.time_out), allocation.height-32)
        cr.stroke()
        # draw an arrow at the end
        angle = math.atan2(allocation.height-32 - 40, 16+(inter*self.time_out) - 16)
        arrow_lenght = 12
        arrow_degrees = 10
        end_x = 16+(inter*self.time_out)
        end_y = allocation.height-32
        x1 = 16+(inter*self.time_out) + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = allocation.height-32 + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = 16+(inter*self.time_out) + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = allocation.height-32 + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()

        # draw In line
        cr.move_to(16, allocation.height-32)
        cr.line_to(16+(inter*self.time_in), 40)
        cr.stroke()
        # draw an arrow at the end
        arrow_lenght = 12
        arrow_degrees = 10
        start_x = 16
        start_y = allocation.height-32
        end_x = 16+(inter*self.time_in)
        end_y = 40
        angle = math.atan2(end_y - start_y, end_x - start_x)
        x1 = end_x + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = end_y + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = end_x + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = end_y + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()

        # draw X1 cursor
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.arc(16, 40, 8, 0, 2*math.pi)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        cr.move_to(11, 42)
        cr.show_text("A")
        # draw X2 cursor
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.arc(16, allocation.height-32, 8, 0, 2*math.pi)
        cr.fill()
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        cr.move_to(11, allocation.height-29)
        cr.show_text("B")

        # draw times number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.move_to(12,16)
        cr.show_text("0")
        cr.move_to(allocation.width-24,16)
        cr.show_text(str(self.time_max))
        if self.time_min != self.time_max:
            cr.move_to(12+(inter*self.time_min),16)
            cr.show_text(str(self.time_min))

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL
        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)
        self.set_realized(True)
        window.set_background_pattern(None)

