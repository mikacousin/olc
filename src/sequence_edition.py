import array
from gi.repository import Gtk, Gio, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_channel import ChannelWidget

class SequenceTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ""
        self.last_chan_selected = ""

        # To stock user modification on channels
        self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        #self.set_row_homogeneous(True)

        # List of Sequences
        self.liststore1 = Gtk.ListStore(int, str, str)

        self.liststore1.append([self.app.sequence.index, self.app.sequence.type_seq, self.app.sequence.text])

        for chaser in range(len(self.app.chasers)):
            self.liststore1.append([self.app.chasers[chaser].index, self.app.chasers[chaser].type_seq, self.app.chasers[chaser].text])

        self.treeview1 = Gtk.TreeView(model=self.liststore1)
        self.treeview1.set_enable_search(False)
        selection = self.treeview1.get_selection()
        selection.connect('changed', self.on_sequence_changed)

        for i, column_title in enumerate(["Seq", "Type", "Name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview1.append_column(column)

        self.attach(self.treeview1, 0, 0, 1, 1)

        # We put channels and memories list in a paned
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Channels in the selected cue
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []
        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i+1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)
        self.paned.add1(self.scrolled)

        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str, str)

        # Selected Sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]

            # Find it
            for i in range(len(self.liststore1)):
                #print(i, path.get_indices()[0])
                if i == selected:
                    #print("Index :", self.liststore1[i][0])
                    if self.liststore1[i][0] == self.app.sequence.index:
                        self.seq = self.app.sequence
                    else:
                        for j in range(len(self.app.chasers)):
                            if self.liststore1[i][0] == self.app.chasers[j].index:
                                self.seq = self.app.chasers[j]
            # Liststore with infos from the sequence
            for i in range(self.seq.last)[1:]:
                if self.seq.steps[i].wait.is_integer():
                    wait = str(int(self.seq.steps[i].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.steps[i].wait)
                if self.seq.steps[i].time_out.is_integer():
                    t_out = str(int(self.seq.steps[i].time_out))
                else:
                    t_out = str(self.seq.steps[i].time_out)
                if self.seq.steps[i].delay_out.is_integer():
                    d_out = str(int(self.seq.steps[i].delay_out))
                    if d_out == "0":
                        d_out = ""
                else:
                    d_out = str(self.seq.steps[i].delay_out)
                if self.seq.steps[i].time_in.is_integer():
                    t_in = str(int(self.seq.steps[i].time_in))
                else:
                    t_in = str(self.seq.steps[i].time_in)
                if self.seq.steps[i].delay_in.is_integer():
                    d_in = str(int(self.seq.steps[i].delay_in))
                    if d_in == "0":
                        d_in = ""
                else:
                    d_in = str(self.seq.steps[i].delay_in)
                channel_time = str(len(self.seq.steps[i].channel_time))
                if channel_time == "0":
                    channel_time = ""
                self.liststore2.append([str(i), str(self.seq.steps[i].cue.memory), self.seq.steps[i].text,
                    wait, d_out, t_out, d_in, t_in, channel_time])

        self.filter2 = self.liststore2.filter_new()
        self.filter2.set_visible_func(self.filter_cue_func)

        self.treeview2 = Gtk.TreeView(model=self.filter2)
        self.treeview2.set_enable_search(False)
        #self.treeview2.set_activate_on_single_click(True)
        self.treeview2.connect('cursor-changed', self.on_memory_changed)
        self.treeview2.connect('row-activated', self.on_row_activated)

        # Display selected sequence
        for i, column_title in enumerate(["Step", "Memory", "Text", "Wait", "Delay Out", "Out", "Delay In", "In", "Channel Time"]):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            if i == 3:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.wait_edited)
            if i == 4:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.delay_out_edited)
            if i == 5:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.out_edited)
            if i == 6:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.delay_in_edited)
            if i == 7:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.in_edited)
            if i == 2:
                renderer.set_property('editable', True)
                renderer.connect('edited', self.text_edited)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)

            if i == 2:
                column.set_min_width(200)
                column.set_resizable(True)

            self.treeview2.append_column(column)

        # Put Cues List in a scrolled window
        self.scrollable2 = Gtk.ScrolledWindow()
        self.scrollable2.set_vexpand(True)
        self.scrollable2.set_hexpand(True)
        self.scrollable2.add(self.treeview2)

        self.paned.add2(self.scrollable2)

        self.attach_next_to(self.paned, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1)

        self.flowbox.set_filter_func(self.filter_func, None)

        # Select Main Playback
        path = Gtk.TreePath.new_first()
        self.treeview1.set_cursor(path, None, False)

    def on_row_activated(self, treeview, path, column):
        # Find the double clicked cell
        itr = self.liststore2.get_iter(path)
        columns = self.treeview2.get_columns()
        for col_nb, col in enumerate(columns):
            if col == column:
                break
        # Double click on Channel Time
        if col_nb == 8:

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        seq = self.app.chasers[i]

            # Edit Channel Time
            step = self.liststore2[path][0]
            self.app._channeltime(seq, step)

    def wait_edited(self, widget, path, text):

        if text == '':
            text = '0'

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            if text == "0":
                self.liststore2[path][3] = ""
            else:
                self.liststore2[path][3] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Wait value
            self.seq.steps[step].wait = float(text)
            # Update Total Time
            if self.seq.steps[step].time_in + self.seq.steps[step].delay_in > self.seq.steps[step].time_out + self.seq.steps[step].delay_out:
                self.seq.steps[step].total_time = self.seq.steps[step].time_in + self.seq.steps[step].wait + self.seq.steps[step].delay_in
            else:
                self.seq.steps[step].total_time = self.seq.steps[step].time_out + self.seq.steps[step].wait + self.seq.steps[step].delay_out
            for channel in self.seq.steps[step].channel_time.keys():
                t = self.seq.steps[step].channel_time[channel].delay + self.seq.steps[step].channel_time[channel].time + self.seq.steps[step].wait
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                if text == "0":
                    self.app.window.cues_liststore1[path][3] = ""
                    self.app.window.cues_liststore2[path][3] = ""
                else:
                    self.app.window.cues_liststore1[path][3] = text
                    self.app.window.cues_liststore2[path][3] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.wait = float(text)
                    self.app.window.sequential.total_time = self.seq.steps[step].total_time
                    self.app.window.sequential.queue_draw()

    def out_edited(self, widget, path, text):

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            self.liststore2[path][5] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Time Out value
            self.seq.steps[step].time_out = float(text)
            # Update Total Time
            if self.seq.steps[step].time_in + self.seq.steps[step].delay_in > self.seq.steps[step].time_out + self.seq.steps[step].delay_out:
                self.seq.steps[step].total_time = self.seq.steps[step].time_in + self.seq.steps[step].wait + self.seq.steps[step].delay_in
            else:
                self.seq.steps[step].total_time = self.seq.steps[step].time_out + self.seq.steps[step].wait + self.seq.steps[step].delay_out
            for channel in self.seq.steps[step].channel_time.keys():
                t = self.seq.steps[step].channel_time[channel].delay + self.seq.steps[step].channel_time[channel].time + self.seq.steps[step].wait
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                self.app.window.cues_liststore1[path][5] = text
                self.app.window.cues_liststore2[path][5] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.time_out = float(text)
                    self.app.window.sequential.total_time = self.seq.steps[step].total_time
                    self.app.window.sequential.queue_draw()

    def in_edited(self, widget, path, text):

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            self.liststore2[path][7] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Time In value
            self.seq.steps[step].time_in = float(text)
            # Update Total Time
            if self.seq.steps[step].time_in + self.seq.steps[step].delay_in > self.seq.steps[step].time_out + self.seq.steps[step].delay_out:
                self.seq.steps[step].total_time = self.seq.steps[step].time_in + self.seq.steps[step].wait + self.seq.steps[step].delay_in
            else:
                self.seq.steps[step].total_time = self.seq.steps[step].time_out + self.seq.steps[step].wait + self.seq.steps[step].delay_out
            for channel in self.seq.steps[step].channel_time.keys():
                t = self.seq.steps[step].channel_time[channel].delay + self.seq.steps[step].channel_time[channel].time + self.seq.steps[step].wait
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                self.app.window.cues_liststore1[path][7] = text
                self.app.window.cues_liststore2[path][7] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.time_in = float(text)
                    self.app.window.sequential.total_time = self.seq.steps[step].total_time
                    self.app.window.sequential.queue_draw()

    def delay_out_edited(self, widget, path, text):

        if text == '':
            text = '0'

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            if text == "0":
                self.liststore2[path][4] = ""
            else:
                self.liststore2[path][4] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            self.seq.steps[step].delay_out = float(text)
            # Update Total Time
            if self.seq.steps[step].time_in + self.seq.steps[step].delay_in > self.seq.steps[step].time_out + self.seq.steps[step].delay_out:
                self.seq.steps[step].total_time = self.seq.steps[step].time_in + self.seq.steps[step].wait + self.seq.steps[step].delay_in
            else:
                self.seq.steps[step].total_time = self.seq.steps[step].time_out + self.seq.steps[step].wait + self.seq.steps[step].delay_out
            for channel in self.seq.steps[step].channel_time.keys():
                t = self.seq.steps[step].channel_time[channel].delay + self.seq.steps[step].channel_time[channel].time + self.seq.steps[step].wait
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                if text == "0":
                    self.app.window.cues_liststore1[path][4] = ""
                    self.app.window.cues_liststore2[path][4] = ""
                else:
                    self.app.window.cues_liststore1[path][4] = text
                    self.app.window.cues_liststore2[path][4] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.delay_out = float(text)
                    self.app.window.sequential.total_time = self.seq.steps[step].total_time
                    self.app.window.sequential.queue_draw()

    def delay_in_edited(self, widget, path, text):

        if text == '':
            text = '0'

        if text.replace('.','',1).isdigit():

            if text[0] == ".":
                text = '0' + text

            if text == "0":
                self.liststore2[path][6] = ""
            else:
                self.liststore2[path][6] = text

            # Find selected sequence
            seq_path, focus_column = self.treeview1.get_cursor()
            selected = seq_path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Cue
            step = int(self.liststore2[path][0])

            # Update Delay Out value
            self.seq.steps[step].delay_in = float(text)
            # Update Total Time
            if self.seq.steps[step].time_in + self.seq.steps[step].delay_in > self.seq.steps[step].time_out + self.seq.steps[step].delay_out:
                self.seq.steps[step].total_time = self.seq.steps[step].time_in + self.seq.steps[step].wait + self.seq.steps[step].delay_in
            else:
                self.seq.steps[step].total_time = self.seq.steps[step].time_out + self.seq.steps[step].wait + self.seq.steps[step].delay_out
            for channel in self.seq.steps[step].channel_time.keys():
                t = self.seq.steps[step].channel_time[channel].delay + self.seq.steps[step].channel_time[channel].time + self.seq.steps[step].wait
                if t > self.seq.steps[step].total_time:
                    self.seq.steps[step].total_time = t

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Sequential Tab
            if self.seq == self.app.sequence:
                path = str(int(path) + 1)
                if text == "0":
                    self.app.window.cues_liststore1[path][6] = ""
                    self.app.window.cues_liststore2[path][6] = ""
                else:
                    self.app.window.cues_liststore1[path][6] = text
                    self.app.window.cues_liststore2[path][6] = text
                if self.app.sequence.position+1 == step:
                    self.app.window.sequential.delay_in = float(text)
                    self.app.window.sequential.total_time = self.seq.steps[step].total_time
                    self.app.window.sequential.queue_draw()

    def text_edited(self, widget, path, text):

        self.liststore2[path][2] = text

        # Find selected sequence
        seq_path, focus_column = self.treeview1.get_cursor()
        selected = seq_path.get_indices()[0]
        sequence = self.liststore1[selected][0]
        if sequence == self.app.sequence.index:
            self.seq = self.app.sequence
        else:
            for i in range(len(self.app.chasers)):
                if sequence == self.app.chasers[i].index:
                    self.seq = self.app.chasers[i]
        # Find Cue
        step = int(self.liststore2[path][0])

        # Update text value
        self.seq.steps[step].text = text

        # Tag filename as modified
        self.app.ascii.modified = True
        self.app.window.header.set_title(self.app.ascii.basename + '*')

        # Update Main Playback
        if self.seq == self.app.sequence:
            path = str(int(path) + 1)
            self.app.window.cues_liststore1[path][2] = text
            self.app.window.cues_liststore2[path][2] = text

            # Update window's subtitle if needed
            if self.app.sequence.position == step:
                subtitle = "Mem. : " + self.seq.steps[step].cue.memory + " " + self.seq.steps[step].text + " - Next Mem. : " + self.seq.steps[step + 1].cue.memory + " " + self.seq.steps[step + 1].text
                self.app.window.header.set_subtitle(subtitle)

            if self.app.sequence.position + 1 == step:
                subtitle = "Mem. : " + self.seq.steps[step - 1].cue.memory + " " + self.seq.steps[step - 1].text + " - Next Mem. : " + self.seq.steps[step].cue.memory + " " + self.seq.steps[step].text
                self.app.window.header.set_subtitle(subtitle)

    def on_memory_changed(self, treeview):
        """ Select memory """
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def filter_cue_func(self, model, iter, data):
        return True

    def filter_func(self, child, user_data):
        """ Filter channels """
        # Find selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
        # Find Step
        i = child.get_index()
        selection = self.treeview2.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter != None:
            step = int(model[treeiter][0])
            # Display channels in step
            channels = self.seq.steps[step].cue.channels

            if channels[i] != 0 or self.channels[i].clicked:
                if self.user_channels[i] == -1:
                    self.channels[i].level = channels[i]
                    self.channels[i].next_level = channels[i]
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                return child
            else:
                if self.user_channels[i] == -1:
                    self.channels[i].level = 0
                    self.channels[i].next_level = 0
                    return False
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                    return child

        if self.user_channels[i] != -1 or self.channels[i].clicked:
            if self.user_channels[i] == -1:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
            else:
                self.channels[i].level = self.user_channels[i]
                self.channels[i].next_level = self.user_channels[i]
            return child

        return False

    def on_sequence_changed(self, selection):
        """ Select Sequence """

        # TODO: voir pourquoi clear declanche un scan de toute la liststore
        #self.liststore2.clear()
        self.liststore2 = Gtk.ListStore(str, str, str, str, str, str, str, str,str)

        model, treeiter = selection.get_selected()

        if treeiter != None:
            selected = model[treeiter][0]
            # Find it
            for i in range(len(self.liststore1)):
                if i + 1 == selected:
                    if self.liststore1[i][0] == self.app.sequence.index:
                        self.seq = self.app.sequence
                    else:
                        for j in range(len(self.app.chasers)):
                            if self.liststore1[i][0] == self.app.chasers[j].index:
                                self.seq = self.app.chasers[j]
            # Liststore with infos from the sequence
            if self.seq == self.app.sequence:
                for i in range(self.seq.last)[1:]:
                    if self.seq.steps[i].wait.is_integer():
                        wait = str(int(self.seq.steps[i].wait))
                        if wait == "0":
                            wait = ""
                    else:
                        wait = str(self.seq.steps[i].wait)
                    if self.seq.steps[i].time_out.is_integer():
                        t_out = str(int(self.seq.steps[i].time_out))
                    else:
                        t_out = str(self.seq.steps[i].time_out)
                    if self.seq.steps[i].delay_out.is_integer():
                        d_out = str(int(self.seq.steps[i].delay_out))
                        if d_out == "0":
                            d_out = ""
                    else:
                        d_out = str(self.seq.steps[i].delay_out)
                    if self.seq.steps[i].time_in.is_integer():
                        t_in = str(int(self.seq.steps[i].time_in))
                    else:
                        t_in = str(self.seq.steps[i].time_in)
                    if self.seq.steps[i].delay_in.is_integer():
                        d_in = str(int(self.seq.steps[i].delay_in))
                        if d_in == "0":
                            d_in = ""
                    else:
                        d_in = str(self.seq.steps[i].delay_in)
                    channel_time = str(len(self.seq.steps[i].channel_time))
                    if channel_time == "0":
                        channel_time = ""
                    self.liststore2.append([str(i), str(self.seq.steps[i].cue.memory), self.seq.steps[i].text,
                        wait, d_out, t_out, d_in, t_in, channel_time])
            else:
                for i in range(self.seq.last)[1:]:
                    if self.seq.steps[i].wait.is_integer():
                        wait = str(int(self.seq.steps[i].wait))
                        if wait == "0":
                            wait = ""
                    else:
                        wait = str(self.seq.steps[i].wait)
                    if self.seq.steps[i].time_out.is_integer():
                        t_out = str(int(self.seq.steps[i].time_out))
                    else:
                        t_out = str(self.seq.steps[i].time_out)
                    if self.seq.steps[i].delay_out.is_integer():
                        d_out = str(int(self.seq.steps[i].delay_out))
                        if d_out == "0":
                            d_out = ""
                    else:
                        d_out = str(self.seq.steps[i].delay_out)
                    if self.seq.steps[i].time_in.is_integer():
                        t_in = str(int(self.seq.steps[i].time_in))
                    else:
                        t_in = str(self.seq.steps[i].time_in)
                    if self.seq.steps[i].delay_in.is_integer():
                        d_in = str(int(self.seq.steps[i].delay_in))
                        if d_in == "0":
                            d_in = ""
                    else:
                        d_in = str(self.seq.steps[i].delay_in)
                    channel_time = str(len(self.seq.steps[i].channel_time))
                    if channel_time == "0":
                        channel_time = ""
                    self.liststore2.append([str(i), str(self.seq.steps[i].cue.memory), self.seq.steps[i].text,
                        wait, d_out, t_out, d_in, t_in, channel_time])

            self.treeview2.set_model(self.liststore2)
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

            self.app.window.show_all()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.sequences_tab)
        self.app.window.notebook.remove_page(page)
        self.app.sequences_tab = None

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
        self.app.sequences_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Q(self):
        """ Cycle Sequences """
        # TODO: Update Shortcuts window
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            path.next()
            self.treeview1.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview1.set_cursor(path)
        path = Gtk.TreePath.new_first()
        self.treeview2.set_cursor(path)
        # Reset user modifications
        self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

    def keypress_q(self):
        """ Prev Memory """

        # Reset user modifications
        self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

        path, focus_column = self.treeview2.get_cursor()
        if path != None:
            if path.prev():
                self.treeview2.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

    def keypress_w(self):
        """ Next Memory """

        # Reset user modifications
        self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

        path, focus_column = self.treeview2.get_cursor()
        if path != None:
            path.next()
            self.treeview2.set_cursor(path)
        else:
            path = Gtk.TreePath.new_first()
            self.treeview2.set_cursor(path)

    def keypress_a(self):
        """ All Channels """

        self.flowbox.unselect_all()

        # Find selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Step
            path, focus_column = self.treeview2.get_cursor()
            if path != None:
                selected = path.get_indices()[0]
                step = int(self.liststore2[selected][0])
                channels = self.seq.steps[step].cue.channels

                for channel in range(MAX_CHANNELS):
                    if channels[channel] != 0:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.app.window.set_focus(child)
                        self.flowbox.select_child(child)
                    else:
                        self.channels[channel].clicked = False
                self.flowbox.invalidate_filter()

    def keypress_c(self):
        """ Channel """

        self.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < MAX_CHANNELS:

                # Only patched channel
                if self.app.patch.channels[channel][0] != [0, 0]:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring
        else:
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        sel = self.flowbox.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(self.last_chan_selected):
                for channel in range(int(self.last_chan_selected) - 1, to_chan):
                    # Only patched channels
                    if self.app.patch.channels[channel][0] != [0, 0]:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.app.window.set_focus(child)
                        self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()
            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):
                    # Only patched channels
                    if self.app.patch.channels[channel][0] != [0, 0]:
                        self.channels[channel].clicked = True
                        child = self.flowbox.get_child_at_index(channel)
                        self.app.window.set_focus(child)
                        self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_plus(self):
        """ Channel + """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if (channel >= 0 and channel < MAX_CHANNELS
                and self.app.patch.channels[channel][0] != [0, 0]):
            self.channels[channel].clicked = True
            self.flowbox.invalidate_filter()

            child = self.flowbox.get_child_at_index(channel)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_minus(self):
        """ Channel - """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if (channel >= 0 and channel < MAX_CHANNELS
                and self.app.patch.channels[channel][0] != [0, 0]):
            self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

            child = self.flowbox.get_child_at_index(channel)
            self.app.window.set_focus(child)
            self.flowbox.unselect_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_equal(self):
        """ @ Level """
        level = int(self.keystring)
        if Gio.Application.get_default().settings.get_boolean('percent'):
            if level >= 0 and level <= 100:
                level = int(round((level / 100) * 255))
            else:
                level = -1
        if level >= 0 and level <= 255:
            sel = self.flowbox.get_selected_children()

            for flowboxchild in sel:
                children = flowboxchild.get_children()

                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1

                    if level != -1:
                        self.channels[channel].level = level
                        self.channels[channel].next_level = level
                        self.channels[channel].queue_draw()
                        self.user_channels[channel] = level

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_colon(self):
        """ Level - % """

        lvl = Gio.Application.get_default().settings.get_int('percent-level')

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                if level - lvl < 0:
                    level = 0
                else:
                    level = level - lvl

                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def keypress_exclam(self):
        """ Level + % """

        lvl = Gio.Application.get_default().settings.get_int('percent-level')

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                level = self.channels[channel].level

                if level + lvl > 255:
                    level = 255
                else:
                    level = level + lvl

                self.channels[channel].level = level
                self.channels[channel].next_level = level
                self.channels[channel].queue_draw()
                self.user_channels[channel] = level

    def keypress_U(self):
        """ Update Cue """

        # Find selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]
            # Find Step
            path, focus_column = self.treeview2.get_cursor()
            if path != None:
                selected = path.get_indices()[0]
                step = int(self.liststore2[selected][0])
                channels = self.seq.steps[step].cue.channels

                memory = self.seq.steps[step].cue.memory

                # Dialog to confirm Update
                dialog = Dialog(self.app.window, memory)
                response = dialog.run()

                if response == Gtk.ResponseType.OK:
                    # Update levels in the cue
                    for channel in range(MAX_CHANNELS):
                        channels[channel] = self.channels[channel].level
                        if channels[channel] != 0:
                            self.seq.channels[channel] = 1

                    # Tag filename as modified
                    self.app.ascii.modified = True
                    self.app.window.header.set_title(self.app.ascii.basename + "*")

                    # Update Main playback display
                    if self.seq == self.app.sequence:
                        if step == self.app.sequence.position + 1:
                            for channel in range(MAX_CHANNELS):
                                self.app.window.channels[channel].next_level = self.seq.steps[step].cue.channels[channel]
                                self.app.window.channels[channel].queue_draw()

                elif response == Gtk.ResponseType.CANCEL:
                    pass

                dialog.destroy()

                # Reset user modifications
                self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

    def keypress_N(self):
        """ New Chaser """

        # Use the next free index
        if len(self.app.chasers) >  0:
            index_seq = self.app.chasers[-1].index + 1
        else:
            # Or 2 (1 is for Main Playback)
            index_seq = 2

        # Create Chaser
        self.app.chasers.append(Sequence(index_seq, self.app.patch, type_seq = "Chaser"))

        # Update List of sequences
        self.liststore1.append([self.app.chasers[-1].index, self.app.chasers[-1].type_seq,
            self.app.chasers[-1].text])

        # Tag filename as modified
        self.app.ascii.modified = True
        self.app.window.header.set_title(self.app.ascii.basename + '*')

    def keypress_R(self):
        """ New Cue """

        # TODO: Doesn't work anymore

        # If user enter a memory number, use it
        mem = -1

        if self.keystring != "":
            mem = float(self.keystring)

            # Memory elready exist ?
            for i in range(len(self.seq.steps)):
                if self.seq.steps[i].cue.memory == float(mem):
                    # Update memory

                    # Dialog to confirm Update
                    dialog = Dialog(self.app.window, str(mem))
                    response = dialog.run()

                    if response == Gtk.ResponseType.OK:
                        # Update memory's levels
                        for channel in range(MAX_CHANNELS):
                            self.seq.steps[i].cue.channels[channel] = self.channels[channel].level
                            if self.seq.steps[i].cue.channels[channel] != 0:
                                self.seq.channels[channel] = 1

                        # Tag filename as modified
                        self.app.ascii.modified = True
                        self.app.window.header.set_title(self.app.ascii.basename + '*')

                        # Select memory modified
                        path = Gtk.TreePath.new_from_indices([i - 1])
                        self.treeview2.set_cursor(path, None, False)

                        # Update Main playback
                        if self.seq == self.app.sequence:
                            if i == self.app.sequence.position + 1:
                                for channel in range(MAX_CHANNELS):
                                    self.app.window.channels[channel].next_level = self.seq.steps[i].cue.channels[channel]
                                    self.app.window.channels[channel].queue_draw()

                    elif response == Gtk.ResponseType.CANCEL:
                        pass

                    dialog.destroy()

                    # Tag filename as modified
                    self.app.ascii.modified = True
                    self.app.window.header.set_title(self.app.ascii.basename + '*')

                    self.keystring = ""
                    self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

                    return

            self.keystring = ""
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        # Find the selected sequence
        path, focus_column = self.treeview1.get_cursor()
        if path != None:
            selected = path.get_indices()[0]
            sequence = self.liststore1[selected][0]
            if sequence == self.app.sequence.index:
                self.seq = self.app.sequence
            else:
                for i in range(len(self.app.chasers)):
                    if sequence == self.app.chasers[i].index:
                        self.seq = self.app.chasers[i]

            # Insert new memory if a number is given
            if mem != -1:
                # Find step where insert new memory
                for i in range(len(self.seq.steps)):
                    if float(self.seq.steps[i].cue.memory) > mem:
                        break

                # For chasers if the new cue is at the end
                if self.seq.index != 1:
                    if float(self.seq.steps[i].cue.memory) < mem:
                        index = i + 1
                    else:
                        index = i
                else:
                    index = i

                memory = mem

            else:
                # Find the next free index and memory
                if self.seq.index == 1:
                    index = self.app.sequence.steps[-2].index + 1
                    memory = float(self.app.sequence.steps[-2].cue.memory) + 1
                else:
                    index = self.seq.steps[-1].index + 1
                    memory = float(self.seq.steps[-1].cue.memory) + 1

            channels = array.array('B', [0] * MAX_CHANNELS)
            for channel in range(MAX_CHANNELS):
                channels[channel] = self.channels[channel].level

            cue = Cue(index, str(memory), channels)

            # Insert Step
            self.seq.steps.insert(index, cue)
            self.seq.last += 1

            ### Update Display

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + '*')

            # Update Main Playback
            if self.seq.index == 1:

                if self.seq.steps[index].wait.is_integer():
                    wait = str(int(self.seq.steps[index].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.steps[index].wait)
                if self.seq.steps[index].time_out.is_integer():
                    t_out = str(int(self.seq.steps[index].time_out))
                else:
                    t_out = str(self.seq.steps[index].time_out)
                if self.seq.steps[index].delay_out.is_integer():
                    d_out = str(int(self.seq.steps[index].delay_out))
                    if d_out == '0':
                        d_out = ''
                else:
                    d_out = str(self.seq.steps[index].delay_out)
                if self.seq.steps[index].time_in.is_integer():
                    t_in = str(int(self.seq.steps[index].time_in))
                else:
                    t_in = str(self.seq.steps[index].time_in)
                if self.seq.steps[index].delay_in.is_integer():
                    d_in = str(int(self.seq.steps[index].delay_in))
                    if d_in == '0':
                        d_in = ''
                else:
                    d_in = str(self.seq.steps[index].delay_in)
                channel_time = str(len(self.seq.steps[index].channel_time))
                if channel_time == "0":
                    channel_time = ""

                self.liststore2.insert(index - 1, [str(index), str(self.seq.steps[index].cue.memory),
                    self.seq.steps[index].text, wait, d_out, t_out, d_in, t_in, channel_time])

                # Update indexes of cues in listsore
                for i in range(index, self.seq.last - 2):
                    self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)

                # Select new step
                path = Gtk.TreePath.new_from_indices([index - 1])
                self.treeview2.set_cursor(path, None, False)

                # Update Main Playback

                bg = "#232729"

                if self.seq.steps[index].wait.is_integer():
                    wait = str(int(self.seq.steps[index].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.steps[index].wait)
                if self.seq.steps[index].time_out.is_integer():
                    t_out = str(int(self.seq.steps[index].time_out))
                else:
                    t_out = str(self.seq.steps[index].time_out)
                if self.seq.steps[index].delay_out.is_integer():
                    d_out = str(int(self.seq.steps[index].delay_out))
                    if d_out == '0':
                        d_out = ''
                else:
                    d_out = str(self.seq.steps[index].delay_out)
                if self.seq.steps[index].time_in.is_integer():
                    t_in = str(int(self.seq.steps[index].time_in))
                else:
                    t_in = str(self.seq.steps[index].time_in)
                if self.seq.steps[index].delay_in.is_integer():
                    d_in = str(int(self.seq.steps[index].delay_in))
                    if d_in == '0':
                        d_in = ''
                else:
                    d_in = str(self.seq.steps[index].delay_in)
                channel_time = str(len(self.seq.steps[index].channel_time))
                if channel_time == "0":
                    channel_time = ""

                self.app.window.cues_liststore1.insert(index, [str(index), str(self.seq.steps[index].cue.memory),
                    self.seq.steps[index].text, wait, d_out, t_out, d_in, t_in, channel_time,
                    bg, Pango.Weight.NORMAL, 42])
                self.app.window.cues_liststore2.insert(index, [str(index), str(self.seq.steps[index].cue.memory),
                    self.seq.steps[index].text, wait, d_out, t_out, d_in, t_in, channel_time])

                # Update indexes of cues in listsore
                for i in range(index + 1, self.seq.last):
                    self.app.window.cues_liststore1[i][0] = str(int(self.app.window.cues_liststore1[i][0]) + 1)
                    self.app.window.cues_liststore2[i][0] = str(int(self.app.window.cues_liststore2[i][0]) + 1)

                # Update Crossfade
                if self.app.sequence.position + 1 == index:
                    self.app.window.sequential.time_in = self.seq.steps[index].time_in
                    self.app.window.sequential.time_out = self.seq.steps[index].time_out
                    self.app.window.sequential.wait = self.seq.steps[index].wait
                    self.app.window.sequential.total_time = self.seq.steps[index].total_time
                    self.app.window.sequential.queue_draw()

            else:
                # Update Chasers

                if self.seq.steps[index].wait.is_integer():
                    wait = str(int(self.seq.steps[index].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.seq.steps[index].wait)
                if self.seq.steps[index].time_out.is_integer():
                    t_out = str(int(self.seq.steps[index].time_out))
                else:
                    t_out = str(self.seq.steps[index].time_out)
                if self.seq.steps[index].time_in.is_integer():
                    t_in = str(int(self.seq.steps[index].time_in))
                else:
                    t_in = str(self.seq.steps[index].time_in)
                channel_time = str(len(self.seq.steps[index].channel_time))
                if channel_time == "0":
                    channel_time = ""

                self.liststore2.insert(index - 1, [str(index), str(self.seq.steps[index].cue.memory),
                    self.seq.steps[index].text, wait, t_out, t_in, channel_time])

                # Update indexes of cues in listsore
                for i in range(index, self.seq.last - 1):
                    self.liststore2[i][0] = str(int(self.liststore2[i][0]) + 1)

                # Select new step
                path = Gtk.TreePath.new_from_indices([index - 1])
                self.treeview2.set_cursor(path, None, False)

            # Reset user modifications
            self.user_channels = array.array('h', [-1] * MAX_CHANNELS)

class Dialog(Gtk.Dialog):

    def __init__(self, parent, memory):
        Gtk.Dialog.__init__(self, "Confirmation", parent, 0,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                 Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_default_size(150,100)

        label = Gtk.Label("Update memory " + memory + " ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()
