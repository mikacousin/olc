import sys
import select

from ola import OlaClient

from olc.define import NB_UNIVERSES, MAX_CHANNELS
from olc.settings import Settings, SettingsDialog
from olc.window import Window
from olc.patch_outputs import PatchOutputsTab
from olc.patch_channels import PatchChannelsTab
from olc.dmx import Dmx, PatchDmx
from olc.cues_edition import CuesEditionTab
from olc.sequence import Sequence
from olc.sequence_edition import SequenceTab
from olc.group import GroupTab
from olc.master import Master
from olc.masters_edition import MastersTab
from olc.channel_time import ChanneltimeTab
from olc.osc import OscServer
from olc.ascii import Ascii
from olc.midi import Midi
from olc.track_channels import TrackChannelsTab
from olc.crossfade import CrossFade
from olc.virtual_console import VirtualConsoleWindow
from olc.widgets_group import GroupWidget
from olc.widgets_track_channels import TrackChannelsHeader, TrackChannelsWidget

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib, Gdk, Pango  # noqa: E402


class Application(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(
            self, application_id="org.gnome.olc", flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        GLib.set_application_name("OpenLightingConsole")
        GLib.set_prgname("olc")

        css_provider_file = Gio.File.new_for_uri(
            "resource://org/gnome/OpenLightingConsole/application.css"
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
        self.settings = Settings.new()

        # Universes
        self.universes = []
        for i in range(NB_UNIVERSES):
            self.universes.append(i)

        # Create patch (1:1)
        self.patch = PatchDmx()

        # Create OlaClient
        try:
            self.ola_client = OlaClient.OlaClient()
            self.sock = self.ola_client.GetSocket()
            for i, univ in enumerate(self.universes):
                func = getattr(self, "on_dmx_" + str(i), None)
                self.ola_client.RegisterUniverse(univ, self.ola_client.REGISTER, func)
        except Exception as e:
            print("Can't connect to Ola !", e)
            sys.exit()

        # Create Main Playback
        self.sequence = Sequence(1, self.patch, text="Main Playback")

        # Create List of Global Memories
        self.memories = []

        # Create List for Chasers
        self.chasers = []

        # Create List of Groups
        self.groups = []

        # Create 2 pages of 20 Masters
        self.masters = []
        for page in range(2):
            for i in range(20):
                self.masters.append(
                    Master(page + 1, i + 1, 0, 0, self.groups, self.chasers)
                )

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

        self.dmx = None
        self.crossfade = None
        self.midi = None
        self.osc_server = None
        self.ascii = None
        self.file = None

    def do_activate(self):

        # Create Main Window
        self.window = Window(self.patch)
        self.sequence.window = self.window
        self.window.show_all()
        # No selected channel on startup
        self.window.flowbox.unselect_all()

        # Maximize window on startup
        self.window.maximize()

        """
        # TODO: Test this code without window manager
        nb_monitors = Gdk.Display.get_default().get_n_monitors()
        #print(nb_monitors)
        if nb_monitors == 2:
            display = Gdk.Display.get_default()
            #print(display)
            monitor = display.get_monitor(1)
            #print(monitor)
            monitor_geometry = monitor.get_geometry()
            print(monitor_geometry.x, monitor_geometry.y)
            print(self.window.get_position())
            self.window.move(monitor_geometry.x, monitor_geometry.y)
            #self.window.move(100, 100)
            print(self.window.get_position())
            #self.window.maximize()
            #self.window.fullscreen_on_monitor(self.window.get_screen(), 1)
            self.window.fullscreen()
        """

        # Add global shortcuts
        # Go
        action = Gio.SimpleAction.new("go", None)
        action.connect("activate", self.sequence.sequence_go)
        self.add_action(action)
        self.set_accels_for_action("app.go", ["<Control>g"])
        # Track Channels
        action = Gio.SimpleAction.new("track_channels", None)
        action.connect("activate", self.track_channels)
        self.add_action(action)
        self.set_accels_for_action("app.track_channels", ["<Shift><Control>t"])
        # Go Back
        action = Gio.SimpleAction.new("go_back", None)
        action.connect("activate", self.sequence.go_back)
        self.add_action(action)
        self.set_accels_for_action("app.go_back", ["<Control>b"])

        # Create several DMX arrays
        self.dmx = Dmx(
            self.universes,
            self.patch,
            self.ola_client,
            self.sequence,
            self.masters,
            self.window,
        )

        # Fetch dmx values on startup
        for univ in self.universes:
            self.ola_client.FetchDmx(univ, self.fetch_dmx)

        # For Manual crossfade
        self.crossfade = CrossFade()

        # Open MIDI Inputs
        self.midi = Midi()
        ports = self.settings.get_strv("midi-in")
        self.midi.open_input(ports)

        # Create and launch OSC server
        self.osc_server = OscServer(self.window)

        # Init of ascii file
        self.ascii = Ascii(None)

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.setup_app_menu()

        # General shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.open", ["<Control>o"])
        self.set_accels_for_action("app.patch_outputs", ["<Control>p"])
        self.set_accels_for_action("app.patch_channels", ["<Shift><Control>p"])
        self.set_accels_for_action("app.groups", ["<Shift><Control>g"])
        self.set_accels_for_action("app.sequences", ["<Control>t"])
        self.set_accels_for_action("app.masters", ["<Control>m"])
        self.set_accels_for_action("app.about", ["F3"])

    def setup_app_menu(self):
        """ Setup application menu, return Gio.Menu """
        builder = Gtk.Builder()

        builder.add_from_resource("/org/gnome/OpenLightingConsole/gtk/menus.ui")

        menu = builder.get_object("app-menu")

        new_action = Gio.SimpleAction.new("new", None)
        new_action.connect("activate", self._new)
        self.add_action(new_action)

        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self._open)
        self.add_action(open_action)

        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self._save)
        self.add_action(save_action)

        patch_outputs_action = Gio.SimpleAction.new("patch_outputs", None)
        patch_outputs_action.connect("activate", self.patch_outputs)
        self.add_action(patch_outputs_action)

        patch_channels_action = Gio.SimpleAction.new("patch_channels", None)
        patch_channels_action.connect("activate", self._patch_channels)
        self.add_action(patch_channels_action)

        memories_action = Gio.SimpleAction.new("memories", None)
        memories_action.connect("activate", self.memories_cb)
        self.add_action(memories_action)

        groups_action = Gio.SimpleAction.new("groups", None)
        groups_action.connect("activate", self.groups_cb)
        self.add_action(groups_action)

        sequences_action = Gio.SimpleAction.new("sequences", None)
        sequences_action.connect("activate", self.sequences)
        self.add_action(sequences_action)

        masters_action = Gio.SimpleAction.new("masters", None)
        masters_action.connect("activate", self._masters)
        self.add_action(masters_action)

        virtual_console_action = Gio.SimpleAction.new("virtual_console", None)
        virtual_console_action.connect("activate", self._virtual_console)
        self.add_action(virtual_console_action)

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._settings)
        self.add_action(settings_action)

        shortcuts_action = Gio.SimpleAction.new("show-help-overlay", None)
        shortcuts_action.connect("activate", self._shortcuts)
        self.add_action(shortcuts_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._about)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._exit)
        self.add_action(quit_action)

        return menu

    def on_fd_read(self, _fd, _condition, _data):
        """Ola messages"""
        readable, _writable, _exceptional = select.select([self.sock], [], [], 0)
        if readable:
            self.ola_client.SocketReady()
        return True

    def on_dmx_0(self, dmxframe):
        for output, level in enumerate(dmxframe):
            channel = self.patch.outputs[0][output][0]
            self.dmx.frame[0][output] = level
            self.window.channels[channel - 1].level = level
            if (
                self.sequence.last > 1
                and self.sequence.position < self.sequence.last - 1
            ):
                next_level = self.sequence.steps[
                    self.sequence.position + 1
                ].cue.channels[channel - 1]
            elif self.sequence.last:
                next_level = self.sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            self.window.channels[channel - 1].next_level = next_level
            self.window.channels[channel - 1].queue_draw()
            if self.patch_outputs_tab:
                self.patch_outputs_tab.outputs[output].queue_draw()

    def on_dmx_1(self, dmxframe):
        for output, level in enumerate(dmxframe):
            channel = self.patch.outputs[1][output][0]
            self.dmx.frame[1][output] = level
            self.window.channels[channel - 1].level = level
            if (
                self.sequence.last > 1
                and self.sequence.position < self.sequence.last - 1
            ):
                next_level = self.sequence.steps[
                    self.sequence.position + 1
                ].cue.channels[channel - 1]
            elif self.sequence.last:
                next_level = self.sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            self.window.channels[channel - 1].next_level = next_level
            self.window.channels[channel - 1].queue_draw()
            if self.patch_outputs_tab:
                self.patch_outputs_tab.outputs[output + 512].queue_draw()

    def on_dmx_2(self, dmxframe):
        for output, level in enumerate(dmxframe):
            channel = self.patch.outputs[2][output][0]
            self.dmx.frame[2][output] = level
            self.window.channels[channel - 1].level = level
            if (
                self.sequence.last > 1
                and self.sequence.position < self.sequence.last - 1
            ):
                next_level = self.sequence.steps[
                    self.sequence.position + 1
                ].cue.channels[channel - 1]
            elif self.sequence.last:
                next_level = self.sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            self.window.channels[channel - 1].next_level = next_level
            self.window.channels[channel - 1].queue_draw()
            if self.patch_outputs_tab:
                self.patch_outputs_tab.outputs[output + 1024].queue_draw()

    def on_dmx_3(self, dmxframe):
        for output, level in enumerate(dmxframe):
            channel = self.patch.outputs[3][output][0]
            self.dmx.frame[3][output] = level
            self.window.channels[channel - 1].level = level
            if (
                self.sequence.last > 1
                and self.sequence.position < self.sequence.last - 1
            ):
                next_level = self.sequence.steps[
                    self.sequence.position + 1
                ].cue.channels[channel - 1]
            elif self.sequence.last:
                next_level = self.sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            self.window.channels[channel - 1].next_level = next_level
            self.window.channels[channel - 1].queue_draw()
            if self.patch_outputs_tab:
                self.patch_outputs_tab.outputs[output + 1536].queue_draw()

    def fetch_dmx(self, _request, univ, dmxframe):
        if dmxframe:
            for output, level in enumerate(dmxframe):
                channel = self.patch.outputs[univ][output][0]
                if channel:
                    self.dmx.frame[univ][output] = level
                    self.window.channels[channel - 1].level = level
                    if (
                        self.sequence.last > 1
                        and self.sequence.position < self.sequence.last
                    ):
                        next_level = self.sequence.steps[
                            self.sequence.position + 1
                        ].cue.channels[channel - 1]
                    elif self.sequence.last:
                        next_level = self.sequence.steps[0].cue.channels[channel - 1]
                    else:
                        next_level = level
                    self.window.channels[channel - 1].next_level = next_level
                    self.window.channels[channel - 1].queue_draw()
                    if self.patch_outputs_tab:
                        self.patch_outputs_tab.outputs[
                            output + (512 * univ)
                        ].queue_draw()

    def _new(self, _action, _parameter):
        # All channels at 0
        for channel in range(MAX_CHANNELS):
            self.dmx.user[channel] = 0
        self.window.flowbox.unselect_all()
        # Reset Patch
        self.patch.patch_1on1()
        # Reset Main Playback
        self.sequence = Sequence(1, self.patch)
        self.sequence.position = 0
        self.sequence.window = self.window
        # Delete memories, groups, chasers, masters
        del self.memories[:]
        del self.groups[:]
        del self.chasers[:]
        del self.masters[:]
        for page in range(2):
            for i in range(20):
                self.masters.append(
                    Master(page + 1, i + 1, 0, 0, self.groups, self.chasers)
                )
        # Redraw Channels
        self.window.flowbox.invalidate_filter()
        # Redraw Sequential Window
        self.window.sequential.time_in = self.sequence.steps[1].time_in
        self.window.sequential.time_out = self.sequence.steps[1].time_out
        self.window.sequential.wait = self.sequence.steps[1].wait
        self.window.sequential.delay_in = self.sequence.steps[1].delay_in
        self.window.sequential.delay_out = self.sequence.steps[1].delay_out
        self.window.sequential.total_time = self.sequence.steps[1].total_time

        self.window.cues_liststore1 = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str, str, int, int
        )
        self.window.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
        )
        self.window.cues_liststore1.append(
            ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
        )

        self.window.cues_liststore2 = Gtk.ListStore(
            str, str, str, str, str, str, str, str, str
        )

        for i in range(self.sequence.last):
            if self.sequence.steps[i].wait.is_integer():
                wait = str(int(self.sequence.steps[i].wait))
                if wait == "0":
                    wait = ""
            else:
                wait = str(self.sequence.steps[i].wait)
            if self.sequence.steps[i].time_out.is_integer():
                t_out = int(self.sequence.steps[i].time_out)
            else:
                t_out = self.sequence.steps[i].time_out
            if self.sequence.steps[i].time_in.is_integer():
                t_in = int(self.sequence.steps[i].time_in)
            else:
                t_in = self.sequence.steps[i].time_in
            if self.sequence.steps[i].delay_out.is_integer():
                d_out = int(self.sequence.steps[i].delay_out)
            else:
                d_out = self.sequence.steps[i].delay_out
            if self.sequence.steps[i].delay_in.is_integer():
                d_in = int(self.sequence.steps[i].delay_in)
            else:
                d_in = self.sequence.steps[i].delay_in
            channel_time = str(len(self.sequence.steps[i].channel_time))
            if channel_time == "0":
                channel_time = ""
            if i in (0, self.sequence.last - 1):
                self.window.cues_liststore1.append(
                    [
                        str(i),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "#232729",
                        Pango.Weight.NORMAL,
                        42,
                    ]
                )
            else:
                self.window.cues_liststore1.append(
                    [
                        str(i),
                        str(self.sequence.steps[i].cue.memory),
                        str(self.sequence.steps[i].text),
                        wait,
                        str(d_out),
                        str(t_out),
                        str(d_in),
                        str(t_in),
                        channel_time,
                        "#232729",
                        Pango.Weight.NORMAL,
                        42,
                    ]
                )
            self.window.cues_liststore2.append(
                [
                    str(i),
                    str(self.sequence.steps[i].cue.memory),
                    str(self.sequence.steps[i].text),
                    wait,
                    str(d_out),
                    str(t_out),
                    str(d_in),
                    str(t_in),
                    channel_time,
                ]
            )
        if self.sequence.last == 1:
            self.window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )

        # Select first cue
        self.window.cues_liststore1[2][9] = "#997004"
        self.window.cues_liststore1[2][10] = Pango.Weight.HEAVY
        # Bold next cue
        self.window.cues_liststore1[3][9] = "#555555"
        self.window.cues_liststore1[3][10] = Pango.Weight.HEAVY

        self.window.step_filter1 = self.window.cues_liststore1.filter_new()
        self.window.step_filter1.set_visible_func(self.window.step_filter_func1)
        self.window.treeview1.set_model(self.window.step_filter1)
        path = Gtk.TreePath.new_from_indices([0])
        self.window.treeview1.set_cursor(path, None, False)

        self.window.step_filter2 = self.window.cues_liststore2.filter_new()
        self.window.step_filter2.set_visible_func(self.window.step_filter_func2)
        self.window.treeview2.set_model(self.window.step_filter2)
        path = Gtk.TreePath.new_from_indices([0])
        self.window.treeview2.set_cursor(path, None, False)

        self.window.seq_grid.queue_draw()

        # Redraw Patch Tabs
        if self.patch_outputs_tab:
            self.patch_outputs_tab.flowbox.queue_draw()
        if self.patch_channels_tab:
            self.patch_channels_tab.flowbox.queue_draw()

        # Redraw Group Tab
        if self.group_tab:
            # Remove old groups
            del self.group_tab.grps[:]
            self.group_tab.scrolled2.remove(self.group_tab.flowbox2)
            self.group_tab.flowbox2.destroy()
            # New flowbox
            self.group_tab.flowbox2 = Gtk.FlowBox()
            self.group_tab.flowbox2.set_valign(Gtk.Align.START)
            self.group_tab.flowbox2.set_max_children_per_line(20)
            self.group_tab.flowbox2.set_homogeneous(True)
            self.group_tab.flowbox2.set_activate_on_single_click(True)
            self.group_tab.flowbox2.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.group_tab.flowbox2.set_filter_func(self.group_tab.filter_groups, None)
            self.group_tab.scrolled2.add(self.group_tab.flowbox2)
            # Add Groups to FlowBox
            for i, _ in enumerate(self.groups):
                self.group_tab.grps.append(
                    GroupWidget(
                        i,
                        self.groups[i].index,
                        self.groups[i].text,
                        self.group_tab.grps,
                    )
                )
                self.group_tab.flowbox2.add(self.group_tab.grps[i])
            self.group_tab.flowbox1.invalidate_filter()
            self.group_tab.flowbox2.invalidate_filter()
            self.window.show_all()

        # Redraw Memories Tab
        if self.memories_tab:
            self.memories_tab.liststore.clear()
            # Select first Memory
            path = Gtk.TreePath.new_first()
            self.memories_tab.treeview.set_cursor(path, None, False)
            for mem in self.memories:
                channels = 0
                for chan in range(MAX_CHANNELS):
                    if mem.channels[chan]:
                        channels += 1
                self.memories_tab.liststore.append(
                    [str(mem.memory), mem.text, channels]
                )
            self.memories_tab.flowbox.invalidate_filter()

        # Redraw Masters in Virtual Console
        if self.virtual_console:
            if self.virtual_console.props.visible:
                for page in range(2):
                    for master in self.masters:
                        if master.page == page + 1:
                            self.virtual_console.flashes[
                                master.number - 1 + (page * 20)
                            ].label = master.text
                            self.virtual_console.flashes[
                                master.number - 1 + (page * 20)
                            ].queue_draw()

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
            for page in range(2):
                for i in range(20):
                    index = i + (page * 20)

                    # Type : None
                    if self.masters[index].content_type == 0:
                        self.masters_tab.liststore.append([index + 1, "", "", ""])

                    # Type : Preset
                    elif self.masters[index].content_type == 1:
                        content_value = str(self.masters[index].content_value)
                        self.masters_tab.liststore.append(
                            [index + 1, "Preset", content_value, ""]
                        )

                    # Type : Channels
                    elif self.masters[index].content_type == 2:
                        nb_chan = 0
                        for chan in range(MAX_CHANNELS):
                            if self.masters[index].channels[chan]:
                                nb_chan += 1
                        self.masters_tab.liststore.append(
                            [index + 1, "Channels", str(nb_chan), ""]
                        )

                    # Type : Sequence
                    elif self.masters[index].content_type == 3:
                        if self.masters[index].content_value.is_integer():
                            content_value = str(int(self.masters[index].content_value))
                        else:
                            content_value = str(self.masters[index].content_value)
                        self.masters_tab.liststore.append(
                            [index + 1, "Sequence", content_value, ""]
                        )

                    # Type : Group
                    elif self.masters[index].content_type == 13:
                        if self.masters[index].content_value.is_integer():
                            content_value = str(int(self.masters[index].content_value))
                        else:
                            content_value = str(self.masters[index].content_value)
                        self.masters_tab.liststore.append(
                            [index + 1, "Group", content_value, "Exclusif"]
                        )

                    # Type : Unknown
                    else:
                        self.masters_tab.liststore.append(
                            [index + 1, "Unknown", "", ""]
                        )

            self.masters_tab.flowbox.invalidate_filter()

        # Redraw Channel Time Tab
        if self.channeltime_tab:
            self.channeltime_tab.liststore.clear()
            self.channeltime_tab.flowbox.invalidate_filter()

        # Redraw Track Channels
        if self.track_channels_tab:
            for widget in self.track_channels_tab.flowbox:
                widget.destroy()
            self.track_channels_tab.channels = []
            levels = []
            self.track_channels_tab.steps = []
            self.track_channels_tab.steps.append(
                TrackChannelsHeader(self.track_channels_tab.channels)
            )
            levels.append([])
            self.track_channels_tab.flowbox.add(self.track_channels_tab.steps[0])
            for step in range(1, self.sequence.last):
                memory = self.sequence.steps[step].cue.memory
                text = self.sequence.steps[step].text
                levels.append([])
                for channel in self.track_channels_tab.channels:
                    level = self.sequence.steps[step].cue.channels[channel]
                    levels[step].append(level)
                self.track_channels_tab.steps.append(
                    TrackChannelsWidget(step, memory, text, levels[step])
                )
                self.track_channels_tab.flowbox.add(self.track_channels_tab.steps[step])
            self.track_channels_tab.flowbox.invalidate_filter()

    def _open(self, _action, _parameter):
        # create a filechooserdialog to open:
        # the arguments are: title of the window, parent_window, action,
        # (buttons, response)
        open_dialog = Gtk.FileChooserDialog(
            "Open ASCII File",
            self.window,
            Gtk.FileChooserAction.OPEN,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.ACCEPT,
            ),
        )

        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text Files")
        filter_text.add_mime_type("text/plain")
        open_dialog.add_filter(filter_text)

        # not only local files can be selected in the file selector
        open_dialog.set_local_only(False)
        # dialog always on top of the textview window
        open_dialog.set_modal(True)
        # connect the dialog with the callback function open_response_cb()
        open_dialog.connect("response", self.open_response_cb)
        # show the dialog
        open_dialog.show()

    def open_response_cb(self, dialog, response_id):
        # callback function for the dialog open_dialog
        open_dialog = dialog

        # if response is "ACCEPT" (the button "Open" has been clicked)
        if response_id == Gtk.ResponseType.ACCEPT:
            # self.file is the file that we get from the FileChooserDialog
            self.file = open_dialog.get_file()

            # Load the ASCII file
            self.ascii.file = self.file
            self.ascii.load()

            for univ in self.universes:
                self.ola_client.FetchDmx(univ, self.fetch_dmx)

        elif response_id == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.OPEN")

        # destroy the FileChooserDialog
        dialog.destroy()

    def _save(self, _action, _parameter):
        # TODO: remettre le try:
        self.ascii.save()
        """
        try:
            self.ascii.save()
        except:
            self._saveas(None, None)
        """

    def _saveas(self, _action, _parameter):
        print("Save As")

    def patch_outputs(self, _action, _parameter):
        # Create Patch Outputs Tab
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

            self.window.notebook.append_page(self.patch_outputs_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.patch_outputs_tab)
            self.window.notebook.set_current_page(page)

    def _patch_channels(self, _action, _parameter):
        # Create Patch Channels Tab
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

            self.window.notebook.append_page(self.patch_channels_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.patch_channels_tab)
            self.window.notebook.set_current_page(page)

    def track_channels(self, _action, _parameter):
        # Create Track Channels Tab
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

            self.window.notebook.append_page(self.track_channels_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.track_channels_tab)
            self.window.notebook.set_current_page(page)

    def memories_cb(self, action, parameter):
        # Create Memories Tab
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

            self.window.notebook.append_page(self.memories_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.memories_tab)
            self.window.notebook.set_current_page(page)

    def groups_cb(self, action, parameter):
        # Create Groups Tab
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

            self.window.notebook.append_page(self.group_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.group_tab)
            self.window.notebook.set_current_page(page)

    def sequences(self, _action, _parameter):
        # Create Sequences Tab
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

            self.window.notebook.append_page(self.sequences_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
            self.window.notebook.grab_focus()
        else:
            page = self.window.notebook.page_num(self.sequences_tab)
            self.window.notebook.set_current_page(page)

    def channeltime(self, sequence, step):
        # Create Channel Time Tab
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

            self.window.notebook.append_page(self.channeltime_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.channeltime_tab)
            self.window.notebook.set_current_page(page)

    def _masters(self, _action, _parameter):
        # Create Masters Tab
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

            self.window.notebook.append_page(self.masters_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.masters_tab)
            self.window.notebook.set_current_page(page)

    def _virtual_console(self, _action, _parameter):
        # Virtual Console Window
        self.virtual_console = VirtualConsoleWindow()
        self.virtual_console.show_all()
        self.add_window(self.virtual_console)

    def _settings(self, _action, _parameter):
        self.win_settings = SettingsDialog()
        self.win_settings.settings_dialog.show_all()

    def _shortcuts(self, _action, _parameter):
        """Create Shortcuts Window"""
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/OpenLightingConsole/gtk/help-overlay.ui")
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
            builder.add_from_resource("/org/gnome/OpenLightingConsole/AboutDialog.ui")
            self.about_window = builder.get_object("about_dialog")
            self.about_window.set_transient_for(self.window)
            self.about_window.connect("response", self._about_response)
            self.about_window.show()
        else:
            self.about_window.present()

    def _about_response(self, dialog, _response):
        """Destroy about dialog when closed
            @param dialog as Gtk.Dialog
            @param response as int
        """
        dialog.destroy()
        self.about_window = None

    def _exit(self, _action, _parameter):
        # Stop Chasers Threads
        for chaser in self.chasers:
            if chaser.run and chaser.thread:
                chaser.run = False
                chaser.thread.stop()
                chaser.thread.join()
        self.quit()
