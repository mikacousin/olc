# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
import array

from gi.repository import Gdk, Gio, Gtk
from olc.cue import Cue
from olc.define import MAX_CHANNELS, App
from olc.step import Step
from olc.widgets.grand_master import GMWidget
from olc.window_channels import LiveView
from olc.window_playback import MainPlaybackView


class Window(Gtk.ApplicationWindow):
    """Main Window"""

    def __init__(self):

        # Fullscreen
        self.full = False

        self.keystring = ""

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

    def toggle_focus(self) -> None:
        """Toggle focus Left/Right"""
        focus = self.get_focus()
        if focus == self.live_view:
            self.playback.grab_focus()
        else:
            self.live_view.grab_focus()

    def fullscreen_toggle(self, _action, _param):
        """Toggle fullscreen"""
        if self.full:
            self.unfullscreen()
            self.full = False
        else:
            self.fullscreen()
            self.full = True

    def update_channels_display(self, step):
        """Update Channels levels display

        Args:
            step: Step
        """
        for channel in range(MAX_CHANNELS):
            level = App().sequence.steps[step].cue.channels[channel]
            next_level = App().sequence.steps[step + 1].cue.channels[channel]
            widget = self.live_view.channels_view.get_channel_widget(channel + 1)
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

        # Channels View
        self.keystring = self.live_view.channels_view.on_key_press(
            keyname, self.keystring
        )

        if func := getattr(self, "_keypress_" + keyname, None):
            return func()
        return False

    def _keypress_exclam(self):
        """Level + (% level) of selected channels"""
        channels = self.live_view.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            for channel in channels:
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][out - 1]
                    App().dmx.user[channel - 1] = min(level + step_level, 255)

    def _keypress_colon(self):
        """Level - (% level) of selected channels"""
        channels = self.live_view.channels_view.get_selected_channels()
        step_level = App().settings.get_int("percent-level")
        if App().settings.get_boolean("percent"):
            step_level = round((step_level / 100) * 255)
        if channels and step_level:
            for channel in channels:
                for output in App().patch.channels[channel]:
                    out = output[0]
                    univ = output[1]
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][out - 1]
                    App().dmx.user[channel - 1] = max(level - step_level, 0)

    def _keypress_KP_Enter(self):  # pylint: disable=C0103
        """@ Level"""
        self._keypress_equal()

    def _keypress_equal(self):
        """@ Level"""
        channels, level = self.live_view.channels_view.at_level(self.keystring)
        if channels and level != -1:
            for channel in channels:
                App().dmx.user[channel - 1] = level
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        """Empty keys buffer"""
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Unselect all channels"""
        self.live_view.channels_view.flowbox.unselect_all()
        self.live_view.channels_view.last_selected_channel = ""
        if App().track_channels_tab:
            App().track_channels_tab.update_display()

    def _keypress_q(self):
        """Seq -"""
        App().sequence.sequence_minus()
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_w(self):
        """Seq +"""
        App().sequence.sequence_plus()
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_G(self):  # pylint: disable=C0103
        """Goto"""
        App().sequence.goto(self.keystring)
        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_R(self):  # pylint: disable=C0103
        """Record new Step and new Preset"""
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
            for channel, outputs in App().patch.channels.items():
                for values in outputs:
                    output = values[0]
                    univ = values[1]
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][output - 1]
                    channels[channel - 1] = level
            cue = Cue(1, mem, channels)
            App().memories.insert(step - 1, cue)

            # Update Presets Tab if exist
            if App().memories_tab:
                nb_chan = sum(1 for chan in range(MAX_CHANNELS) if channels[chan])
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

            for univ in App().universes:
                for output in range(512):
                    channel = App().patch.outputs[univ][output + 1][0]
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][output]

                    App().memories[i].channels[channel - 1] = level

            # Update Presets Tab if exist
            if App().memories_tab:
                nb_chan = sum(
                    bool(App().memories[i].channels[chan])
                    for chan in range(MAX_CHANNELS)
                )

                treeiter = App().memories_tab.liststore.get_iter(i)
                App().memories_tab.liststore.set_value(treeiter, 2, nb_chan)
                App().memories_tab.channels_view.update()

        # Update Sequential edition Tabs
        if App().sequences_tab:
            # Main Playback selected ?
            path, _focus_column = App().sequences_tab.treeview1.get_cursor()
            if path:
                selected = path.get_indices()[0]
                sequence = App().sequences_tab.liststore1[selected][0]
                if sequence == App().sequence.index:
                    # Yes, update it
                    App().sequences_tab.on_sequence_changed()

        # Tag filename as modified
        App().ascii.modified = True
        self.header.set_title(App().ascii.basename + "*")

        self.keystring = ""
        self.statusbar.push(self.context_id, self.keystring)

    def _keypress_U(self):  # pylint: disable=C0103
        """Update Cue"""
        position = App().sequence.position
        memory = App().sequence.steps[position].cue.memory

        # Confirmation Dialog
        dialog = Dialog(self, memory)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            for channel, outputs in App().patch.channels.items():
                if channel not in App().independents.channels:
                    output = outputs[0][0] - 1
                    univ = outputs[0][1]
                    index = App().universes.index(univ)
                    level = App().dmx.frame[index][output]
                    App().sequence.steps[position].cue.channels[channel - 1] = level

            # Tag filename as modified
            App().ascii.modified = True
            self.header.set_title(App().ascii.basename + "*")

        dialog.destroy()

    def _keypress_T(self):  # pylint: disable=C0103
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

    def _keypress_I(self):  # pylint: disable=C0103
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

    def _keypress_O(self):  # pylint: disable=C0103
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

    def _keypress_W(self):  # pylint: disable=C0103
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

    def _keypress_D(self):  # pylint: disable=C0103
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

    def _keypress_K(self):  # pylint: disable=C0103
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

    def _keypress_L(self):  # pylint: disable=C0103
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

        label = Gtk.Label("Update memory " + str(memory) + " ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()
