import time
import threading
import array
import mido
from gi.repository import Gio, Gtk, GObject, Gdk, GLib
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
        self.paned2.set_position(950)
        self.paned2.add1(self.paned)

        self.app = Gio.Application.get_default()
        self.seq = self.app.sequence
        
        # Sequential part of the window
        position = self.seq.position
        t_total = self.seq.cues[position].total_time
        t_in = self.seq.cues[position].time_in
        t_out = self.seq.cues[position].time_out
        t_wait = self.seq.cues[position].wait
        channel_time = self.seq.cues[position].channel_time

        # Crossfade widget
        self.sequential = SequentialWidget(t_total, t_in, t_out, t_wait, channel_time)

        # Model : Step, Memory, Text, Wait, Time Out, Time In, Channel Time
        self.cues_liststore1 = Gtk.ListStore(str, str, str, str, str, str, str, str)
        self.cues_liststore2 = Gtk.ListStore(str, str, str, str, str, str, str)

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
            if self.seq.cues[i].time_in.is_integer():
                t_in = str(int(self.seq.cues[i].time_in))
            else:
                t_in = str(self.seq.cues[i].time_in)
            channel_time = str(len(self.seq.cues[i].channel_time))
            if channel_time == "0":
                channel_time = ""
            bg = "#232729"
            self.cues_liststore1.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                wait, t_out, t_in, channel_time, bg])
            self.cues_liststore2.append([str(i), str(self.seq.cues[i].memory), self.seq.cues[i].text,
                wait, t_out, t_in, channel_time])

        # Filter for the first part of the cue list
        self.step_filter1 = self.cues_liststore1.filter_new()
        self.step_filter1.set_visible_func(self.step_filter_func1)
        # List
        self.treeview1 = Gtk.TreeView(model=self.step_filter1)
        self.treeview1.set_enable_search(False)
        sel = self.treeview1.get_selection()
        sel.set_mode(Gtk.SelectionMode.NONE)
        for i, column_title in enumerate(["Pas", "Mémoire", "Texte", "Wait", "Out", "In", "Channel Time"]):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            column = Gtk.TreeViewColumn(column_title, renderer, text=i, background=7)
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
        for i, column_title in enumerate(["Pas", "Mémoire", "Texte", "Wait", "Out", "In", "Channel Time"]):
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
        self.cues_liststore1[0][7] = "#997004"

        # Open MIDI input port
        try:
            self.inport = mido.open_input('UC-33 USB MIDI Controller MIDI ')
        except:
            self.inport = mido.open_input()

        # Scan MIDI every 100ms
        self.timeout_id = GObject.timeout_add(100, self.on_timeout, None)
        # Scan Ola messages - 27 = IN(1) + HUP(16) + PRI(2) + ERR(8)
        GLib.unix_fd_add_full(0, self.app.sock.fileno(), GLib.IOCondition(27), self.app.on_fd_read, None)

        self.connect('key_press_event', self.on_key_press_event)

        self.set_icon_name('olc')

    def step_filter_func1(self, model, iter, data):
        """ Filter for the first part of the cues list """
        if int(model[iter][0]) == self.app.sequence.position or int(model[iter][0]) == self.app.sequence.position+1:
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
        if child == self.app.patch_tab:
            return self.app.patch_tab.on_key_press_event(widget, event)
        if child == self.app.sequences_tab:
            return self.app.sequences_tab.on_key_press_event(widget, event)
        if child == self.app.channeltime_tab:
            return self.app.channeltime_tab.on_key_press_event(widget, event)

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

    def keypress_q(self):
        # TODO: Update Shortcuts window
        """ Seq - """
        self.app.sequence.sequence_minus(self.app)

    def keypress_w(self):
        """ Seq + """
        self.app.sequence.sequence_plus(self.app)

    def keypress_space(self):
        """ Go """
        self.app.sequence.sequence_go(self.app)

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
