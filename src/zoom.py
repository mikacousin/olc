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
import typing

from olc.patch_outputs import PatchOutputsTab
from olc.widgets.channel import ChannelWidget
from olc.widgets.channels_view import ChannelsView

if typing.TYPE_CHECKING:
    from gi.repository import Gtk
    from olc.window import Window


def zoom(direction: str, window: Window) -> None:
    """Zoom in/out widgets
    FlowBox child needs a 'scale' attribute

    Args:
        direction: "in" or "out"
    """
    tab = window.get_active_tab()
    children = tab.get_children()

    view = None
    if isinstance(tab, (ChannelsView, PatchOutputsTab)):
        view = tab
    else:
        for chld in children:
            if isinstance(chld, ChannelsView):
                view = chld
    if view:
        for flowboxchild in view.flowbox.get_children():
            child = typing.cast("Gtk.FlowBoxChild", flowboxchild).get_child()
            if child and isinstance(child, ChannelWidget):
                if direction == "in" and child.scale < 2:
                    child.scale += 0.01
                elif direction == "out" and child.scale >= 1:
                    child.scale -= 0.01
                flowboxchild.queue_draw()
