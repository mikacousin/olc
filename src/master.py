import array
import threading
import time
from gi.repository import Gtk, GLib

# TODO : - les Masters ne doivent pas descendre sous la valeur dmx envoyée par le sequentiel ou
#        entrée directement à la main.
#        - les Masters ne doivent pas bouger sur un Go si leur valeur est supérieure à celle envoyée dans
#        le séquentiel

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

                            # Pour chaque Output
                            for output in range(512):

                                # Si l'output est patché sur un channel
                                channel = self.app.patch.outputs[output]
                                if channel:
                                    if self.masters[i].groups[j].channels[channel-1] != 0:
                                        # On récupère la valeur enregistrée dans le groupe
                                        level_group = self.masters[i].groups[j].channels[channel-1]
                                        # Calcul du level
                                        if level_scale == 0:
                                            level = 0
                                        else:
                                            level = int(level_group / (256 / level_scale)) + 1

                                        # Mise à jour du tableau des niveau de masters
                                        self.app.dmx.masters[channel-1] = level

                            # On met à jour les niveau DMX
                            self.app.dmx.send()

                # Si c'est un chaser
                elif self.masters[i].content_type == 3:
                    nb = self.masters[i].content_value
                    for j in range(len(self.masters[i].chasers)):
                        if self.masters[i].chasers[j].index == nb:
                            #print("Chaser", self.masters[i].chasers[j].text)

                            # On cherche le chaser
                            for k in range(len(self.app.chasers)):
                                    if self.app.chasers[k].index == nb:

                                        # Si il tournait et que le master passe à 0
                                        if level_scale == 0 and self.app.chasers[k].run == True:
                                            self.app.chasers[k].run = False
                                            # TODO: Stop chaser
                                            self.thread.stop()
                                        # Si il ne tournait pas et master > 0
                                        elif level_scale and self.app.chasers[k].run == False:
                                            self.app.chasers[k].run = True
                                            # TODO: Lancer chaser
                                            self.thread = ThreadChaser(self.app, k, level_scale)
                                            self.thread.start()
                                        # Si il tournait déjà et master > 0
                                        elif level_scale and self.app.chasers[k].run == True:
                                            # TODO: modifier valeurs max du chaser
                                            self.thread.level_scale = level_scale

class ThreadChaser(threading.Thread):
    def __init__(self, app, chaser, level_scale, name=''):
        threading.Thread.__init__(self)
        self.app = app
        self.chaser = chaser
        self.level_scale = level_scale
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
            while i < delay:
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

        for output in range(512):

            channel = self.app.patch.outputs[output]

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

                #print(old_level, next_level, level, chanel+1)

                # On limite le niveau par la valeur du Master
                level = int(level / (256 / self.level_scale))

                self.app.dmx.masters[channel-1] = level

                #if self.app.chasers[0].cues[position].channels[channel] != 0:
                #   print("Channel :", channel+1, "@", self.app.chasers[0].cues[position].channels[channel])

        #self.app.ola_client.SendDmx(self.app.universe, self.app.dmxframe.dmx_frame)
        self.app.dmx.send()
