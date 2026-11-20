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

from gi.repository import Gtk

from olc.gtk3.dmx_outputs import DMXOutputsTab
from olc.gtk3.widgets.channel import ChannelWidget
from olc.gtk3.widgets.channels_view import ChannelsView

if typing.TYPE_CHECKING:
    from olc.gtk3.window import Window


def resolve_zoom_target(
    window: Window | None,
) -> ChannelsView | DMXOutputsTab | None:
    """Resolve the active zoomable ChannelsView or DMXOutputsTab for *window*."""
    if window is None:
        return None
    tab = window.get_active_tab()
    if tab is None and hasattr(window, "_get_active_page"):
        tab = window._get_active_page()  # pylint: disable=protected-access
    if tab is not None:
        if isinstance(tab, (ChannelsView, DMXOutputsTab)):
            return tab
        if isinstance(tab, Gtk.Container):
            for chld in tab.get_children():
                if isinstance(chld, ChannelsView):
                    return chld
    live_view = getattr(window, "live_view", None)
    if live_view is not None:
        return getattr(live_view, "channels_view", None)
    return None


def zoom(direction: str, window: Window | None) -> None:
    """Zoom in/out widgets
    FlowBox child needs a 'scale' attribute

    Args:
        direction: "in" or "out"
        window: Main application window.
    """
    view = resolve_zoom_target(window)
    if view:
        for flowboxchild in view.flowbox.get_children():
            child = typing.cast("Gtk.FlowBoxChild", flowboxchild).get_child()
            if child and isinstance(child, ChannelWidget):
                if direction == "in" and child.scale < 2.0:
                    child.set_scale(child.scale + 0.05)
                elif direction == "out" and child.scale > 0.5:
                    child.set_scale(child.scale - 0.05)
                flowboxchild.queue_draw()
