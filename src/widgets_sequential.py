"""Crossfade Widget"""

import math

import cairo
from gi.repository import Gdk, Gtk
from olc.define import App


class SequentialWidget(Gtk.Widget):
    """Crossfade widget"""

    __gtype_name__ = "SequentialWidget"

    def __init__(
        self, total_time, time_in, time_out, delay_in, delay_out, wait, channel_time
    ):

        self.total_time = total_time
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        self.channel_time = channel_time

        self.position_a = 0
        self.position_b = 0

        Gtk.Widget.__init__(self)
        self.set_size_request(800, 300)

    def do_draw(self, cr):
        """Draw xfade widget"""
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            time_max = self.time_in + self.delay_in
            time_min = self.time_out + self.delay_out
        else:
            time_max = self.time_out + self.delay_out
            time_min = self.time_in + self.delay_in

        # Add Wait Time
        time_max = time_max + self.wait
        time_min = time_min + self.wait

        # paint background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        allocation = self.get_allocation()

        # Draw frame
        if self.position_a or self.position_b:  # Red filter in fades
            cr.set_source_rgba(1, 0, 0, 0.1)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        # draw time line
        fg_color = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(fg_color))
        cr.set_line_width(1)
        cr.move_to(16, 24)
        cr.line_to(allocation.width - 16, 24)
        cr.line_to(allocation.width - 16, 18)
        cr.move_to(16, 24)
        cr.line_to(16, 18)
        # inter = (allocation.width-32)/time_max
        inter = (allocation.width - 32) / self.total_time
        for i in range(int(self.total_time - 1)):
            cr.move_to(16 + (inter * (i + 1)), 24)
            cr.line_to(16 + (inter * (i + 1)), 18)
        cr.stroke()

        # Draw Wait if any
        if self.wait > 0:
            # Draw a grey box
            cr.set_source_rgb(0.2, 0.2, 0.2)
            if self.position_a or self.position_b:  # Red filter in fades
                cr.set_source_rgba(1, 0, 0, 0.1)
            cr.set_line_width(1)
            cr.rectangle(
                16,
                40,
                (inter * self.wait),
                allocation.height - 70 - (len(self.channel_time) * 8),
            )
            cr.fill()
            # Draw Wait lines
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
            wait_x = inter * self.wait
            # Draw Wait time on the time line
            cr.move_to(12 + (inter * self.wait), 16)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(12)
            # If time is integer don't show the ".0"
            if self.wait.is_integer():
                cr.show_text(str(int(self.wait)))
            else:
                cr.show_text(str(self.wait))
        else:
            wait_x = 0

        # Draw Delay Out
        if self.delay_out:
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.set_line_width(3)
            cr.move_to(16 + wait_x, 40)
            cr.line_to(16 + wait_x + (inter * self.delay_out), 40)
            cr.stroke()
            # Draw Delay Out on the time line
            cr.move_to(12 + wait_x + (inter * self.delay_out), 16)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(12)
            # If time is integer don't show the ".0"
            if self.delay_out.is_integer():
                cr.show_text(str(int(self.delay_out + self.wait)))
            else:
                cr.show_text(str(self.delay_out + self.wait))

        # Draw Delay In
        if self.delay_in:
            cr.set_source_rgb(0.9, 0.5, 0.5)
            cr.set_line_width(3)
            cr.move_to(
                16 + wait_x, allocation.height - 32 - (len(self.channel_time) * 8)
            )
            cr.line_to(
                16 + wait_x + (inter * self.delay_in),
                allocation.height - 32 - (len(self.channel_time) * 8),
            )
            cr.stroke()
            # Draw Delay In on the time line
            cr.move_to(12 + wait_x + (inter * self.delay_in), 16)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(12)
            # If time is integer don't show the ".0"
            if self.delay_in.is_integer():
                cr.show_text(str(int(self.delay_in + self.wait)))
            else:
                cr.show_text(str(self.delay_in + self.wait))

        # Draw Channel Time if any
        ct_nb = 0

        # Change height to draw channel time
        self.set_size_request(800, 300 + (len(self.channel_time) * 8))

        for channel in self.channel_time.keys():
            delay = self.channel_time[channel].delay
            time = self.channel_time[channel].time
            # draw Channel number
            cr.move_to((inter * delay) + wait_x, allocation.height - 4 - (ct_nb * 12))
            # cr.move_to((inter*delay)+wait_x,allocation.height-28-(ct_nb*12))
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(10)
            cr.show_text(str(channel))
            # draw Channel Time line
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.set_line_width(1)
            cr.move_to(
                16 + (inter * delay) + wait_x, allocation.height - 8 - (ct_nb * 12)
            )
            cr.line_to(
                16 + (inter * delay) + (inter * time) + wait_x,
                allocation.height - 8 - (ct_nb * 12),
            )
            cr.stroke()
            cr.set_dash([8.0, 6.0])
            cr.move_to(16 + (inter * delay) + wait_x, 24)
            cr.line_to(16 + (inter * delay) + wait_x, allocation.height)
            cr.move_to(16 + (inter * delay) + (inter * time) + wait_x, 24)
            cr.line_to(
                16 + (inter * delay) + (inter * time) + wait_x, allocation.height
            )
            cr.stroke()
            cr.set_dash([])
            # draw Time Cursor
            position = App().sequence.position
            old_level = App().sequence.steps[position].cue.channels[channel - 1]
            next_level = App().sequence.steps[position + 1].cue.channels[channel - 1]
            # Time Cursor follow In or Out Crossfade
            if next_level < old_level:
                # Out Crossfade
                if self.position_a > inter * delay + wait_x:
                    if self.position_a > (inter * delay) + (inter * time) + wait_x:
                        position_channeltime = (inter * delay) + (inter * time) + wait_x
                    else:
                        position_channeltime = self.position_a
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(
                        16 + position_channeltime,
                        allocation.height - 12 - (ct_nb * 12),
                    )
                    cr.line_to(
                        16 + position_channeltime, allocation.height - 4 - (ct_nb * 12),
                    )
                    cr.stroke()
                else:
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(
                        16 + (inter * delay) + wait_x,
                        allocation.height - 12 - (ct_nb * 12),
                    )
                    cr.line_to(
                        16 + (inter * delay) + wait_x,
                        allocation.height - 4 - (ct_nb * 12),
                    )
                    cr.stroke()
            else:
                # In Crossfade
                if self.position_b > inter * delay + wait_x:
                    if self.position_b > (inter * delay) + (inter * time) + wait_x:
                        position_channeltime = (inter * delay) + (inter * time) + wait_x
                    else:
                        position_channeltime = self.position_b
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(
                        16 + position_channeltime,
                        allocation.height - 12 - (ct_nb * 12),
                    )
                    cr.line_to(
                        16 + position_channeltime, allocation.height - 4 - (ct_nb * 12),
                    )
                    cr.stroke()
                else:
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(
                        16 + (inter * delay) + wait_x,
                        allocation.height - 12 - (ct_nb * 12),
                    )
                    cr.line_to(
                        16 + (inter * delay) + wait_x,
                        allocation.height - 4 - (ct_nb * 12),
                    )
                    cr.stroke()
            # draw time number
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.move_to(12 + (inter * delay) + (inter * time) + wait_x, 16)
            t = delay + time + self.wait
            if t != self.total_time:
                # If time is integer don't show the ".0"
                if t.is_integer():
                    cr.show_text(str(int(t)))
                else:
                    cr.show_text(str(t))
            # draw delay number if any
            if delay:
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.move_to(12 + (inter * delay) + wait_x, 16)
                t = delay + self.wait
                # If time is integer don't show the ".0"
                if t.is_integer():
                    cr.show_text(str(int(t)))
                else:
                    cr.show_text(str(t))
            ct_nb += 1

        # draw Out line
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.set_line_width(3)
        cr.move_to(16 + wait_x + (inter * self.delay_out), 40)
        cr.line_to(
            (16 + wait_x + (inter * self.delay_out) + (inter * self.time_out)),
            allocation.height - 32 - (len(self.channel_time) * 8),
        )
        cr.stroke()
        cr.move_to(
            (16 + wait_x + (inter * self.delay_out) + (inter * self.time_out)), 24
        )
        cr.line_to(
            (16 + wait_x + (inter * self.delay_out) + (inter * self.time_out)),
            allocation.height,
        )
        cr.set_dash([8.0, 6.0])
        cr.stroke()
        cr.set_dash([])
        # draw an arrow at the end
        arrow_lenght = 12
        arrow_degrees = 10
        start_x = wait_x + (inter * self.delay_out) + 16
        start_y = 40
        end_x = 16 + wait_x + (inter * self.delay_out) + (inter * self.time_out)
        end_y = allocation.height - 32 - (len(self.channel_time) * 8)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        x1 = end_x + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = end_y + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = end_x + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = end_y + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()
        # draw X1 cursor
        if (not wait_x or self.position_a > wait_x) and (
            not self.delay_out or self.position_a > (inter * self.delay_out) + wait_x
        ):
            x1 = start_x + self.position_a - wait_x - (inter * self.delay_out)
            y1 = start_y + (
                (self.position_a - wait_x - (inter * self.delay_out)) * math.tan(angle)
            )
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
        else:
            x1 = start_x + self.position_a - wait_x - (inter * self.delay_out)
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

        # draw In line
        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.move_to(
            16 + wait_x + (inter * self.delay_in),
            allocation.height - 32 - (len(self.channel_time) * 8),
        )
        cr.line_to((16 + wait_x + (inter * self.delay_in) + (inter * self.time_in)), 40)
        cr.stroke()
        cr.move_to((16 + wait_x + (inter * self.delay_in) + (inter * self.time_in)), 24)
        cr.line_to(
            (16 + wait_x + (inter * self.delay_in) + (inter * self.time_in)),
            allocation.height,
        )
        cr.set_dash([8.0, 6.0])
        cr.stroke()
        cr.set_dash([])
        # draw an arrow at the end
        arrow_lenght = 12
        arrow_degrees = 10
        start_x = wait_x + 16 + (inter * self.delay_in)
        start_y = allocation.height - 32 - (len(self.channel_time) * 8)
        end_x = 16 + wait_x + (inter * self.delay_in) + (inter * self.time_in)
        end_y = 40
        angle = math.atan2(end_y - start_y, end_x - start_x)
        x1 = end_x + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = end_y + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = end_x + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = end_y + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()
        # draw X2 cursor
        if (not wait_x or self.position_b > wait_x) and (
            not self.delay_in or self.position_b > ((inter * self.delay_in) + wait_x)
        ):
            x1 = start_x + self.position_b - wait_x - (inter * self.delay_in)
            y1 = start_y + (
                (self.position_b - wait_x - (inter * self.delay_in)) * math.tan(angle)
            )
            if x1 > end_x:
                x1 = end_x
                y1 = end_y
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.arc(x1, y1, 8, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(10)
            cr.move_to(x1 - 5, y1 + 3)
            cr.show_text("B")
        else:  # Wait and Delay In
            x1 = start_x + self.position_b - wait_x - (inter * self.delay_in)
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
            cr.show_text("B")

        # draw times number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        cr.move_to(12, 16)
        cr.show_text("0")
        cr.move_to(allocation.width - 24, 16)
        # Draw Total Time at the end :
        # If time is integer don't show the ".0"
        if time_max.is_integer():
            cr.show_text(str(int(self.total_time)))
        else:
            cr.show_text(str(self.total_time))
        if time_max != self.total_time:
            cr.move_to(12 + (inter * time_max), 16)
            if time_max.is_integer():
                cr.show_text(str(int(time_max)))
            else:
                cr.show_text(str(time_max))
        if time_min != time_max:
            cr.move_to(12 + (inter * time_min), 16)
            if time_min.is_integer():
                cr.show_text(str(int(time_min)))
            else:
                cr.show_text(str(time_min))

    def do_realize(self):
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
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL
        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)
        self.set_realized(True)
        window.set_background_pattern(None)
