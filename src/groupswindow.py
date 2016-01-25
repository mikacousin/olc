from gi.repository import Gtk

from olc.customwidgets import ChanelWidget, GroupWidget

class GroupsWindow(Gtk.Window):
    def __init__(self, app, groups):

        self.app = app
        self.groups = groups

        Gtk.Window.__init__(self, title="Groups")
        self.set_default_size(800, 500)
        self.set_border_width(10)

        # Fenêtre séparrée en 2 avec en haut les channels du groupe sélectionné
        # et en bas la liste des groupes
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(300)
        #self.paned.set_wide_handle(True)

        # On affiche les channels avec un flowbox dans une fenêtre avec scroller
        self.scrolled1 = Gtk.ScrolledWindow()
        self.scrolled1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox1 = Gtk.FlowBox()
        self.flowbox1.set_valign(Gtk.Align.START)
        self.flowbox1.set_max_children_per_line(20)
        self.flowbox1.set_homogeneous(True)
        self.flowbox1.set_selection_mode(Gtk.SelectionMode.NONE)

        self.channels = []

        for i in range(512):
            self.channels.append(ChanelWidget(i+1, 0, 0))
            self.flowbox1.add(self.channels[i])

        self.scrolled1.add(self.flowbox1)
        self.paned.add1(self.scrolled1)

        # On affiche les groupes avec un flowbox et un scroller
        self.scrolled2 = Gtk.ScrolledWindow()
        self.scrolled2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox2 = Gtk.FlowBox()
        self.flowbox2.set_valign(Gtk.Align.START)
        self.flowbox2.set_max_children_per_line(20)
        self.flowbox2.set_homogeneous(True)
        self.flowbox2.set_activate_on_single_click(True)
        self.flowbox2.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox2.set_filter_func(self.filter_groups, None)

        self.grps = []

        for i in range(len(self.groups)):
            self.grps.append(GroupWidget(self, self.groups[i].index, self.groups[i].text, self.grps))
            self.flowbox2.add(self.grps[i])

        self.scrolled2.add(self.flowbox2)
        self.paned.add2(self.scrolled2)

        # Définition de la fonction de filtre des channels
        self.flowbox1.set_filter_func(self.filter_channels, None)

        self.add(self.paned)

    def filter_channels(self, child, user_data):
        """ Pour n'afficher que les channels du groupe """
        i = child.get_index() # Numéro du widget qu'on filtre (channel-1)
        # On cherche le groupe actuellement séléctionné
        for j in range(len(self.grps)):
            if self.grps[j].clicked:
                # Si le channel est dans le groupe, on l'affiche
                if self.groups[j].channels[i] != 0:
                    # On récupère le level (next_level à la même valeur)
                    self.channels[i].level = self.groups[j].channels[i]
                    self.channels[i].next_level = self.groups[j].channels[i]
                    return child
                else:
                    return False

    def filter_groups(self, child, user_data):
        return True

        """
        self.scale = []
        self.ad = []
        self.label = []

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)

        for i in range(len(self.groups)):
            # Adjustment for scale (initial value, min value, max value,
            # step increment, page increment, page size (not used here)
            self.ad.append(Gtk.Adjustment(0, 0, 255, 1, 10, 0))
            self.scale.append(Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.ad[i]))
            self.scale[i].set_digits(0)
            self.scale[i].set_vexpand(True)
            self.scale[i].set_value_pos(Gtk.PositionType.BOTTOM)
            self.scale[i].set_inverted(True)
            self.scale[i].connect("value-changed", self.scale_moved)
            self.label.append(Gtk.Label())
            self.label[i].set_text(groups[i].text)

            if i == 0:
                self.grid.attach(self.label[i], 0, 0, 1, 1)
                self.grid.attach_next_to(self.scale[i], self.label[i], Gtk.PositionType.BOTTOM, 1, 1)
            elif not i % 10:
                self.grid.attach_next_to(self.label[i], self.scale[i-10], Gtk.PositionType.BOTTOM, 1, 1)
                self.grid.attach_next_to(self.scale[i], self.label[i], Gtk.PositionType.BOTTOM, 1, 1)
            else:
                self.grid.attach_next_to(self.label[i], self.label[i-1], Gtk.PositionType.RIGHT, 1, 1)
                self.grid.attach_next_to(self.scale[i], self.label[i], Gtk.PositionType.BOTTOM, 1, 1)

        self.add(self.grid)

    def scale_moved(self, scale):
        # On cherche quel scale a été actionné
        for i in range(len(self.scale)):
            if self.scale[i] == scale:
                # Valeur du scale
                level_scale = scale.get_value()
                for channel in range(512):
                    # Si le channel a une valeur différente de 0 dans le groupe
                    if self.groups[i].channels[channel] != 0:
                        # On récupère la valeur enregistrée dans le groupe
                        level_group = self.groups[i].channels[channel]
                        # Calcul du level
                        if level_scale == 0:
                            level = 0
                        else:
                            level = int(level_group / (256 / level_scale)) + 1
                        # On regarde le level de la cue actuelle
                        level_cue = self.app.sequence.cues[self.app.sequence.position].channels[channel]
                        if level_cue > level:
                            level = level_cue
                        outputs = self.app.patch.chanels[channel]
                        for output in outputs:
                            self.app.dmxframe.set_level(output-1, level)
                self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        """
