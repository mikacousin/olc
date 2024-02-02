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
from gi.repository import Gtk
from olc.define import App

from .common import rounded_rectangle_fill


class CurveWidget(Gtk.Button):
    """Curve widget"""

    __gtype_name__ = "CurveWidget"

    def __init__(self, curve: int):
        super().__init__()
        self.curve_nb = curve
        self.curve = App().lightshow.curves.get_curve(curve)

        self.connect("clicked", self.on_click)

    def on_click(self, _button) -> None:
        """Button clicked

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def do_draw(self, cr):
        """Draw curve

        Args:
            cr: Cairo context
        """
        self.set_size_request(80, 80)
        width = self.get_allocation().width
        height = self.get_allocation().height
        if isinstance(self.get_parent(), Gtk.FlowBoxChild):
            if self.get_parent().is_selected():
                cr.set_source_rgba(0.6, 0.4, 0.1, 1.0)
            else:
                cr.set_source_rgba(0.3, 0.3, 0.3, 1.0)
        else:
            state = self.get_state_flags()
            if state & Gtk.StateFlags.ACTIVE:
                cr.set_source_rgba(0.5, 0.3, 0.0, 1.0)
            else:
                cr.set_source_rgba(0.3, 0.3, 0.3, 1.0)
        area = (0, width, 0, height)
        rounded_rectangle_fill(cr, area, 10)
        cr.set_line_width(2)
        cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        cr.move_to(0, height - self.curve.values[0])
        for x, y in self.curve.values.items():
            cr.line_to((x / 255) * width, height - ((y / 255) * height))
        cr.stroke()
