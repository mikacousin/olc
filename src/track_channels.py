from gi.repository import Gtk, Gio, Gdk
import cairo
import math

from olc.define import MAX_CHANNELS

class TrackChannelsHeader(Gtk.Widget):
    __gtype_name__ = 'TrackChannelsHeader'

    def __init__(self, channels):
        Gtk.Widget.__init__(self)

        self.channels = channels
        self.width = 535 + (len(channels) * 65)
        self.height = 60
        self.radius = 10

        self.app = Gio.Application.get_default()

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):

        # Draw Step box
        area = (0, 60, 0, 60)
        cr.set_source_rgb(0.2, 0.3, 0.2)
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
        cr.set_source_rgb(0.2, 0.3, 0.2)
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
        cr.set_source_rgb(0.2, 0.3, 0.2)
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
            cr.set_source_rgb(0.2, 0.3, 0.2)
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

        self.step = step
        self.memory = memory
        self.text = text
        self.levels = levels
        self.width = 535 + (len(self.levels) * 65)
        self.height = 60
        self.radius = 10

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
        self.app.track_channels_tab.last_step_selected = str(self.step)
        chan = int((ev.x - 535) / 65)
        if chan >= 0 and chan < len(self.levels):
            self.app.track_channels_tab.channel_selected = chan

    def do_draw(self, cr):

        self.set_size_request(535 + (len(self.levels) * 65), self.height)

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
            cr.set_source_rgb(0.5, 0.3, 0.0)
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
            cr.set_source_rgb(0.5, 0.3, 0.0)
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
            cr.set_source_rgb(0.5, 0.3, 0.0)
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
            if self.get_parent().is_selected() and i == self.app.track_channels_tab.channel_selected:
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)
            self.draw_rounded_rectangle(cr, area, self.radius)

            # Draw Level number
            if self.levels[i]:
                if self.percent_level:
                    level = str(int(round(((self.levels[i] / 255) * 100))))
                else:
                    level = str(self.levels[i])
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

        self.keystring = ''
        self.last_step_selected = ''

        self.channel_selected = 0

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        # Find selected channels
        self.channels = []
        sel = self.app.window.flowbox.get_selected_children()
        for flowboxchild in sel:
            children = flowboxchild.get_children()
            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                if self.app.patch.channels[channel][0] != [0, 0]:
                    self.channels.append(channel)

        # Levels in each steps
        levels = []
        self.steps = []
        self.steps.append(TrackChannelsHeader(self.channels))
        levels.append([])
        self.flowbox.add(self.steps[0])
        for step in range(1, self.app.sequence.last):
            memory = self.app.sequence.cues[step].memory
            text = self.app.sequence.cues[step].text
            levels.append([])
            for channel in range(len(self.channels)):
                level = self.app.sequence.cues[step].channels[self.channels[channel]]
                levels[step].append(level)
            self.steps.append(TrackChannelsWidget(step, memory, text, levels[step]))
            self.flowbox.add(self.steps[step])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.attach(self.scrollable, 0, 0, 1, 1)

    def filter_func(self, child, user_data):
        if child == self.steps[self.app.sequence.last-1].get_parent():
            return False
        else:
            return child

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.track_channels_tab)
        self.app.window.notebook.remove_page(page)
        self.app.track_channels_tab = None

    def on_key_press_event(self, widget, event):

        keyname = Gdk.keyval_name(event.keyval)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.track_channels_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Right(self):
        """ Next Channel """

        if self.last_step_selected == '':
            child = self.flowbox.get_child_at_index(1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = '1'
        else:
            sel = self.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for widget in children:
                    if self.channel_selected + 1 < len(widget.levels):
                        self.channel_selected += 1
                        widget.queue_draw()

    def keypress_Left(self):
        """ Previous Channel """

        if self.last_step_selected == '':
            child = self.flowbox.get_child_at_index(1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = '1'
        else:
            sel = self.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for widget in children:
                    if self.channel_selected > 0:
                        self.channel_selected -= 1
                        widget.queue_draw()

    def keypress_Down(self):
        """ Next Step """

        if self.last_step_selected == '':
            child = self.flowbox.get_child_at_index(1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = '1'
        elif int(self.last_step_selected) < self.app.sequence.last - 2:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) + 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            index = child.get_index()
            self.last_step_selected = str(index)

    def keypress_Up(self):
        """ Previous Step """

        if self.last_step_selected == '':
            child = self.flowbox.get_child_at_index(1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = '1'
        elif int(self.last_step_selected) > 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) - 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            index = child.get_index()
            self.last_step_selected = str(index)

    def keypress_m(self):
        """ Modify Level """

        # Find selected Channel
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            children = flowboxchild.get_children()
            for widget in children:
                step = widget.step
                channel = self.channels[self.channel_selected]
                level = int(self.keystring)

                if self.app.settings.get_boolean('percent'):
                    if level >= 0 and level <= 100:
                        level = int(round((level / 100) * 255))
                    else:
                        level = -1

                if level >= 0 and level <= 255:
                    self.app.sequence.cues[step].channels[channel] = level
                    widget.levels[self.channel_selected] = level
                    widget.queue_draw()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Select Channel """

        self.app.window.flowbox.unselect_all()

        if self.keystring != '' and self.keystring != '0':
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < MAX_CHANNELS:
                child = self.app.window.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.app.window.flowbox.select_child(child)
                self.app.window.last_chan_selected = str(channel)

        # Find selected channels
        self.channels = []
        sel = self.app.window.flowbox.get_selected_children()
        for flowboxchild in sel:
            children = flowboxchild.get_children()
            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                if self.app.patch.channels[channel][0] != [0, 0]:
                    self.channels.append(channel)

        self.channel_selected = 0

        # Update Track Channels Tab
        self.steps[0].channels = self.channels

        levels = []
        for step in range(self.app.sequence.last):
            levels.append([])
            for channel in range(len(self.channels)):
                level = self.app.sequence.cues[step].channels[self.channels[channel]]
                levels[step].append(level)
            self.steps[step].levels = levels[step]
        self.flowbox.queue_draw()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        sel = self.app.window.flowbox.get_selected_children()

        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.app.window.last_chan_selected = channelwidget.channel

        if not self.app.window.last_chan_selected:
            sel = self.app.window.flowbox.get_selected_children()
            if len(sel):
                for flowboxchild in sel:
                    children = flowboxchild.get_children()
                    for channelwidget in children:
                        channel = int(channelwidget.channel)
                self.app.window.last_chan_selected = str(channel)

        if self.app.window.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(self.app.window.last_chan_selected):
                for channel in range(int(self.app.window.last_chan_selected) - 1, to_chan):
                    child = self.app.window.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.app.window.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(self.app.window.last_chan_selected)):
                    child = self.app.window.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.app.window.flowbox.select_child(child)

            self.app.window.last_chan_selected = self.keystring

            # Find selected channels
            self.channels = []
            sel = self.app.window.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    if self.app.patch.channels[channel][0] != [0, 0]:
                        self.channels.append(channel)

            if self.channel_selected > len(self.channels) - 1:
                self.channel_selected = 0

            # Update Track Channels Tab
            self.steps[0].channels = self.channels

            levels = []
            for step in range(self.app.sequence.last):
                levels.append([])
                for channel in range(len(self.channels)):
                    level = self.app.sequence.cues[step].channels[self.channels[channel]]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Add(self):
        self.keypress_plus()

    def keypress_plus(self):
        """ Channel + """

        if self.keystring == '':
            return

        channel = int(self.keystring) - 1
        if channel >= 0 and channel < MAX_CHANNELS:
            child = self.app.window.flowbox.get_child_at_index(channel)
            self.app.window.set_focus(child)
            self.app.window.flowbox.select_child(child)
            self.app.window.last_chan_selected = self.keystring

            # Find selected channels
            self.channels = []
            sel = self.app.window.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    if self.app.patch.channels[channel][0] != [0, 0]:
                        self.channels.append(channel)

            if self.channel_selected > len(self.channels) - 1:
                self.channel_selected = 0

            # Update Track Channels Tab
            self.steps[0].channels = self.channels

            levels = []
            for step in range(self.app.sequence.last):
                levels.append([])
                for channel in range(len(self.channels)):
                    level = self.app.sequence.cues[step].channels[self.channels[channel]]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Subtract(self):
        self.keypress_minus()

    def keypress_minus(self):
        """ Channel - """

        if self.keystring == '':
            return

        channel = int(self.keystring) - 1
        if channel >= 0 and channel < MAX_CHANNELS:
            child = self.app.window.flowbox.get_child_at_index(channel)
            self.app.window.set_focus(child)
            self.app.window.flowbox.unselect_child(child)
            self.app.window.last_chan_selected = self.keystring

            # Find selected channels
            self.channels = []
            sel = self.app.window.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    if self.app.patch.channels[channel][0] != [0, 0]:
                        self.channels.append(channel)

            if self.channel_selected > len(self.channels) - 1:
                self.channel_selected = 0

            # Update Track Channels Tab
            self.steps[0].channels = self.channels

            levels = []
            for step in range(self.app.sequence.last):
                levels.append([])
                for channel in range(len(self.channels)):
                    level = self.app.sequence.cues[step].channels[self.channels[channel]]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
