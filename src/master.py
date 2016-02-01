from gi.repository import Gtk

class Master(object):
    def __init__(self, page, number, content_type, content_value, groups, chasers, exclude_record=True, text=""):
        self.page = page
        self.number = number
        self.content_type = int(content_type)
        self.content_value = int(content_value)
        self.exclude_record = exclude_record
        self.text = text
        self.groups = groups
        self.chasers = chasers

        if self.content_type == 3:
            #print("Type : Sequence", self.content_value)
            for i in range(len(self.chasers)):
                if self.chasers[i].index == self.content_value:
                    if self.chasers[i] == self.content_value:
                        self.text = self.chasers[i].text
                    self.text = self.chasers[i].text
        elif self.content_type == 2 or self.content_type == 13:
            #print("Type : Groupe", self.content_value)
            for i in range(len(self.groups)):
                #print(self.groups[i].index, self.content_value)
                if self.groups[i].index == self.content_value:
                    #print(self.groups[i].text)
                    self.text = self.groups[i].text
        else:
            print("Type : Inconnu")

class MastersWindow(Gtk.Window):
    def __init__(self, app, masters):

        self.app = app
        self.masters = masters

        Gtk.Window.__init__(self, title="Masters")
        self.set_default_size(800, 500)
        self.set_border_width(10)

        self.scale = []
        self.ad = []
        self.label = []

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)

        for i in range(len(self.masters)):
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
            self.label[i].set_text(masters[i].text)

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

    # TODO: Ce n'est pas le level de la cue qu'il faut vérifier mais celui envoyé en DMX
    def scale_moved(self, scale):
        # On cherche quel scale a été actionné
        for i in range(len(self.scale)):
            if self.scale[i] == scale:
                # Valeur du scale
                level_scale = scale.get_value()

                # Si c'est un groupe
                if self.masters[i].content_type == 2 or self.masters[i].content_type == 13:
                    grp = self.masters[i].content_value
                    for j in range(len(self.masters[i].groups)):
                        if self.masters[i].groups[j].index == grp:
                            #print("Groupe", self.masters[i].groups[j].text)
                            for channel in range(512):
                                if self.masters[i].groups[j].channels[channel] != 0:
                                    # On récupère la valeur enregistrée dans le groupe
                                    level_group = self.masters[i].groups[j].channels[channel]
                                    # Calcul du level
                                    if level_scale == 0:
                                        level = 0
                                    else:
                                        level = int(level_group / (256 / level_scale)) + 1
                                    # TODO (voir + haut): On regarde le level de la cue actuelle
                                    level_cue = self.app.sequence.cues[self.app.sequence.position].channels[channel]
                                    if level_cue > level:
                                        level = level_cue
                                    outputs = self.app.patch.chanels[channel]
                                    for output in outputs:
                                        self.app.dmxframe.set_level(output-1, level)
                            self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
                # Si c'est un chaser
                elif self.masters[i].content_type == 3:
                    nb = self.masters[i].content_value
                    for j in range(len(self.masters[i].chasers)):
                        if self.masters[i].chasers[j].index == nb:
                            print("Chaser", self.masters[i].chasers[j].text)
