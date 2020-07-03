import math
import cairo
from gi.repository import Gtk, Gdk

from olc.define import App
from olc.widgets import rounded_rectangle_fill


class PatchChannelHeader(Gtk.Widget):
    __gtype_name__ = "PatchChannelHeader"

    def __init__(self):
        Gtk.Widget.__init__(self)

        self.width = 600
        self.height = 60
        self.radius = 10
        self.channel = "Channel"
        self.outputs = "Outputs"

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):

        # Draw channel box
        area = (0, 60, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Channel text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(self.channel)
        cr.move_to(60 / 2 - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text(self.channel)

        # Draw outputs box
        cr.move_to(65, 0)
        area = (65, 600, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Outputs text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(self.outputs)
        cr.move_to(((65 + 600) / 2) - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text(self.outputs)

        # Draw another box
        cr.move_to(605, 0)
        area = (605, 800, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw text text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents("Text")
        cr.move_to(605 + (200 / 2) - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text("Text")

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


class PatchChannelWidget(Gtk.Widget):
    __gtype_name__ = "PatchChannelWidget"

    def __init__(self, channel, patch):
        Gtk.Widget.__init__(self)

        self.channel = channel
        self.patch = patch
        self.width = 600
        self.height = 60
        self.radius = 10

        self.set_size_request(self.width, self.height)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, tgt, ev):
        App().patch_channels_tab.flowbox.unselect_all()
        child = App().patch_channels_tab.flowbox.get_child_at_index(self.channel - 1)
        App().window.set_focus(child)
        App().patch_channels_tab.flowbox.select_child(child)
        # App().patch_channels_tab.last_out_selected = str(self.channels)

    def do_draw(self, cr):
        # self.set_size_request(self.width, self.height)

        # Draw Grey background if selected
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.2, 0.2, 0.2)
            area = (0, 800, 0, 60)
            rounded_rectangle_fill(cr, area, self.radius)

        # Draw channel box
        area = (0, 60, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Channel number
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.channel))
        cr.move_to(60 / 2 - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text(str(self.channel))

        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.move_to(65, 30)
        area = (65, 600, 0, 60)
        a, b, c, d = area
        cr.arc(
            a + self.radius,
            c + self.radius,
            self.radius,
            2 * (math.pi / 2),
            3 * (math.pi / 2),
        )
        cr.arc(
            b - self.radius,
            c + self.radius,
            self.radius,
            3 * (math.pi / 2),
            4 * (math.pi / 2),
        )
        cr.arc(
            b - self.radius,
            d - self.radius,
            self.radius,
            0 * (math.pi / 2),
            1 * (math.pi / 2),
        )
        cr.arc(
            a + self.radius,
            d - self.radius,
            self.radius,
            1 * (math.pi / 2),
            2 * (math.pi / 2),
        )
        cr.close_path()
        cr.stroke()

        # Draw outputs boxes
        nb_outputs = len(self.patch.channels[self.channel - 1])

        if nb_outputs <= 8:
            for i, item in enumerate(self.patch.channels[self.channel - 1]):
                univ = item[1]
                output = item[0]
                if output != 0:
                    area = (65 + (i * 65), 125 + (i * 65), 0, 60)
                    if self.get_parent().is_selected():
                        cr.set_source_rgb(0.4, 0.5, 0.4)
                    else:
                        cr.set_source_rgb(0.3, 0.4, 0.3)
                    cr.move_to(65 + (i * 65), 0)
                    rounded_rectangle_fill(cr, area, self.radius)

                    # Draw Output number
                    cr.set_source_rgb(0.9, 0.9, 0.9)
                    cr.select_font_face(
                        "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
                    )
                    cr.set_font_size(12)
                    (x, y, w, h, dx, dy) = cr.text_extents(
                        str(output) + "." + str(univ)
                    )
                    cr.move_to(65 + (i * 65) + (60 / 2) - w / 2, 60 / 2 - (h - 20) / 2)
                    cr.show_text(str(output) + "." + str(univ))
        else:
            # If more than 8 outputs
            line = 0
            for i, item in enumerate(self.patch.channels[self.channel - 1]):
                if i > 14:
                    line = 2
                output = item[0]
                univ = item[1]
                if output != 0:
                    if line == 0:
                        # First line
                        area = (65 + (i * 35), 95 + (i * 35), 0, 30)
                        if self.get_parent().is_selected():
                            cr.set_source_rgb(0.4, 0.5, 0.4)
                        else:
                            cr.set_source_rgb(0.3, 0.4, 0.3)
                        cr.move_to(65 + (i * 35), 0)
                        rounded_rectangle_fill(cr, area, self.radius / 2)

                        # Draw Output number
                        cr.set_source_rgb(0.9, 0.9, 0.9)
                        cr.select_font_face(
                            "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
                        )
                        cr.set_font_size(10)
                        (x, y, w, h, dx, dy) = cr.text_extents(
                            str(output) + "." + str(univ)
                        )
                        cr.move_to(
                            65 + (i * 35) + (30 / 2) - w / 2, 30 / 2 - (h - 20) / 2
                        )
                        cr.show_text(str(output) + "." + str(univ))
                    else:
                        # Second line
                        j = i - 15
                        area = (65 + (j * 35), 95 + (j * 35), 30, 60)
                        if self.get_parent().is_selected():
                            cr.set_source_rgb(0.4, 0.5, 0.4)
                        else:
                            cr.set_source_rgb(0.3, 0.4, 0.3)
                        cr.move_to(65 + (j * 35), 30)
                        rounded_rectangle_fill(cr, area, self.radius / 2)

                        # Draw Output number
                        cr.set_source_rgb(0.9, 0.9, 0.9)
                        cr.select_font_face(
                            "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
                        )
                        cr.set_font_size(10)
                        if i == 29:
                            # Draw '...' in the last box
                            (x, y, w, h, dx, dy) = cr.text_extents("...")
                            cr.move_to(
                                65 + (j * 35) + (30 / 2) - w / 2,
                                (30 / 2 - (h - 20) / 2) + 30,
                            )
                            cr.show_text("...")
                            break
                        else:
                            (x, y, w, h, dx, dy) = cr.text_extents(
                                str(output) + "." + str(univ)
                            )
                            cr.move_to(
                                65 + (j * 35) + (30 / 2) - w / 2,
                                (30 / 2 - (h - 20) / 2) + 30,
                            )
                            cr.show_text(str(output) + "." + str(univ))

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
