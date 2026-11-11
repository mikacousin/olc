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
from gettext import gettext as _
from typing import Optional

from gi.repository import Gtk

from olc.curve import InterpolateCurve, LimitCurve, PointsCurve, SegmentsCurve
from olc.gtk3.dmx_outputs import DMXOutputsTab
from olc.gtk3.widgets.curve import CurveWidget, get_curve_display_name
from olc.gtk3.widgets.curve_point import CurvePointWidget, LimitPointWidget
from olc.gtk3.widgets.curve_points_table import CurvePointsTable
from olc.gtk3.widgets.curve_sampled_monitor import CurveSampledMonitor
from olc.gtk3.widgets.curve_units import CurveUnitMode
from olc.gtk3.widgets.edit_curve import EditCurveWidget

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.lightshow import LightShow
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window


# Backward compatibility alias
CurveValues = CurveSampledMonitor


class _ValuesCompatibilityWrapper:
    """Compatibility shim for legacy curve_edition.values.queue_draw() calls."""

    def __init__(self, edition: CurveEdition) -> None:
        self._edition = edition

    def queue_draw(self) -> None:
        if hasattr(self._edition, "sampled_monitor") and self._edition.sampled_monitor:
            self._edition.sampled_monitor.queue_draw()
        if hasattr(self._edition, "points_table") and self._edition.points_table:
            self._edition.points_table.refresh()


