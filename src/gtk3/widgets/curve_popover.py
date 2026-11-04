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
"""Reusable popover for curve selection with carousel navigation."""

from __future__ import annotations

import typing
from typing import Callable, Optional

from gi.repository import Gdk, Gtk

from olc.gtk3.widgets.curve import CurveWidget, get_curve_display_name

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow


class CurvePreviewButton(CurveWidget):
    """Clickable curve preview button inside the selection popover."""

    def __init__(
        self,
        curve: int,
        lightshow: LightShow,
        popover: CurveSelectionPopover,
    ) -> None:
        super().__init__(curve, lightshow)
        self.popover = popover

    def on_click(self, _button: Gtk.Button) -> None:
        """Handle click on curve preview by selecting the curve."""
        self.popover.select_curve(self.curve_nb)


class CurveSelectionPopover(Gtk.Popover):
    """Popover displaying a carousel of available curves with preview and navigation."""

    lightshow: LightShow
    on_curve_selected: Callable[[int], None]
    stack: Gtk.Stack

    def __init__(
        self,
        lightshow: LightShow,
        on_curve_selected: Callable[[int], None],
    ) -> None:
        super().__init__()
        self.lightshow = lightshow
        self.on_curve_selected = on_curve_selected
        self.set_position(Gtk.PositionType.BOTTOM)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(hbox)

        prev_btn = Gtk.Button.new_with_label("<")
        prev_btn.connect("clicked", self._on_nav_clicked)
        hbox.pack_start(prev_btn, False, False, 10)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(500)
        hbox.pack_start(self.stack, False, False, 10)

        next_btn = Gtk.Button.new_with_label(">")
        next_btn.connect("clicked", self._on_nav_clicked)
        hbox.pack_end(next_btn, False, True, 10)

    def populate(self) -> None:
        """Rebuild stack pages matching current lightshow curves."""
        for child in self.stack.get_children():
            child.destroy()

        for number, curve in self.lightshow.curves.curves.items():
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            label = get_curve_display_name(curve)
            box.pack_start(Gtk.Label(label=label), False, False, 10)
            box.pack_start(
                CurvePreviewButton(number, self.lightshow, self),
                False,
                False,
                10,
            )
            self.stack.add_named(box, str(number))

    def open_for_curve(
        self,
        initial_curve_id: int,
        relative_to: Gtk.Widget,
        pointing_to: Optional[Gdk.Rectangle] = None,
    ) -> None:
        """Populate, anchor, position and display the popover.

        Args:
            initial_curve_id: Curve index to show initially.
            relative_to: Widget to anchor the popover to.
            pointing_to: Specific bounding box to point to.
        """
        self.populate()
        self.set_relative_to(relative_to)
        if pointing_to is not None:
            self.set_pointing_to(pointing_to)

        child = self.stack.get_child_by_name(str(initial_curve_id))
        if child is None:
            child = self.stack.get_child_by_name("0")
        if child is not None:
            child.show()
            self.stack.set_visible_child(child)

        self.show_all()
        self.popup()

    def _on_nav_clicked(self, button: Gtk.Button) -> None:
        """Navigate through curves in carousel."""
        label = button.get_label()
        visible_name = self.stack.get_visible_child_name()
        if not visible_name:
            return

        try:
            current_nb = int(visible_name)
        except ValueError:
            return

        curves_list = list(self.lightshow.curves.curves.keys())
        if not curves_list:
            return

        try:
            idx = curves_list.index(current_nb)
        except ValueError:
            idx = 0

        if label == ">":
            target = (
                curves_list[idx + 1] if idx + 1 < len(curves_list) else curves_list[0]
            )
        else:
            target = curves_list[idx - 1]

        child = self.stack.get_child_by_name(str(target))
        if child is not None:
            child.show()
            self.stack.set_visible_child(child)

    def select_curve(self, curve_nb: int) -> None:
        """Confirm selection of a curve, close popover, and trigger callback."""
        self.popdown()
        self.on_curve_selected(curve_nb)
