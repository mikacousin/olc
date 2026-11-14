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

import cairo
from gi.repository import Gdk, GObject, Gtk, Pango, PangoCairo

from olc.gtk3.widgets.common import (
    create_pango_layout_for_widget,
    create_system_font_description,
    register_system_font_listener,
    rounded_rectangle,
    rounded_rectangle_fill,
)


# pylint: disable=too-many-instance-attributes
class FlashWidget(Gtk.Widget):
    """Flash widget"""

    __gtype_name__ = "FlashWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_ACTION, None, ())}

    def __init__(
        self, label: str = "", text: str = "None", midi: object = None
    ) -> None:
        super().__init__()
        self.midi = midi
        self.is_learning = False

        self.width = 40
        self.height = 40
        self.radius = 10
        self.font_size = 8

        self.pressed = False
        self.label = label
        self.text = text

        self.set_size_request(self.width, self.height)

        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)

        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        register_system_font_listener(self.queue_draw)

    def on_press(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Flash button pressed"""
        self.pressed = True
        self.queue_draw()

    def on_release(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Flash button released"""
        self.pressed = False
        self.queue_draw()
        self.emit("clicked")

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Flash button

        Args:
            cr: Cairo context
        """
        is_learning = self.is_learning or (
            self.midi is not None and getattr(self.midi, "learning", "") == self.text
        )
        # Draw rounded box
        if self.text == "None":
            cr.set_source_rgb(0.4, 0.4, 0.4)
        elif self.pressed:
            if is_learning:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.3, 0.0)
        elif is_learning:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        area = (1, self.width - 2, 1, self.height - 2)
        rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.radius)
        # Draw Text
        if self.text == "None":
            cr.set_source_rgb(0.5, 0.5, 0.5)
        else:
            cr.set_source_rgb(0.8, 0.8, 0.8)

        if self.label:
            layout = create_pango_layout_for_widget(cr, self.label)
            desc = create_system_font_description()
            desc.set_weight(Pango.Weight.BOLD)
            desc.set_size(int(self.font_size * Pango.SCALE))
            layout.set_font_description(desc)
            layout.set_alignment(Pango.Alignment.CENTER)
            max_width_px = self.width - 6
            layout.set_width(int(max_width_px * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_height(-2)
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            _ink, logical = layout.get_pixel_extents()
            cr.move_to(
                (self.width - max_width_px) / 2.0,
                (self.height - logical.height) / 2.0,
            )
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