# pylint: disable=too-many-instance-attributes
class CurveEdition(Gtk.Box):
    """Edition Widget"""

    curve_nb: int | None  # Curve number
    points: list[CurvePointWidget]  # Points widgets
    limit_point: LimitPointWidget | None
    fixed: Gtk.Fixed | None
    edit_curve: EditCurveWidget | None
    label: Gtk.Label | None
    pending_active_point_idx: int | None
    points_table: CurvePointsTable
    sampled_monitor: CurveSampledMonitor
    remove_box: Gtk.Box | None
    limit_box: Gtk.Box
    limit_spin: Gtk.SpinButton
    updating_limit_spin: bool
    scale_widget: Gtk.Scale | None
    updating_slider: bool

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        header: Gtk.HeaderBar | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.lightshow = lightshow
        self.tabs = tabs
        self.curve_nb = None
        self.points = []
        self.limit_point = None
        self.fixed = None
        self.edit_curve = None
        self.label = None
        self.scale_widget = None
        self.updating_slider = False
        self.updating_limit_spin = False
        self.pending_active_point_idx = None
        self.remove_box = None

        # HeaderBar: dedicated header bar for curve edition
        if header is not None:
            self.header = header
        else:
            self.header = Gtk.HeaderBar()
            self.header.set_title(_("Select curve"))
            self.pack_start(self.header, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.add(self.hbox)

        # Lower control container
        self.bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Toolbar: Unit selector & Point actions
        self.toolbar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.toolbar_box.set_margin_start(10)
        self.toolbar_box.set_margin_end(10)
        self.toolbar_box.set_margin_top(4)

        unit_label = Gtk.Label(label=_("Display unit:"))
        self.toolbar_box.pack_start(unit_label, False, False, 0)

        self.unit_combo = Gtk.ComboBoxText()
        for mode in CurveUnitMode:
            self.unit_combo.append(mode.value, mode.label)
        self.unit_combo.set_active_id(CurveUnitMode.PERCENT.value)
        self.unit_combo.connect("changed", self._on_unit_mode_changed)
        self.toolbar_box.pack_start(self.unit_combo, False, False, 0)

        # Limit control for LimitCurve
        self.limit_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.limit_box.set_margin_start(16)
        limit_label = Gtk.Label(label=_("Limit:"))
        self.limit_box.pack_start(limit_label, False, False, 0)

        adj = Gtk.Adjustment(
            value=100.0,
            lower=0.0,
            upper=100.0,
            step_increment=1.0,
            page_increment=10.0,
            page_size=0.0,
        )
        self.limit_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1.0, digits=1)
        self.limit_spin.set_numeric(True)
        self.limit_spin.connect("value-changed", self._on_limit_spin_changed)
        self.limit_box.pack_start(self.limit_spin, False, False, 0)
        self.limit_box.show_all()
        self.limit_box.set_no_show_all(True)
        self.limit_box.set_visible(False)
        self.toolbar_box.pack_start(self.limit_box, False, False, 0)

        # Action buttons for PointsCurve
        self.points_actions_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        self.btn_add_point = Gtk.Button(label=_("+ Add Point"))
        self.btn_add_point.connect("clicked", lambda _: self.points_table.add_point())
        self.points_actions_box.pack_start(self.btn_add_point, False, False, 0)

        self.btn_del_point = Gtk.Button(label=_("- Delete Point"))
        self.btn_del_point.connect(
            "clicked", lambda _: self.points_table.delete_point()
        )
        self.points_actions_box.pack_start(self.btn_del_point, False, False, 0)
        self.points_actions_box.show_all()
        self.points_actions_box.set_no_show_all(True)

        self.toolbar_box.pack_end(self.points_actions_box, False, False, 0)
        self.bottom_box.pack_start(self.toolbar_box, False, False, 0)

        # Sampled Monitor (full width under toolbar, fixed height)
        self.monitor_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2
        )
        self.monitor_container.set_margin_start(10)
        self.monitor_container.set_margin_end(10)
        monitor_title = Gtk.Label(label=_("Sampled Readout (11 steps)"))
        monitor_title.set_xalign(0.0)
        monitor_title.get_style_context().add_class("dim-label")
        self.monitor_container.pack_start(monitor_title, False, False, 0)

        self.sampled_monitor = CurveSampledMonitor(lightshow=self.lightshow)
        self.sampled_monitor.set_valign(Gtk.Align.START)
        self.monitor_container.pack_start(self.sampled_monitor, False, False, 0)
        self.bottom_box.pack_start(self.monitor_container, False, False, 0)

        # Points Table (full width below monitor, visible for PointsCurve)
        self.table_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.table_container.set_margin_start(10)
        self.table_container.set_margin_end(10)
        self.table_container.set_margin_bottom(6)
        table_title = Gtk.Label(label=_("Control Points (In / Out)"))
        table_title.set_xalign(0.0)
        table_title.get_style_context().add_class("dim-label")
        self.table_container.pack_start(table_title, False, False, 0)

        self.points_table = CurvePointsTable(
            lightshow=self.lightshow, curve_edition=self
        )
        self.table_container.pack_start(self.points_table, True, True, 0)
        self.table_container.show_all()
        self.table_container.set_no_show_all(True)
        self.bottom_box.pack_start(self.table_container, True, True, 0)

        vbox.pack_start(self.bottom_box, True, True, 0)
        self.pack_start(vbox, True, True, 0)

        # Backward compatibility wrapper for values.queue_draw()
        self.values = _ValuesCompatibilityWrapper(self)

    def _on_unit_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        """Handle change of active unit mode."""
        active_id = combo.get_active_id()
        if not active_id:
            return
        mode = CurveUnitMode(active_id)
        self.points_table.set_unit_mode(mode)
        self.sampled_monitor.set_unit_mode(mode)
        self._update_limit_spin_config()

    def change_curve(self, curve_nb: int) -> None:
        """User selected a curve

        Args:
            curve_nb: Curve number
        """
        # HeaderBar
        self.curve_nb = curve_nb
        curve = self.lightshow.curves.get_curve(curve_nb)
        if curve is None:
            return
        self.header.set_title(get_curve_display_name(curve))
        if self.remove_box is not None:
            self.remove_box.destroy()
            self.remove_box = None
        if curve.editable:
            self.remove_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            button = Gtk.Button(label=_("Remove curve"))
            button.connect("clicked", self.on_del_curve)
            self.remove_box.add(button)
            self.header.pack_end(self.remove_box)
            self.remove_box.show_all()
        self.scale_widget = None
        if self.limit_point is not None:
            self.limit_point.destroy()
            self.limit_point = None

        # Display curve and tools
        for child in self.hbox.get_children():
            child.destroy()
        self.fixed = Gtk.Fixed()
        self.edit_curve = EditCurveWidget(
            curve_nb, lightshow=self.lightshow, tabs=self.tabs
        )
        self.fixed.put(self.edit_curve, 0, 0)
        self.label = Gtk.Label(label="")
        self.fixed.put(self.label, 0, 0)
        if isinstance(curve, PointsCurve) and curve.editable:
            self.points_curve()
        elif isinstance(curve, LimitCurve) and curve.editable:
            self.limit_curve_point()
        self.hbox.add(self.fixed)

        # Update points table & sampled monitor
        if isinstance(curve, PointsCurve):
            self.table_container.set_visible(True)
            self.points_actions_box.set_visible(curve.editable)
            self.points_table.set_curve(curve_nb)
        else:
            self.table_container.set_visible(False)
            self.points_actions_box.set_visible(False)
            self.points_table.set_curve(None)

        # LimitCurve toolbar controls
        if isinstance(curve, LimitCurve):
            self.limit_box.set_visible(True)
            self._update_limit_spin_config()
        else:
            self.limit_box.set_visible(False)

        self.sampled_monitor.set_curve(curve_nb)
        self.values.queue_draw()
        self.show_all()

    def points_curve(self) -> None:
        """Generate PointWidgets"""
        active_idx = self.pending_active_point_idx
        if active_idx is not None:
            self.pending_active_point_idx = None
        else:
            active_idx = self.get_active_point()

        if self.points:
            for point in self.points:
                point.destroy()
        self.points.clear()
        if self.curve_nb is None or self.edit_curve is None or self.fixed is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if curve is None or not isinstance(curve, PointsCurve):
            return
        for number, point in enumerate(curve.points):
            x = point[0]
            y = point[1]
            # Warning: SizeRequest used, not real size
            width = self.edit_curve.get_size_request()[0]
            height = self.edit_curve.get_size_request()[1]
            x_wgt = (
                round((x / 255) * (width - (self.edit_curve.delta * 2)))
                + self.edit_curve.delta
            )
            y_wgt = (
                height
                - self.edit_curve.delta
                - round((y / 255) * (height - (self.edit_curve.delta * 2)))
            )
            self.points.append(
                CurvePointWidget(
                    number=number,
                    curve=curve,
                    lightshow=self.lightshow,
                    tabs=self.tabs,
                )
            )
            self.points[-1].connect("toggled", self.on_toggled, None)
            if number == active_idx:
                self.points[-1].set_active(True)
            self.fixed.put(self.points[-1], x_wgt - 4, y_wgt - 4)
        if hasattr(self, "points_table"):
            self.points_table.refresh()
            self.points_table.select_point(active_idx)
        if hasattr(self, "sampled_monitor"):
            self.sampled_monitor.queue_draw()
        self.show_all()

    def on_del_curve(self, _widget: Gtk.Widget) -> None:
        """Delete selected curve"""
        tab = typing.cast(CurvesTab, self.tabs.tabs["curves"])
        if tab.flowbox is None or self.lightshow.app is None:
            return
        selected = tab.flowbox.get_selected_children()
        if not selected:
            return
        flowboxchild = selected[0]
        curvebutton = flowboxchild.get_child()
        if not isinstance(curvebutton, CurveButton):
            return
        curve_nb = curvebutton.curve_nb
        self.lightshow.app.core.action_registry.execute("curve.delete", curve_nb)
        tab.refresh()
        tab.select_curve(0)
        self.lightshow.set_modified()

    def _update_limit_spin_config(self) -> None:
        """Update limit spinbutton range and digits based on active unit mode."""
        active_id = self.unit_combo.get_active_id()
        mode = CurveUnitMode(active_id) if active_id else CurveUnitMode.PERCENT

        curve = (
            self.lightshow.curves.get_curve(self.curve_nb)
            if self.curve_nb is not None
            else None
        )
        norm = (curve.limit / 255.0) if isinstance(curve, LimitCurve) else 1.0

        self.updating_limit_spin = True
        try:
            if mode == CurveUnitMode.PERCENT:
                self.limit_spin.set_range(0.0, 100.0)
                self.limit_spin.set_increments(1.0, 10.0)
                self.limit_spin.set_digits(1)
                self.limit_spin.set_value(round(norm * 100.0, 1))
            elif mode == CurveUnitMode.NORMALIZED:
                self.limit_spin.set_range(0.0, 1.0)
                self.limit_spin.set_increments(0.01, 0.1)
                self.limit_spin.set_digits(3)
                self.limit_spin.set_value(round(norm, 3))
            elif mode == CurveUnitMode.DMX_8BIT:
                self.limit_spin.set_range(0.0, 255.0)
                self.limit_spin.set_increments(1.0, 10.0)
                self.limit_spin.set_digits(0)
                self.limit_spin.set_value(round(norm * 255.0))
            elif mode == CurveUnitMode.DMX_16BIT:
                self.limit_spin.set_range(0.0, 65535.0)
                self.limit_spin.set_increments(256.0, 2560.0)
                self.limit_spin.set_digits(0)
                self.limit_spin.set_value(round(norm * 65535.0))
        finally:
            self.updating_limit_spin = False

    def _on_limit_spin_changed(self, spin: Gtk.SpinButton) -> None:
        """Handle user changing limit via SpinButton."""
        if getattr(self, "updating_limit_spin", False):
            return
        if self.curve_nb is None or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if not isinstance(curve, LimitCurve):
            return

        active_id = self.unit_combo.get_active_id()
        mode = CurveUnitMode(active_id) if active_id else CurveUnitMode.PERCENT
        val = spin.get_value()

        if mode == CurveUnitMode.PERCENT:
            norm = val / 100.0
        elif mode == CurveUnitMode.NORMALIZED:
            norm = val
        elif mode == CurveUnitMode.DMX_8BIT:
            norm = val / 255.0
        elif mode == CurveUnitMode.DMX_16BIT:
            norm = val / 65535.0
        else:
            norm = val / 100.0

        new_limit = max(0, min(255, int(round(norm * 255.0))))
        if new_limit != curve.limit:
            self.lightshow.app.core.action_registry.execute(
                "curve.set_limit", self.curve_nb, new_limit
            )

    def update_limit_spin_from_curve(self, limit_val: int) -> None:
        """Update spinbutton value from on-graph dragging."""
        self.updating_limit_spin = True
        try:
            active_id = self.unit_combo.get_active_id()
            mode = CurveUnitMode(active_id) if active_id else CurveUnitMode.PERCENT
            norm = limit_val / 255.0
            if mode == CurveUnitMode.PERCENT:
                self.limit_spin.set_value(round(norm * 100.0, 1))
            elif mode == CurveUnitMode.NORMALIZED:
                self.limit_spin.set_value(round(norm, 3))
            elif mode == CurveUnitMode.DMX_8BIT:
                self.limit_spin.set_value(limit_val)
            elif mode == CurveUnitMode.DMX_16BIT:
                self.limit_spin.set_value(round(norm * 65535.0))
        finally:
            self.updating_limit_spin = False

    def limit_curve_point(self) -> None:
        """Place interactive control point on LimitCurve."""
        if self.limit_point is not None:
            self.limit_point.destroy()
            self.limit_point = None
        if self.curve_nb is None or self.edit_curve is None or self.fixed is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_nb)
        if not isinstance(curve, LimitCurve):
            return

        self.limit_point = LimitPointWidget(
            curve_nb=self.curve_nb,
            curve=curve,
            lightshow=self.lightshow,
            tabs=self.tabs,
        )
        width = self.edit_curve.width
        height = self.edit_curve.height
        delta = self.edit_curve.delta
        y_wgt = height - delta - round((curve.limit / 255) * (height - 2 * delta))
        self.fixed.put(self.limit_point, width - delta - 4, y_wgt - 4)
        self.limit_point.show()

    def on_toggled(self, button: CurvePointWidget, _name: object) -> None:
        """Curve point clicked

        Args:
            button: Widget
        """
        if button.get_active():
            for toggle in self.points:
                toggle.set_active(False)
            button.set_active(False)
            if hasattr(self, "points_table"):
                self.points_table.select_point(None)
        else:
            for toggle in self.points:
                toggle.set_active(False)
            button.set_active(True)
            if hasattr(self, "points_table"):
                self.points_table.select_point(button.number)
        if hasattr(self, "sampled_monitor"):
            self.sampled_monitor.queue_draw()

    def select_point(self, index: int | None) -> None:
        """Select a point index across graph and table."""
        if self.points:
            for idx, pt in enumerate(self.points):
                pt.set_active(idx == index)
                pt.queue_draw()
        if hasattr(self, "points_table"):
            self.points_table.select_point(index)
        if hasattr(self, "sampled_monitor"):
            self.sampled_monitor.queue_draw()

    def get_active_point(self) -> Optional[int]:
        """Return index of active point

        Returns:
            Index or None if no point activated
        """
        index = None
        for idx, point in enumerate(self.points):
            if point.get_active():
                index = idx
                break
        return index


