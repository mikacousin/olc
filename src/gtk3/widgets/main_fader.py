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
from __future__ import annotations

import typing

import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from olc.gtk3.widgets.common import (
    create_pango_layout_for_widget,
    create_system_font_description,
    register_system_font_listener,
    rounded_rectangle,
)

if typing.TYPE_CHECKING:
    from olc.core.backends import DMXBackend


class MainFaderWidget(Gtk.Widget):
    """Main Fader widget"""

    __gtype_name__ = "MainFaderWidget"

    def __init__(self, backend: DMXBackend | None) -> None:
        Gtk.Widget.__init__(self)
        self.backend = backend

        self.width = 100
        self.height = 30
        self.radius = 10
        self.label = ""

        self.set_size_request(self.width, self.height)
        register_system_font_listener(self.queue_draw)

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Main Fader widget

        Args:
            cr: Cairo context
        """
        if self.backend:
            is_blackout = bool(getattr(self.backend.dmx, "blackout", False))
            mf_val = float(getattr(self.backend.dmx.main_fader, "value", 1.0))
            if is_blackout or mf_val != 1:
                # Draw rounded box
                cr.set_source_rgb(0.7, 0.2, 0.2)
                area = (1, self.width - 2, 1, self.height - 2)
                rounded_rectangle(cr, area, self.radius)
                # Draw Text
                if is_blackout:
                    self.label = "BLACKOUT"
                    cr.set_source_rgb(1.0, 0.8, 0.8)
                else:
                    self.label = f"Main Fader {round(mf_val * 100)}%"
                    cr.set_source_rgb(0.8, 0.3, 0.3)
                layout = create_pango_layout_for_widget(cr, self.label)
                desc = create_system_font_description()
                desc.set_weight(Pango.Weight.BOLD)
                desc.set_size(int(11 * Pango.SCALE))
                layout.set_font_description(desc)
                _ink, logical = layout.get_pixel_extents()
                x_pos = (self.width - logical.width) / 2.0
                y_pos = (self.height - logical.height) / 2.0
                cr.move_to(x_pos, y_pos)
                PangoCairo.show_layout(cr, layout)
        return False

    def do_realize(self) -> None:
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
