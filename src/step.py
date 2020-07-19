class Step:
    """Step"""
    def __init__(
        self,
        sequence=0,
        cue=None,
        time_in=5.0,
        time_out=5.0,
        delay_in=0.0,
        delay_out=0.0,
        wait=0.0,
        channel_time=None,
        text="",
    ):

        self.sequence = sequence
        self.cue = cue
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        if channel_time is None:
            channel_time = {}
        self.channel_time = channel_time
        self.text = text

        self.update_total_time()

    def update_total_time(self):
        """Calculate Total Time"""
        if self.time_in + self.delay_in > self.time_out + self.delay_out:
            self.total_time = self.time_in + self.delay_in + self.wait
        else:
            self.total_time = self.time_out + self.delay_out + self.wait

        for channel in self.channel_time.keys():
            if (
                self.channel_time[channel].delay
                + self.channel_time[channel].time
                + self.wait
                > self.total_time
            ):
                self.total_time = (
                    self.channel_time[channel].delay
                    + self.channel_time[channel].time
                    + self.wait
                )

    def set_time_in(self, time_in):
        """Set Time In"""
        self.time_in = time_in
        self.update_total_time()

    def set_time_out(self, time_out):
        """Set Time Out"""
        self.time_out = time_out
        self.update_total_time()

    def set_delay_in(self, delay_in):
        """Set Delay In"""
        self.delay_in = delay_in
        self.update_total_time()

    def set_delay_out(self, delay_out):
        """Set Delay Out"""
        self.delay_out = delay_out
        self.update_total_time()

    def set_wait(self, wait):
        """Set Wait"""
        self.wait = wait
        self.update_total_time()

    def set_time(self, time):
        """Set Time In and Time Out"""
        self.time_in = time
        self.time_out = time
        self.update_total_time()

    def set_delay(self, delay):
        """Set Delay In and Out"""
        self.delay_in = delay
        self.delay_out = delay
        self.update_total_time()
