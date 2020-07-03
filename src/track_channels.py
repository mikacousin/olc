from gi.repository import Gtk, Gdk

from olc.define import MAX_CHANNELS, App
from olc.widgets_track_channels import TrackChannelsHeader, TrackChannelsWidget


class TrackChannelsTab(Gtk.Grid):
    def __init__(self):

        self.percent_level = App().settings.get_boolean("percent")

        self.keystring = ""
        self.last_step_selected = ""

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
        sel = App().window.flowbox.get_selected_children()
        for flowboxchild in sel:
            children = flowboxchild.get_children()
            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                if App().patch.channels[channel][0] != [0, 0]:
                    self.channels.append(channel)

        # Levels in each steps
        levels = []
        self.steps = []
        self.steps.append(TrackChannelsHeader(self.channels))
        levels.append([])
        self.flowbox.add(self.steps[0])
        for step in range(1, App().sequence.last):
            memory = App().sequence.steps[step].cue.memory
            text = App().sequence.steps[step].text
            levels.append([])
            for channel in self.channels:
                level = App().sequence.steps[step].cue.channels[channel]
                levels[step].append(level)
            self.steps.append(TrackChannelsWidget(step, memory, text, levels[step]))
            self.flowbox.add(self.steps[step])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.attach(self.scrollable, 0, 0, 1, 1)

    def filter_func(self, child, _user_data):
        if child == self.steps[0].get_parent():
            return child
        if len(self.steps) <= App().sequence.last - 1:
            return False
        if child == self.steps[App().sequence.last - 1].get_parent():
            return False
        return child

    def on_close_icon(self, _widget):
        """ Close Tab on close clicked """
        page = App().window.notebook.page_num(App().track_channels_tab)
        App().window.notebook.remove_page(page)
        App().track_channels_tab = None

    def on_key_press_event(self, _widget, event):

        keyname = Gdk.keyval_name(event.keyval)
        # print(keyname)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            App().window.statusbar.push(App().window.context_id, self.keystring)

        if keyname in (
            "KP_1",
            "KP_2",
            "KP_3",
            "KP_4",
            "KP_5",
            "KP_6",
            "KP_7",
            "KP_8",
            "KP_9",
            "KP_0",
        ):
            self.keystring += keyname[3:]
            App().window.statusbar.push(App().window.context_id, self.keystring)

        func = getattr(self, "keypress_" + keyname, None)
        if func:
            return func()
        return False

    def keypress_Escape(self):
        """ Close Tab """
        page = App().window.notebook.get_current_page()
        App().window.notebook.remove_page(page)
        App().track_channels_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_Right(self):
        """ Next Channel """

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
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

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
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

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        elif int(self.last_step_selected) < App().sequence.last - 2:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) + 1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            index = child.get_index()
            self.last_step_selected = str(index)

    def keypress_Up(self):
        """ Previous Step """

        if self.last_step_selected == "":
            child = self.flowbox.get_child_at_index(1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_step_selected = "1"
        elif int(self.last_step_selected) > 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_step_selected) - 1)
            App().window.set_focus(child)
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

                if App().settings.get_boolean("percent"):
                    if 0 <= level <= 100:
                        level = int(round((level / 100) * 255))
                    else:
                        level = -1

                if 0 <= level <= 255:
                    App().sequence.steps[step].cue.channels[channel] = level
                    widget.levels[self.channel_selected] = level
                    widget.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_c(self):
        """ Select Channel """

        App().window.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = App().window.flowbox.get_child_at_index(channel)
                App().window.set_focus(child)
                App().window.flowbox.select_child(child)
                App().window.last_chan_selected = str(channel)

        # Find selected channels
        self.channels = []
        sel = App().window.flowbox.get_selected_children()
        for flowboxchild in sel:
            children = flowboxchild.get_children()
            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                if App().patch.channels[channel][0] != [0, 0]:
                    self.channels.append(channel)

        self.channel_selected = 0

        # Update Track Channels Tab
        self.steps[0].channels = self.channels

        levels = []
        for step in range(App().sequence.last):
            levels.append([])
            for channel in self.channels:
                level = App().sequence.steps[step].cue.channels[channel]
                levels[step].append(level)
            self.steps[step].levels = levels[step]
        self.flowbox.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        sel = App().window.flowbox.get_selected_children()

        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            App().window.last_chan_selected = channelwidget.channel

        if not App().window.last_chan_selected:
            sel = App().window.flowbox.get_selected_children()
            if len(sel) > 0:
                for flowboxchild in sel:
                    children = flowboxchild.get_children()
                    for channelwidget in children:
                        channel = int(channelwidget.channel)
                App().window.last_chan_selected = str(channel)

        if App().window.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(App().window.last_chan_selected):
                for channel in range(int(App().window.last_chan_selected) - 1, to_chan):
                    child = App().window.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    App().window.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(App().window.last_chan_selected)):
                    child = App().window.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    App().window.flowbox.select_child(child)

            App().window.last_chan_selected = self.keystring

            # Find selected channels
            self.channels = []
            sel = App().window.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels.append(channel)

            if self.channel_selected > len(self.channels) - 1:
                self.channel_selected = 0

            # Update Track Channels Tab
            self.steps[0].channels = self.channels

            levels = []
            for step in range(App().sequence.last):
                levels.append([])
                for channel in self.channels:
                    level = App().sequence.steps[step].cue.channels[channel]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_KP_Add(self):
        self.keypress_plus()

    def keypress_plus(self):
        """ Channel + """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS:
            child = App().window.flowbox.get_child_at_index(channel)
            App().window.set_focus(child)
            App().window.flowbox.select_child(child)
            App().window.last_chan_selected = self.keystring

            # Find selected channels
            self.channels = []
            sel = App().window.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels.append(channel)

            if self.channel_selected > len(self.channels) - 1:
                self.channel_selected = 0

            # Update Track Channels Tab
            self.steps[0].channels = self.channels

            levels = []
            for step in range(App().sequence.last):
                levels.append([])
                for channel in self.channels:
                    level = App().sequence.steps[step].cue.channels[channel]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_KP_Subtract(self):
        self.keypress_minus()

    def keypress_minus(self):
        """ Channel - """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS:
            child = App().window.flowbox.get_child_at_index(channel)
            App().window.set_focus(child)
            App().window.flowbox.unselect_child(child)
            App().window.last_chan_selected = self.keystring

            # Find selected channels
            self.channels = []
            sel = App().window.flowbox.get_selected_children()
            for flowboxchild in sel:
                children = flowboxchild.get_children()
                for channelwidget in children:
                    channel = int(channelwidget.channel) - 1
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels.append(channel)

            if self.channel_selected > len(self.channels) - 1:
                self.channel_selected = 0

            # Update Track Channels Tab
            self.steps[0].channels = self.channels

            levels = []
            for step in range(App().sequence.last):
                levels.append([])
                for channel in self.channels:
                    level = App().sequence.steps[step].cue.channels[channel]
                    levels[step].append(level)
                self.steps[step].levels = levels[step]
            self.flowbox.queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
