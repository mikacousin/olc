# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
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
import typing

import cairo
from gi.repository import Gdk, Gtk
from olc.track_channels import TrackChannelsTab

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.lightshow import LightShow
    from olc.tabs_manager import Tabs
    from olc.window import Window


# pylint: disable=too-many-instance-attributes
class ChannelWidget(Gtk.DrawingArea):
    """Channel widget"""

    __gtype_name__ = "ChannelWidget"

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        channel: int,
        level: int,
        next_level: int,
        lightshow: LightShow,
        settings: Gio.Settings,
        window: Window,
        tabs: Tabs,
    ) -> None:
        super().__init__()
        self.lightshow = lightshow
        self.settings = settings
        self.window = window
        self.tabs = tabs

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

    def on_click(self, target: Gtk.Widget, event: Gdk.EventButton) -> None:
        """Select clicked widget

        Args:
            target: Target
            event: Gdk.EventButton or Gdk.EventTouch
        """
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        flowboxchild = target.get_parent()
        flowbox = flowboxchild.get_parent()
        channels_view = flowbox.get_parent().get_parent().get_parent()

        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            self.window.commandline.set_string(str(self.channel))
            channels_view.select_thru()
        elif flowboxchild.is_selected():
            flowbox.unselect_child(flowboxchild)
        else:
            flowbox.select_child(flowboxchild)
            channels_view.last_selected_channel = self.channel
        # If Main channels view, update Track Channels if opened
        if (
            channels_view is self.window.live_view.channels_view
            and self.tabs.tabs["track_channels"]
        ):
            track_channels = typing.cast(
                TrackChannelsTab, self.tabs.tabs["track_channels"]
            )  # Avoid circular import
            track_channels.update_display()

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw widget

        Args:
            cr: Cairo context
        """
        self.width = 80 * self.scale
        self.set_size_request(self.width, self.width)
        allocation = self.get_allocation()
        percent_level = self.settings.get_boolean("percent")

        self._draw_background(cr, allocation)
        self._draw_channel_number(cr)
        self._draw_level(cr, percent_level)
        self._draw_level_bar(cr, allocation)
        self._draw_next_level(cr, percent_level)
        return False

    def _draw_background(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw background"""
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
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

    def _draw_channel_number(self, cr: cairo.Context) -> None:
        """Draw channel number"""
        cr.set_source_rgb(0.9, 0.6, 0.2)
        # Independent
        if int(self.channel) in self.lightshow.independents.get_channels():
            cr.set_source_rgb(0.5, 0.5, 0.8)
        # Not patched
        if not self.lightshow.patch.is_patched(int(self.channel)):
            cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12 * self.scale)
        cr.move_to(50 * self.scale, 15 * self.scale)
        cr.show_text(self.channel)

    def _draw_level(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw level"""
        cr.set_source_rgb(
            self.color_level.get("red"),
            self.color_level.get("green"),
            self.color_level.get("blue"),
        )
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(13 * self.scale)
        cr.move_to(6 * self.scale, 48 * self.scale)
        # Don't show level 0
        if self.level != 0 or self.next_level != 0:
            if percent_level:
                if self.level == 255:
                    cr.show_text("F")
                else:
                    # Level %
                    cr.show_text(str(round((self.level / 256) * 100)))
            else:
                # Level 0 to 255 value
                cr.show_text(str(self.level))

    def _draw_level_bar(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw level bar"""
        cr.rectangle(
            allocation.width - 9,
            self.width - 4,
            6 * self.scale,
            -((50 / 255) * self.scale) * self.level,
        )
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()

    def _draw_next_level(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw next level indicator"""
        # Don't draw next level if channel is in a independent
        if int(self.channel) in self.lightshow.independents.get_channels():
            return
        if self.next_level < self.level:
            self._draw_down_icon(cr, percent_level)
        if self.next_level > self.level:
            self._draw_up_icon(cr, percent_level)

    def _draw_down_icon(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw down icon"""
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

        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        cr.set_font_size(10 * self.scale)
        cr.move_to(
            offset_x + (24 * self.scale),
            offset_y + self.width - (6 * self.scale),
        )
        self._draw_next_level_text(cr, percent_level)

    def _draw_up_icon(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw up icon"""
        offset_x = 6 * self.scale
        offset_y = 15 * self.scale
        cr.move_to(offset_x + 11 * self.scale, offset_y + 6 * self.scale)
        cr.line_to(offset_x + 6 * self.scale, offset_y + 16 * self.scale)
        cr.line_to(offset_x + 16 * self.scale, offset_y + 16 * self.scale)
        cr.close_path()
        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.fill()

        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        cr.set_font_size(10 * self.scale)
        cr.move_to(offset_x + (24 * self.scale), offset_y + (16 * self.scale))
        self._draw_next_level_text(cr, percent_level)

    def _draw_next_level_text(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw text for next level"""
        if percent_level:
            if self.next_level == 255:
                cr.show_text("F")
            else:
                cr.show_text(str(int(round((self.next_level / 255) * 100))))
        else:
            cr.show_text(str(self.next_level))
