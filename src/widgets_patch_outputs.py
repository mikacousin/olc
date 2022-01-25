"""Patch Output Widget"""

import cairo
from gi.repository import Gdk, Gtk
from olc.define import App
from olc.widgets import rounded_rectangle_fill


class PatchWidget(Gtk.Widget):
    """Patch output widget"""

    __gtype_name__ = "PatchWidget"

    def __init__(self, universe, output):

        self.universe = universe
        self.output = output

        Gtk.Widget.__init__(self)
        self.scale = 1.0
        self.width = 50 * self.scale
        self.set_size_request(self.width, self.width)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, _tgt, event):
        """Widget clicked

        Args:
            event: Gdk.Event
        """
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            # Thru
            App().patch_outputs_tab.keystring = str(self.output)
            App().patch_outputs_tab.thru()
        elif event.state & accel_mask == Gdk.ModifierType.CONTROL_MASK:
            # Toggle selected status
            child = App().patch_outputs_tab.flowbox.get_child_at_index(
                self.output - 1 + (512 * self.universe)
            )
            App().window.set_focus(child)
            if self.get_parent().is_selected():
                App().patch_outputs_tab.flowbox.unselect_child(child)
            else:
                App().patch_outputs_tab.flowbox.select_child(child)
            App().patch_outputs_tab.last_out_selected = str(self.output - 1)
        else:
            # Deselect selected widgets
            App().window.channels_view.flowbox.unselect_all()
            App().patch_outputs_tab.flowbox.unselect_all()
            # Select clicked widget
            child = App().patch_outputs_tab.flowbox.get_child_at_index(
                self.output - 1 + (512 * self.universe)
            )
            App().window.set_focus(child)
            App().patch_outputs_tab.flowbox.select_child(child)
            App().patch_outputs_tab.last_out_selected = str(self.output - 1)

    def do_draw(self, cr):
        """Draw widget

        Args:
            cr: Cairo context
        """
        self.width = 50 * self.scale
        self.set_size_request(self.width, self.width)
        allocation = self.get_allocation()
        # Draw background
        self._draw_background(cr, allocation)
        # Draw output number
        self._draw_output_number(cr, allocation)
        # Draw channel number
        self._draw_channel_number(cr, allocation)
        # Draw Output level
        self._draw_output_level(cr, allocation)
        # Draw Proportional Level
        self._draw_proportional_level(cr, allocation)

    def _draw_background(self, cr, allocation):
        """Draw background

        Args:
            cr: Cairo context
            allocation: Widget's allocation
        """
        area = (1, allocation.width - 2, 1, allocation.height - 2)
        # Dimmer
        if (
            App().patch.outputs[self.universe][self.output - 1][1] == 0
            and App().patch.outputs[self.universe][self.output - 1][0] != 0
        ):
            # Level's output at 0
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.8, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.1, 0.1)
            rounded_rectangle_fill(cr, area, 10)
        elif App().patch.outputs[self.universe][self.output - 1][0] != 0:
            # Patch output
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)
            rounded_rectangle_fill(cr, area, 10)
        elif self.get_parent().is_selected():
            # Unpatched output
            cr.set_source_rgb(0.6, 0.4, 0.1)
            rounded_rectangle_fill(cr, area, 10)

    def _draw_output_number(self, cr, allocation):
        """Draw Output number

        Args:
            cr: Cairo context
            allocation: Widget alocation
        """
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(11 * self.scale)
        text = str(self.output) + "." + str(self.universe)
        (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
        cr.move_to(
            allocation.width / 2 - width / 2, allocation.height / 4 - (height - 20) / 4
        )
        cr.show_text(text)

    def _draw_channel_number(self, cr, allocation):
        """Draw Channel number

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(11 * self.scale)
        # Dimmer
        text = str(App().patch.outputs[self.universe][self.output - 1][0])
        (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
        if App().patch.outputs[self.universe][self.output - 1][0] > 0:
            cr.move_to(
                allocation.width / 2 - width / 2,
                3 * (allocation.height / 4 - (height - 20) / 4),
            )
            cr.show_text(text)

    def _draw_output_level(self, cr, allocation):
        """Draw Output level

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        if App().dmx.frame[self.universe][self.output - 1]:
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(10 * self.scale)
            text = str(App().dmx.frame[self.universe][self.output - 1])
            (_x, _y, width, height, _dx, _dy) = cr.text_extents(text)
            cr.move_to(
                allocation.width / 2 - width / 2,
                allocation.height / 2 - (height - 20) / 2,
            )
            cr.show_text(text)

    def _draw_proportional_level(self, cr, allocation):
        """Draw Proportional Level

        Args:
            cr: Cairo context
            allocation: Widget allocation
        """
        if (
            App().patch.outputs[self.universe][self.output - 1][1] == 100
            or App().patch.outputs[self.universe][self.output - 1][0] == 0
        ):
            return

        cr.rectangle(
            allocation.width - 9,
            allocation.height - 2,
            6 * self.scale,
            -((50 / 100) * self.scale)
            * App().patch.outputs[self.universe][self.output - 1][1],
        )
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.8, 0.1, 0.1)
        else:
            cr.set_source_rgb(0.5, 0.1, 0.1)
        cr.fill()
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.set_font_size(8 * self.scale)
        text = str(App().patch.outputs[self.universe][self.output - 1][1]) + "%"
        cr.move_to(allocation.width - 20, allocation.height - 2)
        cr.show_text(text)

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
