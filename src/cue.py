import array

class Cue(object):
    def __init__(self, index, memory, channels=array.array('B', [0] * 512), time_in=5.0, time_out=5.0, wait=0.0, text="", channel_time={}):
        self.index = index
        self.memory = memory
        self.channels = channels
        self.time_in = time_in
        self.time_out = time_out
        self.wait = wait
        self.text = text
        self.channel_time = channel_time

        # Find the time cue need to operate
        if self.time_in > self.time_out:
            self.total_time = self.time_in + self.wait
        else:
            self.total_time = self.time_out + self.wait
        for channel in self.channel_time.keys():
            #print(channel, channel_time[channel].delay, channel_time[channel].time)
            if channel_time[channel].delay + channel_time[channel].time > self.total_time:
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

    channels = array.array('B', [0] * 512)
    for i in range(512):
        channels[i] = int(i/2)
    cue = Cue(1, 10.0, channels, text="Mise")

    print("Step :", cue.index, "Memory :",cue.memory)
    print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
    print("Text :", cue.text)
    print("")
    for i in range(512):
        print("Chanel :", i+1, "@", cue.channels[i])
