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
"""CIE 1931 xy chromaticity diagram widget with locus, gamut, and reticles."""

from __future__ import annotations

import math
import sys
from typing import Any, Callable, Optional

import cairo
from gi.repository import Gdk, Gtk

from olc.devices import color_pick as cp
from olc.gtk3.widgets.color.hs_disc import DISC_SIZE
from olc.gtk3.widgets.color.point import FixtureColorPoint


class CIExyWidget(Gtk.DrawingArea):  # pylint: disable=too-many-instance-attributes
    """CIE 1931 xy horseshoe diagram with Planckian locus, gamut hull, and reticles."""

    def __init__(
        self,
        on_change: Callable[[float, float], None],
        on_release: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_change = on_change
        self._on_release = on_release
        self.cie_x = 0.3127
        self.cie_y = 0.3290
        self.rgb: cp.RGB = (1.0, 1.0, 1.0)
        self.dragging = False
        self.gamut_xy: list[cp.XY] = []
        self.emitters_xy: list[cp.XY] = []
        self.points: list[FixtureColorPoint] = []
        self._planck_xy = cp.planckian_locus_xy(32)
        self._surface: Optional[cairo.ImageSurface] = None
        self._surface_key: Optional[tuple[int, int]] = None
        self._surface_data: Any = None
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

    def set_xy(self, x: float, y: float, rgb: cp.RGB) -> None:
        """Move the CIE xy reticle (no callback)."""
        self.cie_x, self.cie_y, self.rgb = x, y, rgb
        self.queue_draw()

    def set_overlay(
        self,
        gamut_xy: list[cp.XY],
        points: list[FixtureColorPoint],
        emitters_xy: Optional[list[cp.XY]] = None,
    ) -> None:
        """Update emitter gamut polygon and multi-fixture reticle positions."""
        self.gamut_xy = list(gamut_xy)
        self.emitters_xy = (
            list(emitters_xy) if emitters_xy is not None else list(gamut_xy)
        )
        self.points = list(points)
        self.queue_draw()

    # -- geometry -------------------------------------------------------------

    def _box(self) -> tuple[float, float, float]:
        alloc = self.get_allocation()
        side = max(16.0, float(min(alloc.width, alloc.height)) - 8.0)
        ox = (alloc.width - side) / 2.0
        oy = (alloc.height - side) / 2.0
        return ox, oy, side

    @staticmethod
    def _xy_to_px(
        x: float, y: float, ox: float, oy: float, side: float
    ) -> tuple[float, float]:
        px = ox + (x / cp.CIE_X_MAX) * side
        py = oy + (1.0 - y / cp.CIE_Y_MAX) * side
        return px, py

    @staticmethod
    def _px_to_xy(px: float, py: float, ox: float, oy: float, side: float) -> cp.XY:
        nx = max(0.0, min(1.0, (px - ox) / side))
        ny = max(0.0, min(1.0, 1.0 - (py - oy) / side))
        return nx * cp.CIE_X_MAX, ny * cp.CIE_Y_MAX

    def _on_pointer(self, _w: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        self.dragging = True
        ox, oy, side = self._box()
        raw_x, raw_y = self._px_to_xy(event.x, event.y, ox, oy, side)
        cx, cy = cp.clamp_xy_to_locus(raw_x, raw_y)
        self.cie_x, self.cie_y = cx, cy
        self.rgb = cp.xy_to_srgb(cx, cy)
        self.queue_draw()
        self._on_change(cx, cy)
        return True

    def _on_button_release(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self.dragging = False
        self._on_release()
        return True

    # -- drawing --------------------------------------------------------------

    def _ensure_surface(self, side_int: int) -> cairo.ImageSurface:
        scale = max(1, self.get_scale_factor())
        key = (side_int, scale)
        if self._surface is None or self._surface_key != key:
            pixels = cp.render_cie_xy_diagram(side_int * scale)
            if sys.byteorder == "big":
                pixels = pixels[..., ::-1]
            data = bytearray(pixels.tobytes())
            px_side = side_int * scale
            surface = cairo.ImageSurface.create_for_data(
                data, cairo.FORMAT_ARGB32, px_side, px_side, px_side * 4
            )
            surface.set_device_scale(scale, scale)
            self._surface, self._surface_key, self._surface_data = surface, key, data
        return self._surface

    def _on_draw(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        self, _w: Gtk.Widget, cr: cairo.Context
    ) -> bool:
        ox, oy, side = self._box()
        side_int = max(8, int(side))
        surface = self._ensure_surface(side_int)
        cr.set_source_surface(surface, ox, oy)
        cr.paint()

        # Spectral horseshoe outline
        for idx, (lx, ly) in enumerate(cp.SPECTRAL_LOCUS_XY):
            px, py = self._xy_to_px(lx, ly, ox, oy, side)
            if idx == 0:
                cr.move_to(px, py)
            else:
                cr.line_to(px, py)
        cr.close_path()
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.45)
        cr.set_line_width(1.0)
        cr.stroke()

        # Planckian locus curve (1800 K - 12000 K)
        cr.save()
        for idx, (kx, ky) in enumerate(self._planck_xy):
            px, py = self._xy_to_px(kx, ky, ox, oy, side)
            if idx == 0:
                cr.move_to(px, py)
            else:
                cr.line_to(px, py)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.5)
        cr.set_line_width(2.0)
        cr.stroke_preserve()
        cr.set_source_rgba(1.0, 0.96, 0.85, 0.85)
        cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

        # Lead fixture emitter gamut polygon
        if len(self.gamut_xy) >= 3:
            cr.save()
            for idx, (gx, gy) in enumerate(self.gamut_xy):
                px, py = self._xy_to_px(gx, gy, ox, oy, side)
                if idx == 0:
                    cr.move_to(px, py)
                else:
                    cr.line_to(px, py)
            cr.close_path()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.65)
            cr.set_line_width(2.2)
            cr.stroke_preserve()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
            cr.set_dash([4.0, 3.0])
            cr.set_line_width(1.2)
            cr.stroke()
            cr.restore()

            for gx, gy in self.emitters_xy or self.gamut_xy:
                px, py = self._xy_to_px(gx, gy, ox, oy, side)
                cr.arc(px, py, 2.5, 0.0, 2.0 * math.pi)
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
                cr.fill_preserve()
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.8)
                cr.set_line_width(1.0)
                cr.stroke()

        # Satellite fixture reticles
        for pt in self.points:
            if pt.is_lead:
                continue
            px, py = self._xy_to_px(pt.xy[0], pt.xy[1], ox, oy, side)
            cr.arc(px, py, 4.0, 0.0, 2.0 * math.pi)
            cr.set_source_rgba(0.15, 0.85, 0.95, 0.85)
            cr.fill_preserve()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.75)
            cr.set_line_width(1.0)
            cr.stroke()

        # Lead reticle at current (cie_x, cie_y)
        mx, my = self._xy_to_px(self.cie_x, self.cie_y, ox, oy, side)
        cr.new_sub_path()
        cr.arc(mx, my, 6.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_line_width(2.0)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(mx, my, 7.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.65)
        cr.set_line_width(1.0)
        cr.stroke()
        return False
