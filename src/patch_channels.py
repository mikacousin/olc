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
from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, App
from olc.widgets_patch_channels import PatchChannelHeader, PatchChannelWidget


class PatchChannelsTab(Gtk.Box):
    """Tab to patch by channels"""

    def __init__(self):

        self.keystring = ""
        self.last_chan_selected = ""

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        header = PatchChannelHeader()

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []

        for channel in range(MAX_CHANNELS):
            self.channels.append(PatchChannelWidget(channel + 1, App().patch))
            self.flowbox.add(self.channels[channel])

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        self.pack_start(header, False, False, 2)
        self.pack_start(self.scrollable, True, True, 0)

        child = self.flowbox.get_child_at_index(0)
        self.flowbox.select_child(child)
        self.last_chan_selected = "0"

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        page = App().window.playback.page_num(self)
        App().window.playback.remove_page(page)
        App().patch_channels_tab = None

    def on_key_press_event(self, _widget, event):
        """Key press events

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        # Hack to know if user is editing something
        widget = App().window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
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

        if func := getattr(self, "_keypress_" + keyname, None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        page = App().window.playback.get_current_page()
        App().window.playback.remove_page(page)
        App().patch_channels_tab = None

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Down(self):  # pylint: disable=C0103
        """Select Next Channel"""

        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"
        elif int(self.last_chan_selected) < MAX_CHANNELS - 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) + 1)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) + 1)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Up(self):  # pylint: disable=C0103
        """Select Previous Channel"""
        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"
        elif int(self.last_chan_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) - 1)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(int(self.last_chan_selected) - 1)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_c(self):
        """Select Channel"""
        self.flowbox.unselect_all()

        if self.keystring != "" and "." not in self.keystring:
            channel = int(self.keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = self.flowbox.get_child_at_index(channel)
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):  # pylint: disable=C0103
        """Thru"""
        self.thru()

    def _keypress_greater(self):
        """Thru"""
        self.thru()

    def thru(self):
        """Thru"""
        # If one channel is selected, start from it
        selected = self.flowbox.get_selected_children()
        if len(selected) == 1:
            patchwidget = selected[0].get_child()
            channel = patchwidget.channel - 1
            self.last_chan_selected = str(channel)

        if not self.last_chan_selected:
            return

        to_chan = int(self.keystring)

        if to_chan > int(self.last_chan_selected):
            for chan in range(int(self.last_chan_selected), to_chan):
                child = self.flowbox.get_child_at_index(chan)
                self.flowbox.select_child(child)
        else:
            for chan in range(to_chan - 1, int(self.last_chan_selected)):
                child = self.flowbox.get_child_at_index(chan)
                self.flowbox.select_child(child)
        self.last_chan_selected = str(to_chan - 1)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_m(self):
        """Modify Output"""
        sel = self.flowbox.get_selected_children()
        several = len(sel) > 1
        for i, flowboxchild in enumerate(sel):
            patchchannelwidget = flowboxchild.get_child()
            channel = patchchannelwidget.channel

            # Unpatch if no entry
            if self.keystring in ["", "0"]:
                for item in App().patch.channels[channel]:
                    output = item[0]
                    universe = item[1]
                    App().patch.unpatch(channel, output, universe)
                # Update ui
                self.channels[channel].queue_draw()
            else:
                # New values
                if "." in self.keystring:
                    if self.keystring[0] == ".":
                        # ".universe" for change universe
                        output = App().patch.channels[channel][0][0]
                        universe = int(self.keystring[1:])
                        several = False
                    else:
                        # "output.universe"
                        split = self.keystring.split(".")
                        output = int(split[0])
                        universe = int(split[1])
                else:
                    # "output", use first universe
                    output = int(self.keystring)
                    universe = App().universes[0]

                if 0 < output + i <= 512:
                    # Unpatch old values
                    if channel in App().patch.channels:
                        for item in App().patch.channels[channel]:
                            out = item[0]
                            univ = item[1]
                            App().patch.unpatch(channel, out, univ)
                    if (
                        universe in App().patch.outputs
                        and output + i in App().patch.outputs[universe]
                    ):
                        old_channel = App().patch.outputs[universe][output + i][0]
                        App().patch.unpatch(old_channel, output + i, universe)
                        # Update ui
                        self.channels[old_channel - 1].queue_draw()
                    # Patch
                    if several:
                        App().patch.add_output(channel, output + i, universe)
                    else:
                        App().patch.add_output(channel, output, universe)
                    # Update ui
                    self.channels[channel - 1].queue_draw()

            # Update list of channels
            index = App().universes.index(universe)
            level = App().dmx.frame[index][output]
            widget = App().window.live_view.channels_view.get_channel_widget(channel)
            widget.level = level
            widget.queue_draw()
            App().window.live_view.channels_view.update()

        # Select next channel
        if sel and channel < MAX_CHANNELS:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(channel)
            self.flowbox.select_child(child)
            self.last_chan_selected = str(channel)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_i(self):
        """Insert Output"""
        if self.keystring in ["", "0"]:
            return
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            patchchannelwidget = flowboxchild.get_child()
            channel = patchchannelwidget.channel

            # New values
            if "." in self.keystring:
                if self.keystring[0] == ".":
                    # ".universe" for change universe
                    output = App().patch.channels[channel][0][0]
                    universe = int(self.keystring[1:])
                else:
                    # "output.universe"
                    split = self.keystring.split(".")
                    output = int(split[0])
                    universe = int(split[1])
            else:
                # "output", use first universe
                output = int(self.keystring)
                universe = App().universes[0]

            if 0 < output <= 512:
                # Unpatch old value
                if (
                    universe in App().patch.outputs
                    and output in App().patch.outputs[universe]
                ):
                    old_channel = App().patch.outputs[universe][output][0]
                    App().patch.unpatch(old_channel, output, universe)
                    self.channels[old_channel - 1].queue_draw()
                # Patch
                App().patch.add_output(channel, output, universe)
                # Update ui
                self.channels[channel - 1].queue_draw()

                # Update list of channels
                widget = App().window.live_view.channels_view.get_channel_widget(
                    channel
                )
                widget.queue_draw()
                App().window.live_view.channels_view.update()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_r(self):
        """Remove Output"""
        if self.keystring in ["", "0"]:
            return
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            patchchannelwidget = flowboxchild.get_child()
            channel = patchchannelwidget.channel
            if "." in self.keystring:
                if self.keystring[0] != ".":
                    # "output.universe"
                    split = self.keystring.split(".")
                    output = int(split[0])
                    universe = int(split[1])
            else:
                # "output", use first universe
                output = int(self.keystring)
                universe = App().universes[0]

            if (
                0 < output <= 512
                and [output, universe] in App().patch.channels[channel]
            ):
                # Remove Output
                App().patch.unpatch(channel, output, universe)
                # Update ui
                self.channels[channel - 1].queue_draw()

            # Update list of channels
            widget = App().window.live_view.channels_view.get_channel_widget(channel)
            widget.queue_draw()
            App().window.live_view.channels_view.update()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
