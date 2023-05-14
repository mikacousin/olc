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
from gi.repository import Gtk
from olc.define import App


class EditCurveWidget(Gtk.DrawingArea):
    """Curve edition widget"""

    __gtype_name__ = "EditCurveWidget"

    def __init__(self, curve: int):
        super().__init__()
        self.delta = 20
        self.curve_nb = curve
        self.curve = App().curves.get_curve(curve)
        self.set_size_request(1000, 500)

    def do_draw(self, cr):
        """Draw Edit Curve Widget

        Args:
            cr: Cairo context
        """
        width = self.get_allocation().width
        height = self.get_allocation().height
        cr.set_source_rgba(0.3, 0.3, 0.3, 1.0)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        cr.set_line_width(3)
        cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        cr.move_to(self.delta, self.delta)
        cr.line_to(self.delta, height - self.delta)
        cr.line_to(width - self.delta, height - self.delta)
        cr.stroke()
        cr.set_line_width(1)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(8)
        for x in range(0, 256, 5):
            cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
            cr.move_to(
                round((x / 255) * (width - (self.delta * 2))) + self.delta, self.delta
            )
            cr.line_to(
                round((x / 255) * (width - (self.delta * 2))) + self.delta,
                height - self.delta,
            )
            cr.move_to(
                self.delta, round((x / 255) * (height - (self.delta * 2))) + self.delta
            )
            cr.line_to(
                width - self.delta,
                round((x / 255) * (height - (self.delta * 2))) + self.delta,
            )
            cr.stroke()
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            text = str(x)
            (_x, _y, t_width, t_height, _dx, _dy) = cr.text_extents(text)
            cr.move_to(
                round((x / 255) * (width - (self.delta * 2)))
                + self.delta
                - (t_width / 2),
                height - 8,
            )
            cr.show_text(text)
            cr.move_to(
                2,
                height
                - self.delta
                - round((x / 255) * (height - (self.delta * 2)))
                + (t_height / 2),
            )
            cr.show_text(text)
        cr.set_line_width(2)
        cr.set_source_rgba(0.5, 0.3, 0.0, 1.0)
        cr.move_to(self.delta, height - self.delta - self.curve.values[0])
        for x, y in self.curve.values.items():
            cr.line_to(
                (x / 255) * (width - (self.delta * 2)) + self.delta,
                height - self.delta - ((y / 255) * (height - (self.delta * 2))),
            )
        cr.stroke()
