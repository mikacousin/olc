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
import sys
from gettext import gettext as _
from typing import Any, Optional

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402
from olc.backends.backend import select_backend  # noqa: E402
from olc.channel_time import ChanneltimeTab  # noqa: E402
from olc.crossfade import CrossFade  # noqa: E402
from olc.cues_edition import CuesEditionTab  # noqa: E402
from olc.curve_edition import CurvesTab  # noqa: E402
from olc.define import MAX_CHANNELS  # noqa: E402
from olc.fader_edition import FaderTab  # noqa: E402
from olc.files.export_file import ExportFile  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.group import GroupTab  # noqa: E402
from olc.independent import Independents  # noqa: E402
from olc.independents_edition import IndependentsTab  # noqa: E402
from olc.lightshow import LightShow  # noqa: E402
from olc.midi import Midi  # noqa: E402
from olc.osc import Osc  # noqa: E402
from olc.patch_channels import PatchChannelsTab  # noqa: E402
from olc.patch_outputs import PatchOutputsTab  # noqa: E402
from olc.sequence import Sequence  # noqa: E402
from olc.sequence_edition import SequenceTab  # noqa: E402
from olc.settings import SettingsTab  # noqa: E402
from olc.tabs_manager import Tabs  # noqa: E402
from olc.track_channels import TrackChannelsTab  # noqa: E402
from olc.virtual_console import VirtualConsoleWindow  # noqa: E402
from olc.window import Window  # noqa: E402


