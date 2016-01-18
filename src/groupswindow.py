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

        for i in range(len(self.groups)):
            # Adjustment for scale (initial value, min value, max value,
            # step increment, page increment, page size (not used here)
            ad.append(Gtk.Adjustment(0, 0, 255, 1, 10, 0))
            self.scale.append(Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=ad[i]))
            self.scale[i].set_digits(0)
            self.scale[i].set_vexpand(True)
            self.scale[i].set_value_pos(Gtk.PositionType.BOTTOM)
            self.scale[i].set_inverted(True)
            self.scale[i].connect("value-changed", self.scale_moved)
            self.label.append(Gtk.Label())
            self.label[i].set_text(groups[i].text)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        for i in range(len(self.scale)):
            self.grid.attach(self.label[i], 0, 0, 1, 1)
            self.grid.attach_next_to(self.scale[i], self.label[i], Gtk.PositionType.BOTTOM, 1, 1)

        self.add(self.grid)

    def scale_moved(self, scale):
        for i in range(len(self.scale)):
            if self.scale[i] == scale:
                print("Le Groupe", self.groups[i].text, "est passé à la valeur", int(scale.get_value()))
