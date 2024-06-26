# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
from gi.repository import Gdk, Gio, Gtk
from olc.cue import Cue
from olc.define import MAX_CHANNELS, UNIVERSES, App, string_to_time, time_to_string
from olc.step import Step
from olc.widgets.main_fader import MainFaderWidget
from olc.window_channels import LiveView
from olc.window_playback import MainPlaybackView


class CommandLine:
    """Display keyboard entries"""

    def __init__(self):
        self.keystring = ""

        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("keypress")
        self.widget = Gtk.Grid()
        label = Gtk.Label("Input : ")
        self.widget.add(label)
        self.widget.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)

    def update(self) -> None:
        """Update Display"""
        self.statusbar.push(self.context_id, self.keystring)
        if App().osc:
            App().osc.client.send("/olc/command_line", ("s", self.keystring))

    def add_string(self, string: str) -> None:
        """Add string to displayed string

        Args:
            string: String to add
        """
        self.keystring += string
        self.update()

    def set_string(self, string: str) -> None:
        """Set string to display

        Args:
            string: String to display
        """
        self.keystring = string
        self.update()

    def get_string(self) -> str:
        """Return displayed string

        Returns:
            String
        """
        return self.keystring


class Window(Gtk.ApplicationWindow):
    """Main Window"""

    def __init__(self):
        # Full screen
        self.full = False

        super().__init__(title="Open Lighting Console", application=App())
        self.set_default_size(1400, 1080)
        self.set_name("olc")
        self.connect("delete-event", App().exit)

        # Header Bar
        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("")
        self.header.props.show_close_button = True
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Main Fader viewer
        self.main_fader = MainFaderWidget()
        box.add(self.main_fader)
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
        self.live_view = LiveView()
        paned_chan = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned_chan.set_position(1100)
        paned_chan.pack1(self.live_view, resize=True, shrink=False)
        # Gtk.Statusbar to display keyboard's keys
        self.commandline = CommandLine()
        paned_chan.pack2(self.commandline.widget, resize=True, shrink=False)
        paned.pack1(paned_chan, resize=True, shrink=False)

        # Main Playback
        self.playback = MainPlaybackView()
        paned.pack2(self.playback, resize=True, shrink=False)

        self.add(paned)

        self.set_icon_name("olc")

    def get_active_tab(self) -> Gtk.Widget:
        """Get active tab

        Returns:
            Active tab
        """
        widget = self.get_focus()
        while widget:
            if widget in (self.live_view, self.playback):
                break
            widget = widget.get_parent()
        return widget.get_nth_page(widget.get_current_page())

    def toggle_focus(self) -> None:
        """Toggle focus Left/Right"""
        focus = self.get_focus()
        if focus is self.live_view:
            self.playback.grab_focus()
        else:
            self.live_view.grab_focus()

    def fullscreen_toggle(self, _action, _param):
        """Toggle full screen"""
        if self.full:
            self.unfullscreen()
            self.full = False
        else:
            self.fullscreen()
            self.full = True

    def move_tab(self) -> None:
        """Move focused tab on next notebook"""
        focus = self.get_focus()
        page = focus.get_current_page()
        child = focus.get_nth_page(page)
        label = focus.get_tab_label(child)
        if focus is self.live_view:
            self.live_view.detach_tab(child)
            self.playback.append_page(child, label)
            self.playback.set_current_page(-1)
        else:
            self.playback.detach_tab(child)
            self.live_view.append_page(child, label)
            self.live_view.set_current_page(-1)

    def update_channels_display(self, step):
        """Update Channels levels display

        Args:
            step: Step
        """
        for channel in range(1, MAX_CHANNELS + 1):
            level = App().lightshow.main_playback.steps[step].cue.channels.get(
                channel, 0)
            next_level = App().lightshow.main_playback.steps[step + 1].cue.channels.get(
                channel, 0)
            widget = self.live_view.channels_view.get_channel_widget(channel)
            widget.level = level
            widget.next_level = next_level
            widget.queue_draw()

    def on_key_press_event(self, _widget, event):
        """Executed on key press event

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        keyname = Gdk.keyval_name(event.keyval)
        # print(keyname)
        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.commandline.add_string(keyname)

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
            self.commandline.add_string(keyname[3:])

        if keyname == "period":
            self.commandline.add_string(".")

        # Channels View
        self.live_view.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname}", None):
            return func()
        return False

    def _keypress_exclam(self):
        """Level + (% level) of selected channels"""
        self.live_view.channels_view.level_plus()

    def _keypress_colon(self):
        """Level - (% level) of selected channels"""
        self.live_view.channels_view.level_minus()

    def _keypress_KP_Enter(self):  # pylint: disable=C0103
        """@ Level"""
        self._keypress_equal()

    def _keypress_equal(self):
        """@ Level"""
        self.live_view.channels_view.at_level()
        self.commandline.set_string("")

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        """Empty keys buffer"""
        self.commandline.set_string("")

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Deselect all channels"""
        self.live_view.channels_view.flowbox.unselect_all()
        self.live_view.channels_view.last_selected_channel = ""
        if App().tabs.tabs["track_channels"]:
            App().tabs.tabs["track_channels"].update_display()

    def _keypress_q(self):
        """Seq -"""
        App().lightshow.main_playback.sequence_minus()
        self.commandline.set_string("")

    def _keypress_w(self):
        """Seq +"""
        App().lightshow.main_playback.sequence_plus()
        self.commandline.set_string("")

    def _keypress_G(self):  # pylint: disable=C0103
        """Goto"""
        App().lightshow.main_playback.goto(self.commandline.get_string())
        self.commandline.set_string("")

    def _keypress_R(self):  # pylint: disable=C0103
        """Record new Step and new Preset"""
        found = False
        keystring = self.commandline.get_string()
        if keystring == "":
            # Find next free Cue
            position = App().lightshow.main_playback.position
            mem = App().lightshow.main_playback.get_next_cue(step=position)
            step = position + 1
        else:
            # Use given number
            mem = float(keystring)
            found, step = App().lightshow.main_playback.get_step(cue=mem)

        if not found:
            # Create Preset
            channels = {}
            for channel, outputs in App().lightshow.patch.channels.items():
                if not App().lightshow.patch.is_patched(channel):
                    continue
                for values in outputs:
                    output = values[0]
                    univ = values[1]
                    index = UNIVERSES.index(univ)
                    if level := App().backend.dmx.frame[index][output - 1]:
                        channels[channel] = level
            cue = Cue(1, mem, channels)
            App().lightshow.cues.insert(step - 1, cue)

            # Update Presets Tab if exist
            if App().tabs.tabs["memories"]:
                nb_chan = len(channels)
                App().tabs.tabs["memories"].liststore.insert(step - 1,
                                                             [str(mem), "", nb_chan])

            App().lightshow.main_playback.position = step

            # Create Step
            step_object = Step(1, cue=cue)
            App().lightshow.main_playback.insert_step(step, step_object)

            # Update Main Playback
            self.playback.update_sequence_display()
            self.playback.update_xfade_display(step)
            self.update_channels_display(step)
        else:  # Update Preset
            # Find Preset position
            found = False
            i = 0
            for i, item in enumerate(App().lightshow.cues):
                if item.memory > mem:
                    found = True
                    break
            i -= 1

            for univ in UNIVERSES:
                for output in range(512):
                    channel = App().lightshow.patch.outputs[univ][output + 1][0]
                    index = UNIVERSES.index(univ)
                    level = App().backend.dmx.frame[index][output]

                    App().lightshow.cues[i].channels[channel - 1] = level

            # Update Presets Tab if exist
            if App().tabs.tabs["memories"]:
                nb_chan = sum(
                    bool(App().lightshow.cues[i].channels[chan])
                    for chan in range(MAX_CHANNELS))

                treeiter = App().tabs.tabs["memories"].liststore.get_iter(i)
                App().tabs.tabs["memories"].liststore.set_value(treeiter, 2, nb_chan)
                App().tabs.tabs["memories"].channels_view.update()

        # Update Sequential edition Tabs
        if App().tabs.tabs["sequences"]:
            # Main Playback selected ?
            path, _focus_column = App().tabs.tabs["sequences"].treeview1.get_cursor()
            if path:
                selected = path.get_indices()[0]
                sequence = App().tabs.tabs["sequences"].liststore1[selected][0]
                if sequence == App().lightshow.main_playback.index:
                    # Yes, update it
                    App().tabs.tabs["sequences"].on_sequence_changed()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_U(self):  # pylint: disable=C0103
        """Update Cue"""
        position = App().lightshow.main_playback.position
        memory = App().lightshow.main_playback.steps[position].cue.memory

        # Confirmation Dialog
        dialog = Dialog(self, memory)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            for channel, outputs in App().lightshow.patch.channels.items():
                if not App().lightshow.patch.is_patched(channel):
                    continue
                if channel not in App().lightshow.independents.channels:
                    output = outputs[0][0] - 1
                    univ = outputs[0][1]
                    index = UNIVERSES.index(univ)
                    level = App().backend.dmx.frame[index][output]
                    App().lightshow.main_playback.steps[position].cue.channels[
                        channel] = level

            # Tag filename as modified
            App().lightshow.set_modified()

        dialog.destroy()

    def _keypress_T(self):  # pylint: disable=C0103
        """Change Time In and Time Out of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_time(time)
        self.playback.cues_liststore1[position + 3][5] = string
        self.playback.cues_liststore1[position + 3][7] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = App().lightshow.main_playback.steps[
            position + 1].time_in
        self.playback.sequential.time_out = App().lightshow.main_playback.steps[
            position + 1].time_out
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_I(self):  # pylint: disable=C0103
        """Change Time In of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_time_in(time)
        self.playback.cues_liststore1[position + 3][7] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = App().lightshow.main_playback.steps[
            position + 1].time_in
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_O(self):  # pylint: disable=C0103
        """Change Time Out of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_time_out(time)
        self.playback.cues_liststore1[position + 3][5] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_out = App().lightshow.main_playback.steps[
            position + 1].time_out
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_W(self):  # pylint: disable=C0103
        """Change Wait Time of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_wait(time)
        self.playback.cues_liststore1[position + 3][3] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.wait = App().lightshow.main_playback.steps[position +
                                                                            1].wait
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_D(self):  # pylint: disable=C0103
        """Change Delay In and Out of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_delay(time)
        self.playback.cues_liststore1[position + 3][4] = string
        self.playback.cues_liststore1[position + 3][6] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = App().lightshow.main_playback.steps[
            position + 1].delay_in
        self.playback.sequential.delay_out = (
            App().lightshow.main_playback.steps[position + 1].delay_out)
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_K(self):  # pylint: disable=C0103
        """Change Delay In of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_delay_in(time)
        self.playback.cues_liststore1[position + 3][6] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = App().lightshow.main_playback.steps[
            position + 1].delay_in
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")

    def _keypress_L(self):  # pylint: disable=C0103
        """Change Delay Out of next step"""
        keystring = self.commandline.get_string()
        if keystring == "":
            return

        position = App().lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        App().lightshow.main_playback.steps[position + 1].set_delay_out(time)
        self.playback.cues_liststore1[position + 3][4] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_out = (
            App().lightshow.main_playback.steps[position + 1].delay_out)
        self.playback.sequential.total_time = (
            App().lightshow.main_playback.steps[position + 1].total_time)
        self.playback.grid.queue_draw()

        # Tag filename as modified
        App().lightshow.set_modified()

        self.commandline.set_string("")


class Dialog(Gtk.Dialog):
    """Confirmation dialog when update Cue"""

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

        label = Gtk.Label(f"Update memory {memory} ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()
