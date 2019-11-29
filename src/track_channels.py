from gi.repository import Gtk, Gio, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_track_channels import TrackChannelsHeader, TrackChannelsWidget

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
            memory = self.app.sequence.steps[step].cue.memory
            text = self.app.sequence.steps[step].text
            levels.append([])
            for channel in range(len(self.channels)):
                level = self.app.sequence.steps[step].cue.channels[self.channels[channel]]
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
        #print(keyname)

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
                    self.app.sequence.steps[step].cue.channels[channel] = level
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
                level = self.app.sequence.steps[step].cue.channels[self.channels[channel]]
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
                    level = self.app.sequence.steps[step].cue.channels[self.channels[channel]]
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
                    level = self.app.sequence.steps[step].cue.channels[self.channels[channel]]
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
                    level = self.app.sequence.steps[step].cue.channels[self.channels[channel]]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ''
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
