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
import math
import typing
from dataclasses import dataclass

from gi.repository import Gdk, GObject, Gtk

if typing.TYPE_CHECKING:
    import cairo
    from olc.curve import PointsCurve
    from olc.curve_edition import CurvesTab
    from olc.lightshow import LightShow
    from olc.patch_outputs import PatchOutputsTab
    from olc.tabs_manager import Tabs


@dataclass
class Point:
    """Just a point"""

    x: int = 0
    y: int = 0


# pylint: disable=too-many-instance-attributes
class CurvePointWidget(Gtk.DrawingArea):
    """Curve point widget"""

    __gtype_name__ = "CurvePointWidget"

    __gsignals__ = {"toggled": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(
        self,
        *args: typing.Any,  # noqa: ANN401
        number: int = 0,
        curve: PointsCurve | None = None,
        lightshow: LightShow | None = None,
        tabs: Tabs | None = None,
        **kwds: typing.Any,  # noqa: ANN401
    ) -> None:
        super().__init__(*args, **kwds)
        self.lightshow = lightshow
        self.tabs = tabs

        self.active = False
        self.number = number
        self.curve = curve
        evmask = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK
        self.set_events(evmask)
        self.connect("button_press_event", self.button_pressed)
        self.connect("motion_notify_event", self.motion_notify)
        self.offset = Point()
        self.prev = Point()
        self.max = Point()

    def button_pressed(self, widget: Gtk.Widget, event: Gdk.EventButton) -> None:
        """Button pressed

        Args:
            widget: Widget pressed
            event: Event with coordinates
        """
        if not self.tabs:
            return
        if event.button == 1:
            tab = typing.cast("CurvesTab", self.tabs.tabs["curves"])
            if not tab:
                return
            for toggle in tab.curve_edition.points:
                toggle.set_active(False)
                toggle.queue_draw()
            self.set_active(True)
            parent = widget.get_parent()
            if not parent:
                return
            window = parent.get_window()
            if not window:
                return
            self.offset.x, self.offset.y = window.get_root_origin()
            coords = parent.translate_coordinates(self.get_toplevel(), 0, 0)
            if coords:
                x, y = coords
                self.offset.x += x
                self.offset.y += y
            self.offset.x += int(event.x)
            self.offset.y += int(event.y)
            self.max.x = parent.get_allocation().width - widget.get_allocation().width
            self.max.y = parent.get_allocation().height - widget.get_allocation().height
            # Update Label with point coordinates
            x = round(event.x_root - self.offset.x)
            y = round(event.y_root + 40 - self.offset.y)
            # 20 = grid offset, 4 = point radius
            x = max(min(x, self.max.x), 20 - 4)
            y = max(min(y, self.max.y), 20 - 4)
            if not tab.curve_edition.edit_curve:
                return
            edit_wgt_width = tab.curve_edition.edit_curve.width
            edit_wgt_height = tab.curve_edition.edit_curve.height
            x_curve = round(((x - 20 + 4) / (edit_wgt_width - 40)) * 255)
            y_curve = round(
                ((edit_wgt_height - y - 20 - 4) / (edit_wgt_height - 40)) * 255
            )
            if tab.curve_edition.label:
                tab.curve_edition.label.set_label(f"{x_curve}, {y_curve}")

    def motion_notify(self, widget: Gtk.Widget, event: Gdk.EventMotion) -> None:
        """Button moved

        Args:
            widget: Widget moved
            event: Event with coordinates
        """
        if not self.curve:
            return
        x = round(event.x_root - self.offset.x)
        y = round(event.y_root + 40 - self.offset.y)
        # 20 = grid offset, 4 = point radius
        x = max(min(x, self.max.x), 20 - 4)
        y = max(min(y, self.max.y - 16), 20 - 4)
        if x != self.prev.x or y != self.prev.y:
            self.prev.x = x
            self.prev.y = y
            fixed = typing.cast("Gtk.Fixed", self.get_parent())
            if not fixed or not self.tabs:
                return
            tab = typing.cast("CurvesTab", self.tabs.tabs["curves"])
            if not tab or not tab.curve_edition or not tab.curve_edition.edit_curve:
                return
            edit_wgt_width = tab.curve_edition.edit_curve.width
            edit_wgt_height = tab.curve_edition.edit_curve.height
            x_curve = round(((x - 20 + 4) / (edit_wgt_width - 40)) * 255)
            y_curve = round(
                ((edit_wgt_height - y - 20 - 4) / (edit_wgt_height - 40)) * 255
            )
            # First point
            if self.number == 0 and tab.curve_edition.label:
                tab.curve_edition.label.set_label(f"0, {y_curve}")
                self.curve.points[self.number] = (0, y_curve)
                fixed.move(widget, 16, y)
            # Last point
            elif self.number == len(self.curve.points) - 1 and tab.curve_edition.label:
                tab.curve_edition.label.set_label(f"255, {y_curve}")
                self.curve.points[self.number] = (255, y_curve)
                fixed.move(widget, 976, y)
            # Don't move before/after previous/next point
            elif (
                not x_curve <= self.curve.points[self.number - 1][0]
                and not x_curve >= self.curve.points[self.number + 1][0]
                and tab.curve_edition.label
            ):
                tab.curve_edition.label.set_label(f"{x_curve}, {y_curve}")
                if any(x_curve in point for point in self.curve.points):
                    if self.curve.points[self.number][0] == x_curve:
                        self.curve.points[self.number] = (x_curve, y_curve)
                        fixed.move(widget, x, y)
                if not any(x_curve in point for point in self.curve.points):
                    self.curve.points[self.number] = (x_curve, y_curve)
                    fixed.move(widget, x, y)
            self.curve.populate_values()
            if self.lightshow:
                self.lightshow.set_modified()
            patch_outputs_tab = typing.cast(
                "PatchOutputsTab", self.tabs.tabs["patch_outputs"]
            )
            if patch_outputs_tab:
                patch_outputs_tab.refresh()

    def get_active(self) -> bool:
        """Return activate status

        Returns:
            True or False
        """
        if self.active:
            return True
        return False

    def set_active(self, active: bool) -> None:
        """Set activate status

        Args:
            active: True or False
        """
        self.active = active
        self.queue_draw()

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Curve Point Widget

        Args:
            cr: Cairo context
        """
        self.set_size_request(8, 8)
        cr.set_line_width(1)
        if self.get_active():
            cr.set_source_rgba(0.7, 0.5, 0.2, 1.0)
        else:
            cr.set_source_rgba(0.5, 0.3, 0.0, 1.0)
        cr.arc(4, 4, 4, 0, 2 * math.pi)
        cr.fill()
        return False
