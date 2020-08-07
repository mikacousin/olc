from gi.repository import Gtk, Gdk

from olc.define import MAX_CHANNELS, App
from olc.widgets_patch_channels import PatchChannelHeader, PatchChannelWidget


class PatchChannelsTab(Gtk.Grid):
    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.header = PatchChannelHeader()

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for channel in range(MAX_CHANNELS):
            self.channels.append(PatchChannelWidget(channel + 1, App().patch))
            self.flowbox.add(self.channels[channel])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.attach(self.header, 0, 0, 1, 1)
        self.attach_next_to(
            self.scrollable, self.header, Gtk.PositionType.BOTTOM, 1, 10
        )

    def filter_func(self, _child, _user_data):
        return True

    def on_close_icon(self, _widget):
        """ Close Tab on close clicked """
        page = App().window.notebook.page_num(App().patch_channels_tab)
        App().window.notebook.remove_page(page)
        App().patch_channels_tab = None

    def on_key_press_event(self, widget, event):

        # TODO: Hack to know if user is editing something
        widget = App().window.get_focus()
        # print(widget.get_path().is_type(Gtk.Entry))
        if not widget:
            return False
        if widget.get_path().is_type(Gtk.Entry):
            return False

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

        func = getattr(self, "_keypress_" + keyname, None)
        if func:
            return func()
        return False

    def _keypress_Escape(self):
        """ Close Tab """
        page = App().window.notebook.get_current_page()
        App().window.notebook.remove_page(page)
        App().patch_channels_tab = None

    def _keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Down(self):
        """ Select Next Channel """

        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"
        elif int(self.last_chan_selected) < MAX_CHANNELS - 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) + 1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) + 1)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Up(self):
        """ Select Previous Channel """
        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"
        elif int(self.last_chan_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) - 1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) - 1)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_c(self):
        """ Select Channel """
        self.flowbox.unselect_all()

        if self.keystring != "":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = self.flowbox.get_child_at_index(channel)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_m(self):
        """ Modify Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1

                # Unpatch if no entry
                if self.keystring == "" or self.keystring == "0":
                    # outputs = App().patch.channels[channel]
                    for item in App().patch.channels[channel]:
                        output = item[0] - 1
                        universe = item[1]
                        App().patch.outputs[universe][output][0] = 0
                        App().dmx.frame[universe][output] = 0
                    App().patch.channels[channel] = [[0, 0]]
                    # Update ui
                    self.channels[channel].queue_draw()
                else:
                    # New values
                    if "." in self.keystring:
                        if self.keystring[0] == ".":
                            # ".universe" for change universe
                            output = App().patch.channels[channel][0][0] - 1
                            universe = int(self.keystring[1:])
                        else:
                            # "output.universe"
                            split = self.keystring.split(".")
                            output = int(split[0]) - 1
                            universe = int(split[1])
                    else:
                        # "output", universe is 0
                        output = int(self.keystring) - 1
                        universe = 0

                    if 0 <= output < 512:
                        # Unpatch old values
                        # outputs = App().patch.channels[channel]
                        for item in App().patch.channels[channel]:
                            out = item[0] - 1
                            univ = item[1]
                            App().patch.outputs[univ][out][0] = 0
                        old_channel = App().patch.outputs[universe][output][0]
                        if old_channel:
                            App().patch.outputs[universe][output][0] = 0
                            App().patch.channels[old_channel - 1].remove(
                                [output + 1, universe]
                            )
                            if len(App().patch.channels[old_channel - 1]) == 0:
                                App().patch.channels[old_channel - 1] = [[0, 0]]
                        # Patch
                        App().patch.channels[channel] = [[output + 1, universe]]
                        App().patch.outputs[universe][output][0] = channel + 1
                        # Update ui
                        self.channels[old_channel - 1].queue_draw()
                        self.channels[channel].queue_draw()

                # Update list of channels
                level = App().dmx.frame[universe][output]
                App().window.channels[channel].level = level
                App().window.channels[channel].queue_draw()
                App().window.flowbox.invalidate_filter()

        # Select next channel
        if sel:
            if channel < MAX_CHANNELS - 1:
                self.flowbox.unselect_all()
                child = self.flowbox.get_child_at_index(channel + 1)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel + 1)

        # App().dmx.send()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_i(self):
        """ Insert Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1

                if self.keystring != "" or self.keystring != "0":
                    # New values
                    if "." in self.keystring:
                        if self.keystring[0] == ".":
                            # ".universe" for change universe
                            output = App().patch.channels[channel][0][0] - 1
                            universe = int(self.keystring[1:])
                        else:
                            # "output.universe"
                            split = self.keystring.split(".")
                            output = int(split[0]) - 1
                            universe = int(split[1])
                    else:
                        # "output", universe is 0
                        output = int(self.keystring) - 1
                        universe = 0

                    if 0 <= output < 512:
                        # Unpatch old value
                        old_channel = App().patch.outputs[universe][output][0]
                        if old_channel:
                            App().patch.outputs[universe][output][0] = 0
                            App().patch.channels[old_channel - 1].remove(
                                [output + 1, universe]
                            )
                            if len(App().patch.channels[old_channel - 1]) == 0:
                                App().patch.channels[old_channel - 1] = [[0, 0]]
                        # Patch
                        App().patch.add_output(channel + 1, output + 1, universe)
                        # Update ui
                        self.channels[old_channel - 1].queue_draw()
                        self.channels[channel].queue_draw()

                        # Update list of channels
                        App().window.channels[channel].queue_draw()
                        App().window.flowbox.invalidate_filter()

        # App().dmx.send()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_r(self):
        """ Remove Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1
                # univ = App().patch.channels[channel][1]

                if self.keystring != "" or self.keystring != "0":
                    if "." in self.keystring:
                        if self.keystring[0] != ".":
                            # "output.universe"
                            split = self.keystring.split(".")
                            output = int(split[0]) - 1
                            universe = int(split[1])
                    else:
                        # "output", universe is 0
                        output = int(self.keystring) - 1
                        universe = 0

                    if 0 <= output < 512:
                        # Verify Output is patched to the Channel
                        if [output + 1, universe] in App().patch.channels[channel]:
                            # Remove Output
                            App().patch.channels[channel].remove([output + 1, universe])
                            if len(App().patch.channels[channel]) == 0:
                                App().patch.channels[channel] = [[0, 0]]
                            App().patch.outputs[universe][output][0] = 0
                            App().dmx.frame[universe][output] = 0
                            # Update ui
                            self.channels[channel].queue_draw()

                # Update list of channels
                App().window.channels[channel].queue_draw()
                App().window.flowbox.invalidate_filter()

        # App().dmx.send()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
