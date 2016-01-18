from gi.repository import Gtk

class GroupsWindow(Gtk.Window):
    def __init__(self, app, groups):

        self.app = app
        self.groups = groups

        Gtk.Window.__init__(self, title="Groups")
        self.set_default_size(800, 200)
        self.set_border_width(10)

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
