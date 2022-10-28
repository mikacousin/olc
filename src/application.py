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
import select
import sys
from gettext import gettext as _
import mido

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from olc.ascii import Ascii  # noqa: E402
from olc.channel_time import ChanneltimeTab  # noqa: E402
from olc.crossfade import CrossFade  # noqa: E402
from olc.cues_edition import CuesEditionTab  # noqa: E402
from olc.define import MAX_CHANNELS, MAX_FADER_PAGE, UNIVERSES  # noqa: E402
from olc.dmx import Dmx, PatchDmx  # noqa: E402
from olc.enttec_wing import WingPlayback  # noqa: E402
from olc.group import GroupTab  # noqa: E402
from olc.independent import Independents  # noqa: E402
from olc.independents_edition import IndependentsTab  # noqa: E402
from olc.master import Master  # noqa: E402
from olc.masters_edition import MastersTab  # noqa: E402
from olc.midi import Midi  # noqa: E402
from olc.ola_thread import OlaThread  # noqa: E402
from olc.osc import OscServer  # noqa: E402
from olc.patch_channels import PatchChannelsTab  # noqa: E402
from olc.patch_outputs import PatchOutputsTab  # noqa: E402
from olc.sequence import Sequence  # noqa: E402
from olc.sequence_edition import SequenceTab  # noqa: E402
from olc.settings import SettingsDialog  # noqa: E402
from olc.track_channels import TrackChannelsTab  # noqa: E402
from olc.virtual_console import VirtualConsoleWindow  # noqa: E402
from olc.window import Window  # noqa: E402


