from gi.repository import Gtk, Gio, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_patch_channels import PatchChannelHeader, PatchChannelWidget


class PatchChannelsTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

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
            self.channels.append(PatchChannelWidget(channel + 1, self.app.patch))
            self.flowbox.add(self.channels[channel])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.attach(self.header, 0, 0, 1, 1)
        self.attach_next_to(
            self.scrollable, self.header, Gtk.PositionType.BOTTOM, 1, 10
        )

    def filter_func(self, child, user_data):
        return True

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.patch_channels_tab)
        self.app.window.notebook.remove_page(page)
        self.app.patch_channels_tab = None

    def on_key_press_event(self, widget, event):

        # TODO: Hack to know if user is editing something
        widget = self.app.window.get_focus()
        # print(widget.get_path().is_type(Gtk.Entry))
        if not widget:
            return
        if widget.get_path().is_type(Gtk.Entry):
            return

        keyname = Gdk.keyval_name(event.keyval)

        if (
            keyname == "1"
            or keyname == "2"
            or keyname == "3"
            or keyname == "4"
            or keyname == "5"
            or keyname == "6"
            or keyname == "7"
            or keyname == "8"
            or keyname == "9"
            or keyname == "0"
        ):
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if (
            keyname == "KP_1"
            or keyname == "KP_2"
            or keyname == "KP_3"
            or keyname == "KP_4"
            or keyname == "KP_5"
            or keyname == "KP_6"
            or keyname == "KP_7"
            or keyname == "KP_8"
            or keyname == "KP_9"
            or keyname == "KP_0"
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
        self.app.patch_channels_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Down(self):
        """ Select Next Channel """

        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"
        elif int(self.last_chan_selected) < MAX_CHANNELS - 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) + 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) + 1)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_Up(self):
        """ Select Previous Channel """
        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"
        elif int(self.last_chan_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) - 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) - 1)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Select Channel """
        self.flowbox.unselect_all()

        if self.keystring != "":
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < MAX_CHANNELS:
                child = self.flowbox.get_child_at_index(channel)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_m(self):
        """ Modify Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1

                # Unpatch if no entry
                if self.keystring == "" or self.keystring == "0":
                    # outputs = self.app.patch.channels[channel]
                    for item in self.app.patch.channels[channel]:
                        output = item[0] - 1
                        universe = item[1]
                        self.app.patch.outputs[universe][output][0] = 0
                        self.app.dmx.frame[universe][output] = 0
                    self.app.patch.channels[channel] = [[0, 0]]
                    # Update ui
                    self.channels[channel].queue_draw()
                else:
                    # New values
                    if "." in self.keystring:
                        if self.keystring[0] == ".":
                            # ".universe" for change universe
                            output = self.app.patch.channels[channel][0][0] - 1
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

                    if output >= 0 and output < 512:
                        # Unpatch old values
                        # outputs = self.app.patch.channels[channel]
                        for item in self.app.patch.channels[channel]:
                            out = item[0] - 1
                            univ = item[1]
                            self.app.patch.outputs[univ][out][0] = 0
                        old_channel = self.app.patch.outputs[universe][output][0]
                        if old_channel:
                            self.app.patch.outputs[universe][output][0] = 0
                            self.app.patch.channels[old_channel - 1].remove(
                                [output + 1, universe]
                            )
                            if not len(self.app.patch.channels[old_channel - 1]):
                                self.app.patch.channels[old_channel - 1] = [[0, 0]]
                        # Patch
                        self.app.patch.channels[channel] = [[output + 1, universe]]
                        self.app.patch.outputs[universe][output][0] = channel + 1
                        # Update ui
                        self.channels[old_channel - 1].queue_draw()
                        self.channels[channel].queue_draw()

                # Update list of channels
                level = self.app.dmx.frame[universe][output]
                self.app.window.channels[channel].level = level
                self.app.window.channels[channel].queue_draw()
                self.app.window.flowbox.invalidate_filter()

        # Select next channel
        if sel:
            if channel < MAX_CHANNELS - 1:
                self.flowbox.unselect_all()
                child = self.flowbox.get_child_at_index(channel + 1)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel + 1)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_i(self):
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
                            output = self.app.patch.channels[channel][0][0] - 1
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

                    if output >= 0 and output < 512:
                        # Unpatch old value
                        old_channel = self.app.patch.outputs[universe][output][0]
                        if old_channel:
                            self.app.patch.outputs[universe][output][0] = 0
                            self.app.patch.channels[old_channel - 1].remove(
                                [output + 1, universe]
                            )
                            if not len(self.app.patch.channels[old_channel - 1]):
                                self.app.patch.channels[old_channel - 1] = [[0, 0]]
                        # Patch
                        self.app.patch.add_output(channel + 1, output + 1, universe)
                        # Update ui
                        self.channels[old_channel - 1].queue_draw()
                        self.channels[channel].queue_draw()

                        # Update list of channels
                        self.app.window.channels[channel].queue_draw()
                        self.app.window.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_r(self):
        """ Remove Output """
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchchannelwidget in children:
                channel = patchchannelwidget.channel - 1
                # univ = self.app.patch.channels[channel][1]

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

                    if output >= 0 and output < 512:
                        # Verify Output is patched to the Channel
                        if [output + 1, universe] in self.app.patch.channels[channel]:
                            # Remove Output
                            self.app.patch.channels[channel].remove(
                                [output + 1, universe]
                            )
                            if not len(self.app.patch.channels[channel]):
                                self.app.patch.channels[channel] = [[0, 0]]
                            self.app.patch.outputs[universe][output][0] = 0
                            self.app.dmx.frame[universe][output] = 0
                            # Update ui
                            self.channels[channel].queue_draw()

                # Update list of channels
                self.app.window.channels[channel].queue_draw()
                self.app.window.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
