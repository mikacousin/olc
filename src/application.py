import sys
import array
import select
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, GObject
from ola import OlaClient

from olc.settings import Settings, SettingsDialog
from olc.window import Window
from olc.patch import PatchTab
from olc.dmx import Dmx, PatchDmx
from olc.cue import Cue
from olc.sequence import Sequence, SequenceTab
from olc.group import Group, GroupTab
from olc.master import Master, MasterTab
from olc.channel_time import ChanneltimeTab
from olc.customwidgets import GroupWidget
from olc.osc import OscServer
from olc.ascii import Ascii
from olc.midi import MidiTab

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
        #self.universe = 0
        #self.universe = Gio.Application.get_default().settings.get_value('universe')
        self.universe = self.settings.get_int('universe')

        # Create patch (1:1)
        self.patch = PatchDmx()

        # Create OlaClient
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()
        self.ola_client.RegisterUniverse(self.universe, self.ola_client.REGISTER, self.on_dmx)

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

        # For Tabs
        self.patch_tab = None
        self.master_tab = None
        self.group_tab = None
        self.sequences_tab = None
        self.channeltime_tab = None
        self.midi_tab = None

    def do_activate(self):

        # Create Main Window
        self.window = Window(self, self.patch)
        self.sequence.window = self.window
        self.window.show_all()

        # Create several DMX arrays
        self.dmx = Dmx(self.universe, self.patch, self.ola_client, self.sequence, self.masters, self.window)

        # Fetch dmx values on startup
        self.ola_client.FetchDmx(self.universe, self.fetch_dmx)

        # TODO: Test manual crossfade, must be deleted
        self.win_crossfade = CrossfadeWindow()
        self.win_crossfade.show_all()

        # Create and launch OSC server
        self.osc_server = OscServer(self.window)

        # Init of ascii file
        self.ascii = Ascii(None)

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # TODO: Revoir pour le menu et la gestion auto de la fenetre des shortcuts
        menu = self.setup_app_menu()
        self.set_app_menu(menu)
        #self.build_app_menu()

    def build_app_menu(self):
        actionEntries = [
            ('new', self._new),
            ('open', self._open),
            ('save', self._save),
            ('patch', self._patch),
            ('groups', self._groups),
            ('masters', self._masters),
            ('settings', self._settings),
            ('about', self._about),
            ('quit', self._exit),
        ]

        for action, callback in actionEntries:
            simpleAction = Gio.SimpleAction.new(action, None)
            simpleAction.connect('activate', callback)
            self.add_action(simpleAction)

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

        patchAction = Gio.SimpleAction.new('patch', None)
        patchAction.connect('activate', self._patch)
        self.add_action(patchAction)

        groupsAction = Gio.SimpleAction.new('groups', None)
        groupsAction.connect('activate', self._groups)
        self.add_action(groupsAction)

        mastersAction = Gio.SimpleAction.new('masters', None)
        mastersAction.connect('activate', self._masters)
        self.add_action(mastersAction)

        sequencesAction = Gio.SimpleAction.new('sequences', None)
        sequencesAction.connect('activate', self._sequences)
        self.add_action(sequencesAction)

        settingsAction = Gio.SimpleAction.new('settings', None)
        settingsAction.connect('activate', self._settings)
        self.add_action(settingsAction)

        midiAction = Gio.SimpleAction.new('midi', None)
        midiAction.connect('activate', self._midi)
        self.add_action(midiAction)

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

    def on_dmx(self, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[output]
            level = dmxframe[output]
            self.dmx.frame[output] = level
            self.window.channels[channel-1].level = level
            if self.sequence.position < self.sequence.last:
                next_level = self.sequence.cues[self.sequence.position+1].channels[channel-1]
            else:
                next_level = self.sequence.cues[0].channels[channel-1]
            self.window.channels[channel-1].next_level = next_level
            self.window.channels[channel-1].queue_draw()

    def fetch_dmx(self, request, univ, dmxframe):
        for output in range(len(dmxframe)):
            channel = self.patch.outputs[output]
            level = dmxframe[output]
            self.dmx.frame[output] = level
            self.window.channels[channel-1].level = level
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
                self.patch_tab.liststore[channel][2] = str(channel + 1)
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

            self.ola_client.FetchDmx(self.universe, self.fetch_dmx)

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

    def _patch(self, action, parameter):
        # Create Patch Tab
        if self.patch_tab == None:
            self.patch_tab = PatchTab()

            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.patch_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Patch'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.patch_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.patch_tab)
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

    def _midi(self, action, parameter):
        # Create Midi Tab
        if self.midi_tab == None:
            self.midi_tab = MidiTab()

            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect('clicked', self.midi_tab.on_close_icon)
            label = Gtk.Box()
            label.pack_start(Gtk.Label('Midi'), False, False, 0)
            label.pack_start(button, False, False, 0)
            label.show_all()

            self.window.notebook.append_page(self.midi_tab, label)
            self.window.show_all()
            self.window.notebook.set_current_page(-1)
        else:
            page = self.window.notebook.page_num(self.midi_tab)
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

#######################################################################
#TODO: Must be deleted, just for testing manual crosfade
#######################################################################


class CrossfadeWindow(Gtk.Window):
    def __init__(self):

        self.link = True

        Gtk.Window.__init__(self, title='Crossfade')
        self.set_default_size(200, 400)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)

        self.adA = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleA = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adA)
        self.scaleA.set_draw_value(False)
        self.scaleA.set_vexpand(True)
        #self.scaleA.set_value_pos(Gtk.PositionType.BOTTOM)
        self.scaleA.set_inverted(True)
        self.scaleA.connect('value-changed', self.scale_moved)

        self.adB = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleB = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adB)
        self.scaleB.set_draw_value(False)
        self.scaleB.set_vexpand(True)
        #self.scaleB.set_value_pos(Gtk.PositionType.BOTTOM)
        self.scaleB.set_inverted(True)
        self.scaleB.connect('value-changed', self.scale_moved)

        self.button = Gtk.CheckButton('Link crossfade')
        self.button.set_active(True)
        self.button.connect('toggled', self.on_button_toggled)

        self.grid.attach(self.button, 0, 0, 2, 1)
        self.grid.attach_next_to(self.scaleA, self.button, Gtk.PositionType.BOTTOM, 1, 1)
        self.grid.attach_next_to(self.scaleB, self.scaleA, Gtk.PositionType.RIGHT, 1, 1)

        self.add(self.grid)

    def on_button_toggled(self, button):
        if button.get_active():
            self.link = True
        else:
            self.link = False

    def scale_moved(self, scale):
        # TODO: Bug avec In monté puis après monter Out (les levels des channels tombent à 0)
        # TODO: Bug si on arrive sur un wait
        app = Gio.Application.get_default()
        level = scale.get_value()
        position = app.sequence.position

        # TODO: Pouvoir prendre la main pendant un Go

        # TODO: Si on prend la main sur le crossfade, impossible de faire un Go, Seq+, Seq- si on va pas au bout
        if level != 255 and level != 0:
            app.sequence.on_go = True

        if self.link:
            # Update scales position
            if scale == self.scaleA:
                self.scaleB.set_value(level)
            else:
                self.scaleA.set_value(level)

            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return

            # Update sliders position
            delay = app.sequence.cues[position+1].time_out * 1000
            wait = app.sequence.cues[position+1].wait * 1000
            pos = (level / 255) * delay
            # Get SequentialWindow's width to place cursor
            allocation = app.window.sequential.get_allocation()
            app.window.sequential.pos_xA = ((allocation.width - 32) / delay) * pos
            app.window.sequential.pos_xB = app.window.sequential.pos_xA
            app.window.sequential.queue_draw()
            # Update levels
            for output in range(512):

                channel = app.patch.outputs[output]

                old_level = app.sequence.cues[position].channels[channel-1]

                if channel:
                    if position < app.sequence.last - 1:
                        next_level = app.sequence.cues[position+1].channels[channel-1]
                    else:
                        next_level = app.sequence.cues[0].channels[channel-1]

                    if app.dmx.user[channel-1] != -1:
                        user_level = app.dmx.user[channel-1]
                        if next_level < user_level:
                            lvl = user_level - abs(int(((next_level - user_level) / (delay + wait)) * (pos - wait)))
                        elif next_level > user_level:
                            lvl = int(((next_level - user_level) / (delay + wait)) * (pos - wait)) + user_level
                        else:
                            lvl = user_level
                    else:
                        if next_level < old_level:
                            lvl = old_level - abs(int(((next_level - old_level) / (delay + wait)) * (pos - wait)))
                        elif next_level > old_level:
                            lvl = int(((next_level - old_level) / (delay + wait)) * (pos - wait)) + old_level
                        else:
                            lvl = old_level

                    app.dmx.sequence[channel-1] = lvl

            app.dmx.send()
        elif scale == self.scaleA:
            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return
            # Update slider A position
            delay = app.sequence.cues[position+1].time_out * 1000
            wait = app.sequence.cues[position+1].wait * 1000
            pos = (level / 255) * delay
            # Get SequentialWindow's width to place cursor
            allocation = app.window.sequential.get_allocation()
            app.window.sequential.pos_xA = ((allocation.width - 32) / delay) * pos
            app.window.sequential.queue_draw()
            # Update levels
            for output in range(512):

                channel = app.patch.outputs[output]

                old_level = app.sequence.cues[position].channels[channel-1]

                if channel:
                    if position < app.sequence.last - 1:
                        next_level = app.sequence.cues[position+1].channels[channel-1]
                    else:
                        next_level = app.sequence.cues[0].channels[channel-1]

                    if app.dmx.user[channel-1] != -1:
                        user_level = app.dmx.user[channel-1]
                        if next_level < user_level:
                            lvl = user_level - abs(int(((next_level - user_level) / (delay + wait)) * (pos - wait)))
                        else:
                            lvl = user_level
                    else:
                        if next_level < old_level:
                            lvl = old_level - abs(int(((next_level - old_level) / (delay + wait)) * (pos - wait)))
                        else:
                            lvl = old_level

                    app.dmx.sequence[channel-1] = lvl

            app.dmx.send()
        elif scale == self.scaleB:
            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return
            # Update slider B position
            delay = app.sequence.cues[position+1].time_in * 1000
            wait = app.sequence.cues[position+1].wait * 1000
            pos = (level / 255) * delay
            # Get SequentialWindow's width to place cursor
            allocation = app.window.sequential.get_allocation()
            app.window.sequential.pos_xB = ((allocation.width - 32) / delay) * pos
            app.window.sequential.queue_draw()
            # Update levels
            for output in range(512):

                channel = app.patch.outputs[output]

                old_level = app.sequence.cues[position].channels[channel-1]

                if channel:
                    if position < app.sequence.last - 1:
                        next_level = app.sequence.cues[position+1].channels[channel-1]
                    else:
                        next_level = app.sequence.cues[0].channels[channel-1]

                    if app.dmx.user[channel-1] != -1:
                        user_level = app.dmx.user[channel-1]
                        if next_level > user_level:
                            lvl = int(((next_level - user_level) / (delay + wait)) * (pos - wait)) + user_level
                        else:
                            lvl = user_level
                    else:
                        if next_level > old_level:
                            lvl = int(((next_level - old_level) / (delay + wait)) * (pos - wait)) + old_level
                        else:
                            lvl = old_level

                    app.dmx.sequence[channel-1] = lvl

            app.dmx.send()

        if self.scaleA.get_value() == 255 and self.scaleB.get_value() == 255:
            if app.sequence.on_go == True:
                app.sequence.on_go = False
                if self.scaleA.get_inverted():
                    self.scaleA.set_inverted(False)
                    self.scaleB.set_inverted(False)
                else:
                    self.scaleA.set_inverted(True)
                    self.scaleB.set_inverted(True)
                self.scaleA.set_value(0)
                self.scaleB.set_value(0)
                # Empty array of levels enter by user
                app.dmx.user = array.array('h', [-1] * 512)
                # Go to next cue
                position = app.sequence.position
                position += 1
                # If exist
                if position < app.sequence.last - 1:
                    app.sequence.position += 1
                    t_in = app.sequence.cues[position+1].time_in
                    t_out = app.sequence.cues[position+1].time_out
                    t_wait = app.sequence.cues[position+1].wait
                    app.window.sequential.total_time = app.sequence.cues[position + 1].total_time
                    app.window.sequential.time_in = t_in
                    app.window.sequential.time_out = t_out
                    app.window.sequential.wait = t_wait
                    app.window.sequential.channel_time = app.sequence.cues[position + 1].channel_time
                    app.window.sequential.pos_xA = 0
                    app.window.sequential.pos_xB = 0

                    subtitle = "Mem. :"+app.sequence.cues[position].memory+" "+app.sequence.cues[position].text+" - Next Mem. : "+app.sequence.cues[position+1].memory+" "+app.sequence.cues[position+1].text
                    app.window.header.set_subtitle(subtitle)

                    if position == 0:
                        app.window.cues_liststore1[-2][7] = "#232729"
                        app.window.cues_liststore1[position][7] = "#997004"
                    else:
                        app.window.cues_liststore1[position - 1][7] = "#232729"
                        app.window.cues_liststore1[position][7] = "#997004"
                    app.window.step_filter1.refilter()
                    app.window.step_filter2.refilter()
                    path = Gtk.TreePath.new_from_indices([0])
                    app.window.treeview1.set_cursor(path, None, False)
                    app.window.treeview2.set_cursor(path, None, False)
                    app.window.seq_grid.queue_draw()

                    # If Wait
                    if app.sequence.cues[position+1].wait:
                        app.window.keypress_space()
                # Else, we return to first cue
                # TODO: Update code
                else:
                    app.sequence.position = 0
                    position = 0
                    t_in = app.sequence.cues[position+1].time_in
                    t_out = app.sequence.cues[position+1].time_out
                    t_wait = app.sequence.cues[position+1].wait
                    app.window.sequential.time_in = t_in
                    app.window.sequential.time_out = t_out
                    app.window.sequential.wait = t_wait
                    app.window.sequential.pos_xA = 0
                    app.window.sequential.pos_xB = 0
                    app.window.sequential.queue_draw()

if __name__ == "__main__":
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
