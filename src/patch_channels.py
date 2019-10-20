from gi.repository import Gtk, Gio, Gdk
import cairo
import math

class PatchChannelHeader(Gtk.Widget):
    __gtype_name__ = "PatchChannelHeader"

    def __init__(self):
        Gtk.Widget.__init__(self)

        self.width = 600
        self.height = 60
        self.radius = 10
        self.channel = 'Channel'
        self.outputs = 'Outputs'

        self.set_size_request(self.width, self.height)

    def do_draw(self, cr):

        # Draw channel box
        area = (0, 60, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Channel text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(self.channel)
        cr.move_to(60/2-w/2, 60/2-(h-20)/2)
        cr.show_text(self.channel)

        # Draw outputs box
        cr.move_to(65, 0)
        area = (65, 600, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Outputs text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(self.outputs)
        cr.move_to(65+(600/2)-w/2, 60/2-(h-20)/2)
        cr.show_text(self.outputs)

        # Draw another box
        cr.move_to(605, 0)
        area = (605, 800, 0, 60)
        cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw text text
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents('Text')
        cr.move_to(605+(200/2)-w/2, 60/2-(h-20)/2)
        cr.show_text('Text')

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

class PatchChannelWidget(Gtk.Widget):
    __gtype_name__ = "PatchChannelWidget"

    def __init__(self, channel, patch):
        Gtk.Widget.__init__(self)

        self.channel = channel
        self.patch = patch
        self.width = 600
        self.height = 60
        self.radius = 10

        self.app = Gio.Application.get_default()

        self.set_size_request(self.width, self.height)
        self.connect('button-press-event', self.on_click)
        self.connect('touch-event', self.on_click)

    def on_click(self, tgt, ev):
        self.app.patch_channels_tab.flowbox.unselect_all()
        child = self.app.patch_channels_tab.flowbox.get_child_at_index(self.channel-1)
        self.app.window.set_focus(child)
        self.app.patch_channels_tab.flowbox.select_child(child)
        #self.app.patch_channels_tab.last_out_selected = str(self.channels)

    def do_draw(self, cr):
        #self.set_size_request(self.width, self.height)

        # Draw Grey background if selected
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.2, 0.2, 0.2)
            area = (0, 800, 0, 60)
            self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw channel box
        area = (0, 60, 0, 60)
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgb(0.3, 0.3, 0.3)
        self.draw_rounded_rectangle(cr, area, self.radius)

        # Draw Channel number
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        (x, y, w, h, dx, dy) = cr.text_extents(str(self.channel))
        cr.move_to(60/2-w/2, 60/2-(h-20)/2)
        cr.show_text(str(self.channel))

        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.move_to(65, 30)
        area = (65, 600, 0, 60)
        a,b,c,d = area
        cr.arc(a + self.radius, c + self.radius, self.radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - self.radius, c + self.radius, self.radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - self.radius, d - self.radius, self.radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + self.radius, d - self.radius, self.radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.stroke()

        # Draw outputs boxes
        nb_outputs = len(self.patch.channels[self.channel - 1])

        if nb_outputs <= 8:
            for i in range(len(self.patch.channels[self.channel-1])):
                output = self.patch.channels[self.channel-1][i]
                if output != 0:
                    area = (65+(i*65), 125+(i*65), 0, 60)
                    if self.get_parent().is_selected():
                        cr.set_source_rgb(0.4, 0.5, 0.4)
                    else:
                        cr.set_source_rgb(0.3, 0.4, 0.3)
                    cr.move_to(65+(i*65), 0)
                    self.draw_rounded_rectangle(cr, area, self.radius)

                    # Draw Output number
                    cr.set_source_rgb(0.9, 0.9, 0.9)
                    cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
                    cr.set_font_size(12)
                    (x, y, w, h, dx, dy) = cr.text_extents(str(output))
                    cr.move_to(65+(i*65)+(60/2)-w/2, 60/2-(h-20)/2)
                    cr.show_text(str(output))
        else:
            # If more than 8 outputs
            line = 0
            for i in range(len(self.patch.channels[self.channel-1])):
                if i > 14:
                    line = 2
                output = self.patch.channels[self.channel-1][i]
                if output != 0:
                    if line == 0:
                        # First line
                        area = (65+(i*35), 95+(i*35), 0, 30)
                        if self.get_parent().is_selected():
                            cr.set_source_rgb(0.4, 0.5, 0.4)
                        else:
                            cr.set_source_rgb(0.3, 0.4, 0.3)
                        cr.move_to(65+(i*35), 0)
                        self.draw_rounded_rectangle(cr, area, self.radius/2)

                        # Draw Output number
                        cr.set_source_rgb(0.9, 0.9, 0.9)
                        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD)
                        cr.set_font_size(12)
                        (x, y, w, h, dx, dy) = cr.text_extents(str(output))
                        cr.move_to(65+(i*35)+(30/2)-w/2, 30/2-(h-10)/2)
                        cr.show_text(str(output))
                    else:
                        # Second line
                        j = i - 15
                        area = (65+(j*35), 95+(j*35), 30, 60)
                        if self.get_parent().is_selected():
                            cr.set_source_rgb(0.4, 0.5, 0.4)
                        else:
                            cr.set_source_rgb(0.3, 0.4, 0.3)
                        cr.move_to(65+(j*35), 30)
                        self.draw_rounded_rectangle(cr, area, self.radius/2)

                        # Draw Output number
                        cr.set_source_rgb(0.9, 0.9, 0.9)
                        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD)
                        cr.set_font_size(12)
                        cr.move_to(65+(j*35)+(30/2)-w/2, (30/2-(h-10)/2)+30)
                        if i == 29:
                            # Draw '...' in the last box
                            (x, y, w, h, dx, dy) = cr.text_extents('...')
                            cr.show_text('...')
                            break
                        else:
                            (x, y, w, h, dx, dy) = cr.text_extents(str(output))
                            cr.show_text(str(output))

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

class PatchChannelsTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ''
        self.last_chan_selected = ''

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.header = PatchChannelHeader()

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for channel in range(512):
            self.channels.append(PatchChannelWidget(channel+1, self.app.patch))
            self.flowbox.add(self.channels[channel])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.attach(self.header, 0, 0, 1, 1)
        self.attach_next_to(self.scrollable, self.header, Gtk.PositionType.BOTTOM, 1, 10)

    def filter_func(self, child, user_data):
        return True

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.patch_channels_tab)
        self.app.window.notebook.remove_page(page)
        self.app.patch_channels_tab = None

    def on_key_press_event(self, widget, event):

        # TODO: Hack to know if user is editing something
        widget = self.app.window.get_focus()
        #print(widget.get_path().is_type(Gtk.Entry))
        if not widget:
            return
        if widget.get_path().is_type(Gtk.Entry):
            return

        keyname = Gdk.keyval_name(event.keyval)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'period':
            self.keystring += '.'
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.patch_channels_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Down(self):
        """ Select Next Channel """

        if self.last_chan_selected == '':
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = '0'
        elif int(self.last_chan_selected) < 511:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) + 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) + 1)

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Up(self):
        """ Select Previous Channel """
        if self.last_chan_selected == '':
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = '0'
        elif int(self.last_chan_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) - 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) - 1)

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Select Channel """
        self.flowbox.unselect_all()

        if self.keystring != '':
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < 512:
                child = self.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_m(self):
        """ Modify Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1

                # Unpatch if no entry
                if self.keystring == '' or self.keystring == '0':
                    outputs = self.app.patch.channels[channel]
                    for i in range(len(outputs)):
                        output = self.app.patch.channels[channel][i] - 1
                        self.app.patch.outputs[output] = 0
                    self.app.patch.channels[channel] = [0]
                    # Update ui
                    self.channels[channel].queue_draw()
                else:
                    # New values
                    output = int(self.keystring) - 1

                    if output >= 0 and output < 512:
                        # Unpatch old values
                        outputs = self.app.patch.channels[channel]
                        for i in range(len(outputs)):
                            out = self.app.patch.channels[channel][i] - 1
                            self.app.patch.outputs[out] = 0
                        old_channel = self.app.patch.outputs[output]
                        if old_channel:
                            self.app.patch.outputs[channel] = 0
                            self.app.patch.channels[old_channel - 1].remove(output + 1)
                        # Patch
                        self.app.patch.channels[channel] = [output + 1]
                        self.app.patch.outputs[output] = channel + 1
                        # Update ui
                        self.channels[old_channel-1].queue_draw()
                        self.channels[channel].queue_draw()

                # Update list of channels
                level = self.app.dmx.frame[output]
                self.app.window.channels[channel].level = level
                self.app.window.channels[channel].queue_draw()
                self.app.window.flowbox.invalidate_filter()

        # Select next channel
        if channel < 511:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(channel+1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(channel+1)

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_i(self):
        """ Insert Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1

                if self.keystring != '' or self.keystring != '0':
                    # New values
                    output = int(self.keystring) - 1

                    if output >= 0 and output < 512:
                        # Unpatch old value
                        old_channel = self.app.patch.outputs[output]
                        if old_channel:
                            self.app.patch.channels[old_channel - 1].remove(output + 1)
                        # Patch
                        self.app.patch.add_output(channel + 1, output + 1)
                        # Update ui
                        self.channels[old_channel-1].queue_draw()
                        self.channels[channel].queue_draw()

                        # Update list of channels
                        level = self.app.dmx.frame[self.app.patch.channels[channel][0]]
                        self.app.window.channels[channel].level = level
                        self.app.window.channels[channel].queue_draw()
                        self.app.window.flowbox.invalidate_filter()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_r(self):
        """ Remove Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1

                if self.keystring != '' or self.keystring != '0':
                    output = int(self.keystring) - 1

                    if output >= 0 and output < 512:
                        # Verify Output is patched to the Channel
                        if output+1 in self.app.patch.channels[channel]:
                            # Remove Output
                            self.app.patch.channels[channel].remove(output + 1)
                            self.app.patch.outputs[output] = 0
                            # Update ui
                            self.channels[channel].queue_draw()

                # Update list of channels
                self.app.window.channels[channel].queue_draw()
                self.app.window.flowbox.invalidate_filter()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
