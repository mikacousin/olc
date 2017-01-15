from gi.repository import Gio, Gtk, Gdk

from olc.customwidgets import ChannelWidget, GroupWidget

class GroupsWindow(Gtk.Window):
    def __init__(self, app, groups):

        self.app = app
        self.groups = groups

        self.keystring = ""
        self.last_chan_selected = ""

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

        self.grp_flowbox1 = Gtk.FlowBox()
        self.grp_flowbox1.set_valign(Gtk.Align.START)
        self.grp_flowbox1.set_max_children_per_line(20)
        self.grp_flowbox1.set_homogeneous(True)
        self.grp_flowbox1.set_selection_mode(Gtk.SelectionMode.NONE)

        self.channels = []

        for i in range(512):
            self.channels.append(ChannelWidget(i+1, 0, 0))
            self.grp_flowbox1.add(self.channels[i])

        self.scrolled1.add(self.grp_flowbox1)
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
        self.grp_flowbox1.set_filter_func(self.filter_channels, None)

        self.add(self.paned)

        self.flowbox2.connect('child_activated', self.on_group_selected)
        self.connect('key_press_event', self.on_key_press_event)

    def filter_channels(self, child, user_data):
        """ Pour n'afficher que les channels du groupe """
        i = child.get_index() # Numéro du widget qu'on filtre (channel-1)
        # On cherche le groupe actuellement séléctionné
        for j in range(len(self.grps)):
            if self.grps[j].clicked:
                # Si le channel est dans le groupe, on l'affiche
                if self.groups[j].channels[i] != 0 or self.channels[i].clicked == True:
                    # On récupère le level (next_level à la même valeur)
                    self.channels[i].level = self.groups[j].channels[i]
                    self.channels[i].next_level = self.groups[j].channels[i]
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
        self.grp_flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print(keyname)

        if keyname == "1" or keyname == "2" or keyname == "3" or keyname == "4" or keyname == "5" or keyname == "6" or keyname == "7" or keyname == "8" or keyname == "9" or keyname == "0":
            self.keystring += keyname
        if keyname == "KP_1" or keyname == "KP_2" or keyname == "KP_3" or keyname == "KP_4" or keyname == "KP_5" or keyname == "KP_6" or keyname == "KP_7" or keyname == "KP_8" or keyname == "KP_9" or keyname == "KP_0":
            self.keystring += keyname[3:]

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_a(self):
        """ All Channels """
        for j in range(len(self.grps)):
            if self.grps[j].clicked:
                for channel in range(512):
                    level = self.groups[j].channels[channel]
                    if level > 0:
                        self.channels[channel].clicked = True
                        self.channels[channel].queue_draw()
                    else:
                        self.channels[channel].clicked = False
                        self.channels[channel].queue_draw()

    def keypress_c(self):
        """ Channel """
        if self.keystring == "" or self.keystring == "0":
            for grp in range(len(self.grps)):
                if self.grps[grp].clicked:
                    for channel in range(512):
                        self.channels[channel].clicked = False
                        self.channels[channel].queue_draw()
            self.grp_flowbox1.invalidate_filter()
        else:
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < 512:
                for grp in range(len(self.grps)):
                    if self.grps[grp].clicked:
                        for chan in range(512):
                            self.channels[chan].clicked = False
                self.channels[channel].clicked = True
                self.channels[channel].queue_draw()
                self.grp_flowbox1.invalidate_filter()
                self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Thru """
        to_chan = int(self.keystring)
        for chan in range(int(self.last_chan_selected), to_chan):
            self.channels[chan].clicked = True
            self.channels[chan].queue_draw()
        self.grp_flowbox1.invalidate_filter()
        self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_plus(self):
        """ + """
        channel = int(self.keystring) - 1
        if channel >= 0 and channel < 512:
            self.channels[channel].clicked = True
            self.channels[channel].queue_draw()
            self.grp_flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring
            self.keystring = ""

    def keypress_minus(self):
        """ - """
        channel = int(self.keystring) - 1
        if channel >= 0 and channel < 512:
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
            self.grp_flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring
            self.keystring = ""

    def keypress_equal(self):
        """ @ Level """
        # TODO: Pb de calcul du level (en mode % 0 = 1)
        level = int(self.keystring)
        self.keystring = ""
        if Gio.Application.get_default().settings.get_boolean('percent'):
            if level >= 0 and level <= 100:
                level = int(round((level/100)*255))
                #if level > 255:
                #    level = 255
            else:
                level = -1
        else:
            if level > 255:
                level = 255
        for grp in range(len(self.grps)):
            if self.grps[grp].clicked:
                for channel in range(512):
                    if self.channels[channel].clicked:
                        if level != -1:
                            self.groups[grp].channels[channel] = level
        self.grp_flowbox1.invalidate_filter()

    def keypress_colon(self):
        lvl = Gio.Application.get_default().settings.get_int('percent-level')
        for grp in range(len(self.grps)):
            if self.grps[grp].clicked:
                for channel in range(512):
                    if self.channels[channel].clicked:
                        level = self.groups[grp].channels[channel]
                        if level - lvl < 0:
                            level = 0
                        else:
                            level = level - lvl
                        self.groups[grp].channels[channel] = level
        self.grp_flowbox1.invalidate_filter()

    def keypress_exclam(self):
        lvl = Gio.Application.get_default().settings.get_int('percent-level')
        for grp in range(len(self.grps)):
            if self.grps[grp].clicked:
                for channel in range(512):
                    if self.channels[channel].clicked:
                        level = self.groups[grp].channels[channel]
                        if level + lvl > 255:
                            level = 255
                        else:
                            level = level + lvl
                        self.groups[grp].channels[channel] = level
        self.grp_flowbox1.invalidate_filter()
