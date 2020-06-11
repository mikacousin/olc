import array

from olc.define import MAX_CHANNELS


class Cue:
    def __init__(
        self, sequence, memory, channels=array.array("B", [0] * MAX_CHANNELS), text=""
    ):

        # Sequence == 0 : Global Memory
        # Sequence != 0 : Cue in a sequence
        self.sequence = sequence
        self.memory = memory
        self.channels = channels
        self.text = text

    def set_level(self, channel, level):
        if (
            isinstance(level, int)
            and level >= 0
            and level < 256
            and isinstance(channel, int)
            and channel >= 0
            and channel < MAX_CHANNELS
        ):
            self.channels[channel] = level

    def get_level(self, channel):
        return self.channels[channel]
