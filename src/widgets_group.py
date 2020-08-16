"""Group widget"""

import cairo
from gi.repository import Gdk, Gtk
from olc.define import App
from olc.widgets import rounded_rectangle_fill


class GroupWidget(Gtk.Widget):
    """Group widget"""

    __gtype_name__ = "GroupWidget"

    def __init__(self, index, number, name, grps):

        self.index = index
        self.number = number
        self.name = name
        self.grps = grps

        Gtk.Widget.__init__(self)
        self.set_size_request(80, 80)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, _tgt, _ev):
        """Group clicked"""
        App().group_tab.flowbox2.unselect_all()
        child = App().group_tab.flowbox2.get_child_at_index(self.index)
        App().window.set_focus(child)
        App().group_tab.flowbox2.select_child(child)
        App().group_tab.last_group_selected = str(self.index)
        App().group_tab.flowbox1.invalidate_filter()

    def do_draw(self, cr):
        """Draw Group widget"""
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
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
