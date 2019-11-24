import array

from olc.define import MAX_CHANNELS

class Cue(object):
    def __init__(self, sequence, memory, channels=array.array('B', [0] * MAX_CHANNELS),
            time_in=5.0, time_out=5.0, delay_in=0.0, delay_out=0.0, wait=0.0,
            text="", channel_time={}):
        # Sequence == 0 : Global Memory
        # Sequence != 0 : Cue in a sequence
        self.sequence = sequence
        self.memory = memory
        self.channels = channels
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        self.text = text
        self.channel_time = channel_time

        # Find the time cue need to operate
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            self.total_time = self.time_in + self.delay_in + self.wait
        else:
            self.total_time = self.time_out + self.delay_out + self.wait
        for channel in self.channel_time.keys():
            if channel_time[channel].delay + channel_time[channel].time + self.wait > self.total_time:
                self.total_time = channel_time[channel].delay + channel_time[channel].time + self.wait

    def set_level(self, channel, level):
        self.channels[channel] = level

    def get_level(self, channel):
        return self.channels[channel]

class ChannelTime(object):
    def __init__(self, delay=0.0, time=0.0):
        self.delay = delay
        self.time = time

if __name__ == "__main__":

    channels = array.array('B', [0] * MAX_CHANNELS)
    for i in range(MAX_CHANNELS):
        channels[i] = int(i/2)
    cue = Cue(0, 10.0, channels, text="Mise")

    print("Memory :", cue.memory)
    print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
    print("Delay In :", cue.delay_in, "\nDelay Out :", cue.delay_out)
    print("Text :", cue.text)
    print("")
    for i in range(MAX_CHANNELS):
        print("Chanel :", i+1, "@", cue.channels[i])
