from gi.repository import Gtk, Gdk, Gio
import cairo
import math

from olc.settings import Settings

class ChannelWidget(Gtk.Widget):
    __gtype_name__ = 'ChannelWidget'

    def __init__(self, channel, level, next_level):
        Gtk.Widget.__init__(self)

        self.channel = str(channel)
        self.level = level
        self.next_level = next_level
        self.clicked = False
        self.color_level_red = 0.9
        self.color_level_green = 0.9
        self.color_level_blue = 0.9

        self.app = Gio.Application.get_default()

        self.percent_level = self.app.settings.get_boolean('percent')

        self.connect("button-press-event", self.on_click)
        self.set_size_request(80, 80)

    def on_click(self, tgt, ev):
        # Select clicked widget
        flowboxchild = tgt.get_parent()
        flowbox = flowboxchild.get_parent()

        flowbox.unselect_all()

        self.app.window.set_focus(flowboxchild)
        flowbox.select_child(flowboxchild)
        self.app.window.last_chan_selected = str(int(self.channel) - 1)

    def do_draw(self, cr):

        self.percent_level = Gio.Application.get_default().settings.get_boolean('percent')

        allocation = self.get_allocation()

        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)

        # paint background
        if self.get_parent().is_selected():
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgba(*list(bg_color))
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()

        # draw rectangle
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()
        # draw background
        bg = Gdk.RGBA()
        # TODO: Get background color
        bg.parse('#33393B')
        cr.set_source_rgba(*list(bg))
        cr.rectangle(4, 4, allocation.width-8, 72)
        cr.fill()
        # draw background of channel number
        flowboxchild = self.get_parent()
        if flowboxchild.is_selected():
            cr.set_source_rgb(0.4, 0.4, 0.4)
            cr.rectangle(4, 4, allocation.width-8, 18)
            cr.fill()
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
            cr.rectangle(4, 4, allocation.width-8, 18)
            cr.fill()
        # draw channel number
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.move_to(50,15)
        cr.show_text(self.channel)
        # draw level
        cr.set_source_rgb(self.color_level_red, self.color_level_green, self.color_level_blue)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.move_to(6,48)
        if self.level != 0 or self.next_level != 0:     # Don't show 0 level
            if self.percent_level:
                cr.show_text(str(int(round((self.level/255)*100))))    # Level in %
            else:
                cr.show_text(str(self.level))                  # Level in 0 to 255 value
        # draw level bar
        cr.rectangle(allocation.width-9, allocation.height-2, 6, -(50/255)*self.level)
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()
        # draw down icon
        if self.next_level < self.level:
            offset_x = 6
            offset_y = -6
            cr.move_to(offset_x + 11, offset_y + allocation.height-6)
            cr.line_to(offset_x + 6, offset_y + allocation.height-16)
            cr.line_to(offset_x + 16, offset_y + allocation.height-16)
            cr.close_path()
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.fill()
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            cr.move_to(offset_x + 24, offset_y + allocation.height-6)
            if self.percent_level:
                cr.show_text(str(int(round((self.next_level/255)*100))))   # Level in %
            else:
                cr.show_text(str(self.next_level))                 # Level in 0 to 255 value
        # draw up icon
        if self.next_level > self.level:
            offset_x = 6
            offset_y = 15
            cr.move_to(offset_x + 11, offset_y + 6)
            cr.line_to(offset_x + 6, offset_y + 16)
            cr.line_to(offset_x + 16, offset_y + 16)
            cr.close_path()
            cr.set_source_rgb(0.9, 0.5, 0.5)
            cr.fill()
            #cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            cr.move_to(offset_x + 24, offset_y + 16)
            if self.percent_level:
                cr.show_text(str(int(round((self.next_level/255)*100))))   # Level in %
            else:
                cr.show_text(str(self.next_level))                 # Level in 0 to 255 value

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

