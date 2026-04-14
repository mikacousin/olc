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

import math
import typing

import cairo
from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, time_to_string

if typing.TYPE_CHECKING:
    from olc.lightshow import LightShow


# pylint: disable=too-many-instance-attributes
class SequentialWidget(Gtk.Widget):
    """Crossfade widget"""

    __gtype_name__ = "SequentialWidget"

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        lightshow: LightShow,
    ) -> None:
        self.lightshow = lightshow
        if self.lightshow.main_playback.last > 1:
            position = self.lightshow.main_playback.position
            self.total_time = self.lightshow.main_playback.steps[position].total_time
            self.time_in = self.lightshow.main_playback.steps[position].time_in
            self.time_out = self.lightshow.main_playback.steps[position].time_out
            self.delay_in = self.lightshow.main_playback.steps[position].delay_in
            self.delay_out = self.lightshow.main_playback.steps[position].delay_out
            self.wait = self.lightshow.main_playback.steps[position].wait
            self.channel_time = self.lightshow.main_playback.steps[
                position
            ].channel_time
        else:
            self.total_time = 5.0
            self.time_in = 5.0
            self.time_out = 5.0
            self.delay_in = 0.0
            self.delay_out = 0.0
            self.wait = 0.0
            self.channel_time = {}

        self.position_a = 0
        self.position_b = 0

        Gtk.Widget.__init__(self)
        self.set_size_request(800, 300)

    def _calculate_times(self) -> tuple[float, float]:
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            time_max = self.time_in + self.delay_in
            time_min = self.time_out + self.delay_out
        else:
            time_max = self.time_out + self.delay_out
            time_min = self.time_in + self.delay_in

        # Add Wait Time
        time_max = time_max + self.wait
        time_min = time_min + self.wait
        return time_max, time_min

    # pylint: disable=too-many-locals
    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw crossfade widget

        Args:
            cr: Cairo context
        """
        time_max, time_min = self._calculate_times()
        allocation = self.get_allocation()

        # Change height to draw channel time
        self.set_size_request(800, 300 + (len(self.channel_time) * 8))

        if self.total_time != 0:
            inter = (allocation.width - 32) / self.total_time
        else:
            inter = 0
        wait_x = inter * self.wait if self.wait > 0 else 0

        self._draw_background_frame(cr, allocation)
        self._draw_time_line(cr, allocation, inter)

        if self.wait > 0:
            self._draw_wait(cr, allocation, inter)

        if self.delay_out:
            self._draw_delay_out(cr, inter, wait_x)

        if self.delay_in:
            self._draw_delay_in(cr, allocation, inter, wait_x)

        self._draw_channel_times(cr, allocation, inter, wait_x)

        # Calculate coords for lines and cursors
        out_start_x, out_start_y, out_end_x, out_end_y, out_angle = (
            self._calc_out_coords(allocation, inter, wait_x)
        )
        in_start_x, in_start_y, in_end_x, in_end_y, in_angle = self._calc_in_coords(
            allocation, inter, wait_x
        )

        self._draw_out_line(
            cr, out_start_x, out_start_y, out_end_x, out_end_y, allocation
        )
        self._draw_x1_cursor(
            cr, inter, wait_x, out_start_x, out_start_y, out_end_x, out_end_y, out_angle
        )

        self._draw_in_line(cr, in_start_x, in_start_y, in_end_x, in_end_y, allocation)
        self._draw_x2_cursor(
            cr, inter, wait_x, in_start_x, in_start_y, in_end_x, in_end_y, in_angle
        )

        self._draw_times_number(cr, allocation, inter, time_max, time_min)

        return False

    def _draw_background_frame(
        self, cr: cairo.Context, allocation: Gdk.Rectangle
    ) -> None:
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        if self.position_a or self.position_b:  # Red filter in fades
            cr.set_source_rgba(1, 0, 0, 0.1)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

    def _draw_time_line(
        self, cr: cairo.Context, allocation: Gdk.Rectangle, inter: float
    ) -> None:
        fg_color = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(fg_color))
        cr.set_line_width(1)

        cr.move_to(16, 24)
        cr.line_to(allocation.width - 16, 24)
        cr.line_to(allocation.width - 16, 18)

        cr.move_to(16, 24)
        cr.line_to(16, 18)

        for i in range(int(self.total_time - 1)):
            cr.move_to(16 + (inter * (i + 1)), 24)
            cr.line_to(16 + (inter * (i + 1)), 18)
        cr.stroke()

    def _draw_wait(
        self, cr: cairo.Context, allocation: Gdk.Rectangle, inter: float
    ) -> None:
        cr.set_source_rgb(0.2, 0.2, 0.2)
        if self.position_a or self.position_b:
            cr.set_source_rgba(1, 0, 0, 0.1)
        cr.set_line_width(1)
        cr.rectangle(
            16,
            40,
            (inter * self.wait),
            allocation.height - 70 - (len(self.channel_time) * 8),
        )
        cr.fill()

        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.set_line_width(3)
        cr.move_to(16, 40)
        cr.line_to(16 + (inter * self.wait), 40)
        cr.stroke()

        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.set_line_width(3)
        cr.move_to(16, allocation.height - 32 - (len(self.channel_time) * 8))
        cr.line_to(
            16 + (inter * self.wait),
            allocation.height - 32 - (len(self.channel_time) * 8),
        )
        cr.stroke()

        cr.move_to(12 + (inter * self.wait), 16)
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        cr.show_text(time_to_string(self.wait))

    def _draw_delay_out(self, cr: cairo.Context, inter: float, wait_x: float) -> None:
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.set_line_width(3)
        cr.move_to(16 + wait_x, 40)
        cr.line_to(16 + wait_x + (inter * self.delay_out), 40)
        cr.stroke()
        cr.move_to(12 + wait_x + (inter * self.delay_out), 16)
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        cr.show_text(time_to_string(self.delay_out + self.wait))

    def _draw_delay_in(
        self, cr: cairo.Context, allocation: Gdk.Rectangle, inter: float, wait_x: float
    ) -> None:
        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.set_line_width(3)
        cr.move_to(16 + wait_x, allocation.height - 32 - (len(self.channel_time) * 8))
        cr.line_to(
            16 + wait_x + (inter * self.delay_in),
            allocation.height - 32 - (len(self.channel_time) * 8),
        )
        cr.stroke()
        cr.move_to(12 + wait_x + (inter * self.delay_in), 16)
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        cr.show_text(time_to_string(self.delay_in + self.wait))

    def _draw_channel_times(
        self, cr: cairo.Context, allocation: Gdk.Rectangle, inter: float, wait_x: float
    ) -> None:
        ct_nb = 0
        for channel in sorted(self.channel_time.keys(), reverse=True):
            if channel > MAX_CHANNELS:
                continue
            delay = self.channel_time[channel].delay
            time = self.channel_time[channel].time

            self._draw_channel_info(
                cr, allocation, inter, wait_x, ct_nb, channel, delay, time
            )
            self._draw_channel_cursor(
                cr, allocation, inter, wait_x, ct_nb, channel, delay, time
            )

            t = delay + time + self.wait
            if t != self.total_time:
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.move_to(12 + (inter * delay) + (inter * time) + wait_x, 16)
                cr.show_text(time_to_string(t))

            if delay:
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.move_to(12 + (inter * delay) + wait_x, 16)
                cr.show_text(time_to_string(delay + self.wait))
            ct_nb += 1

    def _draw_channel_info(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        inter: float,
        wait_x: float,
        ct_nb: int,
        channel: int,
        delay: float,
        time: float,
    ) -> None:
        cr.move_to((inter * delay) + wait_x, allocation.height - 4 - (ct_nb * 12))
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(10)
        cr.show_text(str(channel))

        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.set_line_width(1)
        cr.move_to(16 + (inter * delay) + wait_x, allocation.height - 8 - (ct_nb * 12))
        cr.line_to(
            16 + (inter * delay) + (inter * time) + wait_x,
            allocation.height - 8 - (ct_nb * 12),
        )
        cr.stroke()

        cr.set_dash([8.0, 6.0])
        cr.move_to(16 + (inter * delay) + wait_x, 24)
        cr.line_to(16 + (inter * delay) + wait_x, allocation.height)
        cr.move_to(16 + (inter * delay) + (inter * time) + wait_x, 24)
        cr.line_to(16 + (inter * delay) + (inter * time) + wait_x, allocation.height)
        cr.stroke()
        cr.set_dash([])

    def _draw_channel_cursor(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        inter: float,
        wait_x: float,
        ct_nb: int,
        channel: int,
        delay: float,
        time: float,
    ) -> None:
        position = self.lightshow.main_playback.position
        old_level = self.lightshow.main_playback.steps[position].cue.channels.get(
            channel, 0
        )
        next_level = self.lightshow.main_playback.steps[position + 1].cue.channels.get(
            channel, 0
        )

        pos_time = self.position_a if next_level < old_level else self.position_b

        if pos_time > inter * delay + wait_x:
            if pos_time > (inter * delay) + (inter * time) + wait_x:
                position_channeltime = (inter * delay) + (inter * time) + wait_x
            else:
                position_channeltime = pos_time
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.move_to(16 + position_channeltime, allocation.height - 12 - (ct_nb * 12))
            cr.line_to(16 + position_channeltime, allocation.height - 4 - (ct_nb * 12))
            cr.stroke()
        else:
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.move_to(
                16 + (inter * delay) + wait_x, allocation.height - 12 - (ct_nb * 12)
            )
            cr.line_to(
                16 + (inter * delay) + wait_x, allocation.height - 4 - (ct_nb * 12)
            )
            cr.stroke()

    def _calc_out_coords(
        self, allocation: Gdk.Rectangle, inter: float, wait_x: float
    ) -> tuple[float, float, float, float, float]:
        start_x = wait_x + (inter * self.delay_out) + 16
        start_y = 40.0
        end_x = 16 + wait_x + (inter * self.delay_out) + (inter * self.time_out)
        end_y = float(allocation.height - 32 - (len(self.channel_time) * 8))
        angle = math.atan2(end_y - start_y, end_x - start_x)
        return start_x, start_y, end_x, end_y, angle

    def _calc_in_coords(
        self, allocation: Gdk.Rectangle, inter: float, wait_x: float
    ) -> tuple[float, float, float, float, float]:
        start_x = wait_x + 16 + (inter * self.delay_in)
        start_y = float(allocation.height - 32 - (len(self.channel_time) * 8))
        end_x = 16 + wait_x + (inter * self.delay_in) + (inter * self.time_in)
        end_y = 40.0
        angle = math.atan2(end_y - start_y, end_x - start_x)
        return start_x, start_y, end_x, end_y, angle

    def _draw_out_line(
        self,
        cr: cairo.Context,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        allocation: Gdk.Rectangle,
    ) -> None:
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.set_line_width(3)
        cr.move_to(start_x, start_y)
        cr.line_to(end_x, end_y)
        cr.stroke()

        cr.move_to(end_x, 24)
        cr.line_to(end_x, allocation.height)
        cr.set_dash([8.0, 6.0])
        cr.stroke()
        cr.set_dash([])

        angle = math.atan2(end_y - start_y, end_x - start_x)
        self._draw_arrow(cr, end_x, end_y, angle)

    def _draw_in_line(
        self,
        cr: cairo.Context,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        allocation: Gdk.Rectangle,
    ) -> None:
        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.set_line_width(3)
        cr.move_to(start_x, start_y)
        cr.line_to(end_x, end_y)
        cr.stroke()

        cr.move_to(end_x, 24)
        cr.line_to(end_x, allocation.height)
        cr.set_dash([8.0, 6.0])
        cr.stroke()
        cr.set_dash([])

        angle = math.atan2(end_y - start_y, end_x - start_x)
        self._draw_arrow(cr, end_x, end_y, angle)

    def _draw_arrow(
        self, cr: cairo.Context, end_x: float, end_y: float, angle: float
    ) -> None:
        arrow_lenght = 12
        arrow_degrees = 10
        x1 = end_x + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = end_y + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = end_x + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = end_y + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()

    def _draw_x1_cursor(
        self,
        cr: cairo.Context,
        inter: float,
        wait_x: float,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        angle: float,
    ) -> None:
        x1 = start_x + self.position_a - wait_x - (inter * self.delay_out)
        if (not wait_x or self.position_a > wait_x) and (
            not self.delay_out or self.position_a > (inter * self.delay_out) + wait_x
        ):
            y1 = start_y + (
                (self.position_a - wait_x - (inter * self.delay_out)) * math.tan(angle)
            )
        else:
            y1 = start_y

        if x1 > end_x:
            x1 = end_x
            y1 = end_y

        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.arc(x1, y1, 8, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(10)
        cr.move_to(x1 - 5, y1 + 2)
        cr.show_text("A")

    def _draw_x2_cursor(
        self,
        cr: cairo.Context,
        inter: float,
        wait_x: float,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        angle: float,
    ) -> None:
        x1 = start_x + self.position_b - wait_x - (inter * self.delay_in)
        if (not wait_x or self.position_b > wait_x) and (
            not self.delay_in or self.position_b > ((inter * self.delay_in) + wait_x)
        ):
            y1 = start_y + (
                (self.position_b - wait_x - (inter * self.delay_in)) * math.tan(angle)
            )
        else:
            y1 = start_y

        if x1 > end_x:
            x1 = end_x
            y1 = end_y

        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.arc(x1, y1, 8, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(10)

        # Original conditionally shifted text downward. Wait!
        if (not wait_x or self.position_b > wait_x) and (
            not self.delay_in or self.position_b > ((inter * self.delay_in) + wait_x)
        ):
            text_y_offset = 3
        else:
            text_y_offset = 2
        cr.move_to(x1 - 5, y1 + text_y_offset)
        cr.show_text("B")

    def _draw_times_number(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        inter: float,
        time_max: float,
        time_min: float,
    ) -> None:
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)

        cr.move_to(12, 16)
        cr.show_text("0")

        cr.move_to(allocation.width - 24, 16)
        cr.show_text(time_to_string(self.total_time))

        if time_max != self.total_time:
            cr.move_to(12 + (inter * time_max), 16)
            cr.show_text(time_to_string(time_max))

        if time_min != time_max:
            cr.move_to(12 + (inter * time_min), 16)
            cr.show_text(time_to_string(time_min))

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
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL
        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)
        self.set_realized(True)
        window.set_background_pattern(None)
