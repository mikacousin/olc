"""Toggle button widget for Virtual Console"""

from gi.repository import Gtk
from olc.define import App
from olc.widgets import rounded_rectangle, rounded_rectangle_fill


class ToggleWidget(Gtk.ToggleButton):
    """Toggle button widget"""

    __gtype_name__ = "ToggleWidget"

    def __init__(self, text="None"):
        Gtk.ToggleButton.__init__(self)

        self.width = 50
        self.height = 50
        self.radius = 5
        self.text = text

    def do_draw(self, cr):
        """Draw Toggle button"""
        self.set_size_request(self.width, self.height)
        # Button
        area = (10, self.width - 10, 10, self.height - 10)
        if App().midi.midi_learn == self.text:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        elif self.get_active():
            cr.set_source_rgb(0.5, 0.3, 0.0)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.radius)
