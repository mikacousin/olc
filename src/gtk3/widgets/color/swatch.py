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
"""Swatch button widget for color presets and gel filter palettes."""

from __future__ import annotations

import math
from typing import Callable, Optional

import cairo
from gi.repository import Gtk

from olc.devices import color_pick as cp

SWATCH_WIDTH = 34
SWATCH_HEIGHT = 20

_MATCH_TEXT = {
    "exact": "exact",
    "close": "close",
    "approx": "approximate",
    "out": "out of gamut",
}

_MATCH_BADGE_RGB: dict[str, cp.RGB] = {
    "exact": (0.37, 0.75, 0.37),
    "close": (0.66, 0.78, 0.35),
    "approx": (0.88, 0.63, 0.19),
    "out": (0.88, 0.31, 0.31),
}


class SwatchButton(Gtk.Button):  # pylint: disable=too-few-public-methods
    """Small flat button filled with a color, optional gel code, and ΔE badge."""

    def __init__(
        self,
        name: str,
        rgb: cp.RGB,
        on_pick: Callable[[cp.RGB], None],
        code: str = "",
        gel: Optional[cp.GelSwatch] = None,
    ) -> None:
        super().__init__()
        self.base_name = name
        self.rgb = rgb
        self.code = code
        self.gel = gel
        self.match_level: Optional[str] = None
        self.set_tooltip_text(name)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(False)
        self.set_vexpand(False)
        self.get_style_context().add_class("olc-swatch")
        area = Gtk.DrawingArea()
        area.set_size_request(SWATCH_WIDTH, SWATCH_HEIGHT)
        area.set_halign(Gtk.Align.CENTER)
        area.set_valign(Gtk.Align.CENTER)
        area.connect("draw", self._on_draw)
        self._area = area
        self.add(area)
        self.connect("clicked", lambda _b: on_pick(self.rgb))

    def set_match_badge(
        self, level: Optional[str], delta_e: float = 0.0, warning: str = ""
    ) -> None:
        """Update feasibility badge and tooltip for the active Lead profile."""
        self.match_level = level
        if level is None:
            self.set_tooltip_text(self.base_name)
        else:
            warn_str = f" ({warning})" if warning else ""
            self.set_tooltip_text(
                f"{self.base_name} — ΔE {delta_e:.1f} · {_MATCH_TEXT[level]}{warn_str}"
            )
        self._area.queue_draw()

    def _on_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        cr.rectangle(0, 0, w, h)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.35)
        cr.set_line_width(1.0)
        cr.stroke()

        if self.code:
            luma = 0.2126 * self.rgb[0] + 0.7152 * self.rgb[1] + 0.0722 * self.rgb[2]
            if luma > 0.55:
                cr.set_source_rgba(0.05, 0.05, 0.05, 0.9)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.set_font_size(8.5)
            ext = cr.text_extents(self.code)
            cr.move_to(
                (w - ext.width) / 2.0 - ext.x_bearing,
                (h - ext.height) / 2.0 - ext.y_bearing,
            )
            cr.show_text(self.code)

        if self.match_level in _MATCH_BADGE_RGB:
            br, bg, bb = _MATCH_BADGE_RGB[self.match_level]
            cr.new_sub_path()
            cr.arc(w - 4.0, 4.0, 2.8, 0.0, 2.0 * math.pi)
            cr.set_source_rgb(br, bg, bb)
            cr.fill_preserve()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.7)
            cr.set_line_width(0.8)
            cr.stroke()
        return False
