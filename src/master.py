"""Master is used as abstraction for faders"""

import array
import threading
import time

from olc.define import MAX_CHANNELS, NB_UNIVERSES, App


class Master:
    """Master object

    Attributes:
        page (int): page number
        number (int): master number in page
        content_type (int): 0 = None, 1 = Preset, 2 = Channels, 3 = Sequence,
            13 = Group
        content_value (float or array): number's object or array of channels
        text (str): text
        value (float): value (0-255)
    """

    def __init__(self, page, number, content_type, content_value):
        self.page = page
        self.number = number
        self.content_type = int(content_type)
        self.content_value = None
        self.text = ""
        # To store DMX values of the master
        self.dmx = array.array("B", [0] * MAX_CHANNELS)
        self.value = 0.0
        self.old_value = 0

        # Type 0: None
        if self.content_type == 0:
            pass
        # Type 1: Preset
        elif self.content_type == 1:
            self.content_value = float(content_value)
            if cue := next(
                mem for mem in App().memories if mem.memory == self.content_value
            ):
                self.text = cue.text
        # Type 2: Channels
        elif self.content_type == 2:
            self.text += "Ch"
            self.content_value = content_value
            for channel, level in enumerate(content_value):
                if level:
                    self.text += " " + str(channel + 1)
        # Type 3: Chaser
        elif self.content_type == 3:
            self.content_value = float(content_value)
            if chaser := next(
                chsr for chsr in App().chasers if chsr.index == self.content_value
            ):
                self.text = chaser.text
        # Type 13: Group
        elif self.content_type == 13:
            self.content_value = float(content_value)
            if group := next(
                grp for grp in App().groups if grp.index == self.content_value
            ):
                self.text = group.text
        else:
            print("Master Type : Unknown")

    def set_level(self, value):
        """Set master level

        Args:
            value: New level
        """
        self.value = value
        self.level_changed()

    def level_changed(self):
        """Master level has changed"""
        # Type : None
        if self.content_type == 0:
            return
        # Type : Preset
        if self.content_type == 1:
            self._level_changed_preset()
        # Type: Channels
        elif self.content_type == 2:
            self._level_changed_channels()
        # Type: Group
        elif self.content_type == 13:
            self._level_changed_group()
        # Type: Chaser
        elif self.content_type == 3:
            self._level_changed_chaser()

    def _level_changed_preset(self):
        """New level and type is Preset"""
        if mem := next(
            cue for cue in App().memories if cue.memory == self.content_value
        ):
            for channel in range(MAX_CHANNELS):
                if mem.channels[channel]:
                    # Preset level
                    level = mem.channels[channel]
                    # Level in master
                    level = (
                        0 if self.value == 0 else int(round(level / (255 / self.value)))
                    )
                    self.dmx[channel] = level

    def _level_changed_channels(self):
        """New level and type is Channels"""
        for channel, lvl in enumerate(self.content_value):
            level = 0 if self.value == 0 else int(round(lvl / (255 / self.value)))
            self.dmx[channel] = level

    def _level_changed_group(self):
        """New level and type is Group"""
        # Find group
        if group := next(
            grp for grp in App().groups if grp.index == self.content_value
        ):
            # Get Channels and Levels in group
            for channel, lvl in enumerate(group.channels):
                if lvl:
                    # Calculate level
                    level = (
                        0 if self.value == 0 else int(round(lvl / (255 / self.value)))
                    )
                    # Update level in master array
                    self.dmx[channel] = level

    def _level_changed_chaser(self):
        """New level and type is Chaser"""
        number = self.content_value
        # On cherche le chaser
        for i, chaser in enumerate(App().chasers):
            if chaser.index == number:
                # Si il ne tournait pas et master > 0
                if self.value and chaser.run is False:
                    # Start Chaser
                    App().chasers[i].run = True
                    App().chasers[i].thread = ThreadChaser(self, i, self.value)
                    App().chasers[i].thread.start()
                # Si il tournait déjà et master > 0
                elif self.value and chaser.run is True:
                    # Update Max Level
                    App().chasers[i].thread.level_scale = self.value
                # Si il tournait et que le master passe à 0
                elif self.value == 0 and chaser.run is True:
                    # Stop Chaser
                    App().chasers[i].run = False
                    App().chasers[i].thread.stop()
                    for channel in range(MAX_CHANNELS):
                        self.dmx[channel - 1] = 0


