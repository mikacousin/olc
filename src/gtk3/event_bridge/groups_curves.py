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
"""GUI event bridge handler for groups, curves, and independents."""

from __future__ import annotations

import typing

from gi.repository import Gtk

from olc.curve import LimitCurve, PointsCurve
from olc.fader import FaderType
from olc.gtk3.fader import FaderTab
from olc.gtk3.widgets.curve import get_curve_display_name
from olc.independent import IndependentType

from .base import BaseEventBridgeHandler

if typing.TYPE_CHECKING:
    from olc.group import Group
    from olc.gtk3.curve import CurvesTab
    from olc.gtk3.group import GroupTab
    from olc.gtk3.widgets.group import GroupWidget


# pylint: disable=too-few-public-methods
class GroupCurveBridgeHandler(BaseEventBridgeHandler):
    """Handles groups, curves, and independent channels events."""

    def register(self) -> None:
        """Subscribe to Core events for groups, curves, and independents."""
        self.app.core.subscribe(
            "group.created", lambda _: self._run_idle(self._safe_refresh_groups)
        )
        self.app.core.subscribe(
            "group.updated", lambda g: self._run_idle(self._on_group_updated, g)
        )
        self.app.core.subscribe(
            "group.deleted", lambda g: self._run_idle(self._on_group_deleted, g)
        )
        self.app.core.subscribe(
            "group_editor.changed",
            lambda index: self._run_idle(self._safe_refresh_group_editor, index),
        )
        self.app.core.subscribe(
            "group.selected_changed",
            lambda group_nb: self._run_idle(self._on_group_selected_changed, group_nb),
        )
        self.app.core.subscribe(
            "curve.changed",
            lambda curve_nb: self._run_idle(self._safe_refresh_curves, curve_nb),
        )
        self.app.core.subscribe(
            "independent.level_changed",
            lambda number, level: self._run_idle(
                self._on_independent_level_changed, number, level
            ),
        )
        self.app.core.subscribe(
            "independent.channels_changed",
            lambda number: self._run_idle(
                self._on_independent_channels_changed, number
            ),
        )
        self.app.core.subscribe(
            "independent.text_changed",
            lambda number, text: self._run_idle(
                self._on_independent_text_changed, number, text
            ),
        )
        self.app.core.subscribe(
            "independent.type_changed",
            lambda number, inde_type: self._run_idle(
                self._on_independent_type_changed, number, inde_type
            ),
        )

    def _safe_refresh_groups(self) -> bool:
        """Refresh the groups tab UI safely in the GTK thread.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        if self.app.tabs and self.app.tabs.tabs.get("groups") is not None:
            group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
            group_tab.refresh()
        return False

    def _on_group_updated(self, group: Group) -> bool:
        """Update group UI, fader text, virtual console, and midi LCD on group update.

        Args:
            group: Group instance updated.

        Returns:
            Always False.
        """
        self._safe_refresh_groups()

        # Update fader text, virtual console and MIDI LCD if needed
        text = group.text
        fader_bank = self.app.core.lightshow.fader_bank
        for page, faders in fader_bank.faders.items():
            for fader in faders.values():
                if fader.contents is group:
                    fader.text = text
                    # Update Virtual Console
                    if self.app.virtual_console and page == fader_bank.active_page:
                        self.app.virtual_console.flashes[fader.index - 1].label = text
        if self.app.midi:
            self.app.midi.messages.lcd.show_faders()

        # Update the widgets in the GroupTab if we renamed
        if self.app.tabs and self.app.tabs.tabs.get("groups") is not None:
            group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
            for child in group_tab.flowbox.get_children():
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                group_widget = fb_child.get_child()
                # Use duck typing or getattr to read number/name safely
                if (
                    group_widget
                    and getattr(group_widget, "number", None) == group.index
                ):
                    typing.cast("GroupWidget", group_widget).name = text
                    group_widget.queue_draw()
        return False

    def _safe_refresh_group_editor(self, index: float) -> bool:
        """Refresh the channel view in groups tab when temporary overrides change.

        Args:
            index: Group index.

        Returns:
            Always False.
        """
        if self.app.tabs:
            if self.app.tabs.tabs.get("groups") is not None:
                group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
                if getattr(group_tab, "selected_group_number", None) == index:
                    group_tab.channels_view.update()
        return False

    def _on_group_selected_changed(self, group_nb: float | None) -> bool:
        """Synchronize the logical group selection to the GUI.

        Args:
            group_nb: Group number or None.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("groups") is not None:
            group_tab = typing.cast("GroupTab", self.app.tabs.tabs["groups"])
            group_tab.select_group_graphically(group_nb)
        return False

    def _safe_refresh_curves(self, curve_nb: int) -> bool:
        """Refresh curves tab UI safely in the GTK thread.

        Args:
            curve_nb: The active curve number.

        Returns:
            Always False.
        """
        if not self.app.tabs:
            return False
        curves_tab_obj = self.app.tabs.tabs.get("curves")
        if curves_tab_obj is None:
            return False

        curves_tab = typing.cast("CurvesTab", curves_tab_obj)
        is_active_curve = curves_tab.curve_edition.curve_nb == curve_nb
        curves_count = len(curves_tab.lightshow.curves.curves)
        flowbox_count = 0
        if curves_tab.flowbox is not None:
            flowbox_count = len(
                [
                    c
                    for c in curves_tab.flowbox.get_children()
                    if isinstance(c, Gtk.FlowBoxChild)
                ]
            )

        if is_active_curve and curves_count == flowbox_count:
            self._fast_refresh_active_curve(curves_tab, curve_nb)
        else:
            self._slow_refresh_curves(curves_tab, curve_nb)
        return False

    def _fast_refresh_active_curve(self, curves_tab: CurvesTab, curve_nb: int) -> None:
        """Perform a fast local UI update on the currently active curve."""
        curve = curves_tab.lightshow.curves.get_curve(curve_nb)
        if curve is None:
            return

        # Update title
        curves_tab.curve_edition.header.set_title(get_curve_display_name(curve))

        # Update scale slider value (safely using updating flag to avoid loops)
        if (
            isinstance(curve, LimitCurve)
            and curves_tab.curve_edition.scale_widget is not None
        ):
            curves_tab.curve_edition.updating_slider = True
            try:
                curves_tab.curve_edition.scale_widget.set_value(curve.limit)
            finally:
                curves_tab.curve_edition.updating_slider = False

        # Update points if it's a PointsCurve
        if isinstance(curve, PointsCurve):
            curves_tab.curve_edition.points_curve()

        # Redraw Cairo widgets
        curves_tab.curve_edition.values.queue_draw()
        if curves_tab.curve_edition.edit_curve is not None:
            curves_tab.curve_edition.edit_curve.queue_draw()

        # Redraw the button preview in the curves list
        if curves_tab.flowbox is not None:
            for child in curves_tab.flowbox.get_children():
                if not isinstance(child, Gtk.FlowBoxChild):
                    continue
                child_btn = child.get_child()
                if child_btn and getattr(child_btn, "curve_nb", None) == curve_nb:
                    child_btn.queue_draw()
                    break

    def _slow_refresh_curves(self, curves_tab: CurvesTab, curve_nb: int) -> None:
        """Perform a full rebuild of the curves tab UI."""
        curves_tab.refresh()
        curves_tab.curve_edition.change_curve(curve_nb)
        if curves_tab.flowbox is not None:
            for child in curves_tab.flowbox.get_children():
                if not isinstance(child, Gtk.FlowBoxChild):
                    continue
                child_btn = child.get_child()
                if child_btn and getattr(child_btn, "curve_nb", None) == curve_nb:
                    curves_tab.flowbox.select_child(child)
                    break

    def _on_group_deleted(self, group: Group) -> bool:
        """Clean up faders referencing the deleted group and refresh UI.

        Args:
            group: The deleted group instance.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        fader_bank = self.app.core.lightshow.fader_bank
        faders_updated = False
        for page, faders in fader_bank.faders.items():
            for fader in faders.values():
                if fader.contents is group:
                    fader_bank.set_fader(page, fader.index, FaderType.NONE, None)
                    faders_updated = True

        self._safe_refresh_groups()
        if (
            faders_updated
            and self.app.tabs
            and self.app.tabs.tabs.get("faders") is not None
        ):
            fader_tab = typing.cast(FaderTab, self.app.tabs.tabs["faders"])
            fader_tab.refresh()
        return False

    def _on_independent_level_changed(self, number: int, level: float) -> bool:
        """Synchronize independent level changes to GUI and MIDI.

        Args:
            number: Independent number (1-based).
            level: Level in [0.0, 1.0].

        Returns:
            Always False.
        """
        if self.app.virtual_console:
            self.app.virtual_console.update_independent_display(number, level)
        if self.app.midi is not None:
            if number <= 6:
                midi_fader = self.app.midi.faders.inde_faders[number - 1]
                midi_fader.set_state(round(level * 255))
                self.app.midi.messages.control_change.send(
                    f"inde_led_{number}", 32 + int(level * 12)
                )
            else:
                velocity = 0 if level < 0.5 else 127
                self.app.midi.messages.notes.send(f"inde_{number}", velocity)
        return False

    def _on_independent_channels_changed(self, _number: int) -> bool:
        """Refresh independent edit tab on channels configuration changes.

        Args:
            _number: Independent number.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("indes") is not None:
            indes_tab = typing.cast(typing.Any, self.app.tabs.tabs["indes"])
            indes_tab.channels_view.flowbox.queue_draw()
            indes_tab.channels_view.update()
        return False

    def _on_independent_text_changed(self, _number: int, _text: str) -> bool:
        """Refresh independent edit tab treeview on label changes.

        Args:
            _number: Independent number.
            _text: New text label.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("indes") is not None:
            indes_tab = typing.cast(typing.Any, self.app.tabs.tabs["indes"])
            indes_tab.refresh()
        return False

    def _on_independent_type_changed(
        self, _number: int, _inde_type: IndependentType
    ) -> bool:
        """Refresh independent edit tab treeview and Virtual Console on type changes.

        Args:
            _number: Independent number.
            _inde_type: Independent type.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("indes") is not None:
            indes_tab = typing.cast(typing.Any, self.app.tabs.tabs["indes"])
            indes_tab.refresh()
        if self.app.virtual_console:
            self.app.virtual_console.rebuild_independent(_number)
        return False