class PatchWidget(Gtk.Widget):
    __gtype_name__ = "PatchWidget"

    def __init__(self, universe, output, patch):

        self.type = "Output"
        self.universe = universe
        self.output = output
        self.patch = patch

        self.app = Gio.Application.get_default()

        Gtk.Widget.__init__(self)
        self.scale = 1.2
        self.width = 60 * self.scale
        self.set_size_request(self.width,self.width)
        self.connect('button-press-event', self.on_click)
        self.connect('touch-event', self.on_click)

    def on_click(self, tgt, ev):
        # Deselect selected widgets
        self.app.window.flowbox.unselect_all()
        self.app.patch_outputs_tab.flowbox.unselect_all()
        # Select clicked widget
        child = self.app.patch_outputs_tab.flowbox.get_child_at_index(self.output-1)
        self.app.window.set_focus(child)
        self.app.patch_outputs_tab.flowbox.select_child(child)
        self.app.patch_outputs_tab.last_out_selected = str(self.output)

    def do_draw(self, cr):
        self.width = 60 * self.scale
        self.set_size_request(self.width,self.width)
        # paint background
        area = (0, self.width, 0, self.width)

        if self.patch.outputs[self.universe][self.output-1] != 0:
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)

            self.draw_rounded_rectangle(cr, area, 10)
        else:
            if self.get_parent().is_selected():
                cr.set_source_rgb(0.6, 0.4, 0.1)
                self.draw_rounded_rectangle(cr, area, 10)

        # draw output number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12*self.scale)
        text = str(self.output)+'.'+str(self.universe)
        (x, y, width, height, dx, dy) = cr.text_extents(text)
        cr.move_to(self.width/2-width/2,self.width/4-(height-20)/4)
        cr.show_text(text)

        if self.patch.outputs[self.universe][self.output-1] != 0:
            # draw channel number
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12*self.scale)
            text = str(self.patch.outputs[self.universe][self.output-1])
            (x, y, width, height, dx, dy) = cr.text_extents(text)
            cr.move_to(self.width/2-width/2,3*(self.width/4-(height-20)/4))
            cr.show_text(text)

        # Draw Output level
        if self.app.dmx.frame[self.universe][self.output-1]:
            cr.set_source_rgb(0.7, 0.7, 0.7)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12*self.scale)
            text = str(self.app.dmx.frame[self.universe][self.output-1])
            (x, y, width, height, dx, dy) = cr.text_extents(text)
            cr.move_to(self.width/2-width/2,self.width/2-(height-20)/2)
            cr.show_text(text)

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

    def draw_rounded_rectangle(self, cr, area, radius):
        a,b,c,d = area
        cr.arc(a + radius, c + radius, radius, 2*(math.pi/2), 3*(math.pi/2))
        cr.arc(b - radius, c + radius, radius, 3*(math.pi/2), 4*(math.pi/2))
        cr.arc(b - radius, d - radius, radius, 0*(math.pi/2), 1*(math.pi/2))
        cr.arc(a + radius, d - radius, radius, 1*(math.pi/2), 2*(math.pi/2))
        cr.close_path()
        cr.fill()

class GroupWidget(Gtk.Widget):
    __gtype_name__ = 'GroupWidget'

    def __init__(self, index, number, name, grps):

        self.index = index
        self.number = number
        self.name = name
        self.grps = grps

        self.app = Gio.Application.get_default()

        Gtk.Widget.__init__(self)
        self.set_size_request(80, 80)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)

    def on_click(self, tgt, ev):
        self.app.group_tab.flowbox2.unselect_all()
        child = self.app.group_tab.flowbox2.get_child_at_index(self.index)
        self.app.window.set_focus(child)
        self.app.group_tab.flowbox2.select_child(child)
        self.app.group_tab.last_group_selected = str(self.index)
        self.app.group_tab.flowbox1.invalidate_filter()

    def do_draw(self, cr):

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
        self.draw_rounded_rectangle(cr, area, 10)

        # draw group number
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.move_to(50,15)
        if self.number.is_integer():
            txt = str(int(self.number))
        else:
            txt = str(self.number)
        cr.show_text(txt)
        # draw group name
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_NORMAL)
        cr.move_to(8, 32)
        if len(self.name) > 10:
            cr.show_text(self.name[:10])
            cr.move_to(8, 48)
            cr.show_text(self.name[10:])
        else:
            cr.show_text(self.name)

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