class Application(Gtk.Application):
    """Application Class"""

    def __init__(self):
        Gtk.Application.__init__(
            self,
            application_id="com.github.mikacousin.olc",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        GLib.set_application_name("OpenLightingConsole")
        GLib.set_prgname("olc")

        css_provider_file = Gio.File.new_for_uri(
            "resource://com/github/mikacousin/olc/application.css"
        )
        css_provider = Gtk.CssProvider()
        css_provider.load_from_file(css_provider_file)
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        # Change to dark theme
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        # To store settings
        # self.settings = Settings.new()
        self.settings = Gio.Settings.new("com.github.mikacousin.olc")

        # Universes
        self.universes = UNIVERSES
        # Create patch (1:1)
        self.patch = PatchDmx(self.universes)

        # Create OlaClient
        try:
            self.ola_thread = OlaThread()
        except Exception as e:
            print("Can't connect to Ola !", e)
            sys.exit()
        self.ola_thread.start()

        # Create Main Playback
        self.sequence = Sequence(1, text="Main Playback")

        # Create List of Global Memories
        self.memories = []

        # Create List for Chasers
        self.chasers = []

        # Create List of Groups
        self.groups = []

        # Create pages of 10 Masters
        self.masters = []
        for page in range(MAX_FADER_PAGE):
            for i in range(10):
                self.masters.append(Master(page + 1, i + 1, 0, 0))
        self.fader_page = 1

        # Independents
        self.independents = Independents()

        # For Windows
        self.window = None
        self.about_window = None
        self.virtual_console = None
        self.win_settings = None
        self.shortcuts = None

        # For Tabs
        self.patch_outputs_tab = None
        self.patch_channels_tab = None
        self.masters_tab = None
        self.memories_tab = None
        self.group_tab = None
        self.sequences_tab = None
        self.channeltime_tab = None
        self.track_channels_tab = None
        self.inde_tab = None

        self.dmx = None
        self.crossfade = None
        self.midi = None
        self.osc_server = None
        self.ascii = None
        self.file = None
        self.wing = None

    def do_activate(self):

        # Create Main Window
        self.window = Window()
        self.window.show_all()
        # No selected channel on startup
        self.window.channels_view.flowbox.unselect_all()

        # Maximize window on startup
        self.window.maximize()

        # Add global shortcuts
        # Go
        action = Gio.SimpleAction.new("go", None)
        action.connect("activate", self.sequence.do_go)
        self.add_action(action)
        self.set_accels_for_action("app.go", ["<Control>g"])
        # Go Back
        action = Gio.SimpleAction.new("go_back", None)
        action.connect("activate", self.sequence.go_back)
        self.add_action(action)
        self.set_accels_for_action("app.go_back", ["<Control>b"])
        # Pause
        action = Gio.SimpleAction.new("pause", None)
        action.connect("activate", self.sequence.pause)
        self.add_action(action)
        self.set_accels_for_action("app.pause", ["<Control>z"])
        # Fullscreen
        action = Gio.SimpleAction.new("fullscreen", None)
        action.connect("activate", self.window.fullscreen_toggle)
        self.add_action(action)

        # Create several DMX arrays
        self.dmx = Dmx()
        self.dmx.start()

        # Fetch dmx values on startup
        for univ in self.universes:
            self.ola_thread.ola_client.FetchDmx(univ, self.fetch_dmx)

        # For Manual crossfade
        self.crossfade = CrossFade()

        # Open MIDI Inputs and Outputs
        self.midi = Midi()
        # Reset Mackie Control Faders
        for outport in self.midi.ports.outports:
            for i in range(16):
                msg = mido.Message("pitchwheel", channel=i, pitch=-8192, time=0)
                outport.send(msg)

        # Init Enttec Wing Playback
        self.wing = WingPlayback()

        # Create and launch OSC server
        self.osc_server = OscServer()

        # Init of ascii file
        self.ascii = Ascii(None)

        # Send DMX every 50ms
        GObject.timeout_add(50, self._on_timeout, None)

        # Scan Ola messages - 27 = IN(1) + HUP(16) + PRI(2) + ERR(8)
        GLib.unix_fd_add_full(
            0,
            self.ola_thread.sock.fileno(),
            GLib.IOCondition(27),
            self.on_fd_read,
            None,
        )

    def _on_timeout(self, _user_data):
        """Executed every timeout

        Returns:
            True
        """
        # Send DMX
        self.dmx.send()
        return True

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # General shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.open", ["<Control>o"])
        self.set_accels_for_action("app.save", ["<Control>s"])
        self.set_accels_for_action("app.save_as", ["<Shift><Control>s"])
        self.set_accels_for_action("app.patch_outputs", ["<Control>p"])
        self.set_accels_for_action("app.patch_channels", ["<Shift><Control>p"])
        self.set_accels_for_action("app.groups", ["<Shift><Control>g"])
        self.set_accels_for_action("app.sequences", ["<Control>t"])
        self.set_accels_for_action("app.masters", ["<Control>m"])
        self.set_accels_for_action("app.track_channels", ["<Shift><Control>t"])
        self.set_accels_for_action("app.independents", ["<Control>i"])
        self.set_accels_for_action("app.virtual_console", ["<Shift><Control>c"])
        self.set_accels_for_action("app.about", ["F3"])
        self.set_accels_for_action("app.fullscreen", ["F11"])

    def setup_app_menu(self):
        """Setup application menu

        Returns:
            Gio.Menu
        """
        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/menus.ui")
        menu = builder.get_object("app-menu")
        actions = {
            "new": "_new",
            "open": "_open",
            "save": "_save",
            "save_as": "_saveas",
            "patch_outputs": "patch_outputs",
            "patch_channels": "_patch_channels",
            "memories": "memories_cb",
            "groups": "groups_cb",
            "sequences": "sequences",
            "masters": "_masters",
            "track_channels": "track_channels",
            "independents": "_independents",
            "virtual_console": "_virtual_console",
            "settings": "_settings",
            "show-help-overlay": "_shortcuts",
            "about": "_about",
            "quit": "_exit",
        }
        for name, func in actions.items():
            function = getattr(self, func, None)
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", function)
            self.add_action(action)
        return menu

    def on_fd_read(self, _fd, _condition, _data):
        """Ola messages

        Returns:
            True
        """
        readable, _writable, _exceptional = select.select(
            [self.ola_thread.sock], [], [], 0
        )
        if readable:
            self.ola_thread.ola_client.SocketReady()
        return True

    def fetch_dmx(self, _request, univ, dmxframe):
        """Fetch DMX

        Args:
            univ: DMX universe
            dmxframe: List of DMX data
        """
        if not dmxframe:
            return
        index = self.universes.index(univ)
        self.ola_thread.old_frame[index] = dmxframe
        for output, level in enumerate(dmxframe):
            if univ in self.patch.outputs and output + 1 in self.patch.outputs[univ]:
                channel = self.patch.outputs.get(univ).get(output + 1)[0] - 1
                self.dmx.frame[index][output] = level
                if (
                    self.sequence.last > 1
                    and self.sequence.position < self.sequence.last
                ):
                    next_level = self.sequence.steps[
                        self.sequence.position + 1
                    ].cue.channels[channel]
                elif self.sequence.last:
                    next_level = self.sequence.steps[0].cue.channels[channel]
                else:
                    next_level = level
                self.window.channels_view.update_channel_widget(
                    channel, level, next_level
                )
                if self.patch_outputs_tab:
                    self.patch_outputs_tab.outputs[output + (512 * index)].queue_draw()

    def _new(self, _action, _parameter):
        """New show"""
        # Stop Chasers
        for chaser in self.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        # All channels at 0
        for channel in range(MAX_CHANNELS):
            self.dmx.user[channel] = 0
        self.window.channels_view.flowbox.unselect_all()
        # Reset Patch
        self.patch.patch_1on1()
        # Reset Main Playback
        self.sequence = Sequence(1, "Main Playback")
        self.sequence.position = 0
        self.sequence.window = self.window
        # Delete memories, groups, chasers, masters
        del self.memories[:]
        del self.groups[:]
        del self.chasers[:]
        del self.masters[:]
        self.fader_page = 1
        for page in range(MAX_FADER_PAGE):
            for i in range(10):
                self.masters.append(Master(page + 1, i + 1, 0, 0))
        self.independents = Independents()
        # Redraw Sequential Window
        self.window.playback.update_sequence_display()
        self.window.playback.update_xfade_display(self.sequence.position)
        # Turn off all channels
        self.dmx.send()
        self.window.update_channels_display(self.sequence.position)

        # Redraw Patch Tabs
        if self.patch_outputs_tab:
            self.patch_outputs_tab.flowbox.queue_draw()
        if self.patch_channels_tab:
            self.patch_channels_tab.flowbox.queue_draw()

        # Redraw Group Tab
        if self.group_tab:
            # Remove old groups
            self.group_tab.scrolled.remove(self.group_tab.flowbox)
            self.group_tab.flowbox.destroy()
            # Update Group Tab
            self.group_tab.populate_tab()
            self.group_tab.channels_view.flowbox.invalidate_filter()
            self.group_tab.flowbox.invalidate_filter()
            self.window.show_all()

        # Redraw Memories Tab
        if self.memories_tab:
            self.memories_tab.liststore.clear()
            # Select first Memory
            path = Gtk.TreePath.new_first()
            self.memories_tab.treeview.set_cursor(path, None, False)
            for mem in self.memories:
                channels = sum(1 for chan in range(MAX_CHANNELS) if mem.channels[chan])
                self.memories_tab.liststore.append(
                    [str(mem.memory), mem.text, channels]
                )
            self.memories_tab.flowbox.invalidate_filter()

        # Redraw Masters in Virtual Console
        if self.virtual_console and self.virtual_console.props.visible:
            self.virtual_console.page_number.set_label(str(self.fader_page))
            for master in self.masters:
                if master.page == self.fader_page:
                    text = "master_" + str(master.number + ((self.fader_page - 1) * 10))
                    self.virtual_console.masters[master.number - 1].text = text
                    self.virtual_console.masters[master.number - 1].set_value(
                        master.value
                    )
                    self.virtual_console.flashes[master.number - 1].label = master.text
            self.virtual_console.masters_pad.queue_draw()

        # Redraw Sequences Tab
        if self.sequences_tab:
            self.sequences_tab.liststore1.clear()

            self.sequences_tab.liststore1.append(
                [self.sequence.index, self.sequence.type_seq, self.sequence.text]
            )

            for chaser in self.chasers:
                self.sequences_tab.liststore1.append(
                    [chaser.index, chaser.type_seq, chaser.text]
                )

            self.sequences_tab.treeview1.set_model(self.sequences_tab.liststore1)
            path = Gtk.TreePath.new_first()
            self.sequences_tab.treeview1.set_cursor(path, None, False)
            selection = self.sequences_tab.treeview1.get_selection()
            self.sequences_tab.on_sequence_changed(selection)

        # Redraw Masters Tab
        if self.masters_tab:
            self.masters_tab.liststore.clear()
            self.masters_tab.populate_tab()
            self.masters_tab.flowbox.invalidate_filter()

        # Redraw Channel Time Tab
        if self.channeltime_tab:
            self.channeltime_tab.liststore.clear()
            self.channeltime_tab.flowbox.invalidate_filter()

        # Redraw Track Channels
        if self.track_channels_tab:
            self.track_channels_tab.populate_steps()
            self.track_channels_tab.flowbox.invalidate_filter()
            self.track_channels_tab.show_all()
            self.track_channels_tab.update_display()

        # Redraw Independents Tab
        if self.inde_tab:
            self.inde_tab.liststore.clear()
            for inde in self.independents.independents:
                self.inde_tab.liststore.append([inde.number, inde.inde_type, inde.text])
            path = Gtk.TreePath.new_first()
            self.inde_tab.treeview.set_cursor(path, None, False)

        self.window.channels_view.grab_focus()
        self.window.last_chan_selected = ""

    def _open(self, _action, _parameter):
        """create a filechooserdialog to open:
        the arguments are: title of the window, parent_window, action,
        (buttons, response)
        """
        open_dialog = Gtk.FileChooserNative.new(
            _("Open ASCII File"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Open"),
            _("Cancel"),
        )

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text Files")
        filter_text.add_mime_type("text/plain")
        open_dialog.add_filter(filter_text)

        # not only local files can be selected in the file selector
        open_dialog.set_local_only(False)
        # dialog always on top
        open_dialog.set_modal(True)
        # show the dialog
        response = open_dialog.run()

        # if response is "ACCEPT" (the button "Open" has been clicked)
        if response == Gtk.ResponseType.ACCEPT:
            # self.file is the file that we get from the FileChooserNative
            self.file = open_dialog.get_file()

            # Load the ASCII file
            self.ascii.file = self.file
            self.ascii.load()

            for univ in self.universes:
                self.ola_thread.ola_client.FetchDmx(univ, self.fetch_dmx)

        elif response == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.OPEN")

        # destroy the FileChooserNative
        open_dialog.destroy()

    def _save(self, _action, _parameter):
        """Save"""
        if self.file is not None:
            self.ascii.save()
        else:
            self._saveas(_action, _parameter)

    def _saveas(self, _action, _parameter):
        """Save as"""
        save_dialog = Gtk.FileChooserNative.new(
            _("Save ASCII file"),
            self.window,
            Gtk.FileChooserAction.SAVE,
            _("Save"),
            _("Cancel"),
        )
        # the dialog will present a confirmation dialog if the user types a file name
        # that already exists
        save_dialog.set_do_overwrite_confirmation(True)
        # dialog always on top of the main window
        save_dialog.set_modal(True)
        # if self.file has already been saved
        if self.file is not None:
            try:
                # set self.file as the current filename for the file chooser
                save_dialog.set_file(self.file)
            except GObject.GError as e:
                print("Error: " + str(e))
        # show the dialog
        response = save_dialog.run()

        # if response is "ACCEPT" (the button "Save" has been clicked)
        if response == Gtk.ResponseType.ACCEPT:
            # self.file is the currently selected file
            self.file = save_dialog.get_file()
            self.ascii.file = self.file
            # save to file
            self.ascii.save()
            # Set Main Window's title with file name
            basename = self.file.get_basename()
            self.window.header.set_title(basename)
        # if response is "CANCEL" (the button "Cancel" has been clicked)
        elif response == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.SAVE")
        # destroy the FileChooserNative
        save_dialog.destroy()

    def patch_outputs(self, _action, _parameter):
        """Create Patch Outputs Tab"""
        if self.patch_outputs_tab is None:
            self.patch_outputs_tab = PatchOutputsTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.patch_outputs_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Patch Outputs"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.patch_outputs_tab, label)
            self.window.playback.set_tab_reorderable(self.patch_outputs_tab, True)
            self.window.playback.set_tab_detachable(self.patch_outputs_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.patch_outputs_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def _patch_channels(self, _action, _parameter):
        """Create Patch Channels Tab"""
        if self.patch_channels_tab is None:
            self.patch_channels_tab = PatchChannelsTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.patch_channels_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Patch Channels"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.patch_channels_tab, label)
            self.window.playback.set_tab_reorderable(self.patch_channels_tab, True)
            self.window.playback.set_tab_detachable(self.patch_channels_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.patch_channels_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def track_channels(self, _action, _parameter):
        """Create Track Channels Tab"""
        if self.track_channels_tab is None:
            self.track_channels_tab = TrackChannelsTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.track_channels_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Track Channels"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.track_channels_tab, label)
            self.window.playback.set_tab_reorderable(self.track_channels_tab, True)
            self.window.playback.set_tab_detachable(self.track_channels_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.track_channels_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def memories_cb(self, _action, _parameter):
        """Create Memories Tab"""
        if self.memories_tab is None:
            self.memories_tab = CuesEditionTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.memories_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Memories"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.memories_tab, label)
            self.window.playback.set_tab_reorderable(self.memories_tab, True)
            self.window.playback.set_tab_detachable(self.memories_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.memories_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def groups_cb(self, _action, _parameter):
        """Create Groups Tab"""
        if self.group_tab is None:
            self.group_tab = GroupTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.group_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Groups"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.group_tab, label)
            self.window.playback.set_tab_reorderable(self.group_tab, True)
            self.window.playback.set_tab_detachable(self.group_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.group_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def sequences(self, _action, _parameter):
        """Create Sequences Tab"""
        if self.sequences_tab is None:
            self.sequences_tab = SequenceTab()

            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.sequences_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Sequences"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.sequences_tab, label)
            self.window.playback.set_tab_reorderable(self.sequences_tab, True)
            self.window.playback.set_tab_detachable(self.sequences_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.sequences_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def channeltime(self, sequence, step):
        """Create Channel Time Tab

        Args:
            sequence: Sequence number
            step: Position in sequence
        """
        if self.channeltime_tab is None:
            self.channeltime_tab = ChanneltimeTab(sequence, step)

            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.channeltime_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Channel Time"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.channeltime_tab, label)
            self.window.playback.set_tab_reorderable(self.channeltime_tab, True)
            self.window.playback.set_tab_detachable(self.channeltime_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.channeltime_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def _masters(self, _action, _parameter):
        """Create Masters Tab"""
        if self.masters_tab is None:
            self.masters_tab = MastersTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.masters_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Master List"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.masters_tab, label)
            self.window.playback.set_tab_reorderable(self.masters_tab, True)
            self.window.playback.set_tab_detachable(self.masters_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.masters_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def _independents(self, _action, _parameter):
        """Create Independents Tab"""
        if self.inde_tab is None:
            self.inde_tab = IndependentsTab()
            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect("clicked", self.inde_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label("Independents"), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.playback.append_page(self.inde_tab, label)
            self.window.playback.set_tab_reorderable(self.inde_tab, True)
            self.window.playback.set_tab_detachable(self.inde_tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.inde_tab)
            self.window.playback.set_current_page(page)

        self.window.playback.grab_focus()

    def _virtual_console(self, _action, _parameter):
        """Virtual Console Window"""
        if not self.virtual_console:
            self.virtual_console = VirtualConsoleWindow()
            self.virtual_console.show_all()
            self.add_window(self.virtual_console)

    def _settings(self, _action, _parameter):
        """Settings"""
        if not self.win_settings:
            self.win_settings = SettingsDialog()
            self.win_settings.settings_dialog.show_all()

    def _shortcuts(self, _action, _parameter):
        """Create Shortcuts Window"""
        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/gtk/help-overlay.ui")
        self.shortcuts = builder.get_object("help_overlay")
        self.shortcuts.set_transient_for(self.window)
        self.shortcuts.show()

    def _about(self, _action, _parameter):
        """Setup about dialog
        @param action as Gio.SimpleAction
        @param param as GLib.Variant
        """
        if not self.about_window:
            builder = Gtk.Builder()
            builder.add_from_resource("/com/github/mikacousin/olc/AboutDialog.ui")
            self.about_window = builder.get_object("about_dialog")
            self.about_window.set_transient_for(self.window)
            self.about_window.connect("response", self._about_response)
            self.about_window.show()
        else:
            self.about_window.present()

    def _about_response(self, dialog, _response):
        """Destroy about dialog when closed

        Args:
            dialog: Gtk.Dialog
            _response: int
        """
        dialog.destroy()
        self.about_window = None

    def _exit(self, _action, _parameter):
        """Exit application"""
        # Stop Chasers Threads
        for chaser in self.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        self.quit()
