# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Any, List
from gi.repository import Gdk, Gtk
from olc.curve import Curve, LimitCurve, BezierCurve
from olc.define import App
from olc.widgets.bezier_point import BezierPointWidget
from olc.widgets.edit_curve import EditCurveWidget
from olc.widgets.curve import CurveWidget


class CurveEdition(Gtk.Box):
    """Edition Widget"""

    curve_nb: int  # Curve number
    curve: Curve  # Curve
    points: List[BezierPointWidget]  # Bezier points widgets

    def __init__(self):
        self.points = None
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        # HeaderBar
        self.header = Gtk.HeaderBar()
        text = "Select curve"
        self.header.set_title(text)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button("New curve")
        button.connect("clicked", self.on_new_curve)
        box.add(button)
        self.header.pack_end(box)
        self.add(self.header)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.hbox)

    def change_curve(self, curve: int) -> None:
        """User selected a curve

        Args:
            curve: Curve number
        """
        # HeaderBar
        self.curve_nb = curve
        self.curve = App().curves.get_curve(curve)
        text = self.curve.name
        if isinstance(self.curve, LimitCurve):
            text += f" {round((self.curve.limit / 255) * 100)}%"
        self.header.set_title(text)
        for child in self.header.get_children():
            child.destroy()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button("New curve")
        button.connect("clicked", self.on_new_curve)
        box.add(button)
        if self.curve.editable:
            button = Gtk.Button("Remove curve")
            button.connect("clicked", self.on_del_curve)
            box.add(button)
        self.header.pack_end(box)
        # Display curve and tools
        for child in self.hbox.get_children():
            child.destroy()
        fixed = Gtk.Fixed()
        edit_curve = EditCurveWidget(self.curve_nb)
        fixed.put(edit_curve, 0, 0)
        if isinstance(self.curve, BezierCurve):
            self.points = []
            for point in self.curve.points:
                x = point[0]
                y = point[1]
                # Warning: SizeRequest used, not real size
                width = edit_curve.get_size_request()[0]
                height = edit_curve.get_size_request()[1]
                x = (
                    round((x / 255) * (width - (edit_curve.delta * 2)))
                    + edit_curve.delta
                )
                y = (
                    height
                    - edit_curve.delta
                    - round((y / 255) * (height - (edit_curve.delta * 2)))
                )
                self.points.append(BezierPointWidget(curve=self.curve))
                self.points[-1].connect("toggled", self.on_toggled, None)
                fixed.put(self.points[-1], x - 4, y - 4)
        self.hbox.add(fixed)
        if isinstance(self.curve, LimitCurve):
            adj = Gtk.Adjustment(self.curve.limit, 0, 255, 1, 10, 0)
            scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=adj)
            scale.set_digits(0)
            scale.set_inverted(True)
            scale.connect("value-changed", self.limit_changed)
            self.hbox.add(scale)
        self.show_all()

    def on_new_curve(self, _widget) -> None:
        """Create a new curve
        For now, a LimitCurve
        """
        curve_nb = App().curves.add_curve(LimitCurve(255))
        tab = App().tabs.tabs["curves"]
        self.change_curve(curve_nb)
        tab.refresh()
        flowboxchild = None
        for flowboxchild in tab.flowbox.get_children():
            if flowboxchild.get_child().curve_nb == curve_nb:
                break
        if flowboxchild:
            tab.flowbox.select_child(flowboxchild)

    def on_del_curve(self, _widget) -> None:
        """Delete selected curve"""
        tab = App().tabs.tabs["curves"]
        if selected := tab.flowbox.get_selected_children():
            flowboxchild = selected[0]
            curvebutton = flowboxchild.get_child()
            curve_nb = curvebutton.curve_nb
            App().curves.del_curve(curve_nb)
            self.change_curve(0)
            tab.refresh()

    def limit_changed(self, widget: Gtk.Scale) -> None:
        """LimitCurve value has been changed

        Args:
            widget: Scale
        """
        self.curve.limit = int(widget.get_value())
        self.curve.populate_values()
        text = self.curve.name
        text += f" {round((self.curve.limit / 255) * 100)}%*"
        self.header.set_title(text)

    def on_toggled(self, button, _name) -> None:
        """Bezier point clicked

        Args:
            button: Widget
        """
        if button.get_active():
            for toggle in self.points:
                if toggle is not button:
                    toggle.set_active(False)


class CurveButton(CurveWidget):
    """Curve Widget"""

    def __init__(self, curve: int):
        super().__init__(curve)
        self.header = Gtk.HeaderBar()

    def on_click(self, _button) -> None:
        """Button clicked"""
        tab = App().tabs.tabs["curves"]
        tab.curve_edition.change_curve(self.curve_nb)
        tab.flowbox.unselect_all()
        child = self.get_parent()
        tab.flowbox.select_child(child)


class CurvesTab(Gtk.Paned):
    """Tab to display and edit curves"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.curve_edition = CurveEdition()
        self.add1(self.curve_edition)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flowbox = None
        self.populate_curves()
        self.add2(self.scrolled)

    def populate_curves(self) -> None:
        """Add curves to tab"""
        # New Flowbox
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_activate_on_single_click(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # Add curves to Flowbox
        for number in App().curves.curves:
            self.flowbox.add(CurveButton(number))
        self.scrolled.add(self.flowbox)

    def refresh(self) -> None:
        """Refresh display"""
        self.scrolled.remove(self.flowbox)
        self.flowbox.destroy()
        self.populate_curves()
        self.flowbox.invalidate_filter()
        App().window.show_all()

    def on_close_icon(self, _widget) -> None:
        """Close Tab on clicked icon"""
        App().tabs.close("curves")

    def on_key_press_event(self, _widget, event: Gdk.Event) -> Any:
        """Key has been pressed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
        keyname = Gdk.keyval_name(event.keyval)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        App().tabs.close("curves")
