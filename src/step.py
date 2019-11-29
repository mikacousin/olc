from olc.channel_time import ChannelTime

class Step(object):
    def __init__(self, sequence=0, cue=0.0,
            time_in=5.0, time_out=5.0, delay_in=0.0, delay_out=0.0,
            wait=0.0, channel_time={}, text=''):

        self.sequence = sequence
        self.cue = cue
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        self.channel_time = channel_time
        self.text = text

        # Total Time
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            self.total_time = self.time_in + self.delay_in + self.wait
        else:
            self.total_time = self.time_out + self.delay_out + self.wait

        for channel in self.channel_time.keys():
            if (self.channel_time[channel].delay + self.channel_time[channel].time
                    + self.wait > self.total_time):
                self.total_time = self.channel_time[channel].delay + self.channel_time[channel].time + self.wait
