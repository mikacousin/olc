import array
from gi.repository import Gio, Gtk, Gdk

from olc.customwidgets import ChannelWidget, GroupWidget

class Group(object):
    def __init__(self, index, channels=array.array('B', [0] * 512), text=""):
        self.index = index
        self.channels = channels
        self.text = text

class GroupTab(Gtk.Paned):
    def __init__(self):

        self.app = Gio.Application.get_default()

        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_position(300)

        self.scrolled1 = Gtk.ScrolledWindow()
        self.scrolled1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox1 = Gtk.FlowBox()
        self.flowbox1.set_valign(Gtk.Align.START)
        self.flowbox1.set_max_children_per_line(20)
        self.flowbox1.set_homogeneous(True)
        self.flowbox1.set_selection_mode(Gtk.SelectionMode.NONE)

        self.channels = []

        for i in range(512):
            self.channels.append(ChannelWidget(i+1, 0, 0))
            self.flowbox1.add(self.channels[i])

        self.scrolled1.add(self.flowbox1)

        self.add1(self.scrolled1)

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

        for i in range(len(self.app.groups)):
            self.grps.append(GroupWidget(self.app.window, self.app.groups[i].index, self.app.groups[i].text,
                self.grps))
            self.flowbox2.add(self.grps[i])

        self.scrolled2.add(self.flowbox2)

        self.add2(self.scrolled2)

        self.flowbox1.set_filter_func(self.filter_channels, None)

        self.flowbox2.connect('child_activated', self.on_group_selected)

        self.connect('key_press_event', self.on_key_press_event)

    def filter_channels(self, child, user_data):
        """ Pour n'afficher que les channels du groupe """
        i = child.get_index() # Numéro du widget qu'on filtre (channel - 1)
        # On cherche le groupe actuellement séléctionné
        for j in range(len(self.grps)):
            if self.grps[j].clicked:
                # Si le channel est dans le groupe, on l'affiche
                if self.app.groups[j].channels[i] != 0 or self.channels[i].clicked == True:
                    # On récupère le level (next_level à la même valeur)
                    self.channels[i].level = self.app.groups[j].channels[i]
                    self.channels[i].next_level = self.app.groups[j].channels[i]
                    return child
                else:
                    return False

    def filter_groups(self, child, user_data):
        return child

    def on_group_selected(self, flowbox, child):
        for grp in range(len(self.grps)):
            self.grps[grp].clicked = False
        for channel in range(512):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.grps[child.get_index()].clicked = True
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        print(keyname)
