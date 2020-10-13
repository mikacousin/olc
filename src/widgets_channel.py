"""Channel Widget"""

import cairo
import gi
from olc.define import App

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402


class ChannelWidget(Gtk.Widget):
    """Channel widget"""

    __gtype_name__ = "ChannelWidget"

    def __init__(self, channel, level, next_level):
        Gtk.Widget.__init__(self)

        self.channel = str(channel)
        self.level = level
        self.next_level = next_level
        self.clicked = False
        self.color_level = {"red": 0.9, "green": 0.9, "blue": 0.9}
        self.scale = 1.0
        self.width = 80 * self.scale

        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)
        self.set_size_request(self.width, self.width)

    def on_click(self, tgt, event):
        """"Select clicked widget"""
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        flowboxchild = tgt.get_parent()
        flowbox = flowboxchild.get_parent()

        App().window.set_focus(flowboxchild)
        if (
            flowbox is App().window.channels_view.flowbox
            and event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK
        ):
            App().window.keystring = self.channel
            App().window.thru()
        else:
            if flowboxchild.is_selected():
                flowbox.unselect_child(flowboxchild)
            else:
                flowbox.select_child(flowboxchild)
                App().window.last_chan_selected = self.channel
        # If Main channels view, update Track Channels if opened
        if flowbox is App().window.channels_view.flowbox and App().track_channels_tab:
            App().track_channels_tab.update_display()

    def do_draw(self, cr):
        """Draw widget"""
        self.width = 80 * self.scale
        self.set_size_request(self.width, self.width)

        percent_level = App().settings.get_boolean("percent")

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
        background = Gdk.RGBA()
        # TODO: Get background color
        background.parse("#33393B")
        cr.set_source_rgba(*list(background))
        cr.rectangle(4, 4, allocation.width - 8, allocation.height - 8)
        cr.fill()
        # draw background of channel number
        flowboxchild = self.get_parent()
        if flowboxchild.is_selected():
            if App().patch.channels[int(self.channel) - 1][0][0] < 0:
                # Some red for devices
                cr.set_source_rgb(0.5, 0.4, 0.4)
            else:
                cr.set_source_rgb(0.4, 0.4, 0.4)
        else:
            if App().patch.channels[int(self.channel) - 1][0][0] < 0:
                # Some red for devices
                cr.set_source_rgb(0.3, 0.2, 0.2)
            else:
                cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.rectangle(4, 4, allocation.width - 8, 18 * self.scale)
        cr.fill()
        # draw channel number
        cr.set_source_rgb(0.9, 0.6, 0.2)
        if int(self.channel) - 1 in App().independents.get_channels():
            cr.set_source_rgb(0.5, 0.5, 0.8)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12 * self.scale)
        cr.move_to(50 * self.scale, 15 * self.scale)
        cr.show_text(self.channel)
        # draw level
        cr.set_source_rgb(
            self.color_level.get("red"),
            self.color_level.get("green"),
            self.color_level.get("blue"),
        )
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(13 * self.scale)
        cr.move_to(6 * self.scale, 48 * self.scale)
        # Don't show level 0
        if (
            self.level != 0
            or self.next_level != 0
            and int(self.channel) - 1 not in App().independents.get_channels()
        ):
            if percent_level:
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
        # Don't draw next level if channel is in an independent
        if int(self.channel) - 1 in App().independents.get_channels():
            return
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
                "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL
            )
            cr.set_font_size(10 * self.scale)
            cr.move_to(
                offset_x + (24 * self.scale),
                offset_y + allocation.height - (6 * self.scale),
            )
            if percent_level:
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
                "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL
            )
            cr.set_font_size(10 * self.scale)
            cr.move_to(offset_x + (24 * self.scale), offset_y + (16 * self.scale))
            if percent_level:
                if self.next_level == 255:
                    cr.show_text("F")
                else:
                    # Level in %
                    cr.show_text(str(int(round((self.next_level / 255) * 100))))
            else:
                cr.show_text(str(self.next_level))  # Level in 0 to 255 value

    def do_realize(self):
        """Realize widget"""
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
