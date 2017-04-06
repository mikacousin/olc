from gi.repository import Gio, Gtk, Gdk
import cairo

class MidiTab(Gtk.Grid):

    def __init__(self):

        self.app = Gio.Application.get_default()

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.surface = UC33Widget()
        self.attach(self.surface, 0, 0, 1, 1)

        """
        self.background = Gtk.Image.new_from_file('/usr/local/share/open-lighting-console/uc33.png')

        self.knob = []
        for i in range(24):
            self.knob.append(KnobWidget())

        self.attach(self.background, 0, 0, 10, 5)
        self.attach(self.knob[0], 0, 0, 1, 1)
        self.attach_next_to(self.knob[8], self.knob[0], Gtk.PositionType.BOTTOM, 1, 1)
        self.attach_next_to(self.knob[16], self.knob[8], Gtk.PositionType.BOTTOM, 1, 1)
        for i in range(7):
            self.attach_next_to(self.knob[i + 1], self.knob[i], Gtk.PositionType.RIGHT, 1, 1)
            self.attach_next_to(self.knob[i + 9], self.knob[i + 8], Gtk.PositionType.RIGHT, 1, 1)
            self.attach_next_to(self.knob[i + 17], self.knob[i + 16], Gtk.PositionType.RIGHT, 1, 1)
        """

    def on_close_icon(self, Widget):
        """ Close Tab on close click """
        page = self.app.window.notebook.page_num(self.app.midi_tab)
        self.app.window.notebook.remove_page(page)
        self.app.midi_tab = None

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print(keyname)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.midi_tab = None

class KnobWidget(Gtk.Widget):
    __gtype_name__ = 'KnobWidget'

    def __init__(self):

        Gtk.Widget.__init__(self)

        self.app = Gio.Application.get_default()

    def do_draw(self, cr):

        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/knob.png')
        cr.set_source_surface(ims, 0, 0)
        cr.paint()

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.TOUCH_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)

