from gi.repository import Gtk, Gdk
import cairo

class ChanelWidget(Gtk.Widget):
    __gtype_name__ = 'ChanelWidget'

    def __init__(self, chanel, level, next_level):
        Gtk.Widget.__init__(self)
        self.chanel = str(chanel)
        self.level = level
        self.next_level = next_level
        self.set_size_request(80, 80)

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
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL
        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)
        self.set_realized(True)
        window.set_background_pattern(None)

if __name__ == "__main__":
    w = Gtk.Window()
    # Change to dark theme
    settings = Gtk.Settings.get_default()
    settings.set_property('gtk-application-prefer-dark-theme', True)
    table = Gtk.Table(10, 6, True)
    w.add(table)
    i = 1
    for row in range (6):
        for col in range (10):
            chanel = ChanelWidget(i, i*2, 30)
            table.attach(chanel, col, col+1, row, row+1, Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL,
                    Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, 2, 2)
            i += 1
    w.show_all()
    w.present()
    import signal    # enable Ctrl-C since there is no menu to quit
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Gtk.main()
