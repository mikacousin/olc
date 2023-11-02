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
import cairo
from gi.repository import Gdk, Gtk
from olc.curve import LimitCurve, SegmentsCurve, InterpolateCurve
from olc.define import App
from olc.widgets.curve_point import CurvePointWidget
from olc.widgets.edit_curve import EditCurveWidget
from olc.widgets.curve import CurveWidget


class Value(Gtk.Entry):
    """Edit curve value widget"""

    def __init__(self, x, y):
        super().__init__()
        x = str(x)
        y = str(y)

    def do_draw(self, cr):
        """Draw point values

        Args:
            cr: Cairo context
        """
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(8)
        cr.move_to(0, 20)
        cr.show_text(self.x)
        cr.move_to(0, 35)
        cr.show_text(self.y)


class CurveValues(Gtk.ScrolledWindow):
    """Display Curve values"""

    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Create 256 columns
        self.values = Gtk.ListStore(*(256 * (int,)))
        self.tree = Gtk.TreeView(model=self.values)
        self.tree.set_name("treeview_curve_values")
        # self.add(self.tree)

        self.draw = Gtk.DrawingArea()
        self.draw.connect("draw", self.on_draw)
        self.add(self.draw)

    def on_draw(self, _area, cr):
        """Draw grid

        Args:
            cr: Cairo context
        """
        if App().tabs.tabs["curves"].curve_edition.curve_nb is None:
            return
        self.set_size_request(1000, 240)
        curve_nb = App().tabs.tabs["curves"].curve_edition.curve_nb
        curve = App().curves.get_curve(curve_nb)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(8)
        x = 0
        for row in range(8):
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.move_to(2, 10 + row * 30)
            cr.show_text("Input")
            cr.move_to(2, 20 + row * 30)
            cr.show_text("Output")
            for column in range(32):
                cr.set_source_rgb(0.1, 0.1, 0.1)
                i = 41 + column * 20
                j = 1 + row * 30
                cr.rectangle(i, j, 17, 22)
                cr.stroke()
                if (
                    isinstance(curve, (SegmentsCurve, InterpolateCurve))
                    and (x, curve.values[x]) in curve.points
                ):
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                else:
                    cr.set_source_rgb(0.7, 0.7, 0.7)
                cr.move_to(i + 1, j + 9)
                cr.show_text(str(x))
                cr.move_to(i + 1, j + 19)
                cr.show_text(str(curve.values[x]))
                x += 1

    def refresh(self, curve):
        """Update Treeview when curve changed

        Args:
            curve: Curve selected
        """
        # TODO: Unused, must be deleted
        self.draw.queue_draw()
        self.values.clear()
        y = []
        for x in range(256):
            y.append(curve.values[x])
        self.values.append(y)

        for column in self.tree.get_columns():
            self.tree.remove_column(column)

        for val in range(256):
            renderer = Gtk.CellRendererText()
            if isinstance(curve, (SegmentsCurve, InterpolateCurve)):
                if (val, y[val]) in curve.points:
                    renderer.set_property("foreground", "#997004")
            column = Gtk.TreeViewColumn(str(val), renderer, text=val)
            self.tree.append_column(column)


