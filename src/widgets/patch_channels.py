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
from .common import rounded_rectangle, rounded_rectangle_fill


# pylint: disable=R0903
class PatchChannelHeader(Gtk.Misc):
    """Header widget"""

    __gtype_name__ = "PatchChannelHeader"

    def __init__(self):
        Gtk.Misc.__init__(self)

        self.width = 600
        self.height = 40
        self.radius = 5
        self.channel = "Channel"
        self.outputs = "Outputs"

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):
        """Draw Header widget

        Args:
            cr: Cairo context
        """
        # Draw channel box
        area = (3, 63, 0, self.height)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Channel text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(self.channel)
        cr.move_to(63 / 2 - w / 2, self.height / 2 - (h - 20) / 2)
        cr.show_text(self.channel)

        # Draw outputs box
        cr.move_to(68, 0)
        area = (68, 600, 0, self.height)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw Outputs text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(self.outputs)
        cr.move_to(((68 + 600) / 2) - w / 2, self.height / 2 - (h - 20) / 2)
        cr.show_text(self.outputs)

        # Draw Text box
        cr.move_to(605, 0)
        area = (605, 800, 0, self.height)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)

        # Draw text text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents("Text")
        cr.move_to(605 + (200 / 2) - w / 2, self.height / 2 - (h - 20) / 2)
        cr.show_text("Text")


class PatchChannelWidget(Gtk.Widget):
    """Patch Channel widget"""

    __gtype_name__ = "PatchChannelWidget"

    def __init__(self, channel, patch):
        Gtk.Widget.__init__(self)

        self.channel = channel
        self.patch = patch
        self.width = 600
        self.height = 40
        self.radius = 5

        self.set_size_request(self.width, self.height)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, _tgt, event):
        """Widget clicked

        Args:
            event: Gdk.Event
        """
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            # Thru
            App().tabs.tabs["patch_channels"].keystring = str(self.channel)
            App().tabs.tabs["patch_channels"].thru()
        else:
            App().tabs.tabs["patch_channels"].flowbox.unselect_all()
            child = (App().tabs.tabs["patch_channels"].flowbox.get_child_at_index(
                self.channel - 1))
            App().tabs.tabs["patch_channels"].flowbox.select_child(child)
            App().tabs.tabs["patch_channels"].last_chan_selected = str(self.channel - 1)

    def do_draw(self, cr):
        """Draw widget

        Args:
            cr: Cairo context
        """
        # Draw Grey background if selected
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.2, 0.2, 0.2)
            area = (0, 800, 0, self.height)
            rounded_rectangle_fill(cr, area, self.radius)
        # Draw channel box
        area = (0, 60, 0, self.height)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        rounded_rectangle_fill(cr, area, self.radius)
        # Draw Channel number
        self._draw_channel_number(cr)
        # Draw a box for outputs
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.move_to(65, self.height / 2)
        area = (65, 600, 0, self.height)
        rounded_rectangle(cr, area, self.radius)
        # Draw patched outputs
        self._draw_output_boxes(cr)

    def _draw_channel_number(self, cr):
        """Draw Channel number

        Args:
            cr: Cairo context
        """
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(str(self.channel))
        cr.move_to(60 / 2 - w / 2, self.height / 2 - (h - 20) / 2)
        cr.show_text(str(self.channel))

    def _draw_output_boxes(self, cr):
        """Draw outputs boxes

        Args:
            cr: Cairo context
        """
        nb_outputs = 0
        if self.channel in App().lightshow.patch.channels:
            if App().lightshow.patch.channels[self.channel] == [[None, None]]:
                return

        if nb_outputs <= 8:
            self._draw_one_line(cr)
        else:
            self._draw_two_lines(cr)

    def _draw_one_line(self, cr):
        """Draw Outputs on a single line

        Args:
            cr: Cairo context
        """
        for i, item in enumerate(App().lightshow.patch.channels[self.channel]):
            output = item[0]
            if output != 0:
                area = (65 + (i * 65), 125 + (i * 65), 0, self.height)
                if self.get_parent().is_selected():
                    cr.set_source_rgb(0.4, 0.5, 0.4)
                else:
                    cr.set_source_rgb(0.3, 0.4, 0.3)
                cr.move_to(65 + (i * 65), 0)
                rounded_rectangle_fill(cr, area, self.radius)

                # Draw Output number
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.select_font_face("Monaco", cairo.FontSlant.NORMAL,
                                    cairo.FontWeight.BOLD)
                cr.set_font_size(12)
                univ = item[1]
                (_x, _y, w, h, _dx, _dy) = cr.text_extents(f"{output}.{univ}")
                cr.move_to(65 + (i * 65) + (60 / 2) - w / 2,
                           self.height / 2 - (h - 20) / 2)
                cr.show_text(f"{output}.{univ}")

    def _draw_two_lines(self, cr):
        """Draw Outputs on two lines

        Args:
            cr: Cairo context
        """
        two_lines = False
        for i, item in enumerate(App().lightshow.patch.channels[self.channel]):
            if i > 15:
                two_lines = True
            output = item[0]
            if output != 0:
                if self.get_parent().is_selected():
                    cr.set_source_rgb(0.4, 0.5, 0.4)
                else:
                    cr.set_source_rgb(0.3, 0.4, 0.3)
                univ = item[1]
                if not two_lines:
                    self._draw_first_line(cr, i, output, univ)
                else:
                    # Second line
                    j = i - 16
                    area = (
                        65 + (j * 32),
                        95 + (j * 32),
                        self.height / 2 + 1,
                        self.height,
                    )
                    cr.move_to(65 + (j * 32), self.height / 2)
                    rounded_rectangle_fill(cr, area, self.radius / 2)

                    # Draw Output number
                    cr.set_source_rgb(0.9, 0.9, 0.9)
                    cr.select_font_face("Monaco", cairo.FontSlant.NORMAL,
                                        cairo.FontWeight.BOLD)
                    cr.set_font_size(10)
                    if i == 31:
                        # Draw '...' in the last box
                        (_x, _y, w, h, _dx, _dy) = cr.text_extents("...")
                        cr.move_to(
                            65 + (j * 32) + (30 / 2) - w / 2,
                            ((self.height / 2) / 2 - (h - 20) / 2) + self.height / 2,
                        )
                        cr.show_text("...")
                        break
                    (_x, _y, w, h, _dx, _dy) = cr.text_extents(f"{output}.{univ}")
                    cr.move_to(
                        65 + (j * 32) + (30 / 2) - w / 2,
                        ((self.height / 2) / 2 - (h - 20) / 2) + self.height / 2,
                    )

                cr.show_text(f"{output}.{univ}")

    def _draw_first_line(self, cr, i, output, univ):
        """Draw First line of outputs

        Args:
            cr: Cairo context
            i: Output number
            output: Output value
            univ: Universe
        """
        area = (65 + (i * 32), 95 + (i * 32), 1, self.height / 2 - 1)
        cr.move_to(65 + (i * 32), 0)
        rounded_rectangle_fill(cr, area, self.radius / 2)

        # Draw Output number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(10)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(f"{output}.{univ}")
        cr.move_to(65 + (i * 32) + (30 / 2) - w / 2,
                   (self.height / 2) / 2 - (h - 20) / 2)

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
