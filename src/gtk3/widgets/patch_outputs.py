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

import typing

import cairo
from gi.repository import Gdk, Gtk

from olc.gtk3.widgets.common import rounded_rectangle, rounded_rectangle_fill
from olc.gtk3.widgets.curve import CurveWidget, get_curve_display_name

if typing.TYPE_CHECKING:
    from olc.core.backends import DMXBackend
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.patch_outputs import PatchOutputsTab


class CurvePatchOutputWidget(CurveWidget):
    """Curve Widget"""

    def __init__(
        self,
        curve: int,
        lightshow: LightShow,
        widget: PatchWidget,
        tab: PatchOutputsTab,
    ) -> None:
        super().__init__(curve, lightshow)
        self.parent_widget = widget
        self.lightshow = lightshow
        self.tab = tab

    def on_click(self, _button: Gtk.Widget) -> None:
        """Button clicked"""
        if not self.parent_widget.popover:
            return
        self.parent_widget.popover.popdown()
        outputs = self.tab.get_selected_outputs()
        for output in outputs:
            out = output[0]
            univ = output[1]
            if (
                univ in self.lightshow.patch.outputs
                and out in self.lightshow.patch.outputs[univ]
                and self.lightshow.app is not None
            ):
                self.lightshow.app.core.action_registry.execute(
                    "patch.set_output_curve", out, univ, self.curve_nb
                )


