import select
import time
import threading
import mido
from gi.repository import Gio, Gtk, GObject, Gdk, GLib
from ola import OlaClient

from olc.customwidgets import ChanelWidget

class Window(Gtk.ApplicationWindow):

    def __init__(self, app, patch):

        self.app = app
        self.patch = patch

        # 0 : patched channels
        # 1 : all channels
        self.view_type = 0

        self.percent_level = Gio.Application.get_default().settings.get_boolean('percent')

        Gtk.Window.__init__(self, title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1200)

        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("Fonctionne avec ola")
        self.header.props.show_close_button = True

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        #Gtk.StyleContext.add_class(box.get_style_context(), "linked")
        button = Gtk.Button()
        icon = Gio.ThemedIcon(name="view-grid-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.connect("clicked", self.button_clicked_cb)
        button.add(image)
        box.add(button)
        button = Gtk.Button()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)
        box.add(button)
        self.header.pack_end(box)

        self.set_titlebar(self.header)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(950)
        #self.paned.set_wide_handle(True)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_filter_func(self.filter_func, None) # Fonction de filtrage

        self.keystring = ""
        self.last_chan_selected = ""

        #self.grid = []
        self.channels = []
        #self.levels = []
        #self.progressbar = []

        for i in range(512):
            self.channels.append(ChanelWidget(i+1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)
        self.paned.add1(self.scrolled)

        # TODO: Try to use Gtk.Statusbar to display keyboard's keys

        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("keypress")
        #self.statusbar.push(self.context_id, "Test")

        self.grid = Gtk.Grid()
        label = Gtk.Label("Saisie clavier : ")
        self.grid.add(label)
        #self.label = Gtk.Label("")
        #self.grid.attach_next_to(self.label, label, Gtk.PositionType.RIGHT, 1, 1)
        self.grid.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)
        self.paned.add2(self.grid)

        self.add(self.paned)

        # Open MIDI input port
        try:
            self.inport = mido.open_input('UC-33 USB MIDI Controller MIDI ')
        except:
            self.inport = mido.open_input()

        self.timeout_id = GObject.timeout_add(50, self.on_timeout, None)

        self.connect('key_press_event', self.on_key_press_event)

    def filter_func(self, child, user_data):
        if self.view_type == 0:
            i = child.get_index()
            for j in range(len(self.patch.channels[i])):
                #print("Chanel:", i+1, "Output:", self.patch.channels[i][j])
                if self.patch.channels[i][j] != 0:
                    return child
                else:
                    return False
        else:
            return True

    def on_button_toggled(self, button, name):
        if button.get_active():
            state = "on"
        else:
            state = "off"

    def on_timeout(self, user_data):
        # Scan MIDI messages
        for msg in self.inport.iter_pending():
            #print(msg)
            if msg.type == 'note_on' and msg.note == 11 and msg.velocity == 127:
                self.keypress_space()
            if msg.type == 'note_on' and msg.note == 12 and msg.velocity == 127:
                self.keypress_Up()
            if msg.type == 'note_on' and msg.note == 13 and msg.velocity == 127:
                self.keypress_Down()
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 1:
                if self.percent_level:
                    self.app.win_masters.scale[0].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[0].set_value((msg.value/127)*256)
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 2:
                if self.percent_level:
                    self.app.win_masters.scale[1].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[1].set_value((msg.value/127)*256)
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 3:
                if self.percent_level:
                    self.app.win_masters.scale[2].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[2].set_value((msg.value/127)*256)
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 4:
                if self.percent_level:
                    self.app.win_masters.scale[3].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[3].set_value((msg.value/127)*256)
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 5:
                if self.percent_level:
                    self.app.win_masters.scale[4].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[4].set_value((msg.value/127)*256)
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 6:
                if self.percent_level:
                    self.app.win_masters.scale[5].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[5].set_value((msg.value/127)*256)
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 7:
                if self.percent_level:
                    self.app.win_masters.scale[6].set_value((msg.value/127)*100)
                else:
                    self.app.win_masters.scale[6].set_value((msg.value/127)*256)

        # Ola messages
        readable, writable, exceptional = select.select([self.app.sock], [], [], 0)
        if readable:
            self.app.ola_client.SocketReady()
        return True

    def button_clicked_cb(self, button):
        """ Toggle type of view : patched channels or all channels """
        if self.view_type == 0:
            self.view_type = 1
        else:
            self.view_type = 0
        self.flowbox.invalidate_filter()

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print (keyname)
        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname =="6" or keyname == "7" or keyname =="8" or keyname == "9" or keyname =="0":
            self.keystring += keyname
            #self.label.set_label(self.keystring)
            #self.label.queue_draw()
            self.statusbar.push(self.context_id, self.keystring)
        if keyname == "KP_1" or keyname == "KP_2" or keyname == "KP_3" or keyname == "KP_4" or keyname == "KP_5" or keyname == "KP_6" or keyname == "KP_7" or keyname == "KP_8" or keyname == "KP_9" or keyname == "KP_0":
            self.keystring += keyname[3:]
            #self.label.set_label(self.keystring)
            #self.label.queue_draw()
            self.statusbar.push(self.context_id, self.keystring)
        if keyname == "period" :
            self.keystring += "."
            #self.label.set_label(self.keystring)
            #self.label.queue_draw()
            self.statusbar.push(self.context_id, self.keystring)
        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_a(self):
        """ All Channels """
        for output in range(512):
            #level = self.app.dmxframe.get_level(i)
            level = self.app.dmx.frame[output]
            channel = self.app.patch.outputs[output] - 1
            if level > 0:
                self.app.window.channels[channel].clicked = True
                self.app.window.channels[channel].queue_draw()
            else:
                self.app.window.channels[channel].clicked = False
                self.app.window.channels[channel].queue_draw()

    def keypress_c(self):
        """ Channel """
        if self.keystring == "" or self.keystring == "0":
            for i in range(512):
                channel = self.app.patch.outputs[i] - 1
                self.app.window.channels[channel].clicked = False
                self.app.window.channels[channel].queue_draw()
                self.last_chan_selected = ""
        else:
            try:
                channel = int(self.keystring)-1
                if channel >= 0 and channel < 512:
                    self.app.window.channels[channel].clicked = True
                    self.app.window.channels[channel].queue_draw()
                    self.last_chan_selected = self.keystring
            except:
                pass
        self.keystring = ""
        #self.label.set_label(self.keystring)
        #self.label.queue_draw()
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Thru """
        if self.last_chan_selected:
            for channel in range(int(self.last_chan_selected), int(self.keystring)):
                self.app.window.channels[channel].clicked = True
                self.app.window.channels[channel].queue_draw()
            self.last_chan_selected = self.keystring
            self.keystring = ""
            #self.label.set_label(self.keystring)
            #self.label.queue_draw()
            self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Add(self):
        self.keypress_plus()

    def keypress_plus(self):
        """ + """
        channel = int(self.keystring)-1
        if channel >= 0 and channel < 512:
            self.app.window.channels[channel].clicked = True
            self.app.window.channels[channel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""
        #self.label.set_label(self.keystring)
        #self.label.queue_draw()
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Subtract(self):
        self.keypress_minus()

    def keypress_minus(self):
        """ - """
        channel = int(self.keystring)-1
        if channel >= 0 and channel < 512:
            self.app.window.channels[channel].clicked = False
            self.app.window.channels[channel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""
        #self.label.set_label(self.keystring)
        #self.label.queue_draw()
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_Right(self):
        """ Level +1 of selected channels """
        for output in range(512):
            channel = self.app.patch.outputs[output]
            if self.app.window.channels[channel-1].clicked:
                level = self.app.dmx.frame[output]
                if level < 255:
                    self.app.dmx.user[channel-1] = level + 1
        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()

    def keypress_Left(self):
        """ Level -1 of selected channels """
        for output in range(512):
            channel = self.app.patch.outputs[output]
            if self.app.window.channels[channel-1].clicked:
                level = self.app.dmx.frame[output]
                if level > 0:
                    self.app.dmx.user[channel-1] = level - 1
        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()

    def keypress_KP_Enter(self):
        self.keypress_equal()

    def keypress_equal(self):
        """ @ Level """
        for output in range(512):
            channel = self.app.patch.outputs[output] - 1
            if self.app.window.channels[channel].clicked:
                try:
                    level = int(self.keystring)
                    if self.percent_level:
                        if level >= 0 and level <= 100:
                            self.app.dmx.user[channel] = int((level/100)*255+1)
                            if self.app.dmx.user[channel] > 255:
                                self.app.dmx.user[channel] = 255
                    else:
                        if level >= 0 and level <= 255:
                            self.app.dmx.user[channel] = level
                except:
                    pass
        self.keystring = ""
        #self.label.set_label(self.keystring)
        #self.label.queue_draw()
        self.statusbar.push(self.context_id, self.keystring)
        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()

    def keypress_BackSpace(self):
        self.keypress_Escape()

    def keypress_Escape(self):
        self.keystring = ""
        #self.label.set_label(self.keystring)
        #self.label.queue_draw()
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_Up(self):
        """ Seq - """
        self.app.sequence.sequence_minus(self.app)

    def keypress_Down(self):
        """ Seq + """
        self.app.sequence.sequence_plus(self.app)

    def keypress_space(self):
        """ Go """
        self.app.sequence.sequence_go(self.app)

    def keypress_G(self):
        """ Goto """
        self.app.sequence.sequence_goto(self.app, self.keystring)
        self.keystring = ""
        #self.label.set_label(self.keystring)
        #self.label.queue_draw()
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_U(self):
        """ Update Cue """
        position = self.app.sequence.position
        memory = self.app.sequence.cues[position].memory
        # TODO: Dialogue de confirmation de mise à jour
        for output in range(512):
            channel = self.app.patch.outputs[output]
            level = self.app.dmx.frame[output]
            #print("Output", output, "Channel", channel, "@", level)
            self.app.sequence.cues[position].channels[channel-1] = level
        print("Mise à jour de la mémoire", memory)
        # Tag filename as modified
        self.app.ascii.modified = True
        self.app.ascii.basename = self.app.ascii.basename + "*"
        self.app.window.header.set_title(self.app.ascii.basename)
