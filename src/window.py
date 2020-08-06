"""Open Lighting Console's Main window"""

import array
from gi.repository import Gio, Gtk, Gdk, GLib, Pango

from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.cue import Cue
from olc.step import Step
from olc.widgets_sequential import SequentialWidget
from olc.widgets_channel import ChannelWidget
from olc.widgets_grand_master import GMWidget


class Window(Gtk.ApplicationWindow):
    """Main Window"""

    def __init__(self, patch):

        self.patch = patch

        # 0 : patched channels
        # 1 : all channels
        self.view_type = 0

        self.percent_level = App().settings.get_boolean("percent")

        Gtk.ApplicationWindow.__init__(
            self, title="Open Lighting Console", application=App()
        )
        self.set_default_size(1400, 1200)
        self.set_name("olc")

        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("Fonctionne avec ola")
        self.header.props.show_close_button = True

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Gtk.StyleContext.add_class(box.get_style_context(), "linked")
        self.grand_master = GMWidget()
        box.add(self.grand_master)
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
        popover = Gtk.Popover.new_from_model(button, App().setup_app_menu())
        button.set_popover(popover)
        self.header.pack_end(box)

        self.set_titlebar(self.header)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(950)
        # self.paned.set_wide_handle(True)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        # self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_func, None)

        self.keystring = ""
        self.last_chan_selected = ""

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
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

        self.seq = App().sequence

        # Sequential part of the window

        # Model : Step, Memory, Text, Wait, Time Out, Time In, Channel Time
        self.cues_liststore1 = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str, str, int, int
        )
        self.cues_liststore2 = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str
        )

        if self.seq.last > 1:
            position = self.seq.position
            t_total = self.seq.steps[position].total_time
            t_in = self.seq.steps[position].time_in
            t_out = self.seq.steps[position].time_out
            d_in = self.seq.steps[position].delay_in
            d_out = self.seq.steps[position].delay_out
            t_wait = self.seq.steps[position].wait
            channel_time = self.seq.steps[position].channel_time
        else:
            position = 0
            t_total = 5.0
            t_in = 5.0
            t_out = 5.0
            d_in = 0.0
            d_out = 0.0
            t_wait = 0.0
            channel_time = {}

        # Crossfade widget
        self.sequential = SequentialWidget(
            t_total, t_in, t_out, d_in, d_out, t_wait, channel_time
        )

        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
        )
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
        )

        for i in range(App().sequence.last):
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
            else:
                d_out = str(self.seq.steps[i].delay_out)
            if self.seq.steps[i].time_in.is_integer():
                t_in = str(int(self.seq.steps[i].time_in))
            else:
                t_in = str(self.seq.steps[i].time_in)
            if self.seq.steps[i].delay_in.is_integer():
                d_in = str(int(self.seq.steps[i].delay_in))
            else:
                d_in = str(self.seq.steps[i].delay_in)
            channel_time = str(len(self.seq.steps[i].channel_time))
            if channel_time == "0":
                channel_time = ""
            background = "#232729"
            if i in (0, App().sequence.last - 1):
                self.cues_liststore1.append(
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
                        42,
                    ]
                )
            else:
                self.cues_liststore1.append(
                    [
                        str(i),
                        str(self.seq.steps[i].cue.memory),
                        self.seq.steps[i].text,
                        wait,
                        d_out,
                        t_out,
                        d_in,
                        t_in,
                        channel_time,
                        background,
                        Pango.Weight.NORMAL,
                        42,
                    ]
                )
            self.cues_liststore2.append(
                [
                    str(i),
                    str(self.seq.steps[i].cue.memory),
                    self.seq.steps[i].text,
                    wait,
                    d_out,
                    t_out,
                    d_in,
                    t_in,
                    channel_time,
                ]
            )

        if App().sequence.last == 1:
            self.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )

        # Filter for the first part of the cue list
        self.step_filter1 = self.cues_liststore1.filter_new()
        self.step_filter1.set_visible_func(self.step_filter_func1)
        # List
        self.treeview1 = Gtk.TreeView(model=self.step_filter1)
        self.treeview1.set_enable_search(False)
        sel = self.treeview1.get_selection()
        sel.set_mode(Gtk.SelectionMode.NONE)
        for i, column_title in enumerate(
            [
                "Pas",
                "Mémoire",
                "Texte",
                "Wait",
                "Delay Out",
                "Out",
                "Delay In",
                "In",
                "Channel Time",
            ]
        ):
            renderer = Gtk.CellRendererText()
            # Change background color one column out of two
            if i % 2 == 0:
                renderer.set_property("background-rgba", Gdk.RGBA(alpha=0.03))
            column = Gtk.TreeViewColumn(
                column_title, renderer, text=i, background=9, weight=10
            )
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
        for i, column_title in enumerate(
            [
                "Step",
                "Cue",
                "Text",
                "Wait",
                "Delay Out",
                "Out",
                "Delay In",
                "In",
                "Channel Time",
            ]
        ):
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
        self.scrollable2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
        self.scrollable2.add(self.treeview2)
        # Put Cues lists and sequential in a grid
        self.seq_grid = Gtk.Grid()
        self.seq_grid.set_row_homogeneous(False)
        self.seq_grid.attach(self.treeview1, 0, 0, 1, 1)
        self.seq_grid.attach_next_to(
            self.sequential, self.treeview1, Gtk.PositionType.BOTTOM, 1, 1
        )
        self.seq_grid.attach_next_to(
            self.scrollable2, self.sequential, Gtk.PositionType.BOTTOM, 1, 1
        )

        # Sequential in a Tab
        self.notebook = Gtk.Notebook()

        self.notebook.append_page(self.seq_grid, Gtk.Label("Main Playback"))

        self.paned2.add2(self.notebook)

        self.add(self.paned2)

        # Select first Cue
        self.cues_liststore1[2][9] = "#997004"
        self.cues_liststore1[2][10] = Pango.Weight.HEAVY
        # Bold next Cue
        self.cues_liststore1[3][10] = Pango.Weight.HEAVY
        self.cues_liststore1[3][9] = "#555555"

        # Scan Ola messages - 27 = IN(1) + HUP(16) + PRI(2) + ERR(8)
        GLib.unix_fd_add_full(
            0,
            App().ola_thread.sock.fileno(),
            GLib.IOCondition(27),
            App().on_fd_read,
            None,
        )

        self.connect("key_press_event", self.on_key_press_event)
        self.connect("scroll-event", self.on_scroll)

        self.set_icon_name("olc")

    def step_filter_func1(self, model, treeiter, _data):
        """Filter for the first part of the cues list"""
        if App().sequence.position <= 0:
            if int(model[treeiter][11]) == 0 or int(model[treeiter][11]) == 1:
                return True
            if int(model[treeiter][0]) == 0 or int(model[treeiter][0]) == 1:
                return True
            return False

        if App().sequence.position == 1:
            if int(model[treeiter][11]) == 1:
                return True
            if int(model[treeiter][11]) == 0:
                return False
            if (
                int(model[treeiter][0]) == 0
                or int(model[treeiter][0]) == 1
                or int(model[treeiter][0]) == 2
            ):
                return True
            return False

        if int(model[treeiter][11]) == 1:
            return False
        if int(model[treeiter][11]) == 0:
            return False

        if (
            int(model[treeiter][0]) == App().sequence.position
            or int(model[treeiter][0]) == App().sequence.position + 1
            or int(model[treeiter][0]) == App().sequence.position - 1
            or int(model[treeiter][0]) == App().sequence.position - 2
        ):
            return True
        return False

    def step_filter_func2(self, model, treeiter, _data):
        """Filter for the second part of the cues list"""
        if int(model[treeiter][0]) <= App().sequence.position + 1:
            return False
        return True

    def filter_func(self, child, _user_data):
        """Filter for channels window"""
        if self.view_type == 0:
            i = child.get_index()
            for channel in App().patch.channels[i][0]:
                if channel != 0:
                    # print("Chanel:", i+1, "Output:", App().patch.channels[i][j])
                    return child
                return False
        else:
            return True

    def button_clicked_cb(self, button):
        """Toggle type of view : patched channels or all channels"""
        if self.view_type == 0:
            self.view_type = 1
        else:
            self.view_type = 0
        self.flowbox.invalidate_filter()

    def on_scroll(self, widget, event):
        """Executed on scroll wheel mouse event"""
        # Send Events to notebook's pages
        page = self.notebook.get_current_page()
        child = self.notebook.get_nth_page(page)

        if child == App().patch_outputs_tab:
            return App().patch_outputs_tab.on_scroll(widget, event)
        if child == App().memories_tab:
            return App().memories_tab.on_scroll(widget, event)

        # Zoom In/Out Channels in Live View
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if (
            event.state & accel_mask
            == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        ):
            (scroll, direction) = event.get_scroll_direction()
            if scroll and direction == Gdk.ScrollDirection.UP:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale < 2:
                        self.channels[i].scale += 0.1
            if scroll and direction == Gdk.ScrollDirection.DOWN:
                for i in range(MAX_CHANNELS):
                    if self.channels[i].scale >= 1.1:
                        self.channels[i].scale -= 0.1
        return True

    def update_sequence_display(self):
        """Update Sequence display"""
        self.cues_liststore1.clear()
        self.cues_liststore2.clear()
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
        )
        self.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
        )
        for i in range(App().sequence.last):
            if App().sequence.steps[i].wait.is_integer():
                wait = str(int(App().sequence.steps[i].wait))
                if wait == "0":
                    wait = ""
            else:
                wait = str(App().sequence.steps[i].wait)
            if App().sequence.steps[i].time_out.is_integer():
                t_out = int(App().sequence.steps[i].time_out)
            else:
                t_out = App().sequence.steps[i].time_out
            if App().sequence.steps[i].delay_out.is_integer():
                d_out = str(int(App().sequence.steps[i].delay_out))
            else:
                d_out = str(App().sequence.steps[i].delay_out)
            if d_out == "0":
                d_out = ""
            if App().sequence.steps[i].time_in.is_integer():
                t_in = int(App().sequence.steps[i].time_in)
            else:
                t_in = App().sequence.steps[i].time_in
            if App().sequence.steps[i].delay_in.is_integer():
                d_in = str(int(App().sequence.steps[i].delay_in))
            else:
                d_in = str(App().sequence.steps[i].delay_in)
            if d_in == "0":
                d_in = ""
            channel_time = str(len(App().sequence.steps[i].channel_time))
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
            if i in (0, App().sequence.last - 1):
                self.cues_liststore1.append(
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
                self.cues_liststore2.append([str(i), "", "", "", "", "", "", "", ""])
            else:
                self.cues_liststore1.append(
                    [
                        str(i),
                        str(App().sequence.steps[i].cue.memory),
                        str(App().sequence.steps[i].text),
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
                self.cues_liststore2.append(
                    [
                        str(i),
                        str(App().sequence.steps[i].cue.memory),
                        str(App().sequence.steps[i].text),
                        wait,
                        d_out,
                        str(t_out),
                        d_in,
                        str(t_in),
                        channel_time,
                    ]
                )

        self.cues_liststore1[App().sequence.position][9] = "#232729"
        self.cues_liststore1[App().sequence.position + 1][9] = "#232729"
        self.cues_liststore1[App().sequence.position + 2][9] = "#997004"
        self.cues_liststore1[App().sequence.position + 3][9] = "#555555"
        self.cues_liststore1[App().sequence.position][10] = Pango.Weight.NORMAL
        self.cues_liststore1[App().sequence.position + 1][10] = Pango.Weight.NORMAL
        self.cues_liststore1[App().sequence.position + 2][10] = Pango.Weight.HEAVY
        self.cues_liststore1[App().sequence.position + 3][10] = Pango.Weight.HEAVY

        self.step_filter1.refilter()
        self.step_filter2.refilter()

        path1 = Gtk.TreePath.new_from_indices([App().sequence.position + 2])
        path2 = Gtk.TreePath.new_from_indices([App().sequence.position])
        self.treeview1.set_cursor(path1, None, False)
        self.treeview2.set_cursor(path2, None, False)
        self.seq_grid.queue_draw()

    def update_xfade_display(self, step):
        """Update Crossfade display"""
        self.sequential.total_time = App().sequence.steps[step + 1].total_time
        self.sequential.time_in = App().sequence.steps[step + 1].time_in
        self.sequential.time_out = App().sequence.steps[step + 1].time_out
        self.sequential.delay_in = App().sequence.steps[step + 1].delay_in
        self.sequential.delay_out = App().sequence.steps[step + 1].delay_out
        self.sequential.wait = App().sequence.steps[step + 1].wait
        self.sequential.channel_time = App().sequence.steps[step + 1].channel_time
        self.sequential.queue_draw()

    def update_channels_display(self, step):
        """Update Channels levels display"""
        for channel in range(MAX_CHANNELS):
            level = App().sequence.steps[step].cue.channels[channel]
            next_level = App().sequence.steps[step + 1].cue.channels[channel]
            self.channels[channel].level = level
            self.channels[channel].next_level = next_level
            self.channels[channel].queue_draw()

    def on_key_press_event(self, widget, event):
        """Executed on key press event"""
        # Find open page in notebook to send keyboard events
        page = self.notebook.get_current_page()
        child = self.notebook.get_nth_page(page)
        if child == App().group_tab:
            return App().group_tab.on_key_press_event(widget, event)
        if child == App().patch_outputs_tab:
            return App().patch_outputs_tab.on_key_press_event(widget, event)
        if child == App().patch_channels_tab:
            return App().patch_channels_tab.on_key_press_event(widget, event)
        if child == App().sequences_tab:
            return App().sequences_tab.on_key_press_event(widget, event)
        if child == App().channeltime_tab:
            return App().channeltime_tab.on_key_press_event(widget, event)
        if child == App().track_channels_tab:
            return App().track_channels_tab.on_key_press_event(widget, event)
        if child == App().memories_tab:
            return App().memories_tab.on_key_press_event(widget, event)
        if child == App().masters_tab:
            return App().masters_tab.on_key_press_event(widget, event)

        keyname = Gdk.keyval_name(event.keyval)
        # print(keyname)
        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            self.statusbar.push(self.context_id, self.keystring)

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
            self.statusbar.push(self.context_id, self.keystring)

        if keyname == "period":
            self.keystring += "."
            self.statusbar.push(self.context_id, self.keystring)

        func = getattr(self, "keypress_" + keyname, None)

        if func:
            return func()
        return False

    def keypress_Right(self):
        """Next Channel"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        elif int(self.last_chan_selected) < MAX_CHANNELS - 1:
            # Find next patched channel
            next_chan = 0
            for i in range(int(self.last_chan_selected) + 1, MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    next_chan = i
                    break
            if next_chan:
                self.flowbox.unselect_all()
                child = self.flowbox.get_child_at_index(next_chan)
                self.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(next_chan)

    def keypress_Left(self):
        """Previous Channel"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        elif int(self.last_chan_selected) > 0:
            # Find previous patched channel
            chan = int(self.last_chan_selected)
            for i in range(int(self.last_chan_selected), 0, -1):
                if App().patch.channels[i - 1][0] != [0, 0]:
                    chan = i - 1
                    break
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(chan)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(chan)

    def keypress_Down(self):
        """Next Line"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        else:
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            )
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(index)

    def keypress_Up(self):
        """Previous Line"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        else:
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            )
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(index)

    def keypress_a(self):
        """All Channels"""
        self.flowbox.unselect_all()

        for universe in range(NB_UNIVERSES):
            for output in range(512):
                level = App().dmx.frame[universe][output]
                channel = App().patch.outputs[universe][output][0] - 1
                if level > 0:
                    child = self.flowbox.get_child_at_index(channel)
                    self.set_focus(child)
                    self.flowbox.select_child(child)

    def keypress_c(self):
        """Channel"""
        self.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = self.flowbox.get_child_at_index(channel)
                self.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Divide(self):
        """Thru"""
        self.keypress_greater()

    def keypress_greater(self):
        """Thru"""
        sel = self.flowbox.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if not self.last_chan_selected:
            sel = self.flowbox.get_selected_children()
            if len(sel) > 0:
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
        """ + """
        self.keypress_plus()

    def keypress_plus(self):
        """ + """
        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            child = self.flowbox.get_child_at_index(channel)
            self.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_KP_Subtract(self):
        """ - """
        self.keypress_minus()

    def keypress_minus(self):
        """ - """
        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            child = self.flowbox.get_child_at_index(channel)
            self.set_focus(child)
            self.flowbox.unselect_child(child)
            self.last_chan_selected = self.keystring

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_exclam(self):
        """ Level + (% level) of selected channels """
        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")
        if percent:
            lvl = round((lvl / 100) * 255)

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    level = App().dmx.frame[univ][out - 1]
                    if level + lvl > 255:
                        App().dmx.user[channel] = 255
                    else:
                        App().dmx.user[channel] = level + lvl

        App().dmx.send()

    def keypress_colon(self):
        """ Level - (% level) of selected channels """
        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")
        if percent:
            lvl = round((lvl / 100) * 255)

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    level = App().dmx.frame[univ][out - 1]
                    if level - lvl < 0:
                        App().dmx.user[channel] = 0
                    else:
                        App().dmx.user[channel] = level - lvl

        App().dmx.send()

    def keypress_KP_Enter(self):
        """ @ Level """
        self.keypress_equal()

    def keypress_equal(self):
        """ @ Level """
        if self.keystring == "":
            return

        level = int(self.keystring)

        sel = self.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1

                if App().settings.get_boolean("percent"):
                    if 0 <= level <= 100:
                        App().dmx.user[channel] = int(round((level / 100) * 255))
                else:
                    if 0 <= level <= 255:
                        App().dmx.user[channel] = level

        App().dmx.send()

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_BackSpace(self):
        """ Empty keys buffer """
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_Escape(self):
        """ Unselect all channels """
        self.flowbox.unselect_all()
        self.last_chan_selected = ""

    def keypress_q(self):
        """ Seq - """
        App().sequence.sequence_minus()
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_w(self):
        """ Seq + """
        App().sequence.sequence_plus()
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_G(self):
        """ Goto """
        App().sequence.goto(self.keystring)
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def keypress_R(self):
        """ Record new Step and new Preset """
        found = False

        if self.keystring == "":
            # Find next free Cue
            position = App().sequence.position
            mem = App().sequence.get_next_cue(step=position)
            step = position + 1
        else:
            # Use given number
            mem = float(self.keystring)
            found, step = App().sequence.get_step(cue=mem)

        if not found:
            # Create Preset
            channels = array.array("B", [0] * MAX_CHANNELS)
            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = App().patch.outputs[univ][output][0]
                    level = App().dmx.frame[univ][output]
                    channels[channel - 1] = level
            cue = Cue(1, mem, channels)
            App().memories.insert(step - 1, cue)

            # Update Presets Tab if exist
            if App().memories_tab:
                nb_chan = 0
                for chan in range(MAX_CHANNELS):
                    if channels[chan]:
                        nb_chan += 1
                App().memories_tab.liststore.insert(step - 1, [str(mem), "", nb_chan])

            App().sequence.position = step

            # Create Step
            step_object = Step(1, cue=cue)
            App().sequence.insert_step(step, step_object)

            # Update Main Playback
            self.update_sequence_display()
            self.update_xfade_display(step)
            self.update_channels_display(step)
        else:  # Update Preset
            # Find Preset's position
            found = False
            i = 0
            for i, item in enumerate(App().memories):
                if item.memory > mem:
                    found = True
                    break
            i -= 1

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = App().patch.outputs[univ][output][0]
                    level = App().dmx.frame[univ][output]

                    App().memories[i].channels[channel - 1] = level

            # Update Presets Tab if exist
            if App().memories_tab:
                nb_chan = 0
                for chan in range(MAX_CHANNELS):
                    if App().memories[i].channels[chan]:
                        nb_chan += 1
                treeiter = App().memories_tab.liststore.get_iter(i)
                App().memories_tab.liststore.set_value(treeiter, 2, nb_chan)
                App().memories_tab.flowbox.invalidate_filter()

        # Update Sequential edition Tabs
        if App().sequences_tab:
            # Main Playback selected ?
            path, _focus_column = App().sequences_tab.treeview1.get_cursor()
            if path:
                selected = path.get_indices()[0]
                sequence = App().sequences_tab.liststore1[selected][0]
                if sequence == App().sequence.index:
                    # Yes, update it
                    selection = App().sequences_tab.treeview1.get_selection()
                    App().sequences_tab.on_sequence_changed(selection)

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_U(self):
        """ Update Cue """
        position = App().sequence.position
        memory = App().sequence.steps[position].cue.memory

        # Confirmation Dialog
        dialog = Dialog(self, memory)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = App().patch.outputs[univ][output][0]
                    level = App().dmx.frame[univ][output]

                    App().sequence.steps[position].cue.channels[channel - 1] = level

            # Tag filename as modified
            App().ascii.modified = True
            App().window.header.set_title(App().ascii.basename + "*")

        elif response == Gtk.ResponseType.CANCEL:
            pass

        dialog.destroy()

    def keypress_T(self):
        """Change Time In and Time Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_time(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][5] = str(time)
        self.cues_liststore1[position + 3][7] = str(time)
        self.step_filter1.refilter()
        self.sequential.time_in = App().sequence.steps[position + 1].time_in
        self.sequential.time_out = App().sequence.steps[position + 1].time_out
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_I(self):
        """Change Time In of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_time_in(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][7] = str(time)
        self.step_filter1.refilter()
        self.sequential.time_in = App().sequence.steps[position + 1].time_in
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_O(self):
        """Change Time Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_time_out(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][5] = str(time)
        self.step_filter1.refilter()
        self.sequential.time_out = App().sequence.steps[position + 1].time_out
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_W(self):
        """Change Wait Time of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_wait(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][3] = str(time)
        self.step_filter1.refilter()
        self.sequential.wait = App().sequence.steps[position + 1].wait
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_D(self):
        """Change Delay In and Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_delay(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][4] = str(time)
        self.cues_liststore1[position + 3][6] = str(time)
        self.step_filter1.refilter()
        self.sequential.delay_in = App().sequence.steps[position + 1].delay_in
        self.sequential.delay_out = App().sequence.steps[position + 1].delay_out
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_K(self):
        """Change Delay In of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_delay_in(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][6] = str(time)
        self.step_filter1.refilter()
        self.sequential.delay_in = App().sequence.steps[position + 1].delay_in
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def keypress_L(self):
        """Change Delay Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_delay_out(time)
        if time.is_integer():
            time = int(time)
        self.cues_liststore1[position + 3][4] = str(time)
        self.step_filter1.refilter()
        self.sequential.delay_out = App().sequence.steps[position + 1].delay_out
        self.sequential.total_time = App().sequence.steps[position + 1].total_time
        self.seq_grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        App().window.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)


class Dialog(Gtk.Dialog):
    """ Confirmation dialog when update Cue """

    def __init__(self, parent, memory):
        Gtk.Dialog.__init__(
            self,
            "",
            parent,
            0,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK,
                Gtk.ResponseType.OK,
            ),
        )

        self.set_default_size(150, 100)

        label = Gtk.Label("Update memory " + str(memory) + " ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()
