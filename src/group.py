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

        self.keystring = ""
        self.last_chan_selected = ""

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
        self.flowbox2.connect('button_press_event', self.on_group_clicked)

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

    def on_group_clicked(self, widget, event):
        for channel in range(512):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()

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
        #print(keyname)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.group_tab = None

    def keypress_g(self):
        """ Select Group """
        # Deselect group selected
        for grp in range(len(self.grps)):
            self.grps[grp].clicked = False
        # Find the group with is number and select it
        if self.keystring != "" and self.keystring != "0":
            group = int(self.keystring)
            for grp in range(len(self.grps)):
                if group == int(self.grps[grp].number):
                    self.grps[grp].clicked = True
        # Deselect all channels
        for channel in range(512):
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
        # Update display
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()
        self.keystring = ""

    def keypress_a(self):
        """ All Channels """
        for j in range(len(self.grps)):
            if self.grps[j].clicked:
                for channel in range(512):
                    level = self.app.groups[j].channels[channel]
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
            self.flowbox1.invalidate_filter()
        else:
            channel = int(self.keystring) - 1
            if channel >= 0 and channel < 512:
                for grp in range(len(self.grps)):
                    if self.grps[grp].clicked:
                        for chan in range(512):
                            self.channels[chan].clicked = False
                self.channels[channel].clicked = True
                self.channels[channel].queue_draw()
                self.flowbox1.invalidate_filter()
                self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
        """ Channel Thru """
        if not self.last_chan_selected:
            return
        to_chan = int(self.keystring)
        if to_chan > int(self.last_chan_selected):
            for chan in range(int(self.last_chan_selected), to_chan):
                self.channels[chan].clicked = True
                self.channels[chan].queue_draw()
        else:
            for chan in range(to_chan - 1, int(self.last_chan_selected)):
                self.channels[chan].clicked = True
                self.channels[chan].queue_draw()
        self.flowbox1.invalidate_filter()
        self.last_chan_selected = self.keystring
        self.keystring = ""

    def keypress_plus(self):
        """ Channel + """
        channel = int(self.keystring) - 1
        if channel >= 0 and channel < 512:
            self.channels[channel].clicked = True
            self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring
            self.keystring = ""

    def keypress_minus(self):
        """ Channel - """
        channel = int(self.keystring) - 1
        if channel >= 0 and channel < 512:
            self.channels[channel].clicked = False
            self.channels[channel].queue_draw()
            self.flowbox1.invalidate_filter()
            self.last_chan_selected = self.keystring
            self.keystring = ""

    def keypress_equal(self):
        """ @ Level """
        # TODO: Pb de calcul du level (en mode % on a 0 = 1 par ex)
        level = int(self.keystring)
        self.keystring = ""
        if Gio.Application.get_default().settings.get_boolean('percent'):
            if level >= 0 and level <= 100:
                level = int(round((level / 100) * 255))
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
                            self.app.groups[grp].channels[channel] = level
        self.flowbox1.invalidate_filter()

    def keypress_colon(self):
        """ Level - % """
        lvl = Gio.Application.get_default().settings.get_int('percent-level')
        for grp in range(len(self.grps)):
            if self.grps[grp].clicked:
                for channel in range(512):
                    if self.channels[channel].clicked:
                        level = self.app.groups[grp].channels[channel]
                        if level - lvl < 0:
                            level = 0
                        else:
                            level = level - lvl
                        self.app.groups[grp].channels[channel] = level
        self.flowbox1.invalidate_filter()

    def keypress_exclam(self):
        """ Level + % """
        lvl = Gio.Application.get_default().settings.get_int('percent-level')
        for grp in range(len(self.grps)):
            if self.grps[grp].clicked:
                for channel in range(512):
                    if self.channels[channel].clicked:
                        level = self.app.groups[grp].channels[channel]
                        if level + lvl > 255:
                            level = 255
                        else:
                            level = level + lvl
                        self.app.groups[grp].channels[channel] = level
        self.flowbox1.invalidate_filter()

    def keypress_N(self):
        """ New Group """
        # If no group number, use the next one
        if self.keystring == "":
            group_nb = self.app.groups[-1].index + 1
        else:
            group_nb = int(self.keystring)

        self.keystring = ""

        channels = array.array('B', [0] * 512)
        txt = str(group_nb)
        self.app.groups.append(Group(group_nb, channels, txt))
        self.grps.append(GroupWidget(self.app.window, self.app.groups[-1].index,
            self.app.groups[-1].text, self.grps))
        for grp in range(len(self.grps)):
            self.grps[grp].clicked = False
        self.grps[-1].clicked = True
        self.flowbox2.add(self.grps[-1])
        self.flowbox1.invalidate_filter()
        self.flowbox2.invalidate_filter()
        self.app.window.show_all()
