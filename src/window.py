import select
from gi.repository import Gtk, GObject, Gdk
from ola import OlaClient

from olc.customwidget import ChanelWidget

class Window(Gtk.ApplicationWindow):

    def __init__(self, app, patch):

        self.app = app
        self.patch = patch

        Gtk.Window.__init__(self, title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1000)

        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("Fonctionne avec ola")
        self.header.props.show_close_button = True

        self.set_titlebar(self.header)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_filter_func(self.filter_func, None) # Fonction de filtrage

        #self.grid = []
        self.chanels = []
        #self.levels = []
        #self.progressbar = []

        for i in range(512):
            """
            # Création de la grille
            self.grid.append(Gtk.Grid())
            #self.grid[i].set_column_homogeneous(True)
            self.flowbox.add(self.grid[i])

            # Création de la liste des outputs
            self.chanels.append(Gtk.ToggleButton(str(i+1))) # Le numéro du chanel comme label
            self.chanels[i].connect("toggled", self.on_button_toggled, str(i+1))

            # Création de la liste des niveaux
            self.levels.append(Gtk.Label(label=" 0 "))
            self.levels[i].set_justify(Gtk.Justification.CENTER)

            # Création de la liste des barres de progression
            self.progressbar.append(Gtk.ProgressBar())
            self.progressbar[i].set_orientation(Gtk.Orientation.VERTICAL)
            self.progressbar[i].set_inverted(1)

            # On place nos éléments dans la grille
            self.grid[i].add(self.chanels[i])
            self.grid[i].attach_next_to(self.levels[i], self.chanels[i], Gtk.PositionType.BOTTOM, 1, 1)
            self.grid[i].attach_next_to(self.progressbar[i], self.chanels[i], Gtk.PositionType.RIGHT, 1, 2)
            """
            self.chanels.append(ChanelWidget(i+1, 0, 0))
            self.flowbox.add(self.chanels[i])

        self.scrolled.add(self.flowbox)
        self.add(self.scrolled)

        self.timeout_id = GObject.timeout_add(50, self.on_timeout, None)

        self.connect('key_press_event', self.on_key_press_event)

    def filter_func(self, child, user_data):
        i = child.get_index()
        for j in range(len(self.patch.chanels[i])):
            #print("Chanel:", i+1, "Output:", self.patch.chanels[i][j])
            if self.patch.chanels[i][j] != 0:
                return child
            else:
                return False

    def on_button_toggled(self, button, name):
        if button.get_active():
            state = "on"
        else:
            state = "off"

    def on_timeout(self, user_data):
        readable, writable, exceptional = select.select([self.app.sock], [], [], 0)
        if readable:
            self.app.ola_client.SocketReady()
        return True

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print (keyname)
        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname =="6" or keyname == "7" or keyname =="8" or keyname == "9" or keyname =="0":
            self.keystring += keyname
        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_a(self):
        for i in range(512):
            level = self.app.dmxframe.get_level(i)
            chanel = self.app.patch.outputs[i] - 1
            if level > 0:
                self.app.window.chanels[chanel].clicked = True
                self.app.window.chanels[chanel].queue_draw()
            else:
                self.app.window.chanels[chanel].clicked = False
                self.app.window.chanels[chanel].queue_draw()