class ThreadChaser(threading.Thread):
    """Thread for chasers"""

    def __init__(self, master, chaser, level_scale, name=""):
        threading.Thread.__init__(self)
        self.master = master
        self.chaser = chaser
        self.level_scale = level_scale
        self.name = name
        self._stopevent = threading.Event()

    def run(self):
        position = 0

        while App().chasers[self.chaser].run:
            # Next Step Time In and Time Out
            if position != App().chasers[self.chaser].last - 1:
                t_in = App().chasers[self.chaser].steps[position + 1].time_in
                t_out = App().chasers[self.chaser].steps[position + 1].time_out
            else:
                t_in = App().chasers[self.chaser].steps[1].time_in
                t_out = App().chasers[self.chaser].steps[1].time_out

            # Longest Time
            t_max = max([t_in, t_out])

            start_time = time.time() * 1000  # actual time in ms
            delay = t_max * 1000
            delay_in = t_in * 1000
            delay_out = t_out * 1000
            i = (time.time() * 1000) - start_time

            # Loop on longest time
            while i < delay and App().chasers[self.chaser].run:
                # Update levels
                self.update_levels(delay_in, delay_out, i, position)
                time.sleep(0.05)
                i = (time.time() * 1000) - start_time

            position += 1
            if position == App().chasers[self.chaser].last:
                position = 1

    def stop(self):
        """Stop thread"""
        self._stopevent.set()

    def update_levels(self, delay_in, delay_out, i, position):
        """Update levels every 50ms

        Args:
            delay_in: Time In
            delay_out: Time Out
            i: Time spent
            position: Step
        """
        for universe in range(NB_UNIVERSES):
            for output in range(512):
                channel = App().patch.outputs[universe][output][0]
                # Change only channels in chaser
                if App().chasers[self.chaser].channels[channel - 1] != 0:
                    # Start level
                    old_level = (
                        App()
                        .chasers[self.chaser]
                        .steps[position]
                        .cue.channels[channel - 1]
                    )
                    # Level in the sequence
                    seq_level = (
                        App()
                        .sequence.steps[App().sequence.position]
                        .cue.channels[channel - 1]
                    )
                    if old_level < seq_level:
                        old_level = seq_level
                    # Loop on cues and come back at first step
                    if position < App().chasers[self.chaser].last - 1:
                        next_level = (
                            App()
                            .chasers[self.chaser]
                            .steps[position + 1]
                            .cue.channels[channel - 1]
                        )
                        if next_level < seq_level:
                            next_level = seq_level
                    else:
                        next_level = (
                            App()
                            .chasers[self.chaser]
                            .steps[1]
                            .cue.channels[channel - 1]
                        )
                        if next_level < seq_level:
                            next_level = seq_level
                        App().chasers[self.chaser].position = 1
                    # If level increases, use time In
                    if next_level > old_level and i < delay_in:
                        level = (
                            int(((next_level - old_level + 1) / delay_in) * i)
                            + old_level
                        )
                    # If level decreases, use time Out
                    elif next_level < old_level and i < delay_out:
                        level = old_level - abs(
                            int(((next_level - old_level - 1) / delay_out) * i)
                        )
                    # Else, level is already good
                    else:
                        level = next_level
                    # Apply Grand Master to level
                    level = int(round(level / (255 / self.level_scale)))
                    # Update master level
                    self.master.dmx[channel - 1] = level
