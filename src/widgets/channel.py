# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import cairo
from gi.repository import Gdk, Gtk
from olc.define import App


class ChannelWidget(Gtk.DrawingArea):
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

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_click)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.connect("touch-event", self.on_click)
        self.set_size_request(self.width, self.width)

    def on_click(self, tgt, event):
        """Select clicked widget

        Args:
            tgt: Target
            event: Gdk.EventButton or Gdk.EventTouch
        """
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        flowboxchild = tgt.get_parent()
        flowbox = flowboxchild.get_parent()
        channels_view = flowbox.get_parent().get_parent().get_parent()

        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            channels_view.select_thru(self.channel)
        elif flowboxchild.is_selected():
            flowbox.unselect_child(flowboxchild)
        else:
            flowbox.select_child(flowboxchild)
            channels_view.last_selected_channel = self.channel
        # If Main channels view, update Track Channels if opened
        if (
            channels_view is App().window.live_view.channels_view
            and App().tabs.tabs["track_channels"]
        ):
            App().tabs.tabs["track_channels"].update_display()

    def do_draw(self, cr):
        """Draw widget

        Args:
            cr: Cairo context
        """
        self.width = 80 * self.scale
        self.set_size_request(self.width, self.width)

        percent_level = App().settings.get_boolean("percent")

        allocation = self.get_allocation()

        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)

        # Paint background
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgba(*list(bg_color))
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

        # Draw rectangle
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()
        # Draw background
        background = Gdk.RGBA()
        # TODO: Get background color
        background.parse("#33393B")
        cr.set_source_rgba(*list(background))
        cr.rectangle(4, 4, allocation.width - 8, self.width - 8)
        cr.fill()
        # Draw background of channel number
        flowboxchild = self.get_parent()
        if flowboxchild.is_selected():
            cr.set_source_rgb(0.4, 0.4, 0.4)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.rectangle(4, 4, allocation.width - 8, 18 * self.scale)
        cr.fill()
        # Draw channel number
        # Default color
        cr.set_source_rgb(0.9, 0.6, 0.2)
        # Independent color
        if int(self.channel) in App().independents.get_channels():
            cr.set_source_rgb(0.5, 0.5, 0.8)
        # Not patched color
        if int(self.channel) not in App().patch.channels:
            cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12 * self.scale)
        cr.move_to(50 * self.scale, 15 * self.scale)
        cr.show_text(self.channel)
        # Draw level
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
                    cr.show_text(str(round((self.level / 256) * 100)))
            else:
                cr.show_text(str(self.level))  # Level in 0 to 255 value
        # Draw level bar
        cr.rectangle(
            allocation.width - 9,
            self.width - 4,
            6 * self.scale,
            -((50 / 255) * self.scale) * self.level,
        )
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()
        # Don't draw next level if channel is in an independent
        if int(self.channel) - 1 in App().independents.get_channels():
            return
        # Draw down icon
        if self.next_level < self.level:
            offset_x = 6 * self.scale
            offset_y = -6 * self.scale
            cr.move_to(
                offset_x + 11 * self.scale,
                offset_y + self.width - 6 * self.scale,
            )
            cr.line_to(
                offset_x + 6 * self.scale,
                offset_y + self.width - 16 * self.scale,
            )
            cr.line_to(
                offset_x + 16 * self.scale,
                offset_y + self.width - 16 * self.scale,
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
                offset_y + self.width - (6 * self.scale),
            )
            if percent_level:
                if self.next_level == 255:
                    cr.show_text("F")
                else:
                    # Level in %
                    cr.show_text(str(int(round((self.next_level / 255) * 100))))
            else:
                cr.show_text(str(self.next_level))  # Level in 0 to 255 value
        # Draw up icon
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
