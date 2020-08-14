"""Used for manual crossfade"""

import array

from olc.define import MAX_CHANNELS, App
from olc.sequence import update_ui


class Scale:
    """For faders"""

    def __init__(self):
        self.value = 0

    def set_value(self, value):
        """Set scale value"""
        if 0 <= value < 256:
            self.value = value

    def get_value(self):
        """Return scale value"""
        return self.value


class CrossFade:
    """For Manual Crossfade"""

    def __init__(self):
        self.scale_a = Scale()
        self.scale_b = Scale()

        self.manual = False

    def scale_moved(self, scale):
        """On moved"""
        level = scale.get_value()

        if level not in (255, 0):
            App().sequence.on_go = True
            # If Go is sent, stop it
            if App().crossfade.manual and App().sequence.thread:
                if App().sequence.thread.is_alive():
                    App().sequence.thread.stop()
                    App().sequence.thread.join()

        if scale in (self.scale_a, self.scale_b):
            if App().sequence.last == 0:
                # If sequential is empty, don't do anything
                App().sequence.on_go = False
                return
            # Update sliders position
            self.update_slider(scale, level)

        if self.scale_a.get_value() == 255 and self.scale_b.get_value() == 255:
            # In and Out Crossfades at Full
            self.at_full()

    def at_full(self):
        """Slider A and B at Full"""
        if App().sequence.on_go:
            self.manual = False
            App().sequence.on_go = False
            # Empty array of levels enter by user
            App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)
            # Go to next step
            next_step = App().sequence.position + 1
            if next_step < App().sequence.last - 1:
                # Next step
                App().sequence.position += 1
                next_step += 1
            else:
                # Return to first step
                App().sequence.position = 0
                next_step = 1
            # Update UI
            App().window.sequential.total_time = (
                App().sequence.steps[next_step].total_time
            )
            App().window.sequential.time_in = App().sequence.steps[next_step].time_in
            App().window.sequential.time_out = App().sequence.steps[next_step].time_out
            App().window.sequential.delay_in = App().sequence.steps[next_step].delay_in
            App().window.sequential.delay_out = (
                App().sequence.steps[next_step].delay_out
            )
            App().window.sequential.wait = App().sequence.steps[next_step].wait
            App().window.sequential.channel_time = (
                App().sequence.steps[next_step].channel_time
            )
            App().window.sequential.position_a = 0
            App().window.sequential.position_b = 0
            subtitle = (
                "Mem. :"
                + str(App().sequence.steps[App().sequence.position].cue.memory)
                + " "
                + App().sequence.steps[App().sequence.position].text
                + " - Next Mem. : "
                + str(App().sequence.steps[next_step].cue.memory)
                + " "
                + App().sequence.steps[next_step].text
            )
            update_ui(App().sequence.position, subtitle)
            # If Wait
            if App().sequence.steps[next_step].wait:
                App().sequence.on_go = False
                App().sequence.go(None, None)

    def update_slider(self, scale, level):
        """Update sliders position"""
        total_time = App().sequence.steps[App().sequence.position + 1].total_time * 1000
        wait = App().sequence.steps[App().sequence.position + 1].wait * 1000
        position = (level / 255) * total_time
        if scale == self.scale_a:
            App().window.sequential.position_a = (
                (App().window.sequential.get_allocation().width - 32) / total_time
            ) * position
        elif scale == self.scale_b:
            App().window.sequential.position_b = (
                (App().window.sequential.get_allocation().width - 32) / total_time
            ) * position
        App().window.sequential.queue_draw()
        # Update levels
        if position >= wait:
            for channel in range(MAX_CHANNELS):
                old_level = (
                    App().sequence.steps[App().sequence.position].cue.channels[channel]
                )
                if App().sequence.position < App().sequence.last - 1:
                    next_level = (
                        App()
                        .sequence.steps[App().sequence.position + 1]
                        .cue.channels[channel]
                    )
                else:
                    next_level = App().sequence.steps[0].cue.channels[channel]
                if scale == self.scale_a:
                    update_a(
                        channel + 1, old_level, next_level, wait, position,
                    )
                elif scale == self.scale_b:
                    # Get SequentialWindow's width to place cursor
                    update_b(
                        channel + 1, old_level, next_level, wait, position,
                    )


