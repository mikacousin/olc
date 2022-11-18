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
from olc.ola_module import Ola  # noqa: E402
from olc.osc import OscServer  # noqa: E402
from olc.patch_channels import PatchChannelsTab  # noqa: E402
from olc.patch_outputs import PatchOutputsTab  # noqa: E402
from olc.sequence import Sequence  # noqa: E402
from olc.sequence_edition import SequenceTab  # noqa: E402
from olc.settings import SettingsDialog  # noqa: E402
from olc.tabs_manager import Tabs  # noqa: E402
from olc.track_channels import TrackChannelsTab  # noqa: E402
from olc.virtual_console import VirtualConsoleWindow  # noqa: E402
from olc.window import Window  # noqa: E402


class Application(Gtk.Application):
    """Application Class"""

    ola: Ola

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.github.mikacousin.olc",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs,
        )
        GLib.set_application_name("OpenLightingConsole")
        GLib.set_prgname("olc")

        self.add_main_option(
            "http-port",
            ord("p"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.INT,
            "The port to run the Ola HTTP server on. Defaults to 9090",
            None,
        )

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
        self.settings = Gio.Settings.new("com.github.mikacousin.olc")

        # Universes
        self.universes = UNIVERSES
        # Create patch (1:1)
        self.patch = PatchDmx(self.universes)

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
            self.masters.extend(Master(page + 1, i + 1, 0, 0) for i in range(10))
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
        self.tabs = Tabs()

        self.dmx = None
        self.crossfade = None
        self.midi = None
        self.osc_server = None
        self.ascii = None
        self.wing = None

    def do_activate(self):
        # Create Main Window
        self.window = Window()
        self.window.show_all()
        # No selected channel on startup
        self.window.live_view.channels_view.flowbox.unselect_all()

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
            self.ola.ola_thread.ola_client.FetchDmx(univ, self.fetch_dmx)

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
        GLib.timeout_add(50, self._on_timeout, None)

        # Scan Ola messages - 27 = IN(1) + HUP(16) + PRI(2) + ERR(8)
        GLib.unix_fd_add_full(
            0,
            self.ola.ola_thread.sock.fileno(),
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
        if self.dmx.stop:
            return False
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

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> bool:
        Gtk.Application.do_command_line(self, command_line)
        # Options (olad http port)
        olad_port = 9090
        options = command_line.get_options_dict()
        # convert GVariantDict -> GVariant -> dict
        options = options.end().unpack()
        if "http-port" in options:
            olad_port = options["http-port"]
        # Start Ola and activate olc
        self.ola = Ola(olad_port)
        self.ola.start()
        self.activate()
        # Arguments (one ASCII file to open)
        arguments = command_line.get_arguments()
        if len(arguments) > 1:
            self.ascii.file = command_line.create_file_for_arg(arguments[1])
            self.ascii.load()
        return False

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
            [self.ola.ola_thread.sock], [], [], 0
        )
        if readable:
            self.ola.ola_thread.ola_client.SocketReady()
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
        self.ola.ola_thread.old_frame[index] = dmxframe
        for output, level in enumerate(dmxframe):
            if univ in self.patch.outputs and output + 1 in self.patch.outputs[univ]:
                channel = self.patch.outputs.get(univ).get(output + 1)[0]
                self.dmx.frame[index][output] = level
                if (
                    self.sequence.last > 1
                    and self.sequence.position < self.sequence.last
                ):
                    next_level = self.sequence.steps[
                        self.sequence.position + 1
                    ].cue.channels.get(channel, 0)
                elif self.sequence.last:
                    next_level = self.sequence.steps[0].cue.channels.get(channel, 0)
                else:
                    next_level = level
                self.window.live_view.update_channel_widget(channel, level, next_level)
                if self.tabs.tabs["patch_outputs"]:
                    self.tabs.tabs["patch_outputs"].outputs[
                        output + (512 * index)
                    ].queue_draw()

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
        self.window.live_view.channels_view.flowbox.unselect_all()
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

        # Redraw all open tabs
        self.tabs.refresh_all()

        # Redraw Masters in Virtual Console
        if self.virtual_console and self.virtual_console.props.visible:
            self.virtual_console.page_number.set_label(str(self.fader_page))
            for master in self.masters:
                if master.page == self.fader_page:
                    text = f"master_{str(master.number + (self.fader_page - 1) * 10)}"
                    self.virtual_console.masters[master.number - 1].text = text
                    self.virtual_console.masters[master.number - 1].set_value(
                        master.value
                    )
                    self.virtual_console.flashes[master.number - 1].label = master.text
            self.virtual_console.masters_pad.queue_draw()

        self.window.live_view.grab_focus()
        self.window.live_view.channels_view.last_selected_channel = ""

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
            self.ascii.file = open_dialog.get_file()
            # Load the ASCII file
            self.ascii.load()

            for univ in self.universes:
                self.ola.ola_thread.ola_client.FetchDmx(univ, self.fetch_dmx)

        elif response == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.OPEN")

        # destroy the FileChooserNative
        open_dialog.destroy()

    def _save(self, _action, _parameter):
        """Save"""
        if self.ascii.file is not None:
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
        # if file has already been saved
        if self.ascii.file is not None:
            try:
                # set self.ascii.file as the current filename for the file chooser
                save_dialog.set_file(self.ascii.file)
            except GObject.GError as e:
                print(f"Error: {str(e)}")
        # show the dialog
        response = save_dialog.run()

        # if response is "ACCEPT" (the button "Save" has been clicked)
        if response == Gtk.ResponseType.ACCEPT:
            # self.ascii.file is the currently selected file
            self.ascii.file = save_dialog.get_file()
            # save to file
            self.ascii.save()
            # Set Main Window's title with file name
            basename = self.ascii.file.get_basename()
            self.window.header.set_title(basename)
        # if response is "CANCEL" (the button "Cancel" has been clicked)
        elif response == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.SAVE")
        # destroy the FileChooserNative
        save_dialog.destroy()

    def patch_outputs(self, _action, _parameter):
        """Create Patch Outputs Tab"""
        self.tabs.open("patch_outputs", PatchOutputsTab, "Patch Outputs")

    def _patch_channels(self, _action, _parameter):
        """Create Patch Channels Tab"""
        self.tabs.open("patch_channels", PatchChannelsTab, "Patch Channels")

    def track_channels(self, _action, _parameter):
        """Create Track Channels Tab"""
        self.tabs.open("track_channels", TrackChannelsTab, "Track Channels")

    def memories_cb(self, _action, _parameter):
        """Create Memories Tab"""
        self.tabs.open("memories", CuesEditionTab, "Memories")

    def groups_cb(self, _action, _parameter):
        """Create Groups Tab"""
        self.tabs.open("groups", GroupTab, "Groups")

    def sequences(self, _action, _parameter):
        """Create Sequences Tab"""
        self.tabs.open("sequences", SequenceTab, "Sequences")

    def channeltime(self, sequence, step):
        """Create Channel Time Tab

        Args:
            sequence: Sequence number
            step: Position in sequence
        """
        self.tabs.open("channel_time", ChanneltimeTab, "Sequences", sequence, step)

    def _masters(self, _action, _parameter):
        """Create Masters Tab"""
        self.tabs.open("masters", MastersTab, "Masters")

    def _independents(self, _action, _parameter):
        """Create Independents Tab"""
        self.tabs.open("indes", IndependentsTab, "Independents")

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
        # Stop send DMX
        self.dmx.stop = True
        self.ola.stop()
        self.quit()
