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
"""Sampled monitor widget displaying 11 discrete evaluation steps across a curve."""

from __future__ import annotations

import typing

import cairo
from gi.repository import Gtk, Pango

from olc.gtk3.widgets.common import (
    TextAnchor,
    draw_cached_numeric_text,
    register_system_font_listener,
)
from olc.gtk3.widgets.curve_units import CurveUnitMode, format_curve_value

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow

MONITOR_HEIGHT = 54


class CurveSampledMonitor(Gtk.DrawingArea):
    """Visual ruler showing input-to-output evaluation for 11 uniform steps."""

    def __init__(
        self,
        lightshow: LightShow,
        unit_mode: CurveUnitMode = CurveUnitMode.PERCENT,
    ) -> None:
        super().__init__()
        self.lightshow = lightshow
        self.unit_mode = unit_mode
        self.curve_nb: int | None = None
        self.set_size_request(-1, MONITOR_HEIGHT)
        self.set_valign(Gtk.Align.START)
        self.connect("draw", self.on_draw)
        register_system_font_listener(self.queue_draw)

    def set_unit_mode(self, unit_mode: CurveUnitMode) -> None:
        """Change unit mode and redraw."""
        self.unit_mode = unit_mode
        self.queue_draw()

    def set_curve(self, curve_nb: int | None) -> None:
        """Change monitored curve and redraw."""
        self.curve_nb = curve_nb
        self.queue_draw()

    def on_draw(self, _area: Gtk.Widget, cr: cairo.Context) -> None:
        """Draw the 11-step sampling table."""
        alloc = self.get_allocation()
        width = alloc.width
        draw_height = (
            min(alloc.height, MONITOR_HEIGHT) if alloc.height > 0 else MONITOR_HEIGHT
        )

        if self.curve_nb is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if curve is None:
            return

        # Background
        cr.set_source_rgb(0.12, 0.12, 0.12)
        cr.rectangle(0, 0, width, draw_height)
        cr.fill()

        # Labels "In" and "Out" on the left
        label_width = 32
        cr.set_source_rgb(0.55, 0.55, 0.55)
        draw_cached_numeric_text(
            cr,
            4,
            16,
            "In",
            8,
            weight=Pango.Weight.BOLD,
            anchor=TextAnchor.BASELINE_LEFT,
        )
        draw_cached_numeric_text(
            cr,
            4,
            38,
            "Out",
            8,
            weight=Pango.Weight.BOLD,
            anchor=TextAnchor.BASELINE_LEFT,
        )

        steps = 11
        grid_width = width - label_width - 8
        step_w = grid_width / steps

        for i in range(steps):
            norm_in = i / 10.0
            norm_out = float(curve.evaluate_normalized(norm_in))

            in_str = format_curve_value(norm_in, self.unit_mode)
            out_str = format_curve_value(norm_out, self.unit_mode)

            cell_x = label_width + i * step_w
            cell_w = step_w - 2

            # Cell box
            cr.set_source_rgb(0.18, 0.18, 0.18)
            cr.rectangle(cell_x, 2, cell_w, draw_height - 4)
            cr.fill()

            cr.set_source_rgb(0.28, 0.28, 0.28)
            cr.rectangle(cell_x, 2, cell_w, draw_height - 4)
            cr.stroke()

            # Center coordinates
            center_x = cell_x + cell_w / 2.0

            # In level (dimmed / neutral)
            cr.set_source_rgb(0.65, 0.65, 0.65)
            draw_cached_numeric_text(
                cr,
                round(center_x),
                16,
                in_str,
                8,
                weight=Pango.Weight.NORMAL,
                anchor=TextAnchor.BASELINE_CENTER,
            )

            # Out level (amber highlight if changed, cyan/white if linear)
            is_different = abs(norm_out - norm_in) > 1e-3
            if is_different:
                cr.set_source_rgb(1.0, 0.72, 0.3)
            else:
                cr.set_source_rgb(0.9, 0.9, 0.9)

            draw_cached_numeric_text(
                cr,
                round(center_x),
                38,
                out_str,
                8,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_CENTER,
            )
