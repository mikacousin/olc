import array
import threading
import time
from gi.repository import Gio, Gtk, GLib, Gdk

from olc.define import NB_UNIVERSES, MAX_CHANNELS
from olc.settings import Settings

class Master(object):
    def __init__(self, page, number, content_type, content_value, groups, chasers, channels=array.array('B', [0] * MAX_CHANNELS), exclude_record=True, text="", value=0.0):
        self.page = page
        self.number = number
        self.content_type = int(content_type)
        self.content_value = float(content_value)
        self.exclude_record = exclude_record
        self.text = text
        self.groups = groups
        self.chasers = chasers
        self.channels = channels
        # To store DMX values of the master
        self.dmx = array.array('B', [0] * MAX_CHANNELS)
        self.value = value

        # Type 3 : Chaser
        if self.content_type == 3:
            #print("Type : Sequence", self.content_value)
            for i in range(len(self.chasers)):
                if self.chasers[i].index == self.content_value:
                    if self.chasers[i] == self.content_value:
                        self.text = self.chasers[i].text
                    self.text = self.chasers[i].text
        # Type 13 : Group
        elif self.content_type == 13:
            #print("Type : Groupe", self.content_value)
            for i in range(len(self.groups)):
                #print(self.groups[i].index, self.content_value)
                if self.groups[i].index == self.content_value:
                    #print(self.groups[i].text)
                    self.text = self.groups[i].text
        # Type 2 : Channels
        elif self.content_type == 2:
            #print("Type : Channels")
            self.text += 'Ch'
            for channel in range(len(self.channels)):
                if channels[channel] != 0:
                    #print(channel+1, self.channels[channel])
                    self.text += ' ' + str(channel + 1)
        else:
            print("Type : Inconnu")

    def level_changed(self):

        self.app = Gio.Application.get_default()

        self.percent_view = self.app.settings.get_boolean('percent')

        # Master type is Channels
        if self.content_type == 2:
            for channel in range(len(self.channels)):
                if self.value == 0:
                    level = 0
                else:
                    level = int(round(self.channels[channel] / (255 / self.value)))

                self.dmx[channel] = level
            self.app.dmx.send()

        # Master Type is Group
        elif self.content_type == 13:
            grp = self.content_value
            for j in range(len(self.groups)):
                if self.groups[j].index == grp:
                    # For each output
                    for output in range(512):
                        # If Output patched
                        channel = self.app.patch.outputs[output]
                        if channel:
                            if self.groups[j].channels[channel-1] != 0:
                                # Get level saved in group
                                level_group = self.groups[j].channels[channel-1]
                                # Level calculation
                                if self.value == 0:
                                    level = 0
                                else:
                                    level = int(round(level_group / (255 / self.value)))
                                # Update level in master array
                                self.dmx[channel-1] = level

                    # Update DMX levels
                    self.app.dmx.send()

        # Master type is Chaser
        elif self.content_type == 3:
            nb = self.content_value
            for j in range(len(self.chasers)):
                if self.chasers[j].index == nb:
                    #print("Chaser", self.masters[i].chasers[j].text)

                    # On cherche le chaser
                    for k in range(len(self.app.chasers)):
                        if self.app.chasers[k].index == nb:

                            # Si il ne tournait pas et master > 0
                            if self.value and self.app.chasers[k].run == False:
                                # Start Chaser
                                self.app.chasers[k].run = True
                                self.app.chasers[k].thread = ThreadChaser(self.app,
                                        self, k, self.value, self.percent_view)
                                self.app.chasers[k].thread.start()
                            # Si il tournait déjà et master > 0
                            elif self.value and self.app.chasers[k].run == True:
                                # Update Max Level
                                self.app.chasers[k].thread.level_scale = self.value
                            # Si il tournait et que le master passe à 0
                            elif self.value == 0 and self.app.chasers[k].run == True:
                                # Stop Chaser
                                self.app.chasers[k].run = False
                                self.app.chasers[k].thread.stop()
                                for output in range(512):
                                    channel = self.app.patch.outputs[output]
                                    #if self.app.chasers[k].channels[channel-1] != 0:
                                    self.dmx[channel-1] = 0
                                self.app.dmx.send()

class MasterTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.percent_view = self.app.settings.get_boolean('percent')

        self.scale = []
        self.ad = []
        self.flash = []

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)

        for i in range(len(self.app.masters)):
            # Ajustment for scale (initial value, min value, max value,
            # step increment, page increment, page size (not used here)
            if self.percent_view:
                self.ad.append(Gtk.Adjustment(0, 0, 100, 1, 10, 0))
            else:
                self.ad.append(Gtk.Adjustment(0, 0, 255, 1, 10, 0))
            self.scale.append(Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.ad[i]))
            self.scale[i].set_digits(0)
            self.scale[i].set_vexpand(True)
            self.scale[i].set_value_pos(Gtk.PositionType.BOTTOM)
            self.scale[i].set_inverted(True)
            self.scale[i].connect('value-changed', self.scale_moved)
            # A button to flash Master
            self.flash.append(Gtk.Button.new_with_label(self.app.masters[i].text))
            self.flash[i].connect('button-press-event', self.flash_on)
            self.flash[i].connect('button-release-event', self.flash_off)
            # Place masters in tab (4 per line)
            if i == 0:
                self.attach(self.scale[i], 0, 0, 1, 1)
                self.attach_next_to(self.flash[i], self.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
            elif not i % 4:
                self.attach_next_to(self.scale[i], self.flash[i-4], Gtk.PositionType.BOTTOM, 1, 1)
                self.attach_next_to(self.flash[i], self.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
            else:
                self.attach_next_to(self.scale[i], self.scale[i-1], Gtk.PositionType.RIGHT, 1, 1)
                self.attach_next_to(self.flash[i], self.scale[i], Gtk.PositionType.BOTTOM, 1, 1)

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print(keyname)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.master_tab = None

    def on_close_icon(self, widget):
        """ Close Tab on close click """
        page = self.app.window.notebook.page_num(self.app.master_tab)
        self.app.window.notebook.remove_page(page)
        self.app.master_tab = None

    def flash_on(self, widget, event):
        self.percent_view = self.app.settings.get_boolean('percent')
        # Find the number of the button
        for i in range(len(self.app.masters)):
            if widget == self.flash[i]:
                # Put the master's value to Full
                if self.percent_view:
                    self.scale[i].set_value(100)
                else:
                    self.scale[i].set_value(255)
                break

    def flash_off(self, widget, event):
        self.percent_view = self.app.settings.get_boolean('percent')
        # Find the number of the button
        for i in range(len(self.app.masters)):
            if widget == self.flash[i]:
                # Put the master's value to 0
                self.scale[i].set_value(0)
                break

    def scale_moved(self, scale):

        self.percent_view = self.app.settings.get_boolean('percent')

        # Wich Scale has been moved ?
        for i in range(len(self.scale)):
            if self.scale[i] == scale:
                # Scale's Value
                level_scale = self.scale[i].get_value()

                # Master type is Channels
                if self.app.masters[i].content_type == 2:
                    for channel in range(len(self.app.masters[i].channels)):
                        if level_scale == 0:
                            level = 0
                        else:
                            if self.percent_view:
                                level = int(round(self.app.masters[i].channels[channel] / (100 / level_scale)))
                            else:
                                level = int(round(self.app.masters[i].channels[channel] / (255 / level_scale)))
                        self.app.masters[i].dmx[channel] = level
                    self.app.dmx.send()

                # Master Type is Group
                elif self.app.masters[i].content_type == 13:
                    grp = self.app.masters[i].content_value
                    for j in range(len(self.app.masters[i].groups)):
                        if self.app.masters[i].groups[j].index == grp:
                            # For each output
                            for universe in range(NB_UNIVERSES):
                                for output in range(512):
                                    # If Output patched
                                    channel = self.app.patch.outputs[universe][output]
                                    if channel:
                                        if self.app.masters[i].groups[j].channels[channel-1] != 0:
                                            # Get level saved in group
                                            level_group = self.app.masters[i].groups[j].channels[channel-1]
                                            # Level calculation
                                            if level_scale == 0:
                                                level = 0
                                            else:
                                                if self.percent_view:
                                                    level = int(round(level_group / (100 / level_scale)))
                                                else:
                                                    level = int(round(level_group / (255 / level_scale)))
                                            # Update level in master array
                                            self.app.masters[i].dmx[channel-1] = level

                            # Update DMX levels
                            self.app.dmx.send()

                # Master type is Chaser
                elif self.app.masters[i].content_type == 3:
                    nb = self.app.masters[i].content_value
                    for j in range(len(self.app.masters[i].chasers)):
                        if self.app.masters[i].chasers[j].index == nb:
                            #print("Chaser", self.masters[i].chasers[j].text)

                            # On cherche le chaser
                            for k in range(len(self.app.chasers)):
                                    if self.app.chasers[k].index == nb:

                                        # Si il ne tournait pas et master > 0
                                        if level_scale and self.app.chasers[k].run == False:
                                            # Start Chaser
                                            self.app.chasers[k].run = True
                                            self.app.chasers[k].thread = ThreadChaser(self.app,
                                                    self.app.masters[i], k, level_scale, self.percent_view)
                                            self.app.chasers[k].thread.start()
                                        # Si il tournait déjà et master > 0
                                        elif level_scale and self.app.chasers[k].run == True:
                                            # Update Max Level
                                            self.app.chasers[k].thread.level_scale = level_scale
                                        # Si il tournait et que le master passe à 0
                                        elif level_scale == 0 and self.app.chasers[k].run == True:
                                            # Stop Chaser
                                            self.app.chasers[k].run = False
                                            self.app.chasers[k].thread.stop()
                                            for universe in range(NB_UNIVERSES):
                                                for output in range(512):
                                                    channel = self.app.patch.outputs[universe][output]
                                                    #if self.app.chasers[k].channels[channel-1] != 0:
                                                    self.app.masters[i].dmx[channel-1] = 0
                                            self.app.dmx.send()

class ThreadChaser(threading.Thread):
    def __init__(self, app, master, chaser, level_scale, percent_view, name=''):
        threading.Thread.__init__(self)
        self.app = app
        self.master = master
        self.chaser = chaser
        self.level_scale = level_scale
        self.percent_view = percent_view
        self.name = name
        self._stopevent = threading.Event()

    def run(self):
        position = 0

        while self.app.chasers[self.chaser].run:
            # On récupère les temps du pas suivant
            if position != self.app.chasers[self.chaser].last-1:
                t_in = self.app.chasers[self.chaser].cues[position+1].time_in
                t_out = self.app.chasers[self.chaser].cues[position+1].time_out
            else:
                t_in = self.app.chasers[self.chaser].cues[1].time_in
                t_out = self.app.chasers[self.chaser].cues[1].time_out

            # Quel est le temps le plus long
            if t_in > t_out:
                t_max = t_in
                t_min = t_out
            else:
                t_max = t_out
                t_min = t_in

            start_time = time.time() * 1000 # actual time in ms
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            # Boucle sur le temps de monté ou de descente (le plus grand)
            while i < delay and self.app.chasers[self.chaser].run:
                # Mise à jour des niveaux
                GLib.idle_add(self.update_levels, delay, delay_in, delay_out, i, position)
                time.sleep(0.02)
                i = (time.time() * 1000) - start_time

            position += 1
            if position == self.app.chasers[self.chaser].last:
                position = 1


    def stop(self):
        self._stopevent.set()

    def update_levels(self, delay, delay_in, delay_out, i, position):

        self.percent_view = self.app.settings.get_boolean('percent')

        for universe in range(NB_UNIVERSES):
            for output in range(512):

                channel = self.app.patch.outputs[universe][output]

                # On ne modifie que les channels présents dans le chaser
                if self.app.chasers[self.chaser].channels[channel-1] != 0:
                    # Niveau duquel on part
                    old_level = self.app.chasers[self.chaser].cues[position].channels[channel-1]
                    # Niveau dans le sequentiel
                    seq_level = self.app.sequence.cues[self.app.sequence.position].channels[channel-1]

                    if old_level < seq_level:
                        old_level = seq_level

                    # On boucle sur les mémoires et on revient au premier pas
                    if position < self.app.chasers[self.chaser].last-1:
                        next_level = self.app.chasers[self.chaser].cues[position+1].channels[channel-1]
                        if next_level < seq_level:
                            next_level = seq_level
                    else:
                        next_level = self.app.chasers[self.chaser].cues[1].channels[channel-1]
                        if next_level < seq_level:
                            next_level = seq_level
                        self.app.chasers[self.chaser].position = 1

                    # Si le level augmente, on prend le temps de montée
                    if next_level > old_level and i < delay_in:
                        level = int(((next_level - old_level+1) / delay_in) * i) + old_level
                    # si le level descend, on prend le temps de descente
                    elif next_level < old_level and i < delay_out:
                        level = old_level - abs(int(((next_level - old_level-1) / delay_out) * i))
                    # sinon, la valeur est déjà bonne
                    else:
                        level = next_level

                    #print(old_level, next_level, level, channel+1)

                    # On limite le niveau par la valeur du Master
                    if self.percent_view:
                        level = int(round(level / (100 / self.level_scale)))
                    else:
                        level = int(round(level / (255 / self.level_scale)))

                    # Mise à jour de la valeur des masters
                    #self.app.dmx.masters[channel-1] = level
                    self.master.dmx[channel-1] = level

                    #if self.app.chasers[0].cues[position].channels[channel] != 0:
                    #   print("Channel :", channel+1, "@", self.app.chasers[0].cues[position].channels[channel])

        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()
