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
"""Interactive 2D Cairo pad for multi-target Pan/Tilt positioning."""

from __future__ import annotations

import math
from typing import Any

import cairo
from gi.repository import Gdk, Gtk


# pylint: disable=too-many-instance-attributes
class PanTiltPadWidget(Gtk.DrawingArea):
    """Interactive 2D Cairo pad for multi-target Pan/Tilt positioning."""

    def __init__(
        self,
        inspector: Any,  # noqa: ANN401
        pan_range: tuple[float, float] = (-270.0, 270.0),
        tilt_range: tuple[float, float] = (-135.0, 135.0),
    ) -> None:
        super().__init__()
        self.inspector = inspector
        self.pan_min, self.pan_max = pan_range
        self.tilt_min, self.tilt_max = tilt_range
        self.set_size_request(200, 160)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(False)
        self.set_vexpand(False)

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_MOTION_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
        )
        self.connect("button-press-event", self._on_pointer_event)
        self.connect("motion-notify-event", self._on_pointer_event)

    def _coords_to_angles(self, x: float, y: float) -> tuple[float, float]:
        alloc = self.get_allocation()
        w = max(1.0, float(alloc.width))
        h = max(1.0, float(alloc.height))
        norm_x = max(0.0, min(1.0, x / w))
        norm_y = max(0.0, min(1.0, 1.0 - (y / h)))
        pan = self.pan_min + norm_x * (self.pan_max - self.pan_min)
        tilt = self.tilt_min + norm_y * (self.tilt_max - self.tilt_min)
        return round(pan, 2), round(tilt, 2)

    def _angles_to_coords(
        self, pan: float, tilt: float, width: float, height: float
    ) -> tuple[float, float]:
        pan_span = (self.pan_max - self.pan_min) or 540.0
        tilt_span = (self.tilt_max - self.tilt_min) or 270.0
        norm_x = max(0.0, min(1.0, (pan - self.pan_min) / pan_span))
        norm_y = max(0.0, min(1.0, (tilt - self.tilt_min) / tilt_span))
        return norm_x * width, (1.0 - norm_y) * height

    def _on_pointer_event(
        self,
        _widget: Gtk.Widget,
        event: Any,  # noqa: ANN401
    ) -> bool:
        pan, tilt = self._coords_to_angles(event.x, event.y)
        self.inspector.set_pad_position(pan, tilt)
        self.queue_draw()
        return True

    def do_draw(self, cr: cairo.Context) -> bool:  # pylint: disable=too-many-locals
        """Render the 2D coordinate grid, satellite ghost points, and Lead reticle."""
        alloc = self.get_allocation()
        w = float(alloc.width)
        h = float(alloc.height)

        # Background
        cr.set_source_rgb(0.14, 0.16, 0.18)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Center crosshair axes
        cr.set_source_rgba(0.4, 0.45, 0.5, 0.6)
        cr.set_line_width(1.0)
        cr.move_to(w / 2.0, 0)
        cr.line_to(w / 2.0, h)
        cr.move_to(0, h / 2.0)
        cr.line_to(w, h / 2.0)
        cr.stroke()

        targets = self.inspector.get_target_points()
        # Draw satellite points first
        for pt in targets:
            if pt["is_lead"]:
                continue
            px, py = self._angles_to_coords(pt["pan"], pt["tilt"], w, h)
            cr.new_sub_path()
            cr.arc(px, py, 5.0, 0, 2 * math.pi)
            cr.set_source_rgba(0.35, 0.75, 0.95, 0.65)
            cr.fill_preserve()
            cr.set_source_rgba(0.8, 0.9, 1.0, 0.85)
            cr.stroke()

            cr.select_font_face(
                "DejaVu Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL
            )
            cr.set_font_size(9.0)
            cr.move_to(px + 6.0, py - 4.0)
            cr.show_text(f"#{pt['device_id']}")

        # Draw Lead Fixture reticle on top
        for pt in targets:
            if not pt["is_lead"]:
                continue
            px, py = self._angles_to_coords(pt["pan"], pt["tilt"], w, h)
            cr.new_sub_path()
            cr.arc(px, py, 6.5, 0, 2 * math.pi)
            cr.set_source_rgb(0.2, 0.95, 0.4)
            cr.set_line_width(2.0)
            cr.stroke()

            cr.move_to(px - 10.0, py)
            cr.line_to(px + 10.0, py)
            cr.move_to(px, py - 10.0)
            cr.line_to(px, py + 10.0)
            cr.stroke()

            cr.select_font_face(
                "DejaVu Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
            )
            cr.set_font_size(10.0)
            cr.move_to(px + 8.0, py + 4.0)
            cr.show_text(f"#{pt['device_id']}")

        return False
