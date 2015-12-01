import select
from gi.repository import Gtk, GObject, Gdk
from ola import OlaClient

class Window(Gtk.ApplicationWindow):

    def __init__(self, app):

        # TODO: Ne doit pas rester dans cet objet
        ola_client = OlaClient.OlaClient()
        self.sock = ola_client.GetSocket()
        self.universe = 1
        ola_client.RegisterUniverse(unniverse, ola_client.REGISTER, on_dmx)
        #####

        Gtk.Window.__init__(self, title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1000)

        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("Fonctionne avec ola")
        self.header.props.show_close_button = True

        self.set_titlebar(self.header)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)

        self.grid = []
        self.chanels = []
        self.levels = []
        self.progressbar = []

        for i in range(512):
            # Création de la grille
            self.grid.append(Gtk.Grid())
            #self.grid[i].set_column_homogeneous(True)
            self.flowbox.add(self.grid[i])

            # Création de la liste des outputs
            self.chanels.append(Gtk.ToggleButton(str(i+1)))
            #self.chanels.append(Gtk.ToggleButton("Chanel "+str(i+1)))
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

        self.scrolled.add(self.flowbox)
        self.add(self.scrolled)

        self.timeout_id = GObject.timeout_add(50, self.on_timeout, None)

        self.connect('key_press_event', self.on_key_press_event)

    def on_button_toggled(self, button, name):
        if button.get_active():
            state = "on"
        else:
            state = "off"

    def on_timeout(self, user_data):
        readable, writable, exceptional = select.select([sock], [], [], 0)
        if readable:
            ola_client.SocketReady()
        return True

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print (keyname)
        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname =="6" or keyname == "7" or keyname =="8" or keyname == "9" or keyname =="0":
            self.keystring += keyname
        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()


    def on_dmx(dmx):
        # TODO: Ne doit pas rester dans cet objet !
        for i in range(len(dmx)):
            chanel = win.patch.outputs[i]
            #print("output:", i+1, "@", dmx[i], "chanel:", chanel)
            Gtk.ProgressBar.set_fraction(win.progressbar[chanel-1], dmx[i]/255)
            win.levels[chanel-1].set_text(str(dmx[i]))
            win.dmx_frame[i] = dmx[i]
