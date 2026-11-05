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
"""Real-time DMX output visualizer tab."""

from __future__ import annotations

import typing

from gi.repository import Gtk

from olc.gtk3.widgets.dmx_outputs import DMXOutputWidget

if typing.TYPE_CHECKING:
    import olc.gtk3.dmx_outputs
    from olc.core.backends import DMXBackend
    from olc.core.lightshow import LightShow
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.patch import DMXPatch


class DMXOutputsTab(Gtk.Box):
    """Tab displaying real-time DMX output levels and patch occupancy."""

    app: Application
    patch: DMXPatch
    lightshow: LightShow
    tabs: Tabs
    backend: DMXBackend
    outputs: list[DMXOutputWidget]
    flowbox: Gtk.FlowBox

    def __init__(self, app: Application) -> None:
        self.app = app
        self.patch = app.core.lightshow.patch
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.backend = (
            app.core.backend
            if app.core.backend is not None
            else typing.cast(typing.Any, None)
        )

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        # Scrolled window with outputs FlowBox
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)

        self.outputs = []
        for universe in self.patch.universes:
            for out in range(1, 513):
                output = DMXOutputWidget(
                    universe,
                    out,
                    self.app,
                    typing.cast("olc.gtk3.dmx_outputs.DMXOutputsTab", self),
                )
                self.outputs.append(output)
                self.flowbox.add(output)

        # Apply CSS style class
        for child in self.flowbox.get_children():
            child.get_style_context().add_class("olc-flowbox-output")

        scrolled.add(self.flowbox)
        self.pack_start(scrolled, True, True, 0)

        # Register callback for network DMX updates
        self.backend.dmx.add_output_callback(self.on_network_dmx_changed)

    def refresh(self) -> None:
        """Refresh display."""
        self.flowbox.queue_draw()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked."""
        self.tabs.close("dmx_outputs")

    def select_outputs(self) -> None:
        """Compatibility no-op for passive visualizer."""

    def cleanup(self) -> None:
        """Remove network DMX callbacks on tab destruction."""
        self.backend.dmx.remove_output_callback(self.on_network_dmx_changed)

    def rebuild_outputs_ui(self) -> None:
        """Rebuild the output widgets in flowbox for all active universes."""
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)
        self.outputs = []
        for universe in self.patch.universes:
            for out in range(1, 513):
                output = DMXOutputWidget(
                    universe,
                    out,
                    self.app,
                    typing.cast("olc.gtk3.dmx_outputs.DMXOutputsTab", self),
                )
                self.outputs.append(output)
                self.flowbox.add(output)

        for child in self.flowbox.get_children():
            child.get_style_context().add_class("olc-flowbox-output")
        self.flowbox.show_all()

    def add_universe_ui(self, _universe: int) -> None:
        """Add outputs for newly added universe."""
        self.rebuild_outputs_ui()

    def remove_universe_ui(self, _universe: int) -> None:
        """Remove outputs for removed universe."""
        self.rebuild_outputs_ui()

    def on_network_dmx_changed(self, universe: int, outputs: list[int]) -> None:
        """Called when a network backend updates DMX levels.

        Args:
            universe: Universe number
            outputs: List of changed output indices
        """
        if universe not in self.patch.universes:
            return
        idx = self.patch.universes.index(universe)
        for output in outputs:
            if self.patch.get_address_occupant(universe, output + 1) is not None:
                output_idx = output + (idx * 512)
                if output_idx < len(self.outputs):
                    self.outputs[output_idx].queue_draw()
