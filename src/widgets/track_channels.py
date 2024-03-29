# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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

from .common import rounded_rectangle_fill


class TrackChannelsHeader(Gtk.Widget):
    """Header widget"""

    __gtype_name__ = "TrackChannelsHeader"

    def __init__(self, channels):
        Gtk.Widget.__init__(self)

        self.channels = channels
        self.width = 535 + (len(channels) * 65)
        self.height = 60
        self.radius = 10

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):
        """Draw header

        Args:
            cr: Cairo context
        """
        # Draw Step box
        area = (0, 60, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Step text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents("Step")
        cr.move_to(60 / 2 - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text("Step")

        # Draw Memory box
        cr.move_to(65, 0)
        area = (65, 125, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Memory text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents("Memory")
        cr.move_to(65 + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
        cr.show_text("Memory")

        # Draw Text box
        cr.move_to(130, 0)
        area = (130, 530, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents("Text")
        cr.move_to(135, 60 / 2 - (h - 20) / 2)
        cr.show_text("Text")

        for i, channel in enumerate(self.channels):
            # Draw Level boxes
            cr.move_to(535 + (i * 65), 0)
            area = (535 + (i * 65), 595 + (i * 65), 0, 60)
            cr.set_source_rgb(0.2, 0.3, 0.2)
            rounded_rectangle_fill(cr, area, self.radius)

            # Draw Channel number
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(12)
            (_x, _y, w, h, _dx, _dy) = cr.text_extents(str(channel + 1))
            cr.move_to(535 + (i * 65) + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
            cr.show_text(str(channel + 1))

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
        attr.event_mask = (self.get_events()
                           | Gdk.EventMask.EXPOSURE_MASK
                           | Gdk.EventMask.BUTTON_PRESS_MASK
                           | Gdk.EventMask.TOUCH_MASK)
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)


class TrackChannelsWidget(Gtk.Widget):
    """Track Channel widget"""

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

        self.set_size_request(self.width, self.height)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, _tgt, event):
        """Widget clicked

        Args:
            event: Gdk.Event
        """
        App().tabs.tabs["track_channels"].flowbox.unselect_all()
        child = App().tabs.tabs["track_channels"].flowbox.get_child_at_index(self.step)
        App().tabs.tabs["track_channels"].flowbox.select_child(child)
        App().tabs.tabs["track_channels"].last_step_selected = str(self.step)
        chan = int((event.x - 535) / 65)
        if 0 <= chan < len(self.levels):
            App().tabs.tabs["track_channels"].channel_selected = chan

    def do_draw(self, cr):
        """Draw widget

        Args:
            cr: Cairo context
        """
        self.set_size_request(535 + (len(self.levels) * 65), self.height)

        # Draw Grey background if selected
        # if self.get_parent().is_selected():
        #     cr.set_source_rgb(0.2, 0.2, 0.2)
        #     area = (0, 800, 0, 60)
        #     rounded_rectangle_fill(cr, area, self.radius)

        # Draw Step number box
        self._draw_step_box(cr)
        # Draw Cue number box
        self._draw_cue_box(cr)
        # Draw Text box
        self._draw_text_box(cr)
        # Draw level boxes
        self._draw_level_boxes(cr)

    def _draw_step_box(self, cr):
        """Draw Step box

        Args:
            cr: Cairo context
        """
        # Draw box
        area = (0, 60, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)
        # Draw Step number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(str(self.step))
        cr.move_to(60 / 2 - w / 2, 60 / 2 - (h - 20) / 2)
        cr.show_text(str(self.step))

    def _draw_cue_box(self, cr):
        """Draw cue box

        Args:
            cr: Cairo context
        """
        # Draw box
        cr.move_to(65, 0)
        area = (65, 125, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)
        # Draw Memory number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(str(self.memory))
        cr.move_to(65 + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
        cr.show_text(str(self.memory))

    def _draw_text_box(self, cr):
        """Draw text box

        Args:
            cr: Cairo context
        """
        # Draw box
        cr.move_to(130, 0)
        area = (130, 530, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)
        # Draw Text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, _w, h, _dx, _dy) = cr.text_extents(self.text)
        cr.move_to(135, 60 / 2 - (h - 20) / 2)
        cr.show_text(self.text)

    def _draw_level_boxes(self, cr):
        """Draw Level boxes

        Args:
            cr: Cairo context
        """
        for i, lvl in enumerate(self.levels):
            # Draw boxes
            cr.move_to(535 + (i * 65), 0)
            area = (535 + (i * 65), 595 + (i * 65), 0, 60)
            if (self.get_parent().is_selected()
                    and i == App().tabs.tabs["track_channels"].channel_selected):
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)
            rounded_rectangle_fill(cr, area, self.radius)

            # Draw Level number
            if lvl:
                level = (str(int(round(
                    ((lvl / 255) *
                     100)))) if App().settings.get_boolean("percent") else str(lvl))

                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.select_font_face("Monaco", cairo.FontSlant.NORMAL,
                                    cairo.FontWeight.BOLD)
                cr.set_font_size(12)
                (_x, _y, w, h, _dx, _dy) = cr.text_extents(level)
                cr.move_to(535 + (i * 65) + (60 / 2 - w / 2), 60 / 2 - (h - 20) / 2)
                cr.show_text(level)

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
        attr.event_mask = (self.get_events()
                           | Gdk.EventMask.EXPOSURE_MASK
                           | Gdk.EventMask.BUTTON_PRESS_MASK
                           | Gdk.EventMask.TOUCH_MASK)
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
