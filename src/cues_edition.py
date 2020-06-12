import array
from gi.repository import Gtk, Gio, Gdk, Pango

from olc.define import MAX_CHANNELS
from olc.widgets_channel import ChannelWidget
from olc.cue import Cue


class CuesEditionTab(Gtk.Paned):
    def __init__(self):

        self.app = Gio.Application.get_default()

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

        for mem in self.app.memories:
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

    def filter_channel_func(self, child, user_data):
        """ Filter channels """
        # Find selected row
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Index of Channel
            i = child.get_index()

            # Cue's channels
            channels = self.app.memories[row].channels

            if channels[i] or self.channels[i].clicked:
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
        else:
            return False

    def filter_cue_func(self, model, i, data):
        return True

    def on_cue_changed(self, treeview):
        """ Selected Cue """
        self.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.memories_tab)
        self.app.window.notebook.remove_page(page)
        self.app.memories_tab = None

    def on_scroll(self, widget, event):
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

    def on_key_press_event(self, widget, event):

        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

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
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == "period":
            self.keystring += "."
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, "keypress_" + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.memories_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Channel """

        self.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:

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
                        if self.app.patch.channels[channel][0] != [0, 0]:
                            self.channels[channel].clicked = True
                            child = self.flowbox.get_child_at_index(channel)
                            self.app.window.set_focus(child)
                            self.flowbox.select_child(child)
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

        if self.keystring != "":

            channel = int(self.keystring) - 1

            if 0 <= channel < MAX_CHANNELS and self.app.patch.channels[channel][0] != [
                0,
                0,
            ]:
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

        if self.keystring != "":

            channel = int(self.keystring) - 1

            if 0 <= channel < MAX_CHANNELS and self.app.patch.channels[channel][0] != [
                0,
                0,
            ]:
                self.channels[channel].clicked = False
                self.flowbox.invalidate_filter()

                child = self.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.flowbox.unselect_child(child)
                self.last_chan_selected = self.keystring

            self.keystring = ""
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_a(self):
        """ All Channels """

        self.flowbox.unselect_all()

        # Find selected memory
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Memory's channels
            channels = self.app.memories[row].channels

            # Select channels with a level
            for chan in range(MAX_CHANNELS):
                if (
                    channels[chan] and self.user_channels[chan] != 0
                ) or self.user_channels[chan] > 0:
                    self.channels[chan].clicked = True
                    child = self.flowbox.get_child_at_index(chan)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                else:
                    self.channels[chan].clicked = False
            self.flowbox.invalidate_filter()

    def keypress_equal(self):
        """ @ level """

        level = int(self.keystring)

        if self.app.settings.get_boolean("percent"):
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
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_colon(self):
        """ Level - % """

        lvl = self.app.settings.get_int("percent-level")
        percent = self.app.settings.get_boolean("percent")

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

        lvl = self.app.settings.get_int("percent-level")
        percent = self.app.settings.get_boolean("percent")

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
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Memory's channels
            channels = self.app.memories[row].channels

            # Update levels and count channels
            nb_chan = 0
            for chan in range(MAX_CHANNELS):
                channels[chan] = self.channels[chan].level
                if channels[chan] != 0:
                    self.app.sequence.channels[chan] = 1
                    nb_chan += 1

            # Update Display
            treeiter = self.liststore.get_iter(row)
            self.liststore.set_value(treeiter, 2, nb_chan)

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + "*")

    def keypress_Delete(self):
        """ Deletes selected Memory """

        # TODO: Ask confirmation

        self.flowbox.unselect_all()

        # Find selected memory
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Find Steps using selected memory
            steps = []
            for i, _ in enumerate(self.app.sequence.steps):
                if (
                    self.app.sequence.steps[i].cue.memory
                    == self.app.memories[row].memory
                ):
                    steps.append(i)

            # Delete Steps
            for step in steps:
                self.app.sequence.steps.pop(step)
                self.app.sequence.last -= 1

            # Delete memory from the Memories List
            self.app.memories.pop(row)

            # Remove it from the ListStore
            treeiter = self.liststore.get_iter(path)
            self.liststore.remove(treeiter)

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + "*")

            # Update Main Playback
            self.app.window.cues_liststore1.clear()
            self.app.window.cues_liststore2.clear()
            self.app.window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
            )
            self.app.window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )
            for i, step in enumerate(self.app.sequence.steps):
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
                    bg = "#997004"
                elif i == 1:
                    bg = "#555555"
                else:
                    bg = "#232729"
                # Actual and Next Cue in Bold
                if i in (0, 1):
                    weight = Pango.Weight.HEAVY
                else:
                    weight = Pango.Weight.NORMAL
                if i == 0:
                    self.app.window.cues_liststore1.append(
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
                            bg,
                            Pango.Weight.NORMAL,
                            99,
                        ]
                    )
                    self.app.window.cues_liststore2.append(
                        [str(i), "", "", "", "", "", "", "", ""]
                    )
                else:
                    self.app.window.cues_liststore1.append(
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
                            bg,
                            weight,
                            99,
                        ]
                    )
                    self.app.window.cues_liststore2.append(
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

            position = self.app.sequence.position
            self.app.window.cues_liststore1[position][9] = "#232729"
            self.app.window.cues_liststore1[position + 1][9] = "#232729"
            self.app.window.cues_liststore1[position + 2][9] = "#997004"
            self.app.window.cues_liststore1[position + 3][9] = "#555555"
            self.app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
            self.app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
            self.app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY

            self.app.window.step_filter1.refilter()
            self.app.window.step_filter2.refilter()

            # Update Sequence Edition Tab if exist
            if self.app.sequences_tab:
                self.app.sequences_tab.liststore1.clear()

                self.app.sequences_tab.liststore1.append(
                    [
                        self.app.sequence.index,
                        self.app.sequence.type_seq,
                        self.app.sequence.text,
                    ]
                )

                for chaser in self.app.chasers:
                    self.app.sequences_tab.liststore1.append(
                        [chaser.index, chaser.type_seq, chaser.text]
                    )

                self.app.sequences_tab.treeview1.set_model(
                    self.app.sequences_tab.liststore1
                )
                pth = Gtk.TreePath.new()
                self.app.window.treeview1.set_cursor(pth, None, False)

    def keypress_R(self):
        """ Records a copy of the current Memory with a new number """

        if self.keystring != "":
            mem = float(self.keystring)
        else:
            return False

        # Memory already exist ?
        for i, _ in enumerate(self.app.memories):
            if self.app.memories[i].memory == mem:
                # Find selected memory
                path, focus_column = self.treeview.get_cursor()
                if path:
                    row = path.get_indices()[0]
                    # Copy channels
                    self.app.memories[i].channels = self.app.memories[row].channels
                    # Count channels
                    nb_chan = 0
                    for chan in range(MAX_CHANNELS):
                        if self.app.memories[i].channels[chan]:
                            nb_chan += 1
                    # Update Display
                    treeiter = self.liststore.get_iter(i)
                    self.liststore.set_value(treeiter, 2, nb_chan)

                    # Tag filename as modified
                    self.app.ascii.modified = True
                    self.app.window.header.set_title(self.app.ascii.basename + "*")

                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )

                return

        # Find selected memory
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            sequence = self.app.memories[row].sequence
            # memory = self.app.memories[row].memory
            channels = self.app.memories[row].channels
            # text = self.app.memories[row].text

            cue = Cue(sequence, mem, channels)

            # Insert Memory
            for i, _ in enumerate(self.app.memories):
                if self.app.memories[i].memory > mem:
                    break
            if i:
                self.app.memories.insert(i, cue)
                nb_chan = 0
                for chan in range(MAX_CHANNELS):
                    if channels[chan]:
                        nb_chan += 1
                self.liststore.insert(i, [str(mem), "", nb_chan])

                # Tag filename as modified
                self.app.ascii.modified = True
                self.app.window.header.set_title(self.app.ascii.basename + "*")

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Insert(self):
        """ Insert a new Memory """

        if self.keystring == "":
            """ Insert memory with the next free number """
            mem = False
            # Find Next free number
            if len(self.app.memories) > 1:
                for i, _ in enumerate(self.app.memories[:-1]):
                    if (
                        int(self.app.memories[i + 1].memory)
                        - int(self.app.memories[i].memory)
                        > 1
                    ):
                        mem = self.app.memories[i].memory + 1
                        break
            elif len(self.app.memories) == 1:
                # Just one memory
                mem = self.app.memories[0].memory + 1
                i = 1
            else:
                # The list is empty
                i = 0
                mem = 1.0

            # Free number is at the end
            if not mem:
                mem = self.app.memories[-1].memory + 1
                i += 1

            # Find selected memory for channels levels
            path, focus_column = self.treeview.get_cursor()
            if path:
                row = path.get_indices()[0]
                channels = self.app.memories[row].channels
            else:
                channels = array.array("B", [0] * MAX_CHANNELS)

            # Create new memory
            cue = Cue(0, mem, channels)
            self.app.memories.insert(i + 1, cue)
            nb_chan = 0
            for chan in range(MAX_CHANNELS):
                if channels[chan]:
                    nb_chan += 1
            self.liststore.insert(i + 1, [str(mem), "", nb_chan])

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + "*")

        else:
            """ Insert memory with the given number """

            mem = float(self.keystring)

            # Memory already exist ?
            for item in self.app.memories:
                if item.memory == mem:
                    return False

            # Find selected memory
            path, focus_column = self.treeview.get_cursor()
            if path:
                row = path.get_indices()[0]

                sequence = self.app.memories[row].sequence
                # memory = self.app.memories[row].memory
                channels = self.app.memories[row].channels
                # text = self.app.memories[row].text
            else:
                sequence = 0
                channels = array.array("B", [0] * MAX_CHANNELS)

            # Find Memory's position
            found = False
            i = 0
            for i, _ in enumerate(self.app.memories):
                if self.app.memories[i].memory > mem:
                    found = True
                    break
            if not found:
                # Memory is at the end
                i += 1

            # Create Memory
            cue = Cue(sequence, mem, channels)
            self.app.memories.insert(i, cue)

            # Update display
            nb_chan = 0
            for chan in range(MAX_CHANNELS):
                if channels[chan]:
                    nb_chan += 1
            self.liststore.insert(i, [str(mem), "", nb_chan])

            # Tag filename as modified
            self.app.ascii.modified = True
            self.app.window.header.set_title(self.app.ascii.basename + "*")

            self.keystring = ""
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
