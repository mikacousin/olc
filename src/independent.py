"""An independent control channels excluded from recording"""

import array

from olc.define import MAX_CHANNELS


class Independent:
    """Independent object

    Attributes:
        number (int): independent number
        level (int): independent level (0-255)
        channels (set): channels present in independent
        levels (array): channels levels
        text (str): independent text
        dmx (array): DMX levels
    """

    def __init__(self, number, text="", levels=array.array("B", [0] * MAX_CHANNELS)):
        self.number = int(number)
        self.level = 0
        self.channels = set()
        self.levels = levels
        self.text = text
        self.dmx = array.array("B", [0] * MAX_CHANNELS)

        self.update_channels()

    def update_channels(self):
        """Update set of channels"""
        for channel, level in enumerate(self.levels):
            if level:
                self.channels.add(channel)

    def set_levels(self, levels):
        """Define channels and levels

        Args:
            levels (array): channels levels
        """
        self.levels = levels
        self.channels = set()
        for channel, level in enumerate(levels):
            if level:
                self.channels.add(channel)

    def update_dmx(self):
        """Update DMX levels"""
        for channel, level in enumerate(self.levels):
            self.dmx[channel] = round(level * (self.level / 255))


class Independents:
    """All independents

    Attributes:
        independents (list): list of independents
        channels (set): list of channels present in independents
    """

    def __init__(self):
        self.independents = []
        self.channels = set()

    def add(self, independent):
        """Add an independent"""
        number = independent.number
        for inde in self.independents:
            if inde.number == number:
                print("Independent already exist")
                return False
        self.independents.append(independent)
        self._update_channels()
        return True

    def get_channels(self):
        """Returns: (set) channels presents in all independent"""
        return self.channels

    def _update_channels(self):
        """Update set of channels present in all independents"""
        self.channels = set()
        for inde in self.independents:
            self.channels = self.channels | inde.channels
