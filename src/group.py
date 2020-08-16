import array

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets_channel import ChannelWidget
from olc.widgets_group import GroupWidget


class Group:
    def __init__(self, index, channels=array.array("B", [0] * MAX_CHANNELS), text=""):
        self.index = index
        self.channels = channels
        self.text = str(text)


class GroupTab(Gtk.Paned):
    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""
        self.last_group_selected = ""

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        self.scrolled1 = Gtk.ScrolledWindow()
        self.scrolled1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox1 = Gtk.FlowBox()
        self.flowbox1.set_valign(Gtk.Align.START)
        self.flowbox1.set_max_children_per_line(20)
        self.flowbox1.set_homogeneous(True)
        self.flowbox1.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for i in range(MAX_CHANNELS):
            self.channels.append(ChannelWidget(i + 1, 0, 0))
            self.flowbox1.add(self.channels[i])

        self.scrolled1.add(self.flowbox1)

        self.add1(self.scrolled1)

        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.grps = []

        self.populate_tab()

        self.add2(self.scrolled2)

        self.flowbox1.set_filter_func(self.filter_channels, None)

    def populate_tab(self):
        """Add groups to tab"""
        # New FlowBox
        self.flowbox2 = Gtk.FlowBox()
        self.flowbox2.set_valign(Gtk.Align.START)
        self.flowbox2.set_max_children_per_line(20)
        self.flowbox2.set_homogeneous(True)
        self.flowbox2.set_activate_on_single_click(True)
        self.flowbox2.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox2.set_filter_func(self.filter_groups, None)
        # Add groups to FlowBox
        for i, _ in enumerate(App().groups):
            self.grps.append(
                GroupWidget(i, App().groups[i].index, App().groups[i].text, self.grps)
            )
            self.flowbox2.add(self.grps[i])
        self.scrolled2.add(self.flowbox2)

    def filter_channels(self, child, _user_data):
        """ Pour n'afficher que les channels du groupe """
        i = child.get_index()  # Numéro du widget qu'on filtre (channel - 1)
        # On cherche le groupe actuellement séléctionné
        for j, _ in enumerate(self.grps):
            if self.grps[j].get_parent().is_selected():
                # Si le channel est dans le groupe, on l'affiche
                if App().groups[j].channels[i] or self.channels[i].clicked:
                    # On récupère le level (next_level à la même valeur)
                    self.channels[i].level = App().groups[j].channels[i]
                    self.channels[i].next_level = App().groups[j].channels[i]
                    return child
                return False
        return False

    def filter_groups(self, child, _user_data):
        return child

    def on_close_icon(self, _widget):
        """ Close Tab with the icon clicked """
        page = App().window.notebook.page_num(self)
        App().window.notebook.remove_page(page)
        App().group_tab = None

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

        if keyname == "period":
            self.keystring += "."
            App().window.statusbar.push(App().window.context_id, self.keystring)

        func = getattr(self, "_keypress_" + keyname, None)
        if func:
            return func()
        return False

    def _keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Escape(self):
        """ Close Tab """
        page = App().window.notebook.get_current_page()
        App().window.notebook.remove_page(page)
        App().group_tab = None

    def _keypress_Right(self):
        """ Next Group """

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.flowbox2.invalidate_filter()
        elif int(self.last_group_selected) + 1 < len(self.grps):
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected) + 1)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.last_group_selected = str(int(self.last_group_selected) + 1)

    def _keypress_Left(self):
        """ Previous Group """

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.flowbox2.invalidate_filter()
        elif int(self.last_group_selected) > 0:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected) - 1)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.last_group_selected = str(int(self.last_group_selected) - 1)

    def _keypress_Down(self):
        """ Group on Next Line """

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.flowbox2.invalidate_filter()
        else:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected))
            allocation = child.get_allocation()
            child = self.flowbox2.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            )
            if child:
                self.flowbox2.unselect_all()
                index = child.get_index()
                App().window.set_focus(child)
                self.flowbox2.select_child(child)
                # Deselect all channels
                for channel in range(MAX_CHANNELS):
                    self.channels[channel].clicked = False
                    self.channels[channel].queue_draw()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(index)

    def _keypress_Up(self):
        """ Group on Previous Line """

        if self.last_group_selected == "":
            child = self.flowbox2.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox2.select_child(child)
            self.last_group_selected = "0"
            # Deselect all channels
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
                self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.flowbox2.invalidate_filter()
        else:
            child = self.flowbox2.get_child_at_index(int(self.last_group_selected))
            allocation = child.get_allocation()
            child = self.flowbox2.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            )
            if child:
                self.flowbox2.unselect_all()
                index = child.get_index()
                App().window.set_focus(child)
                self.flowbox2.select_child(child)
                # Deselect all channels
                for channel in range(MAX_CHANNELS):
                    self.channels[channel].clicked = False
                    self.channels[channel].queue_draw()
                self.flowbox1.invalidate_filter()
                self.last_group_selected = str(index)

    def _keypress_g(self):
        """ Select Group """

        self.flowbox2.unselect_all()

        if self.keystring != "":
            group = float(self.keystring)
            for grp in self.grps:
                if group == float(grp.number):
                    index = grp.index
                    child = self.flowbox2.get_child_at_index(index)
                    App().window.set_focus(child)
                    self.flowbox2.select_child(child)
                    break
            self.last_group_selected = str(index)
        # Deselect all channels
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        # Update display
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_a(self):
        """ All Channels """

        self.flowbox1.unselect_all()

        sel2 = self.flowbox2.get_selected_children()
        children2 = []
        for flowboxchild2 in sel2:
            children2 = flowboxchild2.get_children()

            for groupwidget in children2:
                index = groupwidget.index

                for channel in range(MAX_CHANNELS):
                    level = App().groups[index].channels[channel]
                    if level > 0:
                        self.channels[channel].clicked = True
                        child = self.flowbox1.get_child_at_index(channel)
                        App().window.set_focus(child)
                        self.flowbox1.select_child(child)

    def _keypress_c(self):
        """ Channel """

        self.flowbox1.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:

                # Only patched channel
                if App().patch.channels[channel][0] != [0, 0]:
                    self.channels[channel].clicked = True
                    self.flowbox1.invalidate_filter()

                    child = self.flowbox1.get_child_at_index(channel)
                    App().window.set_focus(child)
                    self.flowbox1.select_child(child)
                    self.last_chan_selected = self.keystring
        else:
            for channel in range(MAX_CHANNELS):
                self.channels[channel].clicked = False
            self.flowbox1.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):
        self._keypress_greater()

    def _keypress_greater(self):
        """ Channel Thru """

        sel = self.flowbox1.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if self.last_chan_selected:
            to_chan = int(self.keystring)
            if to_chan > int(self.last_chan_selected):
                for channel in range(int(self.last_chan_selected) - 1, to_chan):

                    # Only patched channels
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels[channel].clicked = True

                        child = self.flowbox1.get_child_at_index(channel)
                        App().window.set_focus(child)
                        self.flowbox1.select_child(child)

            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):

                    # Only patched channels
                    if App().patch.channels[channel][0] != [0, 0]:
                        self.channels[channel].clicked = True

                        child = self.flowbox1.get_child_at_index(channel)
                        App().window.set_focus(child)
                        self.flowbox1.select_child(child)

            self.flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_plus(self):
        """ Channel + """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            self.channels[channel].clicked = True
            self.flowbox1.invalidate_filter()

            child = self.flowbox1.get_child_at_index(channel)
            App().window.set_focus(child)
            self.flowbox1.select_child(child)
            self.last_chan_selected = self.keystring

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_minus(self):
        """ Channel - """

        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            self.channels[channel].clicked = False
            self.flowbox1.invalidate_filter()

            child = self.flowbox1.get_child_at_index(channel)
            App().window.set_focus(child)
            self.flowbox1.unselect_child(child)

            self.last_chan_selected = self.keystring

            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self):
        """ @ Level """

        if self.keystring == "":
            return

        level = int(self.keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255)) if 0 <= level <= 100 else -1
        else:
            if level > 255:
                level = 255

        sel = self.flowbox2.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for groupwidget in children:
                index = groupwidget.index

                sel1 = self.flowbox1.get_selected_children()

                for flowboxchild1 in sel1:
                    children1 = flowboxchild1.get_children()

                    for channelwidget in children1:
                        channel = int(channelwidget.channel) - 1

                        if level != -1:
                            App().groups[index].channels[channel] = level

        self.flowbox1.invalidate_filter()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """ Level - % """
        lvl = App().settings.get_int("percent-level")

        sel2 = self.flowbox2.get_selected_children()
        children2 = []
        for flowboxchild2 in sel2:
            children2 = flowboxchild2.get_children()

            for groupwidget in children2:
                index = groupwidget.index

                sel = self.flowbox1.get_selected_children()

                for flowboxchild in sel:
                    children = flowboxchild.get_children()

                    for channelwidget in children:
                        channel = int(channelwidget.channel) - 1

                        level = App().groups[index].channels[channel]

                        level = max(level - lvl, 0)
                        App().groups[index].channels[channel] = level

        self.flowbox1.invalidate_filter()

    def _keypress_exclam(self):
        """ Level + % """
        lvl = App().settings.get_int("percent-level")

        sel2 = self.flowbox2.get_selected_children()
        children2 = []
        for flowboxchild2 in sel2:
            children2 = flowboxchild2.get_children()

            for groupwidget in children2:
                index = groupwidget.index

                sel = self.flowbox1.get_selected_children()

                for flowboxchild in sel:
                    children = flowboxchild.get_children()

                    for channelwidget in children:
                        channel = int(channelwidget.channel) - 1

                        level = App().groups[index].channels[channel]
                        level = min(level + lvl, 255)
                        App().groups[index].channels[channel] = level

        self.flowbox1.invalidate_filter()

    def _keypress_N(self):
        """ New Group """
        # If no group number, use the next one
        if self.keystring == "":
            group_nb = 1 if len(App().groups) == 0 else App().groups[-1].index + 1
        else:
            group_nb = int(self.keystring)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

        channels = array.array("B", [0] * MAX_CHANNELS)
        txt = str(float(group_nb))
        App().groups.append(Group(float(group_nb), channels, txt))
        i = self.grps[-1].index + 1 if len(self.grps) > 0 else 0
        self.grps.append(
            GroupWidget(i, App().groups[-1].index, App().groups[-1].text, self.grps)
        )
        self.flowbox2.add(self.grps[-1])
        # Deselect all channels
        self.flowbox1.unselect_all()
        for channel in range(MAX_CHANNELS):
            self.channels[channel].clicked = False
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()
        App().window.show_all()
