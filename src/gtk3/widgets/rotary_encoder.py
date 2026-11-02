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
"""Endless rotary encoder wheel widget for physical parameter adjustment."""

from __future__ import annotations

import math
from typing import Any, Callable, Optional

import cairo
from gi.repository import Gdk, Gtk


# pylint: disable=too-many-instance-attributes
class RotaryEncoderWidget(Gtk.DrawingArea):
    """Console-style endless rotary encoder wheel with circular drag and scroll."""

    def __init__(
        self,
        label: str,
        on_delta: Callable[[float, bool], None],
        size: int = 96,
    ) -> None:
        super().__init__()
        self.label = label
        self.value_text = "0.0°"
        self._on_delta = on_delta
        self.angle_rad = -math.pi / 2.0
        self._last_pointer_angle: Optional[float] = None
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(False)
        self.set_vexpand(False)

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_MOTION_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
        )
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_release)
        self.connect("scroll-event", self._on_scroll)

    def set_value_text(self, text: str) -> None:
        """Update the readout text drawn in the center of the encoder."""
        self.value_text = text
        self.queue_draw()

    def _center(self) -> tuple[float, float]:
        alloc = self.get_allocation()
        return alloc.width / 2.0, alloc.height / 2.0

    def _on_press(self, _widget: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        cx, cy = self._center()
        self._last_pointer_angle = math.atan2(event.y - cy, event.x - cx)
        return True

    def _on_release(self, _widget: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self._last_pointer_angle = None
        return True

    def _on_motion(self, _widget: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        cx, cy = self._center()
        cur_angle = math.atan2(event.y - cy, event.x - cx)
        if self._last_pointer_angle is None:
            self._last_pointer_angle = cur_angle
            return True
        d_angle = (cur_angle - self._last_pointer_angle + math.pi) % (
            2.0 * math.pi
        ) - math.pi
        self._last_pointer_angle = cur_angle
        if abs(d_angle) < 1e-4:
            return True
        self.angle_rad = (self.angle_rad + d_angle) % (2.0 * math.pi)
        is_shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        self._on_delta(d_angle / (2.0 * math.pi), is_shift)
        self.queue_draw()
        return True

    def _on_scroll(self, _widget: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        is_shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        step = 0.0
        has_dir, direction = event.get_scroll_direction()
        if has_dir:
            if direction == Gdk.ScrollDirection.UP:
                step = 1.0
            elif direction == Gdk.ScrollDirection.DOWN:
                step = -1.0
        if step == 0.0 and hasattr(event, "get_scroll_deltas"):
            has_deltas, _dx, dy = event.get_scroll_deltas()
            if has_deltas and abs(dy) > 1e-3:
                step = -float(dy)
        if step != 0.0:
            d_rad = step * math.radians(10.0)
            self.angle_rad = (self.angle_rad + d_rad) % (2.0 * math.pi)
            self._on_delta(step / 36.0, is_shift)
            self.queue_draw()
        return True

    def do_draw(self, cr: cairo.Context) -> bool:  # pylint: disable=too-many-locals
        """Render the rotary encoder wheel, knurl ticks, LED dot, and readout."""
        alloc = self.get_allocation()
        cx = alloc.width / 2.0
        cy = alloc.height / 2.0
        radius = min(cx, cy) - 4.0

        # Outer encoder bezel
        cr.new_sub_path()
        cr.arc(cx, cy, radius, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(0.14, 0.16, 0.18)
        cr.fill_preserve()
        cr.set_source_rgba(0.45, 0.50, 0.55, 0.85)
        cr.set_line_width(1.5)
        cr.stroke()

        # Rotating knurl ticks around encoder rim
        num_ticks = 24
        for idx in range(num_ticks):
            a = self.angle_rad + idx * (2.0 * math.pi / num_ticks)
            r_in = radius - 6.5
            r_out = radius - 2.0
            cr.move_to(cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
            cr.line_to(cx + math.cos(a) * r_out, cy + math.sin(a) * r_out)
        cr.set_source_rgba(0.65, 0.72, 0.78, 0.65)
        cr.set_line_width(1.2)
        cr.stroke()

        # Inner cap
        cap_r = radius - 9.0
        cr.new_sub_path()
        cr.arc(cx, cy, cap_r, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(0.20, 0.22, 0.25)
        cr.fill_preserve()
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.9)
        cr.set_line_width(1.2)
        cr.stroke()

        # Finger dimple / LED indicator rotating with wheel
        dimple_r = cap_r - 7.0
        dx = cx + math.cos(self.angle_rad) * dimple_r
        dy = cy + math.sin(self.angle_rad) * dimple_r
        cr.new_sub_path()
        cr.arc(dx, dy, 3.2, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(0.25, 0.88, 0.95)
        cr.fill()

        # Center parameter label & physical value readout
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(9.5)
        cr.set_source_rgba(0.75, 0.82, 0.88, 0.95)
        ext_lbl = cr.text_extents(self.label)
        cr.move_to(cx - ext_lbl.width / 2.0 - ext_lbl.x_bearing, cy - 3.0)
        cr.show_text(self.label)

        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        cr.set_font_size(9.0)
        cr.set_source_rgb(0.95, 0.95, 0.95)
        disp = self.value_text.replace(" [Multi]", "")
        ext_val = cr.text_extents(disp)
        cr.move_to(cx - ext_val.width / 2.0 - ext_val.x_bearing, cy + 10.0)
        cr.show_text(disp)
        return False
