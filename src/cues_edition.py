import array
from gi.repository import Gtk, Gdk, Pango

from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget
from olc.cue import Cue


class CuesEditionTab(Gtk.Paned):
    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""

        # Channels modified by user
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        # Channels used in selected Cue
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox.add(self.channels[i])

        self.scrolled.add(self.flowbox)

        self.add(self.scrolled)

        # List of Cues
        self.liststore = Gtk.ListStore(str, str, int)

        for mem in App().memories:
            channels = 0
            for chan in range(MAX_CHANNELS):
                if mem.channels[chan]:
                    channels += 1
            self.liststore.append([str(mem.memory), mem.text, channels])

        self.filter = self.liststore.filter_new()
        self.filter.set_visible_func(self.filter_cue_func)

        self.treeview = Gtk.TreeView(model=self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_cue_changed)

        for i, column_title in enumerate(["Memory", "Text", "Channels"]):
            renderer = Gtk.CellRendererText()

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)

            self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

        self.flowbox.set_filter_func(self.filter_channel_func, None)

        # Select first Memory
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

    def filter_channel_func(self, child, _user_data):
        """ Filter channels """
        # If no Presets, just return
        if not App().memories:
            return False
        # Find selected row
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Index of Channel
            i = child.get_index()

            # Cue's channels
            channels = App().memories[row].channels

            if channels[i] or self.channels[i].clicked:
                if self.user_channels[i] == -1:
                    self.channels[i].level = channels[i]
                    self.channels[i].next_level = channels[i]
                else:
                    self.channels[i].level = self.user_channels[i]
                    self.channels[i].next_level = self.user_channels[i]
                return child
            if self.user_channels[i] == -1:
                self.channels[i].level = 0
                self.channels[i].next_level = 0
                return False
            self.channels[i].level = self.user_channels[i]
            self.channels[i].next_level = self.user_channels[i]
            return child
        return False

    def filter_cue_func(self, _model, _i, _data):
        return True

    def on_cue_changed(self, _treeview):
        """ Selected Cue """
        self.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, _widget):
        """ Close Tab on close clicked """
        page = App().window.notebook.page_num(App().memories_tab)
        App().window.notebook.remove_page(page)
        App().memories_tab = None

    def on_scroll(self, _widget, event):
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if (
            event.state & accel_mask
            == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        ):
            (scroll, direction) = event.get_scroll_direction()
            if scroll and direction == Gdk.ScrollDirection.UP:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale <= 2:
                        self.channels[i].scale += 0.1
                self.flowbox.queue_draw()
            if scroll and direction == Gdk.ScrollDirection.DOWN:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale >= 1.1:
                        self.channels[i].scale -= 0.1
                self.flowbox.queue_draw()
            # TODO: Fix widgets dimensions
            if self.channels[0].scale > 1:
                self.flowbox.set_homogeneous(False)
            else:
                self.flowbox.set_homogeneous(True)

    def on_key_press_event(self, _widget, event):

        keyname = Gdk.keyval_name(event.keyval)

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

        if keyname == "period":
            self.keystring += "."
            App().window.statusbar.push(App().window.context_id, self.keystring)

        func = getattr(self, "keypress_" + keyname, None)
        if func:
            return func()
        return False

    def keypress_Escape(self):
        """ Close Tab """
        page = App().window.notebook.get_current_page()
        App().window.notebook.remove_page(page)
        App().memories_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_c(self):
        """ Channel """

        self.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:

                # Only patched channel
                if App().patch.channels[channel][0] != [0, 0]:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring
        else:
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
            self.flowbox.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        selected_children = self.flowbox.get_selected_children()
        if len(selected_children) == 1:
            flowboxchild = selected_children[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if 0 < to_chan < MAX_CHANNELS:
                if to_chan > int(self.last_chan_selected):
                    for channel in range(int(self.last_chan_selected) - 1, to_chan):
                        # Only patched channels
                        if App().patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            App().window.set_focus(child)
                            self.flowbox.select_child(child)
                else:
                    for channel in range(to_chan - 1, int(self.last_chan_selected)):
                        # Only patched channels
                        if App().patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            App().window.set_focus(child)
                            self.flowbox.select_child(child)
                self.flowbox.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_plus(self):
        """ Channel + """

        if self.keystring != "":

            channel = int(self.keystring) - 1

            if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
                0,
                0,
            ]:
                self.channels[channel].clicked = True
                self.flowbox.invalidate_filter()

                child = self.flowbox.get_child_at_index(channel)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = self.keystring

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_minus(self):
        """ Channel - """

        if self.keystring != "":

            channel = int(self.keystring) - 1

            if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
                0,
                0,
            ]:
                self.channels[channel].clicked = False
                self.flowbox.invalidate_filter()

                child = self.flowbox.get_child_at_index(channel)
                App().window.set_focus(child)
                self.flowbox.unselect_child(child)
                self.last_chan_selected = self.keystring

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_a(self):
        """ All Channels """

        self.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Memory's channels
            channels = App().memories[row].channels

            # Select channels with a level
            for chan in range(MAX_CHANNELS):
                if (
                    channels[chan] and self.user_channels[chan] != 0
                ) or self.user_channels[chan] > 0:
                    self.channels[chan].clicked = True
                    child = self.flowbox.get_child_at_index(chan)
                    App().window.set_focus(child)
                    self.flowbox.select_child(child)
                else:
                    self.channels[chan].clicked = False
            self.flowbox.invalidate_filter()

    def keypress_equal(self):
        """ @ level """

        level = int(self.keystring)

        if App().settings.get_boolean("percent"):
            if 0 <= level <= 100:
                level = int(round((level / 100) * 255))
            else:
                level = -1

        if 0 <= level < 256:

            selected_children = self.flowbox.get_selected_children()

            for flowboxchild in selected_children:
                child = flowboxchild.get_children()

                for channelwidget in child:
                    channel = int(channelwidget.channel) - 1

                    self.channels[channel].level = level
                    self.channels[channel].next_level = level
                    self.channels[channel].queue_draw()
                    self.user_channels[channel] = level

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_colon(self):
        """ Level - % """

        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")

        if percent:
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
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

        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")

        if percent:
            lvl = round((lvl / 100) * 255)

        selected_children = self.flowbox.get_selected_children()

        for flowboxchild in selected_children:
            child = flowboxchild.get_children()

            for channelwidget in child:
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
        """ Update Memory """

        self.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Memory's channels
            channels = App().memories[row].channels

            # Update levels and count channels
            nb_chan = 0
            for chan in range(MAX_CHANNELS):
                channels[chan] = self.channels[chan].level
                if channels[chan] != 0:
                    App().sequence.channels[chan] = 1
                    nb_chan += 1

            # Update Display
            treeiter = self.liststore.get_iter(row)
            self.liststore.set_value(treeiter, 2, nb_chan)

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

    def keypress_Delete(self):
        """ Deletes selected Memory """

        # TODO: Ask confirmation

        self.flowbox.unselect_all()

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Find Steps using selected memory
            steps = []
            for i, _ in enumerate(App().sequence.steps):
                if App().sequence.steps[i].cue.memory == App().memories[row].memory:
                    steps.append(i)

            # Delete Steps
            for step in steps:
                App().sequence.steps.pop(step)
                App().sequence.last -= 1

            # Delete memory from the Memories List
            App().memories.pop(row)

            # Remove it from the ListStore
            treeiter = self.liststore.get_iter(path)
            self.liststore.remove(treeiter)

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

            # Update Main Playback
            App().window.cues_liststore1.clear()
            App().window.cues_liststore2.clear()
            App().window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
            )
            App().window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )
            for i, step in enumerate(App().sequence.steps):
                # Display int as int
                if step.wait.is_integer():
                    wait = str(int(step.wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(step.wait)
                if step.time_out.is_integer():
                    t_out = int(step.time_out)
                else:
                    t_out = step.time_out
                if step.delay_out.is_integer():
                    d_out = str(int(step.delay_out))
                else:
                    d_out = str(step.delay_out)
                if d_out == "0":
                    d_out = ""
                if step.time_in.is_integer():
                    t_in = int(step.time_in)
                else:
                    t_in = step.time_in
                if step.delay_in.is_integer():
                    d_in = str(int(step.delay_in))
                else:
                    d_in = str(step.delay_in)
                if d_in == "0":
                    d_in = ""
                channel_time = str(len(step.channel_time))
                if channel_time == "0":
                    channel_time = ""
                if i == 0:
                    background = "#997004"
                elif i == 1:
                    background = "#555555"
                else:
                    background = "#232729"
                # Actual and Next Cue in Bold
                if i in (0, 1):
                    weight = Pango.Weight.HEAVY
                else:
                    weight = Pango.Weight.NORMAL
                if i == 0:
                    App().window.cues_liststore1.append(
                        [
                            str(i),
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            background,
                            Pango.Weight.NORMAL,
                            99,
                        ]
                    )
                    App().window.cues_liststore2.append(
                        [str(i), "", "", "", "", "", "", "", ""]
                    )
                else:
                    App().window.cues_liststore1.append(
                        [
                            str(i),
                            str(step.cue.memory),
                            str(step.text),
                            wait,
                            d_out,
                            str(t_out),
                            d_in,
                            str(t_in),
                            channel_time,
                            background,
                            weight,
                            99,
                        ]
                    )
                    App().window.cues_liststore2.append(
                        [
                            str(i),
                            str(step.cue.memory),
                            str(step.text),
                            wait,
                            d_out,
                            str(t_out),
                            d_in,
                            str(t_in),
                            channel_time,
                        ]
                    )

            position = App().sequence.position
            App().window.cues_liststore1[position][9] = "#232729"
            App().window.cues_liststore1[position + 1][9] = "#232729"
            App().window.cues_liststore1[position + 2][9] = "#997004"
            App().window.cues_liststore1[position + 3][9] = "#555555"
            App().window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            App().window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            App().window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            App().window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY

            App().window.step_filter1.refilter()
            App().window.step_filter2.refilter()

            # Update Sequence Edition Tab if exist
            if App().sequences_tab:
                App().sequences_tab.liststore1.clear()

                App().sequences_tab.liststore1.append(
                    [
                        App().sequence.index,
                        App().sequence.type_seq,
                        App().sequence.text,
                    ]
                )

                for chaser in App().chasers:
                    App().sequences_tab.liststore1.append(
                        [chaser.index, chaser.type_seq, chaser.text]
                    )

                App().sequences_tab.treeview1.set_model(App().sequences_tab.liststore1)
                pth = Gtk.TreePath.new()
                App().window.treeview1.set_cursor(pth, None, False)

    def keypress_R(self):
        """ Records a copy of the current Memory with a new number """

        if self.keystring != "":
            mem = float(self.keystring)
        else:
            return False

        # Memory already exist ?
        for i, _ in enumerate(App().memories):
            if App().memories[i].memory == mem:
                # Find selected memory
                path, _focus_column = self.treeview.get_cursor()
                if path:
                    row = path.get_indices()[0]
                    # Copy channels
                    App().memories[i].channels = App().memories[row].channels
                    # Count channels
                    nb_chan = 0
                    for chan in range(MAX_CHANNELS):
                        if App().memories[i].channels[chan]:
                            nb_chan += 1
                    # Update Display
                    treeiter = self.liststore.get_iter(i)
                    self.liststore.set_value(treeiter, 2, nb_chan)
                    print(i, App().sequence.position)
                    if i == App().sequence.position:
                        for channel in range(MAX_CHANNELS):
                            App().window.channels[channel].next_level = App().memories[i].channels[channel]
                            App().window.channels[channel].queue_draw()

                    # Tag filename as modified
                    App().ascii.modified = True
                    App().window.header.set_title(App().ascii.basename + "*")

                self.keystring = ""
                App().window.statusbar.push(App().window.context_id, self.keystring)

                return True

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            sequence = App().memories[row].sequence
            # memory = App().memories[row].memory
            channels = App().memories[row].channels
            # text = App().memories[row].text

            cue = Cue(sequence, mem, channels)

            # Insert Memory
            for i, _ in enumerate(App().memories):
                if App().memories[i].memory > mem:
                    break
            if i:
                App().memories.insert(i, cue)
                nb_chan = 0
                for chan in range(MAX_CHANNELS):
                    if channels[chan]:
                        nb_chan += 1
                self.liststore.insert(i, [str(mem), "", nb_chan])

                # Tag filename as modified
                App().ascii.modified = True
                App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

        return True

    def keypress_Insert(self):
        """ Insert a new Memory """

        if self.keystring == "":
            # Insert memory with the next free number
            mem = False
            # Find Next free number
            if len(App().memories) > 1:
                for i, _ in enumerate(App().memories[:-1]):
                    if (
                        int(App().memories[i + 1].memory)
                        - int(App().memories[i].memory)
                        > 1
                    ):
                        mem = App().memories[i].memory + 1
                        break
            elif len(App().memories) == 1:
                # Just one memory
                mem = App().memories[0].memory + 1
                i = 1
            else:
                # The list is empty
                i = 0
                mem = 1.0

            # Free number is at the end
            if not mem:
                mem = App().memories[-1].memory + 1
                i += 1

            # Find selected memory for channels levels
            path, _focus_column = self.treeview.get_cursor()
            if path:
                row = path.get_indices()[0]
                channels = App().memories[row].channels
            else:
                channels = array.array("B", [0] * MAX_CHANNELS)

            # Create new memory
            cue = Cue(0, mem, channels)
            App().memories.insert(i + 1, cue)
            nb_chan = 0
            for chan in range(MAX_CHANNELS):
                if channels[chan]:
                    nb_chan += 1
            self.liststore.insert(i + 1, [str(mem), "", nb_chan])

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

            return True

        # Insert memory with the given number
        mem = float(self.keystring)

        # Memory already exist ?
        for item in App().memories:
            if item.memory == mem:
                return False

        # Find selected memory
        path, _focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            sequence = App().memories[row].sequence
            # memory = App().memories[row].memory
            channels = App().memories[row].channels
            # text = App().memories[row].text
        else:
            sequence = 0
            channels = array.array("B", [0] * MAX_CHANNELS)

        # Find Memory's position
        found = False
        i = 0
        for i, _ in enumerate(App().memories):
            if App().memories[i].memory > mem:
                found = True
                break
        if not found:
            # Memory is at the end
            i += 1

        # Create Memory
        cue = Cue(sequence, mem, channels)
        App().memories.insert(i, cue)

        # Update display
        nb_chan = 0
        for chan in range(MAX_CHANNELS):
            if channels[chan]:
                nb_chan += 1
        self.liststore.insert(i, [str(mem), "", nb_chan])

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

        return True
