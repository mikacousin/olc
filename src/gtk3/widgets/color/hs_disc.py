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
"""Hue/Saturation disc widget with gamut overlay and multi-fixture reticles."""

from __future__ import annotations

import math
import sys
from typing import Any, Callable, Optional

import cairo
from gi.repository import Gdk, Gtk

from olc.devices import color_pick as cp
from olc.gtk3.widgets.color.point import FixtureColorPoint

DISC_SIZE = 260


class HSDiscWidget(Gtk.DrawingArea):  # pylint: disable=too-many-instance-attributes
    """Hue/saturation disc with gamut polygon and multi-fixture reticles."""

    def __init__(
        self,
        on_change: Callable[[float, float], None],
        on_release: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_change = on_change
        self._on_release = on_release
        self.hue = 0.0
        self.sat = 0.0
        self.rgb: cp.RGB = (1.0, 1.0, 1.0)
        self.dragging = False
        self.gamut_hs: list[tuple[float, float]] = []
        self.points: list[FixtureColorPoint] = []
        self._surface: Optional[cairo.ImageSurface] = None
        self._surface_key: Optional[tuple[int, int]] = None
        self._surface_data: Any = None  # keeps the pixel buffer alive
        self.set_size_request(DISC_SIZE, DISC_SIZE)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_MOTION_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
        )
        self.connect("button-press-event", self._on_pointer)
        self.connect("motion-notify-event", self._on_pointer)
        self.connect("button-release-event", self._on_button_release)
        self.connect("draw", self._on_draw)

    def set_hs(self, hue: float, sat: float, rgb: cp.RGB) -> None:
        """Move the marker (no callback)."""
        self.hue, self.sat, self.rgb = hue, sat, rgb
        self.queue_draw()

    def set_overlay(
        self,
        gamut_hs: list[tuple[float, float]],
        points: list[FixtureColorPoint],
    ) -> None:
        """Update gamut polygon and multi-fixture reticle positions."""
        self.gamut_hs = list(gamut_hs)
        self.points = list(points)
        self.queue_draw()

    # -- geometry -------------------------------------------------------------

    def _disc(self) -> tuple[float, float, float]:
        alloc = self.get_allocation()
        radius = max(8.0, min(alloc.width, alloc.height) / 2.0 - 4.0)
        return alloc.width / 2.0, alloc.height / 2.0, radius

    @staticmethod
    def _hs_to_px(
        hue: float, sat: float, cx: float, cy: float, radius: float
    ) -> tuple[float, float]:
        angle = hue * 2.0 * math.pi
        return (
            cx + math.cos(angle) * sat * radius,
            cy + math.sin(angle) * sat * radius,
        )

    def _on_pointer(self, _w: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        self.dragging = True
        cx, cy, radius = self._disc()
        dx, dy = event.x - cx, event.y - cy
        sat = min(1.0, math.hypot(dx, dy) / radius)
        hue = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
        self.hue, self.sat = hue, sat
        self.rgb = cp.hs_to_rgb(hue, sat)
        self.queue_draw()
        self._on_change(hue, sat)
        return True

    def _on_button_release(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self.dragging = False
        self._on_release()
        return True

    # -- drawing --------------------------------------------------------------

    def _ensure_surface(self, diameter: int) -> cairo.ImageSurface:
        scale = max(1, self.get_scale_factor())
        key = (diameter, scale)
        if self._surface is None or self._surface_key != key:
            pixels = cp.render_hs_disc(diameter * scale)
            if sys.byteorder == "big":  # cairo ARGB32 is native-endian
                pixels = pixels[..., ::-1]
            data = bytearray(pixels.tobytes())
            side = diameter * scale
            surface = cairo.ImageSurface.create_for_data(
                data, cairo.FORMAT_ARGB32, side, side, side * 4
            )
            surface.set_device_scale(scale, scale)
            self._surface, self._surface_key, self._surface_data = surface, key, data
        return self._surface

    def _on_draw(  # pylint: disable=too-many-locals
        self, _w: Gtk.Widget, cr: cairo.Context
    ) -> bool:
        cx, cy, radius = self._disc()
        diameter = int(radius * 2.0)
        surface = self._ensure_surface(diameter)
        cr.set_source_surface(surface, cx - diameter / 2.0, cy - diameter / 2.0)
        cr.paint()

        # Thin rim
        cr.arc(cx, cy, diameter / 2.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.35)
        cr.set_line_width(1.0)
        cr.stroke()

        # Lead fixture gamut polygon overlay
        if len(self.gamut_hs) >= 3:
            cr.save()
            for idx, (gh, gs) in enumerate(self.gamut_hs):
                gx, gy = self._hs_to_px(gh, gs, cx, cy, radius)
                if idx == 0:
                    cr.move_to(gx, gy)
                else:
                    cr.line_to(gx, gy)
            cr.close_path()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.55)
            cr.set_line_width(2.0)
            cr.stroke_preserve()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.85)
            cr.set_dash([4.0, 3.0])
            cr.set_line_width(1.2)
            cr.stroke()
            cr.restore()

        # Satellite fixture reticles
        for pt in self.points:
            if pt.is_lead:
                continue
            ph, ps = cp.rgb_to_hs(*pt.rgb, self.hue)
            px, py = self._hs_to_px(ph, ps, cx, cy, radius)
            cr.arc(px, py, 4.0, 0.0, 2.0 * math.pi)
            cr.set_source_rgba(0.15, 0.85, 0.95, 0.8)
            cr.fill_preserve()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.7)
            cr.set_line_width(1.0)
            cr.stroke()

        # Marker at the current (Lead) hue/saturation
        mx, my = self._hs_to_px(self.hue, self.sat, cx, cy, radius)
        cr.new_sub_path()
        cr.arc(mx, my, 6.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_line_width(2.0)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(mx, my, 7.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.6)
        cr.set_line_width(1.0)
        cr.stroke()
        return False
