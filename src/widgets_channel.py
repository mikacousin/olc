import cairo
from gi.repository import Gtk, Gdk, Gio


class ChannelWidget(Gtk.Widget):
    __gtype_name__ = "ChannelWidget"

    def __init__(self, channel, level, next_level):
        Gtk.Widget.__init__(self)

        self.channel = str(channel)
        self.level = level
        self.next_level = next_level
        self.clicked = False
        self.color_level_red = 0.9
        self.color_level_green = 0.9
        self.color_level_blue = 0.9
        self.scale = 1.0
        self.width = 80 * self.scale

        self.app = Gio.Application.get_default()

        self.percent_level = self.app.settings.get_boolean("percent")

        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)
        self.set_size_request(self.width, self.width)

    def on_click(self, tgt, ev):
        # Select clicked widget
        flowboxchild = tgt.get_parent()
        flowbox = flowboxchild.get_parent()

        self.app.window.set_focus(flowboxchild)
        if flowboxchild.is_selected():
            flowbox.unselect_child(flowboxchild)
        else:
            flowbox.select_child(flowboxchild)
            self.app.window.last_chan_selected = str(int(self.channel) - 1)

    def do_draw(self, cr):
        self.width = 80 * self.scale
        self.set_size_request(self.width, self.width)

        self.percent_level = Gio.Application.get_default().settings.get_boolean(
            "percent"
        )

        allocation = self.get_allocation()

        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)

        # paint background
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgba(*list(bg_color))
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

        # draw rectangle
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()
        # draw background
        bg = Gdk.RGBA()
        # TODO: Get background color
        bg.parse("#33393B")
        cr.set_source_rgba(*list(bg))
        # cr.rectangle(4, 4, allocation.width-8, 72)
        cr.rectangle(4, 4, allocation.width - 8, allocation.height - 8)
        cr.fill()
        # draw background of channel number
        flowboxchild = self.get_parent()
        if flowboxchild.is_selected():
            cr.set_source_rgb(0.4, 0.4, 0.4)
            cr.rectangle(4, 4, allocation.width - 8, 18 * self.scale)
            cr.fill()
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
            cr.rectangle(4, 4, allocation.width - 8, 18 * self.scale)
            cr.fill()
        # draw channel number
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12 * self.scale)
        cr.move_to(50 * self.scale, 15 * self.scale)
        cr.show_text(self.channel)
        # draw level
        cr.set_source_rgb(
            self.color_level_red, self.color_level_green, self.color_level_blue
        )
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13 * self.scale)
        cr.move_to(6 * self.scale, 48 * self.scale)
        if self.level != 0 or self.next_level != 0:  # Don't show 0 level
            if self.percent_level:
                if self.level == 255:
                    cr.show_text("F")
                else:
                    # Level in %
                    cr.show_text(str(int(round((self.level / 255) * 100))))
            else:
                cr.show_text(str(self.level))  # Level in 0 to 255 value
        # draw level bar
        cr.rectangle(
            allocation.width - 9,
            allocation.height - 2,
            6 * self.scale,
            -((50 / 255) * self.scale) * self.level,
        )
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()
        # draw down icon
        if self.next_level < self.level:
            offset_x = 6 * self.scale
            offset_y = -6 * self.scale
            cr.move_to(
                offset_x + 11 * self.scale,
                offset_y + allocation.height - 6 * self.scale,
            )
            cr.line_to(
                offset_x + 6 * self.scale,
                offset_y + allocation.height - 16 * self.scale,
            )
            cr.line_to(
                offset_x + 16 * self.scale,
                offset_y + allocation.height - 16 * self.scale,
            )
            cr.close_path()
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.fill()
            cr.select_font_face(
                "Monaco", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            cr.set_font_size(10 * self.scale)
            cr.move_to(
                offset_x + (24 * self.scale),
                offset_y + allocation.height - (6 * self.scale),
            )
            if self.percent_level:
                if self.next_level == 255:
                    cr.show_text("F")
                else:
                    # Level in %
                    cr.show_text(str(int(round((self.next_level / 255) * 100))))
            else:
                cr.show_text(str(self.next_level))  # Level in 0 to 255 value
        # draw up icon
        if self.next_level > self.level:
            offset_x = 6 * self.scale
            offset_y = 15 * self.scale
            cr.move_to(offset_x + 11 * self.scale, offset_y + 6 * self.scale)
            cr.line_to(offset_x + 6 * self.scale, offset_y + 16 * self.scale)
            cr.line_to(offset_x + 16 * self.scale, offset_y + 16 * self.scale)
            cr.close_path()
            cr.set_source_rgb(0.9, 0.5, 0.5)
            cr.fill()
            # cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.select_font_face(
                "Monaco", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            cr.set_font_size(10 * self.scale)
            cr.move_to(offset_x + (24 * self.scale), offset_y + (16 * self.scale))
            if self.percent_level:
                if self.next_level == 255:
                    cr.show_text("F")
                else:
                    # Level in %
                    cr.show_text(str(int(round((self.next_level / 255) * 100))))
            else:
                cr.show_text(str(self.next_level))  # Level in 0 to 255 value

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
