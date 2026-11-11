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

import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from olc.gtk3.widgets.common import (
    create_pango_layout_for_widget,
    create_system_font_description,
    register_system_font_listener,
    rounded_rectangle_fill,
)

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window


class GroupWidget(Gtk.Widget):
    """Group widget"""

    __gtype_name__ = "GroupWidget"

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        number: float,
        name: str,
        *,
        lightshow: LightShow | None = None,
        tabs: Tabs | None = None,
        window: Window | None = None,
    ) -> None:
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.number = number
        self.name = name

        Gtk.Widget.__init__(self)
        self.set_size_request(80, 80)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)
        register_system_font_listener(self.queue_draw)

        self.popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry()
        entry.set_has_frame(False)
        entry.set_text(name)
        entry.connect("activate", self.on_edit)
        vbox.pack_start(entry, False, True, 10)
        vbox.show_all()
        self.popover.add(vbox)
        self.popover.set_relative_to(self)
        self.popover.set_position(Gtk.PositionType.BOTTOM)

    def on_edit(self, widget: Gtk.Entry) -> None:
        """Edit Group text

        Args:
            widget: Entry used
        """
        text = widget.get_text()
        flowboxchild = typing.cast(Gtk.FlowBoxChild, self.get_parent())
        index = flowboxchild.get_index()
        if self.lightshow is not None and self.window is not None:
            group = self.lightshow.groups[index]
            self.window.app.core.action_registry.execute(
                "group.rename", group.index, text
            )
        self.popover.popdown()

    def on_click(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Group clicked"""
        child = typing.cast(Gtk.FlowBoxChild, self.get_parent())
        if not child.is_selected():
            if self.tabs is not None:
                groups_tab = typing.cast(typing.Any, self.tabs.tabs["groups"])
                groups_tab.flowbox.unselect_all()
                groups_tab.flowbox.select_child(child)
                groups_tab.last_group_selected = str(child.get_index())
                groups_tab.channels_view.update()
        else:
            self.popover.popup()

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Group widget

        Args:
            cr: Cairo context
        """
        allocation = self.get_allocation()

        # paint background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

        # draw rectangle
        parent = self.get_parent()
        if parent is not None and getattr(parent, "is_selected", lambda: False)():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        area = (0, allocation.width, 0, allocation.height)
        rounded_rectangle_fill(cr, area, 10)

        # draw group number
        cr.set_source_rgb(0.5, 0.5, 0.9)
        txt = str(int(self.number)) if self.number.is_integer() else str(self.number)
        num_layout = create_pango_layout_for_widget(cr, txt)
        ndesc = create_system_font_description()
        ndesc.set_weight(Pango.Weight.BOLD)
        ndesc.set_size(12 * Pango.SCALE)
        num_layout.set_font_description(ndesc)
        _nink, nlogical = num_layout.get_pixel_extents()
        cr.move_to(allocation.width - nlogical.width - 8, 4)
        PangoCairo.show_layout(cr, num_layout)

        # draw group name
        if self.name:
            cr.set_source_rgb(0.9, 0.9, 0.9)
            name_layout = create_pango_layout_for_widget(cr, self.name)
            mdesc = create_system_font_description()
            mdesc.set_weight(Pango.Weight.NORMAL)
            mdesc.set_size(10 * Pango.SCALE)
            name_layout.set_font_description(mdesc)
            name_layout.set_width(int((allocation.width - 16) * Pango.SCALE))
            name_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            name_layout.set_height(-3)
            name_layout.set_ellipsize(Pango.EllipsizeMode.END)
            cr.move_to(8, 20)
            PangoCairo.show_layout(cr, name_layout)
        return False

    def do_realize(self) -> None:
        """Realize widget"""
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = (
            self.get_events()
            | Gdk.EventMask.EXPOSURE_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.TOUCH_MASK
        )
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
