# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from .common import rounded_rectangle


class GMWidget(Gtk.Widget):
    """Grand Master widget"""

    __gtype_name__ = "GMWidget"

    def __init__(self):
        Gtk.Widget.__init__(self)

        self.width = 60
        self.height = 30
        self.radius = 10
        self.label = ""

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):
        """Draw Grand Master widget

        Args:
            cr: Cairo context
        """
        if App().dmx.grand_master != 255:
            # Draw rounded box
            cr.set_source_rgb(0.7, 0.7, 0.7)
            area = (1, self.width - 2, 1, self.height - 2)
            rounded_rectangle(cr, area, self.radius)
            # Draw Text
            self.label = "GM " + str(round((App().dmx.grand_master / 255) * 100)) + "%"
            cr.set_source_rgb(0.8, 0.3, 0.3)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(11)
            (_x, _y, w, h, _dx, _dy) = cr.text_extents(self.label)
            cr.move_to(
                self.width / 2 - w / 2, self.height / 2 - (h - (self.radius * 2)) / 2
            )
            cr.show_text(self.label)

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
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