class UC33Widget(Gtk.Widget):
    __gtype_name__ = 'UC33Widget'

    def __init__(self):

        Gtk.Widget.__init__(self)

        self.app = Gio.Application.get_default()

        self.selected = None

        self.widgets = []
        self.widgets.append([53, 93, 30, 30, "Knob"]) # x, y, width, height, type
        self.widgets.append([108, 93, 30, 30, "Knob"])
        self.widgets.append([163, 93, 30, 30, "Knob"])
        self.widgets.append([218, 93, 30, 30, "Knob"])
        self.widgets.append([273, 93, 30, 30, "Knob"])
        self.widgets.append([328, 93, 30, 30, "Knob"])
        self.widgets.append([383, 93, 30, 30, "Knob"])
        self.widgets.append([438, 93, 30, 30, "Knob"])
        self.widgets.append([53, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([108, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([163, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([218, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([273, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([328, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([383, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([438, 93 + 55, 30, 30, "Knob"])
        self.widgets.append([53, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([108, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([163, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([218, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([273, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([328, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([383, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([438, 93 + (2 * 55), 30, 30, "Knob"])
        self.widgets.append([55, 250, 28, 180, "SliderTrack"])
        self.widgets.append([110, 250, 28, 180, "SliderTrack"])
        self.widgets.append([165, 250, 28, 180, "SliderTrack"])
        self.widgets.append([220, 250, 28, 180, "SliderTrack"])
        self.widgets.append([275, 250, 28, 180, "SliderTrack"])
        self.widgets.append([330, 250, 28, 180, "SliderTrack"])
        self.widgets.append([385, 250, 28, 180, "SliderTrack"])
        self.widgets.append([440, 250, 28, 180, "SliderTrack"])
        self.widgets.append([495, 250, 28, 180, "SliderTrack"])
        self.widgets.append([55, 360, 28, 180, "Slider"])
        self.widgets.append([110, 360, 28, 180, "Slider"])
        self.widgets.append([165, 360, 28, 180, "Slider"])
        self.widgets.append([220, 360, 28, 180, "Slider"])
        self.widgets.append([275, 360, 28, 180, "Slider"])
        self.widgets.append([330, 360, 28, 180, "Slider"])
        self.widgets.append([385, 360, 28, 180, "Slider"])
        self.widgets.append([440, 360, 28, 180, "Slider"])
        self.widgets.append([495, 360, 28, 180, "Slider"])
        self.widgets.append([584, 279, 26, 21, "Button"])
        self.widgets.append([584 + 34, 279, 26, 21, "Button"])
        self.widgets.append([584 + (2 * 34), 279, 26, 21, "Button"])
        self.widgets.append([584, 279 + 26, 26, 21, "Button"])
        self.widgets.append([584 + 34, 279 + 26, 26, 21, "Button"])
        self.widgets.append([584 + (2 * 34), 279 + 26, 26, 21, "Button"])
        self.widgets.append([584, 279 + (2 *26), 26, 21, "Button"])
        self.widgets.append([584 + 34, 279 + (2 * 26), 26, 21, "Button"])
        self.widgets.append([584 + (2 * 34), 279 + (2 * 26), 26, 21, "Button"])

        self.widgets.append([584 + 34, 278 + (3 * 27), 26, 21, "Button"])

        self.widgets.append([568, 279 + (3 *26) + 39, 26, 21, "Button"])
        self.widgets.append([568 + 32, 279 + (3 *26) + 39, 26, 21, "Button"])
        self.widgets.append([568 + (2 * 32), 279 + (3 *26) + 39, 26, 21, "Button"])
        self.widgets.append([568 + (3 * 32), 279 + (3 *26) + 39, 26, 21, "Button"])

        self.knobs = []
        for i in range(24):
            self.knobs.append(0)

        self.connect('button-press-event', self.on_click)

    def on_click(self, tgt, ev):

        for widget in self.widgets:
            if ev.x > widget[0] and ev.x < widget[0] + widget[2] and ev.y > widget[1] and ev.y < widget[1] + widget[3]:
                self.selected = widget
                self.queue_draw()

        # TODO: Popover
        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        for group in self.app.groups:
            #print(group.index, group.text)
            label = Gtk.Label(group.text)
            grid.add(label)
        rec = Gdk.Rectangle()
        rec.x = self.selected[0]
        rec.y = self.selected[1]
        rec.width = self.selected[2]
        rec.height = self.selected[3]
        popover = Gtk.Popover.new(self)
        popover.set_pointing_to(rec)
        #popover.set_position(Gtk.PositionType.BOTTOM)
        popover.add(grid)
        popover.show_all()

    def do_draw(self, cr):

        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        allocation = self.get_allocation()

        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/uc33.png')
        cr.set_source_surface(ims, 10, 10)
        cr.paint()

        for widget in self.widgets:
            if widget[4] == 'Knob':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/knob.png')
            elif widget[4] == 'SliderTrack':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/slider_track.png')
            elif widget[4] == 'Slider':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/slider.png')
            elif widget[4] == 'Button':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/button.png')
            cr.set_source_surface(ims, widget[0], widget[1])
            cr.paint()

        if self.selected != None:
            if self.selected[4] == 'Knob':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/knob_selected.png')
                cr.set_source_surface(ims, self.selected[0], self.selected[1])
                cr.paint()
            elif self.selected[4] == 'SliderTrack':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/slider_track_selected.png')
                cr.set_source_surface(ims, self.selected[0], self.selected[1])
                cr.paint()
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/slider_selected.png')
                cr.set_source_surface(ims, self.selected[0], self.selected[1] + 110)
                cr.paint()
            elif self.selected[4] == 'Slider':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/slider_track_selected.png')
                cr.set_source_surface(ims, self.selected[0], self.selected[1] - 110)
                cr.paint()
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/slider_selected.png')
                cr.set_source_surface(ims, self.selected[0], self.selected[1])
                cr.paint()
            elif self.selected[4] == 'Button':
                ims = cairo.ImageSurface.create_from_png('/usr/local/share/open-lighting-console/button_selected.png')
                cr.set_source_surface(ims, self.selected[0], self.selected[1])
                cr.paint()

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.TOUCH_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)
