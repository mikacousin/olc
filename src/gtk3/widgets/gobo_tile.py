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
"""GTK3 Cairo/Pixbuf thumbnail widget for gobo slots."""

from __future__ import annotations

import math
from typing import Optional

import cairo
from gi.repository import Gdk, GdkPixbuf, Gtk


def _load_pixbuf(data: Optional[bytes], size: int) -> Optional[GdkPixbuf.Pixbuf]:
    if not data:
        return None
    try:
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        pb = loader.get_pixbuf()
        if pb is None:
            return None
        return pb.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _draw_builtin_pattern(
    cr: cairo.Context, pattern_id: str, cx: float, cy: float, r: float
) -> None:
    cr.set_source_rgb(0.95, 0.96, 0.98)
    if pattern_id == "builtin:open":
        cr.arc(cx, cy, r * 0.82, 0, math.tau)
        cr.fill()
    elif pattern_id == "builtin:stars":
        for i in range(6):
            ang = i * math.tau / 6.0
            cr.arc(
                cx + math.cos(ang) * r * 0.48,
                cy + math.sin(ang) * r * 0.48,
                r * 0.14,
                0,
                math.tau,
            )
            cr.fill()
        cr.arc(cx, cy, r * 0.18, 0, math.tau)
        cr.fill()
    elif pattern_id == "builtin:breakup":
        pts = [
            (-0.35, -0.30, 0.22),
            (0.32, -0.25, 0.18),
            (-0.15, 0.28, 0.25),
            (0.38, 0.26, 0.19),
            (0.0, -0.04, 0.16),
        ]
        for dx, dy, rad in pts:
            cr.arc(cx + dx * r, cy + dy * r, rad * r, 0, math.tau)
            cr.fill()
    elif pattern_id == "builtin:bars":
        for off in (-0.48, -0.16, 0.16, 0.48):
            cr.rectangle(cx + off * r - r * 0.08, cy - r * 0.72, r * 0.16, r * 1.44)
            cr.fill()
    elif pattern_id == "builtin:radial":
        cr.set_line_width(max(1.5, r * 0.12))
        for i in range(8):
            ang = i * math.tau / 8.0
            cr.move_to(cx + math.cos(ang) * r * 0.18, cy + math.sin(ang) * r * 0.18)
            cr.line_to(cx + math.cos(ang) * r * 0.80, cy + math.sin(ang) * r * 0.80)
            cr.stroke()
    elif pattern_id == "builtin:ring":
        cr.set_line_width(max(2.0, r * 0.18))
        cr.arc(cx, cy, r * 0.56, 0, math.tau)
        cr.stroke()
    elif pattern_id == "builtin:grid":
        for gx in (-0.36, 0.0, 0.36):
            for gy in (-0.36, 0.0, 0.36):
                s = r * 0.20
                cr.rectangle(cx + gx * r - s * 0.5, cy + gy * r - s * 0.5, s, s)
                cr.fill()
    elif pattern_id == "builtin:triangle":
        for i in range(3):
            ang = -math.pi / 2 + i * math.tau / 3.0
            x, y = cx + math.cos(ang) * r * 0.70, cy + math.sin(ang) * r * 0.70
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.close_path()
        cr.fill()
    elif pattern_id == "builtin:cross":
        cr.set_line_width(max(2.0, r * 0.22))
        cr.move_to(cx - r * 0.65, cy)
        cr.line_to(cx + r * 0.65, cy)
        cr.move_to(cx, cy - r * 0.65)
        cr.line_to(cx, cy + r * 0.65)
        cr.stroke()
    else:  # builtin:spiral or fallback
        cr.set_line_width(max(1.5, r * 0.13))
        steps = 36
        for i in range(steps + 1):
            t = i / steps
            ang = t * math.tau * 2.0
            rad = t * r * 0.75
            x, y = cx + math.cos(ang) * rad, cy + math.sin(ang) * rad
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()


class GoboTileWidget(Gtk.DrawingArea):
    """Compact 44x44 circular gobo thumbnail (real PNG Pixbuf or Cairo pattern)."""

    def __init__(
        self,
        gobo_id: str,
        image_bytes: Optional[bytes] = None,
        active: bool = False,
        size: int = 42,
    ) -> None:
        super().__init__()
        self.gobo_id = gobo_id
        self.active = active
        self.tile_size = size
        self._pixbuf = _load_pixbuf(image_bytes, size - 8)
        self.set_size_request(size, size)
        self.connect("draw", self._on_draw)

    def _on_draw(self, _widget: Gtk.Widget, cr: cairo.Context) -> bool:
        w = float(self.get_allocated_width())
        h = float(self.get_allocated_height())
        cx, cy = w * 0.5, h * 0.5
        r = min(w, h) * 0.44

        # Dark aperture background
        cr.arc(cx, cy, r, 0, math.tau)
        cr.set_source_rgb(0.08, 0.09, 0.11)
        cr.fill()

        cr.save()
        cr.arc(cx, cy, r * 0.90, 0, math.tau)
        cr.clip()
        if self._pixbuf is not None:
            pw = self._pixbuf.get_width()
            ph = self._pixbuf.get_height()
            Gdk.cairo_set_source_pixbuf(cr, self._pixbuf, cx - pw * 0.5, cy - ph * 0.5)
            cr.paint()
        else:
            _draw_builtin_pattern(cr, self.gobo_id, cx, cy, r)
        cr.restore()

        # Ring border (accent when active)
        cr.arc(cx, cy, r, 0, math.tau)
        if self.active:
            cr.set_source_rgb(0.32, 0.68, 1.0)
            cr.set_line_width(2.5)
        else:
            cr.set_source_rgb(0.35, 0.37, 0.42)
            cr.set_line_width(1.2)
        cr.stroke()
        return False
