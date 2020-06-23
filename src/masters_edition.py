import array
from gi.repository import Gtk, Gio, Gdk

from olc.define import MAX_CHANNELS
from olc.widgets_channel import ChannelWidget


class MastersTab(Gtk.Paned):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ""
        self.last_chan_selected = ""

        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        # Channels used in selected Master
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

        # Content Type
        self.content_type = Gtk.ListStore(str)
        types = ["", "Preset", "Channels", "Sequence", "Group"]
        for item in types:
            self.content_type.append([item])

        # Mode
        self.mode = Gtk.ListStore(str)
        modes = ["Inclusif", "Exclusif"]
        for item in modes:
            self.mode.append([item])

        self.liststore = Gtk.ListStore(int, str, str, str)

        # Masters (2 pages of 20 Masters)
        for page in range(2):
            for i in range(20):
                index = i + (page * 20)

                # Type : None
                if self.app.masters[index].content_type == 0:
                    self.liststore.append([index + 1, "", "", ""])

                # Type : Preset
                elif self.app.masters[index].content_type == 1:
                    content_value = str(self.app.masters[index].content_value)
                    self.liststore.append([index + 1, "Preset", content_value, ""])

                # Type : Channels
                elif self.app.masters[index].content_type == 2:
                    nb_chan = 0
                    for chan in range(MAX_CHANNELS):
                        if self.app.masters[index].channels[chan]:
                            nb_chan += 1
                    self.liststore.append([index + 1, "Channels", str(nb_chan), ""])

                # Type : Sequence
                elif self.app.masters[index].content_type == 3:
                    if self.app.masters[index].content_value.is_integer():
                        content_value = str(int(self.app.masters[index].content_value))
                    else:
                        content_value = str(self.app.masters[index].content_value)
                    self.liststore.append([index + 1, "Sequence", content_value, ""])

                # Type : Group
                elif self.app.masters[index].content_type == 13:
                    if self.app.masters[index].content_value.is_integer():
                        content_value = str(int(self.app.masters[index].content_value))
                    else:
                        content_value = str(self.app.masters[index].content_value)
                    self.liststore.append(
                        [index + 1, "Group", content_value, "Exclusif"]
                    )

                # Type : Unknown
                else:
                    self.liststore.append([index + 1, "Unknown", "", ""])

        self.filter = self.liststore.filter_new()
        self.filter.set_visible_func(self.filter_master)

        self.treeview = Gtk.TreeView(model=self.filter)
        self.treeview.set_enable_search(False)
        self.treeview.connect("cursor-changed", self.on_master_changed)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Master", renderer, text=0)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererCombo()
        renderer.set_property("editable", True)
        renderer.set_property("model", self.content_type)
        renderer.set_property("text-column", 0)
        renderer.set_property("has-entry", False)
        renderer.connect("edited", self.on_content_type_changed)
        column = Gtk.TreeViewColumn("Content type", renderer, text=1)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.set_property("editable", True)
        renderer.connect("edited", self.on_content_value_edited)
        column = Gtk.TreeViewColumn("Content", renderer, text=2)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererCombo()
        renderer.set_property("editable", True)
        renderer.set_property("model", self.mode)
        renderer.set_property("text-column", 0)
        renderer.set_property("has-entry", False)
        renderer.connect("edited", self.on_mode_changed)
        column = Gtk.TreeViewColumn("Mode", renderer, text=3)
        self.treeview.append_column(column)

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_vexpand(True)
        self.scrollable.set_hexpand(True)
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.treeview)

        self.add(self.scrollable)

        self.flowbox.set_filter_func(self.filter_channel_func, None)

        # Select First Master
        path = Gtk.TreePath.new_first()
        self.treeview.set_cursor(path, None, False)

    def filter_master(self, model, i, data):
        return True

    def filter_channel_func(self, child, user_data):
        """ Filter channels """
        # Find selected row
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]
            # Index of Channel
            index = child.get_index()

            # Type : None
            if self.app.masters[row].content_type == 0:
                return False

            # Type : Preset
            if self.app.masters[row].content_type == 1:
                found = False
                preset = self.app.masters[row].content_value
                for mem in self.app.memories:
                    if mem.memory == preset:
                        found = True
                        break
                if found:
                    channels = mem.channels
                    if channels[index] or self.channels[index].clicked:
                        if self.user_channels[index] == -1:
                            self.channels[index].level = channels[index]
                            self.channels[index].next_level = channels[index]
                        else:
                            self.channels[index].level = self.user_channels[index]
                            self.channels[index].next_level = self.user_channels[index]
                        return child
                    if self.user_channels[index] == -1:
                        return False
                    self.channels[index].level = self.user_channels[index]
                    self.channels[index].next_level = self.user_channels[index]
                    return child
                return False

            # Type : Channels
            if self.app.masters[row].content_type == 2:
                channels = self.app.masters[row].channels

                if channels[index] or self.channels[index].clicked:
                    if self.user_channels[index] == -1:
                        self.channels[index].level = channels[index]
                        self.channels[index].next_level = channels[index]
                    else:
                        self.channels[index].level = self.user_channels[index]
                        self.channels[index].next_level = self.user_channels[index]
                    return child
                if self.user_channels[index] == -1:
                    return False
                self.channels[index].level = self.user_channels[index]
                self.channels[index].next_level = self.user_channels[index]
                return child

            # Type : Sequence
            if self.app.masters[row].content_type == 3:
                return False

            # Type : Group
            if self.app.masters[row].content_type == 13:
                found = False
                group = self.app.masters[row].content_value
                for grp in self.app.groups:
                    if grp.index == group:
                        found = True
                        break
                if found:
                    channels = grp.channels
                    if channels[index] or self.channels[index].clicked:
                        if self.user_channels[index] == -1:
                            self.channels[index].level = channels[index]
                            self.channels[index].next_level = channels[index]
                        else:
                            self.channels[index].level = self.user_channels[index]
                            self.channels[index].next_level = self.user_channels[index]
                        return child
                    if self.user_channels[index] == -1:
                        return False
                    self.channels[index].level = self.user_channels[index]
                    self.channels[index].next_level = self.user_channels[index]
                    return child
                return False

        return False

    def on_master_changed(self, treeview):
        """ New master is selected """
        self.flowbox.unselect_all()
        self.user_channels = array.array("h", [-1] * MAX_CHANNELS)
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox.invalidate_filter()

    def on_content_type_changed(self, widget, path, text):
        # Update display
        self.liststore[path][1] = text

        # Find content type
        content_type = 0

        if text == "":
            content_type = 0
        elif text == "Preset":
            content_type = 1
        elif text == "Channels":
            content_type = 2
        elif text == "Sequence":
            content_type = 3
        elif text == "Group":
            content_type = 13

        # Update content type
        index = int(path)

        if self.app.masters[index].content_type != content_type:

            self.app.masters[index].content_type = content_type

            # Update content value
            self.app.masters[index].content_value = -1
            self.app.masters[index].channels = array.array("B", [0] * MAX_CHANNELS)
            self.app.masters[index].text = ""

            # Update ui
            self.flowbox.invalidate_filter()
            self.liststore[path][2] = ""
            self.liststore[path][3] = ""

            # Update Virtual Console
            if self.app.virtual_console:
                if self.app.virtual_console.props.visible:
                    self.app.virtual_console.flashes[index].label = ""
                    self.app.virtual_console.flashes[index].queue_draw()

    def on_mode_changed(self, widget, path, text):
        self.liststore[path][3] = text

    def on_content_value_edited(self, widget, path, text):
        if text == "":
            text = "0"

        if text.replace(".", "", 1).isdigit():

            if text[0] == ".":
                text = "0" + text

            if text == "0":
                self.liststore[path][2] = ""
            else:
                self.liststore[path][2] = text

            # Update content value
            index = int(path)
            content_value = float(text)

            self.app.masters[index].content_value = content_value

            if self.app.masters[index].content_type == 0:
                self.app.masters[index].text = ""

            elif self.app.masters[index].content_type == 1:
                if self.liststore[path][2] != "":
                    self.liststore[path][2] = str(float(self.liststore[path][2]))
                self.app.masters[index].text = ""
                for mem in self.app.memories:
                    if mem.memory == content_value:
                        self.app.masters[index].text = mem.text

            elif self.app.masters[index].content_type == 2:
                self.app.masters[index].text = ""

            elif self.app.masters[index].content_type == 3:
                self.app.masters[index].text = ""
                for chaser in self.app.chasers:
                    if chaser.index == content_value:
                        self.app.masters[index].text = chaser.text

            elif self.app.masters[index].content_type == 13:
                self.app.masters[index].text = ""
                for grp in self.app.groups:
                    if grp.index == content_value:
                        self.app.masters[index].text = grp.text

            self.flowbox.invalidate_filter()

            # Update Virtual Console
            if self.app.virtual_console:
                self.app.virtual_console.flashes[index].label = self.app.masters[
                    index
                ].text
                self.app.virtual_console.flashes[index].queue_draw()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.masters_tab)
        self.app.window.notebook.remove_page(page)
        self.app.masters_tab = None

    def on_key_press_event(self, widget, event):

        # Hack to know if user is editing something
        # TODO: Bug with CellRendererCombo (entry blocked)
        widget = self.app.window.get_focus()
        if not widget:
            return False
        if widget.get_path().is_type(Gtk.Entry):
            return False

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
        return False

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.masters_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Channel """

        # Find Selected Master
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if (
                self.app.masters[row].content_type == 0
                or self.app.masters[row].content_type == 3
            ):
                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return False

            self.flowbox.unselect_all()

            if self.keystring != "" and self.keystring != "0":
                channel = int(self.keystring) - 1
                if 0 <= channel < MAX_CHANNELS:

                    # Only patched channels
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
            return True
        return False

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """

        # Find Selected Master
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if (
                self.app.masters[row].content_type == 0
                or self.app.masters[row].content_type == 3
            ):
                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return False

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
            return True
        return False

    def keypress_plus(self):
        """ Channel + """

        # Find Selected Master
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if (
                self.app.masters[row].content_type == 0
                or self.app.masters[row].content_type == 3
            ):
                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return False

            if self.keystring != "":

                channel = int(self.keystring) - 1

                if 0 <= channel < MAX_CHANNELS and self.app.patch.channels[channel][
                    0
                ] != [0, 0]:
                    self.channels[channel].clicked = True
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.flowbox.select_child(child)
                    self.last_chan_selected = self.keystring

                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return True
            return False
        return False

    def keypress_minus(self):
        """ Channel - """

        # Find Selected Master
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if (
                self.app.masters[row].content_type == 0
                or self.app.masters[row].content_type == 3
            ):
                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return False

            if self.keystring != "":

                channel = int(self.keystring) - 1

                if 0 <= channel < MAX_CHANNELS and self.app.patch.channels[channel][
                    0
                ] != [0, 0]:
                    self.channels[channel].clicked = False
                    self.flowbox.invalidate_filter()

                    child = self.flowbox.get_child_at_index(channel)
                    self.app.window.set_focus(child)
                    self.flowbox.unselect_child(child)
                    self.last_chan_selected = self.keystring

                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return True
            return False
        return False

    def keypress_a(self):
        """ All Channels """

        # Find Selected Master
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            if (
                self.app.masters[row].content_type == 0
                or self.app.masters[row].content_type == 3
            ):
                self.keystring = ""
                self.app.window.statusbar.push(
                    self.app.window.context_id, self.keystring
                )
                return False

            self.flowbox.unselect_all()

            # Master's channels
            if self.app.masters[row].content_type == 1:
                preset = self.app.masters[row].content_value
                found = False
                for mem in self.app.memories:
                    if mem.memory == preset:
                        found = True
                        break
                if found:
                    channels = mem.channels
                else:
                    return False
            elif self.app.masters[row].content_type == 2:
                channels = self.app.masters[row].channels

            elif self.app.masters[row].content_type == 13:
                group = self.app.masters[row].content_value
                found = False
                for grp in self.app.groups:
                    if grp.index == group:
                        found = True
                        break
                if found:
                    channels = grp.channels
                else:
                    return False

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
            return True
        return False

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
        self.keypress_R()

    def keypress_R(self):
        """ Record Master """

        self.flowbox.unselect_all()

        # Find selected Master
        path, focus_column = self.treeview.get_cursor()
        if path:
            row = path.get_indices()[0]

            # Type : None
            if self.app.masters[row].content_type == 0:
                return False

            # Type : Preset
            if self.app.masters[row].content_type == 1:
                found = False
                for mem in self.app.memories:
                    if mem.memory == self.app.masters[row].content_value:
                        found = True
                        break
                if found:
                    channels = mem.channels
                    for chan in range(MAX_CHANNELS):
                        channels[chan] = self.channels[chan].level
                    # Update Preset Tab if open
                    if self.app.memories_tab:
                        self.app.memories_tab.flowbox.invalidate_filter()

            # Type : Channels
            if self.app.masters[row].content_type == 2:
                channels = self.app.masters[row].channels

                nb_chan = 0
                text = "Ch"
                for chan in range(MAX_CHANNELS):
                    channels[chan] = self.channels[chan].level
                    if channels[chan]:
                        nb_chan += 1
                        text += " " + str(chan + 1)

                self.app.masters[row].text = text

                # Update Display
                self.liststore[path][2] = str(nb_chan)
                self.flowbox.invalidate_filter()

                # Update Virtual Console
                if self.app.virtual_console:
                    self.app.virtual_console.flashes[row].label = self.app.masters[
                        row
                    ].text
                    self.app.virtual_console.flashes[row].queue_draw()

            # Type = Group
            elif self.app.masters[row].content_type == 13:
                found = False
                for grp in self.app.groups:
                    if grp.index == self.app.masters[row].content_value:
                        found = True
                        break
                if found:
                    channels = grp.channels
                    for chan in range(MAX_CHANNELS):
                        channels[chan] = self.channels[chan].level
                    # Update Group Tab if open
                    if self.app.group_tab:
                        self.app.group_tab.flowbox1.invalidate_filter()

            self.keystring = ""
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)
            return True

        return False
