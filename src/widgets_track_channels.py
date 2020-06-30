import math
import cairo
from gi.repository import Gtk, Gdk, Gio


class TrackChannelsHeader(Gtk.Widget):
    __gtype_name__ = "TrackChannelsHeader"

    def __init__(self, channels):
        Gtk.Widget.__init__(self)

        self.channels = channels
        self.width = 535 + (len(channels) * 65)
        self.height = 60
        self.radius = 10

        self.app = Gio.Application.get_default()

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):

        # Draw Step box
        area = (0, 60, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Step text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str("Step"))
        cr.move_to(60 / 2 - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text(str("Step"))

        # Draw Memory box
        cr.move_to(65, 0)
        area = (65, 125, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Memory text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str("Memory"))
        cr.move_to(65 + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
        cr.show_text(str("Memory"))

        # Draw Text box
        cr.move_to(130, 0)
        area = (130, 530, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str("Text"))
        cr.move_to(135, 60 / 2 - (h - 20) / 2)
        cr.show_text(str("Text"))

        for i, channel in enumerate(self.channels):
            # Draw Level boxes
            cr.move_to(535 + (i * 65), 0)
            area = (535 + (i * 65), 595 + (i * 65), 0, 60)
            cr.set_source_rgb(0.2, 0.3, 0.2)
            self.draw_rounded_rectangle(cr, area, self.radius)

            # Draw Channel number
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face(
                "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
            )
            cr.set_font_size(12)
            (x, y, w, h, dx, dy) = cr.text_extents(str(channel + 1))
            cr.move_to(535 + (i * 65) + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
            cr.show_text(str(channel + 1))

    def draw_rounded_rectangle(self, cr, area, radius):
        a, b, c, d = area
        cr.arc(a + radius, c + radius, radius, 2 * (math.pi / 2), 3 * (math.pi / 2))
        cr.arc(b - radius, c + radius, radius, 3 * (math.pi / 2), 4 * (math.pi / 2))
        cr.arc(b - radius, d - radius, radius, 0 * (math.pi / 2), 1 * (math.pi / 2))
        cr.arc(a + radius, d - radius, radius, 1 * (math.pi / 2), 2 * (math.pi / 2))
        cr.close_path()
        cr.fill()

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


class TrackChannelsWidget(Gtk.Widget):
    __gtype_name__ = "TrackChannelsWidget"

    def __init__(self, step, memory, text, levels):
        Gtk.Widget.__init__(self)

        self.step = step
        self.memory = memory
        self.text = text
        self.levels = levels
        self.width = 535 + (len(self.levels) * 65)
        self.height = 60
        self.radius = 10

        self.app = Gio.Application.get_default()

        self.percent_level = self.app.settings.get_boolean("percent")

        self.set_size_request(self.width, self.height)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, tgt, ev):
        self.app.track_channels_tab.flowbox.unselect_all()
        child = self.app.track_channels_tab.flowbox.get_child_at_index(self.step)
        self.app.window.set_focus(child)
        self.app.track_channels_tab.flowbox.select_child(child)
        self.app.track_channels_tab.last_step_selected = str(self.step)
        chan = int((ev.x - 535) / 65)
        if 0 <= chan < len(self.levels):
            self.app.track_channels_tab.channel_selected = chan

    def do_draw(self, cr):

        self.set_size_request(535 + (len(self.levels) * 65), self.height)

        """
        # Draw Grey background if selected
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.2, 0.2, 0.2)
            area = (0, 800, 0, 60)
            self.draw_rounded_rectangle(cr, area, self.radius)
        """

        # Draw Step box
        area = (0, 60, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Step number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.step))
        cr.move_to(60 / 2 - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text(str(self.step))

        # Draw Memory box
        cr.move_to(65, 0)
        area = (65, 125, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Memory number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.memory))
        cr.move_to(65 + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
        cr.show_text(str(self.memory))

        # Draw Text box
        cr.move_to(130, 0)
        area = (130, 530, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(self.text)
        cr.move_to(135, 60 / 2 - (h - 20) / 2)
        cr.show_text(self.text)

        for i, lvl in enumerate(self.levels):
            # Draw Level boxes
            cr.move_to(535 + (i * 65), 0)
            area = (535 + (i * 65), 595 + (i * 65), 0, 60)
            if (
                self.get_parent().is_selected()
                and i == self.app.track_channels_tab.channel_selected
            ):
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)
            self.draw_rounded_rectangle(cr, area, self.radius)

            # Draw Level number
            if lvl:
                if self.percent_level:
                    level = str(int(round(((lvl / 255) * 100))))
                else:
                    level = str(lvl)
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.select_font_face(
                    "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
                )
                cr.set_font_size(12)
                (x, y, w, h, dx, dy) = cr.text_extents(level)
                cr.move_to(535 + (i * 65) + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
                cr.show_text(level)

    def draw_rounded_rectangle(self, cr, area, radius):
        a, b, c, d = area
        cr.arc(a + radius, c + radius, radius, 2 * (math.pi / 2), 3 * (math.pi / 2))
        cr.arc(b - radius, c + radius, radius, 3 * (math.pi / 2), 4 * (math.pi / 2))
        cr.arc(b - radius, d - radius, radius, 0 * (math.pi / 2), 1 * (math.pi / 2))
        cr.arc(a + radius, d - radius, radius, 1 * (math.pi / 2), 2 * (math.pi / 2))
        cr.close_path()
        cr.fill()

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
