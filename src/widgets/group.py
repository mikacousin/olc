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
import cairo
from gi.repository import Gdk, Gtk
from olc.define import App
from .common import rounded_rectangle_fill


class GroupWidget(Gtk.Widget):
    """Group widget"""

    __gtype_name__ = "GroupWidget"

    def __init__(self, number, name):

        self.number = number
        self.name = name

        Gtk.Widget.__init__(self)
        self.set_size_request(80, 80)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

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
        # Update widget text
        text = widget.get_text()
        self.name = text
        self.queue_draw()
        # Update group text
        flowboxchild = self.get_parent()
        index = flowboxchild.get_index()
        App().groups[index].text = text
        # Update Master text
        for master in App().masters:
            if (
                master.content_type == 13
                and master.content_value == App().groups[index].index
            ):
                master.text = text
                # Update Virtual Console
                if App().virtual_console and master.page == App().fader_page:
                    App().virtual_console.flashes[master.number - 1].label = text
                break
        self.popover.popdown()

    def on_click(self, _tgt, _ev):
        """Group clicked"""
        child = self.get_parent()
        if not child.is_selected():
            App().tabs.tabs["groups"].flowbox.unselect_all()
            App().tabs.tabs["groups"].flowbox.select_child(child)
            App().tabs.tabs["groups"].last_group_selected = str(child.get_index())
            App().tabs.tabs["groups"].channels_view.update()
        else:
            self.popover.popup()

    def do_draw(self, cr):
        """Draw Group widget

        Args:
            cr: Cairo context
        """
        allocation = self.get_allocation()

        # paint background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

        # draw rectangle
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        area = (0, allocation.width, 0, allocation.height)
        rounded_rectangle_fill(cr, area, 10)

        # draw group number
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(12)
        cr.move_to(50, 15)
        txt = str(int(self.number)) if self.number.is_integer() else str(self.number)
        cr.show_text(txt)
        # draw group name
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        cr.move_to(8, 32)
        if len(self.name) > 10:
            cr.show_text(self.name[:10])
            cr.move_to(8, 48)
            cr.show_text(self.name[10:])
        else:
            cr.show_text(self.name)

    def do_realize(self):
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