class CurveEdition(Gtk.Box):
    """Edition Widget"""

    curve_nb: int  # Curve number
    points: List[CurvePointWidget]  # Points widgets

    def __init__(self):
        self.curve_nb = None
        self.points = []
        self.fixed = None
        self.edit_curve = None
        self.label = None
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        # HeaderBar
        self.header = Gtk.HeaderBar()
        text = "Select curve"
        self.header.set_title(text)
        self.add(self.header)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.add(self.hbox)
        self.values = CurveValues()
        vbox.add(self.values)
        self.add(vbox)

    def change_curve(self, curve_nb: int) -> None:
        """User selected a curve

        Args:
            curve_nb: Curve number
        """
        # HeaderBar
        self.curve_nb = curve_nb
        curve = App().curves.get_curve(curve_nb)
        text = curve.name
        if isinstance(curve, LimitCurve):
            text += f" {round((curve.limit / 255) * 100)}%"
        self.header.set_title(text)
        for child in self.header.get_children():
            child.destroy()
        if curve.editable:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            button = Gtk.Button("Remove curve")
            button.connect("clicked", self.on_del_curve)
            box.add(button)
            self.header.pack_end(box)
        # Display curve and tools
        for child in self.hbox.get_children():
            child.destroy()
        self.fixed = Gtk.Fixed()
        self.edit_curve = EditCurveWidget(self.curve_nb)
        self.fixed.put(self.edit_curve, 0, 0)
        self.label = Gtk.Label("X, Y")
        self.fixed.put(self.label, 0, 0)
        if isinstance(curve, (SegmentsCurve, InterpolateCurve)) and curve.editable:
            self.points_curve()
        self.hbox.add(self.fixed)
        # Add special widgets
        if isinstance(curve, LimitCurve):
            adj = Gtk.Adjustment(curve.limit, 0, 255, 1, 10, 0)
            scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=adj)
            scale.set_digits(0)
            scale.set_inverted(True)
            scale.connect("value-changed", self.limit_changed)
            self.hbox.add(scale)
        # self.values.refresh(curve)
        self.values.draw.queue_draw()
        self.show_all()

    def points_curve(self) -> None:
        """Generate PointWidgets"""
        if self.points:
            for point in self.points:
                point.destroy()
        self.points.clear()
        curve = App().curves.get_curve(self.curve_nb)
        for number, point in enumerate(curve.points):
            x = point[0]
            y = point[1]
            # Warning: SizeRequest used, not real size
            width = self.edit_curve.get_size_request()[0]
            height = self.edit_curve.get_size_request()[1]
            x = (
                round((x / 255) * (width - (self.edit_curve.delta * 2)))
                + self.edit_curve.delta
            )
            y = (
                height
                - self.edit_curve.delta
                - round((y / 255) * (height - (self.edit_curve.delta * 2)))
            )
            self.points.append(CurvePointWidget(number=number, curve=curve))
            self.points[-1].connect("toggled", self.on_toggled, None)
            self.fixed.put(self.points[-1], x - 4, y - 4)
        self.show_all()

    def on_del_curve(self, _widget) -> None:
        """Delete selected curve"""
        tab = App().tabs.tabs["curves"]
        if selected := tab.flowbox.get_selected_children():
            flowboxchild = selected[0]
            curvebutton = flowboxchild.get_child()
            curve_nb = curvebutton.curve_nb
            App().curves.del_curve(curve_nb)
            self.change_curve(0)
            curve_nb = 0
            tab.refresh()
            flowboxchild = None
            for flowboxchild in tab.flowbox.get_children():
                if flowboxchild.get_child().curve_nb == curve_nb:
                    break
            if flowboxchild:
                tab.flowbox.select_child(flowboxchild)

    def limit_changed(self, widget: Gtk.Scale) -> None:
        """LimitCurve value has been changed

        Args:
            widget: Scale
        """
        curve = App().curves.get_curve(self.curve_nb)
        curve.limit = int(widget.get_value())
        curve.populate_values()
        text = curve.name
        text += f" {round((curve.limit / 255) * 100)}%"
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
        # self.header = Gtk.HeaderBar()
        self.popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry()
        entry.set_has_frame(False)
        entry.set_text(self.curve.name)
        entry.connect("activate", self.on_edit)
        vbox.pack_start(entry, False, True, 10)
        vbox.show_all()
        self.popover.add(vbox)
        self.popover.set_relative_to(self)
        self.popover.set_position(Gtk.PositionType.BOTTOM)

    def on_edit(self, widget: Gtk.Entry) -> None:
        """Edit Curve name

        Args:
            widget: Entry used
        """
        text = widget.get_text()
        self.curve.name = text
        App().tabs.tabs["curves"].curve_edition.header.set_title(text)
        self.popover.popdown()

    def on_click(self, _button) -> None:
        """Button clicked"""
        child = self.get_parent()
        if not child.is_selected():
            tab = App().tabs.tabs["curves"]
            tab.curve_edition.change_curve(self.curve_nb)
            tab.flowbox.unselect_all()
            tab.flowbox.select_child(child)
        elif self.curve.editable:
            self.popover.popup()


class CurvesTab(Gtk.Paned):
    """Tab to display and edit curves"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_position(600)

        self.curve_edition = CurveEdition()
        self.add1(self.curve_edition)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_homogeneous(False)
        self.header = Gtk.HeaderBar()
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button("New Limit curve")
        button.connect("clicked", self.on_new_curve)
        header_box.add(button)
        button = Gtk.Button("New Segments curve")
        button.connect("clicked", self.on_new_curve)
        header_box.add(button)
        button = Gtk.Button("New Interpolate curve")
        button.connect("clicked", self.on_new_curve)
        header_box.add(button)
        self.header.pack_end(header_box)
        box.add(self.header)
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flowbox = None
        self.populate_curves()
        box.add(self.scrolled)
        box.set_child_packing(self.scrolled, True, True, 0, Gtk.PackType.START)
        self.add2(box)

    def on_new_curve(self, widget) -> None:
        """Create new curve

        Args:
            widget: button clicked
        """
        if widget.get_label() == "New Limit curve":
            curve_nb = App().curves.add_curve(LimitCurve(255))
        elif widget.get_label() == "New Segments curve":
            curve_nb = App().curves.add_curve(SegmentsCurve())
        elif widget.get_label() == "New Interpolate curve":
            curve_nb = App().curves.add_curve(InterpolateCurve())
        self.curve_edition.change_curve(curve_nb)
        self.refresh()
        flowboxchild = None
        for flowboxchild in self.flowbox.get_children():
            if flowboxchild.get_child().curve_nb == curve_nb:
                break
        if flowboxchild:
            self.flowbox.select_child(flowboxchild)

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

    def _keypress_delete(self) -> None:
        """Delete selected point"""
        if not self.curve_edition.curve_nb:
            return
        curve = App().curves.get_curve(self.curve_edition.curve_nb)
        if isinstance(curve, (SegmentsCurve, InterpolateCurve)):
            for toggle in self.curve_edition.points:
                if toggle.get_active():
                    curve.del_point(toggle.number)
                    self.curve_edition.points_curve()
                    self.curve_edition.queue_draw()
                    if App().tabs.tabs["patch_outputs"]:
                        App().tabs.tabs["patch_outputs"].refresh()
                    break