def update_a(channel, old_level, next_level, wait, pos):
    """Update channel level with A Slider"""
    lvl = -1
    time_out = App().sequence.steps[App().sequence.position + 1].time_out * 1000
    delay_out = App().sequence.steps[App().sequence.position + 1].delay_out * 1000
    channel_time = App().sequence.steps[App().sequence.position + 1].channel_time
    if channel in channel_time and next_level < old_level:
        # Channel Time
        ct_delay = channel_time[channel].delay * 1000
        ct_time = channel_time[channel].time * 1000
        if pos < ct_delay + wait:
            lvl = old_level
        elif ct_delay + wait <= pos < ct_delay + ct_time + wait:
            lvl = old_level - abs(
                int(
                    round(
                        ((next_level - old_level) / ct_time) * (pos - ct_delay - wait)
                    )
                )
            )
        elif pos >= ct_delay + ct_time + wait:
            lvl = next_level
    elif App().dmx.user[channel - 1] != -1:
        # User changed channel's value
        user_level = App().dmx.user[channel - 1]
        if next_level < user_level and pos <= wait + delay_out:
            lvl = old_level
        elif (
            next_level < user_level
            and wait + delay_out < pos < time_out + wait + delay_out
        ):
            lvl = user_level - abs(
                int(
                    round(((next_level - user_level) / time_out))
                    * (pos - wait - delay_out)
                )
            )
        elif next_level < user_level and pos >= time_out + wait + delay_out:
            lvl = next_level
    else:
        # Normal sequential
        if next_level < old_level and pos <= wait + delay_out:
            lvl = old_level
        elif (
            next_level < old_level
            and wait + delay_out < pos < time_out + wait + delay_out
        ):
            lvl = old_level - abs(
                int(
                    round(
                        ((next_level - old_level) / time_out) * (pos - wait - delay_out)
                    )
                )
            )
        elif next_level < old_level and pos >= time_out + wait + delay_out:
            lvl = next_level
    if lvl != -1:
        App().dmx.sequence[channel - 1] = lvl


def update_b(channel, old_level, next_level, wait, pos):
    """Update channel level with B Slider"""
    lvl = -1
    time_in = App().sequence.steps[App().sequence.position + 1].time_in * 1000
    delay_in = App().sequence.steps[App().sequence.position + 1].delay_in * 1000
    channel_time = App().sequence.steps[App().sequence.position + 1].channel_time
    if channel in channel_time and next_level > old_level:
        # Channel Time
        ct_delay = channel_time[channel].delay * 1000
        ct_time = channel_time[channel].time * 1000
        if pos < ct_delay + wait:
            lvl = old_level
        elif ct_delay + wait <= pos < ct_delay + ct_time + wait:
            lvl = int(
                round(((next_level - old_level) / ct_time) * (pos - ct_delay - wait))
                + old_level
            )
        elif pos >= ct_delay + ct_time + wait:
            lvl = next_level
    elif App().dmx.user[channel - 1] != -1:
        # User change channel's value
        user_level = App().dmx.user[channel - 1]
        if next_level > user_level and pos <= wait + delay_in:
            lvl = old_level
        elif (
            next_level > user_level
            and wait + delay_in < pos < time_in + wait + delay_in
        ):
            lvl = int(
                round(((next_level - user_level) / time_in) * (pos - wait - delay_in))
                + user_level
            )
        elif next_level > user_level and pos >= time_in + wait + delay_in:
            lvl = next_level
    else:
        # Normal channel
        if next_level > old_level and pos <= wait + delay_in:
            lvl = old_level
        elif (
            next_level > old_level and wait + delay_in < pos < time_in + wait + delay_in
        ):
            lvl = int(
                round(((next_level - old_level) / time_in) * (pos - wait - delay_in))
                + old_level
            )
        elif next_level > old_level and pos >= time_in + wait + delay_in:
            lvl = next_level
    if lvl != -1:
        App().dmx.sequence[channel - 1] = lvl
