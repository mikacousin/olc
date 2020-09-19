"""Zoom function"""

from gi.repository import Gtk, Gdk


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
                for child in flowboxchild.get_children():
                    if child.scale < 2:
                        child.scale += 0.01
        if scroll and direction == Gdk.ScrollDirection.DOWN:
            for flowboxchild in widget.get_children():
                for child in flowboxchild.get_children():
                    if child.scale >= 1.01:
                        child.scale -= 0.01
        widget.queue_draw()