class Application(Gtk.Application):
    """Application Class"""

    backend: Any
    version: str

    def __init__(self, version, *args, **kwargs):
        self.backend = None
        self.version = version
        super().__init__(
            *args,
            application_id="com.github.mikacousin.olc",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs,
        )
        GLib.set_application_name("OpenLightingConsole")
        GLib.set_prgname("olc")

        self.add_main_option(
            "version",
            ord("v"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Show Open Lighting Console version",
            None,
        )

        self.add_main_option(
            "http-port",
            ord("p"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.INT,
            "The port to run the Ola HTTP server on. Defaults to 9090",
            None,
        )

        self.add_main_option(
            "backend",
            ord("b"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            "The backend to use (sacn or ola). Defaults to sacn",
            "<backend>",
        )

        css_provider_file = Gio.File.new_for_uri(
            "resource://com/github/mikacousin/olc/application.css")
        css_provider = Gtk.CssProvider()
        css_provider.load_from_file(css_provider_file)
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(screen, css_provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # Change to dark theme
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        # To store settings
        self.settings = Gio.Settings.new("com.github.mikacousin.olc")

        # Fader page
        self.fader_page = 1

        # For Windows
        self.window = None
        self.about_window = None
        self.virtual_console = None
        self.shortcuts = None

        # For Tabs
        self.tabs = Tabs()

        self.crossfade = None
        self.midi = None
        self.osc = None

        # Light show initialization
        self.lightshow = LightShow()

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
        action.connect("activate", self.lightshow.main_playback.do_go)
        self.add_action(action)
        self.set_accels_for_action("app.go", ["<Control>g"])
        # Go Back
        action = Gio.SimpleAction.new("go_back", None)
        action.connect("activate", self.lightshow.main_playback.go_back)
        self.add_action(action)
        self.set_accels_for_action("app.go_back", ["<Control>b"])
        # Pause
        action = Gio.SimpleAction.new("pause", None)
        action.connect("activate", self.lightshow.main_playback.pause)
        self.add_action(action)
        self.set_accels_for_action("app.pause", ["<Control>z"])
        # Full screen
        action = Gio.SimpleAction.new("fullscreen", None)
        action.connect("activate", self.window.fullscreen_toggle)
        self.add_action(action)

        # For Manual crossfade
        self.crossfade = CrossFade()

        # Open MIDI Inputs and Outputs
        self.midi = Midi()
        self.midi.messages.lcd.show_faders()
        self.midi.main_fader_init()

        # Create and launch OSC server
        if self.settings.get_boolean("osc"):
            self.osc = Osc()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # General shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.open", ["<Control>o"])
        self.set_accels_for_action("app.import_ascii", ["<Shift><Control>o"])
        self.set_accels_for_action("app.save", ["<Control>s"])
        self.set_accels_for_action("app.save_as", ["<Shift><Control>s"])
        self.set_accels_for_action("app.patch_outputs", ["<Control>p"])
        self.set_accels_for_action("app.patch_channels", ["<Shift><Control>p"])
        self.set_accels_for_action("app.groups", ["<Shift><Control>g"])
        self.set_accels_for_action("app.sequences", ["<Control>t"])
        self.set_accels_for_action("app.faders", ["<Control>f"])
        self.set_accels_for_action("app.track_channels", ["<Shift><Control>t"])
        self.set_accels_for_action("app.independents", ["<Control>i"])
        self.set_accels_for_action("app.virtual_console", ["<Shift><Control>c"])
        self.set_accels_for_action("app.about", ["F3"])
        self.set_accels_for_action("app.fullscreen", ["F11"])

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> bool:
        Gtk.Application.do_command_line(self, command_line)
        options = command_line.get_options_dict()
        # convert GVariantDict -> GVariant -> dict
        options = options.end().unpack()
        if "version" in options:
            print(self.version)
            sys.exit()
        self.backend = select_backend(options, self.settings, self.lightshow.patch)
        if not self.backend:
            sys.exit()
        # Activate olc
        self.activate()
        # Arguments (one ASCII file to open)
        arguments = command_line.get_arguments()
        if len(arguments) > 1:
            self.lightshow.file = command_line.create_file_for_arg(arguments[1])
            # TODO: Load olc file format not ascii
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
            "import_ascii": "_import_ascii",
            "export_ascii": "_export_ascii",
            "patch_outputs": "patch_outputs",
            "patch_channels": "_patch_channels",
            "curves": "_curves",
            "memories": "memories_cb",
            "groups": "groups_cb",
            "sequences": "sequences",
            "faders": "_faders",
            "track_channels": "track_channels",
            "independents": "_independents",
            "virtual_console": "_virtual_console",
            "settings": "_settings",
            "show-help-overlay": "_shortcuts",
            "about": "_about",
            "quit": "exit",
        }
        for name, func in actions.items():
            function = getattr(self, func, None)
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", function)
            self.add_action(action)
        return menu

    def _new(self, _action, _parameter):
        """New show"""
        # Stop Chasers
        for chaser in self.lightshow.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        # All channels at 0
        for channel in range(MAX_CHANNELS):
            self.backend.dmx.levels["user"][channel] = -1
        self.backend.dmx.set_levels()
        self.window.live_view.channels_view.flowbox.unselect_all()
        # Reset Patch
        self.lightshow.patch.patch_1on1()
        # Reset Main Playback
        self.lightshow.main_playback = Sequence(1, "Main Playback")
        self.lightshow.main_playback.position = 0
        self.lightshow.main_playback.window = self.window
        self.lightshow.main_playback.update_channels()
        # Delete cues, groups, chasers, faders
        del self.lightshow.cues[:]
        del self.lightshow.groups[:]
        del self.lightshow.chasers[:]
        self.fader_page = 1
        self.lightshow.fader_bank.reset_faders()
        self.lightshow.independents = Independents()
        # Redraw Sequential Window
        self.window.playback.update_sequence_display()
        self.window.playback.update_xfade_display(self.lightshow.main_playback.position)
        self.window.update_channels_display(self.lightshow.main_playback.position)

        # Redraw all open tabs
        self.tabs.refresh_all()

        self.window.live_view.channels_view.last_selected_channel = ""

    def _open(self, _action, _parameter):
        """create a file chooser dialog to open:
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
            self.lightshow.file = open_dialog.get_file()
            # Load the ASCII file
            self.ascii.load()

        # destroy the FileChooserNative
        open_dialog.destroy()

        # All channels at 0
        for channel in range(MAX_CHANNELS):
            self.backend.dmx.levels["sequence"][channel] = 0
            self.backend.dmx.levels["user"][channel] = -1
        self.backend.dmx.set_levels()

    def _import_ascii(self, _action, _parameter) -> None:
        open_dialog = Gtk.FileChooserNative.new(
            _("Import ASCII File"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Open"),
            _("Cancel"),
        )
        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text Files")
        filter_text.add_mime_type("text/plain")
        open_dialog.add_filter(filter_text)
        open_dialog.set_local_only(False)
        open_dialog.set_modal(True)
        response = open_dialog.run()

        if response == Gtk.ResponseType.ACCEPT:
            imported = ImportFile(open_dialog.get_file(), "ascii")
            imported.parse()
            imported.select_data()
        open_dialog.destroy()

    def _export_ascii(self, _action, _parameter) -> None:
        dialog = Gtk.FileChooserNative.new(_("Export ASCII File"), self.window,
                                           Gtk.FileChooserAction.SAVE, _("Export"),
                                           _("Cancel"))
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_modal(True)
        dialog.set_current_name("Untitled.asc")
        response = dialog.run()

        if response == Gtk.ResponseType.ACCEPT:
            exported = ExportFile(dialog.get_file(), "ascii")
            exported.write()
        dialog.destroy()

    def _save(self, _action, _parameter):
        """Save"""
        if self.lightshow.file is not None:
            exported = ExportFile(self.lightshow.file, "olc")
            exported.write()
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
        if self.lightshow.file is not None:
            try:
                # set self.lightshow.file as the current filename for the file chooser
                save_dialog.set_file(self.lightshow.file)
            except GObject.GError as e:
                print(f"Error: {e}")
        else:
            save_dialog.set_current_name("Untitled.olc")
        # show the dialog
        response = save_dialog.run()

        # if response is "ACCEPT" (the button "Save" has been clicked)
        if response == Gtk.ResponseType.ACCEPT:
            # self.lightshow.file is the currently selected file
            self.lightshow.file = save_dialog.get_file()
            # save to file
            exported = ExportFile(self.lightshow.file, "olc")
            exported.write()
            # Set Main Window's title with file name
            self.lightshow.set_not_modified()
        # destroy the FileChooserNative
        save_dialog.destroy()

    def patch_outputs(self, _action, _parameter):
        """Create Patch Outputs Tab"""
        self.tabs.open("patch_outputs", PatchOutputsTab, "Patch Outputs",
                       self.lightshow.patch)

    def _patch_channels(self, _action, _parameter):
        """Create Patch Channels Tab"""
        self.tabs.open("patch_channels", PatchChannelsTab, "Patch Channels",
                       self.lightshow.patch)

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
        self.tabs.open("channel_time", ChanneltimeTab, "Channel Time", sequence, step)

    def _curves(self, _action, _parameter):
        """Create Curves Edition Tab"""
        self.tabs.open("curves", CurvesTab, "Curves")

    def _faders(self, _action, _parameter):
        """Create Faders Tab"""
        self.tabs.open("faders", FaderTab, "Faders", self.lightshow.fader_bank)

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
        self.tabs.open("settings", SettingsTab, "Settings")

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

    def exit(self, _action, _parameter) -> Optional[bool]:
        """Exit application

        Returns:
            True to not propagate signal
        """
        if self.lightshow.modified:
            dialog = DialogQuit(self.window)
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.CANCEL:
                return True
            if response == 1:
                self._save(None, None)
        for chaser in self.lightshow.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        self.midi.stop()
        self.backend.stop()
        self.quit()
        return False


class DialogQuit(Gtk.Dialog):
    """Ask user if he try to quit with an unsaved file"""

    def __init__(self, parent):
        super().__init__(title=_("Save file ?"), transient_for=parent, flags=0)
        self.add_buttons(
            _("Save"),
            1,
            _("Cancel"),
            Gtk.ResponseType.CANCEL,
            _("Don't Save"),
            Gtk.ResponseType.OK,
        )
        self.set_default_size(150, 100)
        box = self.get_content_area()
        label = Gtk.Label(label=_("Save changes before closing ?"))
        box.add(label)
        label = Gtk.Label(label=_("Your changes will be lost if you don't save them."))
        box.add(label)
        self.show_all()