class SequentialWidget(Gtk.Widget):
    __gtype_name__ = 'SequentialWidget'

    def __init__(self, total_time, time_in, time_out, delay_in, delay_out, wait, channel_time):

        self.total_time = total_time
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        self.channel_time = channel_time

        self.pos_xA = 0
        self.pos_xB = 0

        Gtk.Widget.__init__(self)
        self.set_size_request(800, 300)

    def do_draw(self, cr):
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            self.time_max = self.time_in + self.delay_in
            self.time_min = self.time_out + self.delay_out
        else:
            self.time_max = self.time_out + self.delay_out
            self.time_min = self.time_in + self.delay_in

        # Add Wait Time
        self.time_max = self.time_max + self.wait
        self.time_min = self.time_min + self.wait

        # paint background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(bg_color))
        cr.paint()

        allocation = self.get_allocation()

        # dessine un cadre
        if self.pos_xA or self.pos_xB:  # Red filter in fades
            cr.set_source_rgba(1, 0, 0, 0.1)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.stroke()

        # draw time line
        fg_color = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(*list(fg_color));
        cr.set_line_width(1)
        cr.move_to(16, 24)
        cr.line_to(allocation.width-16, 24)
        cr.line_to(allocation.width-16, 18)
        cr.move_to(16, 24)
        cr.line_to(16, 18)
        #inter = (allocation.width-32)/self.time_max
        inter = (allocation.width - 32) / self.total_time
        for i in range(int(self.total_time-1)):
            cr.move_to(16+(inter*(i+1)), 24)
            cr.line_to(16+(inter*(i+1)), 18)
        cr.stroke()

        # Draw Wait if any
        if self.wait > 0:
            # Draw a grey box
            cr.set_source_rgb(0.2, 0.2, 0.2)
            if self.pos_xA or self.pos_xB:  # Red filter in fades
                cr.set_source_rgba(1, 0, 0, 0.1)
            cr.set_line_width(1)
            cr.rectangle(16, 40, (inter*self.wait), allocation.height-70-(len(self.channel_time)*8))
            cr.fill()
            # Draw Wait lines
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.set_line_width(3)
            cr.move_to(16, 40)
            cr.line_to(16+(inter*self.wait), 40)
            cr.stroke()
            cr.set_source_rgb(0.9, 0.5, 0.5)
            cr.set_line_width(3)
            cr.move_to(16, allocation.height-32-(len(self.channel_time)*8))
            cr.line_to(16+(inter*self.wait), allocation.height-32-(len(self.channel_time)*8))
            cr.stroke()
            wait_x = inter * self.wait
            # Draw Wait time on the time line
            cr.move_to(12+(inter*self.wait),16)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            if self.wait.is_integer():              # If time is integer don't show the ".0"
                cr.show_text(str(int(self.wait)))
            else:
                cr.show_text(str(self.wait))
        else:
            wait_x = 0

        # Draw Delay Out
        if self.delay_out:
            cr.set_source_rgb(0.5, 0.5, 0.9)
            cr.set_line_width(3)
            cr.move_to(16+wait_x, 40)
            cr.line_to(16+wait_x+(inter*self.delay_out), 40)
            cr.stroke()
            # Draw Delay Out on the time line
            cr.move_to(12+wait_x+(inter*self.delay_out),16)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            if self.delay_out.is_integer():              # If time is integer don't show the ".0"
                cr.show_text(str(int(self.delay_out+self.wait)))
            else:
                cr.show_text(str(self.delay_out+self.wait))

        # Draw Delay In
        if self.delay_in:
            cr.set_source_rgb(0.9, 0.5, 0.5)
            cr.set_line_width(3)
            cr.move_to(16+wait_x, allocation.height-32-(len(self.channel_time)*8))
            cr.line_to(16+wait_x+(inter*self.delay_in), allocation.height-32-(len(self.channel_time)*8))
            cr.stroke()
            # Draw Delay In on the time line
            cr.move_to(12+wait_x+(inter*self.delay_in),16)
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            if self.delay_in.is_integer():              # If time is integer don't show the ".0"
                cr.show_text(str(int(self.delay_in+self.wait)))
            else:
                cr.show_text(str(self.delay_in+self.wait))

        # Draw Channel Time if any
        self.ct_nb = 0

        # Change height to draw channel time
        self.set_size_request(800, 300 + (len(self.channel_time) * 8))

        for channel in self.channel_time.keys():
            delay = self.channel_time[channel].delay
            time = self.channel_time[channel].time
            # draw Channel number
            cr.move_to((inter*delay)+wait_x,allocation.height-4-(self.ct_nb*12))
            #cr.move_to((inter*delay)+wait_x,allocation.height-28-(self.ct_nb*12))
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10)
            cr.show_text(str(channel))
            # draw Channel Time line
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.set_line_width(1)
            cr.move_to(16+(inter*delay)+wait_x, allocation.height-8-(self.ct_nb*12))
            cr.line_to(16+(inter*delay)+(inter*time)+wait_x, allocation.height-8-(self.ct_nb*12))
            cr.stroke()
            cr.set_dash([8.0, 6.0])
            cr.move_to(16+(inter*delay)+wait_x, 24)
            cr.line_to(16+(inter*delay)+wait_x, allocation.height)
            cr.move_to(16+(inter*delay)+(inter*time)+wait_x, 24)
            cr.line_to(16+(inter*delay)+(inter*time)+wait_x, allocation.height)
            cr.stroke()
            cr.set_dash([])
            # draw Time Cursor
            app = Gio.Application.get_default()
            position = app.sequence.position
            old_level = app.sequence.cues[position].channels[channel - 1]
            next_level = app.sequence.cues[position + 1].channels[channel - 1]
            # Time Cursor follow In or Out Crossfade
            if next_level < old_level:
                # Out Crossfade
                if self.pos_xA > inter*delay + wait_x:
                    if self.pos_xA > (inter*delay)+(inter*time)+wait_x:
                        self.pos_xCT = (inter * delay) + (inter * time) + wait_x
                    else:
                        self.pos_xCT = self.pos_xA
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(16+self.pos_xCT, allocation.height-12-(self.ct_nb*12))
                    cr.line_to(16+self.pos_xCT, allocation.height-4-(self.ct_nb*12))
                    cr.stroke()
                else:
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(16+(inter*delay)+wait_x, allocation.height-12-(self.ct_nb*12))
                    cr.line_to(16+(inter*delay)+wait_x, allocation.height-4-(self.ct_nb*12))
                    cr.stroke()
            else:
                # In Crossfade
                if self.pos_xB > inter*delay + wait_x:
                    if self.pos_xB > (inter*delay)+(inter*time)+wait_x:
                        self.pos_xCT = (inter * delay) + (inter * time) + wait_x
                    else:
                        self.pos_xCT = self.pos_xB
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(16+self.pos_xCT, allocation.height-12-(self.ct_nb*12))
                    cr.line_to(16+self.pos_xCT, allocation.height-4-(self.ct_nb*12))
                    cr.stroke()
                else:
                    cr.set_source_rgb(0.9, 0.6, 0.2)
                    cr.move_to(16+(inter*delay)+wait_x, allocation.height-12-(self.ct_nb*12))
                    cr.line_to(16+(inter*delay)+wait_x, allocation.height-4-(self.ct_nb*12))
                    cr.stroke()
            # draw time number
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.move_to(12+(inter*delay)+(inter*time)+wait_x,16)
            t = delay + time + self.wait
            if t != self.total_time:
                if t.is_integer():              # If time is integer don't show the ".0"
                    cr.show_text(str(int(t)))
                else:
                    cr.show_text(str(t))
            # draw delay number if any
            if delay:
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.move_to(12+(inter*delay)+wait_x,16)
                t = delay + self.wait
                if t.is_integer():              # If time is integer don't show the ".0"
                    cr.show_text(str(int(t)))
                else:
                    cr.show_text(str(t))
            self.ct_nb += 1

        # draw Out line
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.set_line_width(3)
        cr.move_to(16+wait_x+(inter*self.delay_out), 40)
        cr.line_to(16+wait_x+(inter*self.delay_out)+(inter*self.time_out), allocation.height-32-(len(self.channel_time)*8))
        cr.stroke()
        cr.move_to(16+wait_x+(inter*self.delay_out)+(inter*self.time_out), 24)
        cr.line_to(16+wait_x+(inter*self.delay_out)+(inter*self.time_out), allocation.height)
        cr.set_dash([8.0, 6.0])
        cr.stroke()
        cr.set_dash([])
        # draw an arrow at the end
        arrow_lenght = 12
        arrow_degrees = 10
        start_x = wait_x + (inter*self.delay_out) + 16
        start_y = 40
        end_x = 16+wait_x+(inter*self.delay_out)+(inter*self.time_out)
        end_y = allocation.height-32-(len(self.channel_time)*8)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        x1 = end_x + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = end_y + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = end_x + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = end_y + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()
        # draw X1 cursor
        if (not wait_x or self.pos_xA > wait_x) and (not self.delay_out or self.pos_xA > (inter*self.delay_out)+wait_x):
            x1 = start_x + self.pos_xA - wait_x - (inter*self.delay_out)
            y1 = start_y + ((self.pos_xA - wait_x - (inter*self.delay_out)) * math.tan(angle))
            if x1 > end_x:
                x1 = end_x
                y1 = end_y
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.arc(x1, y1, 8, 0, 2*math.pi)
            cr.fill()
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10)
            cr.move_to(x1 - 5, y1 + 2)
            cr.show_text("A")
        else:
            x1 = start_x + self.pos_xA - wait_x - (inter*self.delay_out)
            y1 = start_y
            if x1 > end_x:
                x1 = end_x
                y1 = end_y
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.arc(x1, y1, 8, 0, 2*math.pi)
            cr.fill()
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10)
            cr.move_to(x1 - 5, y1 + 2)
            cr.show_text("A")

        # draw In line
        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.move_to(16+wait_x+(inter*self.delay_in), allocation.height-32-(len(self.channel_time)*8))
        cr.line_to(16+wait_x+(inter*self.delay_in)+(inter*self.time_in), 40)
        cr.stroke()
        cr.move_to(16+wait_x+(inter*self.delay_in)+(inter*self.time_in), 24)
        cr.line_to(16+wait_x+(inter*self.delay_in)+(inter*self.time_in), allocation.height)
        cr.set_dash([8.0, 6.0])
        cr.stroke()
        cr.set_dash([])
        # draw an arrow at the end
        arrow_lenght = 12
        arrow_degrees = 10
        start_x = wait_x + 16 + (inter*self.delay_in)
        start_y = allocation.height-32-(len(self.channel_time)*8)
        end_x = 16+wait_x+(inter*self.delay_in)+(inter*self.time_in)
        end_y = 40
        angle = math.atan2(end_y - start_y, end_x - start_x)
        x1 = end_x + arrow_lenght * math.cos(angle - arrow_degrees)
        y1 = end_y + arrow_lenght * math.sin(angle - arrow_degrees)
        x2 = end_x + arrow_lenght * math.cos(angle + arrow_degrees)
        y2 = end_y + arrow_lenght * math.sin(angle + arrow_degrees)
        cr.move_to(end_x, end_y)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.fill()
        # draw X2 cursor
        if (not wait_x or self.pos_xB > wait_x) and (not self.delay_in or self.pos_xB > ((inter*self.delay_in)+wait_x)):
            x1 = start_x + self.pos_xB - wait_x - (inter*self.delay_in)
            y1 = start_y + ((self.pos_xB - wait_x - (inter*self.delay_in)) * math.tan(angle))
            if x1 > end_x:
                x1 = end_x
                y1 = end_y
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.arc(x1, y1, 8, 0, 2*math.pi)
            cr.fill()
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10)
            cr.move_to(x1 - 5, y1 + 3)
            cr.show_text("B")
        else:  # Wait and Delay In
            x1 = start_x + self.pos_xB - wait_x - (inter*self.delay_in)
            y1 = start_y
            if x1 > end_x:
                x1 = end_x
                y1 = end_y
            cr.set_source_rgb(0.9, 0.6, 0.2)
            cr.arc(x1, y1, 8, 0, 2*math.pi)
            cr.fill()
            cr.set_source_rgb(0.9, 0.9, 0.9)
            cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10)
            cr.move_to(x1 - 5, y1 + 2)
            cr.show_text("B")

        # draw times number
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Monaco", cairo.FONT_SLANT_NORMAL, 
            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.move_to(12,16)
        cr.show_text("0")
        cr.move_to(allocation.width-24,16)
        # Draw Total Time at the end
        if self.time_max.is_integer():              # If time is integer don't show the ".0"
            cr.show_text(str(int(self.total_time)))
        else:
            cr.show_text(str(self.total_time))
        if self.time_max != self.total_time:
            cr.move_to(12+(inter*self.time_max),16)
            if self.time_max.is_integer():
                cr.show_text(str(int(self.time_max)))
            else:
                cr.show_text(str(self.time_max))
        if self.time_min != self.time_max:
            cr.move_to(12+(inter*self.time_min),16)
            if self.time_min.is_integer():
                cr.show_text(str(int(self.time_min)))
            else:
                cr.show_text(str(self.time_min))

    def do_realize(self):
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
        WAT = Gdk.WindowAttributesType
        mask = WAT.X | WAT.Y | WAT.VISUAL
        window = Gdk.Window(self.get_parent_window(), attr, mask);
        self.set_window(window)
        self.register_window(window)
        self.set_realized(True)
        window.set_background_pattern(None)

