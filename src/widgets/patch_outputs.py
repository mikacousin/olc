# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
import cairo
from gi.repository import Gdk, Gtk
from olc.curve import LimitCurve
from olc.define import App, UNIVERSES
from olc.widgets.curve import CurveWidget
from .common import rounded_rectangle_fill, rounded_rectangle


class CurvePatchOutputWidget(CurveWidget):
    """Curve Widget"""

    def __init__(self, curve: int, widget):
        self.parent_widget = widget
        super().__init__(curve)

    def on_click(self, _button) -> None:
        """Button clicked"""
        self.parent_widget.popover.popdown()
        tab = App().tabs.tabs["patch_outputs"]
        outputs = tab.get_selected_outputs()
        for output in outputs:
            out = output[0]
            univ = output[1]
            if (
                univ in App().backend.patch.outputs
                and out in App().backend.patch.outputs[univ]
            ):
                App().backend.patch.outputs[univ][out][1] = self.curve_nb
        tab.refresh()
        App().ascii.set_modified()


class PatchWidget(Gtk.DrawingArea):
    """Patch output widget"""

    __gtype_name__ = "PatchWidget"

    def __init__(self, universe, output):
        self.universe = universe
        self.output = output

        super().__init__()
        self.scale = 1.0
        self.width = 70 * self.scale
        self.set_size_request(self.width, self.width)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_click)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.connect("touch-event", self.on_click)

        self.popover = None
        self.stack = None

    def on_click(self, _tgt, event: Gdk.Event) -> None:
        """Widget clicked

        Args:
            event: Event with Keyboard modifiers
        """
        index = UNIVERSES.index(self.universe)
        widget_index = self.output - 1 + (512 * index)
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            # Shift pressed: Thru
            App().window.commandline.set_string(f"{self.output}.{self.universe}")
            App().backend.patch.by_outputs.thru()
        elif event.state & accel_mask == Gdk.ModifierType.CONTROL_MASK:
            # Control pressed: Toggle selected status
            child = (
                App()
                .tabs.tabs["patch_outputs"]
                .flowbox.get_child_at_index(widget_index)
            )
            if self.get_parent().is_selected():
                App().tabs.tabs["patch_outputs"].flowbox.unselect_child(child)
                App().window.commandline.set_string(f"{self.output}.{self.universe}")
                App().backend.patch.by_outputs.del_output()
            else:
                App().tabs.tabs["patch_outputs"].flowbox.select_child(child)
                App().window.commandline.set_string(f"{self.output}.{self.universe}")
                App().backend.patch.by_outputs.add_output()
        else:
            child = (
                App()
                .tabs.tabs["patch_outputs"]
                .flowbox.get_child_at_index(widget_index)
            )
            if not child.is_selected():
                App().window.commandline.set_string(f"{self.output}.{self.universe}")
                App().backend.patch.by_outputs.select_output()
            elif (
                self.universe in App().backend.patch.outputs
                and self.output in App().backend.patch.outputs[self.universe]
            ):
                # Change curve only on patched outputs
                self.open_popup()

    def open_popup(self) -> None:
        """Create and open popup to change curve"""
        if not self.popover:
            self.popover = Gtk.Popover()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            self.popover.add(hbox)
            self.popover.set_relative_to(self)
            self.popover.set_position(Gtk.PositionType.BOTTOM)
        else:
            hbox = self.popover.get_children()[0]
        children = hbox.get_children()
        # Delete old curves widgets
        if children:
            for child in children:
                child.destroy()
        button = Gtk.Button.new_with_label("<")
        button.connect("clicked", self.curve_change)
        hbox.pack_start(button, False, False, 10)
        # Add curves widgets
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(500)
        for number, curve in App().curves.curves.items():
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            label = curve.name
            if isinstance(curve, LimitCurve):
                label += f" {round((curve.limit / 255) * 100)}%"
            box.pack_start(Gtk.Label(label=label), False, False, 10)
            box.pack_start(CurvePatchOutputWidget(number, self), False, False, 10)
            self.stack.add_named(box, str(number))
        curve_nb = App().backend.patch.outputs[self.universe][self.output][1]
        child = self.stack.get_child_by_name(str(curve_nb))
        child.show()
        self.stack.set_visible_child(child)
        hbox.pack_start(self.stack, False, False, 10)
        button = Gtk.Button.new_with_label(">")
        button.connect("clicked", self.curve_change)
        hbox.pack_end(button, False, True, 10)
        hbox.show_all()
        self.popover.popup()

    def curve_change(self, button: Gtk.Button) -> None:
        """Change selected curve (not change output curve)

        Args:
            button: Button clicked
        """
        label = button.get_label()
        if label in ">":
            curve_nb = int(self.stack.get_visible_child_name())
            keys = iter(App().curves.curves)
            curve_nb in keys  # pylint: disable=W0104
            next_curve = next(keys, False)
            if not next_curve:
                next_curve = 0
            child = self.stack.get_child_by_name(str(next_curve))
            child.show()
            self.stack.set_visible_child(child)
        else:
            curve_nb = int(self.stack.get_visible_child_name())
            keys = iter(App().curves.curves)
            curves_list = list(App().curves.curves.keys())
            i = 0
            for i, number in enumerate(curves_list):
                if number == curve_nb:
                    break
            prev_curve = curves_list[i - 1]
            child = self.stack.get_child_by_name(str(prev_curve))
            child.show()
            self.stack.set_visible_child(child)

    def do_draw(self, cr):
        """Draw widget

        Args:
            cr: Cairo context
        """
        self.width = 70 * self.scale
        self.set_size_request(self.width, self.width)
        allocation = self.get_allocation()
        # Draw background
        self._draw_background(cr, allocation)
        # Draw output number
        self._draw_output_number(cr, allocation)
        # Draw channel number
        self._draw_channel_number(cr, allocation)
        # Draw Output level
        self._draw_output_level(cr, allocation)
        # Draw Curve
        self._draw_curve(cr, allocation)

    def _draw_background(self, cr, allocation):
        """Draw background

        Args:
            cr: Cairo context
            allocation: Widget's allocation
        """
        area = (1, allocation.width - 2, 1, allocation.height - 2)
        if (
            self.universe in App().backend.patch.outputs
            and self.output in App().backend.patch.outputs[self.universe]
        ):
            number = App().backend.patch.outputs[self.universe][self.output][1]
            curve = App().curves.get_curve(number)
            if curve.is_all_zero():
                # Level's output blocked at 0
                if self.get_parent().is_selected():
                    cr.set_source_rgb(0.8, 0.1, 0.1)
                else:
                    cr.set_source_rgb(0.5, 0.1, 0.1)
                rounded_rectangle_fill(cr, area, 10)
            elif App().backend.patch.outputs[self.universe][self.output][0] != 0:
                # Patch output
                cr.set_source_rgb(0.3, 0.3, 0.3)
                rounded_rectangle_fill(cr, area, 10)
                if self.get_parent().is_selected():
                    cr.set_source_rgb(0.6, 0.4, 0.1)
                    rounded_rectangle(cr, area, 10)
        elif self.get_parent().is_selected():
            # Unpatched output
            cr.set_source_rgb(0.6, 0.4, 0.1)
            rounded_rectangle(cr, area, 10)
        index = UNIVERSES.index(self.universe)
        if App().backend.dmx.frame[index][self.output - 1]:
            level = App().backend.dmx.frame[index][self.output - 1]
            # cr.move_to(0, 0)
            cr.set_source_rgba(
                0.3 + (0.2 / 255 * level), 0.3, 0.3 - (0.3 / 255 * level), 0.6
            )
            area = (1, allocation.width - 2, 1, allocation.height - 2)
            rounded_rectangle_fill(cr, area, 10)

    def _draw_output_number(self, cr, allocation):
        """Draw Output number

        Args:
            cr: Cairo context
            allocation: Widget alocation
        """
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(11 * self.scale)
        text = f"{self.output}.{self.universe}"
        (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
        cr.move_to(
            allocation.width / 2 - width / 2, allocation.height / 4 - (height - 20) / 4
        )
        cr.show_text(text)

    def _draw_channel_number(self, cr, allocation):
        """Draw Channel number

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(11 * self.scale)
        if (
            self.universe in App().backend.patch.outputs
            and self.output in App().backend.patch.outputs[self.universe]
        ):
            text = str(App().backend.patch.outputs[self.universe][self.output][0])
            (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
            if App().backend.patch.outputs[self.universe][self.output][0] > 0:
                cr.move_to(
                    allocation.width / 2 - width / 2,
                    3 * (allocation.height / 4 - (height - 20) / 4),
                )
                cr.show_text(text)

    def _draw_output_level(self, cr, allocation):
        """Draw Output level

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        index = UNIVERSES.index(self.universe)
        if App().backend.dmx.frame[index][self.output - 1]:
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(10 * self.scale)
            level = App().backend.dmx.frame[index][self.output - 1]
            text = str(level)
            (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
            cr.move_to(
                allocation.width / 2 - width / 2,
                allocation.height / 2 - (height - 20) / 2,
            )
            cr.show_text(text)

    def _draw_curve(self, cr, allocation):
        """Draw Dimmer Curve

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        if (
            self.universe in App().backend.patch.outputs
            and self.output in App().backend.patch.outputs[self.universe]
        ):
            number = App().backend.patch.outputs[self.universe][self.output][1]
            # Don't draw linear curve
            if number:
                curve = App().curves.get_curve(number)
                cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
                cr.set_line_width(1)
                cr.move_to(10, allocation.height - curve.values[0] - 10)
                for x, y in curve.values.items():
                    cr.line_to(
                        10 + (x / 255) * (allocation.width - 20),
                        (allocation.height - 10)
                        - ((y / 255) * (allocation.height - 20)),
                    )
                cr.stroke()