class CurveButton(CurveWidget):
    """Curve Widget"""

    def __init__(self, curve: int, lightshow: LightShow, tabs: Tabs) -> None:
        super().__init__(curve, lightshow)
        self.tabs = tabs
        self.popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry()
        entry.set_has_frame(False)
        if self.curve is not None:
            entry.set_text(_(self.curve.name))
        else:
            entry.set_text("")
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
        if self.curve is not None:
            self.curve.name = text
            tab = typing.cast(CurvesTab, self.tabs.tabs["curves"])
            tab.curve_edition.header.set_title(get_curve_display_name(self.curve))
            self.popover.popdown()
            self.lightshow.set_modified()

    def on_click(self, _button: Gtk.Widget) -> None:
        """Button clicked"""
        child = self.get_parent()
        if isinstance(child, Gtk.FlowBoxChild):
            if not child.is_selected():
                tab = typing.cast(CurvesTab, self.tabs.tabs["curves"])
                tab.select_curve(self.curve_nb)
            elif self.curve is not None and self.curve.editable:
                self.popover.popup()


class CurvesTab(Gtk.Box):
    """Tab to display and edit curves"""

    flowbox: Gtk.FlowBox | None
    paned: Gtk.Paned
    sidebar_box: Gtk.Box
    btn_toggle_sidebar: Gtk.ToggleButton

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings

        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Tab settings from workspace
        tab_settings = (
            self.lightshow.workspace.get("tab_settings", {})
            if hasattr(self.lightshow, "workspace")
            else {}
        )
        curves_settings = tab_settings.get("curves", {})
        saved_sidebar_visible = curves_settings.get("sidebar_visible", True)
        saved_paned_pos = curves_settings.get("paned_position", 220)

        # Top HeaderBar: Tab title, library toggle, and curve creation buttons
        self.top_header = Gtk.HeaderBar()
        self.top_header.set_title(_("Curves"))

        # Left of HeaderBar: Toggle library button & Curve creation buttons
        self.btn_toggle_sidebar = Gtk.ToggleButton(label=_("Library"))
        self.btn_toggle_sidebar.set_tooltip_text(_("Show or hide curves library"))
        self.btn_toggle_sidebar.set_active(saved_sidebar_visible)
        self.btn_toggle_sidebar.connect("toggled", self._on_toggle_sidebar)
        self.top_header.pack_start(self.btn_toggle_sidebar)

        self.buttons = {}
        self.buttons["limit"] = Gtk.Button(label=_("New Limit curve"))
        self.buttons["limit"].connect("clicked", self.on_new_curve)
        self.top_header.pack_start(self.buttons["limit"])

        self.buttons["segments"] = Gtk.Button(label=_("New Segments curve"))
        self.buttons["segments"].connect("clicked", self.on_new_curve)
        self.top_header.pack_start(self.buttons["segments"])

        self.buttons["interpolate"] = Gtk.Button(label=_("New Interpolate curve"))
        self.buttons["interpolate"].connect("clicked", self.on_new_curve)
        self.top_header.pack_start(self.buttons["interpolate"])

        # Backward compatibility alias
        self.header = self.top_header
        self.pack_start(self.top_header, False, False, 0)

        # Horizontal Paned: Sidebar (left) and CurveEdition (right)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_position(saved_paned_pos)

        # Left pane: Sidebar
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sidebar_box.set_size_request(190, -1)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flowbox = None
        self.populate_curves()
        self.sidebar_box.pack_start(self.scrolled, True, True, 0)
        self.sidebar_box.show_all()
        self.sidebar_box.set_no_show_all(True)
        self.sidebar_box.set_visible(saved_sidebar_visible)
        self.paned.pack1(self.sidebar_box, False, False)

        # Right pane: CurveEdition
        self.curve_edition = CurveEdition(lightshow=self.lightshow, tabs=self.tabs)
        self.paned.pack2(self.curve_edition, True, False)

        self.pack_start(self.paned, True, True, 0)

        # Select memorized curve or first curve on creation
        selected_curve = curves_settings.get("selected_curve")
        if (
            selected_curve is not None
            and selected_curve in self.lightshow.curves.curves
        ):
            self.select_curve(selected_curve)
        elif self.lightshow.curves.curves:
            first_curve_nb = next(iter(self.lightshow.curves.curves.keys()))
            self.select_curve(first_curve_nb)

    def _on_toggle_sidebar(self, button: Gtk.ToggleButton) -> None:
        """Toggle visibility of the curves library sidebar."""
        is_visible = button.get_active()
        self.sidebar_box.set_visible(is_visible)
        if hasattr(self.lightshow, "workspace"):
            tab_settings = self.lightshow.workspace.setdefault("tab_settings", {})
            tab_settings.setdefault("curves", {})["sidebar_visible"] = is_visible

    def set_sidebar_visible(self, visible: bool) -> None:
        """Set visibility of the curves library sidebar."""
        self.btn_toggle_sidebar.set_active(visible)
        self.sidebar_box.set_visible(visible)

    def is_sidebar_visible(self) -> bool:
        """Get visibility of the curves library sidebar."""
        return self.sidebar_box.get_visible()

    def set_position(self, position: int) -> None:
        """Set position of the inner paned separator."""
        self.paned.set_position(position)

    def get_position(self) -> int:
        """Get position of the inner paned separator."""
        return self.paned.get_position()

    def _memorize_selected_curve(self, curve_nb: int) -> None:
        """Store selected curve number in workspace tab settings."""
        if hasattr(self.lightshow, "workspace"):
            tab_settings = self.lightshow.workspace.setdefault("tab_settings", {})
            tab_settings.setdefault("curves", {})["selected_curve"] = curve_nb

    def select_curve(self, curve_nb: int) -> None:
        """Select a curve by number and update both curve_edition and flowbox."""
        if curve_nb not in self.lightshow.curves.curves:
            return
        self.curve_edition.change_curve(curve_nb)
        self._memorize_selected_curve(curve_nb)
        if self.flowbox is not None:
            self.flowbox.unselect_all()
            for child in self.flowbox.get_children():
                if isinstance(child, Gtk.FlowBoxChild):
                    btn = child.get_child()
                    if isinstance(btn, CurveButton) and btn.curve_nb == curve_nb:
                        self.flowbox.select_child(child)
                        break
        self.check_resize()

    def on_new_curve(self, widget: Gtk.Widget) -> None:
        """Create new curve

        Args:
            widget: button clicked
        """
        if widget is self.buttons["limit"]:
            curve_nb = typing.cast(
                int,
                self.window.app.core.action_registry.execute("curve.new", "limit"),
            )
        elif widget is self.buttons["segments"]:
            curve_nb = typing.cast(
                int,
                self.window.app.core.action_registry.execute("curve.new", "segments"),
            )
        elif widget is self.buttons["interpolate"]:
            curve_nb = typing.cast(
                int,
                self.window.app.core.action_registry.execute(
                    "curve.new", "interpolate"
                ),
            )
        else:
            return
        self.refresh()
        self.select_curve(curve_nb)

    def populate_curves(self) -> None:
        """Add curves to tab"""
        # New Flowbox
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(2)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_activate_on_single_click(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # Add curves to Flowbox
        for number in self.lightshow.curves.curves:
            self.flowbox.add(CurveButton(number, self.lightshow, self.tabs))
        self.scrolled.add(self.flowbox)
        self.flowbox.show_all()

    def refresh(self) -> None:
        """Refresh display"""
        active_nb = self.curve_edition.curve_nb
        if self.flowbox:
            self.scrolled.remove(self.flowbox)
            self.flowbox.destroy()
            self.populate_curves()
            self.flowbox.invalidate_filter()
        if active_nb is not None and active_nb in self.lightshow.curves.curves:
            self.select_curve(active_nb)

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on clicked icon"""
        self.tabs.close("curves")

    def _keypress_delete(self) -> None:
        """Delete selected point"""
        if not self.curve_edition.curve_nb or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_edition.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return
        if hasattr(self.curve_edition, "points_table"):
            self.curve_edition.points_table.delete_point()
            return
        if isinstance(curve, (SegmentsCurve, InterpolateCurve)):
            for toggle in self.curve_edition.points:
                if toggle.get_active():
                    new_points = list(curve.points)
                    del new_points[toggle.number]
                    self.lightshow.app.core.action_registry.execute(
                        "curve.update_points", self.curve_edition.curve_nb, new_points
                    )
                    self.curve_edition.points_curve()
                    self.curve_edition.queue_draw()
                    if self.tabs.tabs["dmx_outputs"]:
                        typing.cast(
                            DMXOutputsTab, self.tabs.tabs["dmx_outputs"]
                        ).refresh()
                    break

    def _keypress_page_up(self) -> None:
        """Select next point"""
        last = len(self.curve_edition.points) - 1
        if last < 0:
            return
        index = self.curve_edition.get_active_point()
        if index is None:
            self.curve_edition.select_point(0)
        elif index < last:
            self.curve_edition.select_point(index + 1)

    def _keypress_page_down(self) -> None:
        """Select previous point"""
        last = len(self.curve_edition.points) - 1
        if last < 0:
            return
        index = self.curve_edition.get_active_point()
        if index is None:
            self.curve_edition.select_point(last)
        elif index > 0:
            self.curve_edition.select_point(index - 1)

    def _keypress_left(self) -> None:
        """Move curve point left"""
        index = self.curve_edition.get_active_point()
        if self.curve_edition.curve_nb is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_edition.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return
        last = len(self.curve_edition.points) - 1
        if index is not None and index != 0 and index != last:
            x = curve.points[index][0] - 1
            if x > curve.points[index - 1][0]:
                y = curve.points[index][1]
                self.__update_point(index, x, y)

    def _keypress_right(self) -> None:
        """Move curve point right"""
        index = self.curve_edition.get_active_point()
        if self.curve_edition.curve_nb is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_edition.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return
        last = len(self.curve_edition.points) - 1
        if index is not None and index != 0 and index != last:
            x = curve.points[index][0] + 1
            if x < curve.points[index + 1][0]:
                y = curve.points[index][1]
                self.__update_point(index, x, y)

    def _keypress_up(self) -> None:
        """Move curve point up"""
        index = self.curve_edition.get_active_point()
        if self.curve_edition.curve_nb is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_edition.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return
        if index is not None and index != 0:
            x = curve.points[index][0]
            y = curve.points[index][1] + 1
            self.__update_point(index, x, y)

    def _keypress_down(self) -> None:
        """Move curve point down"""
        index = self.curve_edition.get_active_point()
        if self.curve_edition.curve_nb is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_edition.curve_nb)
        if not isinstance(curve, PointsCurve) or not curve.editable:
            return
        if index is not None and index != 0:
            x = curve.points[index][0]
            y = curve.points[index][1] - 1
            self.__update_point(index, x, y)

    def __update_point(self, index: int, x: int, y: int) -> None:
        if self.curve_edition.curve_nb is None or self.lightshow.app is None:
            return
        curve = self.lightshow.curves.get_curve(self.curve_edition.curve_nb)
        if not isinstance(curve, PointsCurve):
            return
        new_points = list(curve.points)
        new_points[index] = (x, y)
        self.lightshow.app.core.action_registry.execute(
            "curve.update_points", self.curve_edition.curve_nb, new_points
        )
        self.curve_edition.queue_draw()
        if self.curve_edition.edit_curve is None or self.curve_edition.fixed is None:
            return
        width = self.curve_edition.edit_curve.get_size_request()[0]
        height = self.curve_edition.edit_curve.get_size_request()[1]
        x_wgt = (
            round((x / 255) * (width - (self.curve_edition.edit_curve.delta * 2)))
            + self.curve_edition.edit_curve.delta
        )
        y_wgt = (
            height
            - self.curve_edition.edit_curve.delta
            - round((y / 255) * (height - (self.curve_edition.edit_curve.delta * 2)))
        )
        self.curve_edition.fixed.move(
            self.curve_edition.points[index], x_wgt - 4, y_wgt - 4
        )
        if hasattr(self.curve_edition, "points_table"):
            self.curve_edition.points_table.refresh()
            self.curve_edition.points_table.select_point(index)
        if hasattr(self.curve_edition, "sampled_monitor"):
            self.curve_edition.sampled_monitor.queue_draw()
