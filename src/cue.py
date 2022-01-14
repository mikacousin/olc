"""A Cue or a Preset is used to store intensities for playback in a Sequence."""

import array

from olc.define import MAX_CHANNELS


class Cue:
    """Cue/Preset object

    A cue is attached to a sequence and a preset is a global memory

    Attributes:
        sequence (int): sequence number (0 for Preset)
        memory (float): cue's number
        channels (array): channels's levels
        text (str): cue's text
    """

    def __init__(
        self,
        sequence,
        memory,
        channels=array.array("B", [0] * MAX_CHANNELS),
        text="",
    ):

        self.sequence = sequence
        self.memory = memory
        self.channels = channels
        self.text = text

    def set_level(self, channel, level):
        """Set level of a channel.

        Args :
            channel: channel number
            level: level
        """
        if (
            isinstance(level, int)
            and 0 <= level < 256
            and isinstance(channel, int)
            and 0 <= channel < MAX_CHANNELS
        ):
            self.channels[channel] = level

    def get_level(self, channel):
        """Get channel's level

        Args:
            channel: channel number

        Returns:
            channel's level (0-255)
        """
        return self.channels[channel]
