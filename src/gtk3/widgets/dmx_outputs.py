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
"""Widget displaying real-time DMX output state, level and patch info."""

from __future__ import annotations

import typing

import cairo
from gi.repository import Gdk, Gtk

from olc.gtk3.widgets.common import rounded_rectangle, rounded_rectangle_fill

if typing.TYPE_CHECKING:
    from olc.core.backends import DMXBackend
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.dmx_outputs import DMXOutputsTab


class DMXOutputWidget(Gtk.DrawingArea):
    """DMX output widget displaying live DMX level, circuit and passive curve."""

    __gtype_name__ = "DMXOutputWidget"

    app: Application
    lightshow: LightShow
    tab: DMXOutputsTab
    backend: DMXBackend

    def __init__(
        self,
        universe: int,
        output: int,
        app: Application,
        tab: DMXOutputsTab,
    ) -> None:
        self.universe = universe
        self.output = output
        self.app = app
        self.lightshow = app.core.lightshow
        self.tab = tab
        self.backend = (
            app.core.backend
            if app.core.backend is not None
            else typing.cast(typing.Any, None)
        )

        super().__init__()
        self.scale = 1.0
        size = round(70 * self.scale)
        self.set_size_request(size, size)

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw widget.

        Args:
            cr: Cairo context
        """
        size = round(70 * self.scale)
        self.set_size_request(size, size)
        allocation = self.get_allocation()
        # Draw background
        self._draw_background(cr, allocation)
        # Draw output number
        self._draw_output_number(cr, allocation)
        # Draw channel number
        self._draw_channel_number(cr, allocation)
        # Draw Output level
        self._draw_output_level(cr, allocation)
        # Draw Curve (passive indicator)
        self._draw_curve(cr, allocation)
        # Draw Park badge
        self._draw_park_badge(cr, allocation)
        return False

    def _is_parked(self) -> bool:
        """Check if this DMX output or its patched channel is parked."""
        park_mgr = getattr(self.lightshow, "park", None)
        if park_mgr is None:
            return False
        if park_mgr.is_address_parked(self.universe, self.output):
            return True
        occ = self.lightshow.patch.get_address_occupant(self.universe, self.output)
        if occ is not None and park_mgr.is_channel_parked(occ):
            return True
        return False

    def _draw_background(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw background.

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        area = (1, allocation.width - 2, 1, allocation.height - 2)
        parent = typing.cast("Gtk.FlowBoxChild", self.get_parent())
        is_selected = parent is not None and parent.is_selected()
        occupant = self.lightshow.patch.get_address_occupant(self.universe, self.output)
        if (
            self.universe in self.lightshow.patch.outputs
            and self.output in self.lightshow.patch.outputs[self.universe]
        ):
            number = self.lightshow.patch.outputs[self.universe][self.output][1]
            curve = self.lightshow.curves.get_curve(number)
            if curve and curve.is_all_zero():
                # Level output blocked at 0
                if is_selected:
                    cr.set_source_rgb(0.8, 0.1, 0.1)
                else:
                    cr.set_source_rgb(0.5, 0.1, 0.1)
                rounded_rectangle_fill(cr, area, 10)
            elif self.lightshow.patch.outputs[self.universe][self.output][0] != 0:
                # Patch output
                cr.set_source_rgb(0.3, 0.3, 0.3)
                rounded_rectangle_fill(cr, area, 10)
                if is_selected:
                    cr.set_source_rgb(0.6, 0.4, 0.1)
                    rounded_rectangle(cr, area, 10)
        elif occupant is not None and occupant > 0:
            cr.set_source_rgb(0.3, 0.3, 0.3)
            rounded_rectangle_fill(cr, area, 10)
            if is_selected:
                cr.set_source_rgb(0.6, 0.4, 0.1)
                rounded_rectangle(cr, area, 10)
        elif is_selected:
            # Unpatched output
            cr.set_source_rgb(0.6, 0.4, 0.1)
            rounded_rectangle(cr, area, 10)
        if self.universe in self.tab.patch.universes:
            index = self.tab.patch.universes.index(self.universe)
            if (
                index < len(self.backend.dmx.frame)
                and self.backend.dmx.frame[index][self.output - 1]
            ):
                level = self.backend.dmx.frame[index][self.output - 1]
                cr.set_source_rgba(
                    0.3 + (0.2 / 255 * level), 0.3, 0.3 - (0.3 / 255 * level), 0.6
                )
                rounded_rectangle_fill(cr, area, 10)
        if self._is_parked():
            cr.set_source_rgba(1.0, 0.7, 0.0, 0.8)
            cr.set_line_width(1.5 * self.scale)
            rounded_rectangle(cr, area, 10)

    def _draw_output_number(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw Output number.

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face(
            "DejaVu Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
        )
        cr.set_font_size(11 * self.scale)
        text = f"{self.universe}.{self.output}"
        (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
        cr.move_to(
            allocation.width / 2 - width / 2, allocation.height / 4 - (height - 20) / 4
        )
        cr.show_text(text)

    def _draw_channel_number(  # pylint: disable=too-many-locals
        self, cr: cairo.Context, allocation: Gdk.Rectangle
    ) -> None:
        """Draw Channel number and parameter name.

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        param_info = self.lightshow.patch.get_address_parameter_info(
            self.universe, self.output
        )

        ch_num = 0
        is_simple_dimmer = True
        short_name = ""
        param_color = (1.0, 0.6, 0.2)

        if param_info is not None:
            ch_num = param_info.device_id
            is_simple_dimmer = param_info.is_simple_dimmer
            short_name = param_info.short_name
            param_color = param_info.param_color
        else:
            if (
                self.universe in self.lightshow.patch.outputs
                and self.output in self.lightshow.patch.outputs[self.universe]
            ):
                ch_num = self.lightshow.patch.outputs[self.universe][self.output][0]
            else:
                occ = self.lightshow.patch.get_address_occupant(
                    self.universe, self.output
                )
                if occ is not None:
                    ch_num = occ

        if ch_num <= 0:
            return

        cr.select_font_face(
            "DejaVu Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
        )
        base_font_size = 11.0 * self.scale
        cr.set_font_size(base_font_size)

        num_text = str(ch_num)

        if is_simple_dimmer or not short_name:
            cr.set_source_rgb(0.9, 0.6, 0.2)
            (_x, _y, width, height, _dx, _dy) = cr.text_extents(num_text)
            cr.move_to(
                allocation.width / 2 - width / 2,
                3 * (allocation.height / 4 - (height - 20) / 4),
            )
            cr.show_text(num_text)
        else:
            self._draw_device_param_label(
                cr, allocation, num_text, short_name, param_color, base_font_size
            )

    def _draw_device_param_label(  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        num_text: str,
        short_name: str,
        param_color: tuple[float, float, float],
        base_font_size: float,
    ) -> None:
        """Draw circuit number left-justified and parameter label right-justified."""
        padding = round(6 * self.scale)

        # 1. Circuit number extent
        cr.set_font_size(base_font_size)
        (_x1, _y1, w_num, h_num, _dx1, _dy1) = cr.text_extents(num_text)
        baseline_y = 3 * (allocation.height / 4 - (h_num - 20) / 4)

        # 2. Parameter extent and font scaling if needed
        param_font_size = 9.0 * self.scale
        cr.set_font_size(param_font_size)
        (_x2, _y2, w_param, _h2, _dx2, _dy2) = cr.text_extents(short_name)

        max_available_param = (
            allocation.width - 2 * padding - w_num - round(4 * self.scale)
        )
        if w_param > max_available_param and w_param > 0:
            scale_factor = max_available_param / w_param
            param_font_size = max(7.0 * self.scale, param_font_size * scale_factor)
            cr.set_font_size(param_font_size)
            (_x2, _y2, w_param, _h2, _dx2, _dy2) = cr.text_extents(short_name)

        # 3. Draw circuit number on the left
        cr.set_font_size(base_font_size)
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.move_to(padding, baseline_y)
        cr.show_text(num_text)

        # 4. Draw parameter name on the right
        cr.set_font_size(param_font_size)
        cr.set_source_rgb(*param_color)
        param_x = allocation.width - padding - w_param
        cr.move_to(param_x, baseline_y)
        cr.show_text(short_name)

    def _draw_output_level(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw Output level.

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        is_parked = self._is_parked()
        if (
            self.backend is not None
            and getattr(self.backend, "dmx", None) is not None
            and self.universe in self.tab.patch.universes
        ):
            index = self.tab.patch.universes.index(self.universe)
            if index < len(self.backend.dmx.frame):
                level = int(self.backend.dmx.frame[index][self.output - 1])
                if level > 0 or is_parked:
                    if is_parked:
                        cr.set_source_rgb(1.0, 0.7, 0.0)
                    else:
                        cr.set_source_rgb(0.7, 0.7, 0.7)
                    cr.select_font_face(
                        "DejaVu Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
                    )
                    cr.set_font_size(10 * self.scale)
                    text = str(level)
                    (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
                    cr.move_to(
                        allocation.width / 2 - width / 2,
                        allocation.height / 2 - (height - 20) / 2,
                    )
                    cr.show_text(text)

    def _draw_park_badge(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw 'P' badge if output or occupant channel is parked.

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        if not self._is_parked():
            return
        cr.select_font_face(
            "DejaVu Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
        )
        cr.set_font_size(10 * self.scale)
        cr.set_source_rgb(1.0, 0.7, 0.0)
        cr.move_to(allocation.width - 13 * self.scale, 14 * self.scale)
        cr.show_text("P")

    def _draw_curve(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw Dimmer Curve (passive visual indicator).

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        if (
            self.universe in self.lightshow.patch.outputs
            and self.output in self.lightshow.patch.outputs[self.universe]
        ):
            number = self.lightshow.patch.outputs[self.universe][self.output][1]
            # Don't draw linear curve
            if number:
                curve = self.lightshow.curves.get_curve(number)
                if not curve:
                    return
                cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
                cr.set_line_width(1)
                cr.move_to(
                    10,
                    allocation.height - int(curve.values_array[0]) - 10,
                )
                for x, y in enumerate(curve.values_array):
                    y = int(y)
                    cr.line_to(
                        10 + (x / 255) * (allocation.width - 20),
                        (allocation.height - 10)
                        - ((y / 255) * (allocation.height - 20)),
                    )
                cr.stroke()
