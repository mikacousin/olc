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
from olc.define import App
from olc.patch_outputs import PatchOutputsTab
from olc.widgets.channels_view import ChannelsView


def zoom(direction: str) -> None:
    """Zoom in/out widgets
    FlowBox child needs a 'scale' attribute

    Args:
        direction: "in" or "out"
    """
    tab = App().window.get_active_tab()
    children = tab.get_children()

    view = None
    if isinstance(tab, (ChannelsView, PatchOutputsTab)):
        view = tab
    else:
        for child in children:
            if isinstance(child, ChannelsView):
                view = child
    if view:
        for flowboxchild in view.flowbox.get_children():
            child = flowboxchild.get_child()
            if direction == "in" and child.scale < 2:
                child.scale += 0.01
            elif direction == "out" and child.scale > 1.01:
                child.scale -= 0.01
            flowboxchild.queue_draw()
