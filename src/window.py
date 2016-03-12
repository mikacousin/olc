import select
import time
import threading
from gi.repository import Gio, Gtk, GObject, Gdk, GLib
from ola import OlaClient

from olc.customwidgets import ChanelWidget

class Window(Gtk.ApplicationWindow):

    def __init__(self, app, patch):

        self.app = app
        self.patch = patch

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
        self.chanels = []
        #self.levels = []
        #self.progressbar = []

        for i in range(512):
            self.chanels.append(ChanelWidget(i+1, 0, 0))
            self.flowbox.add(self.chanels[i])

        self.scrolled.add(self.flowbox)
        self.paned.add1(self.scrolled)

        self.grid = Gtk.Grid()
        label = Gtk.Label("Saisie clavier : ")
        self.grid.add(label)
        self.label = Gtk.Label("")
        self.grid.attach_next_to(self.label, label, Gtk.PositionType.RIGHT, 1, 1)
        self.paned.add2(self.grid)

        self.add(self.paned)

        self.timeout_id = GObject.timeout_add(50, self.on_timeout, None)

        self.connect('key_press_event', self.on_key_press_event)

    def filter_func(self, child, user_data):
        i = child.get_index()
        for j in range(len(self.patch.chanels[i])):
            #print("Chanel:", i+1, "Output:", self.patch.chanels[i][j])
            if self.patch.chanels[i][j] != 0:
                return child
            else:
                return False

    def on_button_toggled(self, button, name):
        if button.get_active():
            state = "on"
        else:
            state = "off"

    def on_timeout(self, user_data):
        readable, writable, exceptional = select.select([self.app.sock], [], [], 0)
        if readable:
            self.app.ola_client.SocketReady()
        return True

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print (keyname)
        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname =="6" or keyname == "7" or keyname =="8" or keyname == "9" or keyname =="0":
            self.keystring += keyname
            self.label.set_label(self.keystring)
            self.label.queue_draw()
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
                self.app.window.chanels[channel].clicked = True
                self.app.window.chanels[channel].queue_draw()
            else:
                self.app.window.chanels[channel].clicked = False
                self.app.window.chanels[channel].queue_draw()

    def keypress_c(self):
        """ Channel """
        if self.keystring == "" or self.keystring == "0":
            for i in range(512):
                chanel = self.app.patch.outputs[i] - 1
                self.app.window.chanels[chanel].clicked = False
                self.app.window.chanels[chanel].queue_draw()
                self.last_chan_selected = ""
        else:
            chanel = int(self.keystring)-1
            if chanel >= 0 and chanel < 512:
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
                self.last_chan_selected = self.keystring
        self.keystring = ""
        self.label.set_label(self.keystring)
        self.label.queue_draw()

    def keypress_greater(self):
        """ Thru """
        if self.last_chan_selected:
            for chanel in range(int(self.last_chan_selected), int(self.keystring)):
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
            self.keystring = ""
            self.label.set_label(self.keystring)
            self.label.queue_draw()

    def keypress_plus(self):
        """ + """
        chanel = int(self.keystring)-1
        if chanel >= 0 and chanel < 512:
            self.app.window.chanels[chanel].clicked = True
            self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""
        self.label.set_label(self.keystring)
        self.label.queue_draw()

    def keypress_minus(self):
        """ - """
        chanel = int(self.keystring)-1
        if chanel >= 0 and chanel < 512:
            self.app.window.chanels[chanel].clicked = False
            self.app.window.chanels[chanel].queue_draw()
            self.last_chan_selected = self.keystring
        self.keystring = ""
        self.label.set_label(self.keystring)
        self.label.queue_draw()

    def keypress_Right(self):
        """ Level +1 of selected channels """
        for output in range(512):
            channel = self.app.patch.outputs[output]
            if self.app.window.chanels[channel-1].clicked:
                level = self.app.dmx.frame[output]
                if level < 255:
                    self.app.dmx.user[channel-1] = level + 1
        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()

    def keypress_Left(self):
        """ Level -1 of selected channels """
        for output in range(512):
            channel = self.app.patch.outputs[output]
            if self.app.window.chanels[channel-1].clicked:
                level = self.app.dmx.frame[output]
                if level > 0:
                    self.app.dmx.user[channel-1] = level - 1
        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()

    def keypress_equal(self):
        """ @ Level """
        for output in range(512):
            channel = self.app.patch.outputs[output] - 1
            if self.app.window.chanels[channel].clicked:
                level = int(self.keystring)
                if level >= 0 and level <= 255:
                    self.app.dmx.user[channel] = level
        self.keystring = ""
        self.label.set_label(self.keystring)
        self.label.queue_draw()
        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()

    def keypress_Escape(self):
        self.keystring = ""
        self.label.set_label(self.keystring)
        self.label.queue_draw()

    def keypress_Up(self):
        """ Seq - """
        self.app.sequence.sequence_minus(self.app)

    def keypress_Down(self):
        """ Seq + """
        self.app.sequence.sequence_plus(self.app)

    def keypress_space(self):
        """ Go """
        self.app.sequence.sequence_go(self.app)

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