# pylint: disable=too-many-instance-attributes
class PatchWidget(Gtk.DrawingArea):
    """Patch output widget"""

    __gtype_name__ = "PatchWidget"

    stack: Gtk.Stack | None
    popover: Gtk.Popover | None
    app: Application
    lightshow: LightShow
    tab: PatchOutputsTab
    commandline: CoreCommandLine
    backend: DMXBackend

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        universe: int,
        output: int,
        app: Application,
        tab: PatchOutputsTab,
    ) -> None:
        self.universe = universe
        self.output = output
        self.app = app
        self.lightshow = app.core.lightshow
        self.tab = tab
        self.commandline = app.core.commandline
        self.backend = (
            app.core.backend
            if app.core.backend is not None
            else typing.cast(typing.Any, None)
        )

        super().__init__()
        self.scale = 1.0
        self.width = round(70 * self.scale)
        self.set_size_request(self.width, self.width)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_click)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.connect("touch-event", self.on_click)

        self.popover = None
        self.stack = None

    def on_click(self, _tgt: Gtk.Widget, event: Gdk.EventButton) -> None:
        """Widget clicked

        Args:
            event: Event with Keyboard modifiers
        """
        index = (
            self.tab.patch.universes.index(self.universe)
            if self.universe in self.tab.patch.universes
            else 0
        )
        widget_index = self.output - 1 + (512 * index)
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            # Shift pressed: Thru
            self.app.core.action_registry.execute(
                "commandline.set", f"{self.output}.{self.universe}"
            )
            self.tab.patch_by_outputs.thru()
        elif event.state & accel_mask == Gdk.ModifierType.CONTROL_MASK:
            # Control pressed: Toggle selected status
            child = self.tab.flowbox.get_child_at_index(widget_index)
            if not child:
                return
            parent = typing.cast("Gtk.FlowBoxChild", self.get_parent())
            if parent.is_selected():
                self.tab.flowbox.unselect_child(child)
                self.app.core.action_registry.execute(
                    "commandline.set", f"{self.output}.{self.universe}"
                )
                self.tab.patch_by_outputs.del_output()
            else:
                self.tab.flowbox.select_child(child)
                self.app.core.action_registry.execute(
                    "commandline.set", f"{self.output}.{self.universe}"
                )
                self.tab.patch_by_outputs.add_output()
        else:
            child = self.tab.flowbox.get_child_at_index(widget_index)
            if not child:
                return
            if not child.is_selected():
                self.app.core.action_registry.execute(
                    "commandline.set", f"{self.output}.{self.universe}"
                )
                self.tab.patch_by_outputs.select_output()
            elif (
                self.universe in self.lightshow.patch.outputs
                and self.output in self.lightshow.patch.outputs[self.universe]
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
            hbox = typing.cast("Gtk.Box", self.popover.get_children()[0])
        children = hbox.get_children()
        # Delete old curves widgets
        if children:
            for chld in children:
                chld.destroy()
        button = Gtk.Button.new_with_label("<")
        button.connect("clicked", self.curve_change)
        hbox.pack_start(button, False, False, 10)
        # Add curves widgets
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(500)
        for number, curve in self.lightshow.curves.curves.items():
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            label = get_curve_display_name(curve)
            box.pack_start(Gtk.Label(label=label), False, False, 10)
            box.pack_start(
                CurvePatchOutputWidget(number, self.lightshow, self, self.tab),
                False,
                False,
                10,
            )
            self.stack.add_named(box, str(number))
        curve_nb = self.lightshow.patch.outputs[self.universe][self.output][1]
        child = self.stack.get_child_by_name(str(curve_nb))
        if child:
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
        if not self.stack:
            return

        label = button.get_label()

        number = self.stack.get_visible_child_name()
        if not number:
            return
        curve_nb = int(number)

        curves_list = list(self.lightshow.curves.curves.keys())

        try:
            idx = curves_list.index(curve_nb)
        except ValueError:
            idx = 0

        if label in ">":
            if idx + 1 < len(curves_list):
                target_curve = curves_list[idx + 1]
            else:
                target_curve = 0
        else:
            target_curve = curves_list[idx - 1]

        child = self.stack.get_child_by_name(str(target_curve))
        if child:
            child.show()
            self.stack.set_visible_child(child)

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw widget

        Args:
            cr: Cairo context
        """
        self.width = round(70 * self.scale)
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
        return False

    def _draw_background(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw background

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        area = (1, allocation.width - 2, 1, allocation.height - 2)
        parent = typing.cast("Gtk.FlowBoxChild", self.get_parent())
        occupant = self.lightshow.patch.get_address_occupant(self.universe, self.output)
        if (
            self.universe in self.lightshow.patch.outputs
            and self.output in self.lightshow.patch.outputs[self.universe]
        ):
            number = self.lightshow.patch.outputs[self.universe][self.output][1]
            curve = self.lightshow.curves.get_curve(number)
            if curve and curve.is_all_zero():
                # Level output blocked at 0
                if parent.is_selected():
                    cr.set_source_rgb(0.8, 0.1, 0.1)
                else:
                    cr.set_source_rgb(0.5, 0.1, 0.1)
                rounded_rectangle_fill(cr, area, 10)
            elif self.lightshow.patch.outputs[self.universe][self.output][0] != 0:
                # Patch output
                cr.set_source_rgb(0.3, 0.3, 0.3)
                rounded_rectangle_fill(cr, area, 10)
                if parent.is_selected():
                    cr.set_source_rgb(0.6, 0.4, 0.1)
                    rounded_rectangle(cr, area, 10)
        elif occupant is not None and occupant > 0:
            cr.set_source_rgb(0.3, 0.3, 0.3)
            rounded_rectangle_fill(cr, area, 10)
            if parent.is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
                rounded_rectangle(cr, area, 10)
        elif parent.is_selected():
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
                # cr.move_to(0, 0)
                cr.set_source_rgba(
                    0.3 + (0.2 / 255 * level), 0.3, 0.3 - (0.3 / 255 * level), 0.6
                )
                area = (1, allocation.width - 2, 1, allocation.height - 2)
                rounded_rectangle_fill(cr, area, 10)

    def _draw_output_number(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw Output number

        Args:
            cr: Cairo context
            allocation: Widget allocation
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

    def _draw_channel_number(  # pylint: disable=too-many-locals
        self, cr: cairo.Context, allocation: Gdk.Rectangle
    ) -> None:
        """Draw Channel number and parameter name

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

        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
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
        """Draw Output level

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        if self.universe in self.tab.patch.universes:
            index = self.tab.patch.universes.index(self.universe)
            if (
                index < len(self.backend.dmx.frame)
                and self.backend.dmx.frame[index][self.output - 1]
            ):
                cr.set_source_rgb(0.7, 0.7, 0.7)
                cr.select_font_face(
                    "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD
                )
                cr.set_font_size(10 * self.scale)
                level = self.backend.dmx.frame[index][self.output - 1]
                text = str(level)
                (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
                cr.move_to(
                    allocation.width / 2 - width / 2,
                    allocation.height / 2 - (height - 20) / 2,
                )
                cr.show_text(text)

    def _draw_curve(self, cr: cairo.Context, allocation: Gdk.Rectangle) -> None:
        """Draw Dimmer Curve

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
