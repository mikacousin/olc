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
class PauseWidget(Gtk.Widget):
    """Pause button widget"""

    __gtype_name__ = "PauseWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(
        self,
        label: str = "",
        text: str = "None",
        shortcut_text: str = "",
    ) -> None:
        super().__init__()
        self.is_learning = False
        self.shortcut_text = shortcut_text
        self.show_shortcut = False

        self.width = 50
        self.height = 50
        self.radius = 10
        self.font_size = 10

        self.btn_pressed = False
        self.label = label
        self.text = text

        self.set_size_request(self.width, self.height)

        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)

        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        register_system_font_listener(self.queue_draw)

    def on_press(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Button pressed"""
        self.btn_pressed = True
        self.queue_draw()

    def on_release(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Button released"""
        self.emit("clicked")

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Pause button, lightshow: LightShow | None = None

        Args:
            cr: Cairo context
        """
        if self.text == "None":
            cr.set_source_rgb(0.4, 0.4, 0.4)
        elif self.btn_pressed:
            if self.is_learning:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.3, 0.0)
        elif self.is_learning:
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

        has_badge = bool(self.show_shortcut and self.shortcut_text)
        if self.label:
            layout = create_pango_layout_for_widget(cr, self.label)
            desc = create_system_font_description()
            desc.set_weight(Pango.Weight.BOLD)
            desc.set_size(int(self.font_size * Pango.SCALE))
            layout.set_font_description(desc)
            layout.set_alignment(Pango.Alignment.CENTER)
            _ink, logical = layout.get_pixel_extents()
            y_offset = 4.0 if has_badge else 0.0
            cr.move_to(
                (self.width - logical.width) / 2.0,
                (self.height - logical.height) / 2.0 - y_offset,
            )
            PangoCairo.show_layout(cr, layout)

        # Draw shortcut key badge if enabled
        if has_badge:
            cr.set_source_rgb(1.0, 0.85, 0.2)  # warm gold / amber
            badge_layout = create_pango_layout_for_widget(cr, self.shortcut_text)
            bdesc = create_system_font_description()
            bdesc.set_weight(Pango.Weight.NORMAL)
            badge_size = 7.5 if len(self.shortcut_text) > 4 else 8.5
            bdesc.set_size(int(badge_size * Pango.SCALE))
            badge_layout.set_font_description(bdesc)
            _bink, blogical = badge_layout.get_pixel_extents()
            bw = blogical.width
            badge_x = max(2.0, min(float(self.width - bw - 4), (self.width - bw) / 2.0))
            cr.move_to(badge_x, float(self.height - blogical.height - 3))
            PangoCairo.show_layout(cr, badge_layout)

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
