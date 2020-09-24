"""Open Lighting Console's Main window"""

import array

from gi.repository import Gdk, Gio, Gtk
from olc.cue import Cue
from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.step import Step

from olc.widgets_grand_master import GMWidget
from olc.window_channels import ChannelsView
from olc.window_playback import MainPlaybackView


class Window(Gtk.ApplicationWindow):
    """Main Window"""

    def __init__(self):

        # Fullscreen
        self.full = False

        self.keystring = ""
        self.last_chan_selected = ""

        Gtk.ApplicationWindow.__init__(
            self, title="Open Lighting Console", application=App()
        )
        self.set_default_size(1400, 1080)
        self.set_name("olc")

        # Header Bar
        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("")
        self.header.props.show_close_button = True
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Grand Master viewer
        self.grand_master = GMWidget()
        box.add(self.grand_master)
        # All/Patched channels button
        button = Gtk.Button()
        icon = Gio.ThemedIcon(name="view-grid-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.connect("clicked", self.button_clicked_cb)
        button.add(image)
        box.add(button)
        # Menu button
        button = Gtk.MenuButton()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)
        box.add(button)
        popover = Gtk.Popover.new_from_model(button, App().setup_app_menu())
        button.set_popover(popover)
        self.header.pack_end(box)
        self.set_titlebar(self.header)

        # Paned
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(800)

        # Channels
        self.channels_view = ChannelsView()
        paned_chan = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned_chan.set_position(1100)
        paned_chan.pack1(self.channels_view, resize=True, shrink=False)
        # Gtk.Statusbar to display keyboard's keys
        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("keypress")
        grid = Gtk.Grid()
        label = Gtk.Label("Input : ")
        grid.add(label)
        grid.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)
        paned_chan.pack2(grid, resize=True, shrink=False)
        paned.pack1(paned_chan, resize=True, shrink=False)

        # Main Playback
        self.playback = MainPlaybackView()
        paned.pack2(self.playback, resize=True, shrink=False)

        self.add(paned)

        self.set_icon_name("olc")

    def fullscreen_toggle(self, _action, _param):
        """Toggle fullscreen"""
        if self.full:
            self.unfullscreen()
            self.full = False
        else:
            self.fullscreen()
            self.full = True

    def button_clicked_cb(self, button):
        """Toggle type of view : patched channels or all channels"""
        self.channels_view.view_type = 1 if self.channels_view.view_type == 0 else 0
        self.channels_view.flowbox.invalidate_filter()

    def update_channels_display(self, step):
        """Update Channels levels display"""
        for channel in range(MAX_CHANNELS):
            level = App().sequence.steps[step].cue.channels[channel]
            next_level = App().sequence.steps[step + 1].cue.channels[channel]
            self.channels_view.channels[channel].level = level
            self.channels_view.channels[channel].next_level = next_level
            self.channels_view.channels[channel].queue_draw()

    def on_key_press_event(self, _widget, event):
        """Executed on key press event"""
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

        func = getattr(self, "_keypress_" + keyname, None)

        if func:
            return func()
        return False

    def _keypress_Right(self):
        """Next Channel"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.channels_view.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.channels_view.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        elif int(self.last_chan_selected) < MAX_CHANNELS - 1:
            # Find next patched channel
            next_chan = 0
            for i in range(int(self.last_chan_selected) + 1, MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    next_chan = i
                    break
            if next_chan:
                self.channels_view.flowbox.unselect_all()
                child = self.channels_view.flowbox.get_child_at_index(next_chan)
                self.set_focus(child)
                self.channels_view.flowbox.select_child(child)
                self.last_chan_selected = str(next_chan)

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_Left(self):
        """Previous Channel"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.channels_view.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.channels_view.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        elif int(self.last_chan_selected) > 0:
            # Find previous patched channel
            chan = int(self.last_chan_selected)
            for i in range(int(self.last_chan_selected), 0, -1):
                if App().patch.channels[i - 1][0] != [0, 0]:
                    chan = i - 1
                    break
            self.channels_view.flowbox.unselect_all()
            child = self.channels_view.flowbox.get_child_at_index(chan)
            self.set_focus(child)
            self.channels_view.flowbox.select_child(child)
            self.last_chan_selected = str(chan)

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_Down(self):
        """Next Line"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.channels_view.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.channels_view.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        else:
            child = self.channels_view.flowbox.get_child_at_index(
                int(self.last_chan_selected)
            )
            allocation = child.get_allocation()
            child = self.channels_view.flowbox.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            )
            if child:
                self.channels_view.flowbox.unselect_all()
                index = child.get_index()
                self.set_focus(child)
                self.channels_view.flowbox.select_child(child)
                self.last_chan_selected = str(index)

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_Up(self):
        """Previous Line"""
        if self.last_chan_selected == "":
            # Find first patched channel
            for i in range(MAX_CHANNELS):
                if App().patch.channels[i][0] != [0, 0]:
                    break
            child = self.channels_view.flowbox.get_child_at_index(i)
            self.set_focus(child)
            self.channels_view.flowbox.select_child(child)
            self.last_chan_selected = str(i)
        else:
            child = self.channels_view.flowbox.get_child_at_index(
                int(self.last_chan_selected)
            )
            allocation = child.get_allocation()
            child = self.channels_view.flowbox.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            )
            if child:
                self.channels_view.flowbox.unselect_all()
                index = child.get_index()
                self.set_focus(child)
                self.channels_view.flowbox.select_child(child)
                self.last_chan_selected = str(index)

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_a(self):
        """All Channels"""
        self.channels_view.flowbox.unselect_all()

        for universe in range(NB_UNIVERSES):
            for output in range(512):
                level = App().dmx.frame[universe][output]
                channel = App().patch.outputs[universe][output][0] - 1
                if level > 0:
                    child = self.channels_view.flowbox.get_child_at_index(channel)
                    self.set_focus(child)
                    self.channels_view.flowbox.select_child(child)

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_c(self):
        """Channel"""
        self.channels_view.flowbox.unselect_all()

        if self.keystring != "" and self.keystring != "0":
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = self.channels_view.flowbox.get_child_at_index(channel)
                self.set_focus(child)
                self.channels_view.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_KP_Divide(self):
        """Thru"""
        self.thru()

    def _keypress_greater(self):
        """Thru"""
        self.thru()

    def thru(self):
        """Thru"""
        sel = self.channels_view.flowbox.get_selected_children()
        if len(sel) == 1:
            flowboxchild = sel[0]
            channelwidget = flowboxchild.get_children()[0]
            self.last_chan_selected = channelwidget.channel

        if not self.last_chan_selected:
            sel = self.channels_view.flowbox.get_selected_children()
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
                    child = self.channels_view.flowbox.get_child_at_index(channel)
                    self.set_focus(child)
                    self.channels_view.flowbox.select_child(child)
            else:
                for channel in range(to_chan - 1, int(self.last_chan_selected)):
                    child = self.channels_view.flowbox.get_child_at_index(channel)
                    self.set_focus(child)
                    self.channels_view.flowbox.select_child(child)

            self.last_chan_selected = self.keystring

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_KP_Add(self):
        """ + """
        self._keypress_plus()

    def _keypress_plus(self):
        """ + """
        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            child = self.channels_view.flowbox.get_child_at_index(channel)
            self.set_focus(child)
            self.channels_view.flowbox.select_child(child)
            self.last_chan_selected = self.keystring

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_KP_Subtract(self):
        """ - """
        self._keypress_minus()

    def _keypress_minus(self):
        """ - """
        if self.keystring == "":
            return

        channel = int(self.keystring) - 1
        if 0 <= channel < MAX_CHANNELS and App().patch.channels[channel][0] != [
            0,
            0,
        ]:
            child = self.channels_view.flowbox.get_child_at_index(channel)
            self.set_focus(child)
            self.channels_view.flowbox.unselect_child(child)
            self.last_chan_selected = self.keystring

        if App().track_channels_tab:
            App().track_channels_tab.update_display()

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_exclam(self):
        """ Level + (% level) of selected channels """
        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")
        if percent:
            lvl = round((lvl / 100) * 255)

        sel = self.channels_view.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    level = App().dmx.frame[univ][out - 1]
                    App().dmx.user[channel] = min(level + lvl, 255)

    def _keypress_colon(self):
        """ Level - (% level) of selected channels """
        lvl = App().settings.get_int("percent-level")
        percent = App().settings.get_boolean("percent")
        if percent:
            lvl = round((lvl / 100) * 255)

        sel = self.channels_view.flowbox.get_selected_children()

        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for channelwidget in children:
                channel = int(channelwidget.channel) - 1
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    level = App().dmx.frame[univ][out - 1]
                    App().dmx.user[channel] = max(level - lvl, 0)

    def _keypress_KP_Enter(self):
        """ @ Level """
        self._keypress_equal()

    def _keypress_equal(self):
        """ @ Level """
        if self.keystring == "":
            return

        level = int(self.keystring)

        sel = self.channels_view.flowbox.get_selected_children()

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

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_BackSpace(self):
        """ Empty keys buffer """
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_Escape(self):
        """ Unselect all channels """
        self.channels_view.flowbox.unselect_all()
        self.last_chan_selected = ""
        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_q(self):
        """ Seq - """
        App().sequence.sequence_minus()
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_w(self):
        """ Seq + """
        App().sequence.sequence_plus()
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_G(self):
        """ Goto """
        App().sequence.goto(self.keystring)
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_R(self):
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
                    if channel:
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
            self.playback.update_sequence_display()
            self.playback.update_xfade_display(step)
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
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_U(self):
        """ Update Cue """
        position = App().sequence.position
        memory = App().sequence.steps[position].cue.memory

        # Confirmation Dialog
        dialog = Dialog(self, memory)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = App().patch.outputs[univ][output][0] - 1
                    if channel not in App().independents.channels:
                        level = App().dmx.frame[univ][output]

                    App().sequence.steps[position].cue.channels[channel] = level

            # Tag filename as modified
            App().ascii.modified = True
            self.header.set_title(App().ascii.basename + "*")

        dialog.destroy()

    def _keypress_T(self):
        """Change Time In and Time Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_time(time)
        if time.is_integer():
            time = int(time)
        self.playback.cues_liststore1[position + 3][5] = str(time)
        self.playback.cues_liststore1[position + 3][7] = str(time)
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = App().sequence.steps[position + 1].time_in
        self.playback.sequential.time_out = App().sequence.steps[position + 1].time_out
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_I(self):
        """Change Time In of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_time_in(time)
        if time.is_integer():
            time = int(time)
        self.playback.cues_liststore1[position + 3][7] = str(time)
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = App().sequence.steps[position + 1].time_in
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_O(self):
        """Change Time Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_time_out(time)
        if time.is_integer():
            time = int(time)
        self.playback.cues_liststore1[position + 3][5] = str(time)
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_out = App().sequence.steps[position + 1].time_out
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_W(self):
        """Change Wait Time of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_wait(time)
        if time.is_integer():
            time = int(time)
        time = "" if time == 0 else str(time)
        self.playback.cues_liststore1[position + 3][3] = time
        self.playback.step_filter1.refilter()
        self.playback.sequential.wait = App().sequence.steps[position + 1].wait
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_D(self):
        """Change Delay In and Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_delay(time)
        if time.is_integer():
            time = int(time)
        time = "" if time == 0 else str(time)
        self.playback.cues_liststore1[position + 3][4] = time
        self.playback.cues_liststore1[position + 3][6] = time
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = App().sequence.steps[position + 1].delay_in
        self.playback.sequential.delay_out = (
            App().sequence.steps[position + 1].delay_out
        )
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_K(self):
        """Change Delay In of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_delay_in(time)
        if time.is_integer():
            time = int(time)
        time = "" if time == 0 else str(time)
        self.playback.cues_liststore1[position + 3][6] = time
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = App().sequence.steps[position + 1].delay_in
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_L(self):
        """Change Delay Out of next step"""
        if self.keystring == "":
            return

        position = App().sequence.position

        time = float(self.keystring)
        App().sequence.steps[position + 1].set_delay_out(time)
        if time.is_integer():
            time = int(time)
        time = "" if time == 0 else str(time)
        self.playback.cues_liststore1[position + 3][4] = time
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_out = (
            App().sequence.steps[position + 1].delay_out
        )
        self.playback.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)


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
