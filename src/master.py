import array
import threading
import time
from gi.repository import Gio

from olc.define import NB_UNIVERSES, MAX_CHANNELS


class Master(object):
    def __init__(self, page, number, content_type, content_value, groups,
                 chasers, channels=array.array('B', [0] * MAX_CHANNELS),
                 exclude_record=True, text="", value=0.0):
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
        self.old_value = 0

        self.app = Gio.Application.get_default()

        # Type 0 : None
        if self.content_type == 0:
            pass
        # Type 1 : Preset
        elif self.content_type == 1:
            for mem in self.app.memories:
                if mem.memory == self.content_value:
                    self.text = mem.text
        # Type 2 : Channels
        elif self.content_type == 2:
            self.text += 'Ch'
            for channel, level in enumerate(self.channels):
                if level:
                    self.text += ' ' + str(channel + 1)
        # Type 3 : Chaser
        elif self.content_type == 3:
            for chaser in self.chasers:
                if chaser.index == self.content_value:
                    self.text = chaser.text
        # Type 13 : Group
        elif self.content_type == 13:
            for grp in self.groups:
                if grp.index == self.content_value:
                    self.text = grp.text
        else:
            print("Type : Inconnu")

    def level_changed(self):

        self.percent_view = self.app.settings.get_boolean('percent')

        # Type : None
        if self.content_type == 0:
            return

        # Type : Preset
        if self.content_type == 1:
            preset = self.content_value

            found = False
            for mem in self.app.memories:
                if mem.memory == preset:
                    found = True
                    break
            if found:
                for univ in range(NB_UNIVERSES):
                    for output in range(512):
                        # Only patched channels
                        channel = self.app.patch.outputs[univ][output][0]
                        if channel:
                            if mem.channels[channel - 1]:
                                # Preset's level
                                level = mem.channels[channel - 1]
                                # Level in master
                                if self.value == 0:
                                    level = 0
                                else:
                                    level = int(round(level /
                                                      (255 / self.value)))
                                self.dmx[channel - 1] = level

        # Master type is Channels
        elif self.content_type == 2:
            for channel, lvl in enumerate(self.channels):
                if self.value == 0:
                    level = 0
                else:
                    level = int(round(lvl / (255 / self.value)))

                self.dmx[channel] = level

        # Master Type is Group
        elif self.content_type == 13:
            grp = self.content_value
            for group in self.groups:
                if group.index == grp:
                    # For each output
                    for univ in range(NB_UNIVERSES):
                        for output in range(512):
                            # If Output patched
                            channel = self.app.patch.outputs[univ][output][0]
                            if channel:
                                if group.channels[channel-1] != 0:
                                    # Get level saved in group
                                    level_group = group.channels[channel-1]
                                    # Level calculation
                                    if self.value == 0:
                                        level = 0
                                    else:
                                        level = int(round(level_group /
                                                          (255 / self.value)))
                                    # Update level in master array
                                    self.dmx[channel-1] = level

        # Master type is Chaser
        elif self.content_type == 3:
            nb = self.content_value
            for chsr in self.chasers:
                if chsr.index == nb:

                    # On cherche le chaser
                    for k, chaser in enumerate(self.app.chasers):
                        if chaser.index == nb:

                            # Si il ne tournait pas et master > 0
                            if self.value and chaser.run is False:
                                # Start Chaser
                                self.app.chasers[k].run = True
                                self.app.chasers[k].thread = (
                                    ThreadChaser(self.app, self, k,
                                                 self.value,
                                                 self.percent_view))
                                self.app.chasers[k].thread.start()
                            # Si il tournait déjà et master > 0
                            elif self.value and chaser.run is True:
                                # Update Max Level
                                self.app.chasers[k].thread.level_scale = (
                                    self.value)
                            # Si il tournait et que le master passe à 0
                            elif self.value == 0 and chaser.run is True:
                                # Stop Chaser
                                self.app.chasers[k].run = False
                                self.app.chasers[k].thread.stop()
                                for channel in range(MAX_CHANNELS):
                                    self.dmx[channel - 1] = 0


class ThreadChaser(threading.Thread):
    def __init__(self, app, master, chaser, level_scale,
                 percent_view, name=''):
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
                t_in = self.app.chasers[self.chaser].steps[position+1].time_in
                t_out = (
                    self.app.chasers[self.chaser].steps[position+1].time_out)
            else:
                t_in = self.app.chasers[self.chaser].steps[1].time_in
                t_out = self.app.chasers[self.chaser].steps[1].time_out

            # Quel est le temps le plus long
            if t_in > t_out:
                t_max = t_in
                # t_min = t_out
            else:
                t_max = t_out
                # t_min = t_in

            start_time = time.time() * 1000  # actual time in ms
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            # Boucle sur le temps de monté ou de descente (le plus grand)
            while i < delay and self.app.chasers[self.chaser].run:
                # Mise à jour des niveaux
                self.update_levels(delay, delay_in, delay_out, i, position)
                time.sleep(0.05)
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

                channel = self.app.patch.outputs[universe][output][0]

                # On ne modifie que les channels présents dans le chaser
                if self.app.chasers[self.chaser].channels[channel-1] != 0:
                    # Niveau duquel on part
                    old_level = self.app.chasers[self.chaser].steps[position].cue.channels[channel-1]
                    # Niveau dans le sequentiel
                    seq_level = self.app.sequence.steps[self.app.sequence.position].cue.channels[channel-1]

                    if old_level < seq_level:
                        old_level = seq_level

                    # On boucle sur les mémoires et on revient au premier pas
                    if position < self.app.chasers[self.chaser].last-1:
                        next_level = self.app.chasers[self.chaser].steps[position+1].cue.channels[channel-1]
                        if next_level < seq_level:
                            next_level = seq_level
                    else:
                        next_level = self.app.chasers[self.chaser].steps[1].cue.channels[channel-1]
                        if next_level < seq_level:
                            next_level = seq_level
                        self.app.chasers[self.chaser].position = 1

                    # Si le level augmente, on prend le temps de montée
                    if next_level > old_level and i < delay_in:
                        level = int(((next_level - old_level+1) /
                                     delay_in) * i) + old_level
                    # si le level descend, on prend le temps de descente
                    elif next_level < old_level and i < delay_out:
                        level = old_level - abs(int(((next_level -
                                                      old_level-1) /
                                                     delay_out) * i))
                    # sinon, la valeur est déjà bonne
                    else:
                        level = next_level

                    # print(old_level, next_level, level, channel+1)

                    # On limite le niveau par la valeur du Master
                    level = int(round(level / (255 / self.level_scale)))

                    # Mise à jour de la valeur des masters
                    # self.app.dmx.masters[channel-1] = level
                    self.master.dmx[channel-1] = level
