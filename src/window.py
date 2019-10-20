import time
import threading
import array
import mido
from gi.repository import Gio, Gtk, Gdk, GObject, GLib, Pango
from ola import OlaClient

from olc.group import Group
from olc.customwidgets import ChannelWidget, SequentialWidget, GroupWidget

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
        self.set_name('olc')

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
        button = Gtk.MenuButton()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)
        box.add(button)
        popover = Gtk.Popover.new_from_model(button, app.setup_app_menu())
        button.set_popover(popover)
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
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_func, None) # Fonction de filtrage

        self.keystring = ""
        self.last_chan_selected = ""

        self.channels = []

        for i in range(512):
            self.channels.append(ChannelWidget(i+1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)
        self.paned.add1(self.scrolled)

        # Gtk.Statusbar to display keyboard's keys
        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("keypress")

        self.grid = Gtk.Grid()
        label = Gtk.Label("Saisie clavier : ")
        self.grid.add(label)
        self.grid.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)
        self.paned.add2(self.grid)

        self.paned2 = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned2.set_position(800)
        self.paned2.add1(self.paned)

        self.app = Gio.Application.get_default()
        self.seq = self.app.sequence
        
        # Sequential part of the window
        position = self.seq.position
        t_total = self.seq.cues[position].total_time
        t_in = self.seq.cues[position].time_in
        t_out = self.seq.cues[position].time_out
        d_in = self.seq.cues[position].delay_in
        d_out = self.seq.cues[position].delay_out
        t_wait = self.seq.cues[position].wait
        channel_time = self.seq.cues[position].channel_time

        # Crossfade widget
        self.sequential = SequentialWidget(t_total, t_in, t_out, d_in, d_out, t_wait, channel_time)

        # Model : Step, Memory, Text, Wait, Time Out, Time In, Channel Time
        self.cues_liststore1 = Gtk.ListStore(str, str, str, str, str, str, str, str, str, str, int, int)
        self.cues_liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)

        self.cues_liststore1.append(['', '', '', '', '', '', '', '', '', '#232729', 0, 0])
        self.cues_liststore1.append(['', '', '', '', '', '', '', '', '', '#232729', 0, 1])

        for i in range(self.app.sequence.last):
            if self.seq.cues[i].wait.is_integer():
                wait = str(int(self.seq.cues[i].wait))
                if wait == "0":
                    wait = ""
            else:
                wait = str(self.seq.cues[i].wait)
            if self.seq.cues[i].time_out.is_integer():
                t_out = str(int(self.seq.cues[i].time_out))
            else:
                t_out = str(self.seq.cues[i].time_out)
            if self.seq.cues[i].delay_out.is_integer():
                d_out = str(int(self.seq.cues[i].delay_out))
            else:
                d_out = str(self.seq.cues[i].delay_out)
            if self.seq.cues[i].time_in.is_integer():
                t_in = str(int(self.seq.cues[i].time_in))
            else:
                t_in = str(self.seq.cues[i].time_in)
            if self.seq.cues[i].delay_in.is_integer():
                d_in = str(int(self.seq.cues[i].delay_in))
            else:
                d_in = str(self.seq.cues[i].delay_in)
            channel_time = str(len(self.seq.cues[i].channel_time))
            if channel_time == "0":
                channel_time = ""
            bg = "#232729"
            if i == 0 or i == self.app.sequence.last-1:
                self.cues_liststore1.append([str(i), '', '', '', '', '', '', '', '', bg, Pango.Weight.NORMAL, 42])
            else:
                self.cues_liststore1.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                    wait, d_out, t_out, d_in, t_in, channel_time, bg, Pango.Weight.NORMAL, 42])
            self.cues_liststore2.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                wait, d_out, t_out, d_in, t_in, channel_time])

        # Filter for the first part of the cue list
        self.step_filter1 = self.cues_liststore1.filter_new()
        self.step_filter1.set_visible_func(self.step_filter_func1)
        # List
        self.treeview1 = Gtk.TreeView(model=self.step_filter1)
        self.treeview1.set_enable_search(False)
        sel = self.treeview1.get_selection()
        sel.set_mode(Gtk.SelectionMode.NONE)
        for i, column_title in enumerate(["Pas", "Mémoire", "Texte", "Wait", "Delay Out", "Out", "Delay In", "In", "Channel Time"]):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            column = Gtk.TreeViewColumn(column_title, renderer, text=i, background=9, weight=10)
            if i == 2:
                column.set_min_width(600)
                column.set_resizable(True)
            self.treeview1.append_column(column)

        # Filter
        self.step_filter2 = self.cues_liststore2.filter_new()
        self.step_filter2.set_visible_func(self.step_filter_func2)
        # List
        self.treeview2 = Gtk.TreeView(model=self.step_filter2)
        self.treeview2.set_enable_search(False)
        sel = self.treeview2.get_selection()
        sel.set_mode(Gtk.SelectionMode.NONE)
        for i, column_title in enumerate(["Pas", "Mémoire", "Texte", "Wait", "Delay Out", "Out", "Delay In", "In", "Channel Time"]):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == 2:
                column.set_min_width(600)
                column.set_resizable(True)
            self.treeview2.append_column(column)
        # Put Cues List in a scrolled window
        self.scrollable2 = Gtk.ScrolledWindow()
        self.scrollable2.set_vexpand(True)
        self.scrollable2.set_hexpand(True)
        self.scrollable2.add(self.treeview2)
        # Put Cues lists and sequential in a grid
        self.seq_grid = Gtk.Grid()
        self.seq_grid.set_row_homogeneous(False)
        self.seq_grid.attach(self.treeview1, 0, 0, 1, 1)
        self.seq_grid.attach_next_to(self.sequential, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1)
        self.seq_grid.attach_next_to(self.scrollable2, self.sequential, Gtk.PositionType.BOTTOM, 1, 1)

        # Sequential in a Tab
        self.notebook = Gtk.Notebook()

        self.notebook.append_page(self.seq_grid, Gtk.Label('Main Playback'))

        self.paned2.add2(self.notebook)

        self.add(self.paned2)

        # Select first Cue
        self.cues_liststore1[2][9] = "#997004"
        self.cues_liststore1[2][10] = Pango.Weight.HEAVY
        # Bold next Cue
        self.cues_liststore1[3][10] = Pango.Weight.HEAVY
        self.cues_liststore1[3][9] = "#555555"

        # Open MIDI input port
        #self.inport = mido.open_input('UC-33 USB MIDI Controller:UC-33 USB MIDI Controller MIDI  24:1')
        try:
            self.inport = mido.open_input('UC-33 USB MIDI Controller:UC-33 USB MIDI Controller MIDI  24:0')
        except:
            self.inport = mido.open_input()

        # Scan MIDI every 100ms
        self.timeout_id = GObject.timeout_add(100, self.on_timeout, None)
        # Scan Ola messages - 27 = IN(1) + HUP(16) + PRI(2) + ERR(8)
        GLib.unix_fd_add_full(0, self.app.sock.fileno(), GLib.IOCondition(27), self.app.on_fd_read, None)

        # TODO: Add Enttec wing playback support with Gio.SocketService (et Gio.SocketListener.add_address)
        """
        service = Gio.SocketService()
        service.connect('incoming', self.incoming_connection_cb)
        #service.add_address(Gio.InetSocketAddress(Gio.SocketFamily(2), 3330), Gio.SocketType(2), Gio.SocketProtocal(17), None)
        address = Gio.InetAddress.new_any(2)
        #address = Gio.InetAddress.new_from_string('127.0.0.1')
        #inetsock = Gio.InetSocketAddress.new(address, 3330)
        inetsock = Gio.InetSocketAddress.new_from_string('127.0.0.1', 3330)
        service.add_address(inetsock, Gio.SocketType.DATAGRAM, Gio.SocketProtocol.UDP)
        """
        """
        socket = Gio.Socket.new(Gio.SocketFamily.IPV4, Gio.SocketType.DATAGRAM, Gio.SocketProtocol.UDP)
        address = Gio.InetAddress.new_any(Gio.SocketFamily.IPV4)
        inetsock = Gio.InetSocketAddress.new(address, 3330)
        ret = socket.connect(inetsock)
        print(ret)
        fd = socket.get_fd()
        print(fd)
        ch = GLib.IOChannel.unix_new(fd)
        print(ch)
        GLib.io_add_watch(ch, 0, GLib.IOCondition.IN, self.incoming_connection_cb)
        """
        import socket
        address = ('', 3330)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(address)
        self.fd = self.sock.fileno()
        #ch = GLib.IOChannel.unix_new(fd)
        #GLib.io_add_watch(ch, 0, GLib.IOCondition.IN, self.incoming_connection_cb)
        GLib.unix_fd_add_full(0, self.fd, GLib.IOCondition.IN, self.incoming_connection_cb, None)

        self.connect('key_press_event', self.on_key_press_event)

        self.set_icon_name('olc')

    def incoming_connection_cb(self, fd, condition, data):
        #print(fd, condition, data)
        message = self.sock.recv(1024)
        if message[0:4] == b'WODD':
            print("Wing output data", message[0:4])
            print("Wing firmware :", message[4])
            print("Wing flags :", message[5])

            if message[6] & 16:
                print('Go released')
            else:
                print('Go pressed')
                self.keypress_space()
            if message[6] & 32:
                print('Back released')
            else:
                print('Back pressed')
            if message[6] & 64:
                print('PageDown released')
            else:
                print('PageDown pressed')
            if message[6] & 128:
                print('PageUp released')
            else:
                print('PageUp pressed')

            if message[7] & 1:
                print('Flash 10 (Key 39) released')
            else:
                print('Flash 10 (Key 39) pressed')
            if message[7] & 2:
                print('Flash 9 (Key 38) released')
            else:
                print('Flash 9 (Key 38) pressed')
            if message[7] & 4:
                print('Flash 8 (Key 37) released')
            else:
                print('Flash 8 (Key 37) pressed')
            if message[7] & 8:
                print('Flash 7 (Key 36) released')
            else:
                print('Flash 7 (Key 36) pressed')
            if message[7] & 16:
                print('Flash 6 (Key 35) released')
            else:
                print('Flash 6 (Key 35) pressed')
            if message[7] & 32:
                print('Flash 5 (Key 34) released')
            else:
                print('Flash 5 (Key 34) pressed')
            if message[7] & 64:
                print('Flash 4 (Key 33) released')
            else:
                print('Flash 4 (Key 33) pressed')
            if message[7] & 128:
                print('Flash 3 (Key 32) released')
            else:
                print('Flash 3 (Key 32) pressed')

            if message[8] & 1:
                print('Flash 2 (Key 31) released')
            else:
                print('Flash 2 (Key 31) pressed')
            if message[8] & 2:
                print('Flash 1 (Key 30) released')
            else:
                print('Flash 1 (Key 30) pressed')

            print('Fader 1', int(message[15]))
            self.app.masters[10].value = int(message[15])
            self.app.masters[10].level_changed()
            print('Fader 2', message[16])
            self.app.masters[0].value = int(message[16])
            self.app.masters[0].level_changed()
            print('Fader 3', message[17])
            print('Fader 4', message[18])
            print('Fader 5', message[19])
            print('Fader 6', message[20])
            print('Fader 7', message[21])
            print('Fader 8', message[22])
            print('Fader 9', message[23])
            print('Fader 10', message[24])

        return True

    def step_filter_func1(self, model, iter, data):
        """ Filter for the first part of the cues list """

        if self.app.sequence.position <= 0:
            if int(model[iter][11]) == 0 or int(model[iter][11]) == 1:
                return True
            if int(model[iter][0]) == 0 or int(model[iter][0]) == 1:
                return True
            else:
                return False

        if self.app.sequence.position == 1:
            if int(model[iter][11]) == 1:
                return True
            if int(model[iter][11]) == 0:
                return False
            if int(model[iter][0]) == 0 or int(model[iter][0]) == 1 or int(model[iter][0]) == 2:
                return True
            else:
                return False

        if int(model[iter][11]) == 1:
            return False
        if int(model[iter][11]) == 0:
            return False

        if int(model[iter][0]) == self.app.sequence.position or int(model[iter][0]) == self.app.sequence.position+1 or int(model[iter][0]) == self.app.sequence.position-1 or int(model[iter][0]) == self.app.sequence.position-2:
            return True
        else:
            return False

    def step_filter_func2(self, model, iter, data):
        """ Filter for the second part of the cues list """
        if int(model[iter][0]) <= self.app.sequence.position+1:
            return False
        else:
            return True

    def filter_func(self, child, user_data):
        """ Filter for channels window """
        if self.view_type == 0:
            i = child.get_index()
            for j in range(len(self.patch.channels[i])):
                if self.patch.channels[i][j] != 0:
                    #print("Chanel:", i+1, "Output:", self.patch.channels[i][j])
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

            # Go
            if msg.type == 'note_on' and msg.note == 11 and msg.velocity == 127:
                self.keypress_space()

            # Seq -
            if msg.type == 'note_on' and msg.note == 12 and msg.velocity == 127:
                self.keypress_q()

            # Seq +
            if msg.type == 'note_on' and msg.note == 13 and msg.velocity == 127:
                self.keypress_w()

            # Flash 1
            if msg.type == 'note_on' and msg.note == 1 and msg.velocity == 127:
                self.app.masters[5].value = 255
                self.app.masters[5].level_changed()
            else:
                self.app.masters[5].value = 0
                self.app.masters[5].level_changed()

            # Flash 3
            if msg.type == 'note_on' and msg.note == 3 and msg.velocity == 127:
                self.app.masters[14].value = 255
                self.app.masters[14].level_changed()
            else:
                self.app.masters[14].value = 0
                self.app.masters[14].level_changed()

            # Flash 7
            if msg.type == 'note_on' and msg.note == 7 and msg.velocity == 127:
                self.app.masters[2].value = 255
                self.app.masters[2].level_changed()
            else:
                self.app.masters[2].value = 0
                self.app.masters[2].level_changed()

            # Fader 1
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 1:
                self.app.masters[10].value = (msg.value / 127) * 255
                self.app.masters[10].level_changed()

            # Fader 2
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 2:
                self.app.masters[11].value = (msg.value / 127) * 255
                self.app.masters[11].level_changed()

            # Fader 3
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 3:
                self.app.masters[0].value = (msg.value / 127) * 255
                self.app.masters[0].level_changed()

            # Fader 4
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 4:
                self.app.masters[1].value = (msg.value / 127) * 255
                self.app.masters[1].level_changed()

            # Fader 5
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 5:
                self.app.masters[8].value = (msg.value / 127) * 255
                self.app.masters[8].level_changed()

            # Fader 6
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 6:
                self.app.masters[4].value = (msg.value / 127) * 255
                self.app.masters[4].level_changed()

            # Fader 7
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 7:
                self.app.masters[3].value = (msg.value / 127) * 255
                self.app.masters[3].level_changed()

        return True

    def button_clicked_cb(self, button):
        """ Toggle type of view : patched channels or all channels """
        if self.view_type == 0:
            self.view_type = 1
        else:
            self.view_type = 0
        self.flowbox.invalidate_filter()

    def on_key_press_event(self, widget, event):

        # Cherche la page ouverte dans le notebook
        # Pour rediriger les saisies clavier
        page = self.notebook.get_current_page()
        child = self.notebook.get_nth_page(page)
        if child == self.app.group_tab:
            return self.app.group_tab.on_key_press_event(widget, event)
        if child == self.app.master_tab:
            return self.app.master_tab.on_key_press_event(widget, event)
        if child == self.app.patch_outputs_tab:
            return self.app.patch_outputs_tab.on_key_press_event(widget, event)
        if child == self.app.patch_channels_tab:
            return self.app.patch_channels_tab.on_key_press_event(widget, event)
        if child == self.app.sequences_tab:
            return self.app.sequences_tab.on_key_press_event(widget, event)
        if child == self.app.channeltime_tab:
            return self.app.channeltime_tab.on_key_press_event(widget, event)
        if child == self.app.midi_tab:
            return self.app.midi_tab.on_key_press_event(widget, event)

        keyname = Gdk.keyval_name(event.keyval)
        #print (keyname)
        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname =="6" or keyname == "7" or keyname =="8" or keyname == "9" or keyname =="0":
            self.keystring += keyname
            self.statusbar.push(self.context_id, self.keystring)

        if keyname == "KP_1" or keyname == "KP_2" or keyname == "KP_3" or keyname == "KP_4" or keyname == "KP_5" or keyname == "KP_6" or keyname == "KP_7" or keyname == "KP_8" or keyname == "KP_9" or keyname == "KP_0":
            self.keystring += keyname[3:]
            self.statusbar.push(self.context_id, self.keystring)

        if keyname == "period" :
            self.keystring += "."
            self.statusbar.push(self.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)

        if func:
            return func()

    def keypress_Right(self):
        """ Next Channel """

        if self.last_chan_selected == '':
            # Find first patched channel
            for i in range(512):
                if self.app.patch.channels[i][0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        elif int(self.last_chan_selected) < 511:
            # Find next patched channel
            next_chan = 0
            for i in range(int(self.last_chan_selected)+1, 512):
                if self.app.patch.channels[i][0]:
                    next_chan = i
                    break
            if next_chan:
                self.flowbox.unselect_all()
                child = self.flowbox.get_child_at_index(next_chan)
                self.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(next_chan)

    def keypress_Left(self):
        """ Previous Channel """

        if self.last_chan_selected == '':
            # Find first patched channel
            for i in range(512):
                if self.app.patch.channels[i][0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        elif int(self.last_chan_selected) > 0:
            # Find previous patched channel
            chan = int(self.last_chan_selected)
            for i in range(int(self.last_chan_selected), 0, -1):
                if self.app.patch.channels[i-1][0]:
                    chan = i - 1
                    break
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(chan)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(chan)

    def keypress_Down(self):
        """ Next Line """

        if self.last_chan_selected == '':
            # Find first patched channel
            for i in range(512):
                if self.app.patch.channels[i][0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        else:
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(allocation.x, allocation.y + allocation.height)
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(index)

    def keypress_Up(self):
        """ Previous Line """

        if self.last_chan_selected == '':
            # Find first patched channel
            for i in range(512):
                if self.app.patch.channels[i][0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        else:
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(allocation.x, allocation.y - allocation.height/2)
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(index)

    def keypress_a(self):
        """ All Channels """

        self.flowbox.unselect_all()

        for output in range(512):
            level = self.app.dmx.frame[output]
            channel = self.app.patch.outputs[output] - 1
            if level > 0:
                child = self.flowbox.get_child_at_index(channel)
                self.set_focus(child)
                self.flowbox.select_child(child)

    def keypress_c(self):
        """ Channel """

        self.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < 512:
                child = self.flowbox.get_child_at_index(channel)
                self.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = self.keystring

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Thru """

        sel = self.flowbox.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if not self.last_chan_selected:
            sel = self.flowbox.get_selected_children()
            if len(sel):
                for flowboxchild in sel:
                    children = flowboxchild.get_children()

                    for channelwidget in children:
                        channel = int(channelwidget.channel)
                self.last_chan_selected = str(channel)

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(self.last_chan_selected):
                for channel in range(int(self.last_chan_selected) - 1, to_chan):
                    child = self.flowbox.get_child_at_index(channel)
                    self.set_focus(child)
                    self.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):
                    child = self.flowbox.get_child_at_index(channel)
                    self.set_focus(child)
                    self.flowbox.select_child(child)

            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Add(self):
        self.keypress_plus()

    def keypress_plus(self):
        """ + """

        if self.keystring == "":
            return

        channel = int(self.keystring)-1
        if channel >= 0 and channel < 512:
            child = self.flowbox.get_child_at_index(channel)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Subtract(self):
        self.keypress_minus()

    def keypress_minus(self):
        """ - """

        if self.keystring == "":
            return

        channel = int(self.keystring)-1
        if channel >= 0 and channel < 512:
            child = self.flowbox.get_child_at_index(channel)
            self.set_focus(child)
            self.flowbox.unselect_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_exclam(self):
        """ Level + (% level) of selected channels """

        lvl = Gio.Application.get_default().settings.get_int('percent-level')

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                for output in self.app.patch.channels[channel]:
                    level = self.app.dmx.frame[output - 1]
                    if level + lvl > 255:
                        self.app.dmx.user[channel] = 255
                    else:
                        self.app.dmx.user[channel] = level + lvl

        self.app.dmx.send()

    def keypress_colon(self):
        """ Level - (% level) of selected channels """

        lvl = Gio.Application.get_default().settings.get_int('percent-level')

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                for output in self.app.patch.channels[channel]:
                    level = self.app.dmx.frame[output - 1]
                    if level - lvl < 0:
                        self.app.dmx.user[channel] = 0
                    else:
                        self.app.dmx.user[channel] = level - lvl


        self.app.dmx.send()

    def keypress_KP_Enter(self):
        self.keypress_equal()

    def keypress_equal(self):
        """ @ Level """

        level = int(self.keystring)

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                if self.app.settings.get_boolean('percent'):
                    if level >= 0 and level <= 100:
                        self.app.dmx.user[channel] = int(round((level/100)*255))
                else:
                    if level >= 0 and level <= 255:
                        self.app.dmx.user[channel] = level

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

        self.app.dmx.send()

    def keypress_BackSpace(self):
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_Escape(self):
        self.flowbox.unselect_all()
        self.last_chan_selected = ''

    def keypress_q(self):
        # TODO: Update Shortcuts window
        """ Seq - """
        self.app.sequence.sequence_minus(self.app)

    def keypress_w(self):
        """ Seq + """
        self.app.sequence.sequence_plus(self.app)

    # TODO: Delete this, Go is a global shortcut
    #def keypress_space(self):
    #    """ Go """
    #    self.app.sequence.sequence_go(self.app)

    def keypress_G(self):
        """ Goto """
        self.app.sequence.sequence_goto(self.app, self.keystring)
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_U(self):
        """ Update Cue """
        position = self.app.sequence.position
        memory = self.app.sequence.cues[position].memory

        # Confirmation Dialog
        dialog = Dialog(self, memory)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:

            for output in range(512):
                channel = self.app.patch.outputs[output]
                level = self.app.dmx.frame[output]

                self.app.sequence.cues[position].channels[channel-1] = level

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + "*")

        elif response == Gtk.ResponseType.CANCEL:
            pass

        dialog.destroy()

class Dialog(Gtk.Dialog):

    def __init__(self, parent, memory):
        Gtk.Dialog.__init__(self, "", parent, 0,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                 Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_default_size(150,100)

        label = Gtk.Label("Update memory " + memory + " ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()
