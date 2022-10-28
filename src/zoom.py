# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from gi.repository import Gdk, Gtk


def zoom(widget, event):
    """Zoom in/out widgets

    Args:
        widget: Gtk.FlowBox
        event: Gdk.Event

    FlowBox child needs a 'scale' attribute
    """
    accel_mask = Gtk.accelerator_get_default_mod_mask()
    # Need Control + Shift + Mouse scroll
    if (
        event.state & accel_mask
        == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
    ):
        (scroll, direction) = event.get_scroll_direction()
        if scroll and direction == Gdk.ScrollDirection.UP:
            for flowboxchild in widget.get_children():
                child = flowboxchild.get_child()
                if child.scale < 2:
                    child.scale += 0.01
        if scroll and direction == Gdk.ScrollDirection.DOWN:
            for flowboxchild in widget.get_children():
                child = flowboxchild.get_child()
                if child.scale >= 1.01:
                    child.scale -= 0.01
        widget.queue_draw()
