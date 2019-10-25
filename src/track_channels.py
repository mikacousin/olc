from gi.repository import Gtk, Gio, Gdk
import cairo
import math

class TrackChannelsHeader(Gtk.Widget):
    __gtype_name__ = 'TrackChannelsHeader'

    def __init__(self, channels):
        Gtk.Widget.__init__(self)

        self.width = 600
        self.height = 60
        self.radius = 10
        self.channels = channels

        self.app = Gio.Application.get_default()

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):

        # Draw Step box
        area = (0, 60, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Step text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str('Step'))
        cr.move_to(60/2-w/2, 60/2-(h-20)/2)
        cr.show_text(str('Step'))

        # Draw Memory box
        cr.move_to(65, 0)
        area = (65, 125, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Memory text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str('Memory'))
        cr.move_to(65+(60/2-w/2), 60/2-(h-20)/2)
        cr.show_text(str('Memory'))

        # Draw Text box
        cr.move_to(130, 0)
        area = (130, 530, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str('Text'))
        cr.move_to(135, 60/2-(h-20)/2)
        cr.show_text(str('Text'))

        for i in range(len(self.channels)):
            # Draw Level boxes
            cr.move_to(535+(i*65), 0)
            area = (535+(i*65), 595+(i*65), 0, 60)
            cr.set_source_rgb(0.3, 0.3, 0.3)
            self.draw_rounded_rectangle(cr, area, self.radius)

            # Draw Channel number
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                    cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            (x, y, w, h, dx, dy) = cr.text_extents(str(self.channels[i] + 1))
            cr.move_to(535+(i*65)+(60/2-w/2), 60/2-(h-20)/2)
            cr.show_text(str(self.channels[i] + 1))

    def draw_rounded_rectangle(self, cr, area, radius):
        a,b,c,d = area
        cr.arc(a + radius, c + radius, radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - radius, c + radius, radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - radius, d - radius, radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + radius, d - radius, radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.fill()

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

class TrackChannelsWidget(Gtk.Widget):
    __gtype_name__ = 'TrackChannelsWidget'

    def __init__(self, step, memory, text, levels):
        Gtk.Widget.__init__(self)

        self.width = 600
        self.height = 60
        self.radius = 10
        self.step = step
        self.memory = memory
        self.text = text
        self.levels = levels

        self.app = Gio.Application.get_default()

        self.percent_level = self.app.settings.get_boolean('percent')

        self.set_size_request(self.width, self.height)
        self.connect('button-press-event', self.on_click)
        self.connect('touch-event', self.on_click)

    def on_click(self, tgt, ev):
        self.app.track_channels_tab.flowbox.unselect_all()
        child = self.app.track_channels_tab.flowbox.get_child_at_index(self.step)
        self.app.window.set_focus(child)
        self.app.track_channels_tab.flowbox.select_child(child)

    def do_draw(self, cr):

        """
        # Draw Grey background if selected
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.2, 0.2, 0.2)
            area = (0, 800, 0, 60)
            self.draw_rounded_rectangle(cr, area, self.radius)
        """

        # Draw Step box
        area = (0, 60, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Step number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.step))
        cr.move_to(60/2-w/2, 60/2-(h-20)/2)
        cr.show_text(str(self.step))

        # Draw Memory box
        cr.move_to(65, 0)
        area = (65, 125, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Memory number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.memory))
        cr.move_to(65+(60/2-w/2), 60/2-(h-20)/2)
        cr.show_text(str(self.memory))

        # Draw Text box
        cr.move_to(130, 0)
        area = (130, 530, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.text))
        cr.move_to(135, 60/2-(h-20)/2)
        cr.show_text(str(self.text))

        for i in range(len(self.levels)):
            # Draw Level boxes
            cr.move_to(535+(i*65), 0)
            area = (535+(i*65), 595+(i*65), 0, 60)
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)
            self.draw_rounded_rectangle(cr, area, self.radius)

            # Draw Level number
            if self.percent_level:
                level = str(int(round(((self.levels[i] / 255) * 100))))
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                    cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            (x, y, w, h, dx, dy) = cr.text_extents(level)
            cr.move_to(535+(i*65)+(60/2-w/2), 60/2-(h-20)/2)
            cr.show_text(level)

    def draw_rounded_rectangle(self, cr, area, radius):
        a,b,c,d = area
        cr.arc(a + radius, c + radius, radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - radius, c + radius, radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - radius, d - radius, radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + radius, d - radius, radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.fill()

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

class TrackChannelsTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.percent_level = self.app.settings.get_boolean('percent')

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        # Find selected channels
        channels = []
        sel = self.app.window.flowbox.get_selected_children()
        for flowboxchild in sel:
            children = flowboxchild.get_children()
            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                if self.app.patch.channels[channel][0] != [0, 0]:
                    channels.append(channel)

        # Levels in each steps
        levels = []
        self.steps = []
        for step in range(self.app.sequence.last):
            memory = self.app.sequence.cues[step].memory
            text = self.app.sequence.cues[step].text
            levels.append([])
            for channel in range(len(channels)):
                level = self.app.sequence.cues[step].channels[channels[channel]]
                levels[step].append(level)
            self.steps.append(TrackChannelsWidget(step, memory, text, levels[step]))
            self.flowbox.add(self.steps[step])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.header = TrackChannelsHeader(channels)

        self.attach(self.header, 0, 0, 1, 1)
        self.attach_next_to(self.scrollable, self.header, Gtk.PositionType.BOTTOM, 1, 10)

    def filter_func(self, child, user_data):
        return child

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.track_channels_tab)
        self.app.window.notebook.remove_page(page)
        self.app.track_channels_tab = None
