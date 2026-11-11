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


class ButtonWidget(Gtk.Widget):
    """Button widget"""

    __gtype_name__ = "ButtonWidget"

    __gsignals__ = {"clicked": (GObject.SIGNAL_ACTION, None, ())}

    WIDTH = 50
    HEIGHT = 50
    RADIUS = 10
    FONT_SIZE = 10

    def __init__(
        self, label: str = "", text: str = "None", shortcut_text: str = ""
    ) -> None:
        Gtk.Widget.__init__(self)
        self.is_learning = False

        self.pressed = False
        self.label = label
        self.text = text
        self.shortcut_text = shortcut_text
        self.show_shortcut = False

        self.set_size_request(self.WIDTH, self.HEIGHT)

        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)

        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        self.connect("state-flags-changed", self._on_state_flags_changed)
        register_system_font_listener(self.queue_draw)

    def _on_state_flags_changed(
        self, _widget: Gtk.Widget, _flags: Gtk.StateFlags
    ) -> None:
        """Reset pressed state if widget becomes insensitive."""
        if not self.get_sensitive() and self.pressed:
            self.pressed = False
            self.queue_draw()

    def on_press(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Button pressed"""
        if not self.get_sensitive() and not self.is_learning:
            return
        self.pressed = True
        self.queue_draw()

    def on_release(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Button released"""
        was_pressed = self.pressed
        self.pressed = False
        self.queue_draw()
        if was_pressed and (self.get_sensitive() or self.is_learning):
            self.emit("clicked")

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw button

        Args:
            cr: Cairo context
        """
        # Draw rounded box
        is_disabled = not self.get_sensitive() and not self.is_learning
        if self.text == "None":
            cr.set_source_rgb(0.4, 0.4, 0.4)
        elif is_disabled:
            cr.set_source_rgb(0.12, 0.12, 0.12)
        elif self.pressed:
            if self.is_learning:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.3, 0.0)
        elif self.is_learning:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        area = (1, self.WIDTH - 2, 1, self.HEIGHT - 2)
        rounded_rectangle_fill(cr, area, self.RADIUS)
        if is_disabled:
            cr.set_source_rgb(0.08, 0.08, 0.08)
        else:
            cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.RADIUS)
        # Draw Text via Pango
        if self.text == "None":
            cr.set_source_rgb(0.5, 0.5, 0.5)
        elif is_disabled:
            cr.set_source_rgb(0.35, 0.35, 0.35)
        else:
            cr.set_source_rgb(0.8, 0.8, 0.8)

        has_badge = bool(self.show_shortcut and self.shortcut_text)
        max_width_px = self.WIDTH - 8

        if self.label:
            layout = create_pango_layout_for_widget(cr, self.label)
            desc = create_system_font_description()
            desc.set_weight(Pango.Weight.BOLD)

            lines = self.label.split("\n")
            is_multiline = len(lines) > 1
            font_size_pt = (
                8.5
                if (is_multiline and has_badge)
                else (9.0 if is_multiline else self.FONT_SIZE)
            )
            desc.set_size(int(font_size_pt * Pango.SCALE))
            layout.set_font_description(desc)

            # Auto-scale font down if unconstrained natural width exceeds max_width_px
            _ink, natural_logical = layout.get_pixel_extents()
            natural_w = natural_logical.width
            if natural_w > max_width_px and natural_w > 0:
                scaled_size = max(7.0, font_size_pt * (max_width_px / natural_w))
                desc.set_size(int(scaled_size * Pango.SCALE))
                layout.set_font_description(desc)

            layout.set_alignment(Pango.Alignment.CENTER)
            layout.set_width(int(max_width_px * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            if is_multiline:
                layout.set_spacing(int(1 * Pango.SCALE))

            _ink, logical = layout.get_pixel_extents()
            x_pos = (self.WIDTH - max_width_px) / 2.0
            y_offset = 4.0 if has_badge else 0.0
            y_pos = (self.HEIGHT - logical.height) / 2.0 - y_offset

            cr.move_to(x_pos, y_pos)
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
            badge_x = max(2.0, min(float(self.WIDTH - bw - 4), (self.WIDTH - bw) / 2.0))
            cr.move_to(badge_x, float(self.HEIGHT - blogical.height - 3))
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
