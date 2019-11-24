import sys
import array
import select
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, GObject, Pango
from ola import OlaClient

from olc.define import NB_UNIVERSES
from olc.settings import Settings, SettingsDialog
from olc.window import Window
from olc.patch_outputs import PatchOutputsTab
from olc.patch_channels import PatchChannelsTab
from olc.dmx import Dmx, PatchDmx
from olc.cue import Cue
from olc.sequence import Sequence
from olc.sequence_edition import SequenceTab
from olc.group import Group, GroupTab
from olc.master import Master, MasterTab
from olc.channel_time import ChanneltimeTab
from olc.widgets_group import GroupWidget
from olc.osc import OscServer
from olc.ascii import Ascii
from olc.midi import Midi
from olc.track_channels import TrackChannelsTab
from olc.crossfade import CrossFade
from olc.virtual_console import VirtualConsoleWindow

class Application(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self,
                application_id='org.gnome.olc',
                flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name('OpenLightingConsole')
        GLib.set_prgname('olc')

        # TODO: Test css et unbind des bindings pour la gestion clavier
        cssProviderFile = Gio.File.new_for_uri('resource://org/gnome/OpenLightingConsole/application.css')
        cssProvider = Gtk.CssProvider()
        cssProvider.load_from_file(cssProviderFile)
        screen = Gdk.Screen.get_default()
        styleContext = Gtk.StyleContext()
        styleContext.add_provider_for_screen(screen, cssProvider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # Change to dark theme
        settings = Gtk.Settings.get_default()
        settings.set_property('gtk-application-prefer-dark-theme', True)

        # To store settings
        self.settings = Settings.new()

        # TODO: Choisir son univers
        self.universes = []
        for i in range(NB_UNIVERSES):
            self.universes.append(i)

        # Create patch (1:1)
        self.patch = PatchDmx()

        # Create OlaClient
        try:
            self.ola_client = OlaClient.OlaClient()
            self.sock = self.ola_client.GetSocket()
            for i in range(len(self.universes)):
                func = getattr(self, 'on_dmx_' + str(i), None)
                self.ola_client.RegisterUniverse(self.universes[i], self.ola_client.REGISTER, func)
        except:
            print("Can't connect to Ola !")
            sys.exit()

        # Create Main Playback
        self.sequence = Sequence(1, self.patch, text="Main Playback")
        last = Cue(self.sequence.last + 1, "0.0", text="End")
        self.sequence.add_cue(last)

        # Create List for Chasers
        self.chasers = []

        # Create List of Groups
        self.groups = []

        # Create List of Masters
        self.masters = []

        # For Windows
        self.about_window = None
        self.virtual_console = None

        # For Tabs
        self.patch_outputs_tab = None
        self.patch_channels_tab = None
        self.master_tab = None
        self.group_tab = None
        self.sequences_tab = None
        self.channeltime_tab = None
        self.track_channels_tab = None

    def do_activate(self):

        # Create Main Window
        self.window = Window(self, self.patch)
        self.sequence.window = self.window
        self.window.show_all()
        # No selected channel on startup
        self.window.flowbox.unselect_all()

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
        action = Gio.SimpleAction.new('go', None)
        action.connect('activate', self.sequence.sequence_go)
        self.add_action(action)
        self.set_accels_for_action("app.go", ["<Control>g"])
        # Track Channels
        action = Gio.SimpleAction.new('track_channels', None)
        action.connect('activate', self._track_channels)
        self.add_action(action)
        self.set_accels_for_action("app.track_channels", ["<Shift><Control>t"])

        # Create several DMX arrays
        self.dmx = Dmx(self.universes, self.patch, self.ola_client, self.sequence, self.masters, self.window)

        # Fetch dmx values on startup
        for i in range(len(self.universes)):
            self.ola_client.FetchDmx(self.universes[i], self.fetch_dmx)

        # For Manual crossfade
        self.crossfade = CrossFade()

        # Open MIDI Input
        self.midi = Midi()
        port = self.settings.get_string('midi-in')
        self.midi.open_input(port)

        # Create and launch OSC server
        self.osc_server = OscServer(self.window)

        # Init of ascii file
        self.ascii = Ascii(None)

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # TODO: Revoir pour le menu et la gestion auto de la fenetre des shortcuts
        menu = self.setup_app_menu()

        # General shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.open", ["<Control>o"])
        self.set_accels_for_action("app.patch_outputs", ["<Control>p"])
        self.set_accels_for_action("app.patch_channels", ["<Shift><Control>p"])
        self.set_accels_for_action("app.groups", ["<Shift><Control>g"])
        self.set_accels_for_action("app.masters", ["<Control>m"])
        self.set_accels_for_action("app.sequences", ["<Control>t"])
        self.set_accels_for_action("app.about", ["F3"])

    def setup_app_menu(self):
        """ Setup application menu, return Gio.Menu """
        builder = Gtk.Builder()

        #builder.add_from_resource('/org/gnome/OpenLightingConsole/app-menu.ui')
        builder.add_from_resource('/org/gnome/OpenLightingConsole/gtk/menus.ui')

        menu = builder.get_object('app-menu')

        newAction = Gio.SimpleAction.new('new', None)
        newAction.connect('activate', self._new)
        self.add_action(newAction)

        openAction = Gio.SimpleAction.new('open', None)
        openAction.connect('activate', self._open)
        self.add_action(openAction)

        saveAction = Gio.SimpleAction.new('save', None)
        saveAction.connect('activate', self._save)
        self.add_action(saveAction)

        patch_outputsAction = Gio.SimpleAction.new('patch_outputs', None)
        patch_outputsAction.connect('activate', self._patch_outputs)
        self.add_action(patch_outputsAction)

        patch_channelsAction = Gio.SimpleAction.new('patch_channels', None)
        patch_channelsAction.connect('activate', self._patch_channels)
        self.add_action(patch_channelsAction)

        groupsAction = Gio.SimpleAction.new('groups', None)
        groupsAction.connect('activate', self._groups)
        self.add_action(groupsAction)

        mastersAction = Gio.SimpleAction.new('masters', None)
        mastersAction.connect('activate', self._masters)
        self.add_action(mastersAction)

        sequencesAction = Gio.SimpleAction.new('sequences', None)
        sequencesAction.connect('activate', self._sequences)
        self.add_action(sequencesAction)

        virtual_consoleAction = Gio.SimpleAction.new('virtual_console', None)
        virtual_consoleAction.connect('activate', self._virtual_console)
        self.add_action(virtual_consoleAction)

        settingsAction = Gio.SimpleAction.new('settings', None)
        settingsAction.connect('activate', self._settings)
        self.add_action(settingsAction)

        shortcutsAction = Gio.SimpleAction.new('show-help-overlay', None)
        shortcutsAction.connect('activate', self._shortcuts)
        self.add_action(shortcutsAction)

        aboutAction = Gio.SimpleAction.new('about', None)
        aboutAction.connect('activate', self._about)
        self.add_action(aboutAction)

        quitAction = Gio.SimpleAction.new('quit', None)
        quitAction.connect('activate', self._exit)
        self.add_action(quitAction)

        return menu

    def on_fd_read(self, fd, condition, data):
        # Ola messages
        readable, writable, exceptional = select.select([self.sock], [], [], 0)
        if readable:
            self.ola_client.SocketReady()
        return True

    def on_dmx_0(self, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[0][output]
            level = dmxframe[output]
            self.dmx.frame[0][output] = level
            self.window.channels[channel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
            else:
                next_level = self.sequence.cues[0].channels[channel-1]
            self.window.channels[channel-1].next_level = next_level
            self.window.channels[channel-1].queue_draw()

    def on_dmx_1(self, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[1][output]
            level = dmxframe[output]
            self.dmx.frame[1][output] = level
            self.window.channels[channel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
            else:
                next_level = self.sequence.cues[0].channels[channel-1]
            self.window.channels[channel-1].next_level = next_level
            self.window.channels[channel-1].queue_draw()

    def on_dmx_2(self, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[2][output]
            level = dmxframe[output]
            self.dmx.frame[2][output] = level
            self.window.channels[channel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
            else:
                next_level = self.sequence.cues[0].channels[channel-1]
            self.window.channels[channel-1].next_level = next_level
            self.window.channels[channel-1].queue_draw()
        pass

    def on_dmx_3(self, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[3][output]
            level = dmxframe[output]
            self.dmx.frame[3][output] = level
            self.window.channels[channel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
            else:
                next_level = self.sequence.cues[0].channels[channel-1]
            self.window.channels[channel-1].next_level = next_level
            self.window.channels[channel-1].queue_draw()

    def fetch_dmx(self, request, univ, dmxframe):
        if dmxframe:
            for output in range(len(dmxframe)):
                channel = self.patch.outputs[univ][output]
                if channel:
                    level = dmxframe[output]
                    self.dmx.frame[univ][output] = level
                    self.window.channels[channel-1].level = level
                    if self.sequence.position < self.sequence.last:
                        next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
                    else:
                        next_level = self.sequence.cues[0].channels[channel-1]
                    self.window.channels[channel-1].next_level = next_level
                    self.window.channels[channel-1].queue_draw()

    def _new(self, action, parameter):
        # TODO: Verify this entire fonction
        del(self.chasers[:])
        # Redraw Sequential Window
        self.sequence = Sequence(1, self.patch)
        self.sequence.window = self.window
        cue = Cue(self.sequence.last+1, "0", text="Last Cue")
        self.sequence.add_cue(cue)
        self.sequence.position = 0
        self.window.sequential.time_in = self.sequence.cues[1].time_in
        self.window.sequential.time_out = self.sequence.cues[1].time_out
        self.window.sequential.wait = self.sequence.cues[1].wait
        self.window.cues_liststore = Gtk.ListStore(str, str, str, str, str, str, str)
        for i in range(self.sequence.last):
            if self.sequence.cues[i].wait.is_integer():
                wait = str(int(self.sequence.cues[i].wait))
                if wait == "0":
                    wait = ""
            else:
                wait = str(self.sequence.cues[i].wait)
            if self.sequence.cues[i].time_out.is_integer():
                t_out = int(self.sequence.cues[i].time_out)
            else:
                t_out = self.sequence.cues[i].time_out
            if self.sequence.cues[i].time_in.is_integer():
                t_in = int(self.sequence.cues[i].time_in)
            else:
                t_in = self.sequence.cues[i].time_in
            self.window.cues_liststore.append([str(i), str(self.sequence.cues[i].memory),
                str(self.sequence.cues[i].text), wait,
                str(t_out), str(t_in), ""])
        self.window.step_filter = self.window.cues_liststore.filter_new()
        self.window.step_filter.set_visible_func(self.window.step_filter_func)
        self.window.treeview.set_model(self.window.cues_liststore)
        path = Gtk.TreePath.new_from_indices([0])
        self.window.treeview.set_cursor(path, None, False)
        self.window.seq_grid.queue_draw()
        # Redraw Patch Window
        self.patch.patch_1on1()
        for channel in range(512):
            try:
                self.patch_outputs_tab.liststore[channel][2] = str(channel + 1)
            except:
                pass
        # Redraw Masters Window
        try:
            for i in range(len(self.masters)):
                self.win_masters.scale[i].destroy()
                self.win_masters.flash[i].destroy()
            del(self.win_masters.scale[:])
            del(self.win_masters.ad[:])
            del(self.win_masters.flash[:])
        except:
            pass
        del(self.masters[:])
        # Redraw Groups Window
        for i in range(len(self.win_groups.grps)):
            self.win_groups.grps[i].destroy()
        del(self.groups[:])
        del(self.win_groups.grps[:])
        self.win_groups.flowbox1.invalidate_filter()
        # Redraw Main Window
        self.window.flowbox.invalidate_filter()

    def _open(self, action, parameter):
        # create a filechooserdialog to open:
        # the arguments are: title of the window, parent_window, action,
        # (buttons, response)
        open_dialog = Gtk.FileChooserDialog("Open ASCII File", self.window,
                Gtk.FileChooserAction.OPEN,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))

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

            for i in range(len(self.universes)):
                self.ola_client.FetchDmx(self.universes[i], self.fetch_dmx)

        elif response_id == Gtk.ResponseType.CANCEL:
            print("cancelled: FileChooserAction.OPEN")

        # destroy the FileChooserDialog
        dialog.destroy()

    def _save(self, action, parameter):
        # TODO: remettre le try:
        self.ascii.save()
        """
        try:
            self.ascii.save()
        except:
            self._saveas(None, None)
        """

    def _saveas(self, action, parameter):
        print("Save As")

    def _patch_outputs(self, action, parameter):
        # Create Patch Outputs Tab
        if self.patch_outputs_tab == None:
            self.patch_outputs_tab = PatchOutputsTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.patch_outputs_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Patch Outputs'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.patch_outputs_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.patch_outputs_tab)
            self.window.notebook.set_current_page(page)

    def _patch_channels(self, action, parameter):
        # Create Patch Channels Tab
        if self.patch_channels_tab == None:
            self.patch_channels_tab = PatchChannelsTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.patch_channels_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Patch Channels'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.patch_channels_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.patch_channels_tab)
            self.window.notebook.set_current_page(page)

    def _track_channels(self, action, parameter):
        # Create Track Channels Tab
        if self.track_channels_tab == None:
            self.track_channels_tab = TrackChannelsTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.track_channels_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Track Channels'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.track_channels_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.track_channels_tab)
            self.window.notebook.set_current_page(page)

    def _groups(self, action, parameter):
        # Create Groups Tab
        if self.group_tab == None:
            self.group_tab = GroupTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.group_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Groups'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.group_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.group_tab)
            self.window.notebook.set_current_page(page)

    def _masters(self, action, parameter):
        # Create Masters Tab
        if self.master_tab == None:
            self.master_tab = MasterTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.master_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Masters'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.master_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.master_tab)
            self.window.notebook.set_current_page(page)

    def _sequences(self, action, parameter):
        # Create Sequences Tab
        if self.sequences_tab == None:
            self.sequences_tab = SequenceTab()

            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.sequences_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Sequences'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.sequences_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
            self.window.notebook.grab_focus()
        else:
            page = self.window.notebook.page_num(self.sequences_tab)
            self.window.notebook.set_current_page(page)

    def _channeltime(self, sequence, step):
        # Create Channel Time Tab
        if self.channeltime_tab == None:
            self.channeltime_tab = ChanneltimeTab(sequence, step)

            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.channeltime_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Channel Time'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.channeltime_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.channeltime_tab)
            self.window.notebook.set_current_page(page)

    def _virtual_console(self, action, parameter):
        # Virtual Console Window
        self.virtual_console = VirtualConsoleWindow()
        self.virtual_console.show_all()

    def _settings(self, action, parameter):
        # TODO: Don't open multiple Settings Windows
        self.win_settings = SettingsDialog()
        self.win_settings.settings_dialog.show_all()

    def _shortcuts(self, action, parameter):
        """
            Create Shortcuts Window
        """
        # TODO: Don't open multiple Shortcuts Windows
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/OpenLightingConsole/gtk/help-overlay.ui')
        self.shortcuts = builder.get_object('help_overlay')
        self.shortcuts.set_transient_for(self.window)
        self.shortcuts.show()

    def _about(self, action, parameter):
        """
            Setup about dialog
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        if self.about_window == None:
            builder = Gtk.Builder()
            builder.add_from_resource('/org/gnome/OpenLightingConsole/AboutDialog.ui')
            self.about_window = builder.get_object('about_dialog')
            self.about_window.set_transient_for(self.window)
            self.about_window.connect("response", self._about_response)
            self.about_window.show()
        else:
            self.about_window.present()

    def _about_response(self, dialog, response):
        """
            Destroy about dialog when closed
            @param dialog as Gtk.Dialog
            @param response as int
        """
        dialog.destroy()
        self.about_window = None

    def _exit(self, action, parameter):
        # Stop Chasers Threads
        for i in range(len(self.chasers)):
            if self.chasers[i].run:
                self.chasers[i].run = False
                self.chasers[i].thread.stop()
                self.chasers[i].thread.join()
        self.quit()

if __name__ == "__main__":
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
